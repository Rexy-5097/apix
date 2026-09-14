"""The collection contract an automated adapter must implement, as values.

Nothing here is new methodology. Every constant restates a frozen decision so the
automated path cannot drift from the manual one:

==========================  ==================================================
Search contract             ``compliance/manual-collection-procedure.md`` s3
Departure bands 2-6         ADR-0065 s4, ``day-1-contract.md``
Earliest flight per band    ADR-0065 s4 -- never by price
APW vector                  spec A.3, ``APWBucket`` -- exact lead time
Pacing floor                ``acquisition-protocol.md`` s12
==========================  ==================================================

The APW vector is read from :class:`~apix.schemas.enums.APWBucket` rather than
typed again, so the two cannot disagree. There is no T+21 in it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from apix.schemas.enums import APWBucket
from apix.schemas.observation import DEPARTURE_HOUR_BAND_HOURS

#: IST. Every timestamp the collector records is naive IST, matching the store.
IST = ZoneInfo("Asia/Kolkata")

#: The frozen production APW vector, spec A.3. Read from the enum, never retyped.
FROZEN_APW: tuple[int, ...] = tuple(b.value for b in APWBucket)

#: Departure-hour bands collected -- ADR-0065 s4. 06:00-20:59.
CONTRACT_BANDS: tuple[int, ...] = (2, 3, 4, 5, 6)

#: The route frame this track is scoped to -- ADR-0065 s3.
FRAME_ROUTES: frozenset[tuple[str, str]] = frozenset({("DEL", "BOM")})

#: acquisition-protocol.md s12: at least 10 s between requests to one source group.
MIN_INTERVAL_FLOOR_SECONDS = 10.0


class ConfigError(ValueError):
    """A run configuration that would not measure the contracted observation."""


def band_of(departure: time) -> int:
    """3-hour departure band anchored at 00:00 IST -- spec B.2.2."""
    return departure.hour // DEPARTURE_HOUR_BAND_HOURS


def band_window(band: int) -> str:
    """Human-readable window, e.g. ``06:00-08:59`` for band 2."""
    start = band * DEPARTURE_HOUR_BAND_HOURS
    end = start + DEPARTURE_HOUR_BAND_HOURS - 1
    return f"{start:02d}:00-{end:02d}:59"


def ist_now() -> datetime:
    """Current IST wall-clock time, naive, to the second."""
    return datetime.now(IST).replace(tzinfo=None, microsecond=0)


@dataclass(frozen=True, slots=True)
class CollectionContract:
    """What one search must be. Every field is fixed by the frozen procedure.

    The fields exist so they are *recorded* with every run, not so they can be
    changed: any value other than the contracted one raises, because a search
    for two adults or in USD is a different observation, not a variant of this
    one.
    """

    origin: str = "DEL"
    destination: str = "BOM"
    carrier: str = "6E"
    adults: int = 1
    children: int = 0
    infants: int = 0
    cabin: str = "ECONOMY"
    trip_type: str = "ONE_WAY"
    currency: str = "INR"
    fare_type: str = "REGULAR"
    signed_in: bool = False
    nearby_airports: bool = False
    nonstop_only: bool = True
    #: The fare family taken for every selected flight. Lite is never substituted.
    fare_family: str = "Saver"

    def __post_init__(self) -> None:
        fixed: dict[str, tuple[object, object]] = {
            "adults": (self.adults, 1),
            "children": (self.children, 0),
            "infants": (self.infants, 0),
            "cabin": (self.cabin, "ECONOMY"),
            "trip_type": (self.trip_type, "ONE_WAY"),
            "currency": (self.currency, "INR"),
            "fare_type": (self.fare_type, "REGULAR"),
            "signed_in": (self.signed_in, False),
            "nearby_airports": (self.nearby_airports, False),
            "nonstop_only": (self.nonstop_only, True),
            "carrier": (self.carrier, "6E"),
            "fare_family": (self.fare_family, "Saver"),
        }
        wrong = sorted(k for k, (got, want) in fixed.items() if got != want)
        if wrong:
            raise ConfigError(
                f"contract fields {wrong} differ from the frozen collection contract; "
                "a different search is a different observation, not a variant of this one"
            )
        if (self.origin, self.destination) not in FRAME_ROUTES:
            raise ConfigError(
                f"route {self.origin}-{self.destination} is outside the frozen frame "
                f"{sorted(FRAME_ROUTES)} (ADR-0065 s3)"
            )


@dataclass(frozen=True, slots=True)
class SearchParams:
    """One search: the contract applied to one travel date on one collection date."""

    source_id: str
    contract: CollectionContract
    collection_date: date
    travel_date: date

    @property
    def lead_time_days(self) -> int:
        return (self.travel_date - self.collection_date).days

    @property
    def apw_bucket(self) -> APWBucket | None:
        return APWBucket.from_lead_time(self.lead_time_days)

    def as_record(self) -> dict[str, object]:
        """The parameters as recorded evidence, with deterministic key order."""
        c = self.contract
        return {
            "source_id": self.source_id,
            "origin": c.origin,
            "destination": c.destination,
            "collection_date": self.collection_date.isoformat(),
            "travel_date": self.travel_date.isoformat(),
            "lead_time_days": self.lead_time_days,
            "apw_bucket": self.apw_bucket.value if self.apw_bucket else None,
            "carrier": c.carrier,
            "adults": c.adults,
            "children": c.children,
            "infants": c.infants,
            "cabin": c.cabin,
            "trip_type": c.trip_type,
            "currency": c.currency,
            "fare_type": c.fare_type,
            "signed_in": c.signed_in,
            "nearby_airports": c.nearby_airports,
            "nonstop_only": c.nonstop_only,
            "fare_family": c.fare_family,
            "departure_bands": list(CONTRACT_BANDS),
            "selection_rule": "earliest eligible departure per band; never by price",
        }


def parse_apw(text: str) -> tuple[int, ...]:
    """Parse ``"1,3,7"`` into lead times, refusing anything outside spec A.3."""
    try:
        values = tuple(int(part) for part in text.split(",") if part.strip())
    except ValueError as exc:
        raise ConfigError(f"APW list {text!r} is not comma-separated integers") from exc
    return validate_apw(values)


def validate_apw(values: Sequence[int]) -> tuple[int, ...]:
    """Every lead time must be a frozen bucket; duplicates are refused."""
    if not values:
        raise ConfigError("APW list is empty")
    unknown = sorted(set(values) - set(FROZEN_APW))
    if unknown:
        raise ConfigError(
            f"lead times {unknown} are not in the frozen APW vector {FROZEN_APW} "
            "(spec A.3 assigns by EXACT lead time; T+21 is not a production bucket)"
        )
    if len(set(values)) != len(values):
        raise ConfigError(f"APW list {list(values)} repeats a bucket")
    return tuple(sorted(values))


@dataclass(frozen=True, slots=True)
class CollectionConfig:
    """One run: a source, a collection date, the travel dates, and the window."""

    source: str
    collection_date: date
    travel_dates: tuple[date, ...]
    contract: CollectionContract
    window_id: str = "primary"
    window_start: time = time(21, 0)
    window_end: time = time(22, 0)
    min_interval_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.travel_dates:
            raise ConfigError("a run needs at least one travel date")
        if len(set(self.travel_dates)) != len(self.travel_dates):
            raise ConfigError("travel dates repeat")
        early = sorted(d.isoformat() for d in self.travel_dates if d <= self.collection_date)
        if early:
            raise ConfigError(f"travel dates {early} are not after the collection date")
        if self.min_interval_seconds < MIN_INTERVAL_FLOOR_SECONDS:
            raise ConfigError(
                f"min_interval_seconds={self.min_interval_seconds} is below the "
                f"{MIN_INTERVAL_FLOOR_SECONDS:.0f} s floor in acquisition-protocol.md s12"
            )

    @classmethod
    def for_apw(
        cls,
        source: str,
        collection_date: date,
        apw: Sequence[int],
        contract: CollectionContract | None = None,
        **kw: object,
    ) -> CollectionConfig:
        lead_times = validate_apw(apw)
        return cls(
            source=source,
            collection_date=collection_date,
            travel_dates=tuple(collection_date + timedelta(days=n) for n in lead_times),
            contract=contract or CollectionContract(),
            **kw,  # type: ignore[arg-type]
        )

    @property
    def lead_times(self) -> tuple[int, ...]:
        return tuple((d - self.collection_date).days for d in self.travel_dates)

    @property
    def off_frame_lead_times(self) -> tuple[int, ...]:
        """Lead times matching no frozen bucket. Collected, then excluded by spec A.3."""
        return tuple(n for n in self.lead_times if n not in FROZEN_APW)

    def search_params(self, source_id: str) -> tuple[SearchParams, ...]:
        """One search per travel date, in ascending travel-date order."""
        return tuple(
            SearchParams(
                source_id=source_id,
                contract=self.contract,
                collection_date=self.collection_date,
                travel_date=d,
            )
            for d in sorted(self.travel_dates)
        )

    def frame_id(self, suffix: str) -> str:
        """Frame label that describes exactly the lead times this run collects.

        Built from the configured dates, never typed, so the label cannot
        misdescribe its own wave -- the defect the Day-1 runs carry.
        """
        c = self.contract
        lead = "-".join(f"T{n}" for n in sorted(self.lead_times))
        return f"{c.origin}-{c.destination}/{c.carrier}/AIRLINE_DIRECT/{lead}{suffix}"

    def declared_window(self) -> tuple[datetime, datetime]:
        start = datetime.combine(self.collection_date, self.window_start)
        end = datetime.combine(self.collection_date, self.window_end)
        if end <= start:
            end += timedelta(days=1)
        return start, end


__all__ = [
    "CONTRACT_BANDS",
    "FRAME_ROUTES",
    "FROZEN_APW",
    "IST",
    "MIN_INTERVAL_FLOOR_SECONDS",
    "CollectionConfig",
    "CollectionContract",
    "ConfigError",
    "SearchParams",
    "band_of",
    "band_window",
    "ist_now",
    "parse_apw",
    "validate_apw",
]
