# ADR-0063: Freeze methodology v2.1, and resolve AMB-7 as an implementation gap

> **Status:** Accepted | **Date:** 2026-09-10 | **Decider:** Rexy-5097
> **Checkpoint:** 2E | **Supersedes nothing** | **Depends on:** [ADR-0062](ADR-0062-item-cell-separation.md)

---

## Context

Two states of the repository had drifted apart.

**The implementation said v2.1.** PR #5, *"feat(statistics): implement APIx
methodology v2.1"*, merged as `4618b47`. The item/cell separation, the parent
object, source precedence, Tier-2 bands and the tier-per-`(route, carrier)`
rule are all on `main` and all tested.

**The methodology said v2.1 did not exist.** `apix_formula_spec_v2_1_draft.md`
carried, verbatim:

> **Status:** DRAFT — not frozen, not in force. Awaiting final methodology audit
> by @Rexy-5097.
> Nothing here is in force until the owner freezes it and a separate
> implementation change lands.

Meanwhile `apix_formula_spec_v1.md` still read *"FROZEN for methodology_version
`2.0`"* with no pointer to any amendment, and the golden fixture pinned
`methodology_version: "2.0"` while `tests/test_v2_1_invariants.py` constructed
version vectors reading `"2.1"`.

This is not cosmetic. §O.1 puts `methodology_version` on **every** published
output, and §P.1 keys the reproducibility guarantee on it:

> same `(snapshot_id, methodology_version, basket_version, weight_version,
> code_version)` ⟹ bit-identical APIx-L

A pipeline stamping `2.0` while running v2.1 code, or stamping `2.1` against a
document that says it is not in force, breaks §P.1 at the first publication. No
pipeline could be built until this was settled, independently of AMB-7.

## Problem

Three questions, and they are not the same question.

1. **Is v2.1's text consistent with what shipped?** The freeze is only honest if
   it is.
2. **What is AMB-7 — an ambiguity, or a defect?** It had been carried for three
   checkpoints as a possible A-vs-B methodology choice.
3. **What does the repository's own governance rule require of a freeze?** The
   rule is specific and the temptation to skip it is real.

## Evidence

### 1. One divergence, found and corrected

An audit of every **NEW** and **CHANGED** section of the amendment against
`main` found exactly one:

| §  | Amendment | Implementation | Verdict |
|---|---|---|---|
| B.2 | ITEM ≠ CELL, tier-invariant cell key, Tier-2 bands | `keys.py`, `bands.py` | ✅ |
| B.3 | Tier per `(route, carrier)` for cells | `apix_l.cell_tiers` | ✅ |
| B.4 | `HAND_ONLY` evaluated first | `observation.py:74` | ✅ |
| C.2 | `day_of_week` retained, not a weight dimension | `keys.py` docstring | ✅ |
| D.1 | Matched set keyed by ITEM | `matching.py` | ✅ |
| D.4 | `route` in the duplicate tuple | `dedup.py` | ✅ |
| D.8 | Ordered, versioned, price-blind precedence | `sources.py` | ✅ |
| E.4 | Parent = cell key minus `carrier` | `keys.ParentKey` | ✅ |
| E.6/E.7 | Parent relative and parent level | `parent.py` | ✅ |
| I | Thresholds UNCHANGED | `chaining.py`, `apix_l.py` | ✅ |
| J.0 | New item vs new cell | `chaining.py` | ✅ |
| **O** | **`source_precedence` NEW on the version vector** | **absent** | ❌ |

`sources.py`'s own docstring asserted the field existed — *"`SourcePrecedence.version`
is recorded in the version vector beside `weight_version`"* — and it did not.
Every output since PR #5 was priced by a precedence list it could not name,
losing the one property §D.8.2 calls **Reversible**. Corrected in `11f2b6f`,
before this freeze.

### 2. AMB-7 is an implementation gap, not a methodology ambiguity

The estimand is fixed by LOCKED text, and by dossier text those sections
reproduce verbatim (p.16, p.18, p.27):

| § | Text | Bearing |
|---|---|---|
| C.1 | *"APIx is a weekly-matched index published on a **rolling daily basis**, not a daily-matched one."* | Daily publication |
| C.2 | *"an aggregate over seven interleaved weekday chains, **each contributing its most recent level**"* | Non-linking chains contribute |
| C.3 | freshness at **publication date**, `t − max{s ≤ t : J computed}`, `∈ [0,6]` | Only reachable between links |
| F.2 | `I(r,t) = Σ_{c ∈ r ∩ L_t} v·I(c,t)` — the **live set** | Not "cells that linked at t" |
| F.5 | *"Levels `I(c,t)` vary **daily** (each on its own weekly chain)"* | Daily levels |
| R.1 | *"Provisional publication \| Same day"* | Daily publication |

And the arithmetic closes it. Under §A.3's exact lead-time assignment the seven
APW buckets `{1,3,7,15,30,45,60}` reduce mod 7 to `{1,3,0,1,2,3,4}` — **five
distinct offsets**. At most five of the seven chains can hold an observation on
any collection date, so **at least two must contribute an earlier link's level.**
§C.2 is arithmetically unsatisfiable otherwise.

The alternative reading — a non-linking cell leaves `L_t` — puts route coverage
at `1/7 = 14.29%` against §I's LOCKED `min_route_coverage = 60%`, suppressing
every route on every date. It cannot be reached without contradicting §C.2, §C.3
and §F.5 together. **There is no self-consistent reading in which a non-linking
cell leaves the live set.**

What was actually missing was a **layer**. `advance_cell` was correct and
link-scoped; `calculate_apix_l` was correct and differences nothing. Between
them nothing assembled the live set from states of different link dates, and a
date-equality assertion stood in the gap citing §C.2 — a section whose source
sentence forbids differencing two **observations**, and whose preceding clause
*mandates* aggregating levels of differing dates.

Reproduced over 14 dates on post-merge `main`: chains advanced correctly
(`100.0000 → 101.2635`) and **13 of 14 publications were rejected**.

### 3. What the governance rule actually requires

`apix_formula_spec_v1.md`, *Changing this document*:

> Any change to a LOCKED item requires: a new `methodology_version`, an ADR, an
> update to the golden values in `tests/fixtures/statistical_golden_values.yaml`,
> **and a parallel-published series with a linking factor.** It is not a code
> change.

Applied literally, item by item:

- **New `methodology_version`** — yes: `2.1`. That is this freeze.
- **An ADR** — this document, alongside ADR-0062.
- **Golden-value update** — every case in the fixture is stated at the level of
  items and prices, and v2.1 changes *which observations form an item and a
  cell*, not the arithmetic applied to them. The file is **byte-identical since
  the 2026-09-08 freeze** (one commit, `530ef1a`) and all 20 golden assertions
  pass under the v2.1 implementation. The update the rule asks for is recorded
  as `revalidated_under: "2.1"` in the fixture's `meta` — *verified unchanged*,
  which is the only truthful update available.
- **Parallel-published series with a linking factor** — **not applicable, and
  not manufactured.** §K.2 defines `LF = mean level of the new reference year /
  mean level of the old`. **No APIx series has ever been published**, under any
  `methodology_version`. There is no old series to link from, no continuity to
  protect, and a fabricated parallel series would be a fictional artifact
  asserting a comparison that never happened. §R.2's purpose is protecting
  *published* continuity; there is none yet to protect.

## Decision

**1. `apix_formula_spec_v2_1.md` is FROZEN as `methodology_version 2.1` and is
IN FORCE.** Renamed from `..._draft.md`; the fallback ladder is issued as
**§E.4.1** exactly as the document's own pre-freeze note required, so no v2.0
section number is displaced.

**2. `apix_formula_spec_v1.md` gains a header pointer and nothing else.** Its
body is byte-identical to the 2026-09-08 freeze. The amendment is a separate
file precisely so this one never has to be edited to stay true.

**3. AMB-7 is recorded as an IMPLEMENTATION GAP** against an already-defined
estimand, with **M1** and **M2** recorded as **CLARIFIED** — wording only, no
implementation conforming to the frozen text produces a different number.

**4. As-of is an implementation representation, not a third methodology.** It
computes `Σ v · I(c, most-recent-link ≤ t)`, which is what §C.2 already
specifies. **No fifth `CellStatus`**: a cell that does not link has had no state
event, so there is no outcome to record.

**5. AMB-8 (`expected_cells`) and AMB-9 (carrier allocation of `v[c|r]`) are
registered OPEN and are explicitly NOT resolved by this freeze.** Both change
published values. Both are made structurally visible rather than defaulted:
`within_route_weights` **raises** on a multi-carrier route with no declared
`carrier_shares`, and an undeclared coverage denominator produces a **caveat on
the published output** naming AMB-8.

**6. AMB-10 (`source_precedence` outside §P.1's reproducibility tuple) is
registered OPEN.** §P is UNCHANGED in v2.1 and names five fields; widening a
LOCKED rule without a ruling is exactly what this ADR declines to do.

## Consequences

**Good.**

- `methodology_version` means something again. §P.1's guarantee is stateable.
- The 13-of-14 rejection is gone: 14 of 14 publish, proven from `Observation`
  values in `tests/test_pipeline_14_day.py`.
- §C.3's *"published as a distribution"* is implemented rather than documented.
- Two open questions that were invisible are now impossible to pass silently.

**Bad, and accepted.**

- The freeze ratifies text whose implementation preceded it. The audit above is
  the mitigation, not a denial: the correct order is freeze-then-implement, and
  Checkpoint 2C did not follow it.
- v2.1's §D.8.1 remains **PROVISIONAL** (the procedure is LOCKED, the permanent
  reconciliation statistic is not — OQ-A2). Freezing does not settle it.
- AMB-8 and AMB-9 still block the production pipeline. The freeze makes that
  blockage explicit; it does not clear it.

**Neutral.**

- A cell that does not link produces no state record. Anything reconstructing a
  daily per-cell history must apply the as-of rule; there is no daily row.

## Rejected alternatives

**Freeze and absorb AMB-8/AMB-9 by choosing a plausible default.** Rejected.
Uniform carrier weighting would weight a carrier holding ~60% of a route's
passengers identically to one holding 3%. §S is explicit: *"None of these may be
resolved by choosing a plausible value."*

**Leave the amendment DRAFT and build the pipeline anyway.** Rejected: it breaks
§P.1 at the first publication and leaves the repository asserting two versions.

**Revert PR #5 to restore v2.0 coherence.** Rejected. It would discard a correct
AMB-1 resolution to fix a paperwork order, and reinstate a defect that made every
Tier-1 cell unpublishable.

**Add a fifth `CellStatus` for roll-forward, per the original Option A sketch.**
Rejected. It invents a state the spec does not have, forcing a §I.1 change and
with it the full LOCKED-change machinery — to describe a day on which nothing
happened.

**Manufacture a parallel series with `LF = 1` to satisfy the rule literally.**
Rejected as a fictional artifact. See Evidence 3.

## References

- [`docs/methodology/apix_formula_spec_v1.md`](../../docs/methodology/apix_formula_spec_v1.md) — §A.3, §C.1–C.3, §E.2, §F.2, §F.5, §I, §K.2, §O.1, §P.1, §R.1, §R.2, §S
- [`docs/methodology/apix_formula_spec_v2_1.md`](../../docs/methodology/apix_formula_spec_v2_1.md) — §C.2, §D.8, §E.4.1, §O
- [`docs/methodology/OPEN-AMBIGUITIES-checkpoint-2.md`](../../docs/methodology/OPEN-AMBIGUITIES-checkpoint-2.md) — AMB-7 … AMB-10
- [ADR-0062](ADR-0062-item-cell-separation.md) — the item/cell separation this freeze puts in force
- `src/apix/statistics/index/publication.py` · `src/apix/statistics/aggregation/within_route.py` · `tests/test_pipeline_14_day.py`
