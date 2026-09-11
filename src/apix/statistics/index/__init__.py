"""Index layer — chaining, assembly, annual linking. Spec E, I, J, K, L."""

from apix.statistics.index.apix_l import (
    MAX_PUBLISHED_FRESHNESS_DAYS,
    MAX_SUPPRESSED_WEIGHT,
    MAX_TIER3_WEIGHT,
    MIN_ROUTE_COVERAGE,
    ApixLError,
    calculate_apix_l,
    cell_id,
)
from apix.statistics.index.chaining import (
    MAX_CELL_IMPUTATION,
    MAX_FRESHNESS_DAYS,
    ChainInputs,
    advance_cell,
    freshness_days,
)
from apix.statistics.index.linking import (
    LinkingError,
    LinkResult,
    linking_factor,
    mean_level,
)
from apix.statistics.index.publication import (
    PublicationError,
    apply_freshness_ceiling,
    latest_states_as_of,
    publication_freshness,
    publish,
)

__all__ = [
    "MAX_CELL_IMPUTATION",
    "MAX_FRESHNESS_DAYS",
    "MAX_PUBLISHED_FRESHNESS_DAYS",
    "MAX_SUPPRESSED_WEIGHT",
    "MAX_TIER3_WEIGHT",
    "MIN_ROUTE_COVERAGE",
    "ApixLError",
    "ChainInputs",
    "LinkResult",
    "LinkingError",
    "PublicationError",
    "advance_cell",
    "apply_freshness_ceiling",
    "calculate_apix_l",
    "cell_id",
    "freshness_days",
    "latest_states_as_of",
    "linking_factor",
    "mean_level",
    "publication_freshness",
    "publish",
]
