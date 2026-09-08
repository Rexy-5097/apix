# Methodology ambiguities found while implementing Checkpoint 2

> **Raised, not resolved.** The Checkpoint 2 brief is explicit: *"If any
> methodology ambiguity is discovered: STOP and report it"* and *"If any
> required statistical behavior cannot be implemented from the frozen
> specification: STOP and report it."*
>
> **Owner to rule on these:** @Rexy-5097 (methodology owner).
> **Status:** AMB-1 is **BLOCKING**. AMB-2 to AMB-5 are non-blocking.

The frozen specification exists because *"two developers reading the same
statistical prose will implement two different indices."* Implementing it is the
first real test of whether the symbol table actually removed the interpretation.
It mostly did. These are the places it did not.

---

## AMB-1 — **BLOCKING**. The specification does not distinguish the *cell* from the *item*, and under the literal reading `min_matched_items_per_cell = 3` is unsatisfiable

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

## Summary

| ID | Ambiguity | Blocking | Implemented reading |
|---|---|---|---|
| **AMB-1** | Cell vs item; `min_matched_items = 3` unsatisfiable | **YES** | **None — awaiting the ruling** |
| AMB-2 | `\|M(c,t)\|` denotes two sets | No | Pipeline order (D.1 -> D.7 -> D.2) |
| AMB-3 | Duplicate tuple omits `route` | No | `route` included |
| AMB-4 | Zero-baggage flexible fare | No | `HAND_ONLY` first |
| AMB-5 | MAD exact-zero guard | No | Exact `== 0.0`, as written |

**No ambiguity was resolved by choosing a plausible value.** AMB-2 to AMB-5 were
resolved from the specification's own structure and are documented at each call
site. AMB-1 cannot be resolved that way, so it is not.
