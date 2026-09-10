# statistics/ — the deterministic spine

**Owner:** [@Rexy-5097](https://github.com/Rexy-5097) · **Implements:** `methodology_version 2.1`

```
STATISTICS CALCULATES.  ML/AI EXPLAINS.
```

## The boundary

Nothing here may import `sklearn`, `lightgbm`, `xgboost`, `torch`, `anthropic`
or `openai`, nor `analytics/` nor `ai/`.

Enforced by [`tests/test_architecture.py`](../../../tests/test_architecture.py), which
fails the build. **Do not weaken, skip or mark that test advisory.**

The published index must be reproducible from
`(snapshot_id, methodology_version, weight_version, code_version)` alone.

## Authority

This file is a **map, not a specification**. The contract is:

| Document | Role |
|---|---|
| [`apix_formula_spec_v1.md`](../../../docs/methodology/apix_formula_spec_v1.md) | `methodology_version 2.0`. **FROZEN and immutable historical record.** Superseded in the sections named below |
| [`apix_formula_spec_v2_1_draft.md`](../../../docs/methodology/apix_formula_spec_v2_1_draft.md) | The v2.1 amendment. **Authoritative for every rule it changes** |
| [`AMB-1-resolution.md`](../../../docs/methodology/AMB-1-resolution.md) | Why the amendment exists, with the proof |
| [`ADR-0062`](../../../artifacts/decisions/ADR-0062-item-cell-separation.md) | The decision record |

When code and methodology disagree, **the methodology wins and the code is
wrong** — unless the methodology is self-contradictory, in which case stop and
report it rather than choosing. That is how AMB-1 was found.

## The four statistical objects

The distinction v2.0 lacked, and the reason no Tier-1 cell could ever publish:

| Object | Key | Unit of | Weighted | Matched |
|---|---|---|---|---|
| **ITEM** | T1 `carrier × flight_number`<br>T2 `carrier × departure_hour_band`<br>T3 none | **matching** | no | **yes** |
| **CELL** | `route × carrier × day_of_week × apw × fare_class × channel` | **averaging + weighting** | yes, `v[c\|r]` | no |
| **PARENT** | `route × day_of_week × apw × fare_class × channel` | **fallback** | never | yes, over its own items |
| **ROUTE** | `route` | publication | yes, `w[r]` | no |

Five flights of one carrier on one route, weekday, lead time, fare class and
channel are **5 items in 1 cell producing 1 relative** — not 5 cells.

The cell key is **tier-invariant**. A tier change alters the item definition
only, so weights survive a mid-year degradation (spec F.5).

`day_of_week` is mechanically determined by `(t, apw)` and partitions nothing
within a collection date. It is kept because it is the **chain identifier**:
without it one key would name seven interleaved weekly level sequences.

## The parent has two quantities and they are not interchangeable

```
J(P,t)   parent fallback relative    Jevons over M(P,t)          BOTTOM-UP from
                                                                 raw observations
                                     -> spec E.4 carry ONLY

I(P,t)   parent reference level      weighted mean over the      TOP-DOWN from
                                     independent-live set        child levels
                                     -> spec J.1 entry ONLY
```

> **`I(P,t) = I(P,t-7) × J(P,t)` is forbidden.** The parent is not a chained
> index — no base period, no history. Writing it creates two competing
> definitions of the parent level that diverge silently.

The **independent-live set** excludes exactly one class of child: cells entering
at *t* under §J.1 against this parent, whose level *is* `I(P,t)`. **Carried
children stay in** — a carry depends on `J(P,t)`, not `I(P,t)`, so it creates no
recursion, and excluding carries would empty the set on exactly the thin strata
where carry is normal. An empty set means `I(P,t)` is undefined and the candidate
is **held out**, which is a different quality event from suppression.

## Module map

| Module | Implements |
|---|---|
| `elementary/matching.py` | item and cell assignment, identity stability per `(route, carrier)`, `M(c,t)`, source selection and transitions |
| `elementary/bands.py` | Tier-2 departure bands, the constructed band price, composition diagnostics |
| `elementary/sources.py` | ordered, versioned, **price-blind** source precedence |
| `elementary/jevons.py` | the log-form relative, minimum sample |
| `elementary/outliers.py` | median/MAD, unscaled, `n >= 5`, MAD = 0 declines |
| `elementary/{admissibility,dedup}.py` | spec A.6 and D.4 |
| `index/parent.py` | `J(P,t)`, `I(P,t)`, the independent-live set |
| `index/chaining.py` | chaining, carry, suppression, new-cell entry |
| `index/apix_l.py` | route and national aggregation, tier and status weight shares |
| `aggregation/` | Young / Modified Laspeyres, weights, renormalisation |
| `tpd/`, `uncertainty/` | not implemented — later checkpoints |

## Tier 2 is an identity relaxation, not a threshold relaxation

It relaxes how specifically an item is identified. It does **not** relax
`min_matched_items_per_cell`, and it does **not** guarantee a larger sample: a
band is one item however many flights it holds, so a carrier with four flights
in two bands passes at Tier 1 and **fails** at Tier 2.

The band price is the geometric mean of the band's admissible fares — the only
statistic under which the cell Jevons telescopes back into a flight-level Jevons
when membership is stable. When membership changes the ratio is a unit-value
ratio, and `band_overlap`, `band_membership_delta` and within-band dispersion say
so rather than absorbing it.

## Source handling

Selection takes the highest-ranked source present in **both** periods, so both
legs of every relative come from one source and a cross-source ratio is
impossible. Selection never reads the fare. When the selected source changes
between links the pair is flagged `SOURCE_TRANSITION`, excluded for **exactly one
link**, and resumes automatically. No bridge, no blending, no last-write-wins.

**Provisional.** The permanent reconciliation statistic is not frozen (OQ-A2).

## Testing means invariants — and end-to-end fixtures

Line coverage is the wrong target: an index engine can reach full coverage while
computing the wrong number. The invariant list is in
[CLAUDE.md](../../../CLAUDE.md#testing-means-invariants-not-coverage).

> **Unit tests verify functions. End-to-end statistical fixtures verify that the
> correct statistical objects reach those functions.**
>
> Every methodology-bearing layer carries at least one fixture that runs raw
> observations through to a published number.

AMB-1 survived sixteen hand-calculated golden values, an invariant suite and a
twelve-dimension adversarial review because **not one of them started from an
observation**. Those fixtures now live in
[`tests/test_e2e_v2_1.py`](../../../tests/test_e2e_v2_1.py).

Determinism extends to stochastic procedures. The bootstrap seed is derived
deterministically from the version vector and recorded with the output. **A
confidence interval that moves between runs of identical inputs is a defect, not
sampling variation.**

## Open empirical questions this layer cannot answer

`tools/ci/benchmark_apix_l.py` reports density, viability and tier shares as
**distributions**, never means — a mean of `1.000 items per cell` was what hid
AMB-1 in plain sight. Its frame is synthetic and proves only that the mechanism
works.

Whether real Indian schedules produce viable carrier-specific cells is
**OQ-A1**, answered by the seven-day collection spike. **OQ-A2** (cross-source
spread), **OQ-A5** (the minimum-matched-items threshold), **OQ-A7** (Tier-2 band
occupancy), **OQ-A8** (parent carrier concentration) and **OQ-A9** (source
transition and hold-out rates) are open alongside it. None may be closed by
choosing a plausible value.
