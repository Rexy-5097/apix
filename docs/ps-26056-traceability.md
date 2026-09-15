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
| d | Interactive dashboard showing the **daily** APIx | Jury dashboard (13 chapters) + platform console (12 views: trends, heatmap, lead-time, acquisition, sources, runs, quality, provenance, backtest, methodology, architecture). Both are scroll-driven: shared vendored GSAP/ScrollTrigger/Lenis, animated pipeline graph, drawn curves, interactive heatmap and provenance lineage | `data/dashboard.html`, `data/platform.html`, `tools/analysis/build_platform.py`, `tools/analysis/platform_motion.py` | `test_dashboard_claims.py`, `test_platform_page.py` (27) | **PARTIAL** — both pages real, offline and reduced-motion safe; **no daily production index exists to show** — the daily/weekly/monthly figures on the console are labelled DEMO |

## Detailed description, point by point

| # | PS requirement | APIx component | Path | Test | Status |
|---|---|---|---|---|---|
| 1 | Automatically collect from airline sites and OTAs | Gated collector; fixture adapter works on synthetic pages | `collectors/indigo/`, `collectors/gate.py` | `test_collector_runner.py` | **BLOCKED** — see [source register](../source_registry/registry.yaml) |
| 2 | Handle JS rendering | Playwright browser adapter | `collectors/indigo/live.py` | — (gated; never run) | **COMPLETE** (unexercised) |
| 2 | Handle CAPTCHA / anti-bot **compliantly** | 5-state `PageState`; `ACCESS_CHALLENGE` → `CAPTCHA_OR_ANTIBOT_STOP`, `stop=True`, no retry | `collectors/candidates.py`, `collectors/runner.py` | `test_collection_contract.py::test_access_challenge_is_the_only_stop_signal` | **COMPLETE** — detect → stop → record → defer |
| 2 | Session management | Per-source session lifecycle; `signed_in` frozen `False` | `collectors/contract.py` | `test_collector_contract_and_parse.py` | **COMPLETE** |
| 2 | IP rotation / egress | Declared `EgressPolicy`: `SINGLE_STABLE`, `RotationPolicy.NEVER` (sole member), identifying UA; `select_egress()` takes no refusal argument | `collectors/egress.py` | `test_egress_policy.py` (8 tests, incl. AST scan: no function references both a refusal symbol and an egress symbol; no rotation library imported) | **COMPLETE** — rotation is structurally impossible, not merely absent |
| 2 | Rate limiting | `min_interval_seconds` 30 s default, 10 s floor enforced in code; single retry ≥60 s | `collectors/contract.py`, `scheduling/scheduler.py` | `test_platform.py::test_pacing_floor_and_band_set_are_enforced_by_the_config` | **COMPLETE** |
| 2 | robots.txt and ToS compliance | Four-axis register; five conjunctive live-gate conditions; **no override** | `collectors/gate.py`, `source_registry/registry.yaml` | `test_collector_runner.py::test_no_source_in_the_register_is_cleared_for_live_collection` | **COMPLETE** |
| 3 | Clean and normalise quotes | `normalize.py`, admissibility, dedup, outlier MAD, exclusion replay | `collectors/normalize.py`, `statistics/elementary/` | `test_statistical_edge_cases.py`, `test_execution_boundary.py` | **COMPLETE** |
| 4 | City-pair basket on **DGCA traffic** | `RouteBasket`, `RouteWeight`, `BasketStatus` | `src/apix/config/basket.py` | `test_platform.py` (6 basket tests) | **PARTIAL** — structure complete; **weights PROVISIONAL/DEMO, never publication grade.** OQ-4 open: no DGCA traffic file verified |
| 5 | Multiple APW windows | `ApwWindowSet`; frozen 7 and the PS 5 as a strict subset | `src/apix/config/apw.py` | `test_platform.py` (5 APW tests) | **COMPLETE** |
| 6 | Separate base fare, taxes, **UDF**, convenience charges | `FareBreakdown(base_fare, taxes, fees, user_development_fee)` + `reconciles_with` | `src/apix/schemas/observation.py` | `test_collection_contract.py` | **COMPLETE** — all four fields; absent stays `None`, never `0` |
| 7 | Daily / weekly / monthly APIx | `Frequency`, `aggregate` (geometric), `PeriodPoint` | `src/apix/series/periods.py` | `test_platform.py` (7 period tests) | **PARTIAL** — engine complete and tested; **input is the synthetic fixture, because 0 matched pairs exist** |
| 8 | Price trends | Dashboard APW profile and rail | `data/dashboard.html` | `test_dashboard_claims.py` | **COMPLETE** (descriptive) |
| 8 | Sector **heatmap** | Route × class grid over the six PS city pairs | `build_platform.py::heatmap_svg`, `/coverage` | `test_platform_page.py::test_heatmap_has_exactly_one_filled_cell` | **PARTIAL** — component complete; **one of six cells has data** (DEL–BOM, 35 obs). The five empty cells are rendered as empty, not filled |
| 8 | Lead-time **elasticity** curves | Descriptive APW profile: `/lead-time` endpoint, console view, confound flag | `data/panel.json` → `apw_profile`, `api/payloads.py::lead_time` | `test_api.py::test_lead_time_is_descriptive_not_an_elasticity` | **PARTIAL** — served and plotted, labelled `DESCRIPTIVE_ONLY`; **no elasticity estimate** — one collection date, lead time confounded with travel date |
| 9 | **API for NSO/RBI** | 13 GET endpoints, stdlib HTTP, one envelope (`output_class`, `publication_status`, `data_status`, `live_airfare_acquisition`) on every payload | `src/apix/api/server.py`, `src/apix/api/payloads.py` | `test_api.py` (24 tests: pure routing + one socket test) | **COMPLETE** — serves the real panel and RESEARCH/DEMO series; **nothing it serves is PRODUCTION**, and the tests forbid that label |
| 10 | Documentation | README, capability matrix, claim-evidence matrix, methodology, compliance, permissions, this matrix | `docs/`, `compliance/` | `check_markdown_links.py` (104 files) | **COMPLETE** |
| 10 | Automated testing | 807 tests; invariants, golden values, property tests, architecture boundary, API, exports, page, motion layer | `tests/` | — | **COMPLETE** |
| 11 | **30-day backtest vs DGCA fare data** | Alignment, Pearson, MAE, MAPE, RMSE, directional agreement | `src/apix/backtest/compare.py` | `test_platform.py` (7 backtest tests) | **BLOCKED / INCOMPLETE** — framework complete and metrics verified; **`DGCA_FARE_BENCHMARK_STATUS = NOT_LOCATED`** |

## Presentation layer

| Requirement | APIx component | Path | Test | Status |
|---|---|---|---|---|
| Interactive, explainable presentation | Scroll-driven console: hero observation field (35 recorded points, three declared beats), animated two-lane pipeline graph, index dependency chain, drawn lead-time curve, interactive sector heatmap, provenance lineage explorer, backtest missing-data visual | `tools/analysis/platform_motion.py` | `test_platform_page.py` | **COMPLETE** |
| Honest animation | Two rules, both tested: a figure is **revealed, never tallied** (no frame ever shows a value APIx does not hold), and motion only depicts **work that happened** (the live lane carries no packet, because zero requests were made) | same | `test_no_figure_is_tallied_from_zero`, `test_the_live_lane_carries_no_packet_and_the_index_is_drawn_refused` | **COMPLETE** |
| Accessibility and performance | `prefers-reduced-motion` neutralises every component; rest states gated on `html.js` so a blocked script hides nothing; canvas loop stopped when offscreen; status indicators animate only while their section is on screen; 2.5-second failsafe reveals everything if the mechanism dies | same | `test_reduced_motion_neutralises_every_component_this_page_adds`, `test_rest_states_are_gated_on_the_js_class` | **COMPLETE** |

## Data exports

| PS requirement | Status |
|---|---|
| CSV / JSON exports of observations, index, coverage, weights, provenance | **COMPLETE** — `python -m apix.export` writes 17 files to `data/exports/` with fixed column orders (`src/apix/export/exports.py`, `test_exports.py`). Absent values are empty, never `0`; every JSON file is the API envelope |
| Parquet | **NOT BUILT** — deliberately: the runtime is stdlib-only. CSV and JSON cover the NSO/RBI handoff |

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
| **COMPLETE** | Scheduler · compliance gate · declared egress policy · observation contract · fare decomposition · cleaning and normalisation · deduplication · APW configuration · index engine · publication guards · period aggregation · readiness layer · backtest framework · API (13 endpoints) · CSV/JSON exports · documentation · testing |
| **PARTIAL** | Route basket (structure yes, DGCA weights no) · daily/weekly/monthly (engine yes, production input no) · dashboard and console (real, but the index figures shown are DEMO) · heatmap (built, one of six cells has data) · lead-time (descriptive, not elasticity) |
| **NOT BUILT** | **elasticity estimate** (needs more than one collection date) · **Parquet export** (stdlib-only runtime) |
| **BLOCKED** | Live airfare acquisition (authorization pending) · 30-day DGCA backtest (benchmark not published) |

APIx is a complete end-to-end airfare measurement platform with a compliant acquisition boundary.
The only major production gap is authorized live airfare acquisition: zero automated fares have been
acquired and zero permissions have been granted. Every other layer runs today on the data that exists.
