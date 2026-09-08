# statistics/ — the deterministic spine

**Owner:** [@Rexy-5097](https://github.com/Rexy-5097)

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

## Not yet implemented

Checkpoint 2 — and blocked until `docs/methodology/apix_formula_spec_v1.md` is
frozen. Writing index code before the specification is frozen is out of order.

## Layout

| Directory | Contents |
|---|---|
| `elementary/` | `jevons.py`, `matching.py` — the Tier 1 / 2 / 3 matched-item ladder |
| `aggregation/` | `young_laspeyres.py`, `weights.py` |
| `tpd/` | `specification.py`, `estimator.py`, `splice.py` |
| `uncertainty/` | `bootstrap.py` — cell resampling over the full index path |
| `index/` | `apix.py`, `publication.py`, `vintages.py` |

## The construction is relative at the bottom, level above it

Jevons produces a short-term **relative**; that relative chains into a cell index
**level**; levels are aggregated. Aggregating relatives directly, or dividing one
short-term relative by another, does not produce an index — and is the most
common way this construction goes wrong.

Two consequences that must not be blurred:

- **Daily but weekly-matched.** Each cell advances on its own seven-day chain, so
  the daily series is an aggregate over seven interleaved weekday chains, each
  contributing its most recent level. A Monday and a Tuesday observation are
  never differenced against each other.
- **A new cell enters at its parent's current level, never at 100.** Entering at
  100 injects a spurious jump into the aggregate.

## Testing means invariants

Line coverage is the wrong target: an index engine can reach full coverage while
computing the wrong number. The invariant list is in
[CLAUDE.md](../../../CLAUDE.md#testing-means-invariants-not-coverage).

Determinism extends to stochastic procedures. The bootstrap seed is derived
deterministically from the version vector and recorded with the output, so two
runs of the same publication reproduce the same interval to the last digit. **A
confidence interval that moves between runs of identical inputs is a defect, not
sampling variation.**

## A naming hazard to settle at Checkpoint 1

This directory is named `statistics/`, matching the dossier's repository layout.
At the repository root that shadows Python's standard-library `statistics` module
for anything importing it absolutely.

The architecture test is deliberately **static** — it parses files with `ast` and
never imports the package — so CI is unaffected. The hazard is real for runtime
code and must be settled deliberately (a `src/` layout, a package rename, or a
recorded accepted risk) before the first module lands here.

Flagged rather than silently resolved, because the layout is a dossier decision.
