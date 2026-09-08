"""Admissibility filter — spec A.6.

An observation is rejected from the index, and **retained in the store with a
reason code**, if a required field is missing, entitlements are undeterminable,
the lead time matches no APW bucket, the timestamp falls outside the collection
window, it is a duplicate, or it fails the outlier rule.

Duplicates (D.4) and outliers (D.7) are handled in their own modules because
they are properties of a *set* of observations, not of one observation.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import time

from apix.schemas.enums import Availability, ExclusionReason
from apix.schemas.observation import Observation
from apix.schemas.results import ExcludedObservation


@dataclass(frozen=True, slots=True)
class CollectionWindow:
    """The fixed daily window all collection runs inside — spec A.5.

    **EMPIRICAL / OPEN — OQ-1.** The window's start and end times are a
    published methodology parameter and are *not yet fixed*. This class takes
    them as configuration precisely so no value is invented here: a caller must
    supply the window, and the value used is recorded in the methodology
    parameters rather than buried in code.

    The window is inclusive of ``start`` and exclusive of ``end``.
    """

    start: time
    end: time

    def contains(self, at: time) -> bool:
        """Whether a timestamp falls inside the window.

        Handles a window that wraps past midnight (start > end), which is a real
        possibility for an overnight collection run.
        """
        if self.start <= self.end:
            return self.start <= at < self.end
        return at >= self.start or at < self.end


@dataclass(frozen=True, slots=True)
class AdmissibilityResult:
    """Partitioned observations, with a reason for every exclusion."""

    admissible: tuple[Observation, ...]
    excluded: tuple[ExcludedObservation, ...]

    @property
    def exclusion_rate(self) -> float:
        """Published per source — spec A.6."""
        total = len(self.admissible) + len(self.excluded)
        return len(self.excluded) / total if total else 0.0


def _first_failure(
    obs: Observation, window: CollectionWindow | None
) -> tuple[ExclusionReason, str] | None:
    """Return the first admissibility failure, or None if admissible.

    Order matters only for which reason is reported; an observation failing
    several checks is excluded regardless.
    """
    if not obs.origin or not obs.destination or not obs.carrier:
        return ExclusionReason.MISSING_REQUIRED_FIELD, "origin/destination/carrier"
    if not obs.flight_number:
        return ExclusionReason.MISSING_REQUIRED_FIELD, "flight_number"
    if not obs.source_id:
        return ExclusionReason.MISSING_REQUIRED_FIELD, "source_id"

    # Spec A.4: the payable fare is what the household pays. A non-positive fare
    # is not a cheap ticket, it is a parse failure — and ln(p) is undefined for
    # it, so it can never reach the Jevons relative.
    if obs.payable_fare <= 0:
        return ExclusionReason.NON_POSITIVE_FARE, f"payable_fare={obs.payable_fare}"

    # Spec D.6: a sold-out flight is not a missing price, it is a disappeared
    # item. It is excluded from the matched set like any other unmatched item.
    if obs.availability is Availability.SOLD_OUT:
        return ExclusionReason.SOLD_OUT, "no seat available at any fare in the class"

    # Spec A.3: assignment is by EXACT lead time. No nearest-bucket rounding.
    if obs.apw_bucket is None:
        return (
            ExclusionReason.LEAD_TIME_MATCHES_NO_BUCKET,
            f"lead_time_days={obs.lead_time_days}",
        )

    if window is not None and not window.contains(obs.observation_ts.time()):
        return (
            ExclusionReason.OUTSIDE_COLLECTION_WINDOW,
            f"observation_ts={obs.observation_ts.time().isoformat()}",
        )

    return None


def filter_admissible(
    observations: Iterable[Observation],
    window: CollectionWindow | None = None,
) -> AdmissibilityResult:
    """Partition observations into admissible and excluded — spec A.6.

    Args:
        observations: Candidate observations, in any order.
        window: The collection window (spec A.5). ``None`` disables the window
            check, which is correct only for synthetic data where no window has
            been declared — OQ-1 is open, so no default is invented here.

    Returns:
        An :class:`AdmissibilityResult`. Excluded observations carry a reason
        code and are never silently dropped.

    Output ordering is by ``observation_id`` so the result is deterministic
    regardless of input order (spec P.2).
    """
    admissible: list[Observation] = []
    excluded: list[ExcludedObservation] = []

    for obs in sorted(observations, key=lambda o: o.observation_id):
        failure = _first_failure(obs, window)
        if failure is None:
            admissible.append(obs)
        else:
            reason, detail = failure
            excluded.append(
                ExcludedObservation(
                    observation_id=obs.observation_id,
                    reason=reason,
                    detail=detail,
                    source_id=obs.source_id,
                )
            )

    return AdmissibilityResult(admissible=tuple(admissible), excluded=tuple(excluded))


def exclusion_rate_by_source(
    excluded: Sequence[ExcludedObservation], total_by_source: dict[str, int]
) -> dict[str, float]:
    """Exclusion rate per source — spec A.6.

    A rising rate is the earliest available signal that a site has been
    redesigned, so this is a published alarm rather than an internal counter.
    Callers supply ``total_by_source`` because the excluded records alone cannot
    know the denominator.

    The source is read from :attr:`ExcludedObservation.source_id`. An earlier
    implementation tried to recover it by string-parsing a ``source=`` token out
    of ``detail`` — a token nothing ever emitted — so the function structurally
    returned 0.0 for every source and the alarm could never fire.
    """
    counts: dict[str, int] = {}
    for item in excluded:
        if item.source_id:
            counts[item.source_id] = counts.get(item.source_id, 0) + 1
    return {
        source: counts.get(source, 0) / total
        for source, total in sorted(total_by_source.items())
        if total > 0
    }
