# Methodology

> **GATE CLEARED (Checkpoint 1A, 2026-09-08).**
> [`apix_formula_spec_v1.md`](apix_formula_spec_v1.md) is written and frozen for
> `methodology_version 2.0`. Golden values are frozen in
> [`tests/fixtures/statistical_golden_values.yaml`](../../tests/fixtures/statistical_golden_values.yaml)
> and the specification has been through an
> [adversarial review](adversarial_review_v1.md).
>
> Statistics implementation may begin at Checkpoint 2 — **written from the
> specification, not from the tests** (see R-10).

## The one artifact that must exist before any statistics code

Dossier section 13 is unambiguous:

> `docs/methodology/apix_formula_spec_v1.md` is frozen before the index engine is
> written. Not prose about the methodology — **the methodology, symbol by
> symbol**.

The purpose is narrow and important: two developers reading the same statistical
prose will implement two different indices. A frozen symbol table removes the
interpretation.

This is also the standing mitigation for a named risk in the dossier's register
— *"Two developers implement the aggregation differently"* — whose response is a
frozen formula specification with a symbol table, and **golden values computed by
hand before either implementation exists**.

### Required contents

Each item with its symbol, definition, reference period, weight source,
normalisation rule and edge cases:

- [ ] Unit of observation
- [ ] Matched-item definition and the Tier 1 / 2 / 3 ladder
- [ ] Jevons elementary short-term relative
- [ ] Cell index level and the weekly chain
- [ ] Young / Modified Laspeyres at route level
- [ ] Young / Modified Laspeyres at national level
- [ ] Weight normalisation and renormalisation on suppression
- [ ] New-cell entry rule
- [ ] Missing-cell rule
- [ ] Suppression thresholds
- [ ] Annual re-referencing and linking
- [ ] TPD specification: included and excluded characteristics
- [ ] TPD estimation thresholds and the action on each breach
- [ ] Rolling-window splice
- [ ] Bootstrap procedure and seed derivation
- [ ] Version vector and versioning rules

### Freezing it

Frozen means: merged to `main`, tagged, and changed only through a
`methodology_version` bump. Per dossier section 11, a methodology change **does
not revise the series** — it creates a new `methodology_version` and a new series
published in parallel with a linking factor, the same discipline CPI uses across
base revisions.

Owner: [@Rexy-5097](https://github.com/Rexy-5097). Checkpoint 1.

## Two decisions that must be recorded as declared choices

The dossier is explicit that these are unresolved, and that inventing an answer
would be worse than not having one.

1. **Route weights.** DGCA city-pair passenger volumes may not be publicly
   available at the assumed granularity. Fallback: scheduled seat capacity by
   city pair, as a proxy with a **stated and testable bias**. Gate 1 item.
2. **Advance-purchase weights.** No public Indian source is known to publish a
   booking lead-time distribution. v1 therefore uses **equal weights across APW
   buckets as a declared, documented choice**, with a sensitivity analysis
   showing how far the index moves under plausible alternative curves.
   Booking-curve weighting is claimed only once a source for it exists.

## Thresholds are methodology, not configuration

Every threshold in dossier sections 08 and 14 is a default fixed before
implementation. **Changing one changes the methodology version.** They are not
tunable parameters to adjust until output looks reasonable.

Each must have a test that crosses it in **both** directions.

## Planned documents

| Document | Purpose | Checkpoint | Status |
|---|---|---|---|
| [`apix_formula_spec_v1.md`](apix_formula_spec_v1.md) | The frozen symbol-by-symbol specification | 1A | **DONE** |
| [`../../tests/fixtures/statistical_golden_values.yaml`](../../tests/fixtures/statistical_golden_values.yaml) | 16 values computed by hand before implementation | 1A | **DONE** |
| [`adversarial_review_v1.md`](adversarial_review_v1.md) | Doubt-driven review of the specification | 1A | **DONE** |
| `experiments.md` | The six controlled scenarios and their results | 2 |
| `validation.md` | Short-window validation, with n stated | 4 |
| `publication_policy.md` | Release calendar, vintages, revision triggers | 4 |
| `METHODOLOGY.md` | The methodology note for external readers | 5 |

## Standing honesty constraints

- **APIx-L chains too.** The dossier says so explicitly. What differs is
  exposure: naive chaining links unmatched aggregates, APIx-L links matched items
  only. Scenario A reports the terminal value for **both**, so the residual drift
  is a measurement rather than a rhetorical answer.
- **Daily but weekly-matched.** Each cell advances on its own seven-day chain, so
  the daily series is an aggregate over seven interleaved weekday chains. A
  Monday and a Tuesday observation are never differenced against each other.
- **Validation is short-window, not a back-test.** The base periods do not
  overlap and thirty days is one monthly observation. Report direction agreement
  and magnitude gap **with n stated**.
- **Scenario F is the one that matters.** In A–E the data-generating process
  matches the estimator's specification, so TPD recovers the truth by
  construction — that shows the arithmetic is right, not that the method is
  sound. F breaks the match deliberately. Graceful degradation with a stated
  residual bias is a stronger claim than a tautological exact recovery.
