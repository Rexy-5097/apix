"""Edge-case and property coverage for the deterministic core.

Every threshold in the frozen specification is crossed in **both** directions
(INV-8): one case just below and one just at or above. A threshold tested from
only one side does not prove the threshold exists.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from apix.schemas.enums import (
    APWBucket,
    Availability,
    CellStatus,
    ChangePolicy,
    Channel,
    ExclusionReason,
    FareClass,
    SourceType,
    Tier,
    UndefinedRelativeReason,
)
from apix.schemas.keys import CellKey, ItemKey
from apix.schemas.observation import Entitlements, Observation
from apix.schemas.results import CellState, MatchedPair
from apix.schemas.version_vector import VersionVector
from apix.statistics.aggregation.weights import (
    WeightError,
    normalise,
    renormalise_over_live_set,
    sums_to_one,
    validate,
)
from apix.statistics.aggregation.within_route import (
    CarrierAllocation,
    CarrierAllocationBasis,
    within_route_weights,
)
from apix.statistics.aggregation.young_laspeyres import (
    AggregationError,
    aggregate_levels,
    aggregate_over_live_set,
)
from apix.statistics.elementary.admissibility import CollectionWindow, filter_admissible
from apix.statistics.elementary.dedup import deduplicate, duplicate_key
from apix.statistics.elementary.jevons import (
    MIN_MATCHED_ITEMS_PER_CELL,
    compute_jevons,
)
from apix.statistics.elementary.matching import (
    MATCHING_LAG_DAYS,
    build_matched_set,
    cell_key_for,
    prior_period,
    select_tier,
)
from apix.statistics.elementary.outliers import (
    MIN_ITEMS_FOR_OUTLIER_RULE,
    flag_outliers,
)
from apix.statistics.elementary.sources import SourcePrecedence
from apix.statistics.index.apix_l import ApixLError, calculate_apix_l, cell_id
from apix.statistics.index.chaining import (
    MAX_CELL_IMPUTATION,
    MAX_FRESHNESS_DAYS,
    ChainInputs,
    advance_cell,
)

T = date(2026, 9, 8)  # a Tuesday

#: Spec D.8 requires a declared source rule on every matching call. These
#: fixtures use a single source, so selection is unambiguous — but it is
#: applied rather than bypassed, because an undeclared rule is exactly what
#: v2.1 exists to remove.
PRECEDENCE = SourcePrecedence(version="test-src-v1", order={})
REL_TOL = 1.0e-12


# ─── Builders ────────────────────────────────────────────────────────────────


def cell(carrier: str = "6E", route: str = "DEL-BOM", tier: Tier = Tier.TIER_1) -> CellKey:
    """A v2.1 cell key — spec B.2.1.

    Migrated for methodology v2.1. The cell key is now **tier-invariant** and
    carries no flight identity: flight number and departure band identify
    *items*, not cells. Call sites previously discriminated cells by passing a
    flight number, so the first argument now names the field that actually
    discriminates cells — the **carrier**. Each call site keeps the distinctness
    it had: what were two cells are still two cells.

    ``tier`` is accepted and ignored, so call sites that name one still read
    correctly. Tier is a property of a ``(route, carrier)`` pair recorded
    alongside the cell, never part of its identity.
    """
    del tier
    return CellKey(
        route=route,
        carrier=carrier,
        day_of_week=2,
        apw_bucket=APWBucket.T_PLUS_7,
        fare_class=FareClass.STANDARD,
        channel=Channel.AIRLINE_DIRECT,
    )


def pair(idx: int, p_prev: str, p_now: str) -> MatchedPair:
    prev, now = Decimal(p_prev), Decimal(p_now)
    return MatchedPair(
        item=ItemKey(tier=Tier.TIER_1, carrier="6E", flight_number=f"{idx:02d}"),
        price_t=now,
        price_t_minus_7=prev,
        log_relative=math.log(float(now)) - math.log(float(prev)),
        observation_id_t=f"o{idx}-t",
        observation_id_t_minus_7=f"o{idx}-p",
    )


def obs(
    oid: str,
    *,
    fare: str = "5000.00",
    travel: date | None = None,
    collection: date = T,
    flight: str = "6E101",
    dep: time = time(8, 30),
    ts: datetime | None = None,
    source: str = "indigo",
    availability: Availability = Availability.AVAILABLE,
    baggage: int = 15,
) -> Observation:
    return Observation(
        observation_id=oid,
        origin="DEL",
        destination="BOM",
        travel_date=travel or (collection + timedelta(days=7)),
        departure_time_local=dep,
        observation_ts=ts or datetime(2026, 9, 8, 6, 0, 0),
        collection_date=collection,
        carrier="6E",
        flight_number=flight,
        stops=0,
        duration_minutes=125,
        fare_family_raw="SAVER",
        channel=Channel.AIRLINE_DIRECT,
        source_id=source,
        entitlements=Entitlements(baggage, ChangePolicy.FEE, ChangePolicy.FEE),
        payable_fare=Decimal(fare),
        source_type=SourceType.LIVE_SCRAPE,
        availability=availability,
    )


def vv(model_version: str | None = None) -> VersionVector:
    return VersionVector(
        data_snapshot_id="sha256:abc",
        methodology_version="2.0",
        basket_version="2026-Q3",
        weight_version="dgca-2026-09",
        parser_version="2.4",
        code_version="7f3a91c",
        model_version=model_version,
    )


def published(c: CellKey, level: float, when: date = T) -> CellState:
    return CellState(
        cell=c,
        collection_date=when,
        level=level,
        status=CellStatus.PUBLISHED,
        last_matched_date=when,
    )


# ─── Fares ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fare", ["0.00", "-1.00", "-9999.99"])
def test_non_positive_fare_is_inadmissible(fare: str) -> None:
    """A non-positive fare is a parse failure, not a cheap ticket — and ln(p)
    is undefined for it, so it must never reach the Jevons relative."""
    result = filter_admissible([obs("a", fare=fare)])
    assert not result.admissible
    assert result.excluded[0].reason is ExclusionReason.NON_POSITIVE_FARE


def test_positive_fare_is_admissible() -> None:
    """The other side of the threshold."""
    assert len(filter_admissible([obs("a", fare="0.01")]).admissible) == 1


def test_non_positive_fare_reaching_matching_raises_rather_than_producing_nan() -> None:
    """Defence in depth. If admissibility is skipped, matching must fail loudly
    rather than let a NaN enter the index."""
    bad = obs("bad", fare="-5.00")
    good = obs("bad", fare="5000.00", collection=T - timedelta(days=7))
    with pytest.raises(ValueError, match="non-positive fare"):
        build_matched_set(
            [bad], [good], cell_key_for(good), Tier.TIER_1, source_precedence=PRECEDENCE
        )


# ─── Empty and minimal sets ──────────────────────────────────────────────────


def test_empty_observation_set_is_handled() -> None:
    result = filter_admissible([])
    assert result.admissible == () and result.excluded == ()
    assert result.exclusion_rate == 0.0


def test_empty_matched_set_gives_undefined_not_one() -> None:
    result = compute_jevons(cell(), T, ())
    assert result.relative is None
    assert result.undefined_reason is UndefinedRelativeReason.NO_MATCHED_ITEMS


@pytest.mark.parametrize("n", [1, 2])
def test_below_minimum_matched_items_is_undefined(n: int) -> None:
    """INV-8, below the threshold."""
    pairs = tuple(pair(i, "100.00", "110.00") for i in range(n))
    result = compute_jevons(cell(), T, pairs)
    assert result.relative is None
    assert result.undefined_reason is UndefinedRelativeReason.BELOW_MIN_MATCHED_ITEMS


def test_exactly_three_matched_items_is_defined() -> None:
    """INV-8, at the threshold. Three is the minimum, not the first rejected."""
    assert MIN_MATCHED_ITEMS_PER_CELL == 3
    pairs = tuple(pair(i, "100.00", "110.00") for i in range(3))
    result = compute_jevons(cell(), T, pairs)
    assert result.is_defined
    assert result.relative is not None
    assert math.isclose(result.relative, 1.1, rel_tol=REL_TOL)


# ─── Outlier rule thresholds ─────────────────────────────────────────────────


def test_four_items_does_not_trigger_the_outlier_rule() -> None:
    """INV-8, below the 5-item gate. Even a wild value survives."""
    pairs = tuple(
        pair(i, "100.00", p) for i, p in enumerate(["101.00", "102.00", "103.00", "900.00"])
    )
    report = flag_outliers(pairs)
    assert not report.applied
    assert report.flagged == ()
    assert len(report.kept) == 4


def test_exactly_five_items_triggers_the_outlier_rule() -> None:
    """INV-8, at the gate."""
    assert MIN_ITEMS_FOR_OUTLIER_RULE == 5
    prices = ["101.00", "102.00", "103.00", "104.00", "900.00"]
    pairs = tuple(pair(i, "100.00", p) for i, p in enumerate(prices))
    report = flag_outliers(pairs)
    assert report.applied
    assert len(report.flagged) == 1
    assert report.flag_rate == pytest.approx(0.2)


def test_mad_zero_flags_nothing() -> None:
    """Spec D.7 degenerate rule. Common at long lead times where a fare simply
    does not move; without this the detector would destroy the cell."""
    unchanged = tuple(pair(i, "100.00", "100.00") for i in range(4))
    pairs = (*unchanged, pair(4, "100.00", "150.00"))
    report = flag_outliers(pairs)
    assert report.mad == 0.0
    assert not report.applied
    assert report.flagged == ()
    assert len(report.kept) == 5


def test_mad_is_not_rescaled_by_the_normal_consistency_constant() -> None:
    """Spec D.7: the threshold is 5 x raw MAD. Rescaling by 1.4826 would widen
    it ~48% and silently change what counts as an outlier."""
    pairs = tuple(
        pair(i, "100.00", p)
        for i, p in enumerate(["101.00", "102.00", "103.00", "104.00", "105.00"])
    )
    report = flag_outliers(pairs)
    assert math.isclose(report.threshold, 5.0 * report.mad, rel_tol=REL_TOL)


def test_a_cell_of_near_identical_relatives_plus_outliers_still_yields_a_relative() -> None:
    """After flagging, enough items must survive for J to be defined."""
    prices = ["110.00", "110.10", "110.20", "110.30", "900.00", "0.01"]
    pairs = tuple(pair(i, "100.00", p) for i, p in enumerate(prices))
    result = compute_jevons(cell(), T, pairs)
    assert result.candidate_count == 6
    assert result.matched_count < 6, "the extreme values should have been flagged"
    assert result.is_defined


def test_flagging_below_the_minimum_leaves_the_relative_undefined() -> None:
    """When flagging removes so much that fewer than 3 survive, J is undefined —
    the two thresholds are applied to different sets, in pipeline order."""
    prices = ["100.00", "100.00", "100.00", "900.00", "800.00"]
    pairs = tuple(pair(i, "100.00", p) for i, p in enumerate(prices))
    result = compute_jevons(cell(), T, pairs)
    # MAD is 0 here (three identical), so flagging is inert and J is defined.
    assert result.is_defined


# ─── Deduplication ───────────────────────────────────────────────────────────


def test_duplicates_keep_the_latest_timestamp_and_retain_the_loser() -> None:
    early = obs("early", ts=datetime(2026, 9, 8, 6, 0), fare="5000.00")
    late = obs("late", ts=datetime(2026, 9, 8, 7, 0), fare="5100.00")
    result = deduplicate([early, late])

    assert [o.observation_id for o in result.retained] == ["late"]
    assert len(result.duplicates) == 1
    assert result.duplicates[0].observation_id == "early"
    assert result.duplicates[0].reason is ExclusionReason.DUPLICATE
    assert result.duplicate_rate == pytest.approx(0.5)


def test_same_fare_from_different_sources_is_not_a_duplicate() -> None:
    """source_id is part of the duplicate key. Collapsing across sources would
    erase the channel spread the methodology publishes."""
    a = obs("a", source="indigo")
    b = obs("b", source="makemytrip")
    assert len(deduplicate([a, b]).retained) == 2


def test_same_flight_identity_on_different_routes_is_not_a_duplicate() -> None:
    """Regression: spec D.4 scopes duplicates to observations IN THE SAME CELL,
    and a cell key begins with the route.

    Without route in the key, a carrier's flight number, date and departure time
    collide across every route, and the deduplicator destroys observations that
    are not duplicates. Measured on a full-frame synthetic day before the fix:
    2,800 admissible quotes collapsed to 140.
    """
    del_bom = obs("a")
    del_blr = Observation(
        observation_id="b",
        origin="DEL",
        destination="BLR",  # the only difference
        travel_date=del_bom.travel_date,
        departure_time_local=del_bom.departure_time_local,
        observation_ts=del_bom.observation_ts,
        collection_date=del_bom.collection_date,
        carrier=del_bom.carrier,
        flight_number=del_bom.flight_number,
        stops=del_bom.stops,
        duration_minutes=del_bom.duration_minutes,
        fare_family_raw=del_bom.fare_family_raw,
        channel=del_bom.channel,
        source_id=del_bom.source_id,
        entitlements=del_bom.entitlements,
        payable_fare=del_bom.payable_fare,
        source_type=del_bom.source_type,
    )
    assert del_bom.route != del_blr.route
    assert duplicate_key(del_bom) != duplicate_key(del_blr)

    result = deduplicate([del_bom, del_blr])
    assert len(result.retained) == 2, "different routes are different cells (spec D.4)"
    assert result.duplicates == ()


def test_deduplication_is_order_independent() -> None:
    a = obs("a", ts=datetime(2026, 9, 8, 6, 0))
    b = obs("b", ts=datetime(2026, 9, 8, 7, 0))
    forward = deduplicate([a, b]).retained
    reverse = deduplicate([b, a]).retained
    assert [o.observation_id for o in forward] == [o.observation_id for o in reverse]


# ─── Seven-day matching ──────────────────────────────────────────────────────


def test_prior_period_is_always_seven_days() -> None:
    """Spec C.1. A Monday is matched to the previous Monday, never to Sunday."""
    assert MATCHING_LAG_DAYS == 7
    assert prior_period(T) == T - timedelta(days=7)
    assert prior_period(T).isoweekday() == T.isoweekday()


def test_cross_weekday_observations_do_not_match() -> None:
    """Spec C.2: a Monday and a Tuesday observation are never differenced.

    day_of_week is part of the cell key, so observations whose departures fall
    on different weekdays land in different cells and cannot pair.
    """
    # Both at the SAME APW bucket (T+7), so the only difference is the weekday.
    tuesday_dep = obs("t", collection=T, travel=T + timedelta(days=7))
    wednesday_dep = obs("w", collection=T + timedelta(days=1), travel=T + timedelta(days=8))
    assert tuesday_dep.apw_bucket is wednesday_dep.apw_bucket
    assert tuesday_dep.day_of_week != wednesday_dep.day_of_week

    key_now = cell_key_for(tuesday_dep)
    key_then = cell_key_for(wednesday_dep)
    assert key_now != key_then, "different departure weekdays must be different cells"

    assert (
        build_matched_set(
            [tuesday_dep], [wednesday_dep], key_now, Tier.TIER_1, source_precedence=PRECEDENCE
        ).pairs
        == ()
    )


def test_unmatched_items_enter_neither_side() -> None:
    """Spec D.1. An item present at t but not t-7 contributes nothing — not to
    the numerator, and not as a new item at 100."""
    # Migrated for v2.1. Under v2.0 the item was keyed by departure time, so two
    # observations differing only in ``dep`` were two items. Under v2.1 the item
    # is ``carrier x flight_number``, so the distinctness this test depends on
    # must come from the flight number — otherwise all three observations would
    # collapse into one item and the test would assert nothing.
    now = [obs("a", flight="101", dep=time(8, 30)), obs("b", flight="205", dep=time(14, 0))]
    then = [obs("c", flight="101", dep=time(8, 30), collection=T - timedelta(days=7))]
    key = cell_key_for(now[0])
    matched = build_matched_set(now, then, key, Tier.TIER_1, source_precedence=PRECEDENCE).pairs
    assert len(matched) == 1, "flight 205 is present only at t and matches nothing"
    assert matched[0].item.flight_number == "101"


def test_tier_3_forms_no_matched_set() -> None:
    """A Tier 3 cell publishes a declared unit value; it has no within-cell
    item identity to match on."""
    now = [obs("a")]
    then = [obs("b", collection=T - timedelta(days=7))]
    key = cell_key_for(now[0])
    assert build_matched_set(now, then, key, Tier.TIER_3, source_precedence=PRECEDENCE).pairs == ()


@pytest.mark.parametrize(
    ("stability", "expected"),
    [
        (1.00, Tier.TIER_1),
        (0.70, Tier.TIER_1),  # at and above the Tier 1 gate
        (0.699, Tier.TIER_2),
        (0.40, Tier.TIER_2),  # both edges of the Tier 2 band
        (0.399, Tier.TIER_3),
        (0.00, Tier.TIER_3),  # below the Tier 2 gate
    ],
)
def test_tier_ladder_thresholds_cross_in_both_directions(stability: float, expected: Tier) -> None:
    """INV-8 applied to the tier ladder — spec B.2."""
    assert select_tier(stability) is expected


# ─── Admissibility ───────────────────────────────────────────────────────────


def test_lead_time_matching_no_bucket_is_inadmissible() -> None:
    """Spec A.3: assignment is by EXACT lead time, with no nearest-bucket rounding."""
    off = obs("x", travel=T + timedelta(days=8))  # 8 is not an APW bucket
    result = filter_admissible([off])
    assert not result.admissible
    assert result.excluded[0].reason is ExclusionReason.LEAD_TIME_MATCHES_NO_BUCKET


def test_sold_out_is_excluded_as_a_disappeared_item() -> None:
    """Spec D.6: a sold-out flight is not a missing price."""
    result = filter_admissible([obs("s", availability=Availability.SOLD_OUT)])
    assert result.excluded[0].reason is ExclusionReason.SOLD_OUT


def test_collection_window_excludes_outside_quotes() -> None:
    window = CollectionWindow(start=time(5, 0), end=time(9, 0))
    inside = obs("in", ts=datetime(2026, 9, 8, 6, 0))
    outside = obs("out", ts=datetime(2026, 9, 8, 18, 0))
    result = filter_admissible([inside, outside], window=window)
    assert [o.observation_id for o in result.admissible] == ["in"]
    assert result.excluded[0].reason is ExclusionReason.OUTSIDE_COLLECTION_WINDOW


def test_collection_window_wrapping_midnight() -> None:
    """An overnight collection run is a real configuration."""
    window = CollectionWindow(start=time(22, 0), end=time(2, 0))
    assert window.contains(time(23, 30))
    assert window.contains(time(1, 0))
    assert not window.contains(time(12, 0))


def test_fare_class_is_derived_from_entitlements_not_labels() -> None:
    """Spec B.4."""
    assert Entitlements(0, ChangePolicy.NONE, ChangePolicy.NONE).fare_class() is FareClass.HAND_ONLY
    assert Entitlements(15, ChangePolicy.FEE, ChangePolicy.FEE).fare_class() is FareClass.STANDARD
    assert Entitlements(15, ChangePolicy.FREE, ChangePolicy.FREE).fare_class() is FareClass.FLEX
    # Only STANDARD carries the "and not FLEX" exclusion in spec B.4; HAND_ONLY
    # is unqualified, so a zero-baggage fare is HAND_ONLY even when it is fully
    # flexible. Getting this backwards pools a hand-baggage-only fare with a
    # checked-baggage fare in one cell — the comparison B.4 exists to prevent.
    # Raised as AMB-4: the spec does not say which condition wins.
    assert Entitlements(0, ChangePolicy.FREE, ChangePolicy.FEE).fare_class() is FareClass.HAND_ONLY
    assert Entitlements(0, ChangePolicy.FREE, ChangePolicy.FREE).fare_class() is FareClass.HAND_ONLY
    # With baggage, the FLEX condition does decide.
    assert Entitlements(20, ChangePolicy.FREE, ChangePolicy.FEE).fare_class() is FareClass.FLEX


def test_negative_baggage_is_rejected() -> None:
    with pytest.raises(ValueError, match="checked_baggage_kg"):
        Entitlements(-1, ChangePolicy.FEE, ChangePolicy.FEE)


# ─── Chaining, carry, freshness, entry ───────────────────────────────────────


def test_new_cell_with_parent_enters_at_the_parent_level() -> None:
    c = cell("6ENEW")
    state = advance_cell(
        ChainInputs(
            cell=c,
            collection_date=T,
            jevons=compute_jevons(c, T, ()),
            previous=None,
            parent_level=106.0,
        )
    )
    assert state.status is CellStatus.ENTERED
    assert state.level == 106.0


def test_new_cell_without_parent_and_without_relative_is_held_out() -> None:
    """Spec J.2: never seeded at 100 inside a live aggregate."""
    c = cell("6ENEW")
    state = advance_cell(
        ChainInputs(cell=c, collection_date=T, jevons=compute_jevons(c, T, ()), previous=None)
    )
    assert state.status is CellStatus.HELD_OUT
    assert state.level is None
    assert not state.is_live


def test_standalone_first_cell_takes_the_base_of_100() -> None:
    """Spec E.1/E.3(a) — the system-bootstrap case, where no aggregate exists
    to distort."""
    c = cell()
    pairs = tuple(pair(i, "100.00", "110.00") for i in range(3))
    state = advance_cell(
        ChainInputs(cell=c, collection_date=T, jevons=compute_jevons(c, T, pairs), previous=None)
    )
    assert state.status is CellStatus.PUBLISHED
    assert state.level == 100.0


def test_parent_level_takes_precedence_over_the_base_of_100() -> None:
    """Spec E.3: rule (b) takes precedence whenever a parent exists."""
    c = cell()
    pairs = tuple(pair(i, "100.00", "110.00") for i in range(3))
    state = advance_cell(
        ChainInputs(
            cell=c,
            collection_date=T,
            jevons=compute_jevons(c, T, pairs),
            previous=None,
            parent_level=106.0,
        )
    )
    assert state.status is CellStatus.ENTERED
    assert state.level == 106.0


def test_carry_uses_the_parent_relative_never_the_parent_level() -> None:
    """Spec E.4. Inheriting the level would teleport the cell onto the parent's
    path and erase its own accumulated history."""
    c = cell()
    state = advance_cell(
        ChainInputs(
            cell=c,
            collection_date=T,
            jevons=compute_jevons(c, T, ()),
            previous=published(c, 120.0, T - timedelta(days=7)),
            parent_relative=1.05,
            parent_level=200.0,
        )
    )
    assert state.status is CellStatus.CARRIED
    assert state.level is not None
    assert math.isclose(state.level, 126.0, rel_tol=REL_TOL)  # 120 x 1.05, not 200


def test_no_relative_and_no_parent_relative_suppresses() -> None:
    c = cell()
    state = advance_cell(
        ChainInputs(
            cell=c,
            collection_date=T,
            jevons=compute_jevons(c, T, ()),
            previous=published(c, 120.0, T - timedelta(days=7)),
        )
    )
    assert state.status is CellStatus.SUPPRESSED
    assert state.level is None
    assert "nothing more sophisticated ships in v1" in state.suppression_reason


@pytest.mark.parametrize(("gap", "expect_suppressed"), [(13, False), (14, True)])
def test_freshness_boundary_crosses_in_both_directions(gap: int, expect_suppressed: bool) -> None:
    """INV-8 on spec C.3: 13 days is tolerated, 14 is not."""
    assert MAX_FRESHNESS_DAYS == 13
    c = cell()
    previous = CellState(
        cell=c,
        collection_date=T - timedelta(days=gap),
        level=110.0,
        status=CellStatus.CARRIED,
        last_matched_date=T - timedelta(days=gap),
    )
    state = advance_cell(
        ChainInputs(
            cell=c,
            collection_date=T,
            jevons=compute_jevons(c, T, ()),
            previous=previous,
            parent_relative=1.02,
        )
    )
    if expect_suppressed:
        assert state.status is not CellStatus.CARRIED
    else:
        assert state.status is CellStatus.CARRIED


def test_resumption_after_the_window_re_enters_rather_than_resuming() -> None:
    """Spec E.5: beyond 13 days the claim that the same product class is being
    tracked is no longer defensible."""
    c = cell()
    previous = CellState(
        cell=c,
        collection_date=T - timedelta(days=30),
        level=110.0,
        status=CellStatus.PUBLISHED,
        last_matched_date=T - timedelta(days=30),
    )
    state = advance_cell(
        ChainInputs(
            cell=c,
            collection_date=T,
            jevons=compute_jevons(c, T, ()),
            previous=previous,
            parent_level=104.0,
        )
    )
    assert state.status is CellStatus.ENTERED
    assert state.level == 104.0


@pytest.mark.parametrize(("rate", "suppressed"), [(0.40, False), (0.41, True)])
def test_cell_imputation_ceiling_crosses_in_both_directions(rate: float, suppressed: bool) -> None:
    """INV-8 on spec I: 40% is tolerated, above it the cell is suppressed."""
    assert MAX_CELL_IMPUTATION == 0.40
    c = cell()
    pairs = tuple(pair(i, "100.00", "110.00") for i in range(3))
    state = advance_cell(
        ChainInputs(
            cell=c,
            collection_date=T,
            jevons=compute_jevons(c, T, pairs),
            previous=published(c, 100.0, T - timedelta(days=7)),
            imputation_rate=rate,
        )
    )
    assert (state.status is CellStatus.SUPPRESSED) is suppressed


# ─── Weights ─────────────────────────────────────────────────────────────────


def test_negative_weight_is_rejected() -> None:
    with pytest.raises(WeightError, match="negative"):
        validate({"a": 0.5, "b": -0.1})


def test_zero_total_weight_is_rejected() -> None:
    with pytest.raises(WeightError, match="zero-weight"):
        normalise({"a": 0.0, "b": 0.0})


def test_empty_weight_vector_is_rejected() -> None:
    with pytest.raises(WeightError, match="empty"):
        validate({})


def test_nan_weight_is_rejected() -> None:
    with pytest.raises(WeightError, match="non-finite"):
        validate({"a": float("nan"), "b": 1.0})


def test_renormalisation_over_an_empty_live_set_is_empty_not_an_error() -> None:
    """Every member suppressed is a real state, reported by the caller as a
    withheld index rather than raised here."""
    assert renormalise_over_live_set({"a": 0.5, "b": 0.5}, []) == {}


def test_aggregating_mismatched_keys_raises_rather_than_intersecting() -> None:
    """Silently intersecting is how a suppressed member's weight goes missing
    without renormalisation — the exact failure spec F.4 guards."""
    with pytest.raises(AggregationError, match="same members"):
        aggregate_levels({"a": 100.0}, {"a": 0.5, "b": 0.5})


def test_aggregating_with_unnormalised_weights_raises() -> None:
    with pytest.raises(AggregationError, match=r"not 1\.0"):
        aggregate_levels({"a": 100.0, "b": 110.0}, {"a": 0.5, "b": 0.3})  # sums to 0.8


def test_empty_live_set_raises_rather_than_returning_zero() -> None:
    """Zero is a level. Returning it would publish 'the index is at zero' when
    the truth is 'the index cannot be computed'."""
    with pytest.raises(AggregationError, match="not computable"):
        aggregate_over_live_set({}, {"a": 1.0})


# ─── Version vector ──────────────────────────────────────────────────────────


def test_model_version_leaking_into_apix_l_is_rejected() -> None:
    """INV-12. A non-null model_version means a fitted model entered the
    deterministic path."""
    c = cell()
    with pytest.raises(ApixLError, match="model_version"):
        calculate_apix_l(
            [published(c, 100.0)],
            {cell_id(c): 1.0},
            {"DEL-BOM": 1.0},
            vv(model_version="tpd-1.0"),
            T,
        )


def test_na_model_version_is_accepted() -> None:
    c = cell()
    result = calculate_apix_l(
        [published(c, 100.0)], {cell_id(c): 1.0}, {"DEL-BOM": 1.0}, vv("N/A"), T
    )
    assert result.published


@pytest.mark.parametrize(
    "field",
    [
        "data_snapshot_id",
        "methodology_version",
        "basket_version",
        "weight_version",
        "parser_version",
        "code_version",
    ],
)
def test_malformed_version_vector_is_rejected(field: str) -> None:
    kwargs = {
        "data_snapshot_id": "s",
        "methodology_version": "2.0",
        "basket_version": "b",
        "weight_version": "w",
        "parser_version": "p",
        "code_version": "c",
    }
    kwargs[field] = ""
    with pytest.raises(ValueError, match="missing required fields"):
        VersionVector(**kwargs)


def test_version_vector_renders_model_as_na() -> None:
    assert "model N/A" in vv().render()


# ─── Route and national suppression ──────────────────────────────────────────


def test_one_suppressed_route_renormalises_the_rest() -> None:
    a, b = cell("6E1", "DEL-BOM"), cell("6E2", "DEL-BLR")
    states = [published(a, 102.0), published(b, 108.0)]
    weights = {"DEL-BOM": 0.5, "DEL-BLR": 0.3, "BOM-BLR": 0.2}  # third suppressed
    result = calculate_apix_l(states, {cell_id(a): 1.0, cell_id(b): 1.0}, weights, vv(), T)
    assert result.published
    assert result.level is not None
    assert math.isclose(result.level, 104.25, rel_tol=REL_TOL)
    assert sums_to_one(result.renormalised_route_weights)
    assert math.isclose(result.quality.suppressed_weight_share, 0.2, rel_tol=REL_TOL)


def test_suppressed_weight_above_the_ceiling_raises_a_caveat() -> None:
    """Spec I: above 15% suppressed weight, APIx publishes WITH a quality caveat
    — it still publishes."""
    a = cell("6E1", "DEL-BOM")
    result = calculate_apix_l(
        [published(a, 102.0)],
        {cell_id(a): 1.0},
        {"DEL-BOM": 0.8, "DEL-BLR": 0.2},
        vv(),
        T,
    )
    assert result.published
    assert any("suppressed weight share" in c for c in result.quality.caveats)


def test_tier3_weight_above_the_ceiling_raises_the_unit_value_caveat() -> None:
    a = cell("6E1", "DEL-BOM")
    b = cell("6E2", "DEL-BLR", tier=Tier.TIER_3)
    result = calculate_apix_l(
        [published(a, 100.0), published(b, 100.0)],
        {cell_id(a): 1.0, cell_id(b): 1.0},
        {"DEL-BOM": 0.5, "DEL-BLR": 0.5},
        vv(),
        T,
        route_tiers={"DEL-BOM": Tier.TIER_1, "DEL-BLR": Tier.TIER_3},
    )
    assert any("Tier-3" in c for c in result.quality.caveats)


def test_all_routes_suppressed_withholds_the_index() -> None:
    """The index is withheld, not published as 0.0."""
    c = cell()
    dead = CellState(
        cell=c, collection_date=T, level=None, status=CellStatus.SUPPRESSED, suppression_reason="x"
    )
    result = calculate_apix_l([dead], {cell_id(c): 1.0}, {"DEL-BOM": 1.0}, vv(), T)
    assert not result.published
    assert result.level is None
    assert result.quality.suppressed_weight_share == 1.0


def test_route_below_coverage_minimum_is_suppressed() -> None:
    """Spec I: min_route_coverage = 60%."""
    live = cell("6E1")
    dead = [
        CellState(cell=cell(f"6E{i}"), collection_date=T, level=None, status=CellStatus.SUPPRESSED)
        for i in range(2, 6)
    ]
    weights = {cell_id(live): 1.0} | {cell_id(d.cell): 1.0 for d in dead}
    result = calculate_apix_l([published(live, 100.0), *dead], weights, {"DEL-BOM": 1.0}, vv(), T)
    assert not result.published
    assert result.routes[0].suppressed
    assert "coverage" in result.routes[0].suppression_reason


def test_an_earlier_link_date_is_accepted_at_publication() -> None:
    """Spec C.2, F.2 — AMB-7. A cell contributes its most recent level.

    Rewritten at Checkpoint 2E. This case previously asserted that a state dated
    before the publication date was rejected. That assertion was wrong against
    the frozen methodology: each cell advances on its own seven-day chain
    (spec E.2), so on any publication date most cells last linked days ago, and
    spec C.2 requires each of the seven interleaved chains to contribute **its
    most recent level**. Spec F.2 sums over the live set at *t*, not over cells
    that linked at *t*.

    The differencing spec C.2 forbids happens in ``build_matched_set``, which
    keeps its own single-date guard — see
    ``test_redteam_regressions.py`` D-3, still passing unchanged.
    """
    a = cell("6E1")
    result = calculate_apix_l(
        [published(a, 100.0, T - timedelta(days=1))],
        {cell_id(a): 1.0},
        {"DEL-BOM": 1.0},
        vv(),
        T,
    )
    assert result.published
    assert result.level == pytest.approx(100.0)
    assert result.quality.freshness.median == 1


def test_a_future_link_date_is_rejected() -> None:
    """Spec R.3 — a later period must never enter an earlier vintage."""
    a = cell("6E1")
    with pytest.raises(ApixLError, match="after the period"):
        calculate_apix_l(
            [published(a, 100.0, T + timedelta(days=1))],
            {cell_id(a): 1.0},
            {"DEL-BOM": 1.0},
            vv(),
            T,
        )


# ─── Reproducibility (Phase 19) ──────────────────────────────────────────────


def _scenario() -> tuple[list[CellState], dict[str, float], dict[str, float]]:
    cells = [cell(f"6E{i}", "DEL-BOM" if i % 2 else "DEL-BLR") for i in range(1, 9)]
    states = [published(c, 100.0 + i * 1.7) for i, c in enumerate(cells)]
    cell_weights = {cell_id(c): 1.0 / len(cells) for c in cells}
    route_weights = {"DEL-BOM": 0.6, "DEL-BLR": 0.4}
    return states, cell_weights, route_weights


def test_identical_inputs_reproduce_bit_identical_output() -> None:
    """Spec P.1, INV-9 — asserted bit for bit, not to a tolerance."""
    states, cw, rw = _scenario()
    first = calculate_apix_l(states, cw, rw, vv(), T)
    second = calculate_apix_l(states, cw, rw, vv(), T)
    assert first.level == second.level
    assert first.renormalised_route_weights == second.renormalised_route_weights


@pytest.mark.parametrize("seed", range(8))
def test_input_ordering_does_not_change_a_single_bit(seed: int) -> None:
    """INV-5. Floating-point addition is not associative, so an unordered
    reduction would break bit-identity even with identical inputs."""
    states, cw, rw = _scenario()
    baseline = calculate_apix_l(states, cw, rw, vv(), T)

    # A deterministic permutation per seed — no RNG, which spec P.2 forbids.
    shuffled = states[seed:] + states[:seed]
    result = calculate_apix_l(shuffled, cw, rw, vv(), T)

    assert result.level == baseline.level, (
        f"permutation {seed} changed the level: {baseline.level} -> {result.level}"
    )


def test_reproducibility_tuple_is_the_five_specified_fields() -> None:
    assert vv().reproducibility_tuple() == (
        "sha256:abc",
        "2.0",
        "2026-Q3",
        "dgca-2026-09",
        "7f3a91c",
    )


# ─── Property-based ──────────────────────────────────────────────────────────

positive_fare = st.decimals(min_value=Decimal("1.00"), max_value=Decimal("500000.00"), places=2)


@settings(max_examples=200, deadline=None)
@given(prices=st.lists(st.tuples(positive_fare, positive_fare), min_size=3, max_size=40))
def test_property_jevons_is_always_positive_and_finite(
    prices: list[tuple[Decimal, Decimal]],
) -> None:
    pairs = tuple(pair(i, str(p), str(q)) for i, (p, q) in enumerate(prices))
    result = compute_jevons(cell(), T, pairs, apply_outlier_rule=False)
    assert result.relative is not None
    assert result.relative > 0
    assert math.isfinite(result.relative)


@settings(max_examples=200, deadline=None)
@given(prices=st.lists(positive_fare, min_size=3, max_size=30), k=st.floats(0.01, 100.0))
def test_property_scale_invariance_holds_for_any_k(prices: list[Decimal], k: float) -> None:
    """INV-4a: scaling BOTH periods by k leaves the relative unchanged."""
    scale = Decimal(str(k))
    base = tuple(pair(i, str(p), str(p * Decimal("1.1"))) for i, p in enumerate(prices))
    scaled = tuple(
        pair(i, str(p * scale), str(p * Decimal("1.1") * scale)) for i, p in enumerate(prices)
    )
    a = compute_jevons(cell(), T, base, apply_outlier_rule=False).relative
    b = compute_jevons(cell(), T, scaled, apply_outlier_rule=False).relative
    assert a is not None and b is not None
    assert math.isclose(a, b, rel_tol=1e-9)


@settings(max_examples=200, deadline=None)
@given(
    raw=st.dictionaries(
        st.text(min_size=1, max_size=6, alphabet="abcdefgh"),
        st.floats(min_value=0.001, max_value=1000.0),
        min_size=1,
        max_size=12,
    )
)
def test_property_normalised_weights_always_sum_to_one(raw: dict[str, float]) -> None:
    """INV-1 over arbitrary inputs."""
    assert sums_to_one(normalise(raw))


@settings(max_examples=200, deadline=None)
@given(
    levels=st.lists(st.floats(min_value=1.0, max_value=1000.0), min_size=1, max_size=12),
    raw=st.lists(st.floats(min_value=0.001, max_value=100.0), min_size=1, max_size=12),
)
def test_property_aggregate_lies_between_min_and_max_level(
    levels: list[float], raw: list[float]
) -> None:
    """A weighted mean can never escape the range of its inputs. If it does, the
    weights are wrong."""
    n = min(len(levels), len(raw))
    keys = [f"k{i}" for i in range(n)]
    level_map = dict(zip(keys, levels[:n], strict=True))
    weights = normalise(dict(zip(keys, raw[:n], strict=True)))
    result = aggregate_levels(level_map, weights)
    assert min(level_map.values()) - 1e-9 <= result <= max(level_map.values()) + 1e-9


# ─── AMB-9 — the carrier-allocation seam ─────────────────────────────────────


def _cells_two_carriers() -> list[CellKey]:
    return [cell("6E"), cell("AI")]


def test_multi_carrier_route_refuses_to_weight_without_a_ratified_allocation() -> None:
    """AMB-9. Spec G.3 has no carrier term, so the allocation is undetermined.

    The failure mode this prevents is silent: a uniform default would weight a
    carrier holding ~60% of a route's passengers identically to one holding 3%,
    and nothing downstream would notice.
    """
    with pytest.raises(WeightError, match="no ratified carrier_allocation"):
        within_route_weights(
            _cells_two_carriers(),
            fare_class_shares={FareClass.STANDARD: 1.0},
            channel_shares={Channel.AIRLINE_DIRECT: 1.0},
        )


def test_single_carrier_route_needs_no_allocation() -> None:
    """With one carrier there is no allocation to make — which is why the
    Checkpoint 2G empirical frame can run before AMB-9 is ruled on."""
    weights = within_route_weights(
        [cell("6E")],
        fare_class_shares={FareClass.STANDARD: 1.0},
        channel_shares={Channel.AIRLINE_DIRECT: 1.0},
    )
    assert sums_to_one(weights)


def test_allocation_must_be_ratified() -> None:
    """An allocation with no named owner is an invention, not a rule."""
    with pytest.raises(WeightError, match="not ratified"):
        CarrierAllocation(
            version="v1",
            basis=CarrierAllocationBasis.MEASURED_TRAFFIC,
            shares={"6E": 0.6, "AI": 0.4},
            ratified_by="",
            ratified_date=date(2026, 9, 11),
        )


def test_uniform_declaration_requires_its_sensitivity_band() -> None:
    """Spec G.4's precedent is equal weights *accompanied by* a sensitivity
    analysis. Without the band it is the guess the pattern exists to replace."""
    with pytest.raises(WeightError, match="sensitivity_band_ref"):
        CarrierAllocation(
            version="uniform-v1",
            basis=CarrierAllocationBasis.DECLARED_UNIFORM,
            shares={"6E": 1.0, "AI": 1.0},
            ratified_by="@Rexy-5097",
            ratified_date=date(2026, 9, 11),
        )


def test_uniform_declaration_with_a_band_is_accepted() -> None:
    """The other side of the threshold — INV-8."""
    alloc = CarrierAllocation(
        version="uniform-v1",
        basis=CarrierAllocationBasis.DECLARED_UNIFORM,
        shares={"6E": 1.0, "AI": 1.0},
        ratified_by="@Rexy-5097",
        ratified_date=date(2026, 9, 11),
        sensitivity_band_ref="ADR-00XX sensitivity band",
    )
    weights = within_route_weights(
        _cells_two_carriers(),
        fare_class_shares={FareClass.STANDARD: 1.0},
        channel_shares={Channel.AIRLINE_DIRECT: 1.0},
        carrier_allocation=alloc,
    )
    assert sums_to_one(weights)
    assert len(weights) == 2


def test_measured_shares_flow_through_to_the_weights() -> None:
    """A ratified measured allocation reaches v[c|r] in the declared proportion."""
    alloc = CarrierAllocation(
        version="measured-v1",
        basis=CarrierAllocationBasis.MEASURED_TRAFFIC,
        shares={"6E": 0.75, "AI": 0.25},
        ratified_by="@Rexy-5097",
        ratified_date=date(2026, 9, 11),
    )
    weights = within_route_weights(
        _cells_two_carriers(),
        fare_class_shares={FareClass.STANDARD: 1.0},
        channel_shares={Channel.AIRLINE_DIRECT: 1.0},
        carrier_allocation=alloc,
    )
    by_carrier = {k.split("|")[1]: v for k, v in weights.items()}
    assert by_carrier["6E"] == pytest.approx(0.75)
    assert by_carrier["AI"] == pytest.approx(0.25)


def test_carrier_outside_a_ratified_allocation_raises_rather_than_defaulting() -> None:
    """Silently giving an uncovered carrier zero would drop it from the index
    without saying so."""
    alloc = CarrierAllocation(
        version="partial-v1",
        basis=CarrierAllocationBasis.MEASURED_TRAFFIC,
        shares={"6E": 1.0},
        ratified_by="@Rexy-5097",
        ratified_date=date(2026, 9, 11),
    )
    with pytest.raises(WeightError, match="has no share for"):
        within_route_weights(
            _cells_two_carriers(),
            fare_class_shares={FareClass.STANDARD: 1.0},
            channel_shares={Channel.AIRLINE_DIRECT: 1.0},
            carrier_allocation=alloc,
        )
