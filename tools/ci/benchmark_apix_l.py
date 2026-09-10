#!/usr/bin/env python3
"""Measure the APIx-L deterministic path end to end — methodology v2.1.

Two jobs, and the second is the one that matters:

1. **Runtime.** The dossier's planning estimate is 20,000-35,000 quotes per day
   at full frame (section 06). Spec N.4 (OQ-5) requires bootstrap runtime to be
   measured before a confidence interval is promised on screen, and the bootstrap
   recomputes the whole path 1000 times, so the per-path cost measured here is
   the multiplicand in that budget.

2. **Density.** This is the metric whose absence let AMB-1 through. The v2.0
   benchmark reported a mean and nothing else; a mean of 1.000 items per cell was
   sitting in plain sight. Distributions are reported here, never means alone.

.. warning::

   **SYNTHETIC EVIDENCE ONLY.** Nothing this script prints is evidence about
   Indian airfare. The frame is generated, and its shape was chosen by the
   author. It can show that the *mechanism* works — that cells can hold several
   items, that carry and suppression fire where expected — and it can show what
   the code costs to run. It cannot show that real schedules produce viable
   cells. That is OQ-A1 and it is answered by the seven-day collection spike,
   not here.

   The frame is deliberately **skewed**, not uniform: a uniform frame guarantees
   every cell has the same number of items, which is exactly the assumption under
   test. Trunk routes carry many flights per carrier, thin routes carry one or
   two.

Run:  python tools/ci/benchmark_apix_l.py
"""

from __future__ import annotations

import time as clock
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
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
from apix.schemas.keys import CellKey, ParentKey
from apix.schemas.observation import Entitlements, Observation
from apix.schemas.results import CellState
from apix.schemas.version_vector import VersionVector
from apix.statistics.elementary.admissibility import filter_admissible
from apix.statistics.elementary.bands import band_occupancy
from apix.statistics.elementary.dedup import deduplicate
from apix.statistics.elementary.jevons import compute_jevons
from apix.statistics.elementary.matching import (
    build_matched_set,
    cell_key_for,
    identity_stability,
    item_key_for,
    match_coverage,
    parent_key_for,
    select_tier,
)
from apix.statistics.elementary.sources import SourcePrecedence
from apix.statistics.index.apix_l import calculate_apix_l, cell_id
from apix.statistics.index.chaining import ChainInputs, advance_cell
from apix.statistics.index.parent import compute_parent_relative, parent_level

# --------------------------------------------------------------------------
# Frame
# --------------------------------------------------------------------------

T = date(2026, 9, 14)  # a Monday
PERIODS = [T - timedelta(days=14), T - timedelta(days=7), T]

PRECEDENCE = SourcePrecedence(
    version="bench-src-v1",
    order={
        Channel.AIRLINE_DIRECT: ("carrier-direct",),
        Channel.AGGREGATOR: ("mmt", "ixigo"),
    },
)

STANDARD = Entitlements(15, ChangePolicy.FEE, ChangePolicy.FEE)
HAND_ONLY = Entitlements(0, ChangePolicy.FEE, ChangePolicy.NONE)


@dataclass(frozen=True)
class Sector:
    """One route and how much service it carries. Skewed on purpose."""

    route: tuple[str, str]
    carriers: tuple[str, ...]
    flights_per_carrier: int


def frame_definition() -> list[Sector]:
    """A deliberately uneven network: trunk, mid and thin sectors.

    Real Indian domestic frequency is highly skewed, and the whole question
    AMB-1 leaves open is what happens to carrier-specific cells on the thin end.
    A uniform frame answers it by assumption; this one at least poses it.
    """
    metros = ["DEL", "BOM", "BLR", "MAA", "HYD", "CCU"]
    tier2 = ["GOI", "PNQ", "AMD", "COK", "JAI", "LKO", "IXC", "PAT"]
    thin = ["IXB", "DED", "IXR", "VNS", "BBI", "GAU"]

    sectors: list[Sector] = []
    for i, origin in enumerate(metros):
        for destination in metros[i + 1 :]:
            sectors.append(Sector((origin, destination), ("6E", "AI", "SG", "IX", "QP"), 11))
    for i, origin in enumerate(metros[:4]):
        sectors.append(Sector((origin, tier2[i]), ("6E", "AI", "SG"), 4))
        sectors.append(Sector((origin, tier2[i + 4]), ("6E", "SG"), 3))
    for i, destination in enumerate(thin):
        sectors.append(Sector((metros[i % len(metros)], destination), ("6E", "QP"), 1))
    return sectors


#: (route, carrier) pairs whose flight numbers churn between periods, so the
#: tier ladder is actually exercised rather than asserted.
CHURN = {("DEL-MAA", "SG"), ("BOM-HYD", "IX"), ("DEL-GOI", "AI")}


def synth(collection: date, sectors: Sequence[Sector]) -> list[Observation]:
    """Build one collection date. Deterministic by construction — no RNG.

    Spec P.2 forbids unseeded stochastic procedures anywhere near the statistics
    layer, and a benchmark whose input changes between runs cannot be compared
    with itself.
    """
    out: list[Observation] = []
    n = 0
    epoch = (collection - PERIODS[0]).days // 7

    for sector in sectors:
        origin, destination = sector.route
        route = f"{origin}-{destination}"
        for carrier in sector.carriers:
            churns = (route, carrier) in CHURN
            for slot in range(sector.flights_per_carrier):
                base_number = 100 + slot
                # Renumber once, in the final period only. Every-period churn
                # drives stability to ~0.29 (Tier 3) and Tier 2 is never
                # reached; a single renumbering gives F/(2F) = 0.5, inside
                # the [0.40, 0.70) band the tier ladder is meant to catch.
                number = f"{base_number + (700 if churns and epoch == 2 else 0)}"
                depart = time((5 + (slot * 2) % 18), (slot * 7) % 60)
                for bucket in APWBucket:
                    for channel, sources in (
                        (Channel.AIRLINE_DIRECT, ("carrier-direct",)),
                        (Channel.AGGREGATOR, ("mmt", "ixigo")),
                    ):
                        for source in sources:
                            n += 1
                            # A smooth, repeatable price surface. Nothing random.
                            fare = (
                                3000
                                + (n % 89) * 41
                                + bucket.value * 13
                                + epoch * 25
                                + (60 if channel is Channel.AGGREGATOR else 0)
                            )
                            out.append(
                                Observation(
                                    observation_id=f"{collection.isoformat()}-{n:07d}",
                                    origin=origin,
                                    destination=destination,
                                    travel_date=collection + timedelta(days=bucket.value),
                                    departure_time_local=depart,
                                    observation_ts=datetime.combine(collection, time(6, 0)),
                                    collection_date=collection,
                                    carrier=carrier,
                                    flight_number=number,
                                    stops=0,
                                    duration_minutes=120,
                                    fare_family_raw="SAVER",
                                    channel=channel,
                                    source_id=source,
                                    entitlements=STANDARD if slot % 4 else HAND_ONLY,
                                    payable_fare=Decimal(fare),
                                    source_type=SourceType.SYNTHETIC,
                                )
                            )
    return out


# --------------------------------------------------------------------------
# Distribution reporting
# --------------------------------------------------------------------------


def percentiles(values: Sequence[float]) -> dict[str, float]:
    """P10/P25/median/P75/P90 by linear interpolation on the sorted sample.

    Reported instead of a mean because a mean is what hid AMB-1: ``1.000 items
    per cell`` was the arithmetic mean of a degenerate distribution, and a mean
    cannot show degeneracy.
    """
    if not values:
        return {k: 0.0 for k in ("p10", "p25", "median", "p75", "p90")}
    ordered = sorted(values)
    n = len(ordered)

    def at(q: float) -> float:
        if n == 1:
            return ordered[0]
        pos = q * (n - 1)
        low = int(pos)
        high = min(low + 1, n - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)

    return {"p10": at(0.10), "p25": at(0.25), "median": at(0.50), "p75": at(0.75), "p90": at(0.90)}


def show(label: str, values: Sequence[float], unit: str = "") -> None:
    p = percentiles(values)
    suffix = f" {unit}" if unit else ""
    print(
        f"  {label:<34} n={len(values):>6}  "
        f"P10 {p['p10']:>8.3f}  P25 {p['p25']:>8.3f}  "
        f"med {p['median']:>8.3f}  P75 {p['p75']:>8.3f}  P90 {p['p90']:>8.3f}{suffix}"
    )


def share(part: float, whole: float) -> float:
    return part / whole if whole else 0.0


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------


def main() -> None:
    sectors = frame_definition()
    timings: dict[str, float] = {}

    t0 = clock.perf_counter()
    raw = {p: synth(p, sectors) for p in PERIODS}
    timings["frame generation"] = clock.perf_counter() - t0

    total_raw = sum(len(v) for v in raw.values())

    t0 = clock.perf_counter()
    admitted = {p: filter_admissible(obs) for p, obs in raw.items()}
    timings["admissibility"] = clock.perf_counter() - t0

    t0 = clock.perf_counter()
    deduped = {p: deduplicate(a.admissible) for p, a in admitted.items()}
    timings["deduplication"] = clock.perf_counter() - t0

    observations = {p: d.retained for p, d in deduped.items()}
    window = list(PERIODS)

    # ---- tier selection: per (route, carrier) for cells, per route for parents
    t0 = clock.perf_counter()
    all_obs = [o for p in PERIODS for o in observations[p]]
    routes = sorted({o.route for o in all_obs})
    pairs_rc = sorted({(o.route, o.carrier) for o in all_obs})

    stability_route = {r: identity_stability(all_obs, r, window) for r in routes}
    stability_rc = {(r, c): identity_stability(all_obs, r, window, carrier=c) for r, c in pairs_rc}
    cell_tier = {rc: select_tier(s) for rc, s in stability_rc.items()}
    parent_tier = {r: select_tier(s) for r, s in stability_route.items()}
    timings["tier selection"] = clock.perf_counter() - t0

    # ---- item and cell assignment
    t0 = clock.perf_counter()
    by_cell: dict[date, dict[CellKey, list[Observation]]] = {}
    by_parent: dict[date, dict[ParentKey, list[Observation]]] = {}
    for p in PERIODS:
        cells: dict[CellKey, list[Observation]] = {}
        parents: dict[ParentKey, list[Observation]] = {}
        for obs in observations[p]:
            cells.setdefault(cell_key_for(obs), []).append(obs)
            parents.setdefault(parent_key_for(obs), []).append(obs)
        by_cell[p] = cells
        by_parent[p] = parents
    timings["item + cell assignment"] = clock.perf_counter() - t0

    now, prev = PERIODS[-1], PERIODS[-2]
    all_cells = sorted(by_cell[now], key=lambda c: c.sort_key)

    # ---- distinct items per cell, before matching
    items_per_cell: list[float] = []
    for cell in all_cells:
        tier = cell_tier[(cell.route, cell.carrier)]
        if tier is Tier.TIER_3:
            items_per_cell.append(0.0)
            continue
        items_per_cell.append(float(len({item_key_for(o, tier) for o in by_cell[now][cell]})))

    # ---- matching and Jevons
    t0 = clock.perf_counter()
    matched_sets = {}
    for cell in all_cells:
        tier = cell_tier[(cell.route, cell.carrier)]
        matched_sets[cell] = build_matched_set(
            by_cell[now][cell],
            by_cell[prev].get(cell, []),
            cell,
            tier,
            source_precedence=PRECEDENCE,
        )
    timings["matching"] = clock.perf_counter() - t0

    t0 = clock.perf_counter()
    jevons = {cell: compute_jevons(cell, now, ms.pairs) for cell, ms in matched_sets.items()}
    timings["jevons"] = clock.perf_counter() - t0

    # ---- parent relatives, from raw observations
    t0 = clock.perf_counter()
    parents = sorted(by_parent[now], key=lambda k: k.sort_key)
    parent_results = {
        parent: compute_parent_relative(
            by_parent[now][parent],
            by_parent[prev].get(parent, []),
            parent,
            parent_tier[parent.route],
            now,
            source_precedence=PRECEDENCE,
        )
        for parent in parents
    }
    timings["parent relatives"] = clock.perf_counter() - t0

    # ---- chaining. Seed a prior level so the current period has something to
    #      chain onto; the seed itself is not a measured quantity.
    t0 = clock.perf_counter()
    seeded = {
        cell: CellState(
            cell=cell,
            collection_date=prev,
            level=100.0,
            status=CellStatus.PUBLISHED,
            last_matched_date=prev,
        )
        for cell in all_cells
    }
    states: list[CellState] = []
    for cell in all_cells:
        pr = parent_results.get(cell.parent())
        states.append(
            advance_cell(
                ChainInputs(
                    cell=cell,
                    collection_date=now,
                    jevons=jevons[cell],
                    previous=seeded[cell],
                    parent_relative=(pr.jevons.relative if pr and pr.jevons.is_defined else None),
                    parent_level=None,
                )
            )
        )
    timings["chaining"] = clock.perf_counter() - t0

    # ---- weights and aggregation
    t0 = clock.perf_counter()
    weights = {cell_id(c): 1.0 for c in all_cells}
    route_weights = {r: 1.0 / len(routes) for r in routes}
    vv = VersionVector(
        data_snapshot_id="sha256:" + "b" * 63,
        methodology_version="2.1",
        basket_version="2026-Q3",
        weight_version="bench-w1",
        parser_version="bench-p1",
        code_version="bench",
    )
    result = calculate_apix_l(states, weights, route_weights, vv, now)
    timings["aggregation + APIx-L"] = clock.perf_counter() - t0

    # ---- parent levels, exercising the independent-live rule
    t0 = clock.perf_counter()
    states_by_parent: dict[ParentKey, list[CellState]] = {}
    for state in states:
        states_by_parent.setdefault(state.cell.parent(), []).append(state)
    cell_weight_by_key = {c: 1.0 for c in all_cells}
    parent_levels = {
        parent: parent_level(members, cell_weight_by_key, entered_at_t=())
        for parent, members in sorted(states_by_parent.items(), key=lambda kv: kv[0].sort_key)
    }
    timings["parent levels"] = clock.perf_counter() - t0

    _report(
        total_raw=total_raw,
        admitted=admitted,
        deduped=deduped,
        observations=observations,
        now=now,
        all_cells=all_cells,
        cell_tier=cell_tier,
        items_per_cell=items_per_cell,
        matched_sets=matched_sets,
        jevons=jevons,
        states=states,
        parent_results=parent_results,
        parent_levels=parent_levels,
        stability_route=stability_route,
        stability_rc=stability_rc,
        by_cell=by_cell,
        result=result,
        timings=timings,
        routes=routes,
    )


def _report(**k: object) -> None:
    now = k["now"]
    all_cells: list[CellKey] = k["all_cells"]  # type: ignore[assignment]
    cell_tier: dict[tuple[str, str], Tier] = k["cell_tier"]  # type: ignore[assignment]
    matched_sets = k["matched_sets"]  # type: ignore[assignment]
    jevons = k["jevons"]  # type: ignore[assignment]
    states: list[CellState] = k["states"]  # type: ignore[assignment]
    parent_results = k["parent_results"]  # type: ignore[assignment]
    parent_levels = k["parent_levels"]  # type: ignore[assignment]
    observations = k["observations"]  # type: ignore[assignment]
    by_cell = k["by_cell"]  # type: ignore[assignment]
    timings: dict[str, float] = k["timings"]  # type: ignore[assignment]
    admitted = k["admitted"]  # type: ignore[assignment]
    deduped = k["deduped"]  # type: ignore[assignment]

    print("=" * 78)
    print("APIx-L benchmark — methodology v2.1        SYNTHETIC FRAME, NOT EVIDENCE")
    print("=" * 78)

    print("\nFRAME")
    print(f"  raw observations (3 periods)       {k['total_raw']:>8,}")
    print(f"  observations at t                  {len(observations[now]):>8,}")
    excluded = sum(len(a.excluded) for a in admitted.values())
    admissible = sum(len(a.admissible) for a in admitted.values())
    print(f"  admissible                         {admissible:>8,}")
    print(f"  excluded                           {excluded:>8,}")
    print(f"  duplicate rate                     {deduped[now].duplicate_rate:>8.4%}")
    print(f"  routes                             {len(k['routes']):>8,}")
    print(f"  cells at t                         {len(all_cells):>8,}")

    print("\nDENSITY — the metric whose absence let AMB-1 through")
    show("distinct items per cell", k["items_per_cell"])  # type: ignore[arg-type]
    matched_counts = [float(len(matched_sets[c].pairs)) for c in all_cells]
    show("matched items per cell", matched_counts)

    viable = [c for c in all_cells if jevons[c].is_defined]
    print(f"  cell viability rate                {share(len(viable), len(all_cells)):>8.2%}")

    total_weight = float(len(all_cells))
    viable_weight = float(len(viable))
    print(f"  WEIGHT viability rate              {share(viable_weight, total_weight):>8.2%}")
    print("    ^ equal cell weights in this frame, so it coincides with the count.")
    print("      On a real basket they diverge, and weight viability is the")
    print("      decision metric: losing many light cells is survivable, losing")
    print("      few heavy ones is not.")

    print("\nTIER AND STATUS SHARES (by cell, equal weights)")
    for tier in Tier:
        n = sum(1 for c in all_cells if cell_tier[(c.route, c.carrier)] is tier)
        print(f"  {tier.name:<34} {share(n, len(all_cells)):>8.2%}  ({n})")
    for status in CellStatus:
        n = sum(1 for s in states if s.status is status)
        if n:
            print(f"  {status.name:<34} {share(n, len(states)):>8.2%}  ({n})")

    carried = sum(1 for s in states if s.status is CellStatus.CARRIED)
    held = sum(1 for s in states if s.status is CellStatus.HELD_OUT)
    supp = sum(1 for s in states if s.status is CellStatus.SUPPRESSED)
    print(f"  parent carry share                 {share(carried, len(states)):>8.2%}")
    print(f"  held-out share                     {share(held, len(states)):>8.2%}")
    print(f"  suppressed share                   {share(supp, len(states)):>8.2%}")

    print("\nMATCHING QUALITY")
    coverage = []
    for c in all_cells:
        tier = cell_tier[(c.route, c.carrier)]
        if tier is Tier.TIER_3:
            continue
        expected = len({item_key_for(o, tier) for o in by_cell[now][c]})
        coverage.append(match_coverage(len(matched_sets[c].pairs), expected))
    show("match coverage", coverage)
    transitions = sum(len(matched_sets[c].transitions) for c in all_cells)
    selections = sum(len(matched_sets[c].selections) for c in all_cells)
    print(f"  source-transition rate             {share(transitions, selections):>8.4%}")
    print("    ^ zero here by construction: this frame never changes its source")
    print("      mix between links. The rule is exercised by E2E-12, not by this")
    print("      frame, and its real frequency is OQ-A9.")
    no_common = sum(len(matched_sets[c].unmatched_no_common_source) for c in all_cells)
    print(f"  items with no common source        {no_common:>8,}")

    print("\nIDENTITY STABILITY")
    show("by route", list(k["stability_route"].values()))  # type: ignore[union-attr]
    show("by (route, carrier)", list(k["stability_rc"].values()))  # type: ignore[union-attr]

    print("\nPARENT OBJECT")
    defined = [p for p in parent_results.values() if p.jevons.is_defined]
    print(f"  parents                            {len(parent_results):>8,}")
    print(f"  with a defined relative            {share(len(defined), len(parent_results)):>8.2%}")
    show("carrier count per parent", [float(p.carrier_count) for p in parent_results.values()])
    show(
        "carrier concentration",
        [p.carrier_concentration for p in parent_results.values()],
    )
    print("    ^ concentration is the size of the carrier-mix channel: at 1.0 a")
    print("      parent imputes one carrier's movement to every other carrier's")
    print("      cell. Whether it needs a ceiling is OQ-A8.")
    with_level = sum(1 for v in parent_levels.values() if v is not None)
    print(f"  parents with a defined level       {share(with_level, len(parent_levels)):>8.2%}")

    print("\nTIER-2 BAND DIAGNOSTICS")
    bands = [b for c in all_cells for b in matched_sets[c].bands]
    if bands:
        show("band overlap", [b.overlap for b in bands])
        show("band membership delta", [float(b.membership_delta) for b in bands])
        show("within-band log dispersion", [b.dispersion_t for b in bands])
        telescoping = sum(1 for b in bands if b.telescopes)
        print(f"  bands where the identity holds     {share(telescoping, len(bands)):>8.2%}")
    else:
        print("  no Tier-2 cells in this frame")
    occ = [
        float(band_occupancy(by_cell[now][c]))
        for c in all_cells
        if cell_tier[(c.route, c.carrier)] is Tier.TIER_2
    ]
    if occ:
        show("band occupancy (Tier-2 cells)", occ)

    print("\nSOURCE SPREAD (aggregator vs carrier-direct, log points)")
    spread = _source_spread(observations[now])
    if spread:
        show("cross-channel log spread", spread)
    else:
        print("  not computable on this frame")

    print("\nINDEX")
    result = k["result"]
    print(f"  published                          {result.published!s:>8}")
    print(f"  level                              {result.level if result.level else 0.0:>8.4f}")
    print(f"  live routes                        {result.quality.live_routes:>8,}")
    print(f"  suppressed weight share            {result.quality.suppressed_weight_share:>8.2%}")
    print(f"  imputation rate                    {result.quality.imputation_rate:>8.2%}")
    for caveat in result.quality.caveats:
        print(f"  CAVEAT: {caveat}")

    print("\nRUNTIME")
    total = 0.0
    for stage, seconds in timings.items():
        if stage == "frame generation":
            continue
        total += seconds
        print(f"  {stage:<34} {seconds:>8.3f}s")
    print(f"  {'-' * 34} {'-' * 8}")
    print(f"  {'deterministic path total':<34} {total:>8.3f}s")
    print(f"  ({'frame generation, excluded':<32} {timings['frame generation']:>8.3f}s)")
    print(f"\n  projected 1000-draw bootstrap      {total * 1000 / 60:>8.1f} min single-threaded")
    print("  OQ-5 remains OPEN: this is a measurement on synthetic input, not a")
    print("  budget for real collected data.")
    print("=" * 78)


def _source_spread(observations: Iterable[Observation]) -> list[float]:
    """Log gap between the aggregator and carrier-direct quote for one flight.

    The diagnostic spec B.5 exists to publish, and the earliest signal that a
    parser has drifted.
    """
    import math

    direct: dict[tuple[str, str, str, date], Decimal] = {}
    agg: dict[tuple[str, str, str, date], Decimal] = {}
    for obs in observations:
        key = (obs.route, obs.carrier, obs.flight_number, obs.travel_date)
        if obs.channel is Channel.AIRLINE_DIRECT:
            direct[key] = obs.payable_fare
        elif obs.source_id == "mmt":
            agg[key] = obs.payable_fare
    return [
        math.log(float(agg[k])) - math.log(float(direct[k]))
        for k in sorted(direct.keys() & agg.keys())
    ]


if __name__ == "__main__":
    main()
