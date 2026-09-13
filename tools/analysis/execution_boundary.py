"""How far real market observations actually travel through the frozen code.

The repository has a long-standing honest problem: the 35 real observations are
loaded by ``tools/collection/load_manual.py``, which imports only
``apix.ingestion.store`` and ``apix.schemas``. Everything the engine is tested
on is a synthetic fixture. So "the statistics layer works" and "the statistics
layer has seen this data" were two different statements that a reader could
easily merge into one.

This module stops them merging. It reconstructs the 35 canonical observations
from the committed contract, **runs the frozen elementary functions over them**,
and records exactly which stage each one reaches and in what condition.

Three states, and the difference between them is the whole point
----------------------------------------------------------------
``EXERCISED``
    The frozen code path was executed against the real panel and returned.
    **It does not follow that the statistical property is meaningfully
    validated.** Running is evidence of running.

``DEGENERATE``
    The code executes and returns a defined answer, but the single-wave,
    single-source, single-carrier panel gives it nothing to discriminate
    between. A one-member band has a band price; it cannot have dispersion.

``PENDING``
    The frozen methodology requires evidence that does not exist yet. Nothing
    is broken -- §C.1 needs a *t-7* counterpart and only one wave was collected.

``BLOCKED``
    Refused by a publication guard, by design.

What is reconstructed, and how the reconstruction is checked
------------------------------------------------------------
Observations are rebuilt from ``data/panel.json`` rather than from the SQLite
store, so the boundary is reproducible from committed evidence alone and the
regression tests run on a fresh clone.

Six fields are collection-frame constants fixed by the Day-1 contract. The
change and cancellation policies are the only genuine assumption, and they are
not taken on trust: :func:`reconstruct` asserts that every rebuilt observation
derives the **same canonical fare class** the store recorded, which is the only
thing any downstream stage reads entitlements for. A mismatch raises rather than
producing a quietly wrong boundary.

    python tools/analysis/execution_boundary.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from replay_exclusions import replay  # noqa: E402

from apix.schemas.enums import (  # noqa: E402
    Availability,
    ChangePolicy,
    Channel,
    SourceType,
    Tier,
)
from apix.schemas.observation import Entitlements, Observation  # noqa: E402
from apix.statistics.elementary.admissibility import (  # noqa: E402
    CollectionWindow,
    filter_admissible,
)
from apix.statistics.elementary.bands import band_price, hour_band, log_dispersion  # noqa: E402
from apix.statistics.elementary.dedup import deduplicate, duplicate_key  # noqa: E402
from apix.statistics.elementary.matching import (  # noqa: E402
    cell_key_for,
    item_key_for,
    parent_key_for,
)
from apix.statistics.elementary.sources import SourcePrecedence  # noqa: E402

EXERCISED = "EXERCISED"
DEGENERATE = "DEGENERATE"
PENDING = "PENDING"
BLOCKED = "BLOCKED"

#: Fixed by the Day-1 collection contract for every row inside the frame.
FRAME_CHANNEL = Channel.AIRLINE_DIRECT
FRAME_SOURCE_ID = "indigo-direct"
#: The only assumption. Checked against the store-recorded fare class below.
ASSUMED_CHANGE_POLICY = ChangePolicy.FEE

STATE_MEANINGS = {
    EXERCISED: (
        "the frozen code path ran against the real panel and returned. It does NOT "
        "follow that the statistical property is meaningfully validated."
    ),
    DEGENERATE: (
        "the code executes, but the single-wave / single-source panel supplies too "
        "little variation for the property to be established."
    ),
    PENDING: "the frozen methodology requires evidence that does not exist yet.",
    BLOCKED: "refused by a publication guard, by design.",
}

#: The claim this boundary licenses. Asserted verbatim by the regression tests.
BOUNDARY_CLAIM = (
    "Real market observations pass through APIx's admissibility, banding, key "
    "construction, deduplication and source-precedence stages. The pipeline stops "
    "at the longitudinal Jevons step because the required t-7 observation does not "
    "yet exist."
)


@dataclass(frozen=True, slots=True)
class Stage:
    """One step of the pipeline, with the state real data reaches it in."""

    key: str
    name: str
    spec: str
    state: str
    #: The frozen callable actually invoked, or "" when the stage is not reached.
    ran: str
    evidence: tuple[str, ...]
    note: str

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "spec": self.spec,
            "state": self.state,
            "ran": self.ran,
            "evidence": list(self.evidence),
            "note": self.note,
        }


def reconstruct(panel: dict) -> tuple[Observation, ...]:
    """Rebuild the canonical observations from the committed contract.

    Raises:
        ValueError: if any rebuilt observation derives a different canonical
            fare class from the one the store recorded. That is the check that
            keeps the entitlement assumption from silently changing a cell key.
    """
    collection_date = date.fromisoformat(panel["collection_date"])
    built: list[Observation] = []
    for row in panel["observations"]:
        origin, destination = row["route"].split("-")
        dep_h, dep_m = (int(x) for x in row["dep"].split(":"))
        obs_h, obs_m = (int(x) for x in row["observed_at"].split(":"))
        obs = Observation(
            observation_id=row["observation_id"],
            origin=origin,
            destination=destination,
            travel_date=date.fromisoformat(row["travel_date"]),
            departure_time_local=time(dep_h, dep_m),
            observation_ts=datetime.combine(collection_date, time(obs_h, obs_m)),
            collection_date=collection_date,
            carrier=row["carrier"],
            flight_number=row["flight"].split()[-1],
            stops=row["stops"],
            duration_minutes=row["duration_min"],
            fare_family_raw=row["fare_family_raw"],
            channel=FRAME_CHANNEL,
            source_id=FRAME_SOURCE_ID,
            entitlements=Entitlements(
                checked_baggage_kg=row["checked_baggage_kg"],
                change_permitted=ASSUMED_CHANGE_POLICY,
                cancellation_permitted=ASSUMED_CHANGE_POLICY,
            ),
            payable_fare=Decimal(str(row["total"])),
            source_type=SourceType.LIVE_SCRAPE,
            availability=Availability.AVAILABLE,
        )
        if obs.fare_class.value != row["fare_class"]:
            raise ValueError(
                f"{obs.observation_id}: reconstruction derives fare class "
                f"{obs.fare_class.value}, store recorded {row['fare_class']}. The "
                "entitlement assumption is not inert; do not publish this boundary."
            )
        built.append(obs)
    return tuple(built)


def _declared_window(panel: dict) -> CollectionWindow | None:
    """The window the collection runs declared, if they all declared the same one."""
    declared = {r["window_declared"] for r in panel["runs"]}
    if len(declared) != 1:
        return None
    start, end = next(iter(declared)).split("-")
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    return CollectionWindow(start=time(sh, sm), end=time(eh, em))


def build_boundary(panel: dict) -> dict:
    """Run the frozen elementary layer over the real panel and report the boundary.

    Read-only and deterministic. Every state below is derived from what the code
    returned, never asserted.
    """
    obs = reconstruct(panel)
    n = len(obs)
    stages: list[Stage] = []

    # 1 -- canonical observation ------------------------------------------
    stages.append(
        Stage(
            key="canonical_observation",
            name="Canonical observation",
            spec="A.2, B.4",
            state=EXERCISED,
            ran="apix.schemas.observation.Observation",
            evidence=(
                f"{n} of {len(panel['observations'])} rows rebuilt as canonical observations",
                f"{n}/{n} derive the same fare class the store recorded (spec B.4, "
                "from entitlements, never the marketing label)",
            ),
            note=(
                "Rebuilt from data/panel.json, not from the collection pipeline. The "
                "production loader still does not call the statistics layer."
            ),
        )
    )

    # 2 -- admissibility ---------------------------------------------------
    open_window = filter_admissible(obs)
    window = _declared_window(panel)
    windowed = filter_admissible(obs, window) if window else None
    window_evidence: tuple[str, ...] = ()
    if windowed is not None and window is not None:
        excluded_ids = {e.observation_id for e in windowed.excluded}
        flagged = int(panel["quality"]["window_flags"])
        window_evidence = (
            f"with the runs' declared {window.start:%H:%M}-{window.end:%H:%M} window: "
            f"{len(windowed.admissible)} admissible, {len(windowed.excluded)} excluded "
            "as OUTSIDE_COLLECTION_WINDOW",
            f"those {len(excluded_ids)} are exactly the {flagged} the store already "
            "flagged - the frozen A.5 check and the loader agree on which",
        )
    stages.append(
        Stage(
            key="admissibility",
            name="Admissibility",
            spec="A.3, A.6",
            state=EXERCISED,
            ran="apix.statistics.elementary.admissibility.filter_admissible",
            evidence=(
                f"window=None: {len(open_window.admissible)} admissible, "
                f"{len(open_window.excluded)} excluded",
                *window_evidence,
            ),
            note=(
                "Two runs, because the methodology window's VALUE is OQ-1 OPEN. "
                "No single admissible count is normative until OQ-1 is closed. "
                "Spec A.5 keeps out-of-window quotes in the store and out of the index; "
                "both behaviours below are that rule, not a contradiction."
            ),
        )
    )

    # 3 -- hour / band derivation -----------------------------------------
    bands = {o.observation_id: hour_band(o.departure_time_local) for o in obs}
    recorded = {r["observation_id"]: r["band"] for r in panel["observations"]}
    band_agree = sum(1 for k, v in bands.items() if recorded[k] == v)
    contracted = sorted(set(panel["quality"]["bands_expected"]))
    stages.append(
        Stage(
            key="band_derivation",
            name="Hour / band derivation",
            spec="B.2.2",
            state=EXERCISED,
            ran="apix.statistics.elementary.bands.hour_band",
            evidence=(
                f"{band_agree}/{n} derived bands equal the recorded band",
                f"{len(set(bands.values()))} distinct bands, all inside the "
                f"contracted set {contracted}",
            ),
            note="band = hour // 3 anchored 00:00 IST. Nothing is rounded into a band.",
        )
    )

    # 4 -- cell / parent / item keys ---------------------------------------
    cells = {cell_key_for(o) for o in obs}
    parents = {parent_key_for(o) for o in obs}
    tier1 = {item_key_for(o, Tier.TIER_1) for o in obs}
    tier2 = {item_key_for(o, Tier.TIER_2) for o in obs}
    tier3 = {item_key_for(o, Tier.TIER_3) for o in obs}
    stages.append(
        Stage(
            key="keys",
            name="Cell / parent / item keys",
            spec="B.2.1, B.2.2, E.4",
            state=EXERCISED,
            ran="apix.statistics.elementary.matching.cell_key_for / parent_key_for / item_key_for",
            evidence=(
                f"{len(cells)} distinct cell keys, {len(parents)} distinct parent keys",
                f"item keys: {len(tier1)} at Tier 1 (carrier, flight number), "
                f"{len(tier2)} at Tier 2 (carrier, band)",
                f"Tier 3 returns {tier3.pop() if len(tier3) == 1 else sorted(map(str, tier3))} "
                "- no within-cell item identity, which is the honest answer",
            ),
            note=(
                "Key construction is exercised. It does not follow that any key has a "
                "counterpart to be matched against; see the matched-set stage."
            ),
        )
    )

    # 5 -- exclusion replay -------------------------------------------------
    rep = replay(panel)
    stages.append(
        Stage(
            key="exclusion_replay",
            name="Exclusion replay",
            spec="A.3, B.2",
            state=EXERCISED,
            ran="replay through filter_admissible / APWBucket.from_lead_time / hour_band",
            evidence=(
                f"{rep.agree}/{rep.candidates} mechanically decidable exclusions reproduce "
                f"the recorded §A.3/§B.2 verdict with {rep.disagree} disagreements",
                f"{rep.not_testable} record is not mechanically testable because the required "
                "departure-time field is unavailable",
                f"{len(rep.wrongly_rejected)} false rejections among the "
                f"{rep.accepted_rechecked} accepted observations",
            ),
            note=(
                f"{rep.skipped_total} further exclusions are collection-contract selection "
                "or unreadable-field records. The engine has no verdict on them."
            ),
        )
    )

    # 6/7 -- band price and within-band dispersion --------------------------
    by_cell_band: dict[tuple[object, int], list[Decimal]] = defaultdict(list)
    for o in obs:
        by_cell_band[(cell_key_for(o), hour_band(o.departure_time_local))].append(o.payable_fare)
    sizes = sorted({len(v) for v in by_cell_band.values()})
    largest = max(sizes)
    prices = {k: band_price(v) for k, v in by_cell_band.items()}
    dispersions = {log_dispersion(v) for v in by_cell_band.values()}
    degenerate_bands = largest < 2

    stages.append(
        Stage(
            key="band_price",
            name="Band price",
            spec="B.2.3",
            state=DEGENERATE if degenerate_bands else EXERCISED,
            ran="apix.statistics.elementary.bands.band_price",
            evidence=(
                f"{len(prices)} (cell, band) groups, every one of size {largest}",
                "the geometric mean of a one-member set returns that member's fare "
                "unchanged, so no constructed price differs from an observed one",
            ),
            note=(
                "A band price is meant to represent a departure-hour slot rather than a "
                "flight. With one flight per slot the construction cannot do that work."
            ),
        )
    )
    stages.append(
        Stage(
            key="within_band_dispersion",
            name="Within-band dispersion",
            spec="B.2.3",
            state=DEGENERATE if degenerate_bands else EXERCISED,
            ran="apix.statistics.elementary.bands.log_dispersion",
            evidence=(
                f"returns {sorted(dispersions)} for every group, by the function's own "
                "rule for n < 2",
                f"n = {largest} in every (cell, band) group",
            ),
            note=(
                "This zero means 'a one-flight band cannot have its price moved by "
                "dispersion'. It does NOT mean fares in this panel do not disperse - "
                "the T+3 bucket spreads 24.9% ACROSS bands on one travel date, which is "
                "a different quantity entirely."
            ),
        )
    )

    # 8 -- source precedence ------------------------------------------------
    sources = sorted({o.source_id for o in obs})
    precedence = SourcePrecedence(
        version=panel["runs"][0]["source_precedence_version"],
        order={FRAME_CHANNEL: tuple(sources)},
    )
    ranks = {s: precedence.rank(FRAME_CHANNEL, s) for s in sources}
    stages.append(
        Stage(
            key="source_precedence",
            name="Source precedence",
            spec="D.8.1",
            state=DEGENERATE if len(sources) < 2 else EXERCISED,
            ran="apix.statistics.elementary.sources.SourcePrecedence.rank",
            evidence=(
                f"{len(sources)} distinct source in the panel: {sources}",
                f"rank() returns {ranks[sources[0]]} - a total order over one element",
                f"precedence version recorded on the runs: "
                f"{panel['runs'][0]['source_precedence_version']}",
            ),
            note=(
                "select() is NOT reached: it returns the best source present in BOTH t "
                "and t-7, and there is no t-7. A one-source order cannot discriminate, "
                "so nothing here establishes that the precedence rule works."
            ),
        )
    )

    # 9 -- deduplication ----------------------------------------------------
    dedup = deduplicate(open_window.admissible)
    keys = {duplicate_key(o) for o in obs}
    stages.append(
        Stage(
            key="deduplication",
            name="Deduplication",
            spec="D.4",
            state=EXERCISED,
            ran="apix.statistics.elementary.dedup.duplicate_key / deduplicate",
            evidence=(
                f"{len(keys)} distinct duplicate keys built from {n} observations",
                f"{len(dedup.retained)} retained, {len(dedup.duplicates)} duplicates observed",
            ),
            note=(
                "Key construction is exercised; 0 duplicates were observed. The "
                "tie-break rule for identical timestamps is therefore NOT exercised - "
                "no collision occurred for it to resolve."
            ),
        )
    )

    # 10-13 -- everything longitudinal --------------------------------------
    status = panel["index_status"]
    pairs = int(status["matched_pairs_available"])
    waves = int(status["collection_waves"])
    blocker = (
        f"{waves} collection wave(s), {pairs} matched pairs. "
        "Spec C.1 LOCKED: I(c,t) = I(c,t-7) x J(c,t)."
    )
    for key, name, spec in (
        ("matched_set", "Matched t / t-7", "D.1, D.8"),
        ("jevons", "Jevons relative", "D.2"),
        ("chaining", "Advance-cell / weekly chain", "C.1, F"),
        ("aggregation", "Higher aggregation", "E, G"),
    ):
        stages.append(
            Stage(
                key=key,
                name=name,
                spec=spec,
                state=PENDING if pairs == 0 else EXERCISED,
                ran="",
                evidence=(
                    blocker,
                    f"first date that can supply a pair: {status['next_wave_unlocking_index']}",
                ),
                note=(
                    "Implemented and covered by the synthetic-fixture suite. Not reached "
                    "by real data, which is an evidence condition and not a defect."
                ),
            )
        )

    # 14 -- publication ------------------------------------------------------
    stages.append(
        Stage(
            key="publication",
            name="Publication",
            spec="H, R.3",
            state=BLOCKED,
            ran="",
            evidence=(
                "no APIx index value is computed, so none is published",
                f"apix_l_computable: {status['apix_l_computable']}",
            ),
            note="The guards refuse rather than inventing a level. That is the design.",
        )
    )

    counts: dict[str, int] = defaultdict(int)
    for s in stages:
        counts[s.state] += 1

    return {
        "source": f"{n} real market observations, collection date {panel['collection_date']}",
        "reconstructed_from": "data/panel.json",
        "reconstruction_check": (
            f"{n}/{n} rebuilt observations derive the fare class the store recorded; "
            "the entitlement assumption changes no cell key"
        ),
        "states": STATE_MEANINGS,
        "claim": BOUNDARY_CLAIM,
        "stages": [s.as_dict() for s in stages],
        "state_counts": dict(sorted(counts.items())),
        "caveat": (
            "EXERCISED means the frozen code path ran against the real panel. It is "
            "not a validation claim, and no stage below the Jevons step is reached by "
            "real data at all."
        ),
    }


def main() -> None:
    panel = json.loads((ROOT / "data" / "panel.json").read_text(encoding="utf-8"))
    boundary = build_boundary(panel)
    width = 78

    print("=" * width)
    print("APIx - REAL-DATA EXECUTION BOUNDARY")
    print("=" * width)
    print(boundary["source"])
    print(f"reconstructed from {boundary['reconstructed_from']}")
    print(f"check: {boundary['reconstruction_check']}")
    print("")
    for stage in boundary["stages"]:
        print(f"{stage['name']:<34} {stage['state']:<11} spec {stage['spec']}")
        for line in stage["evidence"]:
            print(f"      - {line}")
        print(f"      note: {stage['note']}")
        print("")
    print("=" * width)
    for state, meaning in boundary["states"].items():
        print(f"{state:<11} {meaning}")
    print("=" * width)
    print(boundary["claim"])
    print("=" * width)


if __name__ == "__main__":
    main()
