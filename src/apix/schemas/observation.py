"""The canonical observation and its entitlements — spec A and B.4.

Immutable by construction. An observation that has entered the index path must
not be mutable, or reproducibility (spec P) cannot be reasoned about.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from apix.schemas.enums import (
    APWBucket,
    Availability,
    ChangePolicy,
    Channel,
    FareClass,
    SourceType,
)

# Spec B.2: 3-hour bands anchored at 00:00 IST.
DEPARTURE_HOUR_BAND_HOURS = 3


@dataclass(frozen=True, slots=True)
class Entitlements:
    """What the fare actually entitles the passenger to — spec B.4.

    These three fields, not the marketing label, determine the canonical fare
    class. ``fare_family_raw`` is stored for audit and never used for matching.
    """

    checked_baggage_kg: int
    change_permitted: ChangePolicy
    cancellation_permitted: ChangePolicy

    def __post_init__(self) -> None:
        if self.checked_baggage_kg < 0:
            raise ValueError(f"checked_baggage_kg must be >= 0, got {self.checked_baggage_kg}")

    def fare_class(self) -> FareClass:
        """Derive the canonical fare class — spec B.4, LOCKED mapping.

        FLEX is tested first: the spec's STANDARD condition is explicitly
        "checked_baggage_kg > 0 **and not FLEX**", so FLEX takes precedence.
        """
        if self.change_permitted is ChangePolicy.FREE and self.cancellation_permitted in (
            ChangePolicy.FREE,
            ChangePolicy.FEE,
        ):
            return FareClass.FLEX
        if self.checked_baggage_kg == 0:
            return FareClass.HAND_ONLY
        return FareClass.STANDARD


@dataclass(frozen=True, slots=True)
class Observation:
    """One displayed, transactable offer — spec A.1.

    One adult passenger, one seat, one-way, economy cabin, from one channel at
    one instant. Round-trip fares are **not** 2x one-way and are out of scope
    for v1.

    ``payable_fare`` is a :class:`~decimal.Decimal`, not a float: spec Notation
    requires monetary arithmetic in decimal, never binary floating point, before
    the log transform.
    """

    observation_id: str
    origin: str
    destination: str
    travel_date: date
    departure_time_local: time
    observation_ts: datetime
    collection_date: date
    carrier: str
    flight_number: str
    stops: int
    duration_minutes: int
    fare_family_raw: str
    channel: Channel
    source_id: str
    entitlements: Entitlements
    payable_fare: Decimal
    source_type: SourceType
    availability: Availability = Availability.AVAILABLE

    @property
    def lead_time_days(self) -> int:
        """Days between the collection date and departure — spec A.2.

        Derived rather than stored, so it cannot contradict the dates it comes
        from.
        """
        return (self.travel_date - self.collection_date).days

    @property
    def apw_bucket(self) -> APWBucket | None:
        """Advance-purchase bucket, or None when the lead time matches none."""
        return APWBucket.from_lead_time(self.lead_time_days)

    @property
    def fare_class(self) -> FareClass:
        """Canonical fare class, derived from entitlements — spec B.4."""
        return self.entitlements.fare_class()

    @property
    def day_of_week(self) -> int:
        """ISO weekday of the *departure*, 1 = Monday.

        The matched item includes day of week (spec B.2), and the recurring
        product is "this carrier's flight on this weekday". The weekday that
        identifies the product is therefore the travel date's, not the
        collection date's.
        """
        return self.travel_date.isoweekday()

    @property
    def departure_hour_band(self) -> int:
        """3-hour departure band anchored at 00:00 IST — spec B.2.

        Returns the band index 0..7, where 0 is [00:00, 03:00).
        """
        return self.departure_time_local.hour // DEPARTURE_HOUR_BAND_HOURS

    @property
    def route(self) -> str:
        """Ordered origin-destination pair. DEL-BOM is not BOM-DEL."""
        return f"{self.origin}-{self.destination}"
