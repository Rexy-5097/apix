"""Item, cell and parent identity keys — spec B.2, E.4, E.6 (methodology v2.1).

**The item and the cell are different objects.** v2.0 used one tuple for both
roles, which made ``min_matched_items_per_cell = 3`` unsatisfiable and prevented
any Tier-1 cell from ever publishing a relative (AMB-1). The separation here is
the correction:

* :class:`ItemKey` — the unit of **matching**. What must reappear at *t* and
  *t-7* for a price relative to exist. Carries no weight and has no level.
* :class:`CellKey` — the unit of **averaging and weighting**. The elementary
  aggregate over which spec D.2 takes a geometric mean, and the lowest level at
  which an index *level* exists.
* :class:`ParentKey` — a strictly coarser stratum supplying a **relative** for
  carry (spec E.4) and a **level** for new-cell entry (spec J.1).

Keys are frozen dataclasses with a deterministic ``sort_key``. Spec P.2 forbids
iteration over an unordered container where order affects the result, so every
collection of keys is processed in explicitly sorted order.
"""

from __future__ import annotations

from dataclasses import dataclass

from apix.schemas.enums import APWBucket, Channel, FareClass, Tier


@dataclass(frozen=True, slots=True, order=True)
class CellKey:
    """An elementary cell — the aggregation and weighting stratum — spec B.2.1.

    .. code-block:: text

        c = (route, carrier, day_of_week, apw_bucket, fare_class, channel)

    **Invariant across all three tiers.** A tier change alters the *item*
    definition only, never this key. That invariance is load-bearing: spec F.5
    fixes weights for the index year, so a cell key that changed with the tier
    would re-partition the cells and re-derive ``v[c|r]`` mid-year on any tier
    degradation.

    ``flight_number`` and ``departure_hour_band`` are **deliberately absent** —
    they identify items, not cells. Their presence here was AMB-1.

    ``day_of_week`` is mechanically determined by ``(t, apw_bucket)`` and so
    partitions nothing within a collection date. It is retained because it is
    the **chain identifier**: without it one key would name seven interleaved
    weekly level sequences and ``I(c,t)`` would be overwritten daily by a level
    belonging to a different chain (spec C.2).
    """

    route: str
    carrier: str
    day_of_week: int
    apw_bucket: APWBucket
    fare_class: FareClass
    channel: Channel

    @property
    def sort_key(self) -> tuple[str, str, int, int, str, str]:
        """Total order over cells, for deterministic reduction — spec P.2."""
        return (
            self.route,
            self.carrier,
            self.day_of_week,
            self.apw_bucket.value,
            self.fare_class.value,
            self.channel.value,
        )

    def parent(self) -> ParentKey:
        """The stratum this cell inherits from — spec E.4.

        The cell key with **carrier dropped**, and nothing else.

        At a fixed collection date and APW bucket the travel date and therefore
        the weekday are determined, so ``carrier`` is the only dimension in this
        key that genuinely varies at *t*. A parent that dropped ``day_of_week``
        instead would contain *exactly the cell's own observations* and could
        never supply a relative when the cell could not — a dead rule.
        """
        return ParentKey(
            route=self.route,
            day_of_week=self.day_of_week,
            apw_bucket=self.apw_bucket,
            fare_class=self.fare_class,
            channel=self.channel,
        )


@dataclass(frozen=True, slots=True, order=True)
class ParentKey:
    """A parent stratum — spec E.4, E.6.

    .. code-block:: text

        parent(c) = (route, day_of_week, apw_bucket, fare_class, channel)

    A **computation stratum, never a publication stratum**: it carries no weight,
    contributes no level to any aggregate, and is never published as an index.
    Two quantities are derived from it and they are different objects computed in
    opposite directions (spec E.6.10, E.7.5):

    ``J(P,t)``
        the parent **relative**, a Jevons over the parent's own matched items,
        computed **bottom-up from raw observations**. Used by spec E.4 carry
        only.

    ``I(P,t)``
        the parent **reference level**, a weighted mean over independently
        determined child levels, computed **top-down**. Used by spec J.1
        new-cell entry only.

    ``I(P,t) = I(P,t-7) * J(P,t)`` is **forbidden**. The parent is not a chained
    index: it has no base period and no history of its own, and writing that
    equation would create two competing definitions of the parent level that
    diverge silently.
    """

    route: str
    day_of_week: int
    apw_bucket: APWBucket
    fare_class: FareClass
    channel: Channel

    @property
    def sort_key(self) -> tuple[str, int, int, str, str]:
        return (
            self.route,
            self.day_of_week,
            self.apw_bucket.value,
            self.fare_class.value,
            self.channel.value,
        )


@dataclass(frozen=True, slots=True, order=True)
class ItemKey:
    """The recurring product class — the unit of matching — spec B.2.2.

    ==========  ==========================================
    Tier 1      ``(carrier, flight_number)``
    Tier 2      ``(carrier, departure_hour_band)``
    Tier 3      no within-cell item identity; the cell publishes a unit value
    ==========  ==========================================

    **On the ``carrier`` field.** Inside a cell, carrier is constant, so its
    presence here cannot change any matched set or index value *there*. At the
    **parent** (spec E.6), carriers are pooled and this field is what keeps
    ``6E101`` and ``AI101`` distinct. It is therefore normative, not decorative,
    and must not be removed as redundant.

    **Not keyed by departure time.** v2.0 identified items by
    ``departure_time_local`` to the second, so a ten-minute retiming unmatched a
    flight from itself. A recurring product class must survive a schedule
    adjustment.
    """

    tier: Tier
    carrier: str
    flight_number: str | None = None
    departure_hour_band: int | None = None

    def __post_init__(self) -> None:
        if self.tier is Tier.TIER_1:
            if self.flight_number is None:
                raise ValueError("Tier 1 item key requires flight_number (spec B.2.2)")
            if self.departure_hour_band is not None:
                raise ValueError("Tier 1 item key must not carry departure_hour_band")
        elif self.tier is Tier.TIER_2:
            if self.departure_hour_band is None:
                raise ValueError("Tier 2 item key requires departure_hour_band (spec B.2.2)")
            if self.flight_number is not None:
                raise ValueError("Tier 2 item key must not carry flight_number")
        else:
            raise ValueError(
                "Tier 3 has no within-cell item identity (spec B.2.2); "
                "item_key_for returns None rather than constructing an ItemKey"
            )

    @property
    def sort_key(self) -> tuple[int, str, str, int]:
        """Total order over items, for deterministic reduction — spec P.2."""
        return (
            self.tier.value,
            self.carrier,
            self.flight_number or "",
            -1 if self.departure_hour_band is None else self.departure_hour_band,
        )
