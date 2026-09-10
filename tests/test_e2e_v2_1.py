"""End-to-end statistical fixtures for methodology v2.1 — observations in, index out.

These exist because of AMB-1. Sixteen hand-calculated golden values, an
invariant suite and a twelve-dimension adversarial review all passed over a
defect that made every Tier-1 cell unpublishable, because **not one of them
started from an observation**. The benchmark found it, being the first thing to
run the pipeline end to end.

The doctrine this file encodes:

    Unit tests verify functions.
    End-to-end statistical fixtures verify that the correct statistical
    objects reach those functions.

Every test here starts from ``Observation`` values and asserts a property of the
statistical object that results. None of them accepts a matched set as an input.

Authority: ``docs/methodology/apix_formula_spec_v2_1_draft.md`` and
``docs/methodology/AMB-1-resolution.md``. Where a test cites a section, that
section is the contract it enforces.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from apix.schemas.enums import (
    Availability,
    CellStatus,
    ChangePolicy,
    Channel,
    FareClass,
    SourceType,
    Tier,
    UndefinedRelativeReason,
)
from apix.schemas.keys import CellKey, ItemKey, ParentKey
from apix.schemas.observation import Entitlements, Observation
from apix.statistics.elementary.bands import band_price, hour_band
from apix.statistics.elementary.jevons import MIN_MATCHED_ITEMS_PER_CELL, compute_jevons
from apix.statistics.elementary.matching import (
    build_matched_set,
    cell_key_for,
    identity_stability,
    item_key_for,
    prior_period,
    select_tier,
)
from apix.statistics.elementary.sources import SourcePrecedence
from apix.statistics.index.chaining import ChainInputs, advance_cell
from apix.statistics.index.parent import (
    compute_parent_relative,
    parent_key_for,
    parent_level,
)

# ---------------------------------------------------------------------------
# Fixture construction
# ---------------------------------------------------------------------------

#: A Monday, derived rather than asserted so the fixture cannot drift if edited.
MONDAY_TRAVEL = date(2026, 10, 5) - timedelta(days=date(2026, 10, 5).isoweekday() - 1)
#: The Tuesday in the same week.
TUESDAY_TRAVEL = MONDAY_TRAVEL + timedelta(days=1)

APW_DAYS = 7

STANDARD = Entitlements(
    checked_baggage_kg=15,
    change_permitted=ChangePolicy.FEE,
    cancellation_permitted=ChangePolicy.FEE,
)

PRECEDENCE = SourcePrecedence(
    version="src-v1",
    order={
        Channel.AIRLINE_DIRECT: ("indigo-direct", "ai-direct"),
        Channel.AGGREGATOR: ("mmt", "ixigo"),
    },
)


def observe(
    *,
    travel_date: date,
    carrier: str = "6E",
    flight_number: str = "101",
    fare: str = "5000",
    departure: time = time(6, 0),
    route: tuple[str, str] = ("DEL", "BOM"),
    channel: Channel = Channel.AIRLINE_DIRECT,
    source_id: str = "indigo-direct",
    entitlements: Entitlements = STANDARD,
    availability: Availability = Availability.AVAILABLE,
    suffix: str = "",
) -> Observation:
    """One admissible observation at exactly ``APW_DAYS`` lead time."""
    collection = travel_date - timedelta(days=APW_DAYS)
    origin, destination = route
    return Observation(
        observation_id=(
            f"{collection.isoformat()}-{carrier}{flight_number}-{origin}{destination}"
            f"-{channel.value}-{source_id}{suffix}"
        ),
        origin=origin,
        destination=destination,
        travel_date=travel_date,
        departure_time_local=departure,
        observation_ts=datetime.combine(collection, time(6, 0)),
        collection_date=collection,
        carrier=carrier,
        flight_number=flight_number,
        stops=0,
        duration_minutes=120,
        fare_family_raw="SAVER",
        channel=channel,
        source_id=source_id,
        entitlements=entitlements,
        payable_fare=Decimal(fare),
        source_type=SourceType.SYNTHETIC,
        availability=availability,
    )


def week(travel_date: date) -> date:
    """The travel date one week earlier — the same weekday by construction."""
    return travel_date - timedelta(days=7)


def collection_of(travel_date: date) -> date:
    return travel_date - timedelta(days=APW_DAYS)


def matched(
    obs_t: list[Observation],
    obs_prior: list[Observation],
    *,
    tier: Tier = Tier.TIER_1,
    cell: CellKey | None = None,
    previous_selection: dict[ItemKey, str] | None = None,
):
    """Run the real matching path. No test may hand-build a matched set."""
    target = cell if cell is not None else cell_key_for(obs_t[0])
    return build_matched_set(
        obs_t,
        obs_prior,
        target,
        tier,
        source_precedence=PRECEDENCE,
        previous_selection=previous_selection,
    )


# ---------------------------------------------------------------------------
# E2E-01 — the AMB-1 regression. Three recurring flights, ONE cell.
# ---------------------------------------------------------------------------


def test_e2e_01_three_tier1_items_in_one_cell() -> None:
    """Three flights on one route/carrier/weekday/APW/class/channel are

    **3 ITEMS in 1 CELL producing 1 Jevons relative** — spec B.2.0.

    Under v2.0 they were three cells of one item each, ``|M| = 1`` in all three,
    and no Tier-1 relative could ever be computed. This is the test whose
    absence let AMB-1 through.
    """
    prior_travel, now_travel = week(MONDAY_TRAVEL), MONDAY_TRAVEL

    prior = [
        observe(travel_date=prior_travel, flight_number="101", fare="5000", departure=time(6, 0)),
        observe(travel_date=prior_travel, flight_number="205", fare="5500", departure=time(9, 15)),
        observe(travel_date=prior_travel, flight_number="317", fare="6000", departure=time(14, 40)),
    ]
    now = [
        observe(travel_date=now_travel, flight_number="101", fare="5100", departure=time(6, 0)),
        observe(travel_date=now_travel, flight_number="205", fare="5500", departure=time(9, 15)),
        observe(travel_date=now_travel, flight_number="317", fare="6120", departure=time(14, 40)),
    ]

    cells = {cell_key_for(o) for o in now}
    assert len(cells) == 1, f"three flights must share one cell, got {len(cells)}"

    cell = cells.pop()
    assert cell == CellKey(
        route="DEL-BOM",
        carrier="6E",
        day_of_week=now_travel.isoweekday(),
        apw_bucket=now[0].apw_bucket,
        fare_class=FareClass.STANDARD,
        channel=Channel.AIRLINE_DIRECT,
    )

    items = {item_key_for(o, Tier.TIER_1) for o in now}
    assert len(items) == 3, "three distinct flight numbers are three items"

    result = matched(now, prior, cell=cell)
    assert len(result.pairs) == 3

    jevons = compute_jevons(cell, collection_of(now_travel), result.pairs)
    assert jevons.is_defined, jevons.undefined_reason
    assert jevons.relative is not None
    # 1.02, 1.00, 1.02 -> exp(mean(ln)) = exp(0.0396052.../3)
    assert jevons.relative == pytest.approx(1.0132894, abs=1e-7)


# ---------------------------------------------------------------------------
# E2E-02 — partial disappearance, three survive.
# ---------------------------------------------------------------------------


def test_e2e_02_partial_disappearance_still_publishes() -> None:
    """Five items, two disappear, three remain matched — the cell still publishes.

    Unmatched items enter neither side of the ratio (spec D.1), so the two that
    vanish contribute nothing rather than being imputed.
    """
    flights = ["101", "205", "317", "421", "509"]
    prior = [
        observe(
            travel_date=week(MONDAY_TRAVEL),
            flight_number=f,
            fare=str(5000 + 100 * i),
            departure=time(6 + i, 0),
        )
        for i, f in enumerate(flights)
    ]
    now = [
        observe(
            travel_date=MONDAY_TRAVEL,
            flight_number=f,
            fare=str(5100 + 100 * i),
            departure=time(6 + i, 0),
        )
        for i, f in enumerate(flights[:3])
    ]

    result = matched(now, prior)
    assert len(result.pairs) == 3, "only the surviving three may match"

    jevons = compute_jevons(cell_key_for(now[0]), collection_of(MONDAY_TRAVEL), result.pairs)
    assert jevons.is_defined
    assert jevons.matched_count == 3


# ---------------------------------------------------------------------------
# E2E-03 — below the minimum. Undefined, never a fabricated 1.0.
# ---------------------------------------------------------------------------


def test_e2e_03_below_minimum_is_undefined_not_one() -> None:
    """Two matched items leave J undefined — spec D.3.

    The failure mode this guards is a substituted relative of 1.0, which asserts
    "the price did not move" when the truth is "we cannot say".
    """
    prior = [
        observe(travel_date=week(MONDAY_TRAVEL), flight_number="101", fare="5000"),
        observe(
            travel_date=week(MONDAY_TRAVEL),
            flight_number="205",
            fare="5500",
            departure=time(9, 0),
        ),
    ]
    now = [
        observe(travel_date=MONDAY_TRAVEL, flight_number="101", fare="5100"),
        observe(travel_date=MONDAY_TRAVEL, flight_number="205", fare="5600", departure=time(9, 0)),
    ]

    result = matched(now, prior)
    assert len(result.pairs) == 2 < MIN_MATCHED_ITEMS_PER_CELL

    jevons = compute_jevons(cell_key_for(now[0]), collection_of(MONDAY_TRAVEL), result.pairs)
    assert not jevons.is_defined
    assert jevons.relative is None
    assert jevons.undefined_reason is UndefinedRelativeReason.BELOW_MIN_MATCHED_ITEMS


# ---------------------------------------------------------------------------
# E2E-04 — two carriers on one route are two cells.
# ---------------------------------------------------------------------------


def test_e2e_04_carriers_are_not_pooled_in_cells() -> None:
    """IndiGo and Air India on DEL-BOM occupy **different cells** — spec B.2.1.

    Carrier is a cell-key field, so a carrier-mix shift moves fixed weights
    between cells rather than the composition inside one.
    """
    indigo = observe(travel_date=MONDAY_TRAVEL, carrier="6E", flight_number="101")
    air_india = observe(
        travel_date=MONDAY_TRAVEL, carrier="AI", flight_number="101", source_id="ai-direct"
    )

    assert cell_key_for(indigo) != cell_key_for(air_india)
    assert cell_key_for(indigo).carrier == "6E"
    assert cell_key_for(air_india).carrier == "AI"

    # Same flight number, different carrier: distinct items too.
    assert item_key_for(indigo, Tier.TIER_1) != item_key_for(air_india, Tier.TIER_1)

    # ...but one parent, which is what makes the carry rule able to help.
    assert parent_key_for(indigo) == parent_key_for(air_india)


# ---------------------------------------------------------------------------
# E2E-05 — Monday never matches Tuesday.
# ---------------------------------------------------------------------------


def test_e2e_05_no_cross_weekday_matching() -> None:
    """A Monday cell and a Tuesday cell are different chains — spec C.2.

    ``day_of_week`` is mechanically determined by ``(t, apw)``, so it partitions
    nothing within a collection date. It is the **chain identifier**: without it
    one key would name seven interleaved level sequences.
    """
    monday = observe(travel_date=MONDAY_TRAVEL)
    tuesday = observe(travel_date=TUESDAY_TRAVEL)

    assert cell_key_for(monday) != cell_key_for(tuesday)
    assert cell_key_for(monday).day_of_week == MONDAY_TRAVEL.isoweekday()
    assert cell_key_for(tuesday).day_of_week == TUESDAY_TRAVEL.isoweekday()

    # The lag is seven days, so a chain never crosses a weekday.
    assert prior_period(collection_of(MONDAY_TRAVEL)) == collection_of(week(MONDAY_TRAVEL))

    # Feeding Tuesday observations into a Monday cell yields no pairs at all.
    monday_prior = [
        observe(travel_date=week(MONDAY_TRAVEL), flight_number=f, departure=time(6 + i, 0))
        for i, f in enumerate(["101", "205", "317"])
    ]
    tuesday_now = [
        observe(travel_date=TUESDAY_TRAVEL, flight_number=f, departure=time(6 + i, 0))
        for i, f in enumerate(["101", "205", "317"])
    ]
    result = matched(tuesday_now, monday_prior, cell=cell_key_for(monday))
    assert result.pairs == ()


# ---------------------------------------------------------------------------
# E2E-06 — Tier-2 identity relaxation and the constructed band price.
# ---------------------------------------------------------------------------


def test_e2e_06_tier2_band_item_and_constructed_price() -> None:
    """The Tier-2 item is ``carrier x departure_hour_band`` — spec B.2.2/B.2.3.

    Two flights inside one 3-hour band collapse to **one item** whose price is
    the geometric mean of the band's admissible fares. With stable membership
    the construction telescopes into a flight-level Jevons.
    """
    prior_travel, now_travel = week(MONDAY_TRAVEL), MONDAY_TRAVEL

    # Bands 2 [06:00,09:00), 3 [09:00,12:00), 4 [12:00,15:00).
    layout = [
        ("101", time(6, 0), "5000", "5100"),
        ("103", time(7, 30), "6000", "6120"),
        ("205", time(9, 15), "5500", "5500"),
        ("317", time(14, 40), "6000", "6120"),
    ]
    prior = [
        observe(travel_date=prior_travel, flight_number=f, departure=d, fare=p0)
        for f, d, p0, _ in layout
    ]
    now = [
        observe(travel_date=now_travel, flight_number=f, departure=d, fare=p1)
        for f, d, _, p1 in layout
    ]

    items = {item_key_for(o, Tier.TIER_2) for o in now}
    assert len(items) == 3, "four flights occupy three bands -> three items"
    assert all(i.departure_hour_band is not None and i.flight_number is None for i in items)
    assert hour_band(time(6, 0)) == hour_band(time(7, 30)) == 2

    result = matched(now, prior, tier=Tier.TIER_2)
    assert len(result.pairs) == 3

    # Band 2 holds 5000 and 6000 at t-7; 5100 and 6120 at t.
    assert band_price([Decimal("5000"), Decimal("6000")]) == pytest.approx(
        math.sqrt(5000 * 6000), rel=1e-12
    )

    diagnostics = {d.band: d for d in result.bands}
    assert diagnostics[2].n_t == 2 and diagnostics[2].n_t_minus_7 == 2
    assert diagnostics[2].overlap == 1.0, "stable membership"
    assert diagnostics[2].membership_delta == 0
    assert diagnostics[2].dispersion_t > 0.0, "5100 and 6120 are dispersed"

    jevons = compute_jevons(cell_key_for(now[0]), collection_of(now_travel), result.pairs)
    assert jevons.is_defined


def test_e2e_06b_tier2_can_have_fewer_items_than_tier1() -> None:
    """Tier 2 is an identity **relaxation**, not a threshold relaxation.

    Four matched flights clustered into two hour bands pass at Tier 1 and
    **fail** at Tier 2, because ``min_matched_items_per_cell`` counts matched
    *bands*. Tier 2 is not uniformly the more permissive tier — the structural
    consequence recorded in the amendment.
    """
    layout = [
        ("101", time(6, 0)),
        ("103", time(7, 0)),
        ("205", time(9, 15)),
        ("207", time(10, 0)),
    ]
    prior = [
        observe(travel_date=week(MONDAY_TRAVEL), flight_number=f, departure=d, fare="5000")
        for f, d in layout
    ]
    now = [
        observe(travel_date=MONDAY_TRAVEL, flight_number=f, departure=d, fare="5100")
        for f, d in layout
    ]

    t1 = matched(now, prior, tier=Tier.TIER_1)
    t2 = matched(now, prior, tier=Tier.TIER_2)

    assert len(t1.pairs) == 4 >= MIN_MATCHED_ITEMS_PER_CELL
    assert len(t2.pairs) == 2 < MIN_MATCHED_ITEMS_PER_CELL

    cell, when = cell_key_for(now[0]), collection_of(MONDAY_TRAVEL)
    assert compute_jevons(cell, when, t1.pairs).is_defined
    assert not compute_jevons(cell, when, t2.pairs).is_defined


def test_e2e_06c_band_membership_change_is_exposed_not_hidden() -> None:
    """A membership change makes the band ratio a unit-value ratio — spec B.2.3.

    No fare moves; a cheaper flight joins the band. The relative moves anyway,
    and the diagnostics say so.
    """
    prior = [
        observe(travel_date=week(MONDAY_TRAVEL), flight_number="101", departure=time(6, 0), fare="5000"),
        observe(travel_date=week(MONDAY_TRAVEL), flight_number="103", departure=time(7, 0), fare="6000"),
    ]
    now = [
        observe(travel_date=MONDAY_TRAVEL, flight_number="101", departure=time(6, 0), fare="5000"),
        observe(travel_date=MONDAY_TRAVEL, flight_number="103", departure=time(7, 0), fare="6000"),
        observe(travel_date=MONDAY_TRAVEL, flight_number="105", departure=time(8, 0), fare="4000"),
    ]

    result = matched(now, prior, tier=Tier.TIER_2)
    assert len(result.pairs) == 1

    band = result.bands[0]
    assert band.membership_delta == 1
    assert band.overlap == pytest.approx(2 / 3)
    assert band.overlap < 1.0, "telescoping identity does not hold"

    ratio = math.exp(result.pairs[0].log_relative)
    assert ratio < 0.95, "composition alone moved the band price"


# ---------------------------------------------------------------------------
# E2E-07 — Tier 3 declared unit value.
# ---------------------------------------------------------------------------


def test_e2e_07_tier3_has_no_item_identity() -> None:
    """Tier 3 has no recurring item identity — spec B.2.2.

    It therefore forms no matched set and publishes a declared unit value. No
    new estimator is invented here.
    """
    now = [
        observe(travel_date=MONDAY_TRAVEL, flight_number=f, departure=time(6 + i, 0))
        for i, f in enumerate(["101", "205", "317"])
    ]
    prior = [
        observe(travel_date=week(MONDAY_TRAVEL), flight_number=f, departure=time(6 + i, 0))
        for i, f in enumerate(["101", "205", "317"])
    ]

    assert item_key_for(now[0], Tier.TIER_3) is None

    result = matched(now, prior, tier=Tier.TIER_3)
    assert result.pairs == ()

    jevons = compute_jevons(cell_key_for(now[0]), collection_of(MONDAY_TRAVEL), result.pairs)
    assert not jevons.is_defined
    assert jevons.undefined_reason is UndefinedRelativeReason.NO_MATCHED_ITEMS


# ---------------------------------------------------------------------------
# E2E-09 — a new flight is a new ITEM, not a new CELL.
# ---------------------------------------------------------------------------


def test_e2e_09_new_flight_is_a_new_item_not_a_new_cell() -> None:
    """``6E999`` appearing in an existing cell must not trigger §J entry.

    It is unmatched at first sighting, contributes to neither side, and the cell
    it lands in is the one that already existed.
    """
    flights = ["101", "205", "317"]
    prior = [
        observe(travel_date=week(MONDAY_TRAVEL), flight_number=f, departure=time(6 + i, 0), fare="5000")
        for i, f in enumerate(flights)
    ]
    now = [
        observe(travel_date=MONDAY_TRAVEL, flight_number=f, departure=time(6 + i, 0), fare="5100")
        for i, f in enumerate([*flights, "999"])
    ]

    existing = cell_key_for(prior[0])
    assert cell_key_for(now[-1]) == existing, "the new flight lands in the existing cell"

    result = matched(now, prior)
    assert len(result.pairs) == 3, "the unmatched newcomer enters neither side"

    jevons = compute_jevons(existing, collection_of(MONDAY_TRAVEL), result.pairs)
    previous = advance_cell(
        ChainInputs(
            cell=existing,
            collection_date=collection_of(week(MONDAY_TRAVEL)),
            jevons=compute_jevons(
                existing,
                collection_of(week(MONDAY_TRAVEL)),
                matched(prior, prior, cell=existing).pairs,
            ),
        )
    )
    state = advance_cell(
        ChainInputs(
            cell=existing,
            collection_date=collection_of(MONDAY_TRAVEL),
            jevons=jevons,
            previous=previous,
            parent_level=250.0,  # would be a loud, obvious wrong answer if §J fired
        )
    )
    assert state.status is CellStatus.PUBLISHED, "a new item must not trigger new-cell entry"
    assert state.level is not None and state.level != 250.0


# ---------------------------------------------------------------------------
# E2E-10 — a new CELL enters at its parent's LEVEL.
# ---------------------------------------------------------------------------


def test_e2e_10_new_cell_enters_at_parent_level_never_100() -> None:
    """A genuinely new cell inherits ``I(P,t)`` — spec J.1.

    Entering at 100 inside a live aggregate would record a newly appearing fare
    as a price movement.
    """
    cell = cell_key_for(observe(travel_date=MONDAY_TRAVEL, carrier="AI", source_id="ai-direct"))
    jevons = compute_jevons(cell, collection_of(MONDAY_TRAVEL), ())

    state = advance_cell(
        ChainInputs(
            cell=cell,
            collection_date=collection_of(MONDAY_TRAVEL),
            jevons=jevons,
            previous=None,
            parent_level=104.25,
        )
    )
    assert state.status is CellStatus.ENTERED
    assert state.level == pytest.approx(104.25)
    assert state.level != 100.0

    held = advance_cell(
        ChainInputs(
            cell=cell,
            collection_date=collection_of(MONDAY_TRAVEL),
            jevons=jevons,
            previous=None,
            parent_level=None,
        )
    )
    assert held.status is CellStatus.HELD_OUT
    assert held.level is None


# ---------------------------------------------------------------------------
# E2E-11 — the parent level must not be recursively self-referential.
# ---------------------------------------------------------------------------


def _state(cell: CellKey, level: float | None, status: CellStatus) -> object:
    from apix.schemas.results import CellState

    return CellState(
        cell=cell,
        collection_date=collection_of(MONDAY_TRAVEL),
        level=level,
        status=status,
        parent=cell.parent(),
    )


def test_e2e_11_parent_level_excludes_only_entrants_not_carried_children() -> None:
    """``I(P,t)`` is the weighted mean over the **independent-live set** — spec E.7.

    A child entering at *t* under §J.1 has ``I(C,t) = I(P,t)`` by construction
    and must be excluded. A **carried** child depends on ``J(P,t)`` — computed
    bottom-up from raw observations — and creates no recursion, so it stays in.
    Excluding carries would empty the set on exactly the thin strata where carry
    is normal.
    """
    a = cell_key_for(observe(travel_date=MONDAY_TRAVEL, carrier="6E"))
    b = cell_key_for(observe(travel_date=MONDAY_TRAVEL, carrier="AI", source_id="ai-direct"))
    c = cell_key_for(observe(travel_date=MONDAY_TRAVEL, carrier="SG"))
    entrant = cell_key_for(observe(travel_date=MONDAY_TRAVEL, carrier="QP"))

    weights = {a: 0.25, b: 0.25, c: 0.25, entrant: 0.25}
    states = [
        _state(a, 105.0, CellStatus.PUBLISHED),
        _state(b, 107.0, CellStatus.PUBLISHED),
        _state(c, 103.0, CellStatus.CARRIED),
        _state(entrant, None, CellStatus.ENTERED),
    ]

    level = parent_level(states, weights, entered_at_t={entrant})
    assert level is not None
    # (105 + 107 + 103) / 3 — the carried child is IN, the entrant is OUT.
    assert level == pytest.approx(105.0)


def test_e2e_11b_empty_independent_live_set_leaves_parent_level_undefined() -> None:
    """No fixed point. An empty independent-live set means ``I(P,t)`` is undefined.

    The consequence is a **hold-out** under §J.2, which is a different quality
    event from suppression: a suppressed cell was live and breached a threshold,
    a held-out cell was never live.
    """
    entrant = cell_key_for(observe(travel_date=MONDAY_TRAVEL, carrier="QP"))
    states = [_state(entrant, None, CellStatus.ENTERED)]

    assert parent_level(states, {entrant: 1.0}, entered_at_t={entrant}) is None


# ---------------------------------------------------------------------------
# E2E-11c — the parent relative comes from OBSERVATIONS, bottom-up.
# ---------------------------------------------------------------------------


def test_e2e_11c_parent_relative_pools_carriers_from_raw_observations() -> None:
    """``J(P,t)`` is a Jevons over the parent's own matched items — spec E.6.

    The parent pools carriers by dropping ``carrier`` from the cell key. It is
    computed from observations, **not** from cell results, so a suppressed
    child still contributes its items.
    """
    prior_travel, now_travel = week(MONDAY_TRAVEL), MONDAY_TRAVEL
    spec = [("6E", "101", "5000", "5100"), ("AI", "201", "6000", "6120"), ("SG", "301", "7000", "7000")]

    prior = [
        observe(travel_date=prior_travel, carrier=c, flight_number=f, fare=p0, departure=time(6 + i, 0))
        for i, (c, f, p0, _) in enumerate(spec)
    ]
    now = [
        observe(travel_date=now_travel, carrier=c, flight_number=f, fare=p1, departure=time(6 + i, 0))
        for i, (c, f, _, p1) in enumerate(spec)
    ]

    parent = parent_key_for(now[0])
    assert parent == ParentKey(
        route="DEL-BOM",
        day_of_week=now_travel.isoweekday(),
        apw_bucket=now[0].apw_bucket,
        fare_class=FareClass.STANDARD,
        channel=Channel.AIRLINE_DIRECT,
    )

    result = compute_parent_relative(
        now, prior, parent, Tier.TIER_1, collection_of(now_travel), source_precedence=PRECEDENCE
    )
    assert result.jevons.is_defined
    assert result.carrier_count == 3
    assert result.carrier_concentration == pytest.approx(1 / 3)


# ---------------------------------------------------------------------------
# E2E-12 — source transition.
# ---------------------------------------------------------------------------


def test_e2e_12_source_transition_excludes_exactly_one_link() -> None:
    """A change of selected source between links suppresses that pair — spec D.8.3.

    Both source ids, both prices and the implied gap are retained. No bridge, no
    blending, no last-write-wins.
    """
    prior_travel, now_travel = week(MONDAY_TRAVEL), MONDAY_TRAVEL
    agg = {"channel": Channel.AGGREGATOR}

    # Previous link selected "mmt" for this item.
    prior = [
        observe(travel_date=prior_travel, fare="6050", source_id="mmt", **agg),
        observe(travel_date=prior_travel, fare="6030", source_id="ixigo", **agg),
    ]
    # mmt has disappeared at t; only ixigo remains.
    now = [observe(travel_date=now_travel, fare="6100", source_id="ixigo", **agg)]

    item = item_key_for(now[0], Tier.TIER_1)
    result = matched(now, prior, previous_selection={item: "mmt"})

    assert result.pairs == (), "the transitioning pair is excluded from M"
    assert len(result.transitions) == 1

    transition = result.transitions[0]
    assert transition.item == item
    assert transition.previous_source == "mmt"
    assert transition.current_source == "ixigo"
    assert transition.price_t == Decimal("6100")

    # It resumes at the next link, once ixigo has two consecutive selections.
    resumed = matched(now, prior, previous_selection={item: "ixigo"})
    assert len(resumed.pairs) == 1
    assert resumed.transitions == ()


def test_e2e_12b_source_selection_is_price_blind_and_paired() -> None:
    """Selection never inspects the fare, and both legs share one source.

    A cross-source ratio is impossible by construction: the rule takes the
    highest-ranked source present in **both** periods.
    """
    agg = {"channel": Channel.AGGREGATOR}
    prior = [
        observe(travel_date=week(MONDAY_TRAVEL), fare="9999", source_id="mmt", **agg),
        observe(travel_date=week(MONDAY_TRAVEL), fare="1000", source_id="ixigo", **agg),
    ]
    now = [
        observe(travel_date=MONDAY_TRAVEL, fare="9999", source_id="mmt", **agg),
        observe(travel_date=MONDAY_TRAVEL, fare="1000", source_id="ixigo", **agg),
    ]

    result = matched(now, prior)
    assert len(result.pairs) == 1
    pair = result.pairs[0]
    # "mmt" outranks "ixigo" in PRECEDENCE regardless of being the dearer quote.
    assert pair.source_id == "mmt"
    assert pair.price_t == Decimal("9999")
    assert pair.price_t_minus_7 == Decimal("9999")


# ---------------------------------------------------------------------------
# E2E-13 — tier is selected per (route, carrier).
# ---------------------------------------------------------------------------


def test_e2e_13_tier_is_selected_per_route_and_carrier() -> None:
    """A stable carrier is not dragged down by an unstable one — spec B.3.

    Flight-number stability is a property of the entity that assigns flight
    numbers. A route-level tier would apply one carrier's churn to every other
    carrier on the route.
    """
    dates = [week(MONDAY_TRAVEL), MONDAY_TRAVEL]
    window = [collection_of(d) for d in dates]

    stable = [
        observe(travel_date=d, carrier="6E", flight_number=f, departure=time(6 + i, 0))
        for d in dates
        for i, f in enumerate(["101", "205", "317", "421", "509"])
    ]
    # Air India renumbers most of its flights between the two weeks.
    churn = [
        observe(travel_date=dates[0], carrier="AI", flight_number=f, departure=time(6 + i, 0), source_id="ai-direct")
        for i, f in enumerate(["201", "202", "203", "204"])
    ] + [
        observe(travel_date=dates[1], carrier="AI", flight_number=f, departure=time(6 + i, 0), source_id="ai-direct")
        for i, f in enumerate(["201", "292", "293", "294"])
    ]
    frame = stable + churn

    indigo = identity_stability(frame, "DEL-BOM", window_dates=window, carrier="6E")
    air_india = identity_stability(frame, "DEL-BOM", window_dates=window, carrier="AI")

    assert indigo == pytest.approx(1.0)
    assert air_india < indigo

    assert select_tier(indigo) is Tier.TIER_1
    assert select_tier(air_india) is not Tier.TIER_1, "the two carriers must tier separately"

    # The pooled route statistic still exists — it is what the PARENT uses.
    pooled = identity_stability(frame, "DEL-BOM", window_dates=window)
    assert 0.0 < pooled < 1.0
