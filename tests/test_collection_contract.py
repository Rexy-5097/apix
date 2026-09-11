"""The collection contract — spec A.4, B.6, H.1, and the AMB-8 input.

These tests guard three things the index cannot recover from if they go wrong at
collection time, because none of them can be reconstructed afterwards:

1. **A collector failure must never read as an absent fare.** If "the site
   blocked us" and "no service was scheduled" collapse into the same empty
   result, spec I's coverage denominator is undefined however long we collect.
2. **An unrendered fare component must never read as zero.** ``None`` says we
   could not see it; ``0`` asserts the charge does not exist.
3. **An unknown source group must never read as independent.** Spec B.6 is
   explicit that treating two resellers of one feed as independent *"would
   understate correlation and inflate effective N"*.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from apix.schemas.collection import (
    CollectionAttempt,
    CollectionRun,
    exclusion_rate,
    has_stop_signal,
)
from apix.schemas.enums import (
    APWBucket,
    Availability,
    ChangePolicy,
    Channel,
    CollectionOutcome,
    FareClass,
    SourceType,
)
from apix.schemas.observation import NO_BREAKDOWN, Entitlements, FareBreakdown, Observation

T = date(2026, 9, 12)
WINDOW_START = datetime(2026, 9, 12, 21, 0)
WINDOW_END = datetime(2026, 9, 12, 22, 0)


def run(**kw: object) -> CollectionRun:
    base: dict[str, object] = {
        "run_id": "run-2026-09-12-01",
        "collection_date": T,
        "started_ts": WINDOW_START,
        "collection_window_start": WINDOW_START,
        "collection_window_end": WINDOW_END,
        "source_precedence_version": "src-v1",
        "basket_version": "2026-Q3",
        "parser_version": "1.0",
        "collector_version": "abc1234",
    }
    base.update(kw)
    return CollectionRun(**base)  # type: ignore[arg-type]


def attempt(outcome: CollectionOutcome, **kw: object) -> CollectionAttempt:
    base: dict[str, object] = {
        "attempt_id": f"att-{outcome.value}",
        "run_id": "run-2026-09-12-01",
        "collection_date": T,
        "attempt_ts": WINDOW_START,
        "source_id": "indigo-direct",
        "channel": Channel.AIRLINE_DIRECT,
        "source_type": SourceType.LIVE_SCRAPE,
        "origin": "DEL",
        "destination": "BOM",
        "travel_date": T + timedelta(days=7),
        "outcome": outcome,
    }
    base.update(kw)
    return CollectionAttempt(**base)  # type: ignore[arg-type]


def observation(**kw: object) -> Observation:
    base: dict[str, object] = {
        "observation_id": "o1",
        "origin": "DEL",
        "destination": "BOM",
        "travel_date": T + timedelta(days=7),
        "departure_time_local": time(6, 10),
        "observation_ts": WINDOW_START,
        "collection_date": T,
        "carrier": "6E",
        "flight_number": "2045",
        "stops": 0,
        "duration_minutes": 125,
        "fare_family_raw": "SAVER",
        "channel": Channel.AIRLINE_DIRECT,
        "source_id": "indigo-direct",
        "entitlements": Entitlements(15, ChangePolicy.FEE, ChangePolicy.FEE),
        "payable_fare": Decimal("5432.00"),
        "source_type": SourceType.LIVE_SCRAPE,
    }
    base.update(kw)
    return Observation(**base)  # type: ignore[arg-type]


# ─── The outcome partition — spec H.1 ────────────────────────────────────────


def test_only_no_flight_leaves_the_coverage_denominator() -> None:
    """Spec H.1 — *"No flight … Cell not expected; excluded from denominators
    of coverage."* Every other absence keeps the cell in the denominator."""
    excluded = {o for o in CollectionOutcome if o.excludes_cell_from_expectation}
    assert excluded == {CollectionOutcome.NO_FLIGHT}


def test_every_outcome_is_classified_exactly_once() -> None:
    """An exhaustive partition, so a new outcome cannot be added unclassified.

    This is the test that matters for AMB-8. If someone adds a sixth failure
    mode and forgets to say whether it is the market's fault or ours, the
    coverage denominator silently acquires a new meaning. This fails instead.
    """
    for outcome in CollectionOutcome:
        buckets = [
            outcome is CollectionOutcome.SUCCESS,
            outcome.is_market_fact,
            outcome.is_collector_failure,
        ]
        assert sum(buckets) == 1, (
            f"{outcome.value} is in {sum(buckets)} classes; every outcome must be "
            "exactly one of SUCCESS, a market fact, or our failure"
        )


def test_collector_failures_are_named() -> None:
    """The three absences that are ours, not the market's."""
    ours = {o for o in CollectionOutcome if o.is_collector_failure}
    assert ours == {
        CollectionOutcome.SOURCE_UNAVAILABLE,
        CollectionOutcome.PARSER_FAILURE,
        CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP,
    }


def test_access_challenge_is_the_only_stop_signal() -> None:
    """An access challenge is a stop signal, never an obstacle to route around."""
    stops = {o for o in CollectionOutcome if o.is_stop_signal}
    assert stops == {CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP}
    assert CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP.is_collector_failure


def test_a_blocked_attempt_is_never_an_absent_fare() -> None:
    """The headline invariant of this module.

    A blocked collector keeps its cell in the denominator AND is attributed to
    us. Reading it as "no quote available" would understate coverage loss and
    make our own outage look like a thin market.
    """
    blocked = attempt(CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP)
    no_flight = attempt(CollectionOutcome.NO_FLIGHT)

    assert blocked.counts_toward_expected_cells
    assert blocked.is_coverage_loss_we_caused

    assert not no_flight.counts_toward_expected_cells
    assert not no_flight.is_coverage_loss_we_caused


# ─── Attempt integrity ───────────────────────────────────────────────────────


def test_success_with_zero_quotes_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one quote"):
        attempt(CollectionOutcome.SUCCESS, quotes_parsed=0)


def test_failure_claiming_quotes_is_rejected() -> None:
    with pytest.raises(ValueError, match="parsed quotes"):
        attempt(CollectionOutcome.PARSER_FAILURE, quotes_parsed=3, observation_ids=("a", "b", "c"))


def test_provenance_must_be_exact() -> None:
    """``observation_ids`` and ``quotes_parsed`` cannot disagree."""
    with pytest.raises(ValueError, match="provenance must be exact"):
        attempt(CollectionOutcome.SUCCESS, quotes_parsed=2, observation_ids=("a",))


def test_a_valid_success_carries_its_provenance() -> None:
    a = attempt(CollectionOutcome.SUCCESS, quotes_parsed=2, observation_ids=("o1", "o2"))
    assert a.route == "DEL-BOM"
    assert a.lead_time_days == 7
    assert a.apw_bucket is APWBucket.T_PLUS_7


def test_attempt_off_bucket_is_still_recorded() -> None:
    """Spec A.3 assigns by exact lead time. An off-bucket attempt cannot feed the
    index, but it happened, and the exclusion rate stays honest only if we say so."""
    a = attempt(
        CollectionOutcome.SUCCESS,
        quotes_parsed=1,
        observation_ids=("o1",),
        travel_date=T + timedelta(days=8),
    )
    assert a.lead_time_days == 8
    assert a.apw_bucket is None


# ─── Exclusion rate and stop signals — spec H.1 ──────────────────────────────


def test_exclusion_rate_counts_only_our_failures() -> None:
    """Market absence is not an exclusion.

    A correctly specified basket that includes a route a carrier does not serve
    will produce NO_FLIGHT every day. Counting that as an exclusion would make a
    healthy collector look broken.
    """
    attempts = [
        attempt(CollectionOutcome.SUCCESS, quotes_parsed=1, observation_ids=("o1",)),
        attempt(CollectionOutcome.NO_FLIGHT),
        attempt(CollectionOutcome.PARSER_FAILURE),
        attempt(CollectionOutcome.SOURCE_UNAVAILABLE),
    ]
    assert exclusion_rate(attempts) == pytest.approx(0.5)
    assert exclusion_rate([]) == 0.0


def test_stop_signal_is_detected_across_a_run() -> None:
    clean = [attempt(CollectionOutcome.NO_FLIGHT), attempt(CollectionOutcome.TECHNICAL_FAILURE)]
    assert not has_stop_signal(clean)
    assert has_stop_signal([*clean, attempt(CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP)])


# ─── Run identity and the spec A.5 window ────────────────────────────────────


def test_run_requires_every_reproducibility_identifier() -> None:
    with pytest.raises(ValueError, match="missing required identifiers"):
        run(parser_version="")


def test_run_rejects_an_inverted_window() -> None:
    with pytest.raises(ValueError, match="must be after"):
        run(collection_window_end=WINDOW_START - timedelta(hours=1))


def test_window_membership_is_inclusive_at_both_ends() -> None:
    """Spec A.5 — quotes outside the window are flagged and excluded. A quote on
    the boundary is inside it, not silently dropped."""
    r = run()
    assert r.contains(WINDOW_START)
    assert r.contains(WINDOW_END)
    assert r.contains(datetime(2026, 9, 12, 21, 30))
    assert not r.contains(datetime(2026, 9, 12, 20, 59))
    assert not r.contains(datetime(2026, 9, 12, 22, 1))


# ─── Fare decomposition — spec A.4, PS 26056 ─────────────────────────────────


def test_unrendered_component_is_none_not_zero() -> None:
    """``None`` says the source did not show it. ``0`` asserts it does not exist."""
    assert NO_BREAKDOWN.base_fare is None
    assert NO_BREAKDOWN.declared_total is None
    assert not NO_BREAKDOWN.is_complete


def test_negative_component_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        FareBreakdown(base_fare=Decimal("-1.00"))


def test_complete_breakdown_reconciles_with_the_payable_fare() -> None:
    """PS 26056 mandates the four-way split: base, taxes, UDF, convenience."""
    b = FareBreakdown(
        base_fare=Decimal("4600.00"),
        taxes=Decimal("532.00"),
        fees=Decimal("150.00"),
        user_development_fee=Decimal("150.00"),
    )
    assert b.is_complete
    assert b.declared_total == Decimal("5432.00")
    assert b.reconciles_with(Decimal("5432.00"))
    assert b.reconciles_with(Decimal("5432.50"))  # within a rupee of rounding
    assert not b.reconciles_with(Decimal("6000.00"))


def test_partial_breakdown_never_claims_to_reconcile() -> None:
    """A partial split sums to less than the total by construction. Reporting
    that as a reconciliation failure would be noise, so it reports False for
    being incomplete instead."""
    b = FareBreakdown(base_fare=Decimal("4600.00"), taxes=Decimal("532.00"))
    assert not b.is_complete
    assert b.declared_total == Decimal("5132.00")
    assert not b.reconciles_with(Decimal("5432.00"))


def test_observation_defaults_to_no_breakdown_and_still_prices() -> None:
    """Spec A.4 — *"The index is never blocked on a breakdown the site does not
    render."* The total enters the index either way."""
    o = observation()
    assert o.fare_breakdown is NO_BREAKDOWN
    assert o.payable_fare == Decimal("5432.00")
    assert o.fare_class is FareClass.STANDARD


# ─── Source groups — spec B.6 ────────────────────────────────────────────────


def test_unknown_source_group_is_none_not_the_source_id() -> None:
    """Spec B.6 — defaulting an unknown group to the source id would silently
    assert independence, inflating effective N in the flattering direction."""
    o = observation()
    assert o.source_group is None
    assert o.source_group != o.source_id


def test_two_sources_in_one_group_are_declared_as_such() -> None:
    mmt = observation(
        observation_id="o-mmt",
        source_id="makemytrip",
        source_group="mmt_group",
        channel=Channel.AGGREGATOR,
    )
    gib = observation(
        observation_id="o-gib",
        source_id="goibibo",
        source_group="mmt_group",
        channel=Channel.AGGREGATOR,
    )
    assert mmt.source_id != gib.source_id
    assert mmt.source_group == gib.source_group


def test_attempt_carries_the_same_group_semantics() -> None:
    assert attempt(CollectionOutcome.NO_FLIGHT).source_group is None
    assert (
        attempt(CollectionOutcome.NO_FLIGHT, source_group="mmt_group").source_group == "mmt_group"
    )


# ─── Backwards compatibility ─────────────────────────────────────────────────


def test_existing_observations_are_unaffected() -> None:
    """Both new fields are optional. Every fixture written before 2G still
    constructs, and the derived properties are unchanged."""
    o = observation(availability=Availability.SOLD_OUT)
    assert o.availability is Availability.SOLD_OUT
    assert o.apw_bucket is APWBucket.T_PLUS_7
    assert o.day_of_week == (T + timedelta(days=7)).isoweekday()
    assert o.departure_hour_band == 2
    assert o.route == "DEL-BOM"
