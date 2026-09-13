"""Regression tests for the exclusion replay and the real-data execution boundary.

Two claims in this repository are unusual in that they are *about the
repository's own honesty*, which makes them exactly the claims most worth
pinning down:

1. **The exclusion replay.** "We excluded 122 screenshots for these reasons" is
   a human claim until the frozen code independently reaches the same verdict.
   These tests fix the exact counts so the claim cannot quietly drift — not
   ``~46``, not "most", but 24/24, 15/16, 6/6.

2. **The execution boundary.** ``EXERCISED`` must mean the frozen code path ran
   against the real panel, and must never be allowed to slide into meaning
   "validated". Several tests below exist only to keep that distinction from
   eroding in the prose.

Everything here runs from committed evidence — ``data/panel.json`` and
``collection-input/extract/`` — so it works on a fresh clone with no SQLite
store present.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "analysis"))

from execution_boundary import (  # noqa: E402
    BLOCKED,
    BOUNDARY_CLAIM,
    DEGENERATE,
    EXERCISED,
    PENDING,
    build_boundary,
    reconstruct,
)
from replay_exclusions import (  # noqa: E402
    ASSUMED_CHANGE_POLICY,
    build_observation,
    load_candidates,
    load_panel,
    replay,
)

from apix.schemas.enums import ChangePolicy  # noqa: E402
from apix.statistics.elementary.admissibility import filter_admissible  # noqa: E402

#: The recorded exclusion groups the engine is asked to adjudicate, and the
#: exact outcome each must produce. Hand-checked against the screenshots.
T68 = "APW_MATCHES_NO_BUCKET (T+68, spec A.3 exact match)"
BAND_7 = "OUTSIDE_CONTRACTED_BANDS (band 7)"
BAND_1 = "OUTSIDE_CONTRACTED_BANDS (band 1)"

#: The one record no rule can decide: band 7 was read off the screenshot, but
#: the departure time itself never was, so spec B.2 has no input.
UNTESTABLE_SHOT = "s116"

EXPECTED_ACCEPTED = 35


@pytest.fixture(scope="module")
def panel() -> dict:
    return load_panel()


@pytest.fixture(scope="module")
def result(panel: dict):
    return replay(panel)


@pytest.fixture(scope="module")
def groups(result) -> dict:
    return {g.label: g for g in result.groups}


@pytest.fixture(scope="module")
def boundary(panel: dict) -> dict:
    return build_boundary(panel)


# ── 1. the replay reproduces the recorded verdicts, exactly ──────────────────


def test_all_24_t68_records_reproduce_the_recorded_a3_verdict(groups: dict) -> None:
    """Spec A.3 assigns by EXACT lead time. T+68 matches no bucket, and must not."""
    g = groups[T68]
    assert (g.candidates, g.agree, g.disagree, g.not_testable) == (24, 24, 0, 0)
    assert g.spec == "A.3"


def test_15_of_16_band_7_records_reproduce_the_recorded_b2_verdict(groups: dict) -> None:
    g = groups[BAND_7]
    assert (g.candidates, g.agree, g.disagree, g.not_testable) == (16, 15, 0, 1)
    assert g.spec == "B.2"


def test_all_6_band_1_records_reproduce_the_recorded_b2_verdict(groups: dict) -> None:
    g = groups[BAND_1]
    assert (g.candidates, g.agree, g.disagree, g.not_testable) == (6, 6, 0, 0)
    assert g.spec == "B.2"


def test_exactly_one_record_is_untestable_and_it_is_the_one_with_no_departure_time(
    result, groups: dict
) -> None:
    """The single gap is a missing field, not a rule that failed to fire.

    ``s116`` carries a lead time — so spec A.3 *can* see it — but its departure
    time was never readable, so spec B.2 has nothing to band. Reconstructing one
    would be inventing the evidence the record exists to say is absent.
    """
    assert result.not_testable == 1
    assert groups[BAND_7].not_testable == 1

    raw, _ = load_candidates()
    row = raw[UNTESTABLE_SHOT]
    assert row["dep"] in (None, ""), "the untestable record must be untestable because of a gap"
    assert row["lead_time_days"] == 60, "and it must still be A.3-visible, which is why 16 != 15"

    # It is the only such record *in the groups spec B.2 adjudicates*. Seven
    # T+68 records also lack a departure time and are still fully testable,
    # because spec A.3 reads the lead time and never the clock — which is why
    # coverage has to be reported per check and not as one number.
    b2_missing = [s for label in (BAND_7, BAND_1) for s in _shots(label) if not raw[s]["dep"]]
    assert b2_missing == [UNTESTABLE_SHOT]

    a3_missing = [s for s in _shots(T68) if not raw[s]["dep"]]
    assert len(a3_missing) == 7
    assert groups[T68].not_testable == 0, "a missing clock does not blind spec A.3"


def test_the_replay_produces_zero_disagreements(result) -> None:
    """The headline. A single disagreement invalidates the exclusion audit."""
    assert result.disagree == 0
    assert [m for g in result.groups for m in g.mismatches] == []
    assert (result.candidates, result.agree, result.not_testable) == (46, 45, 1)


# ── 2. the control: the same rules must ADMIT the accepted panel ─────────────


def test_no_accepted_observation_is_falsely_rejected(result) -> None:
    """A rule that rejects everything proves nothing. This is the other half."""
    assert result.accepted_rechecked == EXPECTED_ACCEPTED
    assert result.wrongly_rejected == ()


def test_the_full_canonical_path_splits_as_expected(result) -> None:
    """9 records carry enough fields for a canonical Observation; 5 admit, 4 reject.

    The split is not a disagreement and the distinction matters: spec A
    adjudicates *admissibility*, and being outside the contracted bands is a
    **collection-contract scope** rule, not an admissibility one. So the band-1
    and band-7 rows are correctly admitted by ``filter_admissible`` while the
    T+68 rows are correctly rejected by it.
    """
    assert (result.reconstructable, result.not_reconstructable) == (9, 37)
    assert (result.spec_a_admitted, result.spec_a_rejected) == (5, 4)
    assert result.spec_a_reject_reasons == ("LEAD_TIME_MATCHES_NO_BUCKET",)


def test_coverage_is_reported_per_check_and_never_as_one_number(groups: dict) -> None:
    """Each rule reaches a different number of records. A flat total overstates it."""
    assert (groups[T68].apw_testable, groups[T68].band_testable) == (24, 17)
    assert (groups[BAND_7].apw_testable, groups[BAND_7].band_testable) == (16, 15)
    assert (groups[BAND_1].apw_testable, groups[BAND_1].band_testable) == (6, 6)
    assert sum(g.reconstructable for g in groups.values()) == 9


# ── 3. the reasons deliberately NOT replayed ────────────────────────────────


def test_selection_and_unreadable_reasons_are_skipped_not_silently_passed(result) -> None:
    """67 + 8 + 1. The engine has no verdict on these and none is claimed."""
    skipped = {s.reason: s.count for s in result.skipped}
    assert skipped == {
        "NOT_EARLIEST_IN_BAND": 67,
        "DEP_TIME_NOT_READABLE": 8,
        "INSUFFICIENT_EVIDENCE": 1,
    }
    assert result.skipped_total == 76
    assert result.candidates + result.skipped_total == 122


# ── 4. determinism and read-only-ness ───────────────────────────────────────


def test_the_replay_is_deterministic_across_repeated_runs(panel: dict) -> None:
    """Spec P.2. Two runs over the same evidence must be byte-identical."""
    first = json.dumps(replay(panel).as_dict(), sort_keys=True)
    second = json.dumps(replay(panel).as_dict(), sort_keys=True)
    assert first == second


def test_the_boundary_is_deterministic_across_repeated_runs(panel: dict) -> None:
    first = json.dumps(build_boundary(panel), sort_keys=True)
    second = json.dumps(build_boundary(panel), sort_keys=True)
    assert first == second


#: Everything the replay and the boundary are forbidden to touch.
PROTECTED = (
    "data/panel.json",
    "data/dashboard.html",
    "data/panel_report.txt",
    "data/engine-validation.html",
    "data/mospi_cpi_airfare.json",
    "docs/methodology/apix_formula_spec_v2_1.md",
    "collection-input/extract/panel_raw.json",
    "collection-input/extract/exclusions.json",
)


def _digest() -> dict[str, str]:
    return {
        p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
        for p in PROTECTED
        if (ROOT / p).exists()
    }


def test_neither_tool_mutates_the_store_panel_artifacts_or_methodology(panel: dict) -> None:
    """Read-only is a property to assert, not a promise to make in a docstring."""
    before = _digest()
    assert len(before) == len(PROTECTED), "a protected file is missing; the guard would pass blind"

    replay(panel)
    build_boundary(panel)
    reconstruct(panel)

    assert _digest() == before

    store = ROOT / "data" / "collection"
    if store.exists():
        # The SQLite store is gitignored, so it may be absent on a fresh clone.
        # When it is present it must come through untouched as well.
        after = {f.name: f.stat().st_mtime_ns for f in sorted(store.rglob("*")) if f.is_file()}
        replay(panel)
        build_boundary(panel)
        assert {
            f.name: f.stat().st_mtime_ns for f in sorted(store.rglob("*")) if f.is_file()
        } == after


# ── 5. the entitlement assumption must not move any verdict ─────────────────


@pytest.mark.parametrize("policy", list(ChangePolicy))
def test_assumed_change_policy_does_not_move_any_admissibility_verdict(policy) -> None:
    """The one field the replay assumes. Proven inert rather than asserted inert.

    ``build_observation`` cannot read a change or cancellation policy off a fare
    screenshot, so it assumes ``FEE``. Spec A.6 consults neither, and this walks
    every alternative to show the verdict is identical under each.
    """
    raw, exclusions = load_candidates()
    shots = [s for label in (T68, BAND_7, BAND_1) for s in _shots(label, exclusions)]

    baseline, alternative = [], []
    for shot in shots:
        row = raw.get(shot)
        if row is None:
            continue
        a = build_observation(row, ASSUMED_CHANGE_POLICY)
        b = build_observation(row, policy)
        if a is None or b is None:
            assert a is b, "reconstructability must not depend on the assumed policy"
            continue
        baseline.append(bool(filter_admissible([a]).admissible))
        alternative.append(bool(filter_admissible([b]).admissible))

    assert baseline == alternative
    assert len(baseline) == 9


def _shots(label: str, exclusions: dict | None = None) -> list[str]:
    if exclusions is None:
        _, exclusions = load_candidates()
    return list(exclusions[label])


# ── 6. the execution boundary is derived, and says what it means ────────────


def test_reconstruction_reproduces_the_fare_class_the_store_recorded(panel: dict) -> None:
    """Spec B.4 derives fare class from entitlements, so a wrong guess moves a cell key."""
    rebuilt = reconstruct(panel)
    assert len(rebuilt) == EXPECTED_ACCEPTED
    recorded = {r["observation_id"]: r["fare_class"] for r in panel["observations"]}
    assert all(o.fare_class.value == recorded[o.observation_id] for o in rebuilt)


def test_every_stage_carries_one_of_the_four_declared_states(boundary: dict) -> None:
    allowed = {EXERCISED, DEGENERATE, PENDING, BLOCKED}
    assert {s["state"] for s in boundary["stages"]} <= allowed
    assert set(boundary["states"]) == allowed


def test_the_boundary_stops_exactly_where_the_evidence_stops(boundary: dict) -> None:
    """Everything longitudinal is PENDING, and publication is BLOCKED."""
    state = {s["key"]: s["state"] for s in boundary["stages"]}
    assert state["matched_set"] == PENDING
    assert state["jevons"] == PENDING
    assert state["chaining"] == PENDING
    assert state["aggregation"] == PENDING
    assert state["publication"] == BLOCKED


def test_the_single_wave_degeneracies_are_marked_degenerate_not_exercised(
    boundary: dict,
) -> None:
    """n=1 bands and a one-source panel cannot establish these properties."""
    state = {s["key"]: s["state"] for s in boundary["stages"]}
    assert state["band_price"] == DEGENERATE
    assert state["within_band_dispersion"] == DEGENERATE
    assert state["source_precedence"] == DEGENERATE


def test_deduplication_is_exercised_and_says_zero_duplicates_were_observed(
    boundary: dict,
) -> None:
    stage = next(s for s in boundary["stages"] if s["key"] == "deduplication")
    assert stage["state"] == EXERCISED
    assert any("0 duplicates observed" in e for e in stage["evidence"])
    assert "tie-break" in stage["note"], "the unexercised half must stay disclosed"


def test_the_boundary_states_are_derived_from_the_panel_not_hardcoded(panel: dict) -> None:
    """Perturb the evidence and the state must follow it.

    Band price is DEGENERATE *because* every (cell, band) group holds one fare.
    Giving one group a second fare must flip it to EXERCISED; if it does not,
    the state is decoration rather than a derivation.
    """
    assert build_boundary(panel)["stages"][5]["state"] == DEGENERATE

    doubled = json.loads(json.dumps(panel))
    twin = json.loads(json.dumps(doubled["observations"][0]))
    twin["observation_id"] += "-twin"
    twin["total"] += 100.0
    doubled["observations"].append(twin)

    flipped = {s["key"]: s["state"] for s in build_boundary(doubled)["stages"]}
    assert flipped["band_price"] == EXERCISED
    assert flipped["within_band_dispersion"] == EXERCISED


def test_the_replay_figures_in_the_boundary_match_the_replay_itself(boundary: dict, result) -> None:
    """One number, one source. The boundary may not restate the replay differently."""
    stage = next(s for s in boundary["stages"] if s["key"] == "exclusion_replay")
    joined = " ".join(stage["evidence"])
    assert f"{result.agree}/{result.candidates}" in joined
    assert f"{result.disagree} disagreements" in joined


# ── 7. semantic audit — EXERCISED must never read as VALIDATED ──────────────

RENDERED = (
    ROOT / "data" / "panel.json",
    ROOT / "data" / "dashboard.html",
)

#: Claims the current evidence does not support, in any rendered surface.
FORBIDDEN_PHRASES = (
    "elementary statistics layer is validated",
    "index engine is validated on real data",
    "dispersion is validated",
    "source precedence is validated",
    "deduplication is validated",
    "validated on real market data",
)


@pytest.mark.parametrize("path", RENDERED, ids=lambda p: p.name)
def test_no_rendered_surface_upgrades_exercised_into_validated(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    found = [phrase for phrase in FORBIDDEN_PHRASES if phrase in text]
    assert not found, f"{path.name} makes an unsupported validation claim: {found}"


def test_the_boundary_spells_out_that_exercised_is_not_validation(boundary: dict) -> None:
    assert "not" in boundary["states"][EXERCISED].lower()
    assert "validated" in boundary["states"][EXERCISED].lower()
    assert "not a validation claim" in boundary["caveat"]


def test_the_boundary_claim_is_the_agreed_wording(boundary: dict) -> None:
    """The exact sentence the project is allowed to make about real data."""
    assert boundary["claim"] == BOUNDARY_CLAIM
    assert "admissibility, banding, key construction, deduplication" in BOUNDARY_CLAIM
    assert "stops at the longitudinal Jevons step" in BOUNDARY_CLAIM
    assert "t-7 observation does not yet exist" in BOUNDARY_CLAIM


def test_within_band_dispersion_is_never_confused_with_the_t3_cross_band_spread(
    panel: dict, boundary: dict
) -> None:
    """24.9% is a cross-band spread on one travel date. It is not within-band dispersion.

    The two sit close together on the dashboard, so the boundary has to name the
    difference rather than leave a reviewer to infer it.
    """
    stage = next(s for s in boundary["stages"] if s["key"] == "within_band_dispersion")
    widest = panel["dispersion"]["widest_spread_pct"]
    assert f"{widest}%" in stage["note"]
    assert "ACROSS bands" in stage["note"]

    dashboard = (ROOT / "data" / "dashboard.html").read_text(encoding="utf-8")
    assert "cross-band" in dashboard
    # The T+3 figure itself is unchanged by this pass.
    assert widest == 24.9
    assert f"{widest}%" in dashboard


def test_the_dashboard_renders_every_stage_with_its_derived_state(panel: dict) -> None:
    """The section is generated from the contract, not authored alongside it."""
    dashboard = (ROOT / "data" / "dashboard.html").read_text(encoding="utf-8")
    assert "Real-data execution boundary" in dashboard
    for stage in panel["execution_boundary"]["stages"]:
        assert stage["name"].replace("/", "/") in dashboard
        assert stage["state"] in dashboard


def test_the_contract_carries_the_boundary_and_the_replay(panel: dict) -> None:
    """The dashboard reads these; they must be in the contract, not recomputed in it."""
    assert panel["replay"]["candidates"] == 46
    assert panel["replay"]["agree"] == 45
    assert panel["replay"]["disagree"] == 0
    assert len(panel["execution_boundary"]["stages"]) == 14
    assert panel["execution_boundary"]["state_counts"] == {
        "BLOCKED": 1,
        "DEGENERATE": 3,
        "EXERCISED": 6,
        "PENDING": 4,
    }
