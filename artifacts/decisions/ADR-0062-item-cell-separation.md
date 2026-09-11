# ADR-0062: Separate the matching ITEM from the elementary CELL

> **Status:** Accepted | **Date:** 2026-09-09 | **Accepted:** 2026-09-10 (Checkpoint 2E) | **Decider:** Rexy-5097
>
> Put in force by the v2.1 freeze — see [ADR-0063](ADR-0063-freeze-methodology-v2-1.md).

---

## Context

Checkpoint 2 implemented the deterministic APIx-L spine from the frozen
specification `docs/methodology/apix_formula_spec_v1.md`
(`methodology_version 2.0`). The engine reproduced all 16 hand-calculated golden
values and passed 157 tests, with mypy, ruff and the architecture boundary clean.

The full-frame benchmark then produced an index in which every route level was
exactly `100.0000` — the harness fallback, not a computed number. Instrumenting
the pipeline gave:

```
2,800 admissible observations
2,800 cells
1.000 matched items per cell
J(c,t) = None    reason = BELOW_MIN_MATCHED_ITEMS    (every cell, every date)
```

This was raised as **AMB-1**. PR #3 was deliberately left blocked rather than
resolved in code: the Checkpoint 2 brief requires methodology ambiguities to be
reported, not silently decided.

## Problem

v2.0 uses **one key for two incompatible statistical roles**:

- §B.2 defines a tuple and calls it the **cell** — the elementary aggregate that
  carries a weight and a level;
- §D.1 says an item's identity within a cell **is that same tuple** — making it
  also the **matching** key;
- §D.3 requires `|M(c,t)| >= 3`.

The three cannot hold together.

**Proof.** §A.3 assigns the APW bucket by *exact* `lead_time_days`, so
`travel_date = t + apw` is a single date and `day_of_week = weekday(t + apw)` is
determined. Fixing route, carrier and flight number then names **one scheduled
departure**; fixing fare class and channel selects at most one canonical fare for
it, after §D.4 collapses same-source repeats. Therefore `|M(c,t)| <= 1 < 3` for
every Tier-1 cell at every date.

**§D.3 is unsatisfiable, not merely hard to satisfy.** It follows from the
*exactness* of §A.3 alone — no volume of data can change it.

**Independent second contradiction.** §B.1 is LOCKED and states that *"a cell
holding one aggregated price per period is a unit value"*, which it forbids.
§B.2 constructs exactly that object. This holds even if
`min_matched_items_per_cell` were 1. **Two LOCKED sections contradict each
other.**

## Evidence

**E1 — the dossier anticipated this exact failure** (v2.1, p. 17):

> *"the flight cannot be the item. But the cell cannot simply be substituted for
> it either: if a cell holds one aggregated price per period, a geometric mean
> across quotes inside it is a unit value, not a Jevons index."*

**E2 — the dossier never defines a cell key.** It defines the tier (item) keys
and the route and leaves the intermediate level undefined. That omission is the
root cause. Its one constraining sentence (p. 18):

> *"APIx-L links matched items only, at weekly frequency, **within cells that
> already hold carrier, fare class, channel and advance-purchase window
> fixed**."*

The cell holds carrier, fare class, channel and APW — **not** flight number.

**E3 — MoSPI's elementary aggregate pools many quotations.** Expert Group Report
§4.6: elementary indices are *"computed at the lowest level using individual
price observations"*; §4.6.1.1: Jevons requires prices *"for every price
quotation"*; §4.2.1: an elementary aggregate is *"the smallest groups of goods
and services for which expenditure data are available"*. One quotation per
aggregate is not the structure MoSPI describes.

**E4 — arithmetic on the project's own benchmark frame**
(20 routes × 5 carriers × 7 APW buckets × 4 flights = 2,800 observations):

| Reading | Cells | Items/cell | `\|M\| >= 3`? |
|---|---|---|---|
| v2.0 as written | **2,800** | **1.000** | never |
| Item/cell separated | **700** | **4.000** | in every cell |

Synthetic evidence only. It proves the design **can** satisfy the threshold; it
proves nothing about Indian schedules.

**E5 — Tier 2 accidentally works, which is itself diagnostic.** The
implementation's `ItemKey` is `departure_time_local`, so at Tier 2 (where the cell
carries an hour band) two flights in one band are two items. **The implementation
only works where item and cell already differ.**

**E6 — §E.4 is internally inconsistent.** Its prose says the parent is *"the cell
key with carrier and flight-identity dropped"*; its rendered tuple additionally
drops `day_of_week`. The prose also presupposes a cell key that *contains* flight
identity — so §E.4 is evidence **for** the broken reading, which is why this is a
methodology change rather than a clarification.

**E7 — a parent that drops only `day_of_week` cannot work.** At fixed
`(t, apw)` the weekday is determined, so such a parent contains *exactly the
cell's observations* and can never supply a relative when the cell cannot.

**E8 — §J.1 requires a parent level that v2.0 never defines** (logged as
**AMB-6**, resolved below).

**E9 — counter-evidence, recorded deliberately.** EG §4.4.3–4.4.4 shows MoSPI
responding to airfare sparsity by *pooling more routes* (*"for cities with
million plus population, airfare for 5 most popular routes may be collected"*).
APIx stratifies far more finely. The defence is collection volume
(~15,000–35,000 quotes/day versus a handful per route per month), **not** MoSPI
precedent.

## Options

| | Option | Elementary object | Outcome |
|---|---|---|---|
| **1** | Keep v2.0, lower `min_matched_items_per_cell` to 1 | unchanged | Does not repair the §B.1 conflict — the cell still holds one price per period |
| **2** | **Candidate A** — item = `carrier × flight_number`; cell adds `route`, drops flight identity | many items per cell, carrier fixed | **ADOPTED** |
| **3** | **Candidate B** — as A, `channel` removed from the cell | denser, channels mixed | Reverses LOCKED §B.5; violates §B.6 |
| **4** | **Candidate C** — as A, `carrier` pooled into the cell | much denser, carrier uncontrolled | Not adopted — see *Rejected alternatives* |
| **5** | **Candidate D** — Candidate C plus a weighted elementary Jevons using fixed DGCA carrier shares | dense **and** carrier-controlled | Departs from MoSPI's unweighted elementary index |

## Decision

**Separate the two roles into two keys.**

```
ITEM   Tier 1 : carrier × flight_number
       Tier 2 : carrier × departure_hour_band
                band price = geometric mean of that carrier's admissible
                fares in the band
       Tier 3 : none — declared unit value

CELL   route × carrier × day_of_week × apw_bucket × fare_class × channel
       invariant across all three tiers

PARENT route × day_of_week × apw_bucket × fare_class × channel
       relative : Jevons over the parent's own matched items, computed
                  from OBSERVATIONS, never from cell results
       level    : renormalised weighted mean of live child cells' levels
       never weighted, never published as an index

TIER UNIT   cells: (route, carrier)   parents: route   thresholds 70/40 unchanged

RUNTIME FALLBACK   CELL -> carrier-pooled PARENT -> SUPPRESS
```

**Accompanying rulings in the same amendment.**

- **Parent object fully specified** (§E.6). The item definition is identical at
  cell and parent level, which is what makes a carried relative comparable to a
  computed one. A **Tier-3 parent has no relative**, so the carry fails and the
  cell suppresses. The parent's matched set is built from **observations**,
  including those of suppressed children.
- **Parent level defined, non-recursively** (§E.7, resolves AMB-6). A definition
  over *all* live children is self-referential, because a cell entering under
  §J.1 has `I(C,t) = I(P,t)` by construction. The level is therefore the
  renormalised weighted mean over the **independent-live set**
  `L_ind(P,t)` — live children whose level at `t` is determined without reference
  to `I(P,t)`. **§J.1 entrants at `t` are the only exclusion; carried cells are
  retained**, because a carry depends on `J(P,t)` (bottom-up from observations),
  not on `I(P,t)`, so it creates no recursion. Excluding carries would discard
  well-determined levels and make hold-out far more frequent than the mathematics
  requires. If `L_ind(P,t)` is empty, `I(P,t)` is **undefined**, the candidate
  cell is **held out** per §J.2 (not suppressed — a distinct quality event,
  reported as `held_out_weight_share`), and existing carries are unaffected.
- **`I(P,t) = I(P,t-7) × J(P,t)` is explicitly FORBIDDEN.** The parent is not a
  chained index: it has no base period, no `t0` and no history. Writing it would
  create two competing definitions of the parent level that diverge silently. A
  boxed four-object distinction (`J(c,t)`, `I(c,t)`, `J(P,t)`, `I(P,t)`) is added
  so a future engineer cannot conflate the bottom-up relative with the top-down
  level.
- **Source transitions (NEW, conservative and provisional).** When the selected
  source changes between consecutive links, the pair is flagged
  `SOURCE_TRANSITION`, **excluded from `M(c,t)` for exactly one link**, recorded
  as a diagnostic, and resumes automatically once the new source has two
  consecutive selected observations. No bridge adjustment, no blending, no
  last-write-wins. **Recorded honestly:** the same-source-paired rule *already*
  makes a cross-source price comparison impossible; the genuine exposure this
  guards is the **splice of an item's series across two price bases between
  links**, and the specification says so rather than claiming the stronger,
  false rationale.
- **Tier 2 relabelled an *identity relaxation*, not a fallback.** It relaxes
  identity specificity, **not** §D.3, and can yield a *smaller* matched sample
  than Tier 1 — a carrier with four flights in two hour bands passes at Tier 1
  and fails at Tier 2. *Fallback* is reserved for the runtime level ladder.
- **Carrier mix in the parent is explicitly count-weighted** (§E.6.9) and
  disclosed, with `parent_carrier_count` and `parent_carrier_concentration`
  published.
- **Tier-2 band price = geometric mean**, because it is the only statistic that
  makes §D.2 telescope back into a Jevons over matched flights when band
  membership is stable. `band_overlap`, `band_membership_delta` and within-band
  dispersion are published so the composition exposure is measured, not hidden.
- **Source precedence (NEW):** an ordered, versioned list per channel; the
  matched pair must come from the **same source in both periods**. Deterministic,
  **price-blind**, auditable, reversible. The permanent reconciliation *statistic*
  is deliberately **not** frozen.
- **Fare-class precedence (CLARIFIED):** `HAND_ONLY -> STANDARD -> FLEX`,
  confirming the implemented behaviour — the only order under which all three
  classes are baggage-homogeneous.
- **`day_of_week` retained in the cell** as the **chain identifier**, not as a
  conditioning variable.
- **New item vs new cell (NEW):** a new flight in an existing cell is a new
  *item* and does not trigger §J.

`methodology_version` moves **2.0 → 2.1**. The test applied was whether identical
observations can produce different statistical results under the amended
definitions. They can — different cells, matched sets, relatives, levels, weight
vectors and tier assignments — so a bump is required; a patch-level bump would
falsely assert reproducibility across 2.0 and 2.0.x. A **minor** bump is correct
because the formula family, weight hierarchy, publication cadence and
version-vector structure are unchanged.

## Consequences

**Positive.**

- Tier 1 can publish. `|M(c,t)| >= 3` becomes attainable rather than impossible.
- §B.1's prohibition on one-price-per-period cells is satisfied for the first
  time.
- The cell is tier-invariant, so a mid-year tier degradation cannot re-partition
  cells and therefore cannot re-derive weights — required by §F.5.
- The `ItemKey = departure_time_local` fragility is repaired incidentally: a
  ten-minute retiming no longer unmatches a flight from itself.
- Multi-source reconciliation stops being an undeclared insertion-order accident,
  and the new rule is **price-blind**, so it cannot bias the level by
  construction.
- Two previously undefined quantities — the parent relative and the parent level —
  are now computable by an independent engineer from the specification alone.

**Negative / accepted.**

- **Carrier-mix drift is confined, not eliminated.** Carried cells inherit the
  parent's relative, and the parent weights each carrier by its count of matched
  flights (§E.6.9). **The claim "carrier mix is controlled by construction" is
  incorrect and is forbidden in APIx documentation, presentations and the
  dashboard.** The accurate claim is *"controlled where the cell computes its own
  relative; confined and measured where it carries."*
- **Thin-route density is unquantified** (**OQ-A1**) and is the dominant open
  risk.
- **`min_matched_items_per_cell = 3` becomes binding for the first time** and was
  never calibrated — it was locked against an object for which no threshold was
  meaningful (**OQ-A5**). Retained unchanged in v2.1 deliberately: one change at
  a time.
- **Tier 2 acquires a unit-value exposure** when band membership differs between
  periods, and — newly identified — **is structurally capped at ~6 realistic items
  per cell**, so `min_matched_items = 3` binds *harder* at Tier 2 than at Tier 1.
  Tier 2 is not uniformly a more permissive tier (**OQ-A7**).
- **Golden-value fixtures need key migration.** The 16 numeric values remain valid
  (they operate at or above the cell *level*); their key literals must be
  rewritten. That is a test-code change and must be reported as one.
- **Two new conservative rules withhold data, at unknown frequency.** The
  source-transition exclusion (§D.8.3) removes items exactly when source coverage
  is weakest; the empty-independent-live-set hold-out (§E.7.4) blocks new-cell
  entry. Both are deliberate and both are measured — **OQ-A9** — but neither's
  cost is yet known, and either could concentrate in heavy strata.
- **This is a methodology change, not a clarification** (E6).

**MoSPI positioning — stated so it is not overclaimed later.**

| Element | Status |
|---|---|
| Jevons at the elementary level; Young/Modified Laspeyres above | **DIRECT MoSPI REQUIREMENT** (FAQ Q20/Q21, EG §4.6) |
| Elementary aggregate pools many individual quotations | **DIRECT MoSPI REQUIREMENT** (EG §4.6, §4.6.1.1) |
| New specification waits for two consecutive periods | **DIRECT MoSPI REQUIREMENT** (EG §4.6.5.2(c)) |
| Carrier in the cell | **UNKNOWN in MoSPI — APIx DESIGN DECISION** |
| Channel in the cell | **APIx DESIGN DECISION that departs from MoSPI**, which pools platforms *"to ensure representativeness"* |
| Seven APW buckets; daily publication; tier ladder; tier unit; source precedence; Tier-2 band construction; parent fallback design | **APIx DESIGN DECISIONS** |
| `T+21` alignment with MoSPI's domestic point | **EMPIRICAL / OPEN — OQ-A6**, deliberately excluded from this amendment |

## Migration

**Sequenced; each step gated on the previous. No step is taken before the owner's
audit of this ADR and the two methodology documents.**

1. Freeze `apix_formula_spec_v2_1.md`; `methodology_version` is set there
   and nowhere else.
2. Write **E2E-01 … E2E-13** against the frozen amendment and confirm they
   **fail** (specification-first). E2E-06b, E2E-11, E2E-12 and E2E-13 cover the
   Tier-2 density regression, parent-level recursion exclusion, carried-child
   inclusion plus hold-out, and the source transition respectively.
3. Extend the golden fixture: cell assignment, items-per-cell, parent relative
   from observations, parent level from children. Migrate existing key literals.
   **Do not touch the 16 numeric values.**
4. Amend production code — `schemas/keys.py` (split `CellKey` / `ItemKey`, fix
   `parent()`), `elementary/matching.py` (`cell_key_for`, `item_key_for`,
   `build_matched_set`, band price, source precedence, stability unit),
   `index/chaining.py` (new-item vs new-cell trigger, parent level),
   `index/apix_l.py` (tier plumbing), `schemas/version_vector.py`
   (`source_precedence`).
5. Re-run the full suite and the benchmark; report items-per-cell as a metric.
6. Amend PR #3 or supersede it — owner's call at step 5.

**Rollback.** Every step before 4 is documentation and test-only. Reverting the
code amendment restores v2.0 behaviour, which is known-broken at Tier 1 but
deterministic; the last known-safe checkpoint remains `530ef1a` (Checkpoint 1A,
merged via #2).

## Rejected alternatives

| Alternative | Verdict |
|---|---|
| **Keep v2.0, lower `min_matched_items_per_cell` to 1** | **Rejected.** It would not repair the §B.1 conflict: the cell would still hold one price per period, which §B.1 defines as a unit value and forbids |
| **Candidate B — remove `channel` from the cell** | **Rejected.** Reverses LOCKED §B.5 (*"an elementary cell never mixes channels"*), destroys the publishable channel spread, and multiplies shared inventory into false observations, violating §B.6 |
| **Candidate C — pool `carrier` into the cell** | **Not adopted.** *Candidate C is a separately versioned future methodology alternative that may be evaluated if empirical density under Candidate A is inadequate.* It is **not** a runtime fallback, not a degradation path, and not reachable by any code path in v2.1 — the complete runtime behaviour is `CELL -> PARENT -> SUPPRESS`. Adopting it would require its own version bump, ADR, amendment and audit. Trigger for evaluation: **OQ-A1** |
| **Candidate D — weighted elementary Jevons with fixed DGCA carrier shares** | **Rejected.** It would give both density and explicit carrier control, but MoSPI's elementary index is an *unweighted* geometric mean of quotations (EG §4.6.1.1) — a departure at the one level where APIx currently matches MoSPI exactly — and it needs carrier-share weights of unproven availability |
| **Parent that drops only `day_of_week`** | **Rejected by proof** (E7): it releases no dimension and can never supply a carry relative |
| **Deeper fallback ladder (channel-pooled, then route)** | **Rejected for v2.1.** Deeper pooling buys coverage by violating a LOCKED homogeneity rule, and suppression is already the visible, published terminal behaviour |
| **Independently chained parent level** | **Rejected, and now explicitly forbidden.** It would drift from its children's weighted mean, so seeding a new cell there would inject exactly the jump §J.1 exists to prevent, and it would create a second competing definition of `I(P,t)` |
| **Solving the parent level as a fixed point** (allowing `I(P,t)` on both sides) | **Rejected.** Algebraically solvable, but it would let a new cell's own weight influence the level it enters at — precisely the spurious contribution §J.1 exists to prevent. The recursion is excluded by definition instead |
| **Excluding *all* inherited children from the parent level** (including carried cells) | **Rejected as over-broad.** A carry depends on `J(P,t)`, not `I(P,t)`, so it introduces no recursion. Excluding carries would discard well-determined levels and, on thin routes where carry is common, could empty the independent-live set almost always — converting a definitional safeguard into a systematic hold-out |
| **Allowing a silent source switch between links** | **Rejected.** Each individual relative would remain same-source and therefore clean, but the chained level would splice two price bases with no disclosure at the point of change |
| **A bridge adjustment or blend across sources at a transition** | **Rejected.** Both require assuming the two sources' price concepts are equivalent, which is exactly what the cross-source spread diagnostic exists to test rather than assume |
| **Arithmetic mean or median for the Tier-2 band price** | **Rejected.** Only the geometric mean telescopes into the log-form Jevons above it when band membership is stable; §D.7 already supplies robustness one level up |
| **`source_id` in the item key** | **Rejected.** It would inflate effective *N* with shared inventory, violating §B.6 |
| **A parent-specific minimum-match threshold** | **Not decided — no number invented.** The cell threshold applies unchanged; `parent_carrier_count` and `parent_carrier_concentration` are published, and whether a rule is needed is **OQ-A8** |
| **Adding `T+21` in this amendment** | **Rejected for scope.** Separable from AMB-1; bundling two methodology changes into one audit weakens both. **OQ-A6** |

## References

- [`docs/methodology/AMB-1-resolution.md`](../../docs/methodology/AMB-1-resolution.md)
- [`docs/methodology/apix_formula_spec_v2_1.md`](../../docs/methodology/apix_formula_spec_v2_1.md)
- [`docs/methodology/OPEN-AMBIGUITIES-checkpoint-2.md`](../../docs/methodology/OPEN-AMBIGUITIES-checkpoint-2.md)
- `docs/methodology/apix_formula_spec_v1.md` — v2.0, FROZEN, unchanged
- MoSPI, *CPI 2024 Series FAQ* (Annexure V)
- MoSPI, *Expert Group Report on Comprehensive Updation of the CPI*
- [ADR-0061](ADR-0061-statistics-package-layout.md) — the `src/apix/` layout the
  code changes would land in
- [ADR-0059](ADR-0059-enforce-statistics-determinism-in-ci.md) — the determinism
  boundary this amendment does not touch
