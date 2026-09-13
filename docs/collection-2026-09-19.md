# The 2026-09-19 unlock — executable procedure for the second wave

> **Status:** procedure, not a prediction.
> **Governs:** the collection wave that makes the first real Jevons relative
> arithmetically possible.
> **Companion to:** [`manual-collection-procedure.md`](../compliance/manual-collection-procedure.md)
> — that document is the general how-to; this one is what the *second* wave
> specifically must do, and why each requirement exists.

**This document does not promise the result will be positive.** It specifies
what must be true for a result to exist at all. A wave that departs from any
line below yields observations, but not a matched pair — and APIx would then
correctly continue to publish nothing.

---

## 0. Why 19 September and not any other day

Methodology §C.1 is **LOCKED**:

```
I(c,t) = I(c,t−7) · J(c,t)
```

Every index value needs a matched pair at *t* and *t−7*. One wave exists
(2026-09-12), so there are **zero** matched pairs today. 2026-09-19 is the first
date whose *t−7* counterpart is a wave APIx actually holds.

Seven days is not an arbitrary gap. The cell key (§B.2.1) contains the **travel
date's day of week**, and a 7-day shift preserves it exactly:

| APW | *t−7* travel date | | *t* travel date | | weekday preserved |
|---|---|---|---|---|:---:|
| T+1 | 2026-09-13 | Sun | 2026-09-20 | Sun | ✅ |
| T+3 | 2026-09-15 | Tue | 2026-09-22 | Tue | ✅ |
| T+7 | 2026-09-19 | Sat | 2026-09-26 | Sat | ✅ |
| T+15 | 2026-09-27 | Sun | 2026-10-04 | Sun | ✅ |
| T+30 | 2026-10-12 | Mon | 2026-10-19 | Mon | ✅ |
| T+45 | 2026-10-27 | Tue | 2026-11-03 | Tue | ✅ |
| T+60 | 2026-11-11 | Wed | 2026-11-18 | Wed | ✅ |

A wave on any other day breaks the weekday component of every cell key and
matches nothing.

---

## 1. Identical collection frame — every line is a match condition

Anything in this table that changes produces a **different cell**, and a
different cell has no *t−7* counterpart.

| Parameter | Required value | Why a change breaks the pair |
|---|---|---|
| Route | **DEL → BOM**, one-way, exact airports | `route` is the first element of the cell key |
| Carrier | **IndiGo (6E)**, marketed *and* operated | `carrier` is in the cell key |
| Channel | `AIRLINE_DIRECT` | in the cell key |
| Source | `indigo-direct` (goindigo.in) | §D.8.1 pairs an item only where a source is present in **both** periods |
| Passengers | 1 adult, Economy, Regular fare | changes the price concept |
| Stops | Non-stop only (`stops = 0`) | frame |
| Fare definition | The cheapest fare **including checked baggage**; `fare_family_raw` recorded verbatim and never used for matching | §B.4 derives `fare_class` from **entitlements**; a Lite fare lands in a different cell |
| Departure bands | **2, 3, 4, 5, 6** (3-hour bands anchored 00:00 IST) | band is the Tier-2 item identity |
| Selection rule | **Earliest eligible departure within each band.** Sort by departure time before selecting; never by price | selecting by price makes the index measure its own selection rule |
| Window | **21:00–22:00 IST** | §A.5 — an out-of-window quote is stored and excluded from the index |
| Acquisition | Manual, by a person, in an ordinary browser. **No script, no agent, no headless browser.** A CAPTCHA or block page is a **stop signal**, not an obstacle | `AUTOMATION_PROHIBITED / MANUAL_PERMITTED` in the source registry |

### 1.1 Advance-purchase buckets — collect all seven

Collect **T+1, T+3, T+7, T+15, T+30, T+45, T+60** from 2026-09-19, by clicking
each travel date in the calendar. Never accept a defaulted date.

> **Open discrepancy, carried deliberately.** The Day-1 runs recorded
> `frame_id = DEL-BOM/6E/AIRLINE_DIRECT/T7-T15-T21-T30@primary`, but the panel
> holds T+1/3/7/15/30/45/60 and **no T+21**. The `frame_id` therefore does not
> describe the wave it labels. Day-1 `runs` are a protected record and **were not
> edited**; the historical provenance stands as collected, and the discrepancy is
> disclosed rather than rewritten. What follows binds the *next* wave only.

### 1.2 PREFLIGHT GATE — run this before opening the browser

> ## 🛑 STOP
>
> **The declared APW vector must equal exactly `{1, 3, 7, 15, 30, 45, 60}`.**
>
> Not a superset. Not a subset. Not "close enough". **If it differs by a single
> bucket, collection does not start** — fix the declared frame first.

This is a hard gate and not a reminder, because a mismatch is silent: collection
succeeds, the wave loads, the panel builds, and only the *matched set* comes out
short — by which point a day of real market data has been spent on cells that can
never pair. Day 1 is the proof that this happens.

Run this before collection. It reads the frozen vector from `APWBucket`, so the
two cannot drift apart, and it **exits non-zero** on any mismatch:

```bash
DECLARED="1,3,7,15,30,45,60" python -c "
import os, sys
sys.path.insert(0, 'src')
from apix.schemas.enums import APWBucket
frozen = tuple(b.value for b in APWBucket)
declared = tuple(int(x) for x in os.environ['DECLARED'].split(','))
if declared != frozen:
    sys.exit(f'PREFLIGHT FAIL: declared {declared} != frozen {frozen}. DO NOT COLLECT.')
print(f'PREFLIGHT OK: declared frame == frozen APW vector {frozen}')
"
```

Set `DECLARED` from the `frame_id` you are about to record on the run — not from
this document, or the check is circular and proves nothing.

**A non-zero exit is a stop, not a warning.** There is no override, and no
variant of the procedure that proceeds past a failed preflight. The correct
response is to correct the declared frame and run it again.

Only buckets present in **both** waves can form a matched pair, so collecting
fewer than seven silently discards cells — and declaring a bucket that is not
collected produces a `frame_id` that misdescribes its own wave, which is the
exact defect Day 1 carries.

---

## 2. Evidence capture — exactly what must be recorded

| Item | Requirement |
|---|---|
| Screenshot | **One per search, including failures.** Named `{YYYYMMDD}-{window}-{travel_date}.png`, never edited, retained 5 years |
| SHA-256 | Every screenshot content-addressed and bound to its run. The T+45 batch on Day 1 arrived as chat images with **no hashable bytes** — that must not recur |
| `observation_ts` | The **actual** capture time per quote, to the minute. Not the window's nominal start |
| Collection timestamp | Recorded per run: declared window *and* actual first/last capture, as Day 1 did (`declared 21:00–22:00; actual 20:54–22:10`) |
| Fare decomposition | `base_fare`, `taxes`, `fees`, `user_development_fee` **only where displayed**. Blank stays blank; a blank is never turned into a zero |
| `payable_fare` | All-inclusive, 1 adult, required for every `AVAILABLE` flight |
| Failure rows | Every search produces a row, including the seven `CollectionOutcome` failure values |
| Version vector | `methodology_version 2.1`, `basket_version`, `parser_version`, `collector_version`, `protocol_version`, `source_precedence_version`, `frame_id` — recorded per run (§O) |

### 2.1 New on this wave: the admissible-flight universe per band

For each of the 4 × 7 searches, record **how many non-stop 6E flights were
eligible in each band** before the earliest-departure rule selected one.

Day 1 did not capture this, and its absence is why APIx reports observed
dispersion and **no confidence interval** — there is no sampling-design
information to build one from. Recording it does not create an interval; it
creates the precondition for one.

| Field | Example |
|---|---|
| `band` | 4 |
| `eligible_flights` | 3 |
| `selected_flight_number` | 6E 6676 |

### 2.2 Observation ids

Ids follow the Day-1 shape so the two waves are trivially comparable:

```
{collection_date}-{run}-{source}-{carrier}{flight}-{travel_date}-{fare_family}
20260919-primary-indigo-direct-6E6218-20260926-Saver fare
```

---

## 3. What becomes computable, in order

Each step below runs only if the one above it produced something. Nothing here
is new code — every function named is implemented and fixture-tested today.

### 3.1 Matched set — `build_matched_set` (§D.1, §D.8)

Items present in **both** periods. The item definition depends on the tier:

| Tier | Item identity | Selected when identity stability is |
|---|---|---|
| Tier 1 | `(carrier, flight_number)` | ≥ 0.70 |
| Tier 2 | `(carrier, departure_hour_band)` | 0.40 – 0.70 |
| Tier 3 | none — declared unit value, no matched set | < 0.40 |

> **Concrete risk on this panel.** Across the seven Day-1 dates, bands 2, 3 and
> 5 each held a single flight number, while band 4 held `6E 324` *and*
> `6E 6676`, and band 6 held `6E 329` *and* `6E 354`. If the 19 Sep schedule
> moves a flight, **Tier 1 loses that item and Tier 2 keeps it.** This is
> exactly what the tier ladder exists for. Do not force Tier 1.

### 3.2 First real Jevons relative — `compute_jevons` (§D.2)

The geometric mean of matched price relatives, computed **in logs**. It is
defined only over items in the matched set, so its denominator is whatever 3.1
produced — not the 35, and not the wave's row count.

**A relative of exactly 1.0 is a measured no-change, not a missing
measurement.** The two must not be conflated in any write-up.

### 3.3 First real index calculation — `advance_cell` → `calculate_apix_l`

`I(c, 2026-09-19) = I(c, 2026-09-12) · J(c, 2026-09-19)`, with the base period
at 100. The index moves **once per weekly link** and is carried between links; a
7-day relative applied daily would compound sevenfold, and the suite asserts
that compounded value as forbidden.

### 3.4 What still will not be publishable on 19 September

Reaching a first index value clears **none** of these:

| Blocker | Why 19 Sep does not clear it |
|---|---|
| **AMB-8** — §I gates routes at "60% of expected cells" | Nothing defines an expected cell. A second wave does not define one |
| **AMB-9** — no carrier term in `v[c\|r]` | Still one carrier. Degenerate, not resolved |
| **OQ-1** — the collection window's published value | Still open. The diagnostic 09:00–10:00 run is evidence toward it, not a ruling |
| **APIx-TPD (§M)** | Empty package. 35 + ~35 quotes against a 1,500 threshold |
| **National representativeness** | One route, one carrier |

**So: a first index value is a first index value.** It is not a published index,
and the publication guards will continue to refuse one.

### 3.5 How uncertainty work becomes possible later

Not on this wave. The order of operations is:

1. **19 Sep** — record the admissible-flight universe per band (§2.1). This is
   the missing sampling-design input, and it costs one number per search.
2. **Accumulate links.** A bootstrap over weekly relatives needs a run of
   links, not two waves.
3. **Then**, and only then, implement `src/apix/statistics/uncertainty/`
   against §M's specified design.

Until step 3 lands, APIx reports **observed dispersion**, which assumes nothing,
and reports no confidence interval anywhere.

---

## 4. Post-collection checklist

```bash
python tools/collection/load_manual.py     # screenshots + rows -> SQLite store
python tools/analysis/build_panel_json.py  # store  -> data/panel.json
python tools/analysis/build_dashboard.py   # contract -> data/dashboard.html
python tools/analysis/panel_report.py      # store  -> data/panel_report.txt
python tools/analysis/replay_exclusions.py # audit the new wave's exclusions
python tools/analysis/execution_boundary.py
```

Then confirm, before writing a single sentence about the result:

- [ ] `index_status.matched_pairs_available` is **≥ 1** — it is derived, never asserted
- [ ] `execution_boundary` shows `matched_set` and `jevons` moved off **PENDING**
- [ ] the exclusion replay still reports **0 disagreements**, on both waves
- [ ] `pytest`, `ruff check`, `ruff format --check`, `mypy src/apix` all clean
- [ ] `git diff --exit-code data/` after regeneration
- [ ] no `frame_id` / collected-bucket mismatch on the new run (§1.1)
- [ ] every claim that changed has a row in
      [`claim-evidence-matrix.md`](claim-evidence-matrix.md)

If the wave fails — a block page, a schedule change, an unreadable fare — that
is a recorded outcome, not a reason to reconstruct a quote. The index stays
`PENDING` and the reason is published.
