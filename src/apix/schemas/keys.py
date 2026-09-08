"""Cell, parent and item identity keys — spec B.2 and E.4.

Keys are frozen dataclasses with a deterministic ``sort_key``. Spec P.2 forbids
iteration over an unordered container where order affects the result, so every
collection of cells is processed in explicitly sorted key order.
"""

from __future__ import annotations

from dataclasses import dataclass

from apix.schemas.enums import APWBucket, Channel, FareClass, Tier


@dataclass(frozen=True, slots=True, order=True)
class CellKey:
    """An elementary cell — one recurring product class — spec B.2.

    The identity fields differ by tier:

    * Tier 1 — carrier x flight_number x day_of_week x APW x fare_class x channel
    * Tier 2 — carrier x departure_hour_band x day_of_week x APW x fare_class x channel
    * Tier 3 — declared unit value; the cell has no within-cell item identity

    ``flight_number`` is populated at Tier 1 only, ``departure_hour_band`` at
    Tier 2 only. Both are None at Tier 3, where the cell is the route stratum
    itself and its price is an explicit unit value.
    """

    route: str
    tier: Tier
    carrier: str
    apw_bucket: APWBucket
    fare_class: FareClass
    channel: Channel
    day_of_week: int
    flight_number: str | None = None
    departure_hour_band: int | None = None

    def __post_init__(self) -> None:
        if self.tier is Tier.TIER_1 and self.flight_number is None:
            raise ValueError("Tier 1 cell key requires flight_number (spec B.2)")
        if self.tier is Tier.TIER_2 and self.departure_hour_band is None:
            raise ValueError("Tier 2 cell key requires departure_hour_band (spec B.2)")
        if self.tier is Tier.TIER_1 and self.departure_hour_band is not None:
            raise ValueError("Tier 1 cell key must not carry departure_hour_band")
        if self.tier is Tier.TIER_2 and self.flight_number is not None:
            raise ValueError("Tier 2 cell key must not carry flight_number")

    @property
    def sort_key(self) -> tuple[str, int, str, int, str, str, int, str, int]:
        """Total order over cells, for deterministic reduction — spec P.2."""
        return (
            self.route,
            self.tier.value,
            self.carrier,
            self.apw_bucket.value,
            self.fare_class.value,
            self.channel.value,
            self.day_of_week,
            self.flight_number or "",
            -1 if self.departure_hour_band is None else self.departure_hour_band,
        )

    def parent(self) -> ParentKey:
        """The stratum this cell inherits a relative from — spec E.4.

        ``parent(c) = (route, apw_bucket, fare_class, channel)`` — the cell key
        with carrier and flight identity dropped. Note it drops ``day_of_week``
        as well: the spec's parent tuple names four fields and this one follows
        it literally.
        """
        return ParentKey(
            route=self.route,
            apw_bucket=self.apw_bucket,
            fare_class=self.fare_class,
            channel=self.channel,
        )


@dataclass(frozen=True, slots=True, order=True)
class ParentKey:
    """A parent stratum — spec E.4.

    ``(route, apw_bucket, fare_class, channel)``. A cell with no defined
    relative inherits **this stratum's relative**, never its level: inheriting
    the level would teleport the cell onto the parent's path and erase its own
    accumulated history.
    """

    route: str
    apw_bucket: APWBucket
    fare_class: FareClass
    channel: Channel

    @property
    def sort_key(self) -> tuple[str, int, str, str]:
        return (self.route, self.apw_bucket.value, self.fare_class.value, self.channel.value)


@dataclass(frozen=True, slots=True, order=True)
class ItemKey:
    """Identity of an item *within* a cell, for matching across t and t-7.

    Spec D.1 matches on "an item's identity within a cell", which is its
    matching key. Within a Tier 1 cell the carrier, flight number, weekday, APW,
    fare class and channel are already fixed by the cell key, so what
    distinguishes items inside the cell is the specific departure — identified
    here by scheduled local departure time.

    At Tier 3 there is no within-cell item identity (the cell publishes a
    declared unit value), so Tier 3 cells never form a matched set.
    """

    departure_time_local: str

    @property
    def sort_key(self) -> str:
        return self.departure_time_local
