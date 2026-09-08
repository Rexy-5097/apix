"""Canonical domain contracts — spec A, B, O.

Written before any collector (dossier section 13). A schema change breaks either
collection or computation, which is why CODEOWNERS requires both the statistical
and data-engineering owners to review this package.
"""

from apix.schemas.enums import (
    APWBucket,
    Availability,
    CellStatus,
    ChangePolicy,
    Channel,
    ExclusionReason,
    FareClass,
    SourceType,
    Tier,
    UndefinedRelativeReason,
)
from apix.schemas.keys import CellKey, ItemKey, ParentKey
from apix.schemas.observation import Entitlements, Observation
from apix.schemas.results import (
    BASE_INDEX_LEVEL,
    RELATIVE_TOLERANCE,
    ApixLResult,
    CellState,
    ExcludedObservation,
    JevonsResult,
    MatchedPair,
    OutlierReport,
    QualityMetrics,
    RouteResult,
)
from apix.schemas.version_vector import MODEL_VERSION_NOT_APPLICABLE, VersionVector

__all__ = [
    "BASE_INDEX_LEVEL",
    "MODEL_VERSION_NOT_APPLICABLE",
    "RELATIVE_TOLERANCE",
    "APWBucket",
    "ApixLResult",
    "Availability",
    "CellKey",
    "CellState",
    "CellStatus",
    "ChangePolicy",
    "Channel",
    "Entitlements",
    "ExcludedObservation",
    "ExclusionReason",
    "FareClass",
    "ItemKey",
    "JevonsResult",
    "MatchedPair",
    "Observation",
    "OutlierReport",
    "ParentKey",
    "QualityMetrics",
    "RouteResult",
    "SourceType",
    "Tier",
    "UndefinedRelativeReason",
    "VersionVector",
]
