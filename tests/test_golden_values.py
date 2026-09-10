"""Golden-value verification of the production implementation.

The distinction that matters (Checkpoint 1A finding R-10): the engine in
``src/apix/statistics`` was written from
``docs/methodology/apix_formula_spec_v1.md``. This file *verifies* it against
values hand-calculated before it existed. The golden values are not the source
the formulas were derived from — if they were, they would prove nothing.

``tests/test_methodology_invariants.py`` validates the fixture itself. This file
runs the production code.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from apix.schemas.enums import (
    APWBucket,
    CellStatus,
    Channel,
    FareClass,
    Tier,
    UndefinedRelativeReason,
)
from apix.schemas.keys import CellKey, ItemKey
from apix.schemas.results import CellState, MatchedPair
from apix.schemas.version_vector import VersionVector
from apix.statistics.aggregation.weights import (
    normalise,
    renormalise_over_live_set,
    sums_to_one,
)
from apix.statistics.aggregation.young_laspeyres import aggregate_levels
from apix.statistics.elementary.jevons import compute_jevons, jevons_relative
from apix.statistics.elementary.outliers import flag_outliers
from apix.statistics.index.apix_l import calculate_apix_l, cell_id
from apix.statistics.index.chaining import ChainInputs, advance_cell
from apix.statistics.index.linking import linking_factor

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "statistical_golden_values.yaml"

DOC = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
REL_TOL: float = DOC["meta"]["relative_tolerance"]
CASES: dict[str, dict[str, Any]] = {c["id"]: c for c in DOC["cases"]}

T = date(2026, 9, 8)


def case(case_id: str) -> dict[str, Any]:
    assert case_id in CASES, f"golden case {case_id} is missing from the fixture"
    return CASES[case_id]


def make_cell(carrier: str = "6E", tier: Tier = Tier.TIER_1) -> CellKey:
    """A v2.1 cell key — spec B.2.1.

    Migrated for methodology v2.1: the cell key is tier-invariant and holds no
    flight identity. Call sites that previously separated cells by flight number
    now separate them by carrier, which is the field that genuinely partitions
    cells. **No expected numeric value in this file changes** — every golden
    value here operates at or above the cell *level*, which the item/cell
    separation does not touch.
    """
    del tier
    return CellKey(
        route="DEL-BOM",
        carrier=carrier,
        day_of_week=2,
        apw_bucket=APWBucket.T_PLUS_7,
        fare_class=FareClass.STANDARD,
        channel=Channel.AIRLINE_DIRECT,
    )


def pairs_from(items: list[dict[str, Any]]) -> tuple[MatchedPair, ...]:
    """Build matched pairs from a fixture's ``matched_items``.

    Prices go in as Decimal, per the spec's Notation rule that monetary
    arithmetic is decimal before the log transform.
    """
    out = []
    for idx, item in enumerate(items):
        p_t = Decimal(str(item["p_t"]))
        p_prev = Decimal(str(item["p_t_minus_7"]))
        out.append(
            MatchedPair(
                item=ItemKey(tier=Tier.TIER_1, carrier="6E", flight_number=f"{idx:02d}"),
                price_t=p_t,
                price_t_minus_7=p_prev,
                log_relative=math.log(float(p_t)) - math.log(float(p_prev)),
                observation_id_t=f"{item['id']}-t",
                observation_id_t_minus_7=f"{item['id']}-p",
            )
        )
    return tuple(out)


def version_vector() -> VersionVector:
    return VersionVector(
        data_snapshot_id="sha256:" + "0" * 63 + "1",
        methodology_version="2.0",
        basket_version="2026-Q3",
        weight_version="dgca-2026-09",
        parser_version="2.4",
        code_version="7f3a91c",
        model_version=None,
    )


# ─── Jevons — G-01..G-04, G-15 ───────────────────────────────────────────────


@pytest.mark.golden
@pytest.mark.parametrize("case_id", ["G-01", "G-02", "G-03", "G-04", "G-15"])
def test_production_jevons_matches_golden(case_id: str) -> None:
    """The production log-form Jevons must reproduce each hand-calculated J."""
    spec = case(case_id)
    pairs = pairs_from(spec["given"]["matched_items"])
    result = compute_jevons(make_cell(), T, pairs)

    assert result.is_defined, f"{case_id}: production returned an undefined relative"
    assert result.relative is not None
    assert math.isclose(result.relative, spec["expected"]["J"], rel_tol=REL_TOL), (
        f"{case_id}: expected J={spec['expected']['J']}, production gave {result.relative}"
    )


@pytest.mark.golden
def test_production_jevons_is_geometric_not_arithmetic() -> None:
    """G-02 discriminates: an arithmetic mean would give 1.1667, not 1.0."""
    pairs = pairs_from(case("G-02")["given"]["matched_items"])
    result = compute_jevons(make_cell(), T, pairs)
    assert result.relative is not None
    assert math.isclose(result.relative, 1.0, rel_tol=REL_TOL)

    arithmetic = sum(float(p.price_t / p.price_t_minus_7) for p in pairs) / len(pairs)
    assert not math.isclose(arithmetic, result.relative, rel_tol=1e-3), (
        "G-02 no longer discriminates geometric from arithmetic means"
    )


@pytest.mark.golden
def test_g03_identical_prices_chain_to_exactly_100() -> None:
    """INV-3: identical prices in both periods produce a level of exactly 100."""
    spec = case("G-03")
    pairs = pairs_from(spec["given"]["matched_items"])
    jevons = compute_jevons(make_cell(), T, pairs)

    previous = CellState(
        cell=make_cell(),
        collection_date=date(2026, 9, 1),
        level=100.0,
        status=CellStatus.PUBLISHED,
        last_matched_date=date(2026, 9, 1),
    )
    state = advance_cell(
        ChainInputs(cell=make_cell(), collection_date=T, jevons=jevons, previous=previous)
    )
    assert state.level is not None
    assert math.isclose(state.level, spec["expected"]["level_from_base_100"], rel_tol=REL_TOL)


# ─── Outliers — G-14, G-16 ───────────────────────────────────────────────────


@pytest.mark.golden
@pytest.mark.parametrize("case_id", ["G-14", "G-16"])
def test_production_outlier_rule_matches_golden(case_id: str) -> None:
    """Production median/MAD flagging, including the MAD = 0 degenerate rule."""
    spec = case(case_id)
    values = spec["given"]["log_relatives"]
    pairs = tuple(
        MatchedPair(
            item=ItemKey(tier=Tier.TIER_1, carrier="6E", flight_number=f"{i:02d}"),
            price_t=Decimal("100.00"),
            price_t_minus_7=Decimal("100.00"),
            log_relative=v,
            observation_id_t=f"o{i}-t",
            observation_id_t_minus_7=f"o{i}-p",
        )
        for i, v in enumerate(values)
    )

    report = flag_outliers(pairs)

    assert math.isclose(report.mad, spec["expected"]["mad"], abs_tol=1e-12)
    flagged_idx = sorted(int(k.flight_number or "-1") for k in report.flagged)
    assert flagged_idx == spec["expected"]["flagged_indices"]
    assert len(report.kept) == spec["expected"]["kept_count"]

    if "median" in spec["expected"]:
        assert math.isclose(report.median, spec["expected"]["median"], abs_tol=1e-12)
    if "threshold" in spec["expected"]:
        assert math.isclose(report.threshold, spec["expected"]["threshold"], abs_tol=1e-12)


# ─── Chaining — G-05, G-12 ───────────────────────────────────────────────────


@pytest.mark.golden
def test_production_weekly_chaining_matches_golden() -> None:
    """G-05: I(c,t) = I(c,t-7) * J(c,t), advanced three weekly links."""
    spec = case("G-05")
    cell = make_cell()
    levels = [spec["given"]["base_level"]]

    state = CellState(
        cell=cell,
        collection_date=date(2026, 8, 18),
        level=spec["given"]["base_level"],
        status=CellStatus.PUBLISHED,
        last_matched_date=date(2026, 8, 18),
    )

    for step, relative in enumerate(spec["given"]["relatives_in_order"], start=1):
        when = date(2026, 8, 18) + timedelta(days=7 * step)
        pairs = tuple(
            MatchedPair(
                item=ItemKey(tier=Tier.TIER_1, carrier="6E", flight_number=f"{i:02d}"),
                price_t=Decimal("100.00"),
                price_t_minus_7=Decimal("100.00"),
                log_relative=math.log(relative),
                observation_id_t=f"s{step}-{i}-t",
                observation_id_t_minus_7=f"s{step}-{i}-p",
            )
            for i in range(3)
        )
        jevons = compute_jevons(cell, when, pairs)
        state = advance_cell(
            ChainInputs(cell=cell, collection_date=when, jevons=jevons, previous=state)
        )
        assert state.level is not None
        levels.append(state.level)

    for got, want in zip(levels, spec["expected"]["levels"], strict=True):
        assert math.isclose(got, want, rel_tol=REL_TOL)
    assert math.isclose(levels[-1], spec["expected"]["final_level"], rel_tol=REL_TOL)


@pytest.mark.golden
def test_production_carry_rule_matches_golden() -> None:
    """G-12: |M| = 2 < 3, so J is UNDEFINED and the parent's RELATIVE is carried."""
    spec = case("G-12")
    cell = make_cell()

    pairs = pairs_from(
        [
            {"id": "i1", "p_t_minus_7": 100.0, "p_t": 110.0},
            {"id": "i2", "p_t_minus_7": 100.0, "p_t": 120.0},
        ]
    )
    assert len(pairs) == spec["given"]["matched_item_count"]

    jevons = compute_jevons(cell, T, pairs)
    assert jevons.relative is None, "with |M| = 2 the relative must be undefined"
    assert jevons.undefined_reason is UndefinedRelativeReason.BELOW_MIN_MATCHED_ITEMS

    previous = CellState(
        cell=cell,
        collection_date=date(2026, 9, 1),
        level=spec["given"]["cell_level_t_minus_7"],
        status=CellStatus.PUBLISHED,
        last_matched_date=date(2026, 9, 1),
    )
    state = advance_cell(
        ChainInputs(
            cell=cell,
            collection_date=T,
            jevons=jevons,
            previous=previous,
            parent_relative=spec["given"]["parent_relative"],
        )
    )

    assert state.status is CellStatus.CARRIED
    assert state.level is not None
    assert math.isclose(state.level, spec["expected"]["level"], rel_tol=REL_TOL)


def test_undefined_relative_is_never_silently_one() -> None:
    """A relative of 1.0 asserts the price did not move; undefined asserts we
    cannot say. Conflating them publishes a claim the data does not support."""
    jevons = compute_jevons(make_cell(), T, ())
    assert jevons.relative is None
    assert jevons.relative != 1.0
    assert jevons.undefined_reason is UndefinedRelativeReason.NO_MATCHED_ITEMS


# ─── Weights and aggregation — G-06, G-07, G-08, G-11 ────────────────────────


@pytest.mark.golden
def test_production_weight_normalisation_matches_golden() -> None:
    spec = case("G-11")
    got = normalise(spec["given"]["raw_weights"])
    for key, want in spec["expected"]["normalised_weights"].items():
        assert math.isclose(got[key], want, rel_tol=REL_TOL)
    assert sums_to_one(got)


@pytest.mark.golden
@pytest.mark.parametrize(
    ("case_id", "collection", "result_key"),
    [("G-06", "cells", "route_level"), ("G-07", "routes", "national_level")],
)
def test_production_young_laspeyres_matches_golden(
    case_id: str, collection: str, result_key: str
) -> None:
    """Weighted arithmetic mean of LEVELS — spec F.1-F.3."""
    spec = case(case_id)
    members = spec["given"][collection]
    levels = {m["id"]: m["level"] for m in members}
    weights = {m["id"]: m["weight"] for m in members}

    got = aggregate_levels(levels, weights)
    assert math.isclose(got, spec["expected"][result_key], rel_tol=REL_TOL)


@pytest.mark.golden
def test_production_suppression_renormalisation_matches_golden() -> None:
    """G-08: dropping a route without renormalising silently reweights the rest."""
    spec = case("G-08")
    routes = spec["given"]["routes"]
    weights = {r["id"]: r["weight"] for r in routes}
    live = {r["id"]: r["level"] for r in routes if r["live"]}

    renormalised = renormalise_over_live_set(weights, live.keys())
    for rid, want in spec["expected"]["renormalised_weights"].items():
        assert math.isclose(renormalised[rid], want, rel_tol=REL_TOL)
    assert sums_to_one(renormalised)

    level = aggregate_levels(live, renormalised)
    assert math.isclose(level, spec["expected"]["national_level"], rel_tol=REL_TOL)

    naive = sum(weights[r] * live[r] for r in sorted(live))
    assert math.isclose(
        naive, spec["expected"]["wrong_answer_if_not_renormalised"], rel_tol=REL_TOL
    )
    assert not math.isclose(naive, level, rel_tol=1e-6)


# ─── New-cell entry — G-09 ───────────────────────────────────────────────────


@pytest.mark.golden
def test_production_new_cell_entry_does_not_move_the_aggregate() -> None:
    """G-09 / INV-10. A newly appearing fare is not a price change."""
    spec = case("G-09")
    before_cells = spec["given"]["before"]["cells"]

    cells = {c["id"]: make_cell(carrier=f"6E{c['id']}") for c in before_cells}
    levels = {cell_id(cells[c["id"]]): c["level"] for c in before_cells}
    weights = {cell_id(cells[c["id"]]): c["weight"] for c in before_cells}

    before_level = aggregate_levels(levels, weights)
    assert math.isclose(before_level, spec["expected"]["route_level_before"], rel_tol=REL_TOL)

    # The entrant takes the PARENT's level via the production chaining rule.
    entering = make_cell(carrier="6EC")
    jevons = compute_jevons(entering, T, ())
    entered = advance_cell(
        ChainInputs(
            cell=entering,
            collection_date=T,
            jevons=jevons,
            previous=None,
            parent_level=before_level,
        )
    )
    assert entered.status is CellStatus.ENTERED
    assert entered.level is not None
    assert math.isclose(entered.level, spec["expected"]["entering_level"], rel_tol=REL_TOL), (
        "a new cell must enter at its parent's level, never at 100"
    )

    w_new = spec["given"]["entering_cell"]["weight"]
    after_levels = {k: v * 1.0 for k, v in levels.items()}
    after_levels[cell_id(entering)] = entered.level
    after_weights = {k: v * (1 - w_new) for k, v in weights.items()}
    after_weights[cell_id(entering)] = w_new
    assert sums_to_one(after_weights)

    after_level = aggregate_levels(after_levels, after_weights)
    assert math.isclose(after_level, before_level, rel_tol=REL_TOL), (
        f"INV-10 broken: {before_level} -> {after_level}"
    )

    wrong_levels = dict(after_levels)
    wrong_levels[cell_id(entering)] = 100.0
    wrong = aggregate_levels(wrong_levels, after_weights)
    assert math.isclose(wrong, spec["expected"]["wrong_answer_if_entered_at_100"], rel_tol=REL_TOL)
    assert not math.isclose(wrong, before_level, rel_tol=1e-6)


# ─── Annual linking — G-10 ───────────────────────────────────────────────────


@pytest.mark.golden
def test_production_annual_linking_matches_golden() -> None:
    spec = case("G-10")
    result = linking_factor(
        [spec["given"]["mean_level_old_reference_year"]],
        [spec["given"]["mean_level_new_reference_year"]],
    )
    assert math.isclose(result.linking_factor, spec["expected"]["linking_factor"], rel_tol=REL_TOL)
    assert math.isclose(
        result.apply(spec["given"]["old_series_value_at_t"]),
        spec["expected"]["linked_value"],
        rel_tol=REL_TOL,
    )


# ─── Determinism — G-13 ──────────────────────────────────────────────────────


@pytest.mark.golden
def test_production_apix_l_is_order_independent_and_bit_identical() -> None:
    """G-13 / INV-5, INV-9. Reordering inputs must not change a single bit."""
    spec = case("G-13")
    members = case("G-06")["given"]["cells"]

    cells = [make_cell(carrier=f"6E{m['id']}") for m in members]
    states = [
        CellState(
            cell=c,
            collection_date=T,
            level=m["level"],
            status=CellStatus.PUBLISHED,
            last_matched_date=T,
        )
        for c, m in zip(cells, members, strict=True)
    ]
    cell_weights = {cell_id(c): m["weight"] for c, m in zip(cells, members, strict=True)}
    route_weights = {"DEL-BOM": 1.0}
    vv = version_vector()

    forward = calculate_apix_l(states, cell_weights, route_weights, vv, T)
    reverse = calculate_apix_l(list(reversed(states)), cell_weights, route_weights, vv, T)

    assert forward.level is not None and reverse.level is not None
    assert forward.level == reverse.level, "reordering changed the result bit-for-bit"
    assert math.isclose(forward.level, spec["expected"]["level_order_A"], rel_tol=REL_TOL)
    assert math.isclose(reverse.level, spec["expected"]["level_order_B"], rel_tol=REL_TOL)
    assert forward.version_vector.model_version is None, "INV-12"


def test_jevons_relative_rejects_empty_input() -> None:
    """The low-level helper must refuse rather than return a neutral 1.0."""
    with pytest.raises(ValueError, match="undefined"):
        jevons_relative([])
