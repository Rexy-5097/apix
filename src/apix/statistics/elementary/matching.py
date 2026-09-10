"""Matching primitives — spec B.2, B.3, C, D.1, D.8 (methodology v2.1).

The correction AMB-1 forced, in one sentence: **the item is the unit of
matching and the cell is the unit of averaging and weighting, and they are
different keys**.

Two quantities computed here are also different things (spec B.3), and
conflating them is a named failure mode:

* **Identity stability** — does the product recur at all? Selects the tier.
  Measured per ``(route, carrier)`` for cells, because flight-number stability
  is a property of the entity that assigns flight numbers; and per ``route`` for
  parents, which pool carriers.
* **Match coverage** — does enough of it survive conditioning to compute a
  relative from? The statistic-driving metric.

Flight numbers can be perfectly stable while the usable matched set collapses
after conditioning on fare class, APW bucket, channel and entitlements.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal

from apix.schemas.enums import Tier
from apix.schemas.keys import CellKey, ItemKey, ParentKey
from apix.schemas.observation import Observation
from apix.schemas.results import (
    BandDiagnostics,
    MatchedPair,
    MatchedSet,
    SourceTransition,
)
from apix.statistics.elementary.bands import band_log_price, hour_band, log_dispersion
from apix.statistics.elementary.sources import SourcePrecedence

# Spec B.3 — LOCKED identity-stability thresholds that select the tier.
TIER_1_STABILITY_THRESHOLD = 0.70
TIER_2_STABILITY_THRESHOLD = 0.40

# Spec C.1 — the matched comparison is against t-7, never t-1.
MATCHING_LAG_DAYS = 7


def _require_bucket(obs: Observation) -> None:
    if obs.apw_bucket is None:
        raise ValueError(
            f"observation {obs.observation_id} has lead_time_days={obs.lead_time_days}, "
            "which matches no APW bucket; it is inadmissible (spec A.3) and must "
            "be filtered before cell assignment"
        )


def cell_key_for(obs: Observation) -> CellKey:
    """The elementary cell an observation belongs to — spec B.2.1.

    **Tier-independent.** The cell key does not depend on the tier and never has
    a flight number or hour band in it; those identify items. That invariance is
    what lets a ``(route, carrier)`` pair degrade from Tier 1 to Tier 2 without
    re-partitioning cells or re-deriving any weight mid-year (spec F.5).

    Raises:
        ValueError: if ``obs`` has no APW bucket. Callers must filter through
            :func:`~apix.statistics.elementary.admissibility.filter_admissible`
            first; reaching here with an unbucketed observation is a pipeline
            ordering bug, not a data condition to paper over.
    """
    _require_bucket(obs)
    assert obs.apw_bucket is not None  # narrowed by _require_bucket
    return CellKey(
        route=obs.route,
        carrier=obs.carrier,
        day_of_week=obs.day_of_week,
        apw_bucket=obs.apw_bucket,
        fare_class=obs.fare_class,
        channel=obs.channel,
    )


def parent_key_for(obs: Observation) -> ParentKey:
    """The parent stratum an observation belongs to — spec E.4, E.6.

    The cell key with **carrier dropped**. Defined here rather than in the index
    layer so the matching step can form a parent's matched set from raw
    observations without importing upwards.
    """
    return cell_key_for(obs).parent()


def item_key_for(obs: Observation, tier: Tier) -> ItemKey | None:
    """The recurring product class an observation instantiates — spec B.2.2.

    Returns None at Tier 3, which has **no within-cell item identity**: the cell
    publishes a declared unit value and never forms a matched set. None is the
    honest answer, not an error.
    """
    if tier is Tier.TIER_1:
        return ItemKey(tier=tier, carrier=obs.carrier, flight_number=obs.flight_number)
    if tier is Tier.TIER_2:
        return ItemKey(
            tier=tier,
            carrier=obs.carrier,
            departure_hour_band=hour_band(obs.departure_time_local),
        )
    return None


def identity_stability(
    observations: Iterable[Observation],
    route: str,
    window_dates: Sequence[date],
    *,
    carrier: str | None = None,
) -> float:
    """Share of scheduled flights whose identity recurs — spec B.3.

    Args:
        observations: The observation window.
        route: The route to measure.
        window_dates: Collection dates in the measurement window.
        carrier: When given, measures ``IdentityStability(route, carrier)`` — the
            **cell** unit under v2.1. When omitted, measures the pooled
            ``IdentityStability(route)``, which is the **parent** unit and is
            exactly the v2.0 quantity, retained unchanged.

    A flight number counts as *recurring* when it is observed at the same weekday
    slot on at least two collection dates seven days apart within the window. One
    sighting is not recurrence.

    Returns 0.0 when nothing matches — an honest "no evidence of stability",
    which places the stratum at Tier 3 where the unit-value caveat applies.
    """
    by_flight: dict[tuple[str, str, int], set[date]] = {}
    for obs in observations:
        if obs.route != route:
            continue
        if carrier is not None and obs.carrier != carrier:
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
    """Map identity stability onto the tier ladder — spec B.3, LOCKED.

    * ``>= 0.70`` -> Tier 1 (flight-identity match)
    * ``[0.40, 0.70)`` -> Tier 2 (**identity relaxation** to the departure slot)
    * ``< 0.40`` -> Tier 3 (declared unit value)

    Thresholds are unchanged from v2.0; only the *unit* they are evaluated over
    changed (spec B.3).
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


def _require_single_collection_date(observations: Sequence[Observation], side: str) -> None:
    """Each side of a matched set must come from exactly one collection date.

    Spec C.2: a Monday and a Tuesday observation are never differenced against
    each other. :func:`~apix.statistics.index.apix_l.calculate_apix_l` already
    rejects mixed dates, but this is the layer that would actually form the wrong
    pair, so the guard belongs here too. Taking ``min()`` and continuing — the
    previous behaviour — silently produced pairs spanning two periods.

    An empty side is not an error: zero distinct dates is not more than one, and
    a cell with no prior-period observations is an ordinary unmatched condition.
    """
    dates = sorted({obs.collection_date for obs in observations})
    if len(dates) > 1:
        raise ValueError(
            f"the {side} side carries more than one collection date {dates}; "
            "differencing across periods would compare a Monday against a "
            "Tuesday (spec C.2). Group observations by collection date before "
            "forming a matched set."
        )


def _stratum_key(obs: Observation, stratum: CellKey | ParentKey) -> CellKey | ParentKey:
    return parent_key_for(obs) if isinstance(stratum, ParentKey) else cell_key_for(obs)


def _index_by_item_and_source(
    observations: Iterable[Observation],
    stratum: CellKey | ParentKey,
    tier: Tier,
) -> dict[ItemKey, dict[str, list[Observation]]]:
    """Group a period's observations by item, then by source.

    Both levels are needed: the item is what gets matched across periods, and the
    source is what spec D.8 selects between *before* any price is read.
    """
    out: dict[ItemKey, dict[str, list[Observation]]] = {}
    for obs in observations:
        if _stratum_key(obs, stratum) != stratum:
            continue
        item = item_key_for(obs, tier)
        if item is None:
            continue
        out.setdefault(item, {}).setdefault(obs.source_id, []).append(obs)
    return out


def _price_and_ids(members: Sequence[Observation], tier: Tier) -> tuple[float, Decimal, str]:
    """The item's price in log space, its audit rendering, and its provenance.

    At Tier 1 an item is one flight, so this is that flight's canonical fare. At
    Tier 2 an item is a **departure band** that may hold several flights, so the
    price is *constructed* — the geometric mean of the band's admissible fares
    (spec B.2.3). The Decimal is an audit rendering of a computed quantity in
    that case, not an observed fare.
    """
    ordered = sorted(members, key=lambda o: o.observation_id)
    for obs in ordered:
        if obs.payable_fare <= 0:
            raise ValueError(
                f"non-positive fare reached matching for observation {obs.observation_id}; "
                "admissibility (spec A.6) must run first"
            )
    if tier is Tier.TIER_1:
        # Provenance names the observation that actually supplied the fare, and
        # only that one. Joining every id here while returning ordered[0]'s fare
        # made the audit trail claim contributors that had not contributed —
        # reachable whenever one flight is listed twice by one source in one
        # period, such as a mid-collection retiming.
        #
        # The non-selected observation is not recorded as an ExcludedObservation
        # because no ExclusionReason covers "not the canonical observation for
        # its item", and that enum is LOCKED: extending it is a methodology
        # change. Raised for the methodology owner rather than resolved here.
        chosen = ordered[0]
        return math.log(float(chosen.payable_fare)), chosen.payable_fare, chosen.observation_id

    # A Tier-2 band price genuinely is composed of every member, so naming all of
    # them is truthful here.
    log_price = band_log_price([o.payable_fare for o in ordered])
    ids = "|".join(o.observation_id for o in ordered)
    return log_price, Decimal(f"{math.exp(log_price):.4f}"), ids


def build_matched_set(
    observations_t: Iterable[Observation],
    observations_t_minus_7: Iterable[Observation],
    stratum: CellKey | ParentKey,
    tier: Tier,
    *,
    source_precedence: SourcePrecedence,
    previous_selection: Mapping[ItemKey, str] | None = None,
) -> MatchedSet:
    """Form ``M(c,t)`` — items present in BOTH *t* and *t-7* — spec D.1, D.8.

    Args:
        observations_t: Admissible, deduplicated observations at *t*.
        observations_t_minus_7: The same at *t-7* (spec C.1).
        stratum: The :class:`CellKey` being computed, or a :class:`ParentKey`
            when forming the parent's matched set (spec E.6.5). The parent's set
            is built from **observations**, never from cell results, so a
            suppressed child still contributes its items.
        tier: Selects the item definition. Tier 3 has no item identity and
            therefore forms no matched set.
        source_precedence: The ordered, versioned, price-blind rule of spec D.8.
        previous_selection: The source selected for each item at the *previous*
            link. Supplying it enables source-transition detection (spec D.8.3);
            omitting it means no transition can be detected, which is correct for
            the first link of a chain.

    Returns:
        A :class:`MatchedSet`. Pairs are sorted by item key so the mean in spec
        D.2 reduces in a stable order (spec P.2).

    **Unmatched items enter neither side of the ratio.** An item present at *t*
    but not at *t-7* contributes nothing: not to the numerator, and not as a new
    item at 100. That is what makes a newly appearing flight a new *item* rather
    than a price change (spec D.1, J.0).
    """
    observations_t = list(observations_t)
    observations_t_minus_7 = list(observations_t_minus_7)
    _require_single_collection_date(observations_t, "t")
    _require_single_collection_date(observations_t_minus_7, "t-7")

    collection_dates = {o.collection_date for o in observations_t}
    collection_date = next(iter(collection_dates)) if collection_dates else date.min

    if tier is Tier.TIER_3:
        return MatchedSet(cell=stratum, tier=tier, collection_date=collection_date)

    current = _index_by_item_and_source(observations_t, stratum, tier)
    prior = _index_by_item_and_source(observations_t_minus_7, stratum, tier)
    previous = dict(previous_selection or {})

    pairs: list[MatchedPair] = []
    selections: list[tuple[ItemKey, str]] = []
    transitions: list[SourceTransition] = []
    bands: list[BandDiagnostics] = []
    no_common_source: list[ItemKey] = []

    for item in sorted(current.keys() & prior.keys(), key=lambda k: k.sort_key):
        by_source_t, by_source_prior = current[item], prior[item]

        chosen = source_precedence.select(
            stratum.channel, by_source_t.keys(), by_source_prior.keys()
        )
        if chosen is None:
            # No source observed in both periods. Pairing across sources would
            # compare two different price concepts, so the item is unmatched.
            no_common_source.append(item)
            continue

        selections.append((item, chosen))

        members_t = by_source_t[chosen]
        members_prior = by_source_prior[chosen]

        log_t, price_t, ids_t = _price_and_ids(members_t, tier)
        log_prior, price_prior, ids_prior = _price_and_ids(members_prior, tier)

        if tier is Tier.TIER_2:
            bands.append(_band_diagnostics(item, members_t, members_prior))

        was = previous.get(item)
        if was is not None and was != chosen:
            transitions.append(_transition(item, was, chosen, price_t, by_source_t, log_t))
            continue

        pairs.append(
            MatchedPair(
                item=item,
                price_t=price_t,
                price_t_minus_7=price_prior,
                log_relative=log_t - log_prior,
                observation_id_t=ids_t,
                observation_id_t_minus_7=ids_prior,
                source_id=chosen,
            )
        )

    return MatchedSet(
        cell=stratum,
        tier=tier,
        collection_date=collection_date,
        pairs=tuple(pairs),
        selections=tuple(selections),
        transitions=tuple(transitions),
        bands=tuple(sorted(bands, key=lambda b: b.band)),
        unmatched_no_common_source=tuple(no_common_source),
    )


def _band_diagnostics(
    item: ItemKey,
    members_t: Sequence[Observation],
    members_prior: Sequence[Observation],
) -> BandDiagnostics:
    """Composition exposure of one Tier-2 band — spec B.2.3.

    Two different questions, and they must not be confused:

    * **Band identity recurrence** — did this ``(carrier, hour band)`` item
      appear in both periods? Answered by whether the item matched at all; an
      unmatched band reaches this function not at all.
    * **Constituent flight membership overlap** — how much of the band's flight
      *membership* carried over? That is what ``overlap`` measures, and what
      ``membership_delta`` counts.

    They diverge completely when a band's flights are renumbered while its count
    holds: ``membership_delta = 0`` and ``overlap = 0.0`` at the same time. Both
    are reported because neither is interpretable alone — a large membership
    change is harmless when within-band dispersion is zero.

    ``overlap == 1`` is the condition under which the band ratio is a pure
    matched-model relative (exact in real arithmetic, equal within spec Q.1's
    tolerance numerically). Below it the ratio carries a composition component.
    """
    flights_t = {o.flight_number for o in members_t}
    flights_prior = {o.flight_number for o in members_prior}
    denominator = max(len(flights_t), len(flights_prior))

    assert item.departure_hour_band is not None  # Tier 2 by construction
    return BandDiagnostics(
        band=item.departure_hour_band,
        n_t=len(members_t),
        n_t_minus_7=len(members_prior),
        membership_delta=len(members_t) - len(members_prior),
        overlap=(len(flights_t & flights_prior) / denominator) if denominator else 0.0,
        dispersion_t=log_dispersion([o.payable_fare for o in members_t]),
        dispersion_t_minus_7=log_dispersion([o.payable_fare for o in members_prior]),
    )


def _transition(
    item: ItemKey,
    previous_source: str,
    current_source: str,
    price_t: Decimal,
    by_source_t: Mapping[str, list[Observation]],
    log_t: float,
) -> SourceTransition:
    """Record a source transition without acting on it — spec D.8.3.

    The implied gap is computed **only** when the previous source is also
    observed at *t*, so it is a like-for-like comparison within one period. It is
    a diagnostic and is never applied as a bridge adjustment: doing so would
    assume the two sources' price concepts are equivalent, which is precisely
    what the cross-source spread exists to test rather than assume.
    """
    old_members = by_source_t.get(previous_source)
    price_old: Decimal | None = None
    gap: float | None = None
    if old_members:
        ordered = sorted(old_members, key=lambda o: o.observation_id)
        price_old = ordered[0].payable_fare
        if price_old > 0:
            gap = log_t - math.log(float(price_old))

    return SourceTransition(
        item=item,
        previous_source=previous_source,
        current_source=current_source,
        price_t=price_t,
        price_t_previous_source=price_old,
        implied_log_gap=gap,
    )


def prior_period(collection_date: date) -> date:
    """The date a collection date is matched against — spec C.1.

    Always ``t - 7``. Never ``t - 1``: a Monday and a Tuesday observation are
    never differenced against each other (spec C.2), and this function is the
    single place that lag is expressed.
    """
    return collection_date - timedelta(days=MATCHING_LAG_DAYS)
