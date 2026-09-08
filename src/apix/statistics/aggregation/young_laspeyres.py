"""Young / Modified Laspeyres aggregation — spec F.

    Aggregate(t) = sum over k of  omega[k] * I(k,t),   sum omega = 1

A **weighted arithmetic mean of index LEVELS**, with weights fixed from a
reference period prior to and independent of the comparison period. This is the
Young form, and it is what MoSPI itself uses in CPI 2024 — which is the point:
APIx-L must be adoptable without a methodology change.

Terminology — LOCKED. The dossier specifies **Young / Modified Laspeyres**. The
term *Lowe* is not used in APIx, and an implementation that introduces it is
non-conforming.

The error this module is written to prevent (spec C.4): aggregating *relatives*
directly, or dividing one short-term relative by another, does not produce an
index. Only levels are aggregated here, and the type signature says so.
"""

from __future__ import annotations

from collections.abc import Mapping

from apix.statistics.aggregation.weights import (
    WeightError,
    renormalise_over_live_set,
    sums_to_one,
)


class AggregationError(ValueError):
    """An aggregation that cannot be performed. Never silently produces 0.0."""


def aggregate_levels(
    levels: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    """Weighted arithmetic mean of index levels — spec F.1.

    Args:
        levels: Index **levels** (base 100) keyed by member id. Not relatives.
        weights: Weights over exactly the same key set, summing to 1.

    Returns:
        The aggregate level.

    Raises:
        AggregationError: if the key sets differ, if ``levels`` is empty, or if
            the weights do not sum to one.

    A mismatched key set is an error rather than an intersection, because
    silently intersecting is how a suppressed member's weight goes missing
    without renormalisation (spec F.4) — the exact failure this design is
    guarding.

    Terms are summed in sorted key order, so the floating-point reduction is
    stable and the result is bit-identical regardless of input ordering
    (spec P.2). Floating-point addition is not associative; an unordered sum
    would break spec P.1.
    """
    if not levels:
        raise AggregationError("cannot aggregate an empty level set")

    level_keys, weight_keys = set(levels), set(weights)
    if level_keys != weight_keys:
        raise AggregationError(
            "levels and weights must cover the same members; "
            f"levels-only={sorted(level_keys - weight_keys)}, "
            f"weights-only={sorted(weight_keys - level_keys)}"
        )

    if not sums_to_one(weights):
        total = sum(weights[k] for k in sorted(weights))
        raise AggregationError(
            f"weights sum to {total}, not 1.0 (INV-1). Renormalise over the live "
            "set (spec F.4) before aggregating — dropping a member without "
            "renormalising silently reweights everything else."
        )

    total = 0.0
    for key in sorted(levels):
        total += weights[key] * levels[key]
    return total


def aggregate_over_live_set(
    levels: Mapping[str, float],
    full_weights: Mapping[str, float],
) -> tuple[float, dict[str, float]]:
    """Renormalise onto the live set, then aggregate — spec F.2, F.3, F.4.

    This is the production path. ``levels`` contains only members that survived
    suppression; ``full_weights`` is the complete weight vector including
    suppressed members.

    Args:
        levels: Levels of the **live** members only.
        full_weights: The complete weight vector for all members, live or not.

    Returns:
        ``(aggregate_level, renormalised_weights)``. The renormalised weights are
        returned rather than discarded because spec I requires the weight
        actually applied to be publishable, not merely used.

    Raises:
        AggregationError: if the live set is empty, or if renormalisation fails.

    An empty live set raises rather than returning 0.0. Zero is a *level*, and
    returning it would publish "the index is at zero" when the truth is "the
    index cannot be computed". Callers suppress the aggregate instead.
    """
    if not levels:
        raise AggregationError(
            "live set is empty; the aggregate is not computable. Suppress it "
            "rather than publishing a level of 0.0."
        )

    try:
        renormalised = renormalise_over_live_set(full_weights, levels.keys())
    except WeightError as exc:
        raise AggregationError(str(exc)) from exc

    return aggregate_levels(levels, renormalised), renormalised
