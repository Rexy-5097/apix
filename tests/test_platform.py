"""The PS 26056 platform layers: config, scheduler, periods, readiness, backtest.

The load-bearing tests here are the ones that stop a convenient lie:

* a scheduled run over an uncleared register records ``PERMISSION_BLOCKED``, and
  that outcome keeps its cell in the coverage denominator and is attributed to
  us -- never ``NO_FLIGHT``, which would read as an absence of flights;
* a window set cannot extend the frozen APW vector, only select from it;
* a provisional or demo basket is never publication grade;
* a period level is aggregated geometrically, and an absent level is ``None``
  rather than zero;
* a benchmark comparison refuses to report level metrics across incomparable
  units, and refuses any metric below the minimum point count.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal

import pytest

from apix.backtest import BenchmarkSeries, compare
from apix.backtest.compare import (
    DGCA_FARE_BENCHMARK_STATUS,
    MIN_POINTS_FOR_METRICS,
    BacktestStatus,
    directional_agreement,
    mae,
    mape,
    pearson,
    rmse,
)
from apix.config import DEMO_BASKET, PILOT_BASKET, PS_26056_WINDOWS
from apix.config.apw import APIX_FROZEN_WINDOWS, ApwWindowSet, window_set
from apix.config.basket import BasketStatus, RouteBasket, RouteWeight
from apix.ingestion.collectors.gate import CollectionMode
from apix.scheduling import SchedulerConfig, build_plan, execute_plan, run_id_for
from apix.scheduling.scheduler import SourceOperationalStatus
from apix.schemas.enums import APWBucket, CollectionOutcome
from apix.series import Frequency, aggregate, assess, period_key
from apix.series.readiness import OutputClass, ReadinessState

CLEARED = {
    "source_id": "cleared",
    "automation_gate": "AUTOMATION_ALLOWED",
    "data_admissibility": "ADMISSIBLE",
    "tos_status": "CLEARLY_PERMITTED",
    "automated_collection_status": "CLEARLY_PERMITTED",
    "robots_status": "NO_RELEVANT_DISALLOW",
}
REFUSED = {
    "source_id": "refused",
    "automation_gate": "AUTOMATION_PROHIBITED",
    "data_admissibility": "INADMISSIBLE",
    "tos_status": "NOT_PERMITTED",
    "automated_collection_status": "NOT_PERMITTED",
    "robots_status": "DISALLOWS_REQUIRED_PATH",
}


def _config(**kw: object) -> SchedulerConfig:
    base: dict[str, object] = {
        "collection_date": date(2026, 9, 15),
        "basket": PILOT_BASKET,
        "windows": PS_26056_WINDOWS,
        "source_ids": ("refused",),
    }
    base.update(kw)
    return SchedulerConfig(**base)  # type: ignore[arg-type]


# ───────────────────────── PERMISSION_BLOCKED ─────────────────────────


def test_permission_blocked_is_our_failure_not_a_market_fact() -> None:
    """The headline invariant of ADR-0066.

    A permission refusal keeps its cell in the spec I denominator and is
    attributed to us. Were it a market fact, a register in which nothing is
    cleared would report full coverage and no flights.
    """
    outcome = CollectionOutcome.PERMISSION_BLOCKED
    assert outcome.is_collector_failure is True
    assert outcome.is_market_fact is False
    assert outcome.excludes_cell_from_expectation is False
    assert outcome.is_stop_signal is False, (
        "a gate refusal is not a stop signal -- no request was made, so there is nothing "
        "to back off from"
    )


def test_permission_blocked_is_distinct_from_every_other_absence() -> None:
    """It must not be collapsed into an outage, a parser bug or a challenge."""
    for other in (
        CollectionOutcome.NO_FLIGHT,
        CollectionOutcome.SOURCE_UNAVAILABLE,
        CollectionOutcome.TECHNICAL_FAILURE,
        CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP,
    ):
        assert CollectionOutcome.PERMISSION_BLOCKED is not other


# ───────────────────────── APW configuration ─────────────────────────


def test_frozen_window_set_is_derived_from_the_locked_enum() -> None:
    """It cannot drift from spec A.3, because it is read from APWBucket."""
    assert APIX_FROZEN_WINDOWS.days == tuple(b.value for b in APWBucket)
    assert APIX_FROZEN_WINDOWS.days == (1, 3, 7, 15, 30, 45, 60)


def test_ps_windows_are_a_strict_subset_of_the_frozen_vector() -> None:
    """So APIx reports the PS set exactly, with no methodology change."""
    assert PS_26056_WINDOWS.days == (1, 7, 15, 30, 45)
    assert APIX_FROZEN_WINDOWS.covers(PS_26056_WINDOWS)
    assert not PS_26056_WINDOWS.covers(APIX_FROZEN_WINDOWS)
    assert set(APIX_FROZEN_WINDOWS.days) - set(PS_26056_WINDOWS.days) == {3, 60}


def test_a_window_set_cannot_extend_the_frozen_vector() -> None:
    """Configuration may SELECT from spec A.3, never add to it."""
    with pytest.raises(ValueError, match="match no frozen APWBucket"):
        ApwWindowSet(set_id="bad", version="1", days=(1, 21), authority="invented")


def test_window_set_lookup_refuses_an_unknown_id() -> None:
    with pytest.raises(KeyError, match="unknown APW window set"):
        window_set("does-not-exist")


def test_window_buckets_resolve_to_frozen_buckets() -> None:
    assert PS_26056_WINDOWS.buckets == (
        APWBucket.T_PLUS_1,
        APWBucket.T_PLUS_7,
        APWBucket.T_PLUS_15,
        APWBucket.T_PLUS_30,
        APWBucket.T_PLUS_45,
    )


# ───────────────────────── route basket ─────────────────────────


def test_neither_declared_basket_is_publication_grade() -> None:
    """OQ-4 is open: APIx holds no DGCA-derived weights."""
    assert PILOT_BASKET.is_publication_grade is False
    assert DEMO_BASKET.is_publication_grade is False
    assert PILOT_BASKET.status is BasketStatus.PROVISIONAL
    assert DEMO_BASKET.status is BasketStatus.DEMO


def test_weights_normalise_to_one() -> None:
    """Spec G.5. A basket that does not sum to one silently rescales the index."""
    for basket in (PILOT_BASKET, DEMO_BASKET):
        total = sum(basket.normalised_weights.values())
        assert total == pytest.approx(Decimal("1"), abs=Decimal("1e-9"))


def test_demo_basket_carries_the_ps_city_pairs() -> None:
    assert [r.pair for r in DEMO_BASKET.routes] == [
        "DEL-BOM",
        "DEL-BLR",
        "BOM-BLR",
        "DEL-CCU",
        "BLR-HYD",
        "MAA-DEL",
    ]


def test_a_non_official_basket_must_state_its_caveat_in_words() -> None:
    route = RouteWeight(
        route_id="DEL-BOM",
        origin="DEL",
        destination="BOM",
        weight=Decimal("1"),
        weight_source="test",
        effective_date=date(2026, 9, 15),
    )
    with pytest.raises(ValueError, match="carries no caveat"):
        RouteBasket(
            basket_version="x",
            methodology_version="2.1",
            status=BasketStatus.DEMO,
            effective_date=date(2026, 9, 15),
            routes=(route,),
            authority="test",
        )


def test_a_weight_must_be_attributed() -> None:
    with pytest.raises(ValueError, match="no weight_source"):
        RouteWeight(
            route_id="DEL-BOM",
            origin="DEL",
            destination="BOM",
            weight=Decimal("1"),
            weight_source="   ",
            effective_date=date(2026, 9, 15),
        )


def test_a_zero_weight_is_refused_rather_than_stored() -> None:
    with pytest.raises(ValueError, match="not a weight"):
        RouteWeight(
            route_id="DEL-BOM",
            origin="DEL",
            destination="BOM",
            weight=Decimal("0"),
            weight_source="test",
            effective_date=date(2026, 9, 15),
        )


# ───────────────────────── scheduler ─────────────────────────


def test_plan_is_routes_times_windows_per_source() -> None:
    """Bands are not planned per request: one search returns the whole day."""
    config = _config(basket=DEMO_BASKET, source_ids=("a", "b"))
    plan = build_plan(config)
    assert len(plan) == 2 * len(DEMO_BASKET.routes) * len(PS_26056_WINDOWS.days)
    assert all(p.bands == config.bands for p in plan)


def test_planned_travel_date_is_always_an_exact_frozen_lead_time() -> None:
    """The plan cannot generate a date that lands off a frozen bucket."""
    for search in build_plan(_config(windows=APIX_FROZEN_WINDOWS)):
        lead = (search.travel_date - date(2026, 9, 15)).days
        assert lead == search.apw_days
        assert APWBucket.from_lead_time(lead) is not None


def test_run_id_is_deterministic_and_input_sensitive() -> None:
    """Re-planning the same schedule is idempotent; changing it is not."""
    a, b = _config(), _config()
    assert run_id_for(a) == run_id_for(b)
    assert run_id_for(_config(basket=DEMO_BASKET)) != run_id_for(a)
    assert run_id_for(_config(windows=APIX_FROZEN_WINDOWS)) != run_id_for(a)


def test_an_uncleared_register_yields_permission_blocked_and_zero_requests() -> None:
    """The current production reality, and it must run to completion."""
    run = execute_plan(_config(), {"refused": REFUSED})
    assert run.by_outcome == {"PERMISSION_BLOCKED": len(run.plan)}
    assert run.requests_made == 0
    assert run.observations_written == 0
    assert run.cleared_sources == ()
    assert run.coverage_loss_attributed_to_us == len(run.plan)
    assert run.source_status["refused"] is SourceOperationalStatus.PERMISSION_BLOCKED
    assert all(not r.requested for r in run.records)
    assert all("Nothing requested, nothing written" in r.detail for r in run.records)


def test_a_source_missing_from_the_register_is_blocked_not_skipped() -> None:
    run = execute_plan(_config(source_ids=("ghost",)), {})
    assert run.by_outcome == {"PERMISSION_BLOCKED": len(run.plan)}
    assert "not in the source register" in run.records[0].detail


def test_every_plan_entry_gets_exactly_one_record() -> None:
    """Missingness is measurable only from a record of attempts — spec H.1."""
    run = execute_plan(_config(basket=DEMO_BASKET), {"refused": REFUSED})
    assert len(run.records) == len(run.plan)
    assert [r.planned for r in run.records] == list(run.plan)


def test_a_cleared_source_without_a_collector_is_unavailable_never_success() -> None:
    """A cleared source that produced no quote is a coverage loss, and it is ours."""
    run = execute_plan(_config(source_ids=("cleared",)), {"cleared": CLEARED}, collector=None)
    assert run.by_outcome == {"SOURCE_UNAVAILABLE": len(run.plan)}
    assert run.requests_made == 0
    assert run.cleared_sources == ("cleared",)


def test_a_stop_signal_halts_the_source_for_the_rest_of_the_run() -> None:
    """No retry past a challenge, at any interval. Remaining searches NOT_ATTEMPTED."""
    calls: list[str] = []

    def collector(search):  # type: ignore[no-untyped-def]
        calls.append(search.search_key)
        return CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP, "challenge presented", 0

    run = execute_plan(_config(source_ids=("cleared",)), {"cleared": CLEARED}, collector=collector)
    assert len(calls) == 1, "the collector must not be called again after a stop signal"
    counts = run.by_outcome
    assert counts["CAPTCHA_OR_ANTIBOT_STOP"] == 1
    assert counts["NOT_ATTEMPTED"] == len(run.plan) - 1
    assert run.source_status["cleared"] is SourceOperationalStatus.CHALLENGED


def test_the_circuit_breaker_opens_after_repeated_unreachability() -> None:
    def collector(search):  # type: ignore[no-untyped-def]
        return CollectionOutcome.SOURCE_UNAVAILABLE, "timeout", 0

    run = execute_plan(
        _config(source_ids=("cleared",), breaker_threshold=2),
        {"cleared": CLEARED},
        collector=collector,
    )
    assert run.source_status["cleared"] is SourceOperationalStatus.UNREACHABLE
    assert run.by_outcome["NOT_ATTEMPTED"] == len(run.plan) - 2


def test_a_successful_collector_is_recorded_with_its_observations() -> None:
    def collector(search):  # type: ignore[no-untyped-def]
        return CollectionOutcome.SUCCESS, "5 bands selected", 5

    run = execute_plan(_config(source_ids=("cleared",)), {"cleared": CLEARED}, collector=collector)
    assert run.by_outcome == {"SUCCESS": len(run.plan)}
    assert run.requests_made == len(run.plan)
    assert run.observations_written == 5 * len(run.plan)
    assert run.coverage_loss_attributed_to_us == 0


def test_pacing_floor_and_band_set_are_enforced_by_the_config() -> None:
    with pytest.raises(ValueError, match="below the 10 s floor"):
        _config(min_interval_seconds=1.0)
    with pytest.raises(ValueError, match="outside the contracted set"):
        _config(bands=(0, 7))


def test_summary_reports_the_basket_publication_grade() -> None:
    run = execute_plan(_config(basket=DEMO_BASKET), {"refused": REFUSED})
    assert run.summary()["basket_is_publication_grade"] is False
    assert run.summary()["basket_status"] == "DEMO"


# ───────────────────────── periods ─────────────────────────


def test_period_keys_use_iso_weeks_and_calendar_months() -> None:
    assert period_key(date(2026, 1, 1), Frequency.DAILY) == "2026-01-01"
    assert period_key(date(2026, 1, 1), Frequency.MONTHLY) == "2026-01"
    iso = date(2026, 1, 1).isocalendar()
    assert period_key(date(2026, 1, 1), Frequency.WEEKLY) == f"{iso.year}-W{iso.week:02d}"


def test_levels_aggregate_geometrically_not_arithmetically() -> None:
    """An index is a ratio scale; the arithmetic mean of ratios does not compose."""
    points = [(date(2026, 3, 2), 100.0), (date(2026, 3, 3), 400.0)]
    monthly = aggregate(points, Frequency.MONTHLY)
    assert len(monthly) == 1
    assert monthly[0].level == pytest.approx(math.sqrt(100.0 * 400.0))
    assert monthly[0].level == pytest.approx(200.0)
    assert monthly[0].level != pytest.approx(250.0), "that would be the arithmetic mean"


def test_a_period_with_no_computable_level_is_none_not_zero() -> None:
    monthly = aggregate([(date(2026, 3, 2), None), (date(2026, 3, 3), None)], Frequency.MONTHLY)
    assert monthly[0].level is None
    assert "no computable level" in monthly[0].coverage_note


def test_change_against_a_missing_period_is_none() -> None:
    series = aggregate(
        [(date(2026, 3, 2), 100.0), (date(2026, 4, 2), None), (date(2026, 5, 2), 110.0)],
        Frequency.MONTHLY,
    )
    assert series[0].change_pct is None, "the first period has no predecessor"
    assert series[1].change_pct is None, "a period with no level has no change"
    assert series[2].change_pct == pytest.approx(10.0), "change skips the absent period"


def test_monthly_change_composes_from_the_daily_levels_it_spans() -> None:
    """The property the geometric mean buys: changes multiply through."""
    jan = aggregate([(date(2026, 1, 5), 100.0), (date(2026, 1, 6), 100.0)], Frequency.MONTHLY)
    feb = aggregate([(date(2026, 2, 5), 110.0), (date(2026, 2, 6), 110.0)], Frequency.MONTHLY)
    assert feb[0].level / jan[0].level == pytest.approx(1.10)


def test_aggregate_of_nothing_is_empty_not_an_error() -> None:
    assert aggregate([], Frequency.DAILY) == ()


# ───────────────────────── readiness ─────────────────────────


def test_the_real_panel_is_research_not_production() -> None:
    verdict = assess(
        collection_waves=1,
        matched_pairs=0,
        admissible_observations=35,
        cleared_sources=0,
        coverage_denominator_defined=False,
        open_blocking_ambiguities=("AMB-8", "AMB-9"),
    )
    assert verdict.state is ReadinessState.MISSING_PREVIOUS_PERIOD
    assert verdict.output_class is OutputClass.RESEARCH
    assert verdict.publishable is False
    assert any("C.1" in b for b in verdict.blockers)
    assert any("AMB-8" in b for b in verdict.blockers)


def test_a_fixture_is_always_demo_and_never_publishable() -> None:
    verdict = assess(
        collection_waves=14,
        matched_pairs=99,
        admissible_observations=999,
        cleared_sources=1,
        coverage_denominator_defined=True,
        basket_is_publication_grade=True,
        backtest_satisfied=True,
        is_fixture=True,
    )
    assert verdict.output_class is OutputClass.DEMO
    assert verdict.publishable is False
    assert "SYNTHETIC FIXTURE" in verdict.blockers[0]


def test_no_cleared_source_reports_source_blocked() -> None:
    verdict = assess(
        collection_waves=0,
        matched_pairs=0,
        admissible_observations=0,
        cleared_sources=0,
        coverage_denominator_defined=False,
    )
    assert verdict.state is ReadinessState.SOURCE_BLOCKED
    assert "no source cleared" in verdict.blockers[0]


def test_every_guard_met_is_the_only_route_to_production() -> None:
    verdict = assess(
        collection_waves=2,
        matched_pairs=5,
        admissible_observations=70,
        cleared_sources=1,
        coverage_denominator_defined=True,
        basket_is_publication_grade=True,
        backtest_satisfied=True,
    )
    assert verdict.state is ReadinessState.READY
    assert verdict.output_class is OutputClass.PRODUCTION
    assert verdict.publishable is True


# ───────────────────────── backtest ─────────────────────────


def test_dgca_fare_benchmark_is_recorded_as_not_located() -> None:
    assert DGCA_FARE_BENCHMARK_STATUS == "NOT_LOCATED"


def test_metrics_are_correct_on_a_known_series() -> None:
    xs = [1.0, 2.0, 3.0, 4.0]
    assert pearson(xs, [2.0, 4.0, 6.0, 8.0]) == pytest.approx(1.0)
    assert pearson(xs, [8.0, 6.0, 4.0, 2.0]) == pytest.approx(-1.0)
    assert mae(xs, [2.0, 3.0, 4.0, 5.0]) == pytest.approx(1.0)
    assert rmse(xs, [2.0, 3.0, 4.0, 5.0]) == pytest.approx(1.0)
    # Averaged over ALL three points, including the exact one: (0.10+0.10+0)/3.
    assert mape([110.0, 90.0, 100.0], [100.0, 100.0, 100.0]) == pytest.approx(100 / 15)
    assert mape([110.0, 110.0, 110.0], [100.0, 100.0, 100.0]) == pytest.approx(10.0)
    assert directional_agreement(xs, [5.0, 6.0, 7.0, 8.0]) == pytest.approx(100.0)
    assert directional_agreement(xs, [8.0, 7.0, 6.0, 5.0]) == pytest.approx(0.0)


def test_metrics_refuse_to_report_below_the_minimum_point_count() -> None:
    """A correlation over two points is +-1 by construction and means nothing."""
    two = [1.0, 2.0]
    assert MIN_POINTS_FOR_METRICS == 3
    assert pearson(two, [1.0, 2.0]) is None
    assert mae(two, [1.0, 2.0]) is None
    assert rmse(two, [1.0, 2.0]) is None
    assert directional_agreement([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) is None


def test_a_constant_series_has_no_correlation_rather_than_zero() -> None:
    assert pearson([5.0, 5.0, 5.0, 5.0], [1.0, 2.0, 3.0, 4.0]) is None


def _bench(points: dict[str, float], *, is_index: bool = True) -> BenchmarkSeries:
    return BenchmarkSeries(
        benchmark_id="b",
        publisher="p",
        measures="m",
        unit="u",
        frequency="monthly",
        points=points,
        provenance="test",
        is_index_number=is_index,
    )


def test_no_overlap_is_no_data_with_the_counts_named() -> None:
    result = compare({"2026-01": 100.0}, _bench({"2025-01": 100.0}))
    assert result.status is BacktestStatus.NO_DATA
    assert result.n == 0
    assert "no overlapping period" in result.reasons[0]


def test_level_metrics_are_suppressed_across_incomparable_units() -> None:
    """An index number against an average fare in rupees is not a difference."""
    points = {f"2026-{m:02d}": 100.0 + m for m in range(1, 6)}
    result = compare(points, _bench({k: v * 50 for k, v in points.items()}, is_index=False))
    assert result.mae is None and result.mape is None and result.rmse is None
    assert result.correlation is not None, "scale-free metrics survive the mismatch"
    assert result.directional_agreement is not None
    assert result.status is BacktestStatus.INCOMPLETE
    assert any("different quantities" in r for r in result.reasons)


def test_a_comparable_aligned_series_is_satisfied() -> None:
    points = {f"2026-{m:02d}": 100.0 + m for m in range(1, 7)}
    result = compare(points, _bench(dict(points)))
    assert result.status is BacktestStatus.SATISFIED
    assert result.n == 6
    assert result.correlation == pytest.approx(1.0)
    assert result.mae == pytest.approx(0.0)


# ───────────────────────── the demo command ─────────────────────────


def test_demo_runs_end_to_end_and_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """``python -m apix.demo`` is the submission entry point; it must not break."""
    from apix import demo

    assert demo.main([]) == 0
    out = capsys.readouterr().out
    for marker in (
        "SCHEDULED COLLECTION",
        "PERMISSION_BLOCKED",
        "REAL-DATA PIPELINE",
        "PUBLICATION READINESS",
        "SYNTHETIC FIXTURE",
        "PERIOD SERIES",
        "BENCHMARK BACKTEST",
        "NO real automated airfare observation has been acquired",
    ):
        assert marker in out, f"the demo must report {marker!r}"


def test_demo_never_claims_live_acquisition(capsys: pytest.CaptureFixture[str]) -> None:
    """The one claim the submission must not make."""
    from apix import demo

    demo.main([])
    out = capsys.readouterr().out.lower()
    assert "requests made     : 0" in out.replace("  ", "  ")
    for forbidden in ("fully scrapes", "live acquisition operational", "captcha bypass"):
        assert forbidden not in out


def test_scheduler_run_carries_a_timestamped_window() -> None:
    run = execute_plan(_config(), {"refused": REFUSED})
    assert isinstance(run.started_at, datetime)
    assert run.finished_at >= run.started_at
    assert run.summary()["run_id"].startswith("sched-2026-09-15-")


def test_search_key_is_stable_and_identifies_one_search() -> None:
    plan = build_plan(_config(basket=DEMO_BASKET))
    keys = [p.search_key for p in plan]
    assert len(keys) == len(set(keys)), "search keys must be unique within a run"
    assert plan[0].search_key.startswith("refused|LIVE|")
    assert plan[0].mode is CollectionMode.LIVE
