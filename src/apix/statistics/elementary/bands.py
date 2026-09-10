"""Tier-2 departure bands and the constructed band price — spec B.2.3.

Tier 2 is an **identity relaxation, not a threshold relaxation**. It relaxes how
specifically an item is identified — from a flight number to a departure-hour
slot — so a cell whose flight numbers churn can still form a matched set. It
does **not** relax ``min_matched_items_per_cell``, and it does **not** guarantee
a larger matched sample: because a band is one item however many flights it
holds, a carrier with four flights clustered into two bands passes at Tier 1 and
fails at Tier 2.

Several flights can occupy one band, so the band needs a price:

.. code-block:: text

    p(b,t) = exp( (1/n) * sum over j in b of ln p(j,t) )

**Why the geometric mean and nothing else.** Substituted into spec D.2, with the
same flight set in both periods, the band log-relative is

.. code-block:: text

    ln p(b,t) - ln p(b,t-7) = (1/n) * sum_j [ ln p(j,t) - ln p(j,t-7) ]

so the cell Jevons **telescopes into a geometric mean of matched flight-level
relatives**, equally weighted per band, and reduces to the Tier-1 Jevons when
every band holds one flight.

The identity is **exact in real arithmetic and equal within spec Q.1's 1e-12
tolerance in IEEE 754** — the two sides group their sums differently and land a
few ulp apart (~7e-16 measured). Bit identity is *not* claimed and must not be
asserted; ``tests/test_redteam_regressions.py`` pins the tolerance instead.

No other central-tendency measure has that property: the arithmetic mean
breaks the identity, and the median is discontinuous in band membership and
equals the arithmetic mean at n = 2.
Robustness is already supplied one level up by spec D.7.

**band_overlap measures constituent flight identities, not band recurrence.**
Whether the Tier-2 *band itself* recurs is already answered by whether the item
matched at all — an unmatched band produces no diagnostics. ``band_overlap``
answers the different question of how much of the band's *flight membership*
carried over, and the two can diverge completely: a band whose every flight is
renumbered while the count holds gives ``membership_delta = 0`` and
``overlap = 0.0`` simultaneously. The field name is the one the approved
specification uses and is not changed here.

**The honest limitation.** When band membership *differs* between periods — which
is why the pair is at Tier 2 — the two band prices are computed over different
flight sets and the ratio is a **unit-value ratio**. Composition enters exactly
to the extent that membership changes *and* within-band fares are dispersed;
zero dispersion makes membership changes harmless however large. That is why
both are published, and why neither alone is interpretable.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from datetime import time
from decimal import Decimal

from apix.schemas.observation import DEPARTURE_HOUR_BAND_HOURS, Observation


def hour_band(departure: time) -> int:
    """3-hour departure band anchored at 00:00 IST — spec B.2.2, LOCKED.

    Returns the band index 0..7, where 0 is ``[00:00, 03:00)``.
    """
    return departure.hour // DEPARTURE_HOUR_BAND_HOURS


def band_log_price(fares: Sequence[Decimal]) -> float:
    """Mean of the log fares in a band — the band price in log space.

    Computed directly in logs rather than as ``ln(band_price(...))`` so the
    telescoping identity above holds without an ``exp``/``log`` round trip.
    Each fare is converted from :class:`~decimal.Decimal` individually, so
    monetary values stay in decimal right up to the log transform as the spec's
    notation section requires.

    Raises:
        ValueError: on an empty band, or a non-positive fare. A band with no
            members has no price, and ``ln`` of a non-positive fare is where a
            silent NaN would enter the index.
    """
    if not fares:
        raise ValueError("a band with no admissible fares has no price (spec B.2.3)")
    # Sorted before summing. Floating-point addition is not associative, so an
    # unordered reduction gives different last bits for the same multiset and
    # breaks the bit-identity guarantee of spec P.1/P.2. Sorting the *values*
    # makes the band price a function of the set, not of the caller's iteration
    # order. Caught by test_band_price_is_order_independent_to_the_bit.
    total = 0.0
    for fare in sorted(fares):
        if fare <= 0:
            raise ValueError(
                f"non-positive fare {fare} reached the band price; admissibility "
                "(spec A.6) must run first"
            )
        total += math.log(float(fare))
    return total / len(fares)


def band_price(fares: Sequence[Decimal]) -> float:
    """Geometric mean of the admissible fares in a band — spec B.2.3.

    A **constructed** price, not an observed one. It represents the carrier's
    departure-hour slot rather than any individual flight.
    """
    return math.exp(band_log_price(fares))


def log_dispersion(fares: Sequence[Decimal]) -> float:
    """Population standard deviation of ``ln(fare)`` within a band — spec B.2.3.

    Bounds how far a membership change can move the band price. Zero for a
    single-member band, which is the correct answer: a one-flight band cannot
    have its price moved by dispersion.
    """
    if len(fares) < 2:
        return 0.0
    centre = band_log_price(fares)
    # Sorted for the same reason as band_log_price: the reduction must be a
    # function of the set of fares, not of the order they arrive in (spec P.2).
    total = 0.0
    for fare in sorted(fares):
        deviation = math.log(float(fare)) - centre
        total += deviation * deviation
    return math.sqrt(total / len(fares))


def band_occupancy(observations: Iterable[Observation]) -> int:
    """Count of distinct 3-hour bands occupied by a set of observations.

    The direct input to the Tier-2 density question: a Tier-2 cell needs its
    carrier's flights spread across at least ``min_matched_items_per_cell``
    distinct bands in **both** periods, and only eight bands exist — about six
    in a realistic 05:00-23:00 operating day.
    """
    return len({hour_band(obs.departure_time_local) for obs in observations})
