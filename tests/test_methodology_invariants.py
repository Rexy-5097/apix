"""Methodology invariants checkable before the index engine exists.

SCOPE — read this before adding to the file
-------------------------------------------
These tests validate the **frozen contract**: the golden-value fixture and the
formula specification. They do **not** test the index engine, which does not
exist yet (Checkpoint 2).

Two things follow from that, and both matter:

1. The small arithmetic below is a **fixture validator**, not an implementation.
   It exists so a transcription slip in a hand-calculated `expected` value is
   caught now rather than becoming the thing Checkpoint 2 is validated against.

2. **The Checkpoint 2 engine must be written from
   `docs/methodology/apix_formula_spec_v1.md`, not from this file.** If the
   engine is derived from these few lines, the golden values stop being an
   independent check and start being a tautology — precisely the failure the
   dossier's "two developers implement the aggregation differently" risk is
   about.

What is genuinely exercised here:

* INV-1 / INV-2 — weight vectors sum to one and are non-negative, on every
  weighted case in the fixture.
* INV-3, INV-4a, INV-4b, INV-5, INV-6, INV-10 — the invariant each golden case
  claims to demonstrate actually holds for the numbers recorded.
* INV-12 — an APIx-L version vector carries no `model_version`.
* Spec/fixture drift — every threshold the fixture depends on is present in the
  frozen specification with the value the fixture assumes.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "statistical_golden_values.yaml"
SPEC = REPO_ROOT / "docs" / "methodology" / "apix_formula_spec_v1.md"

# Spec Q.1. Exact in real arithmetic, evaluated in binary floating point.
REL_TOL = 1.0e-12


def _load() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    doc = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    return doc["meta"], doc["cases"]


def _case(case_id: str) -> dict[str, Any]:
    _, cases = _load()
    for c in cases:
        if c["id"] == case_id:
            return c
    raise AssertionError(f"golden case {case_id} is missing from the fixture")


def _jevons(items: list[dict[str, Any]]) -> float:
    """Spec D.2, log form (normative). Fixture validation only."""
    n = len(items)
    return math.exp(sum(math.log(i["p_t"]) - math.log(i["p_t_minus_7"]) for i in items) / n)


# ─── Fixture integrity ───────────────────────────────────────────────────────


def test_fixture_and_spec_exist() -> None:
    """A missing fixture or spec must fail loudly, not skip silently."""
    assert FIXTURE.is_file(), f"golden values missing at {FIXTURE}"
    assert SPEC.is_file(), f"frozen specification missing at {SPEC}"


def test_every_case_declares_a_spec_reference() -> None:
    """A golden value with no spec reference cannot be audited."""
    _, cases = _load()
    assert cases, "fixture contains no golden cases"
    missing = [c["id"] for c in cases if not c.get("spec_ref")]
    assert not missing, f"golden cases with no spec_ref: {missing}"


def test_every_case_records_its_hand_working() -> None:
    """The working is the evidence. Without it the number is an assertion."""
    _, cases = _load()
    missing = [c["id"] for c in cases if not (c.get("hand_working") or "").strip()]
    assert not missing, f"golden cases with no hand_working: {missing}"


def test_required_cases_are_present() -> None:
    """Phase 4 requires these nine behaviours to be frozen before implementation."""
    _, cases = _load()
    have = {c["id"] for c in cases}
    required = {
        "G-01",  # Jevons
        "G-05",  # chained cell index
        "G-06",  # Young / Modified Laspeyres
        "G-07",  # route -> national aggregation
        "G-09",  # new-cell entry
        "G-12",  # missing-cell carry / suppression
        "G-11",  # weight normalisation
        "G-10",  # annual linking
        "G-13",  # deterministic reproduction
    }
    assert required <= have, f"missing required golden cases: {sorted(required - have)}"


# ─── INV-1 / INV-2 — weights ─────────────────────────────────────────────────


@pytest.mark.invariant
def test_inv1_and_inv2_all_weight_vectors_sum_to_one_and_are_non_negative() -> None:
    """Every weighted structure anywhere in the fixture, not just the ones that
    advertise it. A weight vector that does not sum to one is not a weight
    vector, and a negative weight is a defect rather than a value."""
    _, cases = _load()
    checked = 0

    def weight_vectors(node: Any, path: str):
        """Yield (path, weights) for every weight vector anywhere in the tree.

        Two shapes occur in the fixture: a mapping of id -> weight whose key
        names it a weight vector, and a list of members each carrying a
        `weight`. Recursion matters — G-09 nests its members under `before`.
        """
        leaf = path.rsplit("/", 1)[-1]
        # `raw_weights` is the deliberately UN-normalised input to G-11 and sums
        # to 10 by design. INV-1 applies to weight vectors in force, not to the
        # raw quantities they are derived from.
        is_raw = leaf.startswith("raw_")

        if isinstance(node, dict):
            if (
                "weight" in leaf
                and not is_raw
                and node
                and all(isinstance(v, int | float) for v in node.values())
            ):
                yield path, list(node.values())
            for k, v in node.items():
                yield from weight_vectors(v, f"{path}/{k}")
        elif isinstance(node, list):
            if node and all(isinstance(m, dict) and "weight" in m for m in node):
                yield path, [m["weight"] for m in node]
            for idx, m in enumerate(node):
                yield from weight_vectors(m, f"{path}[{idx}]")

    for case in cases:
        for block_name in ("given", "expected"):
            for path, vec in weight_vectors(case.get(block_name) or {}, block_name):
                checked += 1
                assert all(w >= 0 for w in vec), f"{case['id']}/{path}: negative weight in {vec}"
                assert math.isclose(sum(vec), 1.0, rel_tol=REL_TOL), (
                    f"{case['id']}/{path}: weights sum to {sum(vec)}, not 1.0"
                )

    # Six weight vectors are present across G-06, G-07, G-08 (x2), G-09 (x2),
    # G-11. A lower count means the detector stopped finding them, which would
    # make this test silently vacuous.
    assert checked >= 6, f"expected at least 6 weight vectors, found {checked}"


# ─── Jevons cases ────────────────────────────────────────────────────────────


@pytest.mark.golden
@pytest.mark.parametrize("case_id", ["G-01", "G-02", "G-03", "G-04", "G-15"])
def test_jevons_golden_values_are_arithmetically_correct(case_id: str) -> None:
    """Recompute each hand-calculated Jevons relative from its own inputs."""
    case = _case(case_id)
    computed = _jevons(case["given"]["matched_items"])
    expected = case["expected"]["J"]
    assert math.isclose(computed, expected, rel_tol=REL_TOL), (
        f"{case_id}: fixture says J={expected}, inputs give {computed}"
    )


@pytest.mark.invariant
def test_inv3_identical_prices_give_relative_one_and_level_100() -> None:
    case = _case("G-03")
    assert math.isclose(_jevons(case["given"]["matched_items"]), 1.0, rel_tol=REL_TOL)
    assert case["expected"]["level_from_base_100"] == 100.0


@pytest.mark.invariant
def test_inv4a_scaling_both_periods_leaves_the_relative_unchanged() -> None:
    """G-04 must equal G-01. A currency redenomination cannot move an index."""
    base = _jevons(_case("G-01")["given"]["matched_items"])
    scaled = _jevons(_case("G-04")["given"]["matched_items"])
    assert math.isclose(scaled, base, rel_tol=REL_TOL), (
        f"scale invariance broken: {base} vs {scaled}"
    )


@pytest.mark.invariant
def test_inv4b_scaling_current_period_only_scales_the_relative_by_k() -> None:
    """G-15 must equal k x G-01. This is the half of the dossier's ambiguous
    sentence that INV-4a does not cover — see spec Q, REPORTED INCONSISTENCY."""
    case = _case("G-15")
    k = case["given"]["k"]
    base = _jevons(_case("G-01")["given"]["matched_items"])
    scaled = _jevons(case["given"]["matched_items"])
    assert math.isclose(scaled, k * base, rel_tol=REL_TOL), (
        f"homogeneity broken: expected {k * base}, got {scaled}"
    )


def test_jevons_is_geometric_not_arithmetic() -> None:
    """G-02 discriminates the formula: offsetting moves must give exactly 1.0.
    An arithmetic mean of the same ratios gives 1.1667 — a 16.67% phantom rise."""
    items = _case("G-02")["given"]["matched_items"]
    geometric = _jevons(items)
    arithmetic = sum(i["p_t"] / i["p_t_minus_7"] for i in items) / len(items)

    assert math.isclose(geometric, 1.0, rel_tol=REL_TOL)
    assert not math.isclose(arithmetic, 1.0, rel_tol=1e-3), (
        "this case no longer discriminates geometric from arithmetic means"
    )


# ─── Chaining, aggregation, entry, linking ───────────────────────────────────


@pytest.mark.golden
def test_chained_cell_level_matches_hand_calculation() -> None:
    case = _case("G-05")
    level = case["given"]["base_level"]
    levels = [level]
    for j in case["given"]["relatives_in_order"]:
        level *= j
        levels.append(level)

    for got, want in zip(levels, case["expected"]["levels"], strict=True):
        assert math.isclose(got, want, rel_tol=REL_TOL)
    assert math.isclose(level, case["expected"]["final_level"], rel_tol=REL_TOL)


@pytest.mark.golden
@pytest.mark.parametrize(
    ("case_id", "collection", "result_key"),
    [("G-06", "cells", "route_level"), ("G-07", "routes", "national_level")],
)
def test_young_laspeyres_aggregation_matches_hand_calculation(
    case_id: str, collection: str, result_key: str
) -> None:
    """Weighted arithmetic mean of LEVELS (spec F.1-F.3)."""
    case = _case(case_id)
    members = case["given"][collection]
    computed = sum(m["weight"] * m["level"] for m in members)
    assert math.isclose(computed, case["expected"][result_key], rel_tol=REL_TOL)


@pytest.mark.invariant
def test_suppression_renormalises_weights_and_changes_the_level() -> None:
    """Spec F.4. Also asserts the un-renormalised answer is genuinely wrong, so
    the test fails if someone 'simplifies' renormalisation away."""
    case = _case("G-08")
    live = [r for r in case["given"]["routes"] if r["live"]]
    total = sum(r["weight"] for r in live)

    renormalised = {r["id"]: r["weight"] / total for r in live}
    assert math.isclose(sum(renormalised.values()), 1.0, rel_tol=REL_TOL)
    for rid, w in case["expected"]["renormalised_weights"].items():
        assert math.isclose(renormalised[rid], w, rel_tol=REL_TOL)

    level = sum(renormalised[r["id"]] * r["level"] for r in live)
    assert math.isclose(level, case["expected"]["national_level"], rel_tol=REL_TOL)

    naive = sum(r["weight"] * r["level"] for r in live)
    wrong = case["expected"]["wrong_answer_if_not_renormalised"]
    assert math.isclose(naive, wrong, rel_tol=REL_TOL)
    assert not math.isclose(naive, level, rel_tol=1e-6), (
        "the un-renormalised path must differ, or this case proves nothing"
    )


@pytest.mark.invariant
def test_inv10_new_cell_entry_does_not_move_the_aggregate() -> None:
    """Spec J. A newly appearing fare is not a price change."""
    case = _case("G-09")
    before_cells = case["given"]["before"]["cells"]
    before = sum(c["weight"] * c["level"] for c in before_cells)
    assert math.isclose(before, case["expected"]["route_level_before"], rel_tol=REL_TOL)

    w_new = case["given"]["entering_cell"]["weight"]
    rescaled = {c["id"]: c["weight"] * (1 - w_new) for c in before_cells}
    rescaled[case["given"]["entering_cell"]["id"]] = w_new
    assert math.isclose(sum(rescaled.values()), 1.0, rel_tol=REL_TOL)

    # The entrant takes the PARENT's level, not 100.
    after = (
        sum(rescaled[c["id"]] * c["level"] for c in before_cells)
        + w_new * case["expected"]["entering_level"]
    )

    assert math.isclose(after, before, rel_tol=REL_TOL), f"INV-10 broken: {before} -> {after}"

    # And the bug the rule prevents must still be a real bug.
    wrong = sum(rescaled[c["id"]] * c["level"] for c in before_cells) + w_new * 100.0
    assert math.isclose(wrong, case["expected"]["wrong_answer_if_entered_at_100"], rel_tol=REL_TOL)
    assert not math.isclose(wrong, before, rel_tol=1e-6), (
        "entering at 100 must visibly distort the aggregate"
    )


@pytest.mark.golden
def test_annual_linking_factor() -> None:
    case = _case("G-10")
    g = case["given"]
    lf = g["mean_level_new_reference_year"] / g["mean_level_old_reference_year"]
    assert math.isclose(lf, case["expected"]["linking_factor"], rel_tol=REL_TOL)
    assert math.isclose(
        g["old_series_value_at_t"] * lf, case["expected"]["linked_value"], rel_tol=REL_TOL
    )


@pytest.mark.invariant
def test_inv5_observation_order_does_not_change_the_aggregate() -> None:
    """Spec P.2. Reordering members must not change a weighted sum."""
    members = _case("G-06")["given"]["cells"]
    forward = sum(m["weight"] * m["level"] for m in members)
    reverse = sum(m["weight"] * m["level"] for m in reversed(members))
    by_level = sum(m["weight"] * m["level"] for m in sorted(members, key=lambda m: m["level"]))

    assert math.isclose(forward, reverse, rel_tol=REL_TOL)
    assert math.isclose(forward, by_level, rel_tol=REL_TOL)


@pytest.mark.invariant
def test_inv12_apix_l_version_vector_has_no_model_version() -> None:
    """Spec O.1. A non-null model_version on an APIx-L output means a fitted
    model entered the deterministic path. That is a defect, not a field value."""
    vv = _case("G-13")["given"]["version_vector"]
    assert vv["model_version"] is None, (
        f"APIx-L version vector carries model_version={vv['model_version']!r}; must be N/A"
    )
    for required in (
        "data_snapshot_id",
        "methodology_version",
        "basket_version",
        "weight_version",
        "parser_version",
        "code_version",
    ):
        assert vv.get(required), f"version vector missing {required}"


# ─── Outlier rule ────────────────────────────────────────────────────────────


@pytest.mark.golden
@pytest.mark.parametrize("case_id", ["G-14", "G-16"])
def test_mad_outlier_rule_matches_hand_calculation(case_id: str) -> None:
    """Spec D.7, including the MAD = 0 degenerate case that must NOT flag."""
    case = _case(case_id)
    values = case["given"]["log_relatives"]

    ordered = sorted(values)
    median = (
        ordered[len(ordered) // 2]
        if len(ordered) % 2
        else (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2
    )
    devs = sorted(abs(v - median) for v in values)
    mad = (
        devs[len(devs) // 2]
        if len(devs) % 2
        else (devs[len(devs) // 2 - 1] + devs[len(devs) // 2]) / 2
    )

    assert math.isclose(mad, case["expected"]["mad"], abs_tol=1e-12)

    if mad == 0:
        flagged: list[int] = []  # spec D.7 degenerate rule
    else:
        flagged = [i for i, v in enumerate(values) if abs(v - median) > 5 * mad]

    assert flagged == case["expected"]["flagged_indices"]
    assert len(values) - len(flagged) == case["expected"]["kept_count"]


# ─── Spec / fixture drift ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("threshold", "needle"),
    [
        ("min_matched_items_per_cell", "**3**"),
        ("max_cell_imputation", "**40%**"),
        ("min_route_coverage", "**60%**"),
        ("max_suppressed_weight", "**15%**"),
        ("max_tier3_weight", "**25%**"),
        ("min_quotes_window", "**1,500**"),
        ("min_quotes_per_level", "**30**"),
        ("min_quotes_per_route", "**60**"),
        ("condition_number", "**30**"),
        ("max_missing_characteristic", "**10%**"),
        ("min_periods_overlap", "**7 days**"),
        ("window_length", "**21 days**"),
        ("n_draws", "**1000**"),
    ],
)
def test_locked_thresholds_are_present_in_the_frozen_spec(threshold: str, needle: str) -> None:
    """Catches silent drift: a threshold quietly edited in one place only.

    Every value here is LOCKED for methodology_version 2.0. Changing one is a
    methodology change requiring an ADR and a version bump, never a test edit.
    """
    text = SPEC.read_text(encoding="utf-8")
    assert f"`{threshold}`" in text, f"{threshold} is not named in the frozen spec"
    assert needle in text, f"{threshold} no longer carries its locked value {needle} in the spec"


def test_tier_ladder_thresholds_are_locked_in_the_spec() -> None:
    """Tier boundaries select the matched-item definition, so they are the most
    consequential numbers in the document."""
    text = SPEC.read_text(encoding="utf-8")
    assert "**≥ 70%**" in text, "Tier 1 identity-stability threshold missing"
    assert "**[40%, 70%)**" in text, "Tier 2 identity-stability band missing"
    assert "**40%**" in text, "Tier 3 boundary missing"


def test_every_open_question_is_labelled_and_unresolved() -> None:
    """EMPIRICAL / OPEN items must stay visibly open. Silently resolving one by
    choosing a plausible value is the failure mode this guards."""
    text = SPEC.read_text(encoding="utf-8")
    for oq in [f"OQ-{n}" for n in range(1, 9)]:
        assert oq in text, f"{oq} vanished from the specification"
    assert "EMPIRICAL / OPEN" in text
    flat = " ".join(text.split())
    assert "resolve one by choosing a plausible value" in flat
    assert "may be resolved by choosing a plausible value" in flat


def test_lowe_terminology_is_not_used() -> None:
    """Spec F. The dossier specifies Young / Modified Laspeyres; 'Lowe' is a
    different index and its appearance signals a drifting implementation."""
    text = SPEC.read_text(encoding="utf-8").lower()
    # Permitted only in the sentence that forbids it.
    occurrences = text.count("lowe")
    forbidding = text.count("the term *lowe* is **not** used")
    assert occurrences == forbidding, (
        "'Lowe' appears in the specification outside the clause that forbids it"
    )
