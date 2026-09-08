"""Weight validation, normalisation and renormalisation — spec F.4 and G.

The subtle rule this module exists for (spec F.4):

    Dropping a route without renormalising SILENTLY REWEIGHTS EVERYTHING ELSE.

Renormalisation over the live set is mandatory, and the weight vector is
asserted to sum to one on every publication (INV-1).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from apix.schemas.enums import APWBucket
from apix.schemas.results import RELATIVE_TOLERANCE

# Spec G.4 — the declared v1 choice. Equal weights across the seven APW buckets.
#
# EMPIRICAL / OPEN — OQ-7. No public Indian booking lead-time distribution is
# known. Inventing a booking curve would be worse than not having one, so v1
# declares equal weights and publishes a sensitivity band. Booking-curve
# weighting is claimed only once a data source for it exists.
EQUAL_APW_WEIGHT = 1.0 / len(APWBucket)


class WeightError(ValueError):
    """A weight vector that cannot be used. Never silently repaired."""


def validate(weights: Mapping[str, float]) -> None:
    """Check a weight vector is usable — spec G.5.

    Raises:
        WeightError: if empty, if any weight is negative or non-finite, or if
            the total is zero.

    A negative weight is a defect, not a value (spec G.5). A zero total means
    every member is weightless, which is not a renormalisable state — it is a
    caller error that must surface rather than produce a division by zero.
    """
    if not weights:
        raise WeightError("weight vector is empty")

    negative = sorted(k for k, v in weights.items() if v < 0)
    if negative:
        raise WeightError(f"negative weights are a defect, not a value (spec G.5): {negative}")

    non_finite = sorted(
        k for k, v in weights.items() if v != v or v in (float("inf"), float("-inf"))
    )
    if non_finite:
        raise WeightError(f"non-finite weights: {non_finite}")

    total = sum(weights[k] for k in sorted(weights))
    if total <= 0:
        raise WeightError(f"weights sum to {total}; cannot normalise a zero-weight set")


def normalise(weights: Mapping[str, float]) -> dict[str, float]:
    """Scale a weight vector to sum to one — spec G.5.

    Args:
        weights: Raw, unnormalised weights keyed by member id.

    Returns:
        Normalised weights summing to 1 within
        :data:`~apix.schemas.results.RELATIVE_TOLERANCE`.

    Raises:
        WeightError: per :func:`validate`.

    Keys are summed in sorted order so the total — and therefore every
    normalised weight — is bit-identical regardless of input ordering
    (spec P.2).
    """
    validate(weights)
    ordered = sorted(weights)
    total = sum(weights[k] for k in ordered)
    return {k: weights[k] / total for k in ordered}


def renormalise_over_live_set(
    weights: Mapping[str, float], live: Iterable[str]
) -> dict[str, float]:
    """Renormalise weights over the surviving members — spec F.4.

        w'[r] = w[r] / sum over j in L of w[j],  for r in L

    Args:
        weights: The full weight vector, including suppressed members.
        live: Ids of members that survived suppression.

    Returns:
        Weights over the live set only, summing to 1. Empty dict when the live
        set is empty — every member suppressed is a real state (the index does
        not publish), not an error to raise on.

    Raises:
        WeightError: if a live id is absent from ``weights``, or if the live
            members carry zero total weight.
    """
    live_ids = sorted(set(live))
    if not live_ids:
        return {}

    missing = [k for k in live_ids if k not in weights]
    if missing:
        raise WeightError(f"live members have no weight assigned: {missing}")

    total = sum(weights[k] for k in live_ids)
    if total <= 0:
        raise WeightError(
            f"live members {live_ids} carry total weight {total}; "
            "cannot renormalise. Suppress them instead of publishing a zero-weight index."
        )

    return {k: weights[k] / total for k in live_ids}


def sums_to_one(weights: Mapping[str, float], *, tolerance: float = RELATIVE_TOLERANCE) -> bool:
    """Whether a weight vector satisfies INV-1.

    Asserted on every publication (spec F.4). Uses a relative tolerance rather
    than exact equality per spec Q.1 — these are exact statements in real
    arithmetic evaluated in binary floating point.
    """
    if not weights:
        return False
    total = sum(weights[k] for k in sorted(weights))
    return abs(total - 1.0) <= tolerance


def suppressed_weight_share(weights: Mapping[str, float], live: Iterable[str]) -> float:
    """Share of total weight held by suppressed members — spec I.

    Published, never hidden: above ``max_suppressed_weight`` (15%) APIx
    publishes with a quality caveat.
    """
    validate(weights)
    live_ids = set(live)
    ordered = sorted(weights)
    total = sum(weights[k] for k in ordered)
    suppressed = sum(weights[k] for k in ordered if k not in live_ids)
    return suppressed / total


@dataclass(frozen=True, slots=True)
class APWWeighting:
    """Advance-purchase weights — spec G.4.

    ``equal()`` is the declared v1 choice. The alternative curves exist only to
    produce the published sensitivity band (spec G.4) and are labelled
    *illustrative alternatives*, **never** as estimates of the true curve.
    """

    weights: dict[APWBucket, float]
    label: str

    @classmethod
    def equal(cls) -> APWWeighting:
        """The declared v1 weighting: 1/7 per bucket."""
        return cls(
            weights={bucket: EQUAL_APW_WEIGHT for bucket in APWBucket},
            label="equal-v1-declared",
        )

    @classmethod
    def illustrative(cls, shares: Sequence[float], label: str) -> APWWeighting:
        """An illustrative alternative curve, for the sensitivity band only.

        Raises:
            WeightError: if the number of shares does not match the bucket count,
                or the shares are not a usable weight vector.
        """
        buckets = list(APWBucket)
        if len(shares) != len(buckets):
            raise WeightError(f"expected {len(buckets)} APW shares, got {len(shares)}")
        raw = {str(b.value): float(s) for b, s in zip(buckets, shares, strict=True)}
        normalised = normalise(raw)
        return cls(
            weights={b: normalised[str(b.value)] for b in buckets},
            label=f"illustrative-{label}",
        )

    def is_declared_v1(self) -> bool:
        """Whether this is the declared choice rather than an illustration."""
        return self.label == "equal-v1-declared"
