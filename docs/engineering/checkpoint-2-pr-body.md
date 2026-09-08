## Summary

Implements the deterministic APIx-L spine from the frozen specification:
canonical types → admissibility → deduplication → matching → Jevons → weekly
chaining → Young/Modified Laspeyres → suppression and renormalisation → national
APIx-L, plus annual linking.

All 16 golden values are reproduced by the production code. 157 tests pass.
mypy, ruff and the architecture boundary are clean.

> ⚠️ **This PR is complete but reports a BLOCKING methodology ambiguity (AMB-1).**
> Under the specification's literal reading, **no Tier-1 cell can ever publish a
> relative**. See *Blocking ambiguity* below. The brief requires this be reported
> rather than silently resolved, so it has not been.

## Specification sections implemented

| § | Rule | Where |
|---|---|---|
| A | Observation contract, APW buckets, canonical fare, admissibility | `schemas/observation.py`, `elementary/admissibility.py` |
| B | Recurring product class, tier ladder, entitlement→fare class, channel in the key | `schemas/keys.py`, `elementary/matching.py` |
| C | Seven-day matching, interleaved chains, freshness, relative vs level | `elementary/matching.py`, `index/chaining.py` |
| D | Matched set, Jevons (log form), minimum sample, duplicates, sold-out, outliers | `elementary/{jevons,outliers,dedup}.py` |
| E | Base, chain, first observation, carry, disappearance/resumption | `index/chaining.py` |
| F | Young/Modified Laspeyres, route and national, renormalisation | `aggregation/young_laspeyres.py`, `aggregation/weights.py` |
| G | Weight hierarchy, equal APW as a declared v1 choice, invariants | `aggregation/weights.py` |
| H | Missing/sold-out taxonomy, conservative imputation | `elementary/admissibility.py`, `index/chaining.py` |
| I | Suppression thresholds, publish/carry/suppress/re-enter | `index/{chaining,apix_l}.py` |
| J | New-cell entry at the parent's level | `index/chaining.py` |
| K | Annual linking, isolated from the per-period path | `index/linking.py` |
| L | Deterministic assembly | `index/apix_l.py` |
| O/P | Version vector, reproducibility | `schemas/version_vector.py`, `index/apix_l.py` |

**Not implemented, by design:** TPD (§M), bootstrap (§N) — later checkpoints.

## Architecture

`src/apix/statistics/` imports nothing stochastic and nothing from
`apix.analytics` or `apix.ai`. Enforced by `tests/test_architecture.py`, which
**this PR had to repair** — see below.

Annual linking is deliberately *not* called by `calculate_apix_l`: within-year
chaining and year-to-year linking are different operations (§K.1) and the
boundary is kept visible.

## Statistical behaviour

Choices where the type system carries the rule rather than a comment:

- **`JevonsResult` cannot hold both a relative and an undefined reason**, nor
  neither — enforced in `__post_init__`. A relative of 1.0 asserts "the price did
  not move"; undefined asserts "we cannot say". Conflating them turns a missing
  observation into a published claim of price stability.
- **`aggregate_levels` raises on a mismatched key set** rather than intersecting.
  Silently intersecting is how a suppressed member's weight goes missing without
  renormalisation — the failure §F.4 exists to prevent.
- **An empty live set raises; it never returns 0.0.** Zero is a *level*; returning
  it would publish "the index is at zero" when the truth is "the index cannot be
  computed". `calculate_apix_l` withholds with `published=False`.
- **Carry takes the parent's RELATIVE, never its level** (§E.4) — separate
  parameters on `ChainInputs` so the distinction cannot be lost at a call site.
- **`payable_fare` is `Decimal`**, per the spec's rule that monetary arithmetic is
  decimal before the log transform.

## Tests

157 passing, in three files with different jobs:

| File | Job |
|---|---|
| `test_golden_values.py` | Runs **production code** against the 16 values hand-calculated at Checkpoint 1A |
| `test_statistical_edge_cases.py` | Every locked threshold crossed in **both** directions (INV-8), plus Hypothesis property tests |
| `test_methodology_invariants.py` | Validates the fixture itself (from 1A) |

The engine was written from the specification, not from the tests — finding R-10
of the Checkpoint 1A review. Had it been derived from them, the golden values
would prove nothing.

Thresholds tested from both sides: 2 and 3 matched items; 4 and 5 candidates for
the outlier gate; 13 and 14 days freshness; 0.40 and 0.41 imputation; 0.699 and
0.70 identity stability.

## Golden values

All 16 reproduced by production code. G-02, G-08 and G-09 are *discriminating* —
each records the wrong answer a plausible mis-implementation would give
(arithmetic mean → 1.1667; un-renormalised → 83.4; entry-at-100 → 104.8) and
asserts the production path does not produce it.

## Reproducibility evidence

- Identical inputs → **bit-identical** output (`==`, not `isclose`) — INV-9.
- Eight deterministic input permutations → identical level to the bit — INV-5.
- Every reduction runs in explicitly sorted key order. Floating-point addition is
  not associative, so an unordered sum would break bit-identity even with
  identical inputs (§P.2).
- Mixing collection dates is rejected outright — it would difference a Monday
  against a Tuesday (§C.2).

## Performance

Measured, not estimated:

```
15,120 quotes/day across 72 routes
  admissibility + dedup    0.161s
  cell assignment          0.231s
  matching + Jevons        0.539s
  APIx-L assembly          0.101s
  ----------------------------------
  full deterministic path  1.032s
```

Projects to **~17 minutes for a 1000-draw bootstrap**, single-threaded. Recorded
as a measurement; **OQ-5 stays OPEN** until it runs on real collected data.

## Defects found and fixed

A 12-dimension adversarial review raised 68 findings. These were independently
reproduced before anything was changed:

**INV-11 was unenforced — the most serious.** ADR-0061 moved the layers to
`src/apix/`, so an analytics import reads `apix.analytics`, whose *top-level*
package is `apix`. The detector matched only top-level names, so it could no
longer detect anything while continuing to pass. Proven: planting
`from apix.analytics.anomaly import detect` under `statistics/` left the suite
green. Fixed, with a parametrised regression test that plants each upper-layer
import and asserts it is caught.

**Deduplication omitted `route`**, collapsing 2,800 admissible quotes to 140 on a
full-frame day — 95% silently destroyed. Found by the benchmark, not by a unit
test: every dedup test used a single route.

**`fare_class` inverted §B.4's precedence**, pooling hand-baggage-only fares with
checked-baggage fares.

**`exclusion_rate_by_source` could only ever return 0.0** — it parsed a `source=`
token nothing emitted, so the alarm §A.6 calls *"the earliest available signal
that a site has been redesigned"* could never fire.

**`renormalise_over_live_set` did not check non-negativity**, and it is the only
weight function on the publication path; a negative weight became a routine route
suppression, hiding a data defect as a coverage problem.

## Blocking ambiguity — AMB-1

**Under the specification's literal reading, no Tier-1 cell can ever publish a
relative.**

§B.2 calls the Tier-1 key the **cell**; §D.1 says an item's identity within a cell
*is* that same key; §D.3 requires `|M(c,t)| >= 3`. All three cannot hold — if the
item key equals the cell key, each cell holds exactly one item per period.

Reproduced:

```
cell : 6E 101 dow=2 apw=7
|M|  : 1
J    : None   reason=BELOW_MIN_MATCHED_ITEMS
```

and at scale: **2,800 cells, 2,800 matched items — exactly 1.0 item per cell**,
with every route level landing on the harness fallback of `100.0000`.

The golden values did not catch it because they supply matched items directly and
never exercise cell assignment. Sixteen hand-calculated values, an invariant
suite and a 12-dimension review all passed over it; the benchmark found it,
because it was the first thing to run observations end to end.

**Not resolved here.** The likely reading — the Tier key is the *item* and the
cell is coarser — changes what an elementary aggregate *is*, which is a
methodology change requiring a version bump, an ADR and a golden-value update.
Choosing silently is exactly the failure the frozen specification exists to
prevent.

Full analysis, both candidate readings, and four further non-blocking
ambiguities: [`docs/methodology/OPEN-AMBIGUITIES-checkpoint-2.md`](../methodology/OPEN-AMBIGUITIES-checkpoint-2.md).

## Methodology impact

- [x] **No methodology change made.** Every LOCKED rule is implemented as written.

AMB-1 *requires* one, and this PR deliberately does not make it.

## Data contract impact

- [x] New canonical types in `src/apix/schemas/` — the first implementation of
      §A/§B/§O. No prior schema existed, so nothing is superseded.

`ExcludedObservation` gained `source_id` (defaulted, additive).

## Risk

- **AMB-1 blocks Checkpoint 3.** Collectors would feed a matching layer whose
  cell definition is unsettled.
- **AMB-4** (zero-baggage flexible fare) affects which cell a real product lands
  in. Confirm the ruling.
- **AMB-5**: the MAD guard is an exact float compare; a near-zero MAD reproduces
  the pathology the guard exists to prevent.
- The **`_route_result` fallback** converts an aggregation failure into a route
  suppression. Now guarded for negative weights, but other failures still
  degrade to suppression rather than surfacing.

## Rollback

Last known-safe checkpoint: **`530ef1a`** — CHECKPOINT 1A, merged via #2.
No prior statistics code exists, so reverting removes the layer entirely.

## Explicit exclusions

**Not in this PR, by design:** APIx-TPD (§M) · bootstrap and uncertainty (§N) ·
any ML or fitted model · forecasting · anomaly detection · scraping or collectors
· dashboard · FastAPI business logic.

`src/apix/statistics/tpd/` and `uncertainty/` remain empty `__init__.py`
placeholders. `ingestion/`, `api/`, `analytics/` and `ai/` are untouched.

---

### Reviewer notes

1. **[`OPEN-AMBIGUITIES-checkpoint-2.md`](../methodology/OPEN-AMBIGUITIES-checkpoint-2.md)** —
   read first. AMB-1 needs your ruling before Checkpoint 3.
2. **`index/chaining.py`** — the decision order in `advance_cell` is the densest
   piece of judgement here.
3. **`tests/test_architecture.py`** — confirm the repaired boundary check
   actually enforces what INV-11 claims.
4. **`aggregation/young_laspeyres.py`** — the raise-don't-intersect and
   raise-don't-return-zero choices.

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
