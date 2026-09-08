"""Structured results carried through the deterministic pipeline.

Nothing here returns a bare number. Spec I requires suppression and coverage to
be *published*, not inferred, so every result carries the quality information
needed to interpret it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from apix.schemas.enums import (
    CellStatus,
    ExclusionReason,
    Tier,
    UndefinedRelativeReason,
)
from apix.schemas.keys import CellKey, ItemKey, ParentKey
from apix.schemas.version_vector import VersionVector

# Spec Q.1 — invariants are exact in real arithmetic but evaluated in binary
# floating point after the log transform.
RELATIVE_TOLERANCE = 1.0e-12

# Spec E.1 — every cell chain starts here.
BASE_INDEX_LEVEL = 100.0


@dataclass(frozen=True, slots=True)
class ExcludedObservation:
    """An observation kept out of the matched set, with its reason — spec A.6.

    Retained rather than dropped: exclusion rate is published per source, and a
    rising rate is the earliest signal that a site has been redesigned.
    """

    observation_id: str
    reason: ExclusionReason
    detail: str = ""
    source_id: str = ""


@dataclass(frozen=True, slots=True)
class MatchedPair:
    """One item present in both t and t-7 — spec D.1.

    ``log_relative`` is ``ln(p_t) - ln(p_t_minus_7)``, computed once here so the
    outlier rule (D.7) and the Jevons relative (D.2) operate on identical values
    rather than recomputing and risking divergence.
    """

    item: ItemKey
    price_t: Decimal
    price_t_minus_7: Decimal
    log_relative: float
    observation_id_t: str
    observation_id_t_minus_7: str


@dataclass(frozen=True, slots=True)
class OutlierReport:
    """Result of the median/MAD rule — spec D.7."""

    median: float
    mad: float
    threshold: float
    flagged: tuple[ItemKey, ...]
    kept: tuple[MatchedPair, ...]
    applied: bool
    not_applied_reason: str = ""

    @property
    def flag_rate(self) -> float:
        """Share of the candidate set flagged. Published as a quality metric."""
        total = len(self.flagged) + len(self.kept)
        return len(self.flagged) / total if total else 0.0


@dataclass(frozen=True, slots=True)
class JevonsResult:
    """The elementary short-term relative, defined or explicitly not — spec D.

    ``relative`` is None when undefined. It is **never** silently 1.0: a
    relative of 1.0 asserts "the price did not move", while undefined asserts
    "we cannot say". Conflating them is how a missing observation becomes a
    published statement of price stability.
    """

    cell: CellKey
    collection_date: date
    relative: float | None
    matched_count: int
    candidate_count: int
    undefined_reason: UndefinedRelativeReason | None = None
    outliers: OutlierReport | None = None
    excluded: tuple[ExcludedObservation, ...] = ()

    @property
    def is_defined(self) -> bool:
        return self.relative is not None

    def __post_init__(self) -> None:
        if (self.relative is None) == (self.undefined_reason is None):
            raise ValueError(
                "JevonsResult must carry exactly one of relative or undefined_reason; "
                f"got relative={self.relative!r}, reason={self.undefined_reason!r}"
            )


@dataclass(frozen=True, slots=True)
class CellState:
    """A cell's chained level and publication state — spec E, I, J."""

    cell: CellKey
    collection_date: date
    level: float | None
    status: CellStatus
    last_relative: float | None = None
    last_matched_date: date | None = None
    freshness_days: int | None = None
    parent: ParentKey | None = None
    suppression_reason: str = ""

    @property
    def is_live(self) -> bool:
        """Whether this cell contributes to aggregation — spec F.2, I.

        Suppressed and held-out cells are excluded from the live set, and their
        weight is renormalised away (spec F.4) rather than counted as zero.
        """
        return self.level is not None and self.status in (
            CellStatus.PUBLISHED,
            CellStatus.CARRIED,
            CellStatus.ENTERED,
        )


@dataclass(frozen=True, slots=True)
class RouteResult:
    """A route index level and the cells behind it — spec F.2."""

    route: str
    collection_date: date
    level: float | None
    live_cell_count: int
    expected_cell_count: int
    suppressed_cell_count: int
    tier: Tier | None = None
    suppressed: bool = False
    suppression_reason: str = ""

    @property
    def coverage(self) -> float:
        """Share of expected cells that are live — spec I, `min_route_coverage`."""
        if self.expected_cell_count == 0:
            return 0.0
        return self.live_cell_count / self.expected_cell_count


@dataclass(frozen=True, slots=True)
class QualityMetrics:
    """What a statistical analyst needs to judge the number — spec I, dossier §12."""

    matched_items: int
    live_routes: int
    suppressed_routes: int
    suppressed_weight_share: float
    tier3_weight_share: float
    imputation_rate: float
    route_coverage: float
    caveats: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ApixLResult:
    """The national APIx-L level with everything needed to interpret it.

    Deliberately not a bare float. Spec I requires suppression and coverage to be
    published alongside the value, and spec O requires the version vector on
    every published output.
    """

    collection_date: date
    level: float | None
    version_vector: VersionVector
    routes: tuple[RouteResult, ...]
    quality: QualityMetrics
    renormalised_route_weights: dict[str, float] = field(default_factory=dict)
    published: bool = True
    suppression_reason: str = ""
