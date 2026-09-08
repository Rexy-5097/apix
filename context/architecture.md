# APIx architecture

> **Source of truth:** dossier section 05. This file summarises; the dossier governs.

## Three layers, one hard boundary

```
Layer 1 — Market observation
  Licensed feeds (Amadeus, Travelpayouts) · Airline portals (5 carriers)
  Aggregators (6 OTAs) · Declared tariff sheets
        ↓
  Compliance gate — robots.txt · crawl-delay · rate limiter · ToS register · circuit breaker
        ↓
Layer 2 — Official statistics engine   [deterministic · no ML imports]
  Normalisation → Deduplication → Quality control → Imputation
        ↓
  Canonical observation store — versioned, immutable, content-addressed
        ↓
  ┌─ deterministic ──────────────┐   ┌─ estimated ─────────────────┐
  │ Jevons → Young / Mod. Lasp.  │   │ TPD → rolling splice        │
  │        → APIx-L              │   │      → APIx-TPD             │
  └──────────────────────────────┘   └─────────────────────────────┘
        ↓
  version vector on every output:
  snapshot · methodology · basket · weight · parser · model · code · tier
        ↓
Layer 3 — Analytics   [reads the index, never writes it]
  Anomaly detection · Forecasting · Shock detection · Source health · LLM explanation
```

## The boundary is enforced, not documented

```
STATISTICS CALCULATES.  ML/AI EXPLAINS.
```

`src/apix/statistics/` may not import `sklearn`, `lightgbm`, `xgboost`, `torch`,
`anthropic`, `openai`, nor `src/apix/analytics/` nor `src/apix/ai/`.

`tests/test_architecture.py` parses every module under `src/apix/statistics/` with `ast`
and fails the build on violation. It is a required status check. See
[ADR-0059](../artifacts/decisions/ADR-0059-enforce-statistics-determinism-in-ci.md).

**Removal test:** delete the Claude API integration and the entire analytics
layer. Collection, cleaning, deduplication, Jevons, Young/Modified Laspeyres, TPD
and index publication must all still work. If they do not, the boundary has been
violated somewhere and the CI check will say where.

## Two estimators, never chained together

The paths are **alternatives, not stages**. Jevons output is never fed into the
TPD regression: doing so would strip the within-cell variation the hedonic model
needs, and double-count the aggregation.

| | APIx-L | APIx-TPD |
|---|---|---|
| Elementary | Jevons short-term relative over items matched in *t* and *t−7* | Quote-level panel |
| Aggregation | Young / Modified Laspeyres over cell **levels**, then route levels | TPD hedonic regression, rolling window |
| Joining | Weekly chain per cell | Mean splicing across windows |
| Quality adjusted | No | Yes, under a stated model |
| Role | CPI-aligned headline | Robustness and decomposition |

A third series, the **naive daily average**, is computed as the baseline that
demonstrates the problem.

## Relative at the bottom, level above it

Jevons produces a short-term **relative**; that relative chains into a cell index
**level**; levels are aggregated. Aggregating relatives directly, or dividing one
short-term relative by another, does not produce an index — and is the most
common way this construction goes wrong.

## The matched item is a recurring product class

A specific flight on a specific departure date exists exactly once and never
recurs, so the flight cannot be the item. But a cell holding one aggregated price
per period is a **unit value**, which is biased when the items inside are
heterogeneous — exactly the condition that holds for airfares.

APIx defines a recurring product class instead, and degrades in declared steps:

| Tier | Key | Used when |
|---|---|---|
| **1** — flight identity | carrier × flight_number × day_of_week × APW bucket × fare class × channel | identity stable for ≥ 70% of scheduled flights |
| **2** — schedule slot | carrier × departure_hour_band × day_of_week × APW bucket × fare class × channel | stability 40–70% |
| **3** — declared unit value | cell price published **as a unit value**, with within-cell dispersion reported | below 40% |

The tier is a property of each route, measured during the collection spike and
re-measured monthly. It is recorded per cell in the version vector, and a national
index whose Tier-3 weight share exceeds 25% publishes with a prominent caveat.

**Daily but weekly-matched.** Each cell advances on its own seven-day chain, so
the daily series is an aggregate over seven interleaved weekday chains. A Monday
and a Tuesday observation are never differenced against each other.

## Storage and serving

| Concern | Choice |
|---|---|
| Canonical store | PostgreSQL 16 |
| Snapshots | MinIO / S3, content-addressed, SHA-256 |
| Columnar | Parquet, via Polars / PyArrow |
| Cache | Redis |
| Orchestration | cron + a Python entrypoint, Docker Compose |
| Serving | FastAPI, SQLAlchemy, SDMX-JSON |
| Interface | Next.js + TypeScript, Tailwind, ECharts |

**Deferred and not built:** Airflow, ClickHouse, Kafka/Redpanda, TimescaleDB,
Kubernetes, OpenTelemetry. The dossier's risk register names *"team overbuilds
and nothing integrates"*; the deferred stack stays deferred.

## Provenance is a first-class feature

Any published value walks down to the bytes that produced it:

```
published value → cell contributions → accepted quotes → raw quotes → SHA-256 snapshots
```

Every record carries a `source_type` — `LIVE_SCRAPE`, `AUTHORIZED_FEED`,
`PUBLIC_DATASET`, `BACKFILLED`, `SYNTHETIC` — rendered distinctly and **never
blended silently**.

Published values are never overwritten in place. Every revision creates a new
vintage; the prior vintage stays retrievable.
