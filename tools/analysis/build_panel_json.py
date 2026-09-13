"""Build `data/panel.json` — the single contract the dashboard renders from.

Everything downstream reads this file and nothing types a figure by hand. The
dashboard was previously hand-authored HTML with numbers written into it, and
two of them went stale (a base-year mixing error and a series count) before a
text cross-check caught them. Generating the figures removes the failure mode
rather than re-checking for it.

    store (SQLite)  ->  this module  ->  data/panel.json  ->  dashboard + report

**Evidence grade is computed here, not asserted.** An observation is
PRIMARY_HASHED only if its run actually has a content-addressed artifact bound
to it; everything else is SECONDARY_CHAT_IMAGE. That makes the weaker T+45
provenance a derived fact rather than a label someone remembered to apply.
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from execution_boundary import build_boundary  # noqa: E402
from replay_exclusions import replay  # noqa: E402

from apix.ingestion.store import open_store  # noqa: E402
from apix.schemas.enums import APWBucket  # noqa: E402

COLLECTION_DATE = date(2026, 9, 12)
STORE = ROOT / "data" / "collection"
OUT = ROOT / "data" / "panel.json"

#: Spec A.3, frozen. Read from the enum so the two can never drift.
PRODUCTION_APW = tuple(b.value for b in APWBucket)
#: Spec B.2 bands the Day-1 contract collects. 3-hour bands anchored at 00:00.
CONTRACT_BANDS = (2, 3, 4, 5, 6)
BAND_WINDOWS = {b: f"{3 * b:02d}:00-{3 * b + 2:02d}:59" for b in CONTRACT_BANDS}

PRIMARY = "PRIMARY_HASHED"
SECONDARY = "SECONDARY_CHAT_IMAGE"


def geomean(v: list[float]) -> float:
    """Geometric mean of *levels*, in logs — the same form spec D.2 uses.

    **This is not a D.2 relative and the index engine does not produce it.**
    D.2 aggregates price *relatives* across a matched pair of collection dates;
    with one wave there is no pair, so there is nothing for the engine to
    compute. What this summarises is a single wave's levels, descriptively.

    The log form is kept deliberately so that the descriptive summary and
    `apix.statistics.elementary.jevons` cannot drift into different arithmetic.
    `test_panel_geomean_matches_the_spec_d2_log_form` asserts the agreement on
    the real panel rather than leaving it to a comment.
    """
    return math.exp(sum(math.log(x) for x in v) / len(v))


def build() -> dict:
    store = open_store(STORE)
    obs = store.observations(COLLECTION_DATE)
    runs = store.runs()
    artifacts = store.artifact_refs()
    flags = store.verify()
    store.close()

    con = sqlite3.connect(STORE / "collection.sqlite3")
    run_of = dict(con.execute("SELECT observation_id, run_id FROM canonical_observation"))
    # A run is PRIMARY only if it actually has artifacts bound to it.
    runs_with_artifacts = {a.run_id for a in artifacts}

    def grade(o) -> str:
        return PRIMARY if run_of[o.observation_id] in runs_with_artifacts else SECONDARY

    # ── observations ──────────────────────────────────────────────────────
    rows = []
    for o in sorted(obs, key=lambda o: (o.lead_time_days, o.departure_time_local)):
        fb = o.fare_breakdown
        base = float(fb.base_fare) if fb.base_fare else None
        tax = float(fb.taxes) if fb.taxes else None
        total = float(o.payable_fare)
        rows.append(
            {
                "observation_id": o.observation_id,
                "apw": o.lead_time_days,
                "travel_date": o.travel_date.isoformat(),
                "day_of_week": o.travel_date.strftime("%a"),
                "band": o.departure_hour_band,
                "band_window": BAND_WINDOWS.get(o.departure_hour_band, "?"),
                "carrier": o.carrier,
                "flight": f"{o.carrier} {o.flight_number}",
                "route": o.route,
                "dep": o.departure_time_local.strftime("%H:%M"),
                "duration_min": o.duration_minutes,
                "stops": o.stops,
                "fare_family_raw": o.fare_family_raw,
                "fare_class": o.fare_class.value,
                "checked_baggage_kg": o.entitlements.checked_baggage_kg,
                "base": base,
                "tax": tax,
                "total": total,
                "reconciles": base is not None and tax is not None and base + tax == total,
                "observed_at": o.observation_ts.strftime("%H:%M"),
                "evidence": grade(o),
                "run_id": run_of[o.observation_id],
            }
        )

    # ── APW profile ───────────────────────────────────────────────────────
    # DESCRIPTIVE ONLY. Each bucket sits on a different travel date, so these
    # are seven cross-sections, not a time series. `rel_to_first` is a ratio of
    # two such cross-sections and is NOT a price relative in the spec D.2 sense.
    rows_by_apw: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        rows_by_apw[r["apw"]].append(r)

    def cheapest(rs: list[dict]) -> dict:
        return min(rs, key=lambda r: r["total"])

    def dearest(rs: list[dict]) -> dict:
        return max(rs, key=lambda r: r["total"])

    def cite(r: dict) -> dict:
        """The audit trail behind a min/max — so a spread traces to real rows."""
        return {
            "observation_id": r["observation_id"],
            "flight": r["flight"],
            "dep": r["dep"],
            "band": r["band"],
            "total": r["total"],
        }

    base_g = geomean([r["total"] for r in rows_by_apw[min(rows_by_apw)]]) if rows_by_apw else 1.0
    apw_profile = []
    for a in sorted(rows_by_apw):
        rs = rows_by_apw[a]
        f = [r["total"] for r in rs]
        g = geomean(f)
        apw_profile.append(
            {
                "apw": a,
                "travel_date": rs[0]["travel_date"],
                "day_of_week": rs[0]["day_of_week"],
                "n": len(f),
                "geomean": round(g, 2),
                "min": min(f),
                "max": max(f),
                "spread_pct": round(100 * (max(f) / min(f) - 1), 1),
                "min_obs": cite(cheapest(rs)),
                "max_obs": cite(dearest(rs)),
                "rel_to_first": round(g / base_g, 4),
            }
        )

    # ── dispersion — which bucket is widest, and what drives it ───────────
    widest = max(apw_profile, key=lambda a: a["spread_pct"]) if apw_profile else None
    dispersion = {
        "widest_apw": widest["apw"] if widest else None,
        "widest_spread_pct": widest["spread_pct"] if widest else None,
        "widest_min_obs": widest["min_obs"] if widest else None,
        "widest_max_obs": widest["max_obs"] if widest else None,
        "others_max_spread_pct": (
            max((a["spread_pct"] for a in apw_profile if a is not widest), default=None)
            if widest
            else None
        ),
        # The panel establishes the dispersion. It does not establish a cause,
        # and there is no anomaly-detection definition in force that would let
        # this be called an anomaly.
        "cause_established": False,
        "statement": (
            "Observed within-bucket dispersion. The panel establishes the "
            "dispersion; it does not establish its cause."
        ),
    }

    # ── lead time is confounded with travel date / weekday ────────────────
    weekday_by_apw = {a["apw"]: a["day_of_week"] for a in apw_profile}
    dow_counts: dict[str, int] = defaultdict(int)
    for d in weekday_by_apw.values():
        dow_counts[d] += 1
    confound = {
        "weekday_by_apw": weekday_by_apw,
        "distinct_weekdays": len(dow_counts),
        "repeated_weekdays": {d: n for d, n in sorted(dow_counts.items()) if n > 1},
        "lead_time_confounded": len(dow_counts) < len(weekday_by_apw),
        "statement": (
            "Advance-purchase buckets are not interchangeable time observations. "
            "In this panel lead time is confounded with travel date / day-of-week, "
            "so the APW profile is descriptive and is not an inflation measure."
        ),
    }

    # ── band profile ──────────────────────────────────────────────────────
    by_band: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        by_band[r["band"]].append(r["total"])
    band_profile = [
        {
            "band": b,
            "window": BAND_WINDOWS.get(b, "?"),
            "n": len(by_band[b]),
            "geomean": round(geomean(by_band[b]), 2),
        }
        for b in sorted(by_band)
    ]
    bg = [x["geomean"] for x in band_profile]

    # ── quality ───────────────────────────────────────────────────────────
    # **This is collection-plan completion, NOT statistical coverage.**
    #
    # `plan_slots` is what the Day-1 collection contract asked for: 7 frozen APW
    # buckets x 5 contract bands. Filling all of it says the collector did what
    # it was told. It says nothing about spec I's `min_route_coverage`, whose
    # denominator -- "expected cells" -- is undefined. That is AMB-8, still open.
    # Calling this "coverage" would borrow a statistical meaning the number
    # cannot carry, so the field names, the report and the dashboard all avoid
    # the word. Do not reintroduce it here.
    plan_slots = len(PRODUCTION_APW) * len(CONTRACT_BANDS)
    observed_apw = sorted(rows_by_apw)
    ev = defaultdict(int)
    for r in rows:
        ev[r["evidence"]] += 1

    quality = {
        "plan_slots": plan_slots,
        "valid_observations": len(rows),
        "plan_completion_pct": round(100 * len(rows) / plan_slots, 1),
        "plan_slots_unfilled": plan_slots - len(rows),
        "plan_basis": f"{len(PRODUCTION_APW)} frozen APW buckets x {len(CONTRACT_BANDS)} bands",
        "statistical_coverage": "NOT_ESTABLISHED",
        "statistical_coverage_blocker": (
            "AMB-8 OPEN: spec I gates on '60% of expected cells' and nothing "
            "defines an expected cell. No denominator has been chosen, so no "
            "statistical coverage figure is computed."
        ),
        "reconciled": sum(1 for r in rows if r["reconciles"]),
        "decomposed": sum(1 for r in rows if r["base"] is not None),
        "apw_expected": list(PRODUCTION_APW),
        "apw_observed": observed_apw,
        "apw_missing": [a for a in PRODUCTION_APW if a not in observed_apw],
        "bands_expected": list(CONTRACT_BANDS),
        "bands_observed": sorted(by_band),
        "artifacts": len(artifacts),
        "window_flags": len(flags),
        "window_flag_detail": flags,
        "evidence_counts": dict(ev),
    }

    # ── index feasibility — derived, never asserted ───────────────────────
    collection_dates = sorted({o.collection_date for o in obs})
    needed = {d.toordinal() - 7 for d in collection_dates}
    have = {d.toordinal() for d in collection_dates}
    index_status = {
        "collection_waves": len(collection_dates),
        "collection_dates": [d.isoformat() for d in collection_dates],
        "matched_pairs_available": len(needed & have),
        "apix_l_computable": bool(needed & have),
        "apix_l_blocker": (
            "spec C.1 LOCKED: I(c,t) = I(c,t-7) x J(c,t). "
            f"Have {len(collection_dates)} collection wave(s); no t-7 counterpart exists."
        ),
        "tpd_min_quotes_window": 1500,
        "tpd_quotes_available": len(rows),
        "tpd_computable": len(rows) >= 1500,
        "next_wave_unlocking_index": (
            (collection_dates[0].toordinal() + 7) if collection_dates else None
        ),
    }
    if index_status["next_wave_unlocking_index"]:
        index_status["next_wave_unlocking_index"] = date.fromordinal(
            index_status["next_wave_unlocking_index"]
        ).isoformat()

    # ── runs / version vector ─────────────────────────────────────────────
    run_meta = [
        {
            "run_id": r.run_id,
            "collection_date": r.collection_date.isoformat(),
            "window_declared": f"{r.collection_window_start:%H:%M}-{r.collection_window_end:%H:%M}",
            "collector": r.collector_identity,
            "methodology_version": r.methodology_version,
            "basket_version": r.basket_version,
            "parser_version": r.parser_version,
            "collector_version": r.collector_version,
            "protocol_version": r.protocol_version,
            "source_precedence_version": r.source_precedence_version,
            "frame_id": r.frame_id,
            "notes": r.notes,
            "observations": sum(1 for x in rows if x["run_id"] == r.run_id),
            "evidence": PRIMARY if r.run_id in runs_with_artifacts else SECONDARY,
        }
        for r in runs
    ]

    # ── exclusions ────────────────────────────────────────────────────────
    excl_path = ROOT / "collection-input" / "extract" / "exclusions.json"
    excl_raw = json.loads(excl_path.read_text(encoding="utf-8")) if excl_path.exists() else {}
    exclusions = sorted(
        ({"reason": k, "count": len(v), "shots": v} for k, v in excl_raw.items()),
        key=lambda x: -x["count"],
    )

    # ── benchmark ─────────────────────────────────────────────────────────
    bpath = ROOT / "data" / "mospi_cpi_airfare.json"
    bench = json.loads(bpath.read_text(encoding="utf-8")) if bpath.exists() else {}
    series = list(bench.get("series", {}).values())
    by_base: dict[str, list] = defaultdict(list)
    for r in series:
        by_base[r["baseyear"]].append(r)
    growth = []
    for b in sorted(by_base):
        v = sorted(by_base[b], key=lambda r: r["year"])
        if len(v) < 2:
            growth.append({"baseyear": b, "points": len(v), "cagr_pct": None})
            continue
        g = v[-1]["index"] / v[0]["index"]
        yrs = v[-1]["year"] - v[0]["year"]
        growth.append(
            {
                "baseyear": b,
                "points": len(v),
                "first_year": v[0]["year"],
                "last_year": v[-1]["year"],
                "first": v[0]["index"],
                "last": v[-1]["index"],
                "ratio": round(g, 3),
                "years": yrs,
                "cagr_pct": round(100 * (g ** (1 / yrs) - 1), 2),
            }
        )

    return {
        "generated_from": "data/collection/collection.sqlite3",
        "data_class": "REAL_MARKET_OBSERVATION",
        "synthetic_data_present": False,
        "collection_date": COLLECTION_DATE.isoformat(),
        "frame": {
            "routes": sorted({r["route"] for r in rows}),
            "carriers": sorted({r["carrier"] for r in rows}),
            "fare_families": sorted({r["fare_family_raw"] for r in rows}),
            "fare_classes": sorted({r["fare_class"] for r in rows}),
            "channel": "AIRLINE_DIRECT",
            "passengers": "1 adult, one-way, economy, non-stop",
        },
        "runs": run_meta,
        "observations": rows,
        "apw_profile": apw_profile,
        "apw_profile_class": "DESCRIPTIVE_CROSS_SECTION",
        "apw_profile_disclaimer": (
            "DESCRIPTIVE APW PROFILE - NOT AN INDEX. Each bucket is a separate "
            "cross-section on a different travel date. Differences between "
            "buckets are not temporal price movements and are not inflation."
        ),
        "dispersion": dispersion,
        "confound": confound,
        "band_profile": band_profile,
        "band_spread_pct": round(100 * (max(bg) / min(bg) - 1), 1) if bg else None,
        "quality": quality,
        "index_status": index_status,
        "exclusions": exclusions,
        "exclusions_total": sum(e["count"] for e in exclusions),
        "benchmark": {
            "source": bench.get("source"),
            "item": bench.get("item"),
            "role": bench.get("role"),
            "is_apix_input": bench.get("is_apix_input"),
            "unit": bench.get("unit"),
            "series": sorted(series, key=lambda r: (r["baseyear"], r["year"])),
            "growth_by_base": growth,
        },
    }


def main() -> None:
    panel = build()
    # Both are derived from the panel that was just built, so the contract can
    # never carry a boundary describing a different dataset. Neither writes.
    panel["replay"] = replay(panel).as_dict()
    panel["execution_boundary"] = build_boundary(panel)
    OUT.write_text(json.dumps(panel, indent=1), encoding="utf-8")
    q = panel["quality"]
    i = panel["index_status"]
    print(
        f"observations      {q['valid_observations']}/{q['plan_slots']} "
        f"({q['plan_completion_pct']}% of collection plan)"
    )
    print(f"stat. coverage    {q['statistical_coverage']}  (AMB-8 open)")
    print(f"APW               {q['apw_observed']} | missing {q['apw_missing'] or 'none'}")
    print(f"reconciled        {q['reconciled']}/{q['decomposed']}")
    print(f"evidence          {q['evidence_counts']}")
    print(f"index computable  {i['apix_l_computable']}  (waves={i['collection_waves']})")
    r = panel["replay"]
    print(f"exclusion replay  {r['agree']}/{r['candidates']} agree, {r['disagree']} disagree")
    print(f"exec boundary     {panel['execution_boundary']['state_counts']}")
    print(f"written           {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
