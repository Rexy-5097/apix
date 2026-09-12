"""The advance-purchase profile of the observed panel — Checkpoint 2J.

**This is NOT the APIx index and must never be presented as one.**

Spec C.1 is LOCKED: every APIx-L relative compares collection date `t` against
`t-7`, and `I(c,t) = I(c,t-7) * J(c,t)`. This panel has ONE collection date
(2026-09-12), so the matched set `M(c,t)` is empty for every cell and no Jevons
relative, no chained level and no published index value exists. That is a
property of the data, not a gap in the implementation, and collecting harder on
one day cannot fix it.

What one collection date DOES support is a genuine cross-sectional measurement:
how the fare for the same route and carrier varies with **advance-purchase
distance** and with **departure band**. That is a real empirical finding, it is
what the frozen APW vector was designed to sample, and it is reported here as a
profile — a set of levels and cross-sectional ratios — never as a time series.

The geometric mean is used because spec D.2 makes it the elementary aggregator;
using it here keeps the arithmetic consistent with the index that will later be
computed from the same observations. It does not make the result an index.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from apix.ingestion.store import open_store

COLLECTION_DATE = date(2026, 9, 12)
STORE = Path(__file__).resolve().parents[2] / "data" / "collection"
# Spec A.3, frozen.
PRODUCTION_APW = (1, 3, 7, 15, 30, 45, 60)


def geomean(values: list[float]) -> float:
    return math.exp(sum(math.log(v) for v in values) / len(values))


def main() -> None:
    store = open_store(STORE)
    try:
        obs = store.observations(COLLECTION_DATE)
    finally:
        store.close()

    by_apw: dict[int, list] = defaultdict(list)
    for o in obs:
        by_apw[o.lead_time_days].append(o)

    print("APIx — observed advance-purchase profile")
    print("DEL-BOM · IndiGo 6E · Saver · 1 adult · non-stop · collected 2026-09-12")
    print("REAL MARKET DATA. Not an index. Not a time series.\n")

    print(
        f"{'APW':<7}{'travel date':<14}{'n':<4}{'geo mean':>11}"
        f"{'min':>9}{'max':>9}{'spread':>9}   vs T+1"
    )
    print("-" * 78)

    profile = {}
    base = None
    for apw in sorted(by_apw):
        rows = by_apw[apw]
        fares = [float(o.payable_fare) for o in rows]
        g = geomean(fares)
        if base is None:
            base = g
        rel = g / base
        profile[apw] = {
            "travel_date": rows[0].travel_date.isoformat(),
            "n": len(rows),
            "geomean": round(g, 2),
            "min": min(fares),
            "max": max(fares),
            "spread_pct": round(100 * (max(fares) / min(fares) - 1), 1),
            "relative_to_t1": round(rel, 4),
        }
        print(
            f"T+{apw:<5}{rows[0].travel_date.isoformat():<14}{len(rows):<4}"
            f"{g:>11,.0f}{min(fares):>9,.0f}{max(fares):>9,.0f}"
            f"{profile[apw]['spread_pct']:>8.1f}%{rel:>9.3f}"
        )

    missing = [a for a in PRODUCTION_APW if a not in by_apw]
    print(f"\nproduction APW buckets: {list(PRODUCTION_APW)}")
    print(f"observed               : {sorted(by_apw)}")
    print(f"MISSING                : {missing}  <- not collected; no substitute exists")

    # Departure band structure, pooled across APW.
    print(f"\n{'band':<6}{'window':<16}{'n':<4}{'geo mean':>11}")
    print("-" * 40)
    by_band: dict[int, list[float]] = defaultdict(list)
    for o in obs:
        by_band[o.departure_hour_band].append(float(o.payable_fare))
    windows = {
        2: "06:00-08:59",
        3: "09:00-11:59",
        4: "12:00-14:59",
        5: "15:00-17:59",
        6: "18:00-20:59",
    }
    band_profile = {}
    for b in sorted(by_band):
        g = geomean(by_band[b])
        band_profile[b] = {"n": len(by_band[b]), "geomean": round(g, 2)}
        print(f"{b:<6}{windows.get(b, '?'):<16}{len(by_band[b]):<4}{g:>11,.0f}")

    # What the index would need, stated explicitly rather than approximated.
    print("\nIndex feasibility (spec C.1, LOCKED):")
    print(f"  collection dates in store      : 1 ({COLLECTION_DATE})")
    print("  matched pairs M(c,t) available : 0  — requires t and t-7")
    print("  APIx-L index value             : NOT COMPUTABLE")
    print(
        f"  APIx-TPD                       : NOT COMPUTABLE "
        f"(min_quotes_window = 1,500; have {len(obs)})"
    )

    out = {
        "collection_date": COLLECTION_DATE.isoformat(),
        "route": "DEL-BOM",
        "carrier": "6E",
        "fare_family": "Saver",
        "data_class": "REAL_MARKET_OBSERVATION",
        "is_index": False,
        "is_time_series": False,
        "n_observations": len(obs),
        "apw_profile": profile,
        "band_profile": band_profile,
        "missing_apw": missing,
        "index_computable": False,
        "index_blocker": (
            "spec C.1 requires t vs t-7; one collection date yields zero matched pairs"
        ),
    }
    dest = Path(__file__).resolve().parents[2] / "data" / "apw_profile.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\nwritten: {dest.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
