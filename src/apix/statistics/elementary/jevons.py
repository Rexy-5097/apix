"""The Jevons elementary short-term relative — spec D.

    J(c,t) = exp( (1/|M|) * sum over i in M of [ ln p(i,t) - ln p(i,t-7) ] )

**The log form is normative** (spec D.2), not merely a numerical convenience.
Direct multiplication of ratios overflows and loses precision for large |M|, and
two implementations must agree bit for bit (spec P.1).

J is a **RELATIVE** (a dimensionless ratio near 1), not a level. Chaining it
into a level is spec E, and lives in the index layer.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date

from apix.schemas.enums import ExclusionReason, UndefinedRelativeReason
from apix.schemas.keys import CellKey, ParentKey
from apix.schemas.results import (
    ExcludedObservation,
    JevonsResult,
    MatchedPair,
)
from apix.statistics.elementary.outliers import flag_outliers

# Spec D.3 / I — LOCKED.
MIN_MATCHED_ITEMS_PER_CELL = 3


def jevons_relative(log_relatives: Sequence[float]) -> float:
    """Geometric mean of price relatives, computed in logs — spec D.2.

    Args:
        log_relatives: ``ln(p_t) - ln(p_t_minus_7)`` for each matched item.

    Returns:
        The Jevons relative J.

    Raises:
        ValueError: if the sequence is empty. An empty matched set has no
            relative; callers must handle that as *undefined* (spec D.3), never
            as 1.0.

    The sum is taken in the order given. Callers pass items sorted by item key
    (see :func:`~apix.statistics.elementary.matching.build_matched_set`), which
    is what makes the floating-point reduction order stable — spec P.2.
    """
    if not log_relatives:
        raise ValueError(
            "Jevons relative of an empty matched set is undefined (spec D.3); "
            "the caller must report UndefinedRelativeReason, not substitute 1.0"
        )
    total = 0.0
    for value in log_relatives:
        total += value
    return math.exp(total / len(log_relatives))


def compute_jevons(
    cell: CellKey | ParentKey,
    collection_date: date,
    candidate_pairs: Sequence[MatchedPair],
    *,
    apply_outlier_rule: bool = True,
) -> JevonsResult:
    """Compute J(c,t) for one cell, with outlier flagging — spec D.

    Args:
        cell: The elementary cell.
        collection_date: The period *t*. The matched set was formed against
            ``t - 7`` (spec C.1).
        candidate_pairs: M(c,t) from spec D.1, **before** outlier flagging.
        apply_outlier_rule: Escape hatch for tests that need the raw relative.
            Production callers leave it True; the pipeline in spec L.1 places
            D.7 between D.1 and D.2 unconditionally.

    Returns:
        A :class:`JevonsResult`. When the relative is undefined it carries an
        :class:`UndefinedRelativeReason` and ``relative is None`` — **never a
        substituted 1.0**, because 1.0 asserts the price did not move while
        undefined asserts we cannot say.

    Ordering of the two thresholds — a notational point in the spec worth being
    explicit about. Spec D.7's ``>= 5`` gate applies to the **candidate** set
    (flagging has not happened yet), and spec D.3's ``>= 3`` minimum applies to
    the **surviving** set (D.7 states flagged items are excluded from M, and the
    §L.1 pipeline runs D.7 before D.2). Both are written ``|M(c,t)|``. This
    implementation follows the ordering the pipeline fixes.
    """
    candidate_count = len(candidate_pairs)

    if candidate_count == 0:
        return JevonsResult(
            cell=cell,
            collection_date=collection_date,
            relative=None,
            matched_count=0,
            candidate_count=0,
            undefined_reason=UndefinedRelativeReason.NO_MATCHED_ITEMS,
        )

    report = flag_outliers(candidate_pairs) if apply_outlier_rule else None
    surviving = report.kept if report is not None else tuple(candidate_pairs)

    excluded = tuple(
        ExcludedObservation(
            observation_id=pair.observation_id_t,
            reason=ExclusionReason.OUTLIER_FLAGGED,
            detail=f"log_relative={pair.log_relative:.6f}",
        )
        for pair in candidate_pairs
        if report is not None and pair.item in set(report.flagged)
    )

    if len(surviving) < MIN_MATCHED_ITEMS_PER_CELL:
        return JevonsResult(
            cell=cell,
            collection_date=collection_date,
            relative=None,
            matched_count=len(surviving),
            candidate_count=candidate_count,
            undefined_reason=UndefinedRelativeReason.BELOW_MIN_MATCHED_ITEMS,
            outliers=report,
            excluded=excluded,
        )

    return JevonsResult(
        cell=cell,
        collection_date=collection_date,
        relative=jevons_relative([p.log_relative for p in surviving]),
        matched_count=len(surviving),
        candidate_count=candidate_count,
        outliers=report,
        excluded=excluded,
    )
