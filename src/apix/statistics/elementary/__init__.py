"""Elementary layer — matching, deduplication, outliers, Jevons. Spec A, B, C, D."""

from apix.statistics.elementary.admissibility import (
    AdmissibilityResult,
    CollectionWindow,
    filter_admissible,
)
from apix.statistics.elementary.dedup import DedupResult, deduplicate, duplicate_key
from apix.statistics.elementary.jevons import (
    MIN_MATCHED_ITEMS_PER_CELL,
    compute_jevons,
    jevons_relative,
)
from apix.statistics.elementary.matching import (
    MATCHING_LAG_DAYS,
    TIER_1_STABILITY_THRESHOLD,
    TIER_2_STABILITY_THRESHOLD,
    build_matched_set,
    cell_key_for,
    identity_stability,
    item_key_for,
    match_coverage,
    prior_period,
    select_tier,
)
from apix.statistics.elementary.outliers import (
    MAD_THRESHOLD_MULTIPLIER,
    MIN_ITEMS_FOR_OUTLIER_RULE,
    flag_outliers,
    median,
    median_absolute_deviation,
)

__all__ = [
    "MAD_THRESHOLD_MULTIPLIER",
    "MATCHING_LAG_DAYS",
    "MIN_ITEMS_FOR_OUTLIER_RULE",
    "MIN_MATCHED_ITEMS_PER_CELL",
    "TIER_1_STABILITY_THRESHOLD",
    "TIER_2_STABILITY_THRESHOLD",
    "AdmissibilityResult",
    "CollectionWindow",
    "DedupResult",
    "build_matched_set",
    "cell_key_for",
    "compute_jevons",
    "deduplicate",
    "duplicate_key",
    "filter_admissible",
    "flag_outliers",
    "identity_stability",
    "item_key_for",
    "jevons_relative",
    "match_coverage",
    "median",
    "median_absolute_deviation",
    "prior_period",
    "select_tier",
]
