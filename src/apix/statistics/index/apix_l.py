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
    cell_tiers: Mapping[str, Tier] | None = None,
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
        route_tiers: Tier per route. Under v2.1 the tier is a property of a
            ``(route, carrier)`` pair for cells and of the route only for parents
            (spec B.3), so this is used for :attr:`RouteResult.tier` display and
            as the fallback denominator when ``cell_tiers`` is not supplied.
        cell_tiers: Tier per cell, keyed by :func:`cell_id`. **Preferred.**
            Tier shares are weight-weighted over cells when this is given, which
            is the only correct reading once a route can hold Tier-1 and Tier-2
            cells at once. Falling back to ``route_tiers`` attributes a whole
            route's weight to a single tier and overstates whichever tier the
            route was labelled with.
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

    tier_shares = _tier_weight_shares(
        all_states_for_tiers=cell_states,
        cell_weights=cell_weights,
        route_weights=route_weights,
        cell_tiers=cell_tiers,
        route_tiers=tiers,
    )
    tier3_share = tier_shares.get(Tier.TIER_3, 0.0)
    status_shares = _status_weight_shares(cell_states, cell_weights, route_weights)

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
                held_out_weight_share=status_shares.get(CellStatus.HELD_OUT, 0.0),
                carried_weight_share=status_shares.get(CellStatus.CARRIED, 0.0),
                tier1_weight_share=tier_shares.get(Tier.TIER_1, 0.0),
                tier2_weight_share=tier_shares.get(Tier.TIER_2, 0.0),
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
            held_out_weight_share=status_shares.get(CellStatus.HELD_OUT, 0.0),
            carried_weight_share=status_shares.get(CellStatus.CARRIED, 0.0),
            tier1_weight_share=tier_shares.get(Tier.TIER_1, 0.0),
            tier2_weight_share=tier_shares.get(Tier.TIER_2, 0.0),
        ),
        renormalised_route_weights=renormalised,
        published=True,
    )


def _cell_total_weight(
    state: CellState,
    cell_weights: Mapping[str, float],
    route_weights: Mapping[str, float],
) -> float:
    """A cell's share of national weight: ``w[r] * v[c|r]``."""
    return route_weights.get(state.cell.route, 0.0) * cell_weights.get(cell_id(state.cell), 0.0)


def _tier_weight_shares(
    *,
    all_states_for_tiers: Sequence[CellState],
    cell_weights: Mapping[str, float],
    route_weights: Mapping[str, float],
    cell_tiers: Mapping[str, Tier] | None,
    route_tiers: Mapping[str, Tier],
) -> dict[Tier, float]:
    """Weight share per tier — spec I.

    Above ``max_tier3_weight`` (25%) the headline carries the unit-value caveat.
    Tier 3 is never used silently (spec B.2), and this is the metric that makes
    that true.

    Computed over **cells** whenever ``cell_tiers`` is supplied, because under
    v2.1 the tier is a property of a ``(route, carrier)`` pair and one route can
    hold Tier-1 and Tier-2 cells simultaneously (spec B.3). Attributing a whole
    route's weight to a single tier — the v2.0 reading — lets a route-level label
    leak onto carrier cells that do not share it, in either direction.

    The route-level fallback is retained for callers that have no cell tiers, and
    is documented as the coarser answer it is.
    """
    if cell_tiers is not None:
        ordered = sorted(all_states_for_tiers, key=lambda s: s.cell.sort_key)
        total = sum(_cell_total_weight(s, cell_weights, route_weights) for s in ordered)
        if total <= 0:
            return {}
        shares: dict[Tier, float] = {}
        for state in ordered:
            tier = cell_tiers.get(cell_id(state.cell))
            if tier is None:
                continue
            weight = _cell_total_weight(state, cell_weights, route_weights)
            shares[tier] = shares.get(tier, 0.0) + weight / total
        return shares

    ordered_routes = sorted(route_weights)
    total = sum(route_weights[r] for r in ordered_routes)
    if total <= 0:
        return {}
    shares = {}
    for route in ordered_routes:
        tier = route_tiers.get(route)
        if tier is None:
            continue
        shares[tier] = shares.get(tier, 0.0) + route_weights[route] / total
    return shares


def _status_weight_shares(
    states: Sequence[CellState],
    cell_weights: Mapping[str, float],
    route_weights: Mapping[str, float],
) -> dict[CellStatus, float]:
    """Weight share per publication status — spec I, E.7.4.

    ``HELD_OUT`` is reported separately from ``SUPPRESSED`` because they are
    different quality events: a suppressed cell was live and breached a
    threshold, a held-out cell was never live. Both have their weight
    renormalised away, but conflating them would hide which of the two happened.
    """
    ordered = sorted(states, key=lambda s: s.cell.sort_key)
    total = sum(_cell_total_weight(s, cell_weights, route_weights) for s in ordered)
    if total <= 0:
        return {}
    shares: dict[CellStatus, float] = {}
    for state in ordered:
        weight = _cell_total_weight(state, cell_weights, route_weights)
        shares[state.status] = shares.get(state.status, 0.0) + weight / total
    return shares
