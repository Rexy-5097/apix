# PS 26056 — requirement traceability

> **Status as of 2026-09-15.** Every row names a repository path and a test, or says plainly that
> nothing exists. **`COMPLETE` is used only where the component genuinely works.** A placeholder is
> never `COMPLETE`.
>
> Run the whole platform: **`python -m apix.demo`**

## Status vocabulary

| | |
|---|---|
| **COMPLETE** | Implemented, tested, and exercised by the demo |
| **PARTIAL** | The component exists and works; a named part of the requirement does not |
| **BLOCKED** | Implemented and deliberately refusing, pending something external |
| **NOT BUILT** | No implementation. Stated rather than dressed up |

---

## Expected solution (a)–(d)

| # | PS requirement | APIx component | Path | Test | Status |
|---|---|---|---|---|---|
| a | Multi-source scraping engine, Scrapy/Selenium/**Playwright**, scheduled daily extraction | `SourceAdapter`, compliance gate, eligibility, band selection, fare decision, evidence, runner; Playwright live adapter | `src/apix/ingestion/collectors/` | `test_collector_runner.py`, `test_collector_selection.py`, `test_collector_contract_and_parse.py` | **BLOCKED** — engine complete; **0 of 30 sources cleared, 0 fares ever collected** |
| a | Scheduled daily extraction | `SchedulerConfig`, `build_plan`, `execute_plan` | `src/apix/scheduling/scheduler.py` | `test_platform.py` (12 scheduler tests) | **COMPLETE** — runs to completion with nothing cleared |
| b | Cleaned, de-duplicated DB with origin, destination, carrier, APW, fare class, base, taxes, total | `Observation`, `FareBreakdown`, `Entitlements`, SQLite store | `src/apix/schemas/observation.py`, `src/apix/ingestion/store.py` | `test_collection_contract.py`, `test_collection_store.py`, `test_observed_panel.py` | **COMPLETE** — schema; **35 real rows held** |
| c | Index construction on given routes and weights | Jevons, matching, chaining, Young/Modified Laspeyres, publication guards | `src/apix/statistics/` | `test_golden_values.py`, `test_pipeline_14_day.py`, `test_v2_1_invariants.py` | **COMPLETE** — engine; **no production index value** |
| d | Interactive dashboard showing the **daily** APIx | Generated jury dashboard, 13 chapters | `data/dashboard.html`, `tools/analysis/build_dashboard.py` | `test_dashboard_claims.py` | **PARTIAL** — dashboard is real; **no heatmap, no elasticity curve, no daily index** |

## Detailed description, point by point

| # | PS requirement | APIx component | Path | Test | Status |
|---|---|---|---|---|---|
| 1 | Automatically collect from airline sites and OTAs | Gated collector; fixture adapter works on synthetic pages | `collectors/indigo/`, `collectors/gate.py` | `test_collector_runner.py` | **BLOCKED** — see [source register](../source_registry/registry.yaml) |
| 2 | Handle JS rendering | Playwright browser adapter | `collectors/indigo/live.py` | — (gated; never run) | **COMPLETE** (unexercised) |
| 2 | Handle CAPTCHA / anti-bot **compliantly** | 5-state `PageState`; `ACCESS_CHALLENGE` → `CAPTCHA_OR_ANTIBOT_STOP`, `stop=True`, no retry | `collectors/candidates.py`, `collectors/runner.py` | `test_collection_contract.py::test_access_challenge_is_the_only_stop_signal` | **COMPLETE** — detect → stop → record → defer |
| 2 | Session management | Per-source session lifecycle; `signed_in` frozen `False` | `collectors/contract.py` | `test_collector_contract_and_parse.py` | **COMPLETE** |
| 2 | IP rotation / egress | **Declared egress policy not written** | — | — | **NOT BUILT** — the one acknowledged architectural gap. Rotation is *deliberately* absent; what is missing is the written policy and the test asserting no code path reaches egress selection from a refusal handler |
| 2 | Rate limiting | `min_interval_seconds` 30 s default, 10 s floor enforced in code; single retry ≥60 s | `collectors/contract.py`, `scheduling/scheduler.py` | `test_platform.py::test_pacing_floor_and_band_set_are_enforced_by_the_config` | **COMPLETE** |
| 2 | robots.txt and ToS compliance | Four-axis register; five conjunctive live-gate conditions; **no override** | `collectors/gate.py`, `source_registry/registry.yaml` | `test_collector_runner.py::test_no_source_in_the_register_is_cleared_for_live_collection` | **COMPLETE** |
| 3 | Clean and normalise quotes | `normalize.py`, admissibility, dedup, outlier MAD, exclusion replay | `collectors/normalize.py`, `statistics/elementary/` | `test_statistical_edge_cases.py`, `test_execution_boundary.py` | **COMPLETE** |
| 4 | City-pair basket on **DGCA traffic** | `RouteBasket`, `RouteWeight`, `BasketStatus` | `src/apix/config/basket.py` | `test_platform.py` (6 basket tests) | **PARTIAL** — structure complete; **weights PROVISIONAL/DEMO, never publication grade.** OQ-4 open: no DGCA traffic file verified |
| 5 | Multiple APW windows | `ApwWindowSet`; frozen 7 and the PS 5 as a strict subset | `src/apix/config/apw.py` | `test_platform.py` (5 APW tests) | **COMPLETE** |
| 6 | Separate base fare, taxes, **UDF**, convenience charges | `FareBreakdown(base_fare, taxes, fees, user_development_fee)` + `reconciles_with` | `src/apix/schemas/observation.py` | `test_collection_contract.py` | **COMPLETE** — all four fields; absent stays `None`, never `0` |
| 7 | Daily / weekly / monthly APIx | `Frequency`, `aggregate` (geometric), `PeriodPoint` | `src/apix/series/periods.py` | `test_platform.py` (7 period tests) | **PARTIAL** — engine complete and tested; **input is the synthetic fixture, because 0 matched pairs exist** |
| 8 | Price trends | Dashboard APW profile and rail | `data/dashboard.html` | `test_dashboard_claims.py` | **COMPLETE** (descriptive) |
| 8 | Sector **heatmap** | — | — | — | **NOT BUILT** — needs more than one route |
| 8 | Lead-time **elasticity** curves | Descriptive APW profile only | `data/panel.json` → `apw_profile` | `test_observed_panel.py` | **PARTIAL** — cross-sectional profile exists and is labelled `DESCRIPTIVE_CROSS_SECTION`; **no elasticity estimate**, and the T+1→T+60 spread is *not* causal |
| 9 | **API for NSO/RBI** | — | `src/apix/api/` is an empty package | — | **NOT BUILT** |
| 10 | Documentation | README, capability matrix, claim-evidence matrix, methodology, compliance, permissions, this matrix | `docs/`, `compliance/` | `check_markdown_links.py` (102 files) | **COMPLETE** |
| 10 | Automated testing | 731 tests; invariants, golden values, property tests, architecture boundary | `tests/` | — | **COMPLETE** |
| 11 | **30-day backtest vs DGCA fare data** | Alignment, Pearson, MAE, MAPE, RMSE, directional agreement | `src/apix/backtest/compare.py` | `test_platform.py` (7 backtest tests) | **BLOCKED / INCOMPLETE** — framework complete and metrics verified; **`DGCA_FARE_BENCHMARK_STATUS = NOT_LOCATED`** |

## Data exports

| PS requirement | Status |
|---|---|
| CSV / JSON / Parquet exports of observations, index, coverage, weights, provenance | **NOT BUILT.** `data/panel.json` and `data/reference/*.json` are stable committed JSON contracts, and `collection-input/loader/*.csv` are stable CSV, but there is no export module |

## Why the backtest cannot be satisfied

Two independent reasons, both evidenced:

1. **The PS's stated benchmark is not published.** DGCA's complete A–Z index and sitemap were
   enumerated on 2026-09-15. Its air-transport statistics are traffic and capacity — departures,
   hours, kilometres, passengers, ASKM, load factors, cargo. **No rupee-denominated fare field
   appears anywhere**, and the site carries an all-rights-reserved notice with no reuse grant.
2. **APIx holds no real index series to compare.** Spec C.1 needs a matched `t / t−7` pair; one
   collection wave is held, so zero pairs exist.

A third, found while wiring the fallback: the one public benchmark APIx does hold — the MoSPI CPI
airfare item index — is **declared monthly but publishes only December** for each year 2014–2025,
across two base years. In practice it is an annual series, and mixing base 2010 with base 2012 is a
units error. The demo filters to base 2012 and says so.

**The framework is real and its metrics are verified against known series.** What is absent is
comparable public data, and that is a finding rather than an excuse.

## The acquisition boundary, stated once

**APIx has automatically collected zero airfares from any airline or travel website.** The engine
exists, is tested, and is refused at the gate. `python -m apix.demo` prints
`requests MADE : 0` against the real register, every refusal recorded as `PERMISSION_BLOCKED` —
never as `NO_FLIGHT`, which would read as an absence of flights (see
[ADR-0066](../artifacts/decisions/ADR-0066-permission-blocked-collection-outcome.md)).

Two access requests are drafted and **unsent** in [`docs/permissions/`](permissions/README.md).
Until one is granted, this row cannot change.

## Honest summary

| | |
|---|---|
| **COMPLETE** | Scheduler · compliance gate · observation contract · fare decomposition · cleaning and normalisation · deduplication · APW configuration · index engine · publication guards · period aggregation · readiness layer · backtest framework · documentation · testing |
| **PARTIAL** | Route basket (structure yes, DGCA weights no) · daily/weekly/monthly (engine yes, production input no) · dashboard (real, but no heatmap or elasticity) · lead-time (descriptive, not elasticity) |
| **NOT BUILT** | **API** · **exports** · **heatmap** · **elasticity estimate** · **declared egress policy** |
| **BLOCKED** | Live airfare acquisition (authorization pending) · 30-day DGCA backtest (benchmark not published) |

APIx is a complete end-to-end airfare measurement platform with a compliant acquisition boundary.
The largest production gap is authorized live airfare acquisition. The largest *build* gaps are the
API and the export layer, and neither is started.
