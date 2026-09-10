"""Invariants for the methodology v2.1 surface — spec P, Q.

These hold for **any** correct implementation, which is what makes them worth
asserting. An index engine can reach full line coverage while computing the
wrong number; it cannot satisfy time-reversal, scale invariance and bit-identical
reordering while doing so.

Scope is deliberately the surface v2.1 *added* — item/cell separation, bands,
source precedence, the parent object. The pre-existing invariants for Jevons,
chaining and aggregation live in ``test_statistical_edge_cases.py`` and are
unchanged.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from apix.schemas.enums import (
    Availability,
    CellStatus,
    ChangePolicy,
    Channel,
    SourceType,
    Tier,
)
from apix.schemas.keys import CellKey
from apix.schemas.observation import Entitlements, Observation
from apix.schemas.results import CellState
from apix.statistics.elementary.bands import band_price, log_dispersion
from apix.statistics.elementary.jevons import compute_jevons
from apix.statistics.elementary.matching import (
    build_matched_set,
    cell_key_for,
    item_key_for,
    parent_key_for,
)
from apix.statistics.elementary.sources import SourcePrecedence
from apix.statistics.index.parent import compute_parent_relative, parent_level

MONDAY = date(2026, 10, 5) - timedelta(days=date(2026, 10, 5).isoweekday() - 1)
APW = 7
STANDARD = Entitlements(15, ChangePolicy.FEE, ChangePolicy.FEE)
PRECEDENCE = SourcePrecedence(
    version="inv-v1",
    order={Channel.AIRLINE_DIRECT: ("a", "b"), Channel.AGGREGATOR: ("mmt", "ixigo")},
)


def ob(
    travel: date,
    flight: str,
    fare: Decimal,
    *,
    carrier: str = "6E",
    dep: time = time(6, 0),
    source: str = "a",
    channel: Channel = Channel.AIRLINE_DIRECT,
) -> Observation:
    collection = travel - timedelta(days=APW)
    return Observation(
        observation_id=f"{collection}-{carrier}{flight}-{source}-{dep}",
        origin="DEL",
        destination="BOM",
        travel_date=travel,
        departure_time_local=dep,
        observation_ts=datetime.combine(collection, time(6, 0)),
        collection_date=collection,
        carrier=carrier,
        flight_number=flight,
        stops=0,
        duration_minutes=120,
        fare_family_raw="SAVER",
        channel=channel,
        source_id=source,
        entitlements=STANDARD,
        payable_fare=fare,
        source_type=SourceType.SYNTHETIC,
        availability=Availability.AVAILABLE,
    )


def relative(now: list[Observation], prior: list[Observation], tier: Tier = Tier.TIER_1) -> float:
    cell = cell_key_for(now[0])
    pairs = build_matched_set(now, prior, cell, tier, source_precedence=PRECEDENCE).pairs
    result = compute_jevons(cell, now[0].collection_date, pairs)
    assert result.relative is not None
    return result.relative


FARES = st.decimals(min_value=Decimal("500"), max_value=Decimal("200000"), places=2)


# ---------------------------------------------------------------------------
# Determinism (spec P.1, P.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rotation", range(8))
def test_observation_order_does_not_change_a_single_bit(rotation: int) -> None:
    """INV-5. Eight deterministic permutations, one bit-identical answer.

    Floating-point addition is not associative, so an unordered reduction would
    diverge in the last places even on identical inputs. Every reduction in the
    matching and Jevons path runs in explicitly sorted key order.
    """
    flights = ["101", "205", "317", "421", "509"]
    prior = [
        ob(MONDAY - timedelta(days=7), f, Decimal(5000 + 137 * i)) for i, f in enumerate(flights)
    ]
    now = [ob(MONDAY, f, Decimal(5100 + 149 * i)) for i, f in enumerate(flights)]

    baseline = relative(now, prior)
    rotated_now = now[rotation:] + now[:rotation]
    rotated_prior = list(reversed(prior)) if rotation % 2 else prior[rotation:] + prior[:rotation]

    assert relative(rotated_now, rotated_prior) == baseline  # `==`, not isclose


def test_band_price_is_order_independent_to_the_bit() -> None:
    """The Tier-2 construction reduces in sorted order too."""
    fares = [Decimal("5000"), Decimal("6000"), Decimal("4000"), Decimal("7500")]
    assert band_price(fares) == band_price(list(reversed(fares)))
    assert log_dispersion(fares) == log_dispersion(list(reversed(fares)))


# ---------------------------------------------------------------------------
# Price-relative invariants (spec Q)
# ---------------------------------------------------------------------------


@settings(max_examples=60, deadline=None)
@given(fares=st.lists(FARES, min_size=3, max_size=8, unique=True))
def test_identical_prices_give_a_relative_of_exactly_one(fares: list[Decimal]) -> None:
    """INV-1. Unchanged prices must give exactly 1.0, not 0.9999999999999999.

    The log form makes this exact: ln(p) - ln(p) is exactly 0.0 for any finite
    p, the mean of zeros is 0.0, and exp(0.0) is exactly 1.0.
    """
    flights = [f"{100 + i}" for i in range(len(fares))]
    prior = [ob(MONDAY - timedelta(days=7), f, p) for f, p in zip(flights, fares, strict=True)]
    now = [ob(MONDAY, f, p) for f, p in zip(flights, fares, strict=True)]
    assert relative(now, prior) == 1.0


@settings(max_examples=60, deadline=None)
@given(
    fares=st.lists(FARES, min_size=3, max_size=6, unique=True),
    k=st.integers(min_value=2, max_value=50),
)
def test_scaling_both_periods_leaves_the_relative_unchanged(fares: list[Decimal], k: int) -> None:
    """INV-2. A relative is invariant to a common scaling of both periods.

    Multiplying every fare by k adds ln(k) to both legs of every ratio, and it
    cancels. This is what makes the index a measure of *change* rather than of
    level.
    """
    flights = [f"{100 + i}" for i in range(len(fares))]
    prior = [ob(MONDAY - timedelta(days=7), f, p) for f, p in zip(flights, fares, strict=True)]
    now = [ob(MONDAY, f, p * 2) for f, p in zip(flights, fares, strict=True)]

    scaled_prior = [
        ob(MONDAY - timedelta(days=7), f, p * k) for f, p in zip(flights, fares, strict=True)
    ]
    scaled_now = [ob(MONDAY, f, p * 2 * k) for f, p in zip(flights, fares, strict=True)]

    assert relative(scaled_now, scaled_prior) == pytest.approx(relative(now, prior), rel=1e-12)


# ---------------------------------------------------------------------------
# Source precedence (spec D.8)
# ---------------------------------------------------------------------------


@settings(max_examples=60, deadline=None)
@given(cheap=FARES, dear=FARES)
def test_source_selection_never_depends_on_the_price(cheap: Decimal, dear: Decimal) -> None:
    """Spec D.8.2. The rule is price-blind, so it cannot bias the level.

    Whichever way round the two sources' fares fall, the higher-ranked source is
    selected. If selection ever consulted the fare, one of these two orderings
    would pick the other source.
    """
    agg = {"channel": Channel.AGGREGATOR}
    for first, second in ((cheap, dear), (dear, cheap)):
        prior = [
            ob(MONDAY - timedelta(days=7), "101", first, source="mmt", **agg),
            ob(MONDAY - timedelta(days=7), "101", second, source="ixigo", **agg),
        ]
        now = [
            ob(MONDAY, "101", first, source="mmt", **agg),
            ob(MONDAY, "101", second, source="ixigo", **agg),
        ]
        result = build_matched_set(
            now, prior, cell_key_for(now[0]), Tier.TIER_1, source_precedence=PRECEDENCE
        )
        assert len(result.pairs) == 1
        assert result.pairs[0].source_id == "mmt", "mmt outranks ixigo regardless of price"


def test_both_legs_of_a_relative_come_from_one_source() -> None:
    """Spec D.8.2. A cross-source ratio is impossible by construction."""
    agg = {"channel": Channel.AGGREGATOR}
    prior = [
        ob(MONDAY - timedelta(days=7), "101", Decimal("6000"), source="mmt", **agg),
        ob(MONDAY - timedelta(days=7), "101", Decimal("6100"), source="ixigo", **agg),
    ]
    now = [
        ob(MONDAY, "101", Decimal("6300"), source="mmt", **agg),
        ob(MONDAY, "101", Decimal("6100"), source="ixigo", **agg),
    ]
    pairs = build_matched_set(
        now, prior, cell_key_for(now[0]), Tier.TIER_1, source_precedence=PRECEDENCE
    ).pairs
    assert len(pairs) == 1
    # 6300/6000 from mmt alone. A cross-source pairing would give 6100/6000 or
    # 6300/6100, both of which mix two price concepts.
    assert math.exp(pairs[0].log_relative) == pytest.approx(6300 / 6000, rel=1e-12)


# ---------------------------------------------------------------------------
# Item / cell separation (spec B.2.0)
# ---------------------------------------------------------------------------


@settings(max_examples=50, deadline=None)
@given(n=st.integers(min_value=1, max_value=9))
def test_flights_of_one_carrier_never_split_a_cell(n: int) -> None:
    """Spec B.2.1. However many flights a carrier runs, they share one cell.

    This is AMB-1 stated as a property: the cell count must not scale with the
    flight count. Under v2.0 it did, exactly one-to-one.
    """
    now = [ob(MONDAY, f"{100 + i}", Decimal("5000"), dep=time(6 + i % 12, 0)) for i in range(n)]
    assert len({cell_key_for(o) for o in now}) == 1
    assert len({item_key_for(o, Tier.TIER_1) for o in now}) == n


def test_tier_change_does_not_move_the_cell() -> None:
    """Spec B.2.1. The cell key is tier-invariant, so weights survive a degrade.

    If the tier changed the cell key, a mid-year degradation would re-partition
    cells and re-derive ``v[c|r]``, violating spec F.5's fixed weights.
    """
    o = ob(MONDAY, "101", Decimal("5000"))
    cell = cell_key_for(o)
    assert all(cell == cell_key_for(o) for _ in Tier)
    assert not hasattr(cell, "tier")


# ---------------------------------------------------------------------------
# Parent object (spec E.6, E.7)
# ---------------------------------------------------------------------------


def _state(cell: CellKey, level: float | None, status: CellStatus) -> CellState:
    return CellState(
        cell=cell,
        collection_date=MONDAY - timedelta(days=APW),
        level=level,
        status=status,
        parent=cell.parent(),
    )


@settings(max_examples=40, deadline=None)
@given(entrant_weight=st.floats(min_value=0.01, max_value=100.0))
def test_an_entrant_can_never_move_the_parent_level(entrant_weight: float) -> None:
    """Spec E.7.2. The recursion is excluded by definition, not solved.

    Whatever weight a §J.1 entrant carries, it must not influence the level it
    is about to enter at. A fixed-point solution would let it, which is the
    spurious contribution §J.1 exists to prevent.
    """
    a = cell_key_for(ob(MONDAY, "101", Decimal("5000"), carrier="6E"))
    b = cell_key_for(ob(MONDAY, "101", Decimal("5000"), carrier="AI"))
    entrant = cell_key_for(ob(MONDAY, "101", Decimal("5000"), carrier="QP"))

    states = [_state(a, 105.0, CellStatus.PUBLISHED), _state(b, 107.0, CellStatus.PUBLISHED)]
    weights = {a: 1.0, b: 1.0, entrant: entrant_weight}

    without = parent_level(states, weights)
    with_entrant = parent_level(
        [*states, _state(entrant, 999.0, CellStatus.ENTERED)],
        weights,
        entered_at_t={entrant},
    )
    assert with_entrant == without == pytest.approx(106.0)


def test_a_carried_child_still_counts_toward_the_parent_level() -> None:
    """Spec E.7.3. Carries depend on ``J(P,t)``, not ``I(P,t)`` — no recursion.

    Excluding them would empty the independent-live set on exactly the thin
    strata where carry is normal, turning a definitional safeguard into a
    systematic hold-out.
    """
    a = cell_key_for(ob(MONDAY, "101", Decimal("5000"), carrier="6E"))
    carried = cell_key_for(ob(MONDAY, "101", Decimal("5000"), carrier="AI"))
    states = [
        _state(a, 100.0, CellStatus.PUBLISHED),
        _state(carried, 110.0, CellStatus.CARRIED),
    ]
    assert parent_level(states, {a: 1.0, carried: 1.0}) == pytest.approx(105.0)


def test_parent_relative_is_independent_of_observation_order() -> None:
    """Spec E.6.7 uses the same estimator, so it inherits the same determinism."""
    spec = [("6E", "101"), ("AI", "201"), ("SG", "301"), ("IX", "401")]
    prior = [
        ob(MONDAY - timedelta(days=7), f, Decimal(5000 + 100 * i), carrier=c, dep=time(6 + i, 0))
        for i, (c, f) in enumerate(spec)
    ]
    now = [
        ob(MONDAY, f, Decimal(5200 + 100 * i), carrier=c, dep=time(6 + i, 0))
        for i, (c, f) in enumerate(spec)
    ]
    parent = parent_key_for(now[0])

    def run(a: list[Observation], b: list[Observation]) -> float | None:
        return compute_parent_relative(
            a,
            b,
            parent,
            Tier.TIER_1,
            MONDAY - timedelta(days=APW),
            source_precedence=PRECEDENCE,
        ).jevons.relative

    assert run(now, prior) == run(list(reversed(now)), list(reversed(prior)))


def test_parent_pools_carriers_but_never_channels_or_fare_classes() -> None:
    """Spec E.4. Only ``carrier`` is dropped — pooling more would break §B.5/§B.4."""
    base = ob(MONDAY, "101", Decimal("5000"))
    other_carrier = ob(MONDAY, "101", Decimal("5000"), carrier="AI")
    other_channel = ob(MONDAY, "101", Decimal("5000"), channel=Channel.AGGREGATOR, source="mmt")

    assert parent_key_for(base) == parent_key_for(other_carrier), "carriers pool"
    assert parent_key_for(base) != parent_key_for(other_channel), "channels do not"
    assert not hasattr(parent_key_for(base), "carrier")


# ---------------------------------------------------------------------------
# New item vs new cell (spec J.0)
# ---------------------------------------------------------------------------


def test_a_new_item_leaves_the_cell_population_unchanged() -> None:
    """Spec J.0 case 1. A newly appearing flight is not a new elementary aggregate."""
    established = [ob(MONDAY, f"{100 + i}", Decimal("5000")) for i in range(3)]
    with_newcomer = [*established, ob(MONDAY, "999", Decimal("5000"))]

    assert {cell_key_for(o) for o in established} == {cell_key_for(o) for o in with_newcomer}
    assert len({item_key_for(o, Tier.TIER_1) for o in with_newcomer}) == 4


def test_an_unmatched_newcomer_contributes_to_neither_side() -> None:
    """Spec D.1. It cannot move the index on the day it appears."""
    flights = ["101", "205", "317"]
    prior = [ob(MONDAY - timedelta(days=7), f, Decimal("5000")) for f in flights]
    now = [ob(MONDAY, f, Decimal("5000")) for f in flights]
    with_newcomer = [*now, ob(MONDAY, "999", Decimal("99999"))]

    assert relative(now, prior) == relative(with_newcomer, prior) == 1.0


# ---------------------------------------------------------------------------
# Tier accounting (spec I, B.3)
# ---------------------------------------------------------------------------


def test_a_route_level_tier_label_does_not_leak_onto_carrier_cells() -> None:
    """Spec B.3, I. Tier shares are weight-weighted over CELLS, not routes.

    Under v2.1 one route can hold a Tier-1 cell and a Tier-2 cell at the same
    time, because tier is a property of a ``(route, carrier)`` pair. Attributing
    the whole route's weight to a single tier — the v2.0 reading — would report
    100% Tier-3 for a route where only one of two carriers is Tier 3.
    """
    from apix.schemas.version_vector import VersionVector
    from apix.statistics.index.apix_l import calculate_apix_l, cell_id

    tier1 = cell_key_for(ob(MONDAY, "101", Decimal("5000"), carrier="6E"))
    tier3 = cell_key_for(ob(MONDAY, "101", Decimal("5000"), carrier="QP"))
    when = MONDAY - timedelta(days=APW)

    states = [
        CellState(cell=tier1, collection_date=when, level=100.0, status=CellStatus.PUBLISHED),
        CellState(cell=tier3, collection_date=when, level=100.0, status=CellStatus.PUBLISHED),
    ]
    vv = VersionVector(
        data_snapshot_id="sha256:a",
        methodology_version="2.1",
        basket_version="b",
        weight_version="w",
        parser_version="p",
        code_version="c",
    )

    result = calculate_apix_l(
        states,
        {cell_id(tier1): 0.5, cell_id(tier3): 0.5},
        {"DEL-BOM": 1.0},
        vv,
        when,
        route_tiers={"DEL-BOM": Tier.TIER_3},
        cell_tiers={cell_id(tier1): Tier.TIER_1, cell_id(tier3): Tier.TIER_3},
    )

    # Half the route's weight is Tier 3, not all of it.
    assert result.quality.tier3_weight_share == pytest.approx(0.5)
    assert result.quality.tier1_weight_share == pytest.approx(0.5)

    # The v2.0 reading, for contrast: with only a route label to go on, the
    # whole route counts as Tier 3 and the share doubles to 1.0.
    route_only = calculate_apix_l(
        states,
        {cell_id(tier1): 0.5, cell_id(tier3): 0.5},
        {"DEL-BOM": 1.0},
        vv,
        when,
        route_tiers={"DEL-BOM": Tier.TIER_3},
    )
    assert route_only.quality.tier3_weight_share == pytest.approx(1.0)
    assert result.quality.tier3_weight_share < route_only.quality.tier3_weight_share

    # 50% still breaches the 25% ceiling, so the caveat fires either way — the
    # point is the magnitude, which drives the published quality metric.
    assert any("Tier-3" in c for c in result.quality.caveats)


def test_held_out_weight_is_reported_separately_from_suppressed() -> None:
    """Spec E.7.4. Two different quality events, two different numbers."""
    from apix.schemas.version_vector import VersionVector
    from apix.statistics.index.apix_l import calculate_apix_l, cell_id

    live = cell_key_for(ob(MONDAY, "101", Decimal("5000"), carrier="6E"))
    held = cell_key_for(ob(MONDAY, "101", Decimal("5000"), carrier="AI"))
    when = MONDAY - timedelta(days=APW)

    states = [
        CellState(cell=live, collection_date=when, level=100.0, status=CellStatus.PUBLISHED),
        CellState(cell=held, collection_date=when, level=None, status=CellStatus.HELD_OUT),
    ]
    vv = VersionVector(
        data_snapshot_id="sha256:a",
        methodology_version="2.1",
        basket_version="b",
        weight_version="w",
        parser_version="p",
        code_version="c",
    )
    result = calculate_apix_l(
        states,
        {cell_id(live): 0.5, cell_id(held): 0.5},
        {"DEL-BOM": 1.0},
        vv,
        when,
    )
    assert result.quality.held_out_weight_share == pytest.approx(0.5)
    assert result.quality.carried_weight_share == 0.0
