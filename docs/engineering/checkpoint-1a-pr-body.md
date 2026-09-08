## Summary

Checkpoint 1A. **Specification-first:** the mathematical contract and its
hand-calculated expected values land *before* any index code exists.

Three deliverables: the `src/apix/` layout decision, the frozen formula
specification, and 16 golden values with an invariant suite that exercises them.

**No statistical implementation.** Every layer module under `src/apix/` is an
empty `__init__.py`.

## Problem

Dossier §13 requires `apix_formula_spec_v1.md` frozen *before the index engine is
written*, for a stated reason: **two developers reading the same statistical
prose implement two different indices.** That is a named risk in the dossier's
own register, and its stated mitigation is a frozen symbol table plus golden
values computed by hand before either implementation.

Checkpoint 0 also left one flagged, unresolved question: a root-level
`statistics/` package shadowing Python's standard-library module.

## Architecture decision — [ADR-0061](../../artifacts/decisions/ADR-0061-statistics-package-layout.md)

The shadow was **measured, not assumed**:

```
$ cd apix && python -c "import statistics; statistics.mean([1,2,3])"
AttributeError: module 'statistics' has no attribute 'mean'
(consider renaming '...\statistics\__init__.py' since it has the same name as
 the standard library module named 'statistics')
```

CPython emits its own rename hint. The failure is **directory-dependent** — from
any other working directory the same import resolves to the stdlib — so it
appears in one developer's terminal and not another's.

Honest about blast radius: nothing breaks *today*. `random.py` imports
`statistics` only inside its `__main__` block, and no currently installed package
imports it. The problem is that the failure is **latent and conditional**, and
the dossier's stack (SciPy, statsmodels, Polars, Pandera, Hypothesis) is not
installed yet.

**Decision: `src/apix/`.** This *follows* the dossier rather than departing from
it — the §13 tree is rooted at **`apix/`**, so those directories are the contents
of the `apix` package, not of the repository root. Only a `src/` prefix is added,
and the dossier's own CI snippet already reads `walk_imports("apix/statistics")`.

**Reported for the record:** the on-disk tree now differs from the dossier's
printed listing by one `src/` level. The logical package path is unchanged.

## Mathematical specification — [`apix_formula_spec_v1.md`](../methodology/apix_formula_spec_v1.md)

Sections A–T, every symbol defined with reference period, weight source,
normalisation rule and edge case. Covers: data unit · recurring product class ·
Tier 1/2/3 · 7-day matching · Jevons · cell chaining · Young/Modified Laspeyres ·
route and national aggregation · weight hierarchy · missing and sold-out ·
suppression · new-cell entry · annual linking · APIx-L pipeline · TPD ·
bootstrap · version vector · reproducibility · invariants · glossary.

Every decision is labelled **LOCKED** or **EMPIRICAL / OPEN**.

## Golden values — [`statistical_golden_values.yaml`](../../tests/fixtures/statistical_golden_values.yaml)

16 cases, each with its hand-working recorded. Several **discriminate** rather
than merely confirm:

| Case | What it would catch |
|---|---|
| G-02 | Arithmetic mean instead of geometric — gives 1.1667 where the answer is exactly 1.0 |
| G-08 | Forgetting to renormalise after suppression — records the wrong answer, 83.4 |
| G-09 | New cell entering at 100 instead of the parent level — records the wrong answer, 104.8 |
| G-15 | Confusing scale invariance with homogeneity |
| G-16 | Outlier rule flagging everything when MAD = 0 |

## Verification

```
pytest                    51 passed
ruff check .              All checks passed
ruff format --check .     17 files already formatted
mypy src/apix             clean
link check                70 files, all internal links resolve
yamllint                  clean
AgentOS validator         93/100 — unchanged by the migration
```

**The invariant suite was proven non-vacuous**: corrupting a fixture weight
(`0.375` → `0.999`) makes INV-1 fail, and restoring it returns the suite to
green. The architecture boundary remains non-vacuous after the move — its
`test_statistics_root_exists` guard means a renamed directory cannot make it pass
silently.

## Adversarial review — [`adversarial_review_v1.md`](../methodology/adversarial_review_v1.md)

Run before the specification was declared frozen. 13 findings: **8 locked, 5
empirical.** Three gaps were found *while hand-computing the golden values* and
closed before freezing:

- **R-11** — the outlier rule was **undefined when MAD = 0**, where the threshold
  collapses to zero and every non-identical observation is flagged. Common at
  long lead times. Now locked: no flagging occurs. Golden case G-16.
- **R-12** — the dossier's invariant *"Scaling every price by k scales the index
  by k; the price relatives are unchanged"* is **self-contradictory**. Split into
  INV-4a (scale invariance) and INV-4b (homogeneity), both true of different
  things. **REPORTED, not silently resolved — awaiting the dossier author.**
- **R-13** — exact-equality invariants are untestable in floating point; INV-10
  evaluates to `106.00000000000001`. Tolerance locked at 1e-12, with INV-9
  (reproducibility) still asserted bit for bit.

## Methodology impact

- [x] **Methodology impact — this PR *defines* the methodology.**

It establishes `methodology_version 2.0`. No prior version exists, so nothing is
superseded and no linking factor is required. Every subsequent change to a LOCKED
item requires a version bump, an ADR, updated golden values, and a parallel
series.

## Data contract impact

- [x] No schema change

`src/apix/schemas/` is still empty. §A defines the *observation contract* the
schemas must implement at Checkpoint 2.

## API impact

- [x] No external API change

§O freezes the version vector that API responses will carry.

## Security / compliance impact

None directly. The specification restates the compliance position: no CAPTCHA
solver, no evasion, an access challenge is a stop signal. §H.1 requires an
unavailable source to be recorded as a retrieval failure and **never silently
substituted** from another channel.

## Risk

- **The golden values could become a tautology** if the Checkpoint 2 engine is
  written by reading `test_methodology_invariants.py` instead of the
  specification. Mitigated by an explicit instruction in that file's docstring,
  but ultimately a **review obligation** (R-10).
- **Five empirical questions remain open** (OQ-2, OQ-3, OQ-4, OQ-5, OQ-7). The
  index cannot publish real numbers until they are measured. Locked fallbacks
  exist for the weight questions.
- **R-12 is unresolved pending the dossier author.** Both readings are
  implemented and tested, so no work is blocked.
- **Re-vendoring AgentOS** still drops patches UP-001 and UP-004.

## Rollback

Last known-safe checkpoint: **`c267f12`** — CHECKPOINT 0, merged via #1.

The migration is the only structurally risky part, and it is a pure `git mv` with
zero content change to the moved files.

## Open empirical questions

**None has been resolved by choosing a plausible value.**

| ID | Question | Fallback if unavailable |
|---|---|---|
| OQ-1 | Collection window start/end (IST) | — must be fixed and published |
| OQ-2 | Tier-1 match-coverage floor | Set from the 7-day spike, not invented |
| OQ-3 | Is low availability associated with higher prices? | Tested and reported; **no correction in v1** |
| OQ-4 | DGCA city-pair volumes public at required granularity? | Scheduled seat capacity proxy, bias stated |
| OQ-5 | Bootstrap runtime at 1000 draws | Reduce draws, **report the interval-width penalty** |
| OQ-6 | CPI airfare item label/code/frequency | Benchmark is configuration, not code |
| OQ-7 | Indian booking lead-time distribution | **Equal APW weights, declared**, with sensitivity band |
| OQ-8 | Licensed-feed coverage | Supplementary/backfill only, never a silent substitute |

## Screenshots

N/A — no UI in this change.

---

### Reviewer notes

The human owner has asked to **audit the formula specification before any
implementation**. Suggested reading order:

1. **[`apix_formula_spec_v1.md`](../methodology/apix_formula_spec_v1.md)** §C.4
   (relative vs level), §D.2 (the Jevons form), §F (Young/Modified Laspeyres),
   §J (new-cell entry) — these four carry most of the risk.
2. **[`adversarial_review_v1.md`](../methodology/adversarial_review_v1.md)** —
   especially R-12, which needs your confirmation as dossier author.
3. **[`statistical_golden_values.yaml`](../../tests/fixtures/statistical_golden_values.yaml)** —
   check the hand-working, not just the numbers. If a hand calculation is wrong,
   it is wrong *now*, before anything is built on it.
4. **[ADR-0061](../../artifacts/decisions/ADR-0061-statistics-package-layout.md)** —
   confirm the `src/` divergence from the dossier's printed tree is acceptable.

**A governance issue this PR will demonstrate rather than describe:**
`.github/CODEOWNERS` makes @Rexy-5097 the owner of `*`, `/src/apix/statistics/`
and `/docs/methodology/`, and branch protection requires code-owner review. Since
@Rexy-5097 authored this PR and GitHub forbids self-approval, **the code-owner
requirement cannot be satisfied by the author.** #1 merged only because `main`
was an empty commit with no CODEOWNERS file at the time. This needs a decision —
a second owner on Rexy-owned paths, or a different review rule.

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
