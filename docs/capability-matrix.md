# APIx capability matrix

> **Authoritative answer to "what actually works today?"**
> Generated state as of **2026-09-13**. Methodology frozen at **v2.1**.
> If this disagrees with any other document, believe the code and the tests, then
> fix the other document.

This file exists because "implemented" is routinely read as "working on real
data", and for APIx those are different claims with different evidence. Four
status levels are used, and they are **not** interchangeable:

| Level | Means |
|---|---|
| **REAL-DATA EXERCISED** | Real collected market observations have passed through this code. **Passing through is not validation** — see the execution boundary below |
| **FIXTURE-ONLY** | Implemented and invariant-tested, but **only ever executed on synthetic test fixtures** |
| **SPECIFIED-ONLY** | The methodology defines it. **No implementation exists.** |
| **BLOCKED** | Implementation deliberately refuses, pending a decision that cannot be made in code |

---

## The sentence that matters most

> **Real market observations pass through APIx's admissibility, banding, key
> construction, deduplication and source-precedence stages. The pipeline stops at
> the longitudinal Jevons step because the required t−7 observation does not yet
> exist.**

Those five named stages — and only those — are **REAL-DATA EXERCISED**. The
layer is not exercised as a whole, and no stage below the Jevons step is reached
by real data at all.

Until 2026-09-13 this section said real observations did not enter
`src/apix/statistics/` at all. That is no longer true, and the correction is
narrow enough to be worth stating exactly:

- **What now runs on the 35 real observations.** `filter_admissible` (§A.6),
  `hour_band` (§B.2.2), `cell_key_for` / `parent_key_for` / `item_key_for`,
  `duplicate_key` / `deduplicate` (§D.4) and `SourcePrecedence.rank` (§D.8.1).
- **What still does not.** `build_matched_set`, `compute_jevons`,
  `advance_cell`, the aggregation layer and `publish`. §C.1 is locked at
  `I(c,t) = I(c,t−7) · J(c,t)`, and one collection wave gives zero matched
  pairs.
- **How they run.** `tools/analysis/execution_boundary.py` reconstructs the
  canonical observations **from `data/panel.json`** and calls the frozen
  functions read-only. The *production* loader,
  `tools/collection/load_manual.py`, still imports nothing from
  `apix.statistics` — so this is a harness, not a pipeline change.
- **What it does not license.** Three of those stages are **DEGENERATE**: band
  price and within-band dispersion at n=1, and source precedence at one source.
  They execute and return defined answers that establish nothing.

The authority on this question is
[the execution boundary](#real-data-execution-boundary), which is generated
from the contract rather than written here.

**"The engine is complete" means every algorithm exists and passes its
invariant tests. It does NOT mean the production pipeline can publish a real
index today.** Those two claims are not equivalent and must not be substituted
for one another.

---

## Matrix

| Component | Specified | Implemented | Tested | Real data reaches it | **Status** |
|---|:---:|:---:|:---:|:---:|---|
| Canonical observation model | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| Ingestion store (SQLite) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| Collection bridge (manual loader) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| Automated collector — IndiGo adapter, fixture mode | ✅ | ✅ | ✅ | ❌ *(SYNTHETIC pages only)* | **FIXTURE-ONLY** |
| Automated collector — IndiGo NDC API, sandbox | ✅ | gate + credentials + index boundary only | ✅ | ❌ *(no request ever sent)* | **BLOCKED** *(official request model unconfirmed; no UAT credentials)* |
| Automated collector — IndiGo adapter, live mode | ✅ | ✅ *(selectors unverified)* | gate only | ❌ *(never run)* | **BLOCKED** *(registry: `AUTOMATION_PROHIBITED`)* |
| Evidence / provenance grading | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| APW bucket assignment (§A.3) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| Departure-band assignment (§B.2) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| Band price / within-band dispersion (§B.2.3) | ✅ | ✅ | ✅ | ⚠️ | **REAL-DATA EXERCISED — DEGENERATE** *(n=1 in every cell-band group)* |
| Fare-class derivation (§B.4) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| Panel generation → `panel.json` | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| Dashboard + text report renderers | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| MoSPI benchmark ingestion | ✅ | ✅ | ✅ | ✅ *(reference only)* | **REAL-DATA EXERCISED** |
| Cell / parent / item keys (§B.2.1) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| Admissibility filter (§A.6) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** |
| Matched set / tier ladder (§D.1) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Jevons elementary relative (§D.2) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Deduplication (§D.4) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA EXERCISED** *(0 duplicates observed; tie-break not exercised)* |
| Outlier / MAD rule | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Source precedence (§D.8) | ✅ | ✅ | ✅ | ⚠️ | **REAL-DATA EXERCISED — DEGENERATE** *(`rank` only; 1 source, `select` unreachable)* |
| Advance-cell / weekly chain (§E) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Carry / freshness / suppression | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Parent fallback (§E.4, §E.6) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Within-route weights (§G.3) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Young / Modified Laspeyres | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Annual linking | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| National assembly (`calculate_apix_l`) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Publication guard (`publish`) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Engine validation fixture (14 days) | ✅ | ✅ | ✅ | n/a *(synthetic by design)* | **FIXTURE-ONLY** |
| **Carrier allocation of `v[c\|r]`** | ❌ **AMB-9** | guard only | ✅ | ❌ | **BLOCKED** |
| **Route coverage denominator (§I)** | ❌ **AMB-8** | guard only | ✅ | ❌ | **BLOCKED** |
| APIx-TPD estimator (§M) | ✅ | ❌ | ❌ | ❌ | **SPECIFIED-ONLY** |
| Uncertainty / bootstrap | ✅ | ❌ | ❌ | ❌ | **SPECIFIED-ONLY** |
| Analytics layer | ✅ | ❌ | ❌ | ❌ | **SPECIFIED-ONLY** |
| AI explanation layer | ✅ | ❌ | ❌ | ❌ | **SPECIFIED-ONLY** |
| API (stdlib HTTP, 13 endpoints) | ✅ | ✅ | ✅ | ❌ | **BUILT — serves RESEARCH/DEMO only; no PRODUCTION payload exists** |
| CSV/JSON exports (17 files) | ✅ | ✅ | ✅ | ❌ | **BUILT — same envelope as the API** |
| SDMX serialisers | ✅ | ❌ | ❌ | ❌ | **SPECIFIED-ONLY** |
| Next.js dashboard (`dashboard-planned/`) | ✅ | ❌ | ❌ | ❌ | **SPECIFIED-ONLY** |
| AgentOS framework | ✅ | ✅ | ✅ CI | n/a | **DEV INFRASTRUCTURE — not part of the statistic** |

`src/apix/statistics/tpd/`, `src/apix/statistics/uncertainty/`,
`src/apix/analytics/`, `src/apix/ai/` and
`src/apix/experiments/` are **empty packages**. A test
(`test_tpd_and_uncertainty_packages_are_genuinely_empty`) fails the build if
that stops being true without the documentation being updated.

---

## Real-data execution boundary

Generated, not written here: `data/panel.json` → `execution_boundary`, rendered
as section 09 of [`data/dashboard.html`](../data/dashboard.html) and printed by
`python tools/analysis/execution_boundary.py`. Regenerate it rather than editing
the states below.

```
  REAL MARKET OBSERVATIONS   35, collected 2026-09-12
           ↓
  canonical observation            EXERCISED    §A.2, §B.4
           ↓
  admissibility                    EXERCISED    §A.3, §A.6
           ↓
  hour / band derivation           EXERCISED    §B.2.2
           ↓
  cell / parent / item keys        EXERCISED    §B.2.1, §E.4
           ↓
  exclusion replay                 EXERCISED    45/46 decidable, 1 not testable
           ↓
  band price                       DEGENERATE   n=1 in every cell-band group
  within-band dispersion           DEGENERATE   n=1 — returns 0.0 by definition
  source precedence                DEGENERATE   1 source; select() unreachable
  deduplication                    EXERCISED    0 duplicates observed
           ↓
──────────────── real data stops here: §C.1 needs a t−7 wave ────────────────
           ↓
  matched t / t−7                  PENDING      0 matched pairs from 1 wave
           ↓
  Jevons relative (§D.2)           PENDING
           ↓
  advance-cell / weekly chain      PENDING      LOCKED: I(c,t) = I(c,t−7)·J(c,t)
           ↓
  higher aggregation               PENDING      AMB-9 beyond one carrier
           ↓
  publication                      BLOCKED      AMB-8: expected_cells undefined
           ↓
  PUBLISHED INDEX                  NONE         no APIx market index exists
```

**EXERCISED** — the frozen code path ran against the real panel. It does **not**
follow that the statistical property is meaningfully validated.
**DEGENERATE** — the code executes, but the single-wave / single-source panel
supplies too little variation for the property to be established.
**PENDING** — the frozen methodology requires evidence that does not exist yet.

| Stage | Implementation | Test |
|---|---|---|
| Observations | `src/apix/schemas/observation.py` | `tests/test_collection_contract.py` |
| Store | `src/apix/ingestion/store.py` | `tests/test_collection_store.py` |
| Loader | `tools/collection/load_manual.py` | `tests/test_manual_loader.py` |
| Panel | `tools/analysis/build_panel_json.py` | `tests/test_observed_panel.py` |
| Exclusion replay | `tools/analysis/replay_exclusions.py` | `tests/test_execution_boundary.py` |
| Execution boundary | `tools/analysis/execution_boundary.py` | `tests/test_execution_boundary.py` |
| Matching | `src/apix/statistics/elementary/matching.py` | `tests/test_pipeline_14_day.py` |
| Jevons | `src/apix/statistics/elementary/jevons.py` | `tests/test_golden_values.py` |
| Chaining | `src/apix/statistics/index/chaining.py` | `tests/test_pipeline_14_day.py` |
| Aggregation | `src/apix/statistics/aggregation/young_laspeyres.py` | `tests/test_golden_values.py` |
| API | `src/apix/api/server.py`, `src/apix/api/payloads.py` | `tests/test_api.py` |
| Exports | `src/apix/export/exports.py` | `tests/test_exports.py` |
| Platform console | `tools/analysis/build_platform.py` → `data/platform.html` | `tests/test_platform_page.py` |
| Console motion layer | `tools/analysis/platform_motion.py` | `tests/test_platform_page.py` |
| Publication | `src/apix/statistics/index/publication.py` | `tests/test_pipeline_14_day.py` |

---

## What blocks publication

Four independent guards. None may be weakened to obtain a number.

| Guard | Where | Refuses |
|---|---|---|
| **§C.1 locked** | `index/chaining.py` | No index without a matched `t / t−7` pair |
| **AMB-8** | `publish(expected_cells_by_route=…)` — required, **no default** | Publication without a declared coverage denominator |
| **AMB-9** | `within_route_weights` raises `WeightError` | Multi-carrier weighting with no declared shares |
| **§A.3 exact** | `APWBucket.from_lead_time` returns `None` | A quote whose lead time matches no frozen bucket |

Plus `tests/test_architecture.py`, which fails the build if anything under
`src/apix/statistics/` imports `sklearn`, `lightgbm`, `xgboost`, `torch`,
`anthropic` or `openai`. **AI/ML is not a dependency of the published
statistic.**

---

## AMB-9 and the single-carrier case

The observed panel holds **one carrier** (IndiGo, 6E). At one carrier the
carrier allocation is **mathematically degenerate**: with §G.5's sum-to-one
constraint, the sole carrier on a route receives that route's entire weight
under *any* allocation rule, so no choice is being made and no unmeasured bias
is introduced.

**This does not resolve AMB-9, and the guard is unchanged.**
`within_route_weights` still raises `WeightError` the moment a route carries
more than one carrier without declared `carrier_shares`. What the degeneracy
establishes is narrower and worth stating precisely:

- the **single-carrier** case is safe to compute and safe to demonstrate;
- the **multi-carrier** case is genuinely blocked and needs an owner ruling
  before any route or carrier expansion.

See [`OPEN-AMBIGUITIES-checkpoint-2.md`](methodology/OPEN-AMBIGUITIES-checkpoint-2.md).

---

## Evidence

| | |
|---|---|
| Automated quality gate | pytest, Ruff (`check` + `format --check`), mypy, internal-link check and the semantic claim audit — all green in CI on every commit |
| Lint | `ruff check` + `ruff format --check` clean |
| Types | `mypy src/apix` clean |
| Reproducibility | `data/panel.json`, `dashboard.html`, `panel_report.txt`, `engine-validation.html` all regenerate **deterministically** — content-identical after Git's `eol=lf` normalisation. Verify with `git diff --exit-code data/`, not a raw checksum (see README) |
| Real observations | 35 · 7/7 frozen APW buckets · 5/5 bands · 35/35 reconciled |
| Provenance | 30 `PRIMARY_HASHED` + 5 `SECONDARY_CHAT_IMAGE` |
| Exclusions | 122, each with a reason and an id |
| Exclusion replay | 45/46 mechanically decidable exclusions reproduce the recorded §A.3/§B.2 verdict with zero disagreements; 1 record is not mechanically testable because the required departure-time field is unavailable. All 35 accepted observations pass the corresponding checks with zero false rejections. |
| Statistical coverage | **NOT ESTABLISHED** (AMB-8) |
| Published index | **NONE** |

Next unlock: **2026-09-19** — the second collection wave, after which the
matching and Jevons stages receive real data for the first time.
