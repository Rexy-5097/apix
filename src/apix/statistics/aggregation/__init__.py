"""Aggregation layer — weights and Young / Modified Laspeyres. Spec F, G."""

from apix.statistics.aggregation.weights import (
    EQUAL_APW_WEIGHT,
    APWWeighting,
    WeightError,
    normalise,
    renormalise_over_live_set,
    sums_to_one,
    suppressed_weight_share,
    validate,
)
from apix.statistics.aggregation.within_route import (
    CarrierAllocation,
    CarrierAllocationBasis,
    within_route_weights,
)
from apix.statistics.aggregation.young_laspeyres import (
    AggregationError,
    aggregate_levels,
    aggregate_over_live_set,
)

__all__ = [
    "EQUAL_APW_WEIGHT",
    "APWWeighting",
    "AggregationError",
    "CarrierAllocation",
    "CarrierAllocationBasis",
    "WeightError",
    "aggregate_levels",
    "aggregate_over_live_set",
    "normalise",
    "renormalise_over_live_set",
    "sums_to_one",
    "suppressed_weight_share",
    "validate",
    "within_route_weights",
]
