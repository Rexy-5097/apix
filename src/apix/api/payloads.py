"""Every payload the API serves, the platform page renders and the exports write.

One module builds them, three consumers read them, so the dashboard cannot
show a number the API does not serve and the export cannot disagree with either.

Every payload is wrapped by :func:`envelope`, which stamps what the reader must
never lose sight of: the methodology version, the **output class** --
``PRODUCTION`` / ``RESEARCH`` / ``DEMO`` -- and the publication state. A number
without its class is not served.

Sources of truth, all committed files or pure computation:

* ``data/panel.json`` -- the 35 real observations and everything derived from them
* ``source_registry/registry.yaml`` -- the 30-source compliance register
* ``apix.config`` / ``apix.scheduling`` -- the plan and its refusals
* ``apix.series`` / ``apix.backtest`` -- period series and the benchmark verdict
* the synthetic 14-day engine fixture -- the only source of an index level, DEMO

Nothing here contacts a network.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from apix.backtest import BenchmarkSeries, compare
from apix.backtest.compare import DGCA_FARE_BENCHMARK_DETAIL, DGCA_FARE_BENCHMARK_STATUS
from apix.config import DEMO_BASKET, PILOT_BASKET, PS_26056_WINDOWS
from apix.config.apw import APIX_FROZEN_WINDOWS, declared_sets
from apix.config.basket import declared_baskets
from apix.ingestion.collectors.egress import DECLARED_EGRESS
from apix.scheduling import SchedulerConfig, execute_plan
from apix.series import Frequency, aggregate, assess
from apix.series.readiness import OutputClass

REPO = Path(__file__).resolve().parents[3]
PANEL = REPO / "data" / "panel.json"
BENCHMARK = REPO / "data" / "mospi_cpi_airfare.json"
REGISTRY = REPO / "source_registry" / "registry.yaml"
REFERENCE = REPO / "data" / "reference" / "alliance_air_tariff.json"

API_VERSION = "1.0"
METHODOLOGY_VERSION = "2.1"
COLLECTION_DATE = date(2026, 9, 15)

_MONTHS = {
    m: i
    for i, m in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        start=1,
    )
}


def envelope(
    data: Any,
    *,
    output_class: OutputClass,
    publication_status: str,
    data_status: str,
    endpoint: str,
    note: str = "",
) -> dict[str, Any]:
    """Wrap a payload with what a statistical consumer must never lose."""
    return {
        "api_version": API_VERSION,
        "endpoint": endpoint,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "methodology_version": METHODOLOGY_VERSION,
        "output_class": output_class.value,
        "publication_status": publication_status,
        "data_status": data_status,
        "live_airfare_acquisition": "BLOCKED — authorization pending; 0 of 30 sources cleared",
        "note": note,
        "data": data,
    }


@lru_cache(maxsize=1)
def panel() -> dict[str, Any]:
    return json.loads(PANEL.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def registry() -> dict[str, dict[str, Any]]:
    """Parsed register, or empty when PyYAML is absent — never a clearance."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return {}
    raw = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return {e["source_id"]: e for e in raw.get("sources", []) if isinstance(e, dict)}


@lru_cache(maxsize=1)
def scheduled_run() -> Any:
    """The demo schedule against the real register. Deterministic, no network."""
    cfg = SchedulerConfig(
        collection_date=COLLECTION_DATE,
        basket=DEMO_BASKET,
        windows=PS_26056_WINDOWS,
        source_ids=("indigo", "air_india", "makemytrip", "cleartrip", "indigo_ndc"),
    )
    return execute_plan(cfg, registry())


@lru_cache(maxsize=1)
def demo_levels() -> dict[date, float]:
    """Published index points from the synthetic fixture. DEMO only."""
    sys.path.insert(0, str(REPO / "tools" / "analysis"))
    try:
        import engine_demo  # type: ignore[import-not-found]
    except ImportError:
        return {}
    result = engine_demo.run()
    return {
        r.collection_date: float(r.level)
        for r in result["results"]
        if r.published and r.level is not None
    }


def real_readiness() -> Any:
    p = panel()
    return assess(
        collection_waves=p["index_status"]["collection_waves"],
        matched_pairs=p["index_status"]["matched_pairs_available"],
        admissible_observations=len(p["observations"]),
        cleared_sources=len(scheduled_run().cleared_sources),
        coverage_denominator_defined=False,
        open_blocking_ambiguities=("AMB-8", "AMB-9"),
        basket_is_publication_grade=PILOT_BASKET.is_publication_grade,
        backtest_satisfied=False,
    )


# ───────────────────────────── endpoints ─────────────────────────────


def health() -> dict[str, Any]:
    return envelope(
        {
            "status": "ok",
            "panel_present": PANEL.exists(),
            "register_present": REGISTRY.exists(),
            "register_parsed": bool(registry()),
            "reference_present": REFERENCE.exists(),
            "observations_held": len(panel()["observations"]),
            "egress_policy": DECLARED_EGRESS.as_dict(),
        },
        output_class=OutputClass.RESEARCH,
        publication_status="NOT_PUBLISHED",
        data_status="REAL_PANEL_HELD",
        endpoint="/health",
    )


def sources() -> dict[str, Any]:
    run = scheduled_run()
    reg = registry()
    rows = []
    for sid, entry in sorted(reg.items()):
        rows.append(
            {
                "source_id": sid,
                "display_name": entry.get("display_name"),
                "channel": entry.get("channel"),
                "automation_gate": entry.get("automation_gate"),
                "data_admissibility": entry.get("data_admissibility"),
                "data_rights": entry.get("data_rights", "RETENTION_UNKNOWN"),
                "robots_status": entry.get("robots_status"),
                "tos_status": entry.get("tos_status"),
                "operational_status": run.source_status.get(sid).value
                if sid in run.source_status
                else "NOT_SCHEDULED",
                "evidence_date": entry.get("evidence_date"),
            }
        )
    return envelope(
        {
            "register_size": len(rows),
            "cleared_for_live": list(run.cleared_sources),
            "gate_vocabulary": [
                "AUTOMATION_ALLOWED",
                "AUTOMATION_ALLOWED_WITH_PERMISSION",
                "AUTOMATION_UNKNOWN",
                "AUTOMATION_PROHIBITED",
                "MANUAL_ONLY",
            ],
            "sources": rows,
        },
        output_class=OutputClass.RESEARCH,
        publication_status="NOT_APPLICABLE",
        data_status="REGISTER" if rows else "REGISTER_UNPARSED (PyYAML absent)",
        endpoint="/sources",
        note=(
            "Zero sources clear the live gate. "
            "A permission refusal is PERMISSION_BLOCKED, never NO_FLIGHT."
        ),
    )


def routes() -> dict[str, Any]:
    p = panel()
    observed = {o.get("route", "DEL-BOM") for o in p["observations"]}
    baskets = []
    for b in declared_baskets():
        d = b.as_dict()
        for r in cast(list[dict[str, Any]], d["routes"]):
            r["observations_held"] = len(p["observations"]) if r["pair"] in observed else 0
        baskets.append(d)
    return envelope(
        {"baskets": baskets, "routes_with_real_observations": sorted(observed)},
        output_class=OutputClass.RESEARCH,
        publication_status="NOT_APPLICABLE",
        data_status="PROVISIONAL_WEIGHTS — OQ-4 open, no DGCA traffic file verified",
        endpoint="/routes",
        note="No basket is publication grade. Equal demo weights are a placeholder, not a finding.",
    )


def observations() -> dict[str, Any]:
    p = panel()
    return envelope(
        {
            "count": len(p["observations"]),
            "collection_date": p["collection_date"],
            "data_class": p["data_class"],
            "frame": p["frame"],
            "evidence_counts": p["quality"]["evidence_counts"],
            "observations": p["observations"],
        },
        output_class=OutputClass.RESEARCH,
        publication_status="NOT_PUBLISHED",
        data_status="REAL_MARKET_OBSERVATION — manual collection, @primary",
        endpoint="/observations",
    )


def index(frequency: Frequency, *, demo: bool = False) -> dict[str, Any]:
    """The index series at one frequency.

    The real panel has no index -- zero matched pairs -- so the production path
    returns an empty series with the readiness verdict. ``demo=True`` returns the
    synthetic fixture's series, labelled DEMO in the envelope.
    """
    if demo:
        pts = sorted(demo_levels().items())
        series = [pp.as_dict() for pp in aggregate(pts, frequency)]
        return envelope(
            {"frequency": frequency.value, "series": series, "source": "synthetic 14-day fixture"},
            output_class=OutputClass.DEMO,
            publication_status="NOT_PUBLISHABLE — SYNTHETIC",
            data_status="SYNTHETIC_FIXTURE",
            endpoint=f"/index/{frequency.value.lower()}?class=demo",
            note="Real arithmetic, real guards, fictional market. Never a measurement.",
        )
    verdict = real_readiness()
    return envelope(
        {
            "frequency": frequency.value,
            "series": [],
            "readiness": verdict.as_dict(),
            "next_unlock": panel()["index_status"]["next_wave_unlocking_index"],
        },
        output_class=verdict.output_class,
        publication_status=verdict.state.value,
        data_status="NO_INDEX — spec C.1 needs a matched t/t-7 pair; one wave held",
        endpoint=f"/index/{frequency.value.lower()}",
    )


def coverage() -> dict[str, Any]:
    p = panel()
    run = scheduled_run()
    return envelope(
        {
            "plan_completion": p["quality"],
            "statistical_coverage": p["quality"]["statistical_coverage"],
            "blocker": p["quality"]["statistical_coverage_blocker"],
            "scheduled_run": run.summary(),
        },
        output_class=OutputClass.RESEARCH,
        publication_status="NOT_ESTABLISHED",
        data_status="AMB-8 OPEN — coverage denominator undefined",
        endpoint="/coverage",
    )


def lead_time() -> dict[str, Any]:
    p = panel()
    profile = p["apw_profile"]
    first = profile[0]["geomean"]
    rows = [
        {
            **a,
            "in_ps_26056_set": a["apw"] in PS_26056_WINDOWS.days,
            "premium_vs_t1_pct": round(100 * (a["geomean"] / first - 1), 2),
        }
        for a in profile
    ]
    return envelope(
        {
            "profile_class": p["apw_profile_class"],
            "disclaimer": p["apw_profile_disclaimer"],
            "confound": p["confound"],
            "window_sets": [s.as_dict() for s in declared_sets()],
            "profile": rows,
        },
        output_class=OutputClass.RESEARCH,
        publication_status="DESCRIPTIVE_ONLY",
        data_status="CROSS_SECTIONAL — each bucket is a different travel date; not an elasticity",
        endpoint="/lead-time",
    )


def provenance(observation_id: str) -> dict[str, Any] | None:
    p = panel()
    obs = next((o for o in p["observations"] if o["observation_id"] == observation_id), None)
    if obs is None:
        return None
    run = next((r for r in p["runs"] if r["run_id"] == obs.get("run_id")), None)
    return envelope(
        {
            "observation": obs,
            "collection_run": run,
            "evidence_class": obs.get("evidence"),
            "methodology_version": run["methodology_version"] if run else METHODOLOGY_VERSION,
            "parser_version": run["parser_version"] if run else None,
            "chain": [
                "screenshot corpus (152) -> collection-input/extract/panel_raw.json",
                "human triage -> exclusions.json / verified.csv",
                "tools/collection/load_manual.py -> data/collection/collection.sqlite3",
                "tools/analysis/build_panel_json.py -> data/panel.json (canonical)",
            ],
        },
        output_class=OutputClass.RESEARCH,
        publication_status="NOT_PUBLISHED",
        data_status="REAL_MARKET_OBSERVATION",
        endpoint=f"/provenance/{observation_id}",
    )


def backtest() -> dict[str, Any]:
    raw = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    base = "2012"
    points = {
        f"{r['year']}-{_MONTHS[r['month']]:02d}": float(r["index"])
        for r in raw["series"].values()
        if r.get("index") is not None and r.get("baseyear") == base and r["month"] in _MONTHS
    }
    bench = BenchmarkSeries(
        benchmark_id=f"mospi_cpi_airfare_base{base}",
        publisher="MoSPI eSankhyiki",
        measures=raw["item"],
        unit=raw["unit"],
        frequency=raw["frequency"],
        points=points,
        provenance=raw["source"],
        is_index_number=True,
    )
    apix_monthly = {
        pp.period: pp.level
        for pp in aggregate(sorted(demo_levels().items()), Frequency.MONTHLY)
        if pp.level is not None
    }
    result = compare(apix_monthly, bench)
    return envelope(
        {
            "dgca_fare_benchmark": {
                "status": DGCA_FARE_BENCHMARK_STATUS,
                "detail": DGCA_FARE_BENCHMARK_DETAIL,
            },
            "fallback_benchmark": {
                "id": bench.benchmark_id,
                "publisher": bench.publisher,
                "measures": bench.measures,
                "unit": bench.unit,
                "declared_frequency": bench.frequency,
                "months_actually_published": sorted({r["month"] for r in raw["series"].values()}),
                "points": len(points),
            },
            "comparison": result.as_dict(),
            "status": "INCOMPLETE",
            "reasons": [
                "PUBLIC BENCHMARK AVAILABILITY: no DGCA average-fare series is published",
                "PUBLIC BENCHMARK GRANULARITY: the held benchmark publishes one month per year",
                "APIx holds no real index series: zero matched t/t-7 pairs",
            ],
        },
        output_class=OutputClass.DEMO,
        publication_status="BACKTEST_INCOMPLETE",
        data_status="FRAMEWORK_COMPLETE — no comparable public data",
        endpoint="/backtest",
    )


def reference() -> dict[str, Any]:
    if not REFERENCE.exists():
        return envelope(
            {"present": False},
            output_class=OutputClass.RESEARCH,
            publication_status="NOT_APPLICABLE",
            data_status="REFERENCE_ABSENT",
            endpoint="/reference",
        )
    r = json.loads(REFERENCE.read_text(encoding="utf-8"))
    return envelope(
        {k: v for k, v in r.items() if k != "basic_fares"}
        | {"basic_fare_rows": r["basic_fares"]["row_count"]},
        output_class=OutputClass.RESEARCH,
        publication_status="NOT_APPLICABLE",
        data_status="REFERENCE_ONLY — INADMISSIBLE — never an observation",
        endpoint="/reference",
    )


def config() -> dict[str, Any]:
    return envelope(
        {
            "apw_window_sets": [s.as_dict() for s in declared_sets()],
            "frozen_vector": list(APIX_FROZEN_WINDOWS.days),
            "ps_26056_vector": list(PS_26056_WINDOWS.days),
            "ps_is_subset_of_frozen": APIX_FROZEN_WINDOWS.covers(PS_26056_WINDOWS),
            "departure_bands": {
                "2": "06:00-08:59",
                "3": "09:00-11:59",
                "4": "12:00-14:59",
                "5": "15:00-17:59",
                "6": "18:00-20:59",
            },
            "egress_policy": DECLARED_EGRESS.as_dict(),
        },
        output_class=OutputClass.RESEARCH,
        publication_status="NOT_APPLICABLE",
        data_status="CONFIGURATION",
        endpoint="/config",
    )


__all__ = [
    "API_VERSION",
    "backtest",
    "config",
    "coverage",
    "envelope",
    "health",
    "index",
    "lead_time",
    "observations",
    "panel",
    "provenance",
    "reference",
    "registry",
    "routes",
    "scheduled_run",
    "sources",
]
