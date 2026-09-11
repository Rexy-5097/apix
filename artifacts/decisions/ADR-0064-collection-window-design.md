# ADR-0064: Collection window design for the 30-day study

> **Status:** Proposed — **awaiting owner ratification** | **Date:** 2026-09-11
> **Decider:** @Rexy-5097 (methodology) | **Proposer:** @slazyverse (ingestion)
> **Checkpoint:** 2H | **Bears on:** OQ-1, §A.5, §R.1

---

## What this ADR does and does not decide

**Does NOT decide:** the published collection window. That is **OQ-1**, listed in
§S as *"Exact collection window start/end (IST)"*, and §S is unambiguous:
*"None of these may be resolved by choosing a plausible value."* Resolving it
requires evidence that does not yet exist.

**Does decide:** what to **sample** during the 30-day study so that OQ-1 becomes
answerable at the end of it. A sampling design is an engineering decision; the
window value it eventually informs is not.

The distinction matters because the two are easy to conflate, and conflating
them would let a convenient collection time harden into a methodology parameter
without anyone ruling on it.

## Context

§A.5 is **LOCKED as a rule, EMPIRICAL as a value**:

> *"All collection runs inside a **fixed daily window**… Fares move intraday. A
> quote at 03:00 and one at 18:00 are two different prices, not two draws from
> the same price."*
>
> *"**EMPIRICAL / OPEN — OQ-1.** The window's start and end times are a published
> methodology parameter and are **not yet fixed**."*

MoSPI's own CPI compiles airfare *"from well-known websites **across different
time windows** to ensure representativeness"* (Expert Group Report, "Air fare
charges") — so the national statistical office treats intraday variation as
real enough to sample around.

**The 30-day study is the only opportunity to gather this evidence.** §A.3
assigns APW by **exact** lead time, so a time-of-day not sampled during the
window can never be recovered: the flights, the dates and the prices are gone.

---

## Options

### Option A — one fixed daily window

| | |
|---|---|
| **OQ-1 evidence** | **None.** Intraday variation cannot be measured from one time of day. Choosing A assumes the window does not matter, which is precisely the question |
| **Effort** | 3 searches/day × 30 days = **90 sessions** |
| **Reproducibility** | Sound. One declared window, uniformly applied |
| **30-day impact** | None — this is the baseline |

### Option B — two fixed daily windows, every day

| | |
|---|---|
| **OQ-1 evidence** | **Direct and complete.** Paired observations of the same flight on the same day at two times, for all 30 days |
| **Effort** | 6 searches/day × 30 days = **180 sessions — double** |
| **Reproducibility** | Sound, provided both windows are declared and the index consumes only one |
| **30-day impact** | Doubles a manual burden for a month. **The realistic failure mode is attrition**, and a missed day costs two weekly links |

### Option B-minimal — primary window daily, second window on 7 days

| | |
|---|---|
| **OQ-1 evidence** | **Sufficient.** ~7 paired days × ~15 flights ≈ **100+ paired observations**, one on each weekday, so the weekly cycle is covered |
| **Effort** | 90 + **21 extra searches** ≈ 2.5 extra hours across the month |
| **Reproducibility** | Sound. Each window is its own run with its own declared bounds |
| **30-day impact** | **~23% more effort, not 100%** |

---

## Decision — **Option B-minimal**

**Primary window: 21:00–22:00 IST, every day.** The only window whose
observations enter the index.

**Diagnostic window: 09:00–10:00 IST, on 7 days** — one per weekday, on
collection days 1, 4, 7, 10, 13, 16 and 19 of the study (a +3 stride, which
walks the full weekday cycle).

### Why not Option A

It cannot answer OQ-1, and **OQ-1 is unrecoverable after the fact**. Spending 30
days collecting and still not knowing whether the window matters would waste the
one chance to find out. §A.5 already asserts that a 03:00 quote and an 18:00
quote are different prices; Option A gathers no evidence either way and leaves
the assertion unmeasured.

### Why not full Option B

Doubling a manual burden for 30 days risks the study itself. **A missed day costs
two weekly links**, not one — the index compares `t` against `t−7`, so skipping
day 19 breaks the link for day 12 and day 26 alike. A design that is likely to
be abandoned in week three is worse than a smaller one that completes.

The marginal evidence from days 8–30 of paired sampling is also low: intraday
variation is a property of the pricing engine and the weekday, and seven paired
days cover every weekday once. If the first seven show material movement, the
owner can extend; if they show none, 23 more days of pairs prove the same null
more expensively.

### Why 21:00 primary

A slot a person can reliably hold for 30 consecutive days. Reliability is the
binding constraint on a manual study, and a window that is missed is worse than
one that is theoretically better. **This is not a claim that 21:00 is the right
published window** — that is what the diagnostic evidence is for.

### Why 09:00 diagnostic

~12 hours from the primary, which maximises the chance of detecting movement if
movement exists. A gap of two hours could show nothing and prove nothing.

---

## Consequences

**Good**

- OQ-1 becomes answerable from evidence rather than assertion.
- The index is unaffected: only primary-window runs feed it, so the diagnostic
  window cannot contaminate a published number.
- If intraday movement turns out to be immaterial, that is itself a publishable
  finding and simplifies the published calendar.

**Bad, and accepted**

- 21 extra searches of manual effort.
- Seven paired days is enough to detect **material** movement, not to
  characterise its full shape. A precise intraday curve would need Option B.
- The diagnostic window is at a **fixed** time, so it measures 09:00-vs-21:00
  and not intraday variation generally.

**Neutral**

- Two runs on paired days, distinguished by `frame_id` suffix. Each run is
  internally consistent against its own declared window, so `verify()` stays
  quiet rather than flagging the diagnostic run's quotes as out-of-window.

## Implementation

`source_registry/collection-windows.yaml` carries the declared windows and the
paired-day schedule. Each run records the window **actually used** in
`CollectionRun.collection_window_start/_end`, so the record is what happened
rather than what was planned.

`frame_id` carries the role:

```
DEL-BOM/6E/AIRLINE_DIRECT/T7-T15-T21-T30@primary        → feeds the index
DEL-BOM/6E/AIRLINE_DIRECT/T7-T15-T21-T30@diagnostic-oq1 → OQ-1 evidence only
```

**Only `@primary` runs are index input.** A consumer that blends the two would
be averaging 09:00 and 21:00 prices, which §A.5 says are different prices —
*"a between-source comparison measures the clock as much as the market"*.

## Rejected alternatives

**Randomised collection times.** Would sample the intraday distribution better
and destroys comparability: §A.5 requires a *fixed* window precisely so that
day-over-day movement is not confounded with time-of-day.

**Deciding the published window now from the first week's data.** Changing the
window mid-study ends the window (acquisition protocol §15). OQ-1 is resolved
**after** the 30 days, not during.

**Recording the diagnostic quotes in the primary run and flagging them.** §A.5
permits flag-and-exclude, but it puts two populations in one run and relies on
every downstream consumer honouring the flag. Separate runs make the separation
structural instead.

## References

- `docs/methodology/apix_formula_spec_v1.md` §A.5, §R.1, §S (OQ-1)
- `compliance/acquisition-protocol.md` §2, §15
- MoSPI CPI Expert Group Report, "Air fare charges"
