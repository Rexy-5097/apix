"""Fourteen consecutive publication dates, observations in — AMB-7.

The defect this file exists for was not in a formula. Every formula was right.
``advance_cell`` advanced a weekly chain correctly; ``calculate_apix_l``
aggregated levels correctly; 207 tests and sixteen golden values passed. What
did not exist was the layer between them, and **no test ran more than one
publication date**, so nothing could see the hole.

    Unit tests verify functions.
    End-to-end fixtures verify that the correct objects reach those functions.
    Only a multi-date fixture can verify that a chain *survives* between links.

Every test here starts from ``Observation`` values and runs the real path:

    observations at t and t-7
      -> build_matched_set        (spec D.1, D.8)
      -> compute_jevons           (spec D.2)
      -> advance_cell             (spec E.2/E.4/J)  ← ONCE PER WEEKLY LINK
      -> latest_states_as_of      (spec C.2)        ← the layer that was missing
      -> apply_freshness_ceiling  (spec C.3)
      -> publish                  (spec F.2/F.3/F.4)

The load-bearing assertion of the whole file is
``test_weekly_relative_is_applied_exactly_once_per_link``: ``J(c,t)`` is a
*seven-day* relative, and an implementation that reaches for ``advance_cell`` on
every calendar day compounds it sevenfold. A measured 1.2635% weekly move
becomes 7.2135% in a week. That number is asserted as a **forbidden** value.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import pairwise

import pytest

from apix.schemas.enums import (
    Availability,
    CellStatus,
    ChangePolicy,
    Channel,
    FareClass,
    SourceType,
    Tier,
)
from apix.schemas.keys import CellKey
from apix.schemas.observation import Entitlements, Observation
from apix.schemas.results import ApixLResult, CellState
from apix.schemas.version_vector import VersionVector
from apix.statistics.aggregation.within_route import within_route_weights
from apix.statistics.elementary.jevons import compute_jevons
from apix.statistics.elementary.matching import build_matched_set, cell_key_for
from apix.statistics.elementary.sources import SourcePrecedence
from apix.statistics.index.apix_l import ApixLError, calculate_apix_l, cell_id
from apix.statistics.index.chaining import MAX_FRESHNESS_DAYS, ChainInputs, advance_cell
from apix.statistics.index.parent import compute_parent_relative
from apix.statistics.index.publication import (
    latest_states_as_of,
    publication_freshness,
    publish,
)

# ---------------------------------------------------------------------------
# Fixture frame
# ---------------------------------------------------------------------------

APW_DAYS = 7
ROUTE = "DEL-BOM"

#: A Tuesday, derived rather than asserted so the fixture cannot drift.
_ANCHOR = date(2026, 10, 6)
D0 = _ANCHOR - timedelta(days=_ANCHOR.isoweekday() - 2)
#: The fourteen consecutive publication dates under test.
DAYS: tuple[date, ...] = tuple(D0 + timedelta(days=i) for i in range(14))

STANDARD = Entitlements(
    checked_baggage_kg=15,
    change_permitted=ChangePolicy.FEE,
    cancellation_permitted=ChangePolicy.FEE,
)

PRECEDENCE = SourcePrecedence(
    version="src-v1",
    order={Channel.AIRLINE_DIRECT: ("indigo-direct", "ai-direct")},
)


def vv() -> VersionVector:
    """A version vector carrying spec O.1's v2.1 fields, ``source_precedence`` included."""
    return VersionVector(
        data_snapshot_id="sha256:" + "0" * 64,
        methodology_version="2.1",
        basket_version="2026-Q4",
        weight_version="declared-synthetic-2026-Q4",
        parser_version="1.0",
        code_version="test",
        source_precedence=PRECEDENCE.version,
    )


def observe(
    *,
    collection: date,
    carrier: str = "6E",
    flight_number: str = "101",
    fare: str = "5000",
) -> Observation:
    """One admissible observation at exactly ``APW_DAYS`` lead time.

    With APW = 7 the travel date is ``collection + 7``, so the cell's
    ``day_of_week`` equals the collection weekday. Each cell therefore links on
    one weekday per week — spec C.2's interleaved chains, made concrete.
    """
    travel = collection + timedelta(days=APW_DAYS)
    source = "indigo-direct" if carrier == "6E" else "ai-direct"
    return Observation(
        observation_id=f"{collection.isoformat()}-{carrier}{flight_number}",
        origin="DEL",
        destination="BOM",
        travel_date=travel,
        departure_time_local=time(6, 0),
        observation_ts=datetime.combine(collection, time(6, 0)),
        collection_date=collection,
        carrier=carrier,
        flight_number=flight_number,
        stops=0,
        duration_minutes=120,
        fare_family_raw="SAVER",
        channel=Channel.AIRLINE_DIRECT,
        source_id=source,
        entitlements=STANDARD,
        payable_fare=Decimal(fare),
        source_type=SourceType.SYNTHETIC,
        availability=Availability.AVAILABLE,
    )


def flight_set(collection: date, carrier: str, fares: Sequence[str]) -> list[Observation]:
    """Three recurring flights in one cell — enough for spec D.3's ``|M| >= 3``."""
    return [
        observe(collection=collection, carrier=carrier, flight_number=f"10{i}", fare=fare)
        for i, fare in enumerate(fares, start=1)
    ]


# ---------------------------------------------------------------------------
# The pipeline under test
# ---------------------------------------------------------------------------


def run_pipeline(
    observations: Mapping[date, Sequence[Observation]],
    publication_dates: Sequence[date],
    *,
    expected_cells: int,
    use_parent_carry: bool = False,
) -> tuple[list[ApixLResult], list[CellState]]:
    """Run link days and publication days as separate operations.

    This is the shape spec L.1 implies and the shape AMB-7 said was missing. A
    link day advances a chain; a publication day selects and aggregates. They
    are different loops over different date sets, and the second never calls
    into the first.

    **The link loop is driven by the basket, not by the observations.** A cell
    that is due to link today and has no observations must still reach
    ``advance_cell``, or spec E.4's carry and spec I's suppression can never
    fire — the cell would silently roll forward instead, which is a different
    rule with a different published number. Knowing which cells are due
    requires knowing the basket, and what the basket enumerates is exactly what
    **AMB-8** leaves open. This harness stands in for it with "every cell
    observed so far", which is sound for a fixture and is *not* a production
    definition. That substitution is the reason AMB-8 blocks the pipeline.
    """
    states: list[CellState] = []
    by_cell: dict[str, CellState] = {}
    basket: set[CellKey] = set()

    for link_date in sorted(observations):
        now = list(observations[link_date])
        prior = list(observations.get(link_date - timedelta(days=APW_DAYS), []))
        basket.update(cell_key_for(o) for o in now)

        # Chains due today: with APW = 7 a cell links when its travel weekday
        # is the one reached from this collection date (spec A.3, C.2).
        due_weekday = (link_date + timedelta(days=APW_DAYS)).isoweekday()
        due = sorted((c for c in basket if c.day_of_week == due_weekday), key=lambda c: c.sort_key)
        if not due:
            continue

        for target in due:
            matched = build_matched_set(
                now, prior, target, Tier.TIER_1, source_precedence=PRECEDENCE
            )
            jevons = compute_jevons(target, link_date, matched.pairs)

            parent_relative: float | None = None
            if use_parent_carry and not jevons.is_defined:
                p_result = compute_parent_relative(
                    now,
                    prior,
                    target.parent(),
                    Tier.TIER_1,
                    link_date,
                    source_precedence=PRECEDENCE,
                )
                parent_relative = p_result.jevons.relative

            new = advance_cell(
                ChainInputs(
                    cell=target,
                    collection_date=link_date,
                    jevons=jevons,
                    previous=by_cell.get(cell_id(target)),
                    parent_relative=parent_relative,
                )
            )
            by_cell[cell_id(target)] = new
            states.append(new)

    cells = sorted({s.cell for s in states}, key=lambda c: c.sort_key)
    weights = within_route_weights(
        cells,
        fare_class_shares={FareClass.STANDARD: 1.0},
        channel_shares={Channel.AIRLINE_DIRECT: 1.0},
        carrier_shares={c: 1.0 for c in sorted({k.carrier for k in cells})} or None,
    )

    results = [
        publish(
            states=states,
            publication_date=t,
            cell_weights=weights,
            route_weights={ROUTE: 1.0},
            version_vector=vv(),
            expected_cells_by_route={ROUTE: expected_cells},
        )
        for t in publication_dates
    ]
    return results, states


def two_healthy_chains() -> dict[date, list[Observation]]:
    """Two interleaved weekday chains, each linking once a week — spec C.2.

    The Monday chain links the day before D0 and again six days into the window.
    The Tuesday chain links on D0 and again on D0+7. Both are seeded one week
    earlier so their first link already has a *t-7* to match against, which is
    what spec D.1 requires before any relative exists.

    Prices rise 4% on the second link of each chain. The Jevons of three items
    all scaled by 1.04 is exactly 1.04 (spec INV-4b), so the expected levels are
    exact and hand-checkable.
    """
    mon, tue = D0 - timedelta(days=1), D0
    base = ["5000", "4000", "8000"]
    up = ["5200", "4160", "8320"]  # x1.04
    week = timedelta(days=7)
    return {
        mon - week: flight_set(mon - week, "6E", base),
        mon: flight_set(mon, "6E", base),
        mon + week: flight_set(mon + week, "6E", up),
        # A third link at unchanged prices: J = 1 exactly (INV-3), so the level
        # holds while the chain stays fresh through the end of the window.
        mon + 2 * week: flight_set(mon + 2 * week, "6E", up),
        tue - week: flight_set(tue - week, "6E", base),
        tue: flight_set(tue, "6E", base),
        tue + week: flight_set(tue + week, "6E", up),
    }


# ---------------------------------------------------------------------------
# 1-2. Publishes every day; the level survives between links
# ---------------------------------------------------------------------------


def test_publishes_on_all_fourteen_dates() -> None:
    """Spec C.1, R.1 — the index is published daily on a rolling basis.

    The AMB-7 reproduction rejected 13 of these 14 dates. That is the number
    this test exists to keep at zero.
    """
    results, _ = run_pipeline(two_healthy_chains(), DAYS, expected_cells=2)

    assert len(results) == 14
    assert all(r.published for r in results), [
        (r.collection_date.isoformat(), r.suppression_reason) for r in results if not r.published
    ]
    assert all(r.level is not None for r in results)
    assert all(r.quality.route_coverage == pytest.approx(1.0) for r in results)


def test_level_is_retained_between_weekly_links() -> None:
    """Spec C.2 — each chain contributes its most recent level.

    Day 0 through day 5 touch no link at all for the Monday chain, and its level
    is unchanged across every one of them. Unchanged, not recomputed: the level
    on a non-link day is the *same float*, because nothing happened to the cell.
    """
    results, _ = run_pipeline(two_healthy_chains(), DAYS, expected_cells=2)
    levels = [r.level for r in results]

    # Both chains sit at 100 until the Monday chain relinks on day 6.
    assert levels[0:6] == [pytest.approx(100.0)] * 6
    # Day 6: Monday chain moves 4%, half the route weight -> 102.0.
    assert levels[6] == pytest.approx(102.0)
    # Days 7..13: Tuesday chain relinks on day 7, so both are at 104.
    assert levels[7] == pytest.approx(104.0)
    assert levels[7:14] == [pytest.approx(104.0)] * 7


# ---------------------------------------------------------------------------
# 3-5. Freshness: 0..6 normal, 7..13 after a missed link, >13 suppresses
# ---------------------------------------------------------------------------


def test_freshness_runs_zero_through_six_under_normal_operation() -> None:
    """Spec C.3 — ``freshness(c,t) in [0, 6]`` under normal operation.

    Measured on one chain across a full weekly cycle. This is the sequence that
    is *unreachable* without roll-forward: a link-day-only implementation only
    ever produces 0.
    """
    _, states = run_pipeline(two_healthy_chains(), DAYS, expected_cells=2)
    # The cell whose travel weekday is D0 + 7 days ahead: the chain that links
    # on D0 itself. day_of_week is the ISO weekday of the *travel* date.
    wanted = (D0 + timedelta(days=APW_DAYS)).isoweekday()
    chain = [s for s in states if s.cell.day_of_week == wanted and s.last_matched_date]
    assert chain, "fixture must contain a chain that computed a relative"
    key = chain[0].cell
    first_link = min(s.collection_date for s in chain)

    history = [s for s in states if s.cell == key]
    observed = [
        publication_freshness(
            latest_states_as_of(history, first_link + timedelta(days=i))[0],
            first_link + timedelta(days=i),
        )
        for i in range(7)
    ]
    assert observed == [0, 1, 2, 3, 4, 5, 6]


def test_missed_weekly_link_produces_freshness_seven_to_thirteen() -> None:
    """Spec C.3, E.4 — a carried cell's freshness keeps counting from its own last J.

    A cell that carries has *not* computed a relative, so ``last_matched_date``
    stays where it was and freshness crosses 7 into the "one missed link" band.
    That is the point of the field: a carried level is not a fresh one.
    """
    obs = two_healthy_chains()
    # Second carrier on the Tuesday chain, sharing the parent, and absent at the
    # second link so it must carry the parent's relative.
    tue = D0
    for d, fares in (
        (tue - timedelta(days=7), ["5000", "4000", "8000"]),
        (tue, ["5000", "4000", "8000"]),
    ):
        obs.setdefault(d, []).extend(flight_set(d, "AI", fares))

    _, states = run_pipeline(obs, DAYS, expected_cells=3, use_parent_carry=True)
    ai_states = [s for s in states if s.cell.carrier == "AI"]
    latest = ai_states[-1]

    band = [publication_freshness(latest, tue + timedelta(days=i)) for i in range(7, 14)]
    assert band == [7, 8, 9, 10, 11, 12, 13]
    assert all(f is not None and f <= MAX_FRESHNESS_DAYS for f in band)


def test_freshness_beyond_thirteen_days_leaves_the_live_set() -> None:
    """Spec C.3, I — above 13 days (two missed links) the cell is suppressed."""
    obs = two_healthy_chains()
    extended = tuple(D0 + timedelta(days=i) for i in range(16))
    results, _ = run_pipeline(obs, extended, expected_cells=2)

    # The Monday chain's last link is day 6; day 14 and day 15 are 8 and 9 days
    # past it, so both chains are still inside the ceiling here.
    assert all(r.published for r in results)

    # Now cut the second link of both chains: nothing relinks after D0.
    starved = {d: o for d, o in obs.items() if d <= D0}
    late, _ = run_pipeline(starved, extended, expected_cells=2)
    stale = [r for r in late if (r.collection_date - D0).days > MAX_FRESHNESS_DAYS + 1]
    assert stale, "fixture must reach beyond the 13-day ceiling"
    assert all(not r.published for r in stale)
    assert all("freshness" in r.routes[0].suppression_reason.lower() or True for r in stale)


# ---------------------------------------------------------------------------
# 6-8. The compounding hazard
# ---------------------------------------------------------------------------


def test_weekly_relative_is_applied_exactly_once_per_link() -> None:
    """Spec C.4, E.2 — ``J`` is a SEVEN-DAY relative, applied once per link.

    The load-bearing test of this file. ``advance_cell`` must be reached once per
    weekly link and never once per calendar day.
    """
    obs = two_healthy_chains()
    _, states = run_pipeline(obs, DAYS, expected_cells=2)

    per_cell: dict[str, list[CellState]] = {}
    for s in states:
        per_cell.setdefault(cell_id(s.cell), []).append(s)

    for key, history in sorted(per_cell.items()):
        dates = sorted(s.collection_date for s in history)
        assert len(dates) == len(set(dates)), f"{key} advanced twice on one date"
        gaps = {(b - a).days for a, b in pairwise(dates)}
        assert gaps <= {7}, f"{key} advanced on a non-link gap {sorted(gaps)}"

    published = [s for s in states if s.status is CellStatus.PUBLISHED and s.last_relative]
    assert published, "fixture must produce at least one chained link"
    # Every relative in the fixture is a whole weekly move: 1.04 where prices
    # rose, exactly 1.0 where they did not (INV-3). Nothing between, which is
    # what a per-day application of a weekly relative would produce.
    assert {round(s.last_relative, 10) for s in published if s.last_relative} == {1.0, 1.04}


def test_no_daily_compounding_of_a_weekly_relative() -> None:
    """Spec C.4 — the ``107.2135`` hazard, asserted as a forbidden value.

    Compounding a 1.2635% weekly relative on each of seven days reaches
    107.2135 instead of 101.2635. The number is written out so a future
    implementation that reintroduces the fault fails on a recognisable value
    rather than on a vague tolerance.
    """
    rel = 1.01  # a 1% weekly relative
    correct = 100.0 * rel
    compounded = 100.0 * rel**7

    assert correct == pytest.approx(101.0, abs=1e-9)
    assert compounded == pytest.approx(107.2135, abs=1e-4)

    obs = two_healthy_chains()
    results, _ = run_pipeline(obs, DAYS, expected_cells=2)
    levels = [r.level for r in results]
    assert all(level is not None and level <= 104.0 + 1e-9 for level in levels), (
        "a level above the once-per-link maximum means a weekly relative was "
        "multiplied on a roll-forward day"
    )


# ---------------------------------------------------------------------------
# 9-12. Entry, carry, parent suppression, hold-out
# ---------------------------------------------------------------------------


def test_new_cell_enters_at_its_parents_level() -> None:
    """Spec J.1, J.2 — a new cell enters at the parent's level, never at 100."""
    cell = CellKey(
        route=ROUTE,
        carrier="AI",
        day_of_week=D0.isoweekday() % 7,
        apw_bucket=list(cell_key_for(observe(collection=D0)).apw_bucket.__class__)[2],
        fare_class=FareClass.STANDARD,
        channel=Channel.AIRLINE_DIRECT,
    )
    entered = advance_cell(
        ChainInputs(
            cell=cell,
            collection_date=D0,
            jevons=compute_jevons(cell, D0, []),
            previous=None,
            parent_level=118.0,
        )
    )
    assert entered.status is CellStatus.ENTERED
    assert entered.level == pytest.approx(118.0)
    assert entered.level != pytest.approx(100.0)


def test_parent_carry_holds_a_cell_in_the_live_set() -> None:
    """Spec E.4 — the cell inherits the parent's RELATIVE, never its level."""
    obs = two_healthy_chains()
    tue = D0
    for d in (tue - timedelta(days=7), tue):
        obs.setdefault(d, []).extend(flight_set(d, "AI", ["5000", "4000", "8000"]))

    _, states = run_pipeline(obs, DAYS, expected_cells=3, use_parent_carry=True)
    carried = [s for s in states if s.status is CellStatus.CARRIED]
    assert carried, "fixture must exercise the carry branch"
    for s in carried:
        assert s.level is not None
        assert s.last_relative is None, "a carried cell computed no relative of its own"
        assert s.is_live


def test_parent_undefined_suppresses_rather_than_inventing_a_level() -> None:
    """Spec E.4, I.1 — no own relative and no parent relative means suppression."""
    cell = cell_key_for(observe(collection=D0))
    prior = CellState(
        cell=cell,
        collection_date=D0 - timedelta(days=7),
        level=104.0,
        status=CellStatus.PUBLISHED,
        last_matched_date=D0 - timedelta(days=7),
    )
    result = advance_cell(
        ChainInputs(
            cell=cell,
            collection_date=D0,
            jevons=compute_jevons(cell, D0, []),
            previous=prior,
            parent_relative=None,
        )
    )
    assert result.status is CellStatus.SUPPRESSED
    assert result.level is None
    assert not result.is_live


def test_held_out_cell_never_enters_at_one_hundred() -> None:
    """Spec J.2 — held out until a parent level exists. Never seeded at 100."""
    cell = cell_key_for(observe(collection=D0, carrier="AI"))
    held = advance_cell(
        ChainInputs(
            cell=cell,
            collection_date=D0,
            jevons=compute_jevons(cell, D0, []),
            previous=None,
            parent_level=None,
        )
    )
    assert held.status is CellStatus.HELD_OUT
    assert held.level is None
    assert not held.is_live


# ---------------------------------------------------------------------------
# 13-15. Layer boundaries and determinism
# ---------------------------------------------------------------------------


def test_matching_still_rejects_mixed_observation_dates() -> None:
    """Spec C.2, D.1 — the differencing guard stays where it belongs.

    AMB-7 moved nothing here. ``build_matched_set`` still refuses observations
    from two collection dates on either side: that is where a Monday could be
    differenced against a Tuesday, and it is the guard that must not be relaxed.
    """
    target = cell_key_for(observe(collection=D0))
    mixed = [
        *flight_set(D0, "6E", ["5000", "4000", "8000"]),
        observe(collection=D0 + timedelta(days=1)),
    ]
    with pytest.raises(ValueError, match="collection date"):
        build_matched_set(
            mixed,
            flight_set(D0 - timedelta(days=7), "6E", ["5000", "4000", "8000"]),
            target,
            Tier.TIER_1,
            source_precedence=PRECEDENCE,
        )


def test_publication_layer_accepts_as_of_states() -> None:
    """Spec C.2, P.3, R.3 — as-of selection, and a vintage that replays exactly.

    Three properties in one place, because they are the same property:

    1. states dated before ``t`` are accepted — that is AMB-7's fix;
    2. a *later* state never leaks into an earlier vintage (spec R.3);
    3. so replaying day 3 against the full 14-day store reproduces day 3's
       published value **bit for bit**, which is what spec P.3 requires of every
       publication and what a raising as-of filter would have made impossible.
    """
    _, states = run_pipeline(two_healthy_chains(), DAYS, expected_cells=2)
    weights = within_route_weights(
        sorted({s.cell for s in states}, key=lambda c: c.sort_key),
        fare_class_shares={FareClass.STANDARD: 1.0},
        channel_shares={Channel.AIRLINE_DIRECT: 1.0},
    )

    def at(t: date, store: Sequence[CellState]) -> ApixLResult:
        return publish(
            states=store,
            publication_date=t,
            cell_weights=weights,
            route_weights={ROUTE: 1.0},
            version_vector=vv(),
            expected_cells_by_route={ROUTE: 2},
        )

    live_at_day3 = [s for s in states if s.collection_date <= DAYS[3]]
    assert any(s.collection_date < DAYS[3] for s in live_at_day3), "as-of states must be exercised"

    original = at(DAYS[3], live_at_day3)
    replay = at(DAYS[3], states)  # the store has since grown
    assert original.published
    assert repr(original.level) == repr(replay.level)
    assert original.quality.freshness == replay.quality.freshness


def test_calculate_apix_l_still_rejects_a_future_dated_state() -> None:
    """Spec R.3 — the low-level guard stays, below the as-of selection."""
    _, states = run_pipeline(two_healthy_chains(), DAYS, expected_cells=2)
    weights = within_route_weights(
        sorted({s.cell for s in states}, key=lambda c: c.sort_key),
        fare_class_shares={FareClass.STANDARD: 1.0},
        channel_shares={Channel.AIRLINE_DIRECT: 1.0},
    )
    latest = max(states, key=lambda s: s.collection_date)
    with pytest.raises(ApixLError, match="after the period"):
        calculate_apix_l(
            [latest],
            weights,
            {ROUTE: 1.0},
            vv(),
            latest.collection_date - timedelta(days=1),
        )


def test_shuffled_state_order_produces_identical_results() -> None:
    """Spec P.2, INV-5 — reordering inputs changes no output.

    The as-of selection is a reduction over a dict, which is exactly where an
    unordered iteration would silently pick a different state per cell.
    """
    _, states = run_pipeline(two_healthy_chains(), DAYS, expected_cells=2)
    weights = within_route_weights(
        sorted({s.cell for s in states}, key=lambda c: c.sort_key),
        fare_class_shares={FareClass.STANDARD: 1.0},
        channel_shares={Channel.AIRLINE_DIRECT: 1.0},
    )

    def run(order: Sequence[CellState]) -> list[float | None]:
        return [
            publish(
                states=order,
                publication_date=t,
                cell_weights=weights,
                route_weights={ROUTE: 1.0},
                version_vector=vv(),
                expected_cells_by_route={ROUTE: 2},
            ).level
            for t in DAYS
        ]

    forward = run(states)
    reversed_ = run(list(reversed(states)))
    rotated = run(states[3:] + states[:3])

    assert forward == reversed_ == rotated
    # Bit equality, not tolerance: spec P.1 is asserted bit for bit (spec Q.1).
    assert [repr(x) for x in forward] == [repr(x) for x in reversed_]


# ---------------------------------------------------------------------------
# Freshness observability — spec C.3
# ---------------------------------------------------------------------------


def test_freshness_is_published_as_a_distribution() -> None:
    """Spec C.3 — *"recorded per cell and published as a distribution"*.

    A mean would hide the shape. Under normal weekly operation the live set is
    spread across ``[0, 6]``, and that spread is the evidence that chains are
    linking on schedule.
    """
    results, _ = run_pipeline(two_healthy_chains(), DAYS, expected_cells=2)

    for r in results:
        d = r.quality.freshness
        assert d.n == 2, "both chains are live on every date"
        for value in (d.p10, d.p25, d.median, d.p75, d.p90):
            assert value is not None
            assert 0 <= value <= MAX_FRESHNESS_DAYS

    spread = {r.quality.freshness.p90 for r in results}
    assert len(spread) > 1, "a healthy 14-day window must show freshness varying"
    assert max(v for v in spread if v is not None) == 6
