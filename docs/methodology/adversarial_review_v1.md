# Adversarial review of the APIx v1 formula specification

> **Method:** doubt-driven review, run against
> `apix_formula_spec_v1.md` before it was declared frozen.
> **Reviewer stance:** assume the specification is wrong and try to show it.
> **Date:** 2026-09-08 · **Owner:** @Rexy-5097 · **Checkpoint:** 1A

Each finding states the attack, the mitigation, and whether the answer is
**LOCKED** (settled by rule) or **EMPIRICAL** (settled only by measurement).

An honest count: of the thirteen findings below, **eight are locked, five remain
empirical**. The empirical ones are not oversights — they are questions that
cannot be answered from a desk, and inventing answers for them would be the
worse failure.

---

## R-1. Could the matched item fail to recur?

**Attack.** The whole construction rests on a product class reappearing every
seven days. If flight numbers churn, Tier 1 has no items and the elementary
index is uncomputable. Worse, it could *partially* fail — enough items to compute
a relative, too few for it to mean anything.

**Mitigation.** The tier ladder (§B.2) degrades in **declared steps** rather than
failing: Tier 1 ≥ 70% identity stability, Tier 2 in [40%, 70%), Tier 3 below.
Tier is a property of **each route**, measured during the collection spike and
**re-measured monthly**. The tier is recorded per cell in the version vector, and
Tier-3 weight share above 25% puts a unit-value caveat on the headline.

Critically, §B.3 separates **identity stability** from **match coverage** and
states that they are different quantities:

> Flight numbers can be perfectly stable while the usable matched set collapses
> after conditioning on fare class, APW bucket, channel and determinable
> entitlements. Stability says the product recurs; coverage says enough of it
> survives to compute a relative from.

**Status: LOCKED (the ladder and its thresholds) / EMPIRICAL (OQ-2 — the
match-coverage floor).** The floor is set from the spike, *not invented now*.
This is the gate that can reshape the design, and the design says so.

---

## R-2. Could channel differences contaminate the cell?

**Attack.** A carrier-direct fare and an aggregator fare for the same seat differ
by a convenience charge. If both land in one cell, the "price change" measured
when the mix shifts between them is a channel artifact, not inflation.

**Mitigation.** **Channel is part of the cell key** (§B.5). An elementary cell
never mixes channels, by construction. The cross-channel difference is therefore
not averaged away — it becomes a **published diagnostic series** (the channel
spread), which additionally exposes parser drift early.

**Residual risk.** A source could silently change *what it includes* in the
displayed total — adding or dropping a convenience charge — without changing
channel. That would look like a price change. Mitigated indirectly: the canonical
fare concept (§A.4) is fixed, `parser_version` is in the version vector, and a
shift in the channel spread is visible on the diagnostic series.

**Status: LOCKED.**

---

## R-3. Could a change in APW composition create artificial movement?

**Attack.** This is the dossier's central claim turned back on APIx itself. If
the mix of advance-purchase windows shifts, a naive index moves without any
comparable product changing price.

**Mitigation, three layers deep:**

1. **APW bucket is part of the cell key** (§B.2), so a mix shift moves weight
   *between* cells rather than changing any cell's own relative.
2. **Weights are fixed for the index year** (§F.5), so between-cell mix shifts
   cannot move the aggregate either.
3. **The sampling frame** (§A.3) samples departures at fixed forward offsets, so
   APW varies cross-sectionally within every period. The fix lives in the
   sampling frame, not the estimator.

**But APIx-L still chains, and §L.3 says so explicitly.** Chaining is not the
defect; chaining *unmatched aggregates* is. APIx-L links matched items only, at
weekly frequency, inside cells that already hold carrier, fare class, channel and
APW fixed. The residual drift is bounded by matching quality — and controlled
experiment scenario A reports the terminal value **for APIx-L as well as** for the
naive index, so the number is known before anyone asks.

**Status: LOCKED (structure) / EMPIRICAL (the residual drift magnitude — scenario A).**

---

## R-4. Could route weights be unsupported?

**Attack.** §G.2 assumes DGCA city-pair passenger volumes at a granularity that
may not be publicly downloadable. If they are not, the weights are invented.

**Mitigation.** The specification does **not** assume the data exists. OQ-4 is
open, and a **fallback is locked in advance**: scheduled seat capacity by city
pair, derived from published airline schedules, as a proxy **with a stated and
testable bias**. If the fallback is used, `weight_version` records it and the
bias direction is published alongside the index.

The same discipline applies to APW weights (§G.4): no public Indian booking
lead-time distribution is known, so v1 uses **equal weights as a declared,
documented choice** with a published sensitivity band. Booking-curve weighting is
claimed only once a source for it exists.

> This is the finding most likely to be attacked in review, and the defensible
> answer is not a better guess — it is a declared choice plus a measured
> sensitivity band.

**Status: EMPIRICAL (OQ-4, OQ-7) with LOCKED fallbacks.**

---

## R-5. Could missing / sold-out treatment bias the index?

**Attack.** A sold-out flight is likely to have been the *cheap* one. Dropping it
biases the measured price level **downward** exactly when the market is tight —
the index would understate inflation precisely when inflation matters.

**Mitigation.** §D.6 refuses to treat a sell-out as a missing price:

> A sold-out flight is not a missing price. It is a disappeared item.

It is recorded as `SOLD_OUT` and excluded from the matched set, like any other
unmatched item. Imputation is deterministic and conservative (§H.2): a missing
cell inherits its **parent stratum's relative**, and where none exists the cell is
suppressed with the coverage loss published. Nothing more sophisticated ships in
v1, and model-based completion is explicitly confined to the analytics layer.

**Honest residual.** The bias direction is **plausible but not assumed**. OQ-3
tests it by comparing realised prices in cells shortly before and after sell-out,
and **reports the result**. **No correction is applied in v1** — applying one on
an untested assumption would be the larger error.

**Status: LOCKED (treatment rule) / EMPIRICAL (OQ-3 — the bias direction and
magnitude).**

---

## R-6. Could new cells create artificial jumps?

**Attack.** A new fare appears. If it enters a chained index at 100 while the
aggregate sits at 106, the aggregate is dragged down and the drop is recorded as
deflation. **A newly appearing fare is not a price change.**

**Mitigation.** §J locks entry at the **parent's current level, never at 100**,
and INV-10 asserts that entry moves no aggregate level on its entry date.

This is not left as prose. Golden case **G-09** works it numerically and records
*both* answers: the correct 106.0, and the wrong 104.8 that entry-at-100 would
produce — a spurious −1.13%. The test asserts the wrong answer is genuinely
different, so the case cannot rot into a tautology.

**Status: LOCKED, with a golden value and an executing test.**

---

## R-7. Could the daily rolling publication be misinterpreted?

**Attack.** APIx publishes daily. A reader will assume daily matching, and will
try to difference Monday against Tuesday. That comparison is meaningless: each
cell advances on its own seven-day chain, so consecutive calendar days come from
different interleaved chains.

**Mitigation.** §C states it and refuses to blur it:

> APIx is a weekly-matched index published on a rolling daily basis, not a
> daily-matched one. A Monday and a Tuesday observation are never differenced
> against each other.

**Chain freshness** (§C.3) is defined, recorded per cell, published as a
distribution, and a cell exceeding 13 days (two missed links) is suppressed
rather than carried.

**Residual risk — presentational, not mathematical.** A user can still difference
adjacent published values. The mitigation is the methodology switchboard screen
and the published freshness distribution; it cannot be enforced in the formula.
Flagged for the product surface at Checkpoint 5.

**Status: LOCKED (mathematically) / OPEN (as a presentation obligation).**

---

## R-8. Could TPD accidentally condition on endogenous variables?

**Attack.** Seats remaining, availability flags and promotion markers are the
most predictive regressors available. Including them would raise fit
dramatically — and would **absorb the very movement being measured**, because
they are jointly determined with demand and fare formation. The model would
report that prices barely moved, and be confidently wrong.

**Mitigation.** §M.3 excludes them by name — seats remaining, availability
signals, promotion flags, inventory-depth proxies — and states that **adding any
of them is a methodology change, not a modelling improvement**. That framing is
the actual defence: it forces a version bump and an ADR rather than a quiet
commit by whoever is tuning $R^2$.

**Residual risk.** An *included* characteristic could be endogenous in a way not
yet recognised — fare family is the candidate, since carriers reshape families in
response to demand. Not resolved here; flagged for the Checkpoint 2 experiments,
where scenario F (deliberate misspecification) is the relevant test.

**Status: LOCKED (the exclusion list) / OPEN (endogeneity of fare family).**

---

## R-9. Could the two estimators be incorrectly compared?

**Attack.** Reporting "APIx-L = 126.8, APIx-TPD = 121.4, so quality adjustment
removes 5.4 points" is wrong. The two accumulate along different paths from the
base period; a level gap is an artifact of cumulative divergence, not a statement
about the current period.

**Mitigation.** §M.8 locks it:

> **Compare GROWTH RATES, never LEVELS.**

The published quantity is **method divergence** = (APIx-L growth) − (APIx-TPD
growth) in percentage points over a stated horizon. §M.7 additionally forbids the
structural error: TPD output must never feed APIx-L, and Jevons output must never
feed the TPD regression — the latter would strip the within-cell variation the
hedonic model needs and double-count the aggregation.

**Status: LOCKED, and enforced structurally by the layer layout.**

---

## R-10. Could someone implement the formula in two different ways?

**Attack.** This is the dossier's own named risk. Two developers reading the same
prose implement two different indices, and the difference surfaces months later
as an unexplainable revision.

**Mitigation.** Four layers, and the review found this to be the strongest area:

1. **A frozen symbol table** — every symbol defined with reference period,
   weight source, normalisation rule and edge case.
2. **The log form of Jevons is normative**, not merely suggested (§D.2), so two
   implementations agree bit for bit rather than to eight decimals.
3. **Sixteen golden values, hand-calculated before any implementation**, each
   carrying its working.
4. **Discriminating cases.** G-02 gives exactly 1.0 under the geometric mean and
   1.1667 under an arithmetic one, so the most likely wrong implementation fails
   loudly instead of looking plausible. G-08 records what the *un-renormalised*
   answer would be; G-09 records what *entry-at-100* would produce.

**Residual risk.** The Checkpoint 2 engine could be written by reading
`tests/test_methodology_invariants.py` instead of the specification, which would
make the golden values a tautology. Mitigated by an explicit instruction in that
file's module docstring, but ultimately a review obligation, not a mechanical
one.

**Status: LOCKED, with the tautology risk flagged for Checkpoint 2 review.**

---

## Findings raised by this review that changed the specification

Three gaps were found while hand-computing the golden values. All three were
closed **before** freezing.

### R-11. The outlier rule was undefined when MAD = 0 — **now LOCKED**

With more than half the log relatives identical — common at long lead times when
a fare simply does not move — $\operatorname{MAD}_c = 0$, the threshold
$5 \times \operatorname{MAD}$ collapses to zero, and **every** non-identical
observation is flagged. The detector would destroy the data it exists to protect.

The dossier states no rule here. §D.7 now locks: **when MAD = 0, no flagging
occurs**, with golden case G-16 exercising it.

### R-12. The dossier's scale-invariance invariant is self-contradictory — **REPORTED**

Dossier §13 states: *"Scaling every price by k scales the index by k; the price
relatives are unchanged."*

Those clauses cannot both hold. Scale **both** periods and the relatives are
unchanged **and so is the index**. Scale **only the current** period and the
index scales by $k$ **but the relatives change**.

This specification does **not** silently pick one. It splits them into **INV-4a**
(scale invariance) and **INV-4b** (homogeneity) — both true, of different things
— with golden values G-04 and G-15 and a test for each. **Raised for the dossier
author's confirmation.**

### R-13. Exact-equality invariants are untestable in floating point — **now LOCKED**

INV-3, INV-4a, INV-6 and INV-10 are exact statements in real arithmetic,
evaluated in binary floating point after the log transform. Measured: the INV-10
golden case evaluates to `106.00000000000001` against an exact `106.0` — a 1-ulp
artifact of representing 0.32 in binary.

Asserting exact equality would produce a permanently failing test that a future
maintainer would "fix" by weakening the invariant. §Q.1 now locks a **relative
tolerance of 1e-12** for those four, while **INV-9 (reproducibility) remains bit
for bit**, because it compares two runs of the same computation where any
difference is a defect rather than representation noise.

---

## Summary

| # | Finding | Status |
|---|---|---|
| R-1 | Matched item may not recur | LOCKED ladder / **EMPIRICAL** OQ-2 |
| R-2 | Channel contamination | LOCKED |
| R-3 | APW composition drift | LOCKED / **EMPIRICAL** residual drift |
| R-4 | Route weights unsupported | **EMPIRICAL** OQ-4, OQ-7 + locked fallback |
| R-5 | Sold-out bias | LOCKED rule / **EMPIRICAL** OQ-3 |
| R-6 | New-cell jumps | LOCKED + golden value |
| R-7 | Daily publication misread | LOCKED / **OPEN** presentation |
| R-8 | TPD endogeneity | LOCKED list / **OPEN** fare-family |
| R-9 | Estimator comparison | LOCKED |
| R-10 | Divergent implementations | LOCKED + 16 golden values |
| R-11 | MAD = 0 undefined | **LOCKED (gap closed)** |
| R-12 | Dossier invariant contradictory | **REPORTED — awaiting author** |
| R-13 | Float tolerance undefined | **LOCKED (gap closed)** |

**No empirical question was resolved by choosing a plausible value.**
