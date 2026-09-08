"""Outlier flagging by median/MAD — spec D.7.

Applied to log price relatives **within a cell**, **before** the Jevons relative
(spec D.7 and the §L.1 pipeline: D.1 -> D.7 -> D.2).

Three details are locked and easy to get wrong:

1. **MAD is NOT rescaled by 1.4826.** The threshold 5 is expressed in raw MAD
   units. Applying the usual normal-consistency constant would widen the
   threshold by ~48% and silently change what counts as an outlier.
2. **The rule is applied only when the candidate set has at least 5 items.**
   Below that the dispersion estimate is not meaningful.
3. **When MAD = 0, no flagging occurs.** Otherwise the threshold collapses to
   zero and every non-identical observation is flagged — the detector
   destroying the data it exists to protect.

Median/MAD rather than mean/SD, because the estimator must not be dragged by the
very contamination it is detecting.
"""

from __future__ import annotations

from collections.abc import Sequence

from apix.schemas.results import MatchedPair, OutlierReport

# Spec D.7 — LOCKED.
MAD_THRESHOLD_MULTIPLIER = 5.0
MIN_ITEMS_FOR_OUTLIER_RULE = 5


def median(values: Sequence[float]) -> float:
    """Median of a non-empty sequence.

    Implemented here rather than taken from ``statistics.median`` so the
    tie-breaking on even-length inputs is explicit and cannot change with a
    standard-library revision — spec P.1 requires bit-identical output across
    runs, which includes across interpreter upgrades.
    """
    if not values:
        raise ValueError("median of an empty sequence is undefined")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def median_absolute_deviation(values: Sequence[float], centre: float) -> float:
    """MAD about a given centre, **unscaled** — spec D.7.

    Deliberately not multiplied by 1.4826.
    """
    if not values:
        raise ValueError("MAD of an empty sequence is undefined")
    return median([abs(v - centre) for v in values])


def flag_outliers(pairs: Sequence[MatchedPair]) -> OutlierReport:
    """Flag contaminating observations within a cell — spec D.7.

    Args:
        pairs: The candidate matched set M(c,t) from spec D.1, before flagging.

    Returns:
        An :class:`OutlierReport`. Flagged items are excluded from the matched
        set that reaches spec D.2, retained for the store, and counted in a
        published flag rate.

    Failure conditions: none. An empty or small candidate set is a valid input
    and yields ``applied=False`` with everything kept — the rule declining to
    act is a defined outcome, not an error.
    """
    if len(pairs) < MIN_ITEMS_FOR_OUTLIER_RULE:
        return OutlierReport(
            median=0.0,
            mad=0.0,
            threshold=0.0,
            flagged=(),
            kept=tuple(pairs),
            applied=False,
            not_applied_reason=(
                f"candidate set has {len(pairs)} items, below the "
                f"{MIN_ITEMS_FOR_OUTLIER_RULE}-item minimum for a meaningful "
                "dispersion estimate (spec D.7)"
            ),
        )

    log_relatives = [p.log_relative for p in pairs]
    centre = median(log_relatives)
    mad = median_absolute_deviation(log_relatives, centre)

    if mad == 0.0:
        return OutlierReport(
            median=centre,
            mad=0.0,
            threshold=0.0,
            flagged=(),
            kept=tuple(pairs),
            applied=False,
            not_applied_reason=(
                "MAD = 0: more than half the log relatives are identical, so the "
                "threshold would collapse to zero and flag every non-identical "
                "observation (spec D.7, degenerate dispersion)"
            ),
        )

    threshold = MAD_THRESHOLD_MULTIPLIER * mad
    flagged = tuple(p.item for p in pairs if abs(p.log_relative - centre) > threshold)
    flagged_set = set(flagged)
    kept = tuple(p for p in pairs if p.item not in flagged_set)

    return OutlierReport(
        median=centre,
        mad=mad,
        threshold=threshold,
        flagged=flagged,
        kept=kept,
        applied=True,
    )
