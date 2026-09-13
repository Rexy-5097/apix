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
| **REAL-DATA VALIDATED** | Real collected market observations have passed through this code |
| **FIXTURE-ONLY** | Implemented and invariant-tested, but **only ever executed on synthetic test fixtures** |
| **SPECIFIED-ONLY** | The methodology defines it. **No implementation exists.** |
| **BLOCKED** | Implementation deliberately refuses, pending a decision that cannot be made in code |

---

## The sentence that matters most

> **Real observations currently do NOT enter `src/apix/statistics/`.**

The 35 collected observations reach `apix.ingestion.store` and
`apix.schemas`, and are then read by the analysis tools in `tools/analysis/`,
which compute **descriptive** statistics. They have never been passed to the
matching, Jevons, chaining, aggregation or publication code.

This is not an oversight. Spec **§C.1** is locked at
`I(c,t) = I(c,t−7) · J(c,t)`, so the elementary layer cannot even be invoked
without two collection waves seven days apart. One wave exists (2026-09-12). The
second is planned for **2026-09-19**, and that is the date the statistics layer
first sees real data.

Verifiable: `tools/analysis/build_panel_json.py` imports exactly
`apix.ingestion.store` and `apix.schemas.enums` — nothing from
`apix.statistics`.

**"The engine is complete" means every algorithm exists and passes its
invariant tests. It does NOT mean the production pipeline can publish a real
index today.** Those two claims are not equivalent and must not be substituted
for one another.

---

## Matrix

| Component | Specified | Implemented | Tested | Real-data validated | **Status** |
|---|:---:|:---:|:---:|:---:|---|
| Canonical observation model | ✅ | ✅ | ✅ | ✅ | **REAL-DATA VALIDATED** |
| Ingestion store (SQLite) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA VALIDATED** |
| Collection bridge (manual loader) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA VALIDATED** |
| Evidence / provenance grading | ✅ | ✅ | ✅ | ✅ | **REAL-DATA VALIDATED** |
| APW bucket assignment (§A.3) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA VALIDATED** |
| Departure-band assignment (§B.2) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA VALIDATED** |
| Fare-class derivation (§B.4) | ✅ | ✅ | ✅ | ✅ | **REAL-DATA VALIDATED** |
| Panel generation → `panel.json` | ✅ | ✅ | ✅ | ✅ | **REAL-DATA VALIDATED** |
| Dashboard + text report renderers | ✅ | ✅ | ✅ | ✅ | **REAL-DATA VALIDATED** |
| MoSPI benchmark ingestion | ✅ | ✅ | ✅ | ✅ *(reference only)* | **REAL-DATA VALIDATED** |
| Matching / tier ladder (§D.1) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Jevons elementary relative (§D.2) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Deduplication (§D.4) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Outlier / MAD rule | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
| Source precedence (§D.8) | ✅ | ✅ | ✅ | ❌ | **FIXTURE-ONLY** |
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
| API (FastAPI) | ✅ | ❌ | ❌ | ❌ | **SPECIFIED-ONLY** |
| SDMX serialisers | ✅ | ❌ | ❌ | ❌ | **SPECIFIED-ONLY** |
| Next.js dashboard (`dashboard/`) | ✅ | ❌ | ❌ | ❌ | **SPECIFIED-ONLY** |
| AgentOS framework | ✅ | ✅ | ✅ CI | n/a | **DEV INFRASTRUCTURE — not part of the statistic** |

`src/apix/statistics/tpd/`, `src/apix/statistics/uncertainty/`,
`src/apix/analytics/`, `src/apix/ai/`, `src/apix/api/` and
`src/apix/experiments/` are **empty packages**. A test
(`test_tpd_and_uncertainty_packages_are_genuinely_empty`) fails the build if
that stops being true without the documentation being updated.

---

## Pipeline trace — where real data stops

```
  canonical observations   ✅ REAL      35 observations, 2026-09-12
           ↓
  ingestion store          ✅ REAL      SQLite, 6 SHA-256 artifacts
           ↓
  panel generation         ✅ REAL      data/panel.json
           ↓
─────────────────── real data stops here ────────────────────
           ↓
  matching (§D.1)          ⬜ fixture   needs a t−7 wave
           ↓
  Jevons relative (§D.2)   ⬜ fixture   needs a matched set
           ↓
  advance-cell (§E.2)      ⬜ fixture   needs a relative
           ↓
  weekly chain (§C.1)      ⬜ fixture   LOCKED: I(c,t) = I(c,t−7)·J(c,t)
           ↓
  route aggregation        ⬜ fixture   AMB-9 beyond one carrier
           ↓
  Young/Mod. Laspeyres     ⬜ fixture
           ↓
  publication guard        ⬜ fixture   AMB-8: expected_cells undefined
           ↓
  PUBLISHED INDEX          ❌ NONE      no APIx market index exists
```

| Stage | Implementation | Test |
|---|---|---|
| Observations | `src/apix/schemas/observation.py` | `tests/test_collection_contract.py` |
| Store | `src/apix/ingestion/store.py` | `tests/test_collection_store.py` |
| Loader | `tools/collection/load_manual.py` | `tests/test_manual_loader.py` |
| Panel | `tools/analysis/build_panel_json.py` | `tests/test_observed_panel.py` |
| Matching | `src/apix/statistics/elementary/matching.py` | `tests/test_pipeline_14_day.py` |
| Jevons | `src/apix/statistics/elementary/jevons.py` | `tests/test_golden_values.py` |
| Chaining | `src/apix/statistics/index/chaining.py` | `tests/test_pipeline_14_day.py` |
| Aggregation | `src/apix/statistics/aggregation/young_laspeyres.py` | `tests/test_golden_values.py` |
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
| Tests | **369 passing** |
| Lint | `ruff check` + `ruff format --check` clean |
| Types | `mypy src/apix` clean |
| Reproducibility | `data/panel.json`, `dashboard.html`, `panel_report.txt`, `engine-validation.html` all regenerate **bit-for-bit** |
| Real observations | 35 · 7/7 frozen APW buckets · 5/5 bands · 35/35 reconciled |
| Provenance | 30 `PRIMARY_HASHED` + 5 `SECONDARY_CHAT_IMAGE` |
| Exclusions | 122, each with a reason and an id |
| Statistical coverage | **NOT ESTABLISHED** (AMB-8) |
| Published index | **NONE** |

Next unlock: **2026-09-19** — the second collection wave, after which the
matching and Jevons stages receive real data for the first time.
