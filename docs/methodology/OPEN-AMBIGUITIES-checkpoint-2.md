# Methodology ambiguities found while implementing Checkpoint 2

> **Raised, not resolved.** The Checkpoint 2 brief is explicit: *"If any
> methodology ambiguity is discovered: STOP and report it"* and *"If any
> required statistical behavior cannot be implemented from the frozen
> specification: STOP and report it."*
>
> **Owner to rule on these:** @Rexy-5097 (methodology owner).
> **Status:** AMB-1 **RESOLVED** ([ADR-0062](../../artifacts/decisions/ADR-0062-item-cell-separation.md), methodology v2.1). AMB-2 to AMB-4 confirmed; AMB-5 open, non-blocking.
> **AMB-7 RESOLVED** as an implementation gap ([ADR-0063](../../artifacts/decisions/ADR-0063-freeze-methodology-v2-1.md)).
> **AMB-8 and AMB-9 are OPEN and BLOCK the production pipeline.** AMB-10 is
> open, non-blocking.
>
> **AMB-7 to AMB-10 were raised after Checkpoint 2, against merged code.**
> They are recorded here rather than in a new file because this is where a
> reader looks, and because AMB-7 is the first ambiguity in this project to
> reach a **merged PR** without ever being written down. That is the control
> failure, and it is the reason these four have entries at all.

The frozen specification exists because *"two developers reading the same
statistical prose will implement two different indices."* Implementing it is the
first real test of whether the symbol table actually removed the interpretation.
It mostly did. These are the places it did not.

---

## AMB-1 — **RESOLVED** (raised BLOCKING). The specification does not distinguish the *cell* from the *item*, and under the literal reading `min_matched_items_per_cell = 3` is unsatisfiable

### The contradiction

Spec B.2 defines the Tier 1 key:

```
c = (carrier, flight_number, day_of_week, apw_bucket, fare_class, channel)
```

and calls it the **cell**. Spec D.1 then defines the matched set as *"items
present in both t and t-7"* where *"an item's identity within a cell is its
matching key (§B.2)"* — the same key. Spec D.3 requires:

```
|M(c,t)| >= min_matched_items_per_cell = 3
```

**These three cannot all hold.** If an item's identity within a cell is the cell
key, each cell contains exactly one item per period, so `|M| <= 1` always, and
the three-item minimum can never be met.

It is not a boundary case. Fixing carrier, flight number, weekday, APW bucket,
fare class and channel identifies **one departure**: a collection date *t* plus an
APW bucket determines the travel date exactly, and flight 6E101 departs once.

### Reproduced

```
cell            : 6E 101 dow=2 apw=7
|M|             : 1
J               : None   reason=BELOW_MIN_MATCHED_ITEMS
```

The full-frame benchmark confirms it at scale: **2,800 cells, 2,800 matched
items — exactly 1.0 item per cell** — and every route level came out at exactly
`100.0000`, which was the harness's fallback rather than a computed index.

**Under the literal reading, no Tier-1 cell can ever publish a relative, and
APIx-L cannot be computed from real observations at its preferred tier.**

### Why this was not caught earlier

Golden values G-01 through G-04 and G-15 supply matched items *directly* and
verify the Jevons arithmetic. They never exercise cell assignment, so they pass
while the layer that would feed them in production cannot produce a set of three.
That is a real gap in the Checkpoint 1A fixture, and it is worth recording that
16 hand-calculated values, an invariant suite and a 12-dimension review all
passed over it — the benchmark found it, because the benchmark was the first
thing to run observations end to end.

### The two candidate readings

**Reading A — the Tier key is the ITEM; the cell is coarser.**

The dossier says the Tier 1 key gives *"price relatives between comparable
product classes"*, and calls the recurring product class the thing that recurs.
On this reading:

```
item = (carrier, flight_number)             # the recurring product class
cell = (route, day_of_week, apw_bucket, fare_class, channel)
```

A cell then holds every flight on that route/weekday/APW/class/channel, `|M| >= 3`
is reachable, each cell still advances on its own seven-day chain (day_of_week is
in the cell), and Jevons averages over flights — which is what a geometric mean
of price relatives is *for*.

*Against it:* spec E.4 defines `parent(c) = (route, apw_bucket, fare_class,
channel)` as *"the cell key with carrier and flight-identity dropped"*. Under
Reading A the cell never contained carrier or flight identity, so that sentence
does not describe it — the parent would be the cell minus `day_of_week`.

**Reading B — the cell is the Tier key as written.**

Then `min_matched_items_per_cell = 3` must apply to something other than the
matched set of one cell, and the spec does not say what.

### Recommendation

Reading A, with spec E.4's parent definition corrected to
`(route, apw_bucket, fare_class, channel)` = the cell minus `day_of_week`.

**This has not been implemented.** Choosing between these silently is precisely
the failure the frozen specification exists to prevent, and Reading A changes
what an elementary aggregate *is* — a methodology change requiring a
`methodology_version` bump, an ADR, and a golden-value update, not a code fix.

### What is affected

| Component | State |
|---|---|
| `build_matched_set`, `cell_key_for`, `ItemKey` | **Blocked** — depend on the ruling |
| Jevons relative, outlier rule | Implemented and verified; operate on a matched set however it is formed |
| Chaining, carry, suppression, entry, aggregation, APIx-L assembly, linking | Implemented and verified; operate on levels and are unaffected |

---

## AMB-2 — `|M(c,t)|` denotes two different sets in D.3 and D.7

Spec D.7 gates the outlier rule at `|M(c,t)| >= 5` and states flagged items are
*"excluded from M(c,t)"*. Spec D.3 requires `|M(c,t)| >= 3` for J to be defined.
Both write `|M(c,t)|`, but the first must mean the **candidate** set (flagging has
not happened yet) and the second the **surviving** set.

**Resolved by the §L.1 pipeline**, which fixes the order D.1 -> D.7 -> D.2, so the
reading is determined. Implemented that way and documented at the call site.
Raised only so the notation can be tightened at the next version bump.

**Non-blocking.**

---

## AMB-3 — the duplicate tuple omits `route` while the same sentence scopes duplicates to a cell

Spec D.4: *"two observations **in the same cell** at the same t with identical
(carrier, flight_number, travel_date, departure_time_local, fare_class, channel,
source_id)"*. A cell key begins with the route, so the parenthesised tuple is
under-specified relative to its own scoping clause.

**Consequence measured:** without `route`, a full-frame synthetic day collapsed
from 2,800 admissible quotes to 140 — 95% silently destroyed — leaving 1 of 20
routes live. Implemented with `route` included, because the "same cell" qualifier
requires it.

**Non-blocking**, but the tuple should gain `route` at the next version bump.

---

## AMB-4 — a zero-baggage flexible fare satisfies both `HAND_ONLY` and `FLEX`

Spec B.4's LOCKED mapping:

| `fare_class` | Condition |
|---|---|
| `HAND_ONLY` | `checked_baggage_kg == 0` |
| `STANDARD` | `checked_baggage_kg > 0` **and** not `FLEX` |
| `FLEX` | `change_permitted == FREE` **and** `cancellation_permitted ∈ {FREE, FEE}` |

A fare with no checked baggage and free changes satisfies both `HAND_ONLY` and
`FLEX` literally. The spec does not say which wins.

Implemented as **HAND_ONLY first**, because only STANDARD carries the "and not
FLEX" exclusion — HAND_ONLY is unqualified. That yields a total partition using
every condition as written.

This matters: a flexible hand-baggage-only fare is a real product, and the wrong
ruling pools it with a checked-baggage fare in the same cell — the comparison
B.4 exists to prevent. **Non-blocking, but confirm the ruling.**

---

## AMB-5 — the MAD degenerate guard is an exact float comparison

Spec D.7 locks *"when MAD = 0, no flagging occurs"*. Implemented as `mad == 0.0`,
exactly as written.

A cell whose log relatives are *near*-identical but not bit-identical yields a
MAD of, say, `1e-17`. The rule then fires with a threshold of `5e-17`, and every
observation outside that window is flagged — the same pathology the degenerate
guard exists to prevent, one ulp away from being caught.

**Not changed**, because widening an exact-zero test to a tolerance changes a
LOCKED rule and would need a version bump. Raised so the methodology owner can
decide whether "MAD = 0" means exactly zero or negligibly small.

**Non-blocking.**

---

## AMB-7 — **RESOLVED (implementation gap)**. The specification fixes a daily estimand over seven weekly chains, but nothing made a non-linking cell available to the daily aggregation, and `calculate_apix_l` asserted the opposite

### Classification

| Layer | Verdict |
|---|---|
| **Estimand** | **Not ambiguous.** §C.1, §C.2, §C.3, §F.2 and §F.5 fix it: the daily series aggregates seven interleaved weekday chains, each contributing its most recent level, subject to the §C.3 freshness ceiling |
| **Implementation representation** | **Undetermined by the specification, and correctly so.** Whether the most recent level is materialised per calendar day or read as-of at aggregation is an engineering choice. Both produce identical published numbers |
| **Methodology decision required** | **One only** — M1 below, and it is a *recorded interpretation of existing LOCKED text*, not a new rule |
| **Engineering decision required** | Where the latest-state store lives; whether the ceiling sits in `publish` or in its caller; how `advance_cell` is kept off non-link days |

### Original observation

Reproduced on post-merge `main` over 14 consecutive dates, two ways:

- **Advance every cell on every calendar day.** The chain never reaches
  `I(c,t) = I(c,t-7)·J(c,t)`; each cell resets to `100.0000` weekly, destroying
  the level §E.5 requires resumption to restore. Index withheld 14/14.
- **Advance each cell only on its own weekday.** Chains accumulate correctly
  (`100.0000 -> 101.2635`), and `calculate_apix_l` rejected **13 of 14** dates.

### Repository evidence

- `apix_l.py` raised whenever any `CellState.collection_date` differed from the
  requested date, citing §C.2. That function performs §F.1/F.2/F.3 — weighted
  arithmetic means of **levels** — and differences nothing. The differencing
  §C.2 forbids happens in `build_matched_set`, which has its own single-date
  guard. **The assertion was at the wrong semantic layer.**
- `advance_cell` was already correct and already link-scoped: *"Advance one cell
  by one **weekly link**"*, with `ChainInputs.previous` documented as *"the
  cell's state at `t - 7` — its own weekly chain, **not the previous calendar
  day**"*.
- **Nothing existed between them.** No component assembled the live set at a
  publication date from states produced on different link dates.
- `CellState` already carried `level`, `collection_date`, `last_matched_date`
  and `freshness_days`. **No new field was required.**
- §C.3's 13-day ceiling was never enforced at the publication layer: `is_live`
  tests only `level is not None` and the status.

### LOCKED specification references

| Section | Bearing |
|---|---|
| **§C.1** | *"a weekly-matched index published on a **rolling daily basis**"* — verbatim dossier p.16 |
| **§C.2** | *"an aggregate over seven interleaved weekday chains, **each contributing its most recent level**"* — verbatim dossier p.18 |
| **§C.3** | freshness at **publication date**, `t − max{s ≤ t : J computed}`, range `[0,6]`, published as a distribution; above 13 days suppresses |
| **§F.2** | sums over `c ∈ r ∩ L_t`, the live set |
| **§F.5** | *"Levels `I(c,t)` vary **daily** (each on its own weekly chain)"* |
| **§R.1** | *"Provisional publication \| Same day"* — verbatim dossier p.27 |
| **§A.3** | APW `{1,3,7,15,30,45,60}` reduces mod 7 to `{1,3,0,1,2,3,4}` — **five** distinct offsets, so at most five of seven chains can hold an observation on any date and **at least two must contribute an earlier link's level.** §C.2 is arithmetically unsatisfiable otherwise |
| **§J.2** | names *"held out"*, a condition §I.1 does not enumerate — §I.1's four bullets were never exhaustive |

### Decision

**M1 — a weekly-link cell that does not link on date `t` has no state event on `t`.**

> Each cell advances on its own seven-day chain (§C.2). A publication date on
> which a cell does not link is **not a period for that cell**: no matched set is
> formed, no relative is computed, no carry occurs, and no §I threshold is
> evaluated. The cell does not enter a new state, and no `CellStatus` describes
> such a day, because nothing happened to the cell.
>
> Its most recent valid level remains available to the daily aggregation of §F.2,
> subject to the §C.3 freshness ceiling: a cell whose freshness exceeds 13 days
> (two missed weekly links) is suppressed and leaves `L_t`. Within the ceiling
> the level is **repeated unchanged — never multiplied by any relative.**
> `J(c,t)` is a *seven-day* relative; multiplying it on each of seven days
> compounds it sevenfold, turning a 1% weekly move into 7.2135%. That is a
> defect, and it is asserted as a forbidden value in
> `tests/test_pipeline_14_day.py`.
>
> **CLARIFIED — wording only. No implementation conforming to §C.2 and §F.2
> produces a different number.**

**M2 — `max_cell_imputation` counts weekly link periods, not calendar publication dates.**

> The trailing window in §I is **8 weekly links**, not 56 publication dates. The
> numerator is the count of those links resolved by §E.4 carry — inheriting the
> parent stratum's relative — which is what §T defines as imputation. A
> publication date on which the cell does not link is counted in neither
> numerator nor denominator (M1), and a repeated level is **not** an imputation:
> no relative is inherited and no §E.4 operation occurs.
>
> **Why this reading and only this one.** A cell links once per seven days
> (§E.2), so at most 8 links fall in 8 weeks. Counting publication dates gives a
> maximum ratio of `8/56 = 14.29%`, permanently below the 40% ceiling — the
> threshold would be **unreachable**, and §Q **INV-8** (*"Every threshold in §I
> and §M.4 has a test that crosses it in both directions"*) unsatisfiable. The
> glossary's definition of *Relative* as *"a ratio between two periods"*, applied
> to `J(c,t)`, likewise makes a cell's adjacent periods `t` and `t−7`.
>
> **Consequential correction, recorded not applied.** §E.2's *"Note the lag is 7
> days, not one period"* uses *period* to mean a calendar day and is inconsistent
> with §I's usage. **The word *period* has no §T glossary entry** and carries at
> least three referents across the document. §E.2's aside should read *"not one
> calendar day"*, and *period* should be added to §T as **the interval between a
> cell's consecutive weekly links** — at the next version bump, since neither
> changes a number.
>
> **CLARIFIED for §I.**

### Why as-of is an implementation representation, not a third methodology

It computes the sum of `v[c|r] · I(c, s)` where `s = max{link dates ≤ t}` per
cell — which is what §C.2 already specifies. The alternative representation
(materialising a level per cell per calendar day) computes the same sum from a
different store. **Identical published numbers by construction**, and neither is
named by any LOCKED text, because the specification describes the estimand and is
silent on state representation.

Implemented in `src/apix/statistics/index/publication.py`:

```
latest state per CellKey  ->  as-of at t  ->  freshness ceiling  ->  L_t
      §C.2                      §C.2             §C.3               §F.2
```

**No fifth `CellStatus`.** A cell that did not link has had no event, so there is
no outcome to record.

### Implementation implication

The as-of selection **filters** later states rather than rejecting them: §P.3
requires a publication to be *"re-run from its recorded version vector and
compared bit for bit"* and §R.3 keeps prior vintages retrievable, both of which
mean replaying an earlier date against a store that has since grown. The
low-level guard in `calculate_apix_l` still rejects a future-dated state (§R.3).

### Dependencies

- **AMB-8** — blocking and upstream. A cell *due* to link today with no
  observations must still reach `advance_cell`, or §E.4 carry and §I suppression
  never fire and it silently rolls forward instead — a different rule with a
  different number. Knowing which cells are due means knowing the basket.
- **AMB-9** — blocking and upstream. No weight vector can be constructed.

### Open sub-questions

1. Does the freshness ceiling belong in `publish` or in the caller that assembles
   the live set? **Engineering.**
2. Should the per-weekday-chain weight share be published? One dark chain is
   `1/7 = 14.29%`, below `max_suppressed_weight = 15%` by 0.71pp, and clears
   `min_route_coverage` at `6/7 = 85.71%`. **Observability, non-blocking.**
3. §C.3's freshness distribution is now published (`QualityMetrics.freshness`).
   Whether a p90 beyond 6 days should become a *rule* rather than a caveat is a
   methodology question. **No threshold invented; it is a caveat only.**

---

## AMB-8 — **OPEN. BLOCKING.** `min_route_coverage = 60% of expected cells`, and nothing defines an expected cell

Spec §I gates every route on every date at *"**60%** of expected cells"*. The
term is used once and defined nowhere.

**What the repository does determine** — three constraints any definition must
satisfy:

1. It must **exclude** cells classed *No flight* — §H.1: *"No service scheduled
   on that weekday/slot. Cell not expected; **excluded from denominators of
   coverage**."* This is the only LOCKED sentence touching the denominator, and
   it states an *exclusion*, presupposing a base set it does not define.
2. It must be **independent of whether the cell links on `t`** (AMB-7 / M1).
3. It must be **fixed within a `basket_version`** (§F.5's discipline that only
   levels move within a year; §O.1's reproducibility role).

**Why the basket cannot supply it.** §O.1 calls `basket_version` the *"Route/cell
universe in force"*, but [AMB-1-resolution.md](AMB-1-resolution.md) §16 rules
that a new fare class, channel or carrier is **"Basket event? No"** — only a new
route is. A `basket_version` cannot be an exhaustive, current cell enumeration
and simultaneously not change when cells enter.

**Do not confuse it with §B.3's `MatchCoverage`**, whose denominator is *expected
recurring **items*** and which selects the tier under OQ-2. Different metric,
different unit, different purpose.

### How plausible definitions change published results

| Definition | One weekday chain dark | Effect |
|---|---|---|
| **Observed count** (`max(expected, len(states))`) | denominator shrinks with the numerator — **coverage does not fall** | Routes essentially never suppress on coverage; **silent, undetectable loss** |
| **Scheduled cross-product** | `6/7 = 85.71%` passes; three dark chains give `57.14%` and the route is suppressed | §F.4 renormalises; **the national level shifts** |
| **Linked in the trailing 8 weeks** | self-adapting; an exited cell leaves the denominator after 8 weeks | Fewer permanent false suppressions; **different suppression timing, different level** |
| **Expected to link at `t`** | `7/7 = 100%` always | Coherent only under M1 = NO, which contradicts §C.2, §C.3 and §F.5 |

### Interim control — no default, and no silent one

`calculate_apix_l` keeps its observed-count fallback for unit fixtures, but any
live route with no declared denominator now produces a **caveat on the published
output** naming AMB-8 and saying the figure is optimistic rather than measured.
`publication.publish`, the production entry point, takes
`expected_cells_by_route` as a **required argument with no default**.

**No definition has been chosen.** §S: *"None of these may be resolved by
choosing a plausible value."*

---

## AMB-9 — **OPEN. BLOCKING.** The cell key carries `carrier`; `v[c|r]` has no carrier term, and nothing says the allocation is uniform

§G.3: `v[c|r] = alpha_apw × beta_fare_class|r × delta_channel|r / normaliser`.
§G.1's diagram agrees: *"within-route — **APW × fare class × channel**
composition"*. The cell key has six dimensions; the formula has three.

**One of the two omissions is settled and the other is not.**

`day_of_week` — **RESOLVED.** v2.1 §C.2 states it outright: *"Because it is
determined, it is **not** an independent weight dimension — §G.3 correctly omits
it, UNCHANGED."* At fixed `(t, apw)` the weekday is mechanically determined, adds
no observations and partitions nothing within a collection date. It carries no
weight factor, so with §G.5's sum-to-one the seven weekday variants of one
`(apw, fare_class, channel)` group divide that group's weight equally. **A
derivation, not a choice**, and implemented as one.

`carrier` — **OPEN.** The omission is *unexplained*, unlike the weekday's, and
the dimension is not determined: §M.2 conditions APIx-TPD on carrier precisely
because it is price-determining, and AMB-1 §21 calls it so. Uniform allocation
would weight a carrier holding roughly 60% of a route's passengers identically to
one holding 3% — a substantive choice with an unmeasured bias that no frozen text
authorises.

**Inherited, not introduced.** v2.0's §B.2 cell key already carried `carrier`,
`day_of_week` **and** `flight_number` against the same three-term formula — three
unweighted dimensions. v2.1 moved `flight_number` into the ITEM key and justified
`day_of_week`, leaving one. **v2.1 strictly reduced this gap.**

**Not registered anywhere until now.** §S's OQ-4 covers route weights and OQ-7
covers the APW curve. **There is no open question for carrier shares**, and
AMB-1 §5 rejected Candidate D partly because it *"requires carrier-share weights
of unproven availability"* — the unavailability was known and never written down
as an open item.

### Interim control

`within_route_weights` implements §G.3 exactly and **raises `WeightError`** on a
route carrying more than one carrier with no declared `carrier_shares`. There is
no default and no fallback. Two ways to satisfy it, both explicit: declare
measured shares recorded in `weight_version`, or declare uniform shares *as a
stated v1 choice with a published sensitivity band* — the pattern §G.4 already
uses for `alpha` under OQ-7. **That is the owner's ruling to write down.**

---

## AMB-10 — `source_precedence` is on every published output but outside §P.1's reproducibility tuple

v2.1 §O adds `source_precedence` to the version vector — the ordered list §D.8
prices every matched pair from. §P is **UNCHANGED** in v2.1 and §P.1 names five
fields, which do not include it.

Two runs whose precedence lists differ can therefore select different quotes,
produce different numbers, and claim the same reproducibility tuple. §D.8.2
requires the rule to be **Reversible** — *"changing the list is a version-vector
change, visible in every vintage"* — which the field now satisfies; §P.1's
guarantee is what does not follow.

**Not changed**, because widening §P.1 is a change to a LOCKED item and needs a
ruling, not an implementation decision. The field is carried and recorded; only
the guarantee's wording lags.

**Non-blocking** while `source_precedence` is constant, which it is for a single
declared list. It becomes blocking the first time the list is revised.

---

## Summary

| ID | Ambiguity | Blocking | Implemented reading |
|---|---|---|---|
| **AMB-1** | Cell vs item; `min_matched_items = 3` unsatisfiable | **Resolved** | ITEM key separated from CELL key (ADR-0062, methodology v2.1) |
| AMB-2 | `\|M(c,t)\|` denotes two sets | No | Pipeline order (D.1 -> D.7 -> D.2) |
| AMB-3 | Duplicate tuple omits `route` | No | `route` included |
| AMB-4 | Zero-baggage flexible fare | No | `HAND_ONLY` first |
| AMB-5 | MAD exact-zero guard | No | Exact `== 0.0`, as written |
| **AMB-7** | Non-linking cell absent from the daily live set | **Resolved** | As-of publication layer; M1/M2 CLARIFIED (ADR-0063) |
| **AMB-8** | `expected_cells` undefined | **YES** | **None** — required argument, caveat on every output that lacks it |
| **AMB-9** | `v[c\|r]` has no carrier term | **YES** | **None** — `WeightError` until declared |
| AMB-10 | `source_precedence` outside §P.1's tuple | No | Field carried; §P.1 unchanged |

*(AMB-6 was raised and resolved inside [AMB-1-resolution.md](AMB-1-resolution.md)
§11.11 — the parent LEVEL — and has no entry here.)*

**No ambiguity was resolved by choosing a plausible value.** AMB-2 to AMB-5 were
resolved from the specification's own structure and are documented at each call
site. AMB-1 could not be, and was not — it went to ADR-0062. AMB-7 was resolved
from LOCKED text and arithmetic, not from preference. **AMB-8 and AMB-9 cannot be
resolved that way either, so they are not.** Both are blocked at the code
boundary rather than defaulted: one raises, the other caveats every output that
lacks it.
