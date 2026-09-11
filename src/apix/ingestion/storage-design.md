# Collection storage — minimum production design

**Owner:** [@slazyverse](https://github.com/slazyverse) · **Checkpoint:** 2G · **Status:** designed, **not implemented**

Seven stores, plus one small table 2H added when the loader made its absence
concrete. Nothing more, because everything here has to exist before Day 1
and anything that does not is scope that delays the clock.

Technology follows `context/tech_stack.md`: **PostgreSQL 16** for records,
**MinIO/S3** content-addressed for raw artifacts. No new component.

---

## The seven stores

```
   raw_artifact ──────► canonical_observation ──────► cell_state
   (S3, sha256)         (the index input)             (latest per CellKey)
         ▲                      ▲                            │
         │                      │                            ▼
   collection_attempt ──────────┘                     publication
   (INCLUDING failures)                               (version vector)
         ▲
         │
   collection_run ──────► source_metadata
   (the anchor)           (registry snapshot)
```

### 1. `raw_artifact` — S3, content-addressed

| Field | Note |
|---|---|
| `sha256` | **Primary key.** Content-addressed, so identical bytes store once |
| `run_id`, `attempt_id` | Provenance |
| `content_type`, `byte_size`, `captured_ts` | |
| `storage_uri` | `s3://apix-raw/{sha256[:2]}/{sha256}` |

**Why raw bytes at all.** §P.3 requires a publication to be re-run and compared
**bit for bit**. That is impossible if only the parsed result survives. It also
means a parser fixed in week 3 can be re-run over week 1 rather than week 1
being lost.

Retention **≥ 90 days**. These are the largest objects and the only ones that
expire.

### 2. `canonical_observation` — the index input

One row per `Observation`. All §A.2 required fields, plus the 2G additions:
`source_group`, and the four `fare_breakdown` components.

| Constraint | Why |
|---|---|
| `PRIMARY KEY (observation_id)` | §A.2 |
| `UNIQUE (collection_date, source_id, carrier, flight_number, travel_date, departure_time_local, fare_class, channel)` | §D.4's duplicate tuple, **including route** via carrier+O&D — AMB-3 |
| `payable_fare NUMERIC(10,2) NOT NULL CHECK (> 0)` | **Never float.** Notation requires decimal before the log transform |
| `base_fare/taxes/fees/udf NUMERIC(10,2) NULL` | **NULL means unrendered, never zero** |
| `source_group TEXT NULL` | **NULL means ungrouped, never independent** — §B.6 |
| `run_id NOT NULL` | Reproducibility |

**Immutable.** Corrections create a new row under a new `run_id`; §R.3 —
published values are never overwritten in place.

#### 2a. `unpriced_flight` — the flights this table cannot hold

Added in 2H, when the loader was built and the gap became concrete.

A flight that was listed but sold no seat at any price is a **disappeared item**
(§D.6), not a missing price. It cannot live in `canonical_observation`:
`payable_fare` is non-optional and constrained positive, so the only ways to put
it there are to invent a number or to write a zero — and a zero asserts the fare
*was* zero.

Dropping it instead would be worse. "Sold out" and "this flight does not
operate" would become the same absence, and that distinction is exactly what
AMB-8's coverage denominator turns on: a sold-out flight is an expected cell
that produced no quote; a flight that does not operate is not an expected cell
at all.

It carries flight identity, timestamps, provenance and `availability` — and no
price, ever. It is **observed fact, not expectation**, so it is not the circular
basket table ruled out below.

### 3. `collection_attempt` — the store that makes missingness measurable

One row per `(source, route, travel_date)` attempted, **including every
failure**. Mirrors `CollectionAttempt`.

| Field | Note |
|---|---|
| `attempt_id` PK, `run_id` FK | |
| `outcome` | The seven `CollectionOutcome` values |
| `quotes_parsed`, `observation_ids[]` | Must agree — enforced in the dataclass |
| `http_status`, `latency_ms`, `detail` | Source health |

**Indexed on `(collection_date, outcome)`** because the two queries that matter
are the exclusion rate (§H.1) and the coverage denominator (§I, AMB-8), and both
scan by date and outcome.

> This is the store the project did not have, and the one AMB-8 needs. Without
> it a quote table records only successes, and **you cannot measure missingness
> from a table of successes.**

### 4. `source_metadata` — the registry, snapshotted per run

A frozen copy of the `source_registry/` entries **in force for that run**:
`automation_gate`, `manual_gate`, `source_group`, the precedence version.

Snapshotted rather than referenced because the register will change, and a
publication must be interpretable against the rules that governed it — not
against today's. A run that collected under `AUTOMATION_UNKNOWN` must still read
that way in a year.

### 5. `cell_state` — latest state per `CellKey`

Mirrors `CellState`. The store `publication.latest_states_as_of()` reads.

| Constraint | Why |
|---|---|
| `PRIMARY KEY (cell_id, collection_date)` | A cell has one state per **link date** |
| Index `(cell_id, collection_date DESC)` | The as-of lookup is the hot path |

**Append-only.** A non-link day writes **nothing** — under AMB-7's resolution a
cell that does not link has had *no state event*, so there is no daily row.
`latest_states_as_of` filters `collection_date <= t` and takes the newest, which
is why §P.3's vintage replay works against a store that has since grown.

This store is also the only possible source of `I(c, t−7)`, which §E.2 needs and
§L.1's diagram never shows arriving from anywhere.

### 6. `collection_run` — the reproducibility anchor

Mirrors `CollectionRun`: `run_id`, `collection_date`, the §A.5 window **actually
used**, `source_precedence_version`, `basket_version`, `parser_version`,
`collector_version`.

Every observation and attempt joins here, so the inputs behind a published
number are a query rather than a reconstruction.

### 7. `publication` — the vintage record

One row per published value: `collection_date`, `level`, the full version
vector, the `QualityMetrics` (coverage, suppressed weight, tier shares, the §C.3
freshness distribution), and `caveats`.

**Never updated.** §R.3 — every revision is a **new vintage**, and the prior one
stays retrievable.

---

## What is deliberately absent

| Not built | Why |
|---|---|
| A dashboard or API schema | Downstream; §10 of the 2G brief excludes it |
| TPD panel tables | §M.1 is quote-level and reads `canonical_observation`; no new store |
| Bootstrap draw storage | §N recomputes; drawing is not persisted |
| A `basket` table enumerating expected cells | **That is AMB-8.** Creating the table would invite filling it with observed cells, which is circular — coverage measured against our own success can never fall |

---

## Implementation order

1. **`collection_run` + `collection_attempt`** — smallest, and they unblock the
   attempt log the manual spike already produces.
2. **`canonical_observation`** + `unpriced_flight` + the raw artifact bucket.
3. **`source_metadata`** snapshotting.
4. **`cell_state`** — needed only when the index runs, not when collection starts.
5. **`publication`** — needed only at first publication.

**Steps 1–2 are the Day-1 requirement.** Steps 3–5 can land during the 30-day
window without disturbing it, because none of them changes what is collected.
