#!/usr/bin/env python3
"""Measure APIx-L runtime at realistic scale.

The dossier's planning estimate is **20,000-35,000 quotes per day at full
frame** (section 06), described there as small data whose difficulty is
comparability rather than volume. This script checks that claim holds for the
deterministic core rather than assuming it.

It also matters for a *later* checkpoint: spec N.4 (OQ-5) requires the bootstrap
runtime to be measured before a confidence interval is promised on screen, and
the bootstrap recomputes the entire index path 1000 times. The per-path cost
measured here is the multiplicand in that budget.

Run:  python tools/ci/benchmark_apix_l.py
"""

from __future__ import annotations

import time as clock
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from apix.schemas.enums import (
    APWBucket,
    CellStatus,
    ChangePolicy,
    Channel,
    SourceType,
    Tier,
)
from apix.schemas.keys import CellKey
from apix.schemas.observation import Entitlements, Observation
from apix.schemas.results import CellState
from apix.schemas.version_vector import VersionVector
from apix.statistics.elementary.admissibility import filter_admissible
from apix.statistics.elementary.dedup import deduplicate
from apix.statistics.elementary.jevons import compute_jevons
from apix.statistics.elementary.matching import build_matched_set, cell_key_for
from apix.statistics.index.apix_l import calculate_apix_l, cell_id

T = date(2026, 9, 8)
ROUTES = [
    f"{o}-{d}" for o in ("DEL", "BOM", "BLR", "MAA", "CCU") for d in ("HYD", "GOI", "PNQ", "AMD")
]
CARRIERS = ("6E", "AI", "IX", "QP", "SG")


def synth_observations(collection: date, flights_per_cell: int = 4) -> list[Observation]:
    """Build a synthetic day at roughly full-frame size.

    Deterministic by construction — no RNG, because spec P.2 forbids unseeded
    stochastic procedures anywhere near the statistics layer, and a benchmark
    whose input changes between runs cannot be compared with itself.
    """
    out: list[Observation] = []
    n = 0
    for route in ROUTES:
        origin, destination = route.split("-")
        for carrier in CARRIERS:
            for bucket in APWBucket:
                for slot in range(flights_per_cell):
                    n += 1
                    # A smooth, repeatable price surface; no randomness.
                    fare = 3000 + (n % 97) * 53 + bucket.value * 11
                    out.append(
                        Observation(
                            observation_id=f"{collection.isoformat()}-{n:06d}",
                            origin=origin,
                            destination=destination,
                            travel_date=collection + timedelta(days=bucket.value),
                            departure_time_local=time(6 + (slot * 4) % 18, 0),
                            observation_ts=datetime.combine(collection, time(6, 0)),
                            collection_date=collection,
                            carrier=carrier,
                            flight_number=f"{100 + slot}",
                            stops=0,
                            duration_minutes=120,
                            fare_family_raw="SAVER",
                            channel=Channel.AIRLINE_DIRECT,
                            source_id=carrier.lower(),
                            entitlements=Entitlements(15, ChangePolicy.FEE, ChangePolicy.FEE),
                            payable_fare=Decimal(f"{fare}.00"),
                            source_type=SourceType.SYNTHETIC,
                        )
                    )
    return out


def main() -> int:
    today = synth_observations(T)
    prior = synth_observations(T - timedelta(days=7))
    print(f"synthetic quotes: {len(today):,} at t, {len(prior):,} at t-7")

    started = clock.perf_counter()
    adm_t = filter_admissible(today).admissible
    adm_p = filter_admissible(prior).admissible
    dedup_t = deduplicate(adm_t).retained
    dedup_p = deduplicate(adm_p).retained
    ingest_s = clock.perf_counter() - started
    print(f"admissibility + dedup      : {ingest_s:7.3f}s  ({len(dedup_t):,} admissible)")

    started = clock.perf_counter()
    by_cell: dict[CellKey, list[Observation]] = {}
    for o in dedup_t:
        by_cell.setdefault(cell_key_for(o, Tier.TIER_1), []).append(o)
    prior_by_cell: dict[CellKey, list[Observation]] = {}
    for o in dedup_p:
        prior_by_cell.setdefault(cell_key_for(o, Tier.TIER_1), []).append(o)
    assign_s = clock.perf_counter() - started
    print(f"cell assignment            : {assign_s:7.3f}s  ({len(by_cell):,} cells)")

    started = clock.perf_counter()
    states: list[CellState] = []
    matched_total = 0
    for key in sorted(by_cell, key=lambda k: k.sort_key):
        pairs = build_matched_set(by_cell[key], prior_by_cell.get(key, []), key, Tier.TIER_1)
        matched_total += len(pairs)
        result = compute_jevons(key, T, pairs)
        level = 100.0 * (result.relative or 1.0)
        states.append(
            CellState(
                cell=key,
                collection_date=T,
                level=level,
                status=CellStatus.PUBLISHED if result.is_defined else CellStatus.CARRIED,
                last_relative=result.relative,
                last_matched_date=T,
            )
        )
    elementary_s = clock.perf_counter() - started
    print(f"matching + Jevons          : {elementary_s:7.3f}s  ({matched_total:,} matched items)")

    cell_weights = {cell_id(s.cell): 1.0 for s in states}
    route_weights = dict.fromkeys(ROUTES, 1.0)
    vv = VersionVector(
        data_snapshot_id="bench",
        methodology_version="2.0",
        basket_version="bench",
        weight_version="bench",
        parser_version="bench",
        code_version="bench",
    )

    started = clock.perf_counter()
    runs = 5
    for _ in range(runs):
        result = calculate_apix_l(states, cell_weights, route_weights, vv, T)
    assemble_s = (clock.perf_counter() - started) / runs
    print(f"APIx-L assembly (mean of {runs}): {assemble_s:7.3f}s")

    total = ingest_s + assign_s + elementary_s + assemble_s
    print(f"{'-' * 52}\nfull deterministic path    : {total:7.3f}s")
    print(f"APIx-L level               : {result.level:.4f}")
    print(f"live routes                : {result.quality.live_routes}/{len(ROUTES)}")
    print()
    print("Bootstrap projection (spec N.4 / OQ-5): 1000 draws x full path")
    print(f"  = {total * 1000 / 60:.1f} minutes at this scale, single-threaded.")
    print("  Recorded as a measurement, not a promise — OQ-5 stays OPEN until it")
    print("  is measured on real collected data of realistic composition.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
