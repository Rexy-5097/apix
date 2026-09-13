"""Replay recorded exclusions through the FROZEN admissibility and band code.

The 122 exclusions were decided by human triage plus loader logic. The frozen
statistics layer never saw them: ``tools/collection/load_manual.py`` imports
only ``apix.ingestion.store`` and ``apix.schemas``, so "we excluded 122
screenshots for these reasons" was, until this module, a **human claim**.

This feeds the recorded candidates back through the same spec A.3 and spec B.2
code the engine uses and asks whether the engine independently reaches the
recorded verdict.

Two recorded reasons are mechanically decidable and are replayed::

    APW_MATCHES_NO_BUCKET      spec A.3 -- exact lead-time match, no rounding
    OUTSIDE_CONTRACTED_BANDS   spec B.2 -- band = hour // 3, contract bands 2-6

The other three are **not** replayed, and that is not a gap to be closed.
``NOT_EARLIEST_IN_BAND`` is a *collection-contract selection* rule, not an
admissibility rule -- the engine has no opinion on it. ``DEP_TIME_NOT_READABLE``
and ``INSUFFICIENT_EVIDENCE`` record that a field could not be read at all, so
there is nothing to reconstruct and nothing may be invented to stand in for it.

**Coverage is reported per check, never as one number.** The retained records
support the checks unevenly: every candidate carries a lead time, most carry a
departure time, and only a few carry the full field set a canonical
``Observation`` requires. A flat "46 replayed" would overstate the weakest of
the three.

What is reconstructed, and what is assumed
------------------------------------------
:func:`build_observation` takes ``travel_date``, ``flight_no``, ``dep``,
``dur_min``, ``total`` and the baggage flag from the recorded row, and refuses
to build at all if any is absent. The remaining fields are **collection-frame
constants**, not per-row facts: the Day-1 contract fixes DEL-BOM / 6E /
AIRLINE_DIRECT / ``indigo-direct`` / Saver for every row in the frame.

The change and cancellation policies are the one genuine assumption. They are
set to ``FEE``, disclosed rather than hidden, and
``test_assumed_change_policy_does_not_move_any_admissibility_verdict`` asserts
that no verdict here turns on the choice.

The 35 accepted observations are replayed too. A rejection rule that also
rejects the accepted panel would be worthless, so a run is only meaningful if
the engine admits all 35.

Read-only: nothing here writes to the store, the panel or the methodology.

    python tools/analysis/replay_exclusions.py
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from apix.schemas.enums import (  # noqa: E402
    APWBucket,
    Availability,
    ChangePolicy,
    Channel,
    SourceType,
)
from apix.schemas.observation import Entitlements, Observation  # noqa: E402
from apix.statistics.elementary.admissibility import filter_admissible  # noqa: E402
from apix.statistics.elementary.bands import hour_band  # noqa: E402

EXTRACT = ROOT / "collection-input" / "extract"
PANEL = ROOT / "data" / "panel.json"

#: Spec B.2 bands the Day-1 collection contract covers.
CONTRACT_BANDS = frozenset({2, 3, 4, 5, 6})
COLLECTION_DATE = date(2026, 9, 12)

#: Recorded reason -> the frozen rule that should independently reject it.
MECHANICAL = {
    "APW_MATCHES_NO_BUCKET": "A.3",
    "OUTSIDE_CONTRACTED_BANDS": "B.2",
}

#: Why each remaining reason is deliberately not replayed.
NOT_MECHANICAL = {
    "NOT_EARLIEST_IN_BAND": (
        "collection-contract selection rule, not a spec A admissibility rule -- "
        "the engine has no verdict to reach"
    ),
    "DEP_TIME_NOT_READABLE": (
        "the departure time was never readable, so there is nothing to reconstruct "
        "and nothing may be invented in its place"
    ),
    "INSUFFICIENT_EVIDENCE": (
        "the flight row scrolled off; no flight number and no times were captured"
    ),
}

#: Fixed by the Day-1 collection contract for every row inside the frame.
FRAME_ORIGIN = "DEL"
FRAME_DESTINATION = "BOM"
FRAME_CARRIER = "6E"
FRAME_FARE_FAMILY = "Saver fare"
FRAME_CHANNEL = Channel.AIRLINE_DIRECT
FRAME_SOURCE_ID = "indigo-direct"

#: The one genuine assumption. Asserted inert by the replay regression tests.
ASSUMED_CHANGE_POLICY = ChangePolicy.FEE


def _count(n: int) -> str:
    """Spell a small count in the public statement; "zero" reads harder than "0"."""
    return "zero" if n == 0 else str(n)


@dataclass(frozen=True, slots=True)
class GroupReplay:
    """One recorded exclusion reason, replayed through its frozen rule."""

    label: str
    reason: str
    spec: str
    candidates: int
    #: Field coverage -- what the retained records can support, per check.
    apw_testable: int
    band_testable: int
    reconstructable: int
    #: Outcome of this group's own check.
    agree: int
    disagree: int
    not_testable: int
    mismatches: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "reason": self.reason,
            "spec": self.spec,
            "candidates": self.candidates,
            "apw_testable": self.apw_testable,
            "band_testable": self.band_testable,
            "reconstructable_as_observation": self.reconstructable,
            "agree": self.agree,
            "disagree": self.disagree,
            "not_testable": self.not_testable,
            "mismatches": list(self.mismatches),
        }


@dataclass(frozen=True, slots=True)
class SkippedGroup:
    """A recorded reason the engine is deliberately not asked to adjudicate."""

    label: str
    reason: str
    count: int
    why: str

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "reason": self.reason,
            "count": self.count,
            "why": self.why,
        }


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """The whole replay, as data. Every published figure is a field here."""

    groups: tuple[GroupReplay, ...]
    skipped: tuple[SkippedGroup, ...]
    accepted_rechecked: int
    wrongly_rejected: tuple[str, ...]
    reconstructable: int
    not_reconstructable: int
    spec_a_admitted: int
    spec_a_rejected: int
    spec_a_reject_reasons: tuple[str, ...]

    @property
    def candidates(self) -> int:
        return sum(g.candidates for g in self.groups)

    @property
    def agree(self) -> int:
        return sum(g.agree for g in self.groups)

    @property
    def disagree(self) -> int:
        return sum(g.disagree for g in self.groups)

    @property
    def not_testable(self) -> int:
        return sum(g.not_testable for g in self.groups)

    @property
    def skipped_total(self) -> int:
        return sum(s.count for s in self.skipped)

    def as_dict(self) -> dict:
        return {
            "groups": [g.as_dict() for g in self.groups],
            "skipped": [s.as_dict() for s in self.skipped],
            "candidates": self.candidates,
            "agree": self.agree,
            "disagree": self.disagree,
            "not_testable": self.not_testable,
            "skipped_total": self.skipped_total,
            "accepted_rechecked": self.accepted_rechecked,
            "wrongly_rejected": list(self.wrongly_rejected),
            "reconstructable_as_observation": self.reconstructable,
            "not_reconstructable": self.not_reconstructable,
            "spec_a_admitted": self.spec_a_admitted,
            "spec_a_rejected": self.spec_a_rejected,
            "spec_a_reject_reasons": list(self.spec_a_reject_reasons),
            # The agreed public wording. Generated from the fields above rather
            # than typed, so the sentence cannot outlive the numbers in it.
            "statement": (
                f"{self.agree}/{self.candidates} mechanically decidable exclusions "
                "reproduce the recorded §A.3/§B.2 verdict with "
                f"{_count(self.disagree)} disagreements; {self.not_testable} record is not "
                "mechanically testable because the required departure-time field is "
                f"unavailable. All {self.accepted_rechecked} accepted observations pass the "
                f"corresponding checks with {_count(len(self.wrongly_rejected))} false "
                "rejections."
            ),
            "scope_note": (
                f"{self.skipped_total} further recorded exclusions are collection-contract "
                "selection or unreadable-field records. The engine has no verdict on them "
                "and none is claimed."
            ),
        }


def load_panel() -> dict:
    return json.loads(PANEL.read_text(encoding="utf-8"))


def load_candidates() -> tuple[dict, dict]:
    """The recorded rows, and the recorded exclusion decisions."""
    raw = {r["shot"]: r for r in json.loads((EXTRACT / "panel_raw.json").read_text("utf-8"))}
    exclusions = json.loads((EXTRACT / "exclusions.json").read_text("utf-8"))
    return raw, exclusions


def reason_of(label: str) -> str | None:
    """Map a recorded label onto the mechanical rule that should decide it."""
    for key in MECHANICAL:
        if label.startswith(key):
            return key
    return None


def skip_reason_of(label: str) -> tuple[str, str] | None:
    for key, why in NOT_MECHANICAL.items():
        if label.startswith(key):
            return key, why
    return None


def check_apw(row: dict) -> tuple[bool | None, str]:
    """Spec A.3 -- assignment is by EXACT lead time; nothing is rounded in."""
    lead = row.get("lead_time_days")
    if lead in (None, ""):
        return None, "no lead time recorded"
    bucket = APWBucket.from_lead_time(int(lead))
    if bucket is None:
        return True, f"T+{lead} matches no A.3 bucket -> inadmissible"
    return False, f"T+{lead} -> bucket {bucket.value} (admissible)"


def check_band(row: dict) -> tuple[bool | None, str]:
    """Spec B.2 -- band = hour // 3, anchored 00:00 IST."""
    dep = row.get("dep")
    if dep in (None, ""):
        return None, "no departure time recorded"
    hh, mm = (int(x) for x in str(dep).split(":"))
    band = hour_band(time(hh, mm))
    if band not in CONTRACT_BANDS:
        return True, f"dep {dep} -> band {band}, outside contract bands 2-6"
    return False, f"dep {dep} -> band {band} (inside contract)"


def build_observation(
    row: dict, change_policy: ChangePolicy = ASSUMED_CHANGE_POLICY
) -> Observation | None:
    """A canonical Observation, or None when a per-row field is absent.

    Deliberately strict about the *row*: a value that was never read is not
    invented, so an incomplete record is reported as not-reconstructable rather
    than filled with a plausible default. The frame constants are a different
    thing -- the Day-1 contract fixes them for every row it covers -- and
    ``change_policy`` is a parameter so a test can prove no verdict turns on it.
    """
    need = ("travel_date", "flight_no", "dep", "dur_min", "total")
    if any(row.get(f) in (None, "", []) for f in need):
        return None
    hh, mm = (int(x) for x in str(row["dep"]).split(":"))
    return Observation(
        observation_id=f"replay-{row['shot']}",
        origin=FRAME_ORIGIN,
        destination=FRAME_DESTINATION,
        travel_date=date.fromisoformat(row["travel_date"]),
        departure_time_local=time(hh, mm),
        observation_ts=datetime.fromisoformat(row["captured"]),
        collection_date=COLLECTION_DATE,
        carrier=FRAME_CARRIER,
        flight_number=str(row["flight_no"]),
        stops=0 if row.get("non_stop") else 1,
        duration_minutes=int(row["dur_min"]),
        fare_family_raw=FRAME_FARE_FAMILY,
        channel=FRAME_CHANNEL,
        source_id=FRAME_SOURCE_ID,
        entitlements=Entitlements(
            checked_baggage_kg=15 if row.get("checked_bag_15") else 0,
            change_permitted=change_policy,
            cancellation_permitted=change_policy,
        ),
        payable_fare=Decimal(str(row["total"])),
        source_type=SourceType.LIVE_SCRAPE,
        availability=Availability.AVAILABLE,
    )


def _coverage(rows: list[dict | None]) -> tuple[int, int, int]:
    """How many of these records each check can actually reach."""
    apw = sum(1 for r in rows if r is not None and r.get("lead_time_days") not in (None, ""))
    band = sum(1 for r in rows if r is not None and r.get("dep") not in (None, ""))
    full = sum(1 for r in rows if r is not None and build_observation(r) is not None)
    return apw, band, full


def replay(panel: dict) -> ReplayResult:
    """Run every recorded candidate back through the frozen rules.

    Pure and deterministic: it reads two committed JSON files plus the panel
    contract handed in, and returns data. Nothing is written anywhere.
    """
    raw, exclusions = load_candidates()

    groups: list[GroupReplay] = []
    skipped: list[SkippedGroup] = []

    for label, shots in exclusions.items():
        reason = reason_of(label)
        if reason is None:
            skip = skip_reason_of(label)
            if skip is None:
                raise ValueError(f"unclassified exclusion reason: {label!r}")
            key, why = skip
            skipped.append(SkippedGroup(label=label, reason=key, count=len(shots), why=why))
            continue

        rows = [raw.get(shot) for shot in shots]
        apw_n, band_n, full_n = _coverage(rows)
        check: Callable[[dict], tuple[bool | None, str]] = (
            check_apw if reason == "APW_MATCHES_NO_BUCKET" else check_band
        )

        agree = disagree = untestable = 0
        mismatches: list[str] = []
        for shot, row in zip(shots, rows, strict=True):
            if row is None:
                untestable += 1
                continue
            rejected, why = check(row)
            if rejected is None:
                untestable += 1
            elif rejected:
                agree += 1
            else:
                disagree += 1
                mismatches.append(f"{shot}: recorded {reason}, engine says {why}")

        groups.append(
            GroupReplay(
                label=label,
                reason=reason,
                spec=MECHANICAL[reason],
                candidates=len(shots),
                apw_testable=apw_n,
                band_testable=band_n,
                reconstructable=full_n,
                agree=agree,
                disagree=disagree,
                not_testable=untestable,
                mismatches=tuple(mismatches),
            )
        )

    # -- control: the same rules must ADMIT every accepted observation -------
    wrongly_rejected: list[str] = []
    for obs in panel["observations"]:
        if APWBucket.from_lead_time(obs["apw"]) is None:
            wrongly_rejected.append(f"{obs['observation_id']}: A.3 rejects T+{obs['apw']}")
        hh, mm = (int(x) for x in obs["dep"].split(":"))
        if hour_band(time(hh, mm)) not in CONTRACT_BANDS:
            wrongly_rejected.append(f"{obs['observation_id']}: B.2 band outside contract")

    # -- the full canonical path, wherever the retained fields reach it ------
    built = unbuildable = admitted = 0
    reject_reasons: set[str] = set()
    for label, shots in exclusions.items():
        if reason_of(label) is None:
            continue
        for shot in shots:
            row = raw.get(shot)
            candidate = build_observation(row) if row is not None else None
            if candidate is None:
                unbuildable += 1
                continue
            built += 1
            result = filter_admissible([candidate])
            if result.admissible:
                admitted += 1
            else:
                reject_reasons.update(e.reason.value for e in result.excluded)

    return ReplayResult(
        groups=tuple(groups),
        skipped=tuple(skipped),
        accepted_rechecked=len(panel["observations"]),
        wrongly_rejected=tuple(wrongly_rejected),
        reconstructable=built,
        not_reconstructable=unbuildable,
        spec_a_admitted=admitted,
        spec_a_rejected=built - admitted,
        spec_a_reject_reasons=tuple(sorted(reject_reasons)),
    )


def rule(ch: str = "-", n: int = 78) -> str:
    return ch * n


def main() -> None:
    result = replay(load_panel())
    w = print

    w(rule("="))
    w("APIx - EXCLUSION REPLAY through the frozen A.3 / B.2 code")
    w(rule("="))
    w("Recorded verdicts were made by human triage + loader logic. This asks")
    w("whether the frozen engine independently agrees.")
    w("")

    for g in result.groups:
        w(rule())
        w(f"{g.label}   ({g.candidates} shots)   -> spec {g.spec}")
        w(rule())
        w(
            f"  field coverage: A.3-testable {g.apw_testable}   "
            f"B.2-testable {g.band_testable}   full Observation {g.reconstructable}"
        )
        w(f"  engine agrees {g.agree}   disagrees {g.disagree}   not testable {g.not_testable}")
        for m in g.mismatches:
            w(f"    MISMATCH {m}")
        w("")

    for s in result.skipped:
        w(f"SKIPPED  {s.label}  ({s.count} shots)")
        w(f"         {s.why}")
        w("")

    w(rule())
    w(f"CONTROL - the {result.accepted_rechecked} accepted observations must NOT be rejected")
    w(rule())
    w(f"  accepted observations re-checked : {result.accepted_rechecked}")
    w(f"  wrongly rejected by the engine   : {len(result.wrongly_rejected)}")
    for m in result.wrongly_rejected[:5]:
        w(f"     {m}")
    w("")

    w(rule())
    w("FULL ADMISSIBILITY - canonical Observation + filter_admissible (spec A)")
    w(rule())
    w(f"  reconstructable as Observation : {result.reconstructable}")
    w(f"  not reconstructable            : {result.not_reconstructable}  (a field was never read)")
    w(f"  of those built, spec A admits  : {result.spec_a_admitted}")
    w(f"  of those built, spec A rejects : {result.spec_a_rejected}")
    w(f"  rejection reasons              : {', '.join(result.spec_a_reject_reasons) or 'none'}")
    w("")
    w("  Both outcomes are correct, and the split is the interesting part:")
    w("")
    w("    REJECTED  the T+68 rows, with ExclusionReason.LEAD_TIME_MATCHES_NO_BUCKET.")
    w("              filter_admissible enforces A.3 itself, so the full canonical")
    w("              path reaches the recorded verdict independently.")
    w("")
    w("    ADMITTED  the band-1 / band-7 rows. This is NOT a disagreement.")
    w("              Being outside bands 2-6 is a COLLECTION-CONTRACT scope rule,")
    w("              not a spec A admissibility rule: those fares are real and")
    w("              admissible, they simply sit outside what Day-1 collects.")
    w("              The contract rule is the B.2 check above, which agreed.")
    w("")

    w(rule("="))
    w("SUMMARY")
    w(rule("="))
    w(f"  mechanically decidable candidates : {result.candidates}")
    w(f"  engine AGREES with recorded verdict: {result.agree}")
    w(f"  engine DISAGREES                  : {result.disagree}")
    w(f"  not testable (field never read)   : {result.not_testable}")
    w(f"  accepted panel wrongly rejected   : {len(result.wrongly_rejected)}")
    w(f"  deliberately not replayed         : {result.skipped_total}")
    w(rule("="))


if __name__ == "__main__":
    main()
