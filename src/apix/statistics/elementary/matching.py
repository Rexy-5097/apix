"""Matching primitives — spec B.2, B.3, C, D.1.

Two quantities are computed here and they are **different things** (spec B.3):

* **Identity stability** — does the product recur at all? Selects the tier.
* **Match coverage** — does enough of it survive conditioning to compute a
  relative from? The statistic-driving metric.

Conflating them is a named failure mode. Flight numbers can be perfectly stable
while the usable matched set collapses after conditioning on fare class, APW
bucket, channel and determinable entitlements.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from datetime import date, timedelta

from apix.schemas.enums import Tier
from apix.schemas.keys import CellKey, ItemKey
from apix.schemas.observation import Observation
from apix.schemas.results import MatchedPair

# Spec B.2 — LOCKED identity-stability thresholds that select the tier.
TIER_1_STABILITY_THRESHOLD = 0.70
TIER_2_STABILITY_THRESHOLD = 0.40

# Spec C.1 — the matched comparison is against t-7, never t-1.
MATCHING_LAG_DAYS = 7


def cell_key_for(obs: Observation, tier: Tier) -> CellKey:
    """Build the cell key for an observation at a given tier — spec B.2.

    Raises:
        ValueError: if ``obs`` has no APW bucket. Callers must filter through
            :func:`~apix.statistics.elementary.admissibility.filter_admissible`
            first; reaching here with an unbucketed observation is a pipeline
            ordering bug, not a data condition to paper over.
    """
    bucket = obs.apw_bucket
    if bucket is None:
        raise ValueError(
            f"observation {obs.observation_id} has lead_time_days={obs.lead_time_days}, "
            "which matches no APW bucket; it is inadmissible (spec A.3) and must "
            "be filtered before cell assignment"
        )

    # Written out per tier rather than unpacked from a shared dict: the identity
    # fields differ by tier, and spelling each one out is what lets the type
    # checker verify that a Tier 1 key really does carry a flight number and a
    # Tier 2 key really does carry an hour band.
    if tier is Tier.TIER_1:
        return CellKey(
            route=obs.route,
            tier=tier,
            carrier=obs.carrier,
            apw_bucket=bucket,
            fare_class=obs.fare_class,
            channel=obs.channel,
            day_of_week=obs.day_of_week,
            flight_number=obs.flight_number,
        )
    if tier is Tier.TIER_2:
        return CellKey(
            route=obs.route,
            tier=tier,
            carrier=obs.carrier,
            apw_bucket=bucket,
            fare_class=obs.fare_class,
            channel=obs.channel,
            day_of_week=obs.day_of_week,
            departure_hour_band=obs.departure_hour_band,
        )
    # Tier 3: a declared unit value. No flight identity, no hour band.
    return CellKey(
        route=obs.route,
        tier=tier,
        carrier=obs.carrier,
        apw_bucket=bucket,
        fare_class=obs.fare_class,
        channel=obs.channel,
        day_of_week=obs.day_of_week,
    )


def item_key_for(obs: Observation) -> ItemKey:
    """Identity of an item within its cell — spec D.1.

    Everything else that distinguishes the product is already fixed by the cell
    key, so what remains is the specific scheduled departure.
    """
    return ItemKey(departure_time_local=obs.departure_time_local.isoformat())


def identity_stability(
    observations: Iterable[Observation],
    route: str,
    window_dates: Sequence[date],
) -> float:
    """Share of a route's scheduled flights whose identity recurs — spec B.3.

    A flight number counts as *recurring* when it is observed at the same
    weekday slot on at least two distinct collection dates seven days apart
    within the window. One sighting is not recurrence.

    Returns 0.0 when the route has no scheduled flights in the window — an
    honest "no evidence of stability", which places the route at Tier 3 where
    the unit-value caveat applies.
    """
    by_flight: dict[tuple[str, str, int], set[date]] = {}
    for obs in observations:
        if obs.route != route:
            continue
        key = (obs.carrier, obs.flight_number, obs.day_of_week)
        by_flight.setdefault(key, set()).add(obs.collection_date)

    if not by_flight:
        return 0.0

    window = set(window_dates)
    recurring = 0
    for dates in by_flight.values():
        seen = dates & window if window else dates
        if any(d + timedelta(days=MATCHING_LAG_DAYS) in seen for d in seen):
            recurring += 1

    return recurring / len(by_flight)


def select_tier(stability: float) -> Tier:
    """Map identity stability onto the tier ladder — spec B.2, LOCKED.

    * ``>= 0.70`` -> Tier 1 (flight-identity match)
    * ``[0.40, 0.70)`` -> Tier 2 (schedule-slot match)
    * ``< 0.40`` -> Tier 3 (declared unit value)
    """
    if stability >= TIER_1_STABILITY_THRESHOLD:
        return Tier.TIER_1
    if stability >= TIER_2_STABILITY_THRESHOLD:
        return Tier.TIER_2
    return Tier.TIER_3


def match_coverage(matched_items: int, expected_recurring_items: int) -> float:
    """Share of expected recurring items that survive conditioning — spec B.3.

    **The floor this is compared against is EMPIRICAL / OPEN (OQ-2)** and is set
    from the seven-day collection spike, not invented here. This function
    computes the statistic; it deliberately applies no threshold.
    """
    if expected_recurring_items <= 0:
        return 0.0
    return matched_items / expected_recurring_items


def build_matched_set(
    observations_t: Iterable[Observation],
    observations_t_minus_7: Iterable[Observation],
    cell: CellKey,
    tier: Tier,
) -> tuple[MatchedPair, ...]:
    """Form M(c,t) — items present in BOTH t and t-7 — spec D.1.

    **Unmatched items enter neither side of the ratio.** An item present at t
    but not at t-7 contributes nothing: not to the numerator, and not as a new
    item at 100.

    Tier 3 cells have no within-cell item identity (the cell publishes a
    declared unit value), so they never form a matched set and this returns
    empty for them.

    Returns pairs sorted by item key, so the mean in spec D.2 reduces in a
    stable order (spec P.2).
    """
    if tier is Tier.TIER_3:
        return ()

    def index_by_item(obs_list: Iterable[Observation]) -> dict[ItemKey, Observation]:
        out: dict[ItemKey, Observation] = {}
        for obs in obs_list:
            if cell_key_for(obs, tier) != cell:
                continue
            out[item_key_for(obs)] = obs
        return out

    current = index_by_item(observations_t)
    prior = index_by_item(observations_t_minus_7)

    pairs: list[MatchedPair] = []
    for item in sorted(current.keys() & prior.keys(), key=lambda k: k.sort_key):
        now, before = current[item], prior[item]
        # Guarded by admissibility, but asserted here because ln(p) of a
        # non-positive price is where a silent NaN would enter the index.
        if now.payable_fare <= 0 or before.payable_fare <= 0:
            raise ValueError(
                f"non-positive fare reached matching for item {item.departure_time_local} "
                f"in cell {cell.sort_key}; admissibility (spec A.6) must run first"
            )
        pairs.append(
            MatchedPair(
                item=item,
                price_t=now.payable_fare,
                price_t_minus_7=before.payable_fare,
                log_relative=math.log(float(now.payable_fare))
                - math.log(float(before.payable_fare)),
                observation_id_t=now.observation_id,
                observation_id_t_minus_7=before.observation_id,
            )
        )

    return tuple(pairs)


def prior_period(collection_date: date) -> date:
    """The date a collection date is matched against — spec C.1.

    Always ``t - 7``. Never ``t - 1``: a Monday and a Tuesday observation are
    never differenced against each other (spec C.2), and this function is the
    single place that lag is expressed.
    """
    return collection_date - timedelta(days=MATCHING_LAG_DAYS)
