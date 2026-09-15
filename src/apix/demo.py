"""``python -m apix.demo`` — the whole platform, end to end, in one command.

Runs every stage PS 26056 asks for, against the data APIx actually holds, and
labels each output by what it is:

======================  ===========================================================
Stage                   What it runs on
======================  ===========================================================
Scheduled collection    The **real** source register. Every search is refused at
                        the compliance gate, and each refusal is recorded.
Real-data pipeline      The **35 real observations** collected 2026-09-12.
Publication readiness   The real panel -> ``RESEARCH``, not publishable.
Index engine            A **synthetic 14-day fixture** -> ``DEMO`` index. Real
                        arithmetic, real guards, fictional market.
Period series           Daily / weekly / monthly from the demo index points.
Benchmark backtest      MoSPI CPI airfare index -> ``INCOMPLETE``.
======================  ===========================================================

**Nothing here fabricates a market observation, and nothing presents the demo
index as a measurement.** The one command exists so a reviewer can see the whole
chain without assembling it, and so the labels travel with the numbers.

Needs no network and no optional dependency.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "analysis"))

from apix.backtest import BenchmarkSeries, compare  # noqa: E402
from apix.backtest.compare import (  # noqa: E402
    DGCA_FARE_BENCHMARK_DETAIL,
    DGCA_FARE_BENCHMARK_STATUS,
)
from apix.config import DEMO_BASKET, PILOT_BASKET, PS_26056_WINDOWS  # noqa: E402
from apix.config.apw import APIX_FROZEN_WINDOWS  # noqa: E402
from apix.scheduling import SchedulerConfig, execute_plan  # noqa: E402
from apix.series import Frequency, aggregate, assess  # noqa: E402

PANEL = REPO / "data" / "panel.json"
BENCHMARK = REPO / "data" / "mospi_cpi_airfare.json"
REGISTRY = REPO / "source_registry" / "registry.yaml"

BAR = "=" * 78
DASH = "-" * 78


def _head(n: int, title: str) -> None:
    print(f"\n{BAR}\n {n}. {title}\n{BAR}")


def _load_registry() -> dict[str, Any]:
    """Parse the register. Falls back to an empty mapping without PyYAML.

    An empty register is the safe failure: every source is then absent, every
    search is PERMISSION_BLOCKED, and nothing is collected. A missing parser must
    never look like a clearance.
    """
    try:
        import yaml  # type: ignore[import-untyped]  # stubs not a project dependency
    except ImportError:
        print("  ! PyYAML not installed; treating the register as EMPTY (nothing cleared)")
        return {}
    raw = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return {e["source_id"]: e for e in raw.get("sources", []) if isinstance(e, dict)}


def stage_scheduler() -> dict[str, Any]:
    _head(1, "SCHEDULED COLLECTION — against the real source register")
    registry = _load_registry()
    config = SchedulerConfig(
        collection_date=date(2026, 9, 15),
        basket=DEMO_BASKET,
        windows=PS_26056_WINDOWS,
        source_ids=("indigo", "air_india", "makemytrip", "cleartrip", "indigo_ndc"),
    )
    run = execute_plan(config, registry)
    s = run.summary()
    print(f"  run id            : {s['run_id']}")
    print(
        f"  basket            : {s['basket_version']} ({s['basket_status']}, "
        f"publication grade: {s['basket_is_publication_grade']})"
    )
    print(f"  windows           : {s['window_set']} {s['windows']}")
    print(f"  bands             : {s['bands']}")
    print(f"  planned searches  : {s['planned_searches']}")
    print(f"  requests MADE     : {s['requests_made']}")
    print(f"  cleared sources   : {s['cleared_sources'] or 'NONE'}")
    print(f"  outcomes          : {s['by_outcome']}")
    print(f"  coverage loss OURS: {s['coverage_loss_attributed_to_us']}")
    print(DASH)
    print("  Every search refused at the gate BEFORE any request. A permission refusal is")
    print("  recorded as PERMISSION_BLOCKED, never as NO_FLIGHT — so our lack of")
    print("  authorisation is never mistaken for an absence of flights (ADR-0066).")
    return s


def stage_real_panel() -> dict[str, Any]:
    _head(2, "REAL-DATA PIPELINE — 35 observations collected 2026-09-12")
    # tools/analysis is on sys.path at runtime (see the header); mypy cannot follow that.
    from execution_boundary import build_boundary, reconstruct  # type: ignore[import-not-found]

    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    observations = reconstruct(panel)
    boundary = build_boundary(panel)
    counts = boundary["state_counts"]

    print(f"  observations rebuilt : {len(observations)}")
    print(f"  data class           : {panel['data_class']}")
    print(f"  synthetic present    : {panel['synthetic_data_present']}")
    print(f"  stage states         : {counts}")
    print(DASH)
    for stage in boundary["stages"]:
        print(f"   {stage['state']:<11} {stage['name']} ({stage['spec']})")
    print(DASH)
    print(f"  {boundary['claim']}")
    return {"observations": len(observations), "boundary": boundary, "panel": panel}


def stage_readiness(panel: dict[str, Any]) -> dict[str, Any]:
    _head(3, "PUBLICATION READINESS — the layer allowed to say no")
    index_status = panel["index_status"]
    verdict = assess(
        collection_waves=index_status["collection_waves"],
        matched_pairs=index_status["matched_pairs_available"],
        admissible_observations=len(panel["observations"]),
        cleared_sources=0,
        coverage_denominator_defined=False,
        open_blocking_ambiguities=("AMB-8", "AMB-9"),
        basket_is_publication_grade=PILOT_BASKET.is_publication_grade,
        backtest_satisfied=False,
    )
    print(f"  state         : {verdict.state.value}")
    print(f"  output class  : {verdict.output_class.value}")
    print(f"  publishable   : {verdict.publishable}")
    print("  blockers      :")
    for b in verdict.blockers:
        print(f"    - {b}")
    print(DASH)
    print(f"  {verdict.detail}")
    return verdict.as_dict()


def stage_demo_index() -> dict[str, Any]:
    _head(4, "INDEX ENGINE — synthetic 14-day fixture (DEMO, not a measurement)")
    import engine_demo  # type: ignore[import-not-found]  # same sys.path reason as above

    result = engine_demo.run()
    # Index levels come from the ApixLResult series -- the engine's own published
    # output -- not from cell states. A CellState carries a cell-level value that
    # may be HELD_OUT or SUPPRESSED; reading those as index points would report
    # levels the engine declined to publish.
    levels: dict[date, float] = {
        r.collection_date: float(r.level)
        for r in result["results"]
        if r.published and r.level is not None
    }
    held_back = [r.collection_date for r in result["results"] if not r.published]

    print(f"  fixture observations : {result['observations']}")
    print(f"  collection dates     : {len(result['collection_dates'])}")
    print(f"  t/t-7 links opened   : {len(result['links'])}")
    print(f"  engine results       : {len(result['results'])}")
    print(f"  PUBLISHED points     : {len(levels)}")
    print(f"  withheld by engine   : {len(held_back)}")
    if result["links"]:
        first = result["links"][0]
        jev = first["jevons"]
        rel = jev.relative
        print(f"  first link           : {first['t_7']} -> {first['t']}")
        print(f"    matched items      : {jev.matched_count} of {jev.candidate_count} candidates")
        print(f"    Jevons relative    : {rel if rel is None else round(rel, 6)}")
    guard, detail = engine_demo.guard_demo(result["states"])
    print(f"  publication guard    : refused with {guard}")
    print(f"    {detail[:120]}")
    print(DASH)
    print("  SYNTHETIC FIXTURE. Real arithmetic, real guards, fictional market. This is the")
    print("  only place in APIx where an index number is ever computed.")
    return {"levels": levels, "links": len(result["links"]), "guard": guard}


def stage_periods(levels: dict[date, float]) -> dict[str, Any]:
    _head(5, "PERIOD SERIES — daily / weekly / monthly (DEMO input)")
    points = sorted(levels.items())
    out: dict[str, Any] = {}
    for freq in (Frequency.DAILY, Frequency.WEEKLY, Frequency.MONTHLY):
        series = aggregate(points, freq)
        out[freq.value] = [p.as_dict() for p in series]
        print(f"\n  {freq.value}: {len(series)} period(s)")
        for p in series[:4]:
            lvl = "None" if p.level is None else f"{p.level:.4f}"
            chg = "    —" if p.change_pct is None else f"{p.change_pct:+7.3f}%"
            print(f"    {p.period:<12} level={lvl:<10} change={chg}  ({p.coverage_note})")
        if len(series) > 4:
            print(f"    … {len(series) - 4} more")
    print(DASH)
    print("  Levels aggregate GEOMETRICALLY — an index is a ratio scale, so an arithmetic")
    print("  mean of levels is not the level of anything.")
    return out


def stage_backtest(levels: dict[date, float]) -> dict[str, Any]:
    _head(6, "BENCHMARK BACKTEST — PS-required DGCA comparison")
    print(f"  DGCA fare benchmark : {DGCA_FARE_BENCHMARK_STATUS}")
    print(f"    {DGCA_FARE_BENCHMARK_DETAIL[:150]}…")
    print(DASH)

    raw = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    months = {
        "January": 1,
        "February": 2,
        "March": 3,
        "April": 4,
        "May": 5,
        "June": 6,
        "July": 7,
        "August": 8,
        "September": 9,
        "October": 10,
        "November": 11,
        "December": 12,
    }
    # ONE base year only. The series carries both base 2010 and base 2012 for the
    # 2014 overlap, and dividing a base-2012 index by a base-2010 one is a units
    # error, not a rate of change -- the fetcher's own docstring says so.
    base = "2012"
    points = {
        f"{r['year']}-{months[r['month']]:02d}": float(r["index"])
        for r in raw["series"].values()
        if r.get("index") is not None and r.get("baseyear") == base and r["month"] in months
    }
    observed_months = sorted({r["month"] for r in raw["series"].values()})
    benchmark = BenchmarkSeries(
        benchmark_id=f"mospi_cpi_airfare_base{base}",
        publisher="MoSPI eSankhyiki",
        measures=raw["item"],
        unit=raw["unit"],
        frequency=raw["frequency"],
        points=points,
        provenance=raw["source"],
        is_index_number=True,
    )
    print(f"  fallback benchmark  : {benchmark.benchmark_id} ({len(points)} points, base {base})")
    print(f"    measures          : {benchmark.measures}")
    print(f"    unit              : {benchmark.unit}")
    print(f"    declared frequency: {benchmark.frequency}")
    print(f"    months ACTUALLY published: {observed_months}")
    if len(observed_months) == 1:
        print("    ! declared monthly, but only ONE month per year is present — in practice")
        print("      this is an ANNUAL series, and it cannot support a 30-day backtest")

    apix_monthly = {
        p.period: p.level
        for p in aggregate(sorted(levels.items()), Frequency.MONTHLY)
        if p.level is not None
    }
    result = compare(apix_monthly, benchmark)
    print(f"  status              : {result.status.value}")
    print(f"  aligned periods     : {result.n}")
    print(f"  comparability       : {result.comparability[:110]}")
    for r in result.reasons:
        print(f"    - {r}")
    print(DASH)
    print("  BACKTEST STATUS = INCOMPLETE. Two independent reasons: the PS's stated")
    print("  benchmark (DGCA average fares) is not published, and APIx holds no real index")
    print("  series to compare. The framework is implemented and its metrics are real.")
    return result.as_dict()


def stage_service_surface() -> dict[str, object]:
    """Stage 7 — the surfaces NSO/RBI would consume: exports, API contract, console."""
    from apix.api import ENDPOINTS
    from apix.export import write_all

    _head(7, "SERVICE SURFACE — EXPORTS, API CONTRACT, PLATFORM CONSOLE")
    written = write_all()
    print(f"  exports written     : {len(written)} files -> {written[0].parent}")
    print(f"  API endpoints       : {len(ENDPOINTS)}  (serve: python -m apix.api --port 8760)")
    for ep in ENDPOINTS:
        print(f"    GET {ep}")
    print("  platform console    : data/platform.html  (python tools/analysis/build_platform.py)")
    print(DASH)
    print("  Every JSON export is the API envelope: output_class, publication_status,")
    print("  live_airfare_acquisition=BLOCKED on every payload. No PRODUCTION value exists.")
    return {"exports": len(written), "endpoints": len(ENDPOINTS)}


def main(argv: list[str] | None = None) -> int:
    print(BAR)
    print(" APIx — REAL-TIME AIRFARE MEASUREMENT INFRASTRUCTURE FOR INDIA")
    print(" MoSPI Problem Statement 26056 · end-to-end platform demonstration")
    print(BAR)
    print(" Compliant, auditable augmentation of CPI airfare measurement.")
    print(f" APW frozen production vector : {list(APIX_FROZEN_WINDOWS.days)}")
    print(
        f" APW PS 26056 vector          : {list(PS_26056_WINDOWS.days)}"
        f"  (subset: {APIX_FROZEN_WINDOWS.covers(PS_26056_WINDOWS)})"
    )

    scheduler = stage_scheduler()
    panel_stage = stage_real_panel()
    readiness = stage_readiness(panel_stage["panel"])
    demo = stage_demo_index()
    periods = stage_periods(demo["levels"])
    backtest = stage_backtest(demo["levels"])
    surface = stage_service_surface()

    _head(8, "SUBMISSION STATUS")
    rows = [
        ("Scheduled collection", "WORKING", f"{scheduler['planned_searches']} searches planned"),
        ("Compliance gate", "WORKING", f"{scheduler['requests_made']} requests made — all refused"),
        ("Real observations", "HELD", f"{panel_stage['observations']} audited, 1 route, 1 carrier"),
        ("Real-data stages", "EXERCISED", str(panel_stage["boundary"]["state_counts"])),
        ("Publication readiness", readiness["state"], readiness["output_class"]),
        ("Index engine", "WORKING", f"{demo['links']} t/t-7 links on a SYNTHETIC fixture"),
        ("Period series", "WORKING", f"{len(periods['MONTHLY'])} monthly period(s), DEMO input"),
        ("Backtest framework", backtest["status"], "DGCA fare benchmark NOT_LOCATED"),
        (
            "API + exports",
            "WORKING",
            f"{surface['endpoints']} endpoints, {surface['exports']} export files",
        ),
        ("Live airfare acquisition", "BLOCKED", "authorization pending — 0 of 30 sources cleared"),
    ]
    for name, status, detail in rows:
        print(f"  {name:<26} {status:<22} {detail}")

    print(f"\n{BAR}")
    print(" APIx is a complete end-to-end airfare measurement platform with a compliant")
    print(" acquisition boundary. The only major production gap is authorized live airfare")
    print(" acquisition. NO real automated airfare observation has been acquired.")
    print(BAR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
