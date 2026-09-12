"""Render the observed panel as plain text, straight from the store.

This exists to be checked against the dashboard. The dashboard is hand-authored
HTML with figures written into it; this reads the SQLite store and the analysis
JSON and recomputes everything. If the two agree, the dashboard is verified; if
they disagree, the store wins and the dashboard is wrong.
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

from apix.ingestion.store import open_store  # noqa: E402

COLLECTION_DATE = date(2026, 9, 12)
PRODUCTION_APW = (1, 3, 7, 15, 30, 45, 60)
BANDS = {
    2: "06:00-08:59",
    3: "09:00-11:59",
    4: "12:00-14:59",
    5: "15:00-17:59",
    6: "18:00-20:59",
}


def geomean(v: list[float]) -> float:
    return math.exp(sum(math.log(x) for x in v) / len(v))


def rule(ch: str = "-", n: int = 78) -> str:
    return ch * n


def main() -> None:
    store = open_store(ROOT / "data" / "collection")
    obs = store.observations(COLLECTION_DATE)
    runs = store.runs()
    artifacts = store.artifact_refs()
    flags = store.verify()
    store.close()

    con = sqlite3.connect(ROOT / "data" / "collection" / "collection.sqlite3")
    run_of = dict(con.execute("SELECT observation_id, run_id FROM canonical_observation"))

    out: list[str] = []
    w = out.append

    w(rule("="))
    w("APIx - OBSERVED PANEL   (text rendering of the dashboard, generated from the store)")
    w(rule("="))
    w("Route DEL-BOM | Carrier IndiGo 6E | Saver fare | 1 adult | one-way | non-stop")
    w(f"Collected {COLLECTION_DATE} | methodology 2.1 | DATA CLASS: REAL MARKET OBSERVATION")
    w("")
    w("ESTABLISHED      The complete advance-purchase vector: all 7 frozen A.3 buckets.")
    w("NOT ESTABLISHED  Any index value. Spec C.1 is LOCKED: I(c,t) = I(c,t-7) * J(c,t).")
    w("                 One collection date => matched set M(c,t) is empty => no relative.")
    w("")

    # ---- APW profile -------------------------------------------------------
    by_apw: dict[int, list] = defaultdict(list)
    for o in obs:
        by_apw[o.lead_time_days].append(o)

    w(rule("="))
    w("1. ADVANCE-PURCHASE PROFILE   (geometric mean of the 5 band fares, spec D.2)")
    w(rule("="))
    w(
        f"{'APW':<7}{'travel date':<14}{'n':<4}{'geo mean':>10}{'min':>9}{'max':>9}"
        f"{'spread':>9}{'vs T+1':>9}"
    )
    w(rule())
    base = None
    for apw in sorted(by_apw):
        fares = [float(o.payable_fare) for o in by_apw[apw]]
        g = geomean(fares)
        base = base or g
        w(
            f"T+{apw:<5}{by_apw[apw][0].travel_date.isoformat():<14}{len(fares):<4}"
            f"{g:>10,.0f}{min(fares):>9,.0f}{max(fares):>9,.0f}"
            f"{100 * (max(fares) / min(fares) - 1):>8.1f}%{g / base:>9.3f}"
        )
    w("")
    w(f"production buckets (A.3): {list(PRODUCTION_APW)}")
    w(f"observed                : {sorted(by_apw)}")
    w(f"missing                 : {[a for a in PRODUCTION_APW if a not in by_apw] or 'NONE'}")
    w("")

    # ---- quality -----------------------------------------------------------
    decomposed = sum(1 for o in obs if o.fare_breakdown.base_fare)
    reconciles = sum(
        1
        for o in obs
        if o.fare_breakdown.base_fare
        and o.fare_breakdown.base_fare + o.fare_breakdown.taxes == o.payable_fare
    )
    expected = len(PRODUCTION_APW) * len(BANDS)
    w(rule("="))
    w("2. DATA QUALITY")
    w(rule("="))
    w(f"  valid observations        {len(obs)}")
    w(f"  expected cells            {expected}   (7 APW x 5 bands)")
    w(f"  coverage                  {100 * len(obs) / expected:.1f}%")
    w(f"  missing cells             {expected - len(obs)}")
    w(f"  fully decomposed          {decomposed}/{len(obs)}")
    w(f"  base + tax == total       {reconciles}/{decomposed}")
    w(f"  runs                      {len(runs)}")
    w(f"  artifacts (SHA-256)       {len(artifacts)}")
    w(f"  spec A.5 window flags     {len(flags)}   (stored + flagged, never discarded)")
    w("")
    for r in runs:
        w(f"  run {r.run_id}")
        w(
            f"      window declared {r.collection_window_start:%H:%M}-"
            f"{r.collection_window_end:%H:%M} | collector {r.collector_identity}"
        )
        w(f"      notes: {r.notes}")
    w("")

    # ---- the observations --------------------------------------------------
    w(rule("="))
    w(f"3. THE {len(obs)} OBSERVATIONS")
    w(rule("="))
    w(
        f"{'APW':<6}{'travel date':<13}{'bd':<4}{'flight':<10}{'dep':<7}{'min':>5}"
        f"{'base':>9}{'tax+fees':>10}{'TOTAL':>9}  {'seen':<7}evidence"
    )
    w(rule("-", 92))
    for o in sorted(obs, key=lambda o: (o.lead_time_days, o.departure_time_local)):
        fb = o.fare_breakdown
        hashed = run_of[o.observation_id] == "run-20260912-primary"
        w(
            f"T+{o.lead_time_days:<4}{o.travel_date.isoformat():<13}{o.departure_hour_band:<4}"
            f"6E {o.flight_number:<7}{o.departure_time_local:%H:%M}  {o.duration_minutes:>4}"
            f"{float(fb.base_fare):>9,.0f}{float(fb.taxes):>10,.0f}"
            f"{float(o.payable_fare):>9,.0f}  {o.observation_ts:%H:%M}   "
            f"{'SHA-256' if hashed else 'nominal'}"
        )
    w("")
    w("  evidence  SHA-256 = bound to a hash-addressed screenshot in the store")
    w("            nominal = supplied as chat image; no bytes hashed, capture time is a")
    w("                      placeholder. Collection date confirmed by the collector.")
    w("")

    # ---- bands -------------------------------------------------------------
    by_band: dict[int, list[float]] = defaultdict(list)
    for o in obs:
        by_band[o.departure_hour_band].append(float(o.payable_fare))
    w(rule("="))
    w("4. DEPARTURE-BAND STRUCTURE   (spec B.2, 3-hour bands anchored at 00:00 IST)")
    w(rule("="))
    w(f"{'band':<6}{'window':<16}{'n':<4}{'geo mean':>10}")
    w(rule("-", 40))
    gs = []
    for b in sorted(by_band):
        g = geomean(by_band[b])
        gs.append(g)
        w(f"{b:<6}{BANDS.get(b, '?'):<16}{len(by_band[b]):<4}{g:>10,.0f}")
    w("")
    w(
        f"  spread across bands: {100 * (max(gs) / min(gs) - 1):.1f}%  "
        f"(pooled across APW, so confounded by the T+60 level)"
    )
    w("")

    # ---- exclusions --------------------------------------------------------
    excl = json.loads((ROOT / "collection-input" / "extract" / "exclusions.json").read_text())
    w(rule("="))
    w("5. EXCLUSION AUDIT   (nothing deleted; every excluded shot carries a reason)")
    w(rule("="))
    total_excl = sum(len(v) for v in excl.values())
    for reason, shots in sorted(excl.items(), key=lambda kv: -len(kv[1])):
        w(f"  {len(shots):>4}  {reason}")
    w(rule("-", 78))
    w(f"  {total_excl:>4}  total excluded from the 12-Sep file corpus (152 screenshots)")
    w("")
    w("  The 27-Oct (T+45) batch arrived separately as 24 chat images: 5 selected,")
    w("  14 not-earliest-in-band, 5 outside bands 2-6.")
    w("")

    # ---- benchmark ---------------------------------------------------------
    bench = json.loads((ROOT / "data" / "mospi_cpi_airfare.json").read_text())
    series = sorted(bench["series"].values(), key=lambda r: r["year"])
    w(rule("="))
    w("6. OFFICIAL BENCHMARK - MoSPI eSankhyiki")
    w(rule("="))
    w(f"  source  {bench['source']}")
    w(f"  item    {bench['item']}")
    w(f"  role    {bench['role']}   is_apix_input={bench['is_apix_input']}")
    w(f"  unit    {bench['unit']} | {bench['frequency']} | {bench['geography']}")
    w("")
    w(f"  {'period':<18}{'base':>6}{'index':>8}{'y/y':>9}")
    w(rule("-", 43))
    for r in sorted(series, key=lambda r: (r["baseyear"], r["year"])):
        infl = "-" if r["inflation"] is None else f"{r['inflation']:.2f}%"
        w(f"  {r['year']}-{r['month']:<12}{r['baseyear']:>6}{r['index']:>8.1f}{infl:>9}")
    w("")
    by_base: dict[str, list] = {}
    for r in series:
        by_base.setdefault(r["baseyear"], []).append(r)
    for b in sorted(by_base):
        v = sorted(by_base[b], key=lambda r: r["year"])
        if len(v) < 2:
            w(f"  base {b}: 1 point — no growth rate computable")
            continue
        g = v[-1]["index"] / v[0]["index"]
        yrs = v[-1]["year"] - v[0]["year"]
        w(
            f"  base {b}: {v[0]['index']} -> {v[-1]['index']} over {yrs} years "
            f"= {g:.3f}x = {100 * (g ** (1 / yrs) - 1):.2f}%/yr geometric"
        )
    w("")
    w("  Growth is computed WITHIN a base year only. MoSPI publishes Dec 2014 under")
    w("  both base 2010 and base 2012 during the rebasing overlap; dividing one by")
    w("  the other is a units error, not a rate of change.")
    w("")
    w("  CANNOT validate this panel: a monthly All-India index number has no route,")
    w("  carrier, flight or rupee fare. No overlapping unit exists. Carried as the")
    w("  external reference the index will eventually be validated against.")
    w("")

    # ---- not established ---------------------------------------------------
    w(rule("="))
    w("7. WHAT IS NOT ESTABLISHED")
    w(rule("="))
    rows = [
        (
            "APIx-L index value",
            "NOT COMPUTABLE",
            "a 2nd collection date exactly 7 days later (C.1)",
        ),
        ("APIx-TPD estimate", "NOT COMPUTABLE", f"min_quotes_window=1,500; panel has {len(obs)}"),
        ("30-day back-test", "NOT PERFORMED", "daily fare history we do not have"),
        ("National representativeness", "NO", "1 route of 2,186; 1 carrier of 5"),
        ("Route weights (G)", "NOT EXERCISED", ">=2 routes + DGCA city-pair volumes"),
        ("Carrier allocation", "OPEN - AMB-9", "owner ruling; moot at one carrier"),
        ("Coverage denominator", "OPEN - AMB-8", "owner ruling on expected cells"),
        ("Intraday effect (OQ-1)", "DEFERRED", "paired 09:00/21:00 runs not collected"),
        (
            "Fare 4-way split (A.4)",
            "OPEN - AMB-12",
            "IndiGo shows one aggregated Taxes & Fees line",
        ),
        ("Collection pipeline", "DEMONSTRATED", "on real data, with hashed evidence"),
        ("Advance-purchase measurement", "DEMONSTRATED", "all 7 frozen APW buckets"),
    ]
    for claim, status, need in rows:
        w(f"  {claim:<30}{status:<17}{need}")
    w("")
    w(rule("="))
    w("Generated from data/collection/collection.sqlite3 + data/*.json.")
    w("If this disagrees with the dashboard, the store is correct.")
    w(rule("="))

    text = "\n".join(out)
    dest = ROOT / "data" / "panel_report.txt"
    dest.write_text(text, encoding="utf-8")
    print(text)
    print(f"\n[written: {dest}]")


if __name__ == "__main__":
    main()
