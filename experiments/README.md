# experiments/ — controlled experiments and ablations

**Owner:** [@Rexy-5097](https://github.com/Rexy-5097)

## Not yet implemented

Checkpoint 2.

## The six scenarios

The central claim — that naive aggregation accumulates composition effects while
the quality-adjusted estimator does not — is demonstrated where the true answer
is **known by construction**, not extracted from a conveniently chosen window of
real data.

Design: hold the comparable-product price process fixed by construction; let the
product mix evolve according to the mix path actually observed in the collected
data; run all three estimators on the resulting synthetic panel. Any departure
from the known true index is measured bias.

**One scenario is not an experiment. Six are run, and one is designed so the
method can fail.**

| | True price path | Perturbation | What it tests |
|---|---|---|---|
| A | Flat | Advance-purchase mix shifts | The core drift claim |
| B | +5% over window | Advance-purchase mix shifts | Real movement is not suppressed along with composition |
| C | Flat | Carrier mix shifts | Generalisation beyond the APW dimension |
| D | Flat | Cells go missing at observed rates | The imputation rule under attrition |
| E | Flat | Contaminating outliers injected | Robustness of the flagging rule |
| F | Flat | **Misspecified**: an unobserved price-driving characteristic, a nonlinear APW effect the bucket dummies cannot capture, heteroskedastic noise | Whether the method survives being wrong |

### Why scenario F is the one that matters

In A through E the data-generating process matches the estimator's
specification, so TPD recovers the truth by construction. That demonstrates the
arithmetic is correct; it does not demonstrate the method is sound.

F breaks the match deliberately. The result to report is **graceful degradation
with a stated residual bias**. TPD ending at 101.4 against a naive 107 is a far
stronger claim than TPD ending at exactly 100.0, because the first is a
measurement and the second is a tautology.

### Scenario A reports APIx-L too

APIx-L is itself a chained index and is therefore not drift-free by
construction. What differs is exposure: naive chaining links unmatched
aggregates, so every change in the quote mix enters the link, while APIx-L links
matched items only, at weekly frequency, within cells that already hold carrier,
fare class, channel and advance-purchase window fixed.

Scenario A reports the terminal value for **both**, so APIx-L's own residual
drift is a number known before the pitch rather than a rhetorical answer.

## Ablations

How much each design decision moves the index: with and without sold-out
imputation; with and without outlier flagging; equal-weighted versus alternative
advance-purchase curves; TPD window length across the 15 / 21 / 25 / 31
sensitivity sweep; matched-item tier forced down a level; and a five-day
simulated source outage to confirm the index stays inside its interval.
