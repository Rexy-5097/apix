"""Deterministic assembly of the national APIx-L index — spec L.

    cell LEVELS -> route LEVELS (spec F.2) -> national APIx-L (spec F.3)

with renormalisation over the live set at every step (spec F.4).

Determinism (spec L.2, P). ``calculate_apix_l`` is a pure function of its
arguments. It contains no random number generation, no fitted model, no
wall-clock or locale dependence, and every reduction runs in explicitly sorted
key order — floating-point addition is not associative, so an unordered sum
would break the bit-identity guarantee of spec P.1.

This module imports nothing from ``apix.analytics`` or ``apix.ai``, and nothing
stochastic. Enforced by ``tests/test_architecture.py``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from apix.schemas.enums import CellStatus, Tier
from apix.schemas.keys import CellKey
from apix.schemas.results import (
    ApixLResult,
    CellState,
    QualityMetrics,
    RouteResult,
)
from apix.schemas.version_vector import VersionVector
from apix.statistics.aggregation.weights import suppressed_weight_share
from apix.statistics.aggregation.young_laspeyres import (
    AggregationError,
    aggregate_over_live_set,
)

# Spec I — LOCKED.
MIN_ROUTE_COVERAGE = 0.60
MAX_SUPPRESSED_WEIGHT = 0.15
MAX_TIER3_WEIGHT = 0.25


class ApixLError(ValueError):
    """APIx-L could not be computed from the inputs given."""


def cell_id(cell: CellKey) -> str:
    """A stable, sortable string id for a cell.

    Derived from :attr:`CellKey.sort_key`, so id ordering and key ordering agree
    and the aggregation reduces in one well-defined order (spec P.2).
    """
    return "|".join(str(part) for part in cell.sort_key)


def _route_result(
    route: str,
    collection_date: date,
    states: Sequence[CellState],
    cell_weights: Mapping[str, float],
    expected_cells: int,
    tier: Tier | None,
) -> tuple[RouteResult, float | None]:
    """Aggregate one route's live cells — spec F.2, F.4, I.

    Returns the route result and its level (None when suppressed), so the caller
    does not have to re-derive liveness from the result object.
    """
    live = [s for s in states if s.is_live]
    suppressed_count = len(states) - len(live)
    expected = max(expected_cells, len(states))

    coverage = len(live) / expected if expected else 0.0
    if not live or coverage < MIN_ROUTE_COVERAGE:
        return (
            RouteResult(
                route=route,
                collection_date=collection_date,
                level=None,
                live_cell_count=len(live),
                expected_cell_count=expected,
                suppressed_cell_count=suppressed_count,
                tier=tier,
                suppressed=True,
                suppression_reason=(
                    f"route coverage {coverage:.1%} is below the "
                    f"{MIN_ROUTE_COVERAGE:.0%} minimum (spec I); weights renormalised"
                ),
            ),
            None,
        )

    levels = {cell_id(s.cell): s.level for s in live if s.level is not None}
    try:
        level, _ = aggregate_over_live_set(levels, cell_weights)
    except AggregationError as exc:
        return (
            RouteResult(
                route=route,
                collection_date=collection_date,
                level=None,
                live_cell_count=len(live),
                expected_cell_count=expected,
                suppressed_cell_count=suppressed_count,
                tier=tier,
                suppressed=True,
                suppression_reason=f"cell aggregation failed: {exc}",
            ),
            None,
        )

    return (
        RouteResult(
            route=route,
            collection_date=collection_date,
            level=level,
            live_cell_count=len(live),
            expected_cell_count=expected,
            suppressed_cell_count=suppressed_count,
            tier=tier,
        ),
        level,
    )


def calculate_apix_l(
    cell_states: Sequence[CellState],
    cell_weights: Mapping[str, float],
    route_weights: Mapping[str, float],
    version_vector: VersionVector,
    collection_date: date,
    *,
    route_tiers: Mapping[str, Tier] | None = None,
    expected_cells_by_route: Mapping[str, int] | None = None,
) -> ApixLResult:
    """Compute the national APIx-L level — spec L.1.

    Args:
        cell_states: Cell levels for this period, already advanced through
            :func:`~apix.statistics.index.chaining.advance_cell`. Suppressed and
            held-out cells are included; they are excluded from aggregation here
            and their weight is renormalised away rather than counted as zero.
        cell_weights: ``v[c|r]`` keyed by :func:`cell_id`, for every cell in the
            basket including suppressed ones.
        route_weights: ``w[r]`` keyed by route, for every route in the basket
            including suppressed ones.
        version_vector: Spec O. Must carry ``model_version`` N/A.
        collection_date: The period *t*.
        route_tiers: Matched-item tier per route (spec B.2), recorded per cell
            in the version vector and used for the Tier-3 weight share.
        expected_cells_by_route: Expected cell count per route, the denominator
            of route coverage (spec I). Defaults to the observed count, which
            makes coverage optimistic — supply it in production.

    Returns:
        An :class:`ApixLResult` carrying the level, the version vector, every
        route result, the renormalised weights actually applied, and quality
        metrics. **Never a bare float**: spec I requires suppression and
        coverage to be published alongside the value.

        ``level is None`` with ``published=False`` when every route is
        suppressed. That is a real state — the index cannot be computed — and is
        reported rather than rendered as 0.0.

    Raises:
        ApixLError: if the version vector carries a ``model_version``, meaning a
            fitted model has entered the deterministic path (spec O.1, INV-12),
            or if the route weight vector is unusable.
    """
    try:
        version_vector.assert_apix_l_safe()
    except ValueError as exc:
        raise ApixLError(str(exc)) from exc

    mismatched = sorted({s.collection_date for s in cell_states} - {collection_date})
    if mismatched:
        raise ApixLError(
            f"cell states carry collection dates {mismatched} but APIx-L was asked "
            f"for {collection_date}; mixing periods would difference a Monday "
            "against a Tuesday (spec C.2)"
        )

    tiers = route_tiers or {}
    expected = expected_cells_by_route or {}

    by_route: dict[str, list[CellState]] = {}
    for state in cell_states:
        by_route.setdefault(state.cell.route, []).append(state)

    route_results: list[RouteResult] = []
    live_levels: dict[str, float] = {}

    for route in sorted(by_route):
        states = sorted(by_route[route], key=lambda s: s.cell.sort_key)
        result, level = _route_result(
            route=route,
            collection_date=collection_date,
            states=states,
            cell_weights=cell_weights,
            expected_cells=expected.get(route, 0),
            tier=tiers.get(route),
        )
        route_results.append(result)
        if level is not None:
            live_levels[route] = level

    all_states = sorted(cell_states, key=lambda s: s.cell.sort_key)
    matched_items = sum(1 for s in all_states if s.status is CellStatus.PUBLISHED)
    carried = sum(1 for s in all_states if s.status is CellStatus.CARRIED)
    imputation_rate = carried / len(all_states) if all_states else 0.0

    tier3_share = _tier3_weight_share(route_weights, tiers)

    if not live_levels:
        return ApixLResult(
            collection_date=collection_date,
            level=None,
            version_vector=version_vector,
            routes=tuple(route_results),
            quality=QualityMetrics(
                matched_items=matched_items,
                live_routes=0,
                suppressed_routes=len(route_results),
                suppressed_weight_share=1.0,
                tier3_weight_share=tier3_share,
                imputation_rate=imputation_rate,
                route_coverage=0.0,
            ),
            published=False,
            suppression_reason=(
                "every route is suppressed; the index is not computable for this "
                "period and is withheld rather than published as 0.0"
            ),
        )

    try:
        national_level, renormalised = aggregate_over_live_set(live_levels, route_weights)
    except AggregationError as exc:
        raise ApixLError(f"national aggregation failed: {exc}") from exc

    suppressed_share = suppressed_weight_share(route_weights, live_levels.keys())

    caveats: list[str] = []
    if suppressed_share > MAX_SUPPRESSED_WEIGHT:
        caveats.append(
            f"suppressed weight share {suppressed_share:.1%} exceeds "
            f"{MAX_SUPPRESSED_WEIGHT:.0%} (spec I): published with a quality caveat"
        )
    if tier3_share > MAX_TIER3_WEIGHT:
        caveats.append(
            f"Tier-3 weight share {tier3_share:.1%} exceeds {MAX_TIER3_WEIGHT:.0%} "
            "(spec I): the headline carries the unit-value caveat"
        )

    return ApixLResult(
        collection_date=collection_date,
        level=national_level,
        version_vector=version_vector,
        routes=tuple(route_results),
        quality=QualityMetrics(
            matched_items=matched_items,
            live_routes=len(live_levels),
            suppressed_routes=len(route_results) - len(live_levels),
            suppressed_weight_share=suppressed_share,
            tier3_weight_share=tier3_share,
            imputation_rate=imputation_rate,
            route_coverage=len(live_levels) / len(route_results) if route_results else 0.0,
            caveats=tuple(caveats),
        ),
        renormalised_route_weights=renormalised,
        published=True,
    )


def _tier3_weight_share(route_weights: Mapping[str, float], tiers: Mapping[str, Tier]) -> float:
    """Share of total weight on Tier-3 (declared unit value) routes — spec I.

    Above 25% the headline carries the unit-value caveat. Tier 3 is never used
    silently (spec B.2), and this is the metric that makes that true.
    """
    ordered = sorted(route_weights)
    total = sum(route_weights[r] for r in ordered)
    if total <= 0:
        return 0.0
    tier3 = sum(route_weights[r] for r in ordered if tiers.get(r) is Tier.TIER_3)
    return tier3 / total
