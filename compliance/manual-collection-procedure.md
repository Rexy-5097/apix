# Manual collection procedure — the step-by-step for a human collector

> **Owner:** [@slazyverse](https://github.com/slazyverse) · **Checkpoint:** 2H
> **Governs:** every fare observation that enters APIx
> **Companion to:** [`acquisition-protocol.md`](acquisition-protocol.md) — that
> document says *what the rules are and why*; this one says *what to do*.
> **Protocol version recorded on each run:** `acquisition-protocol-2G`

---

## 0. Read this first

**A person performs this procedure in an ordinary browser. No script, no
extension, no automation, no headless browser, no agent.**

That is not a stylistic preference. The Checkpoint 2G automation gate found
**zero** sources rated `AUTOMATION_ALLOWED` across the 14-source register. IndiGo
is `AUTOMATION_PROHIBITED / MANUAL_PERMITTED` — its terms carve out *"standard
search engine or internet browser usage"*, which describes a human, and prohibit
automated access to the platform. Manual collection is the **only** permitted
mode today. See [`../source_registry/registry.yaml`](../source_registry/registry.yaml).

**Four rules that override anything else in this document:**

1. **Do not infer a missing fare component.** Blank stays blank.
2. **Do not turn a missing component into zero.** A zero is a claim; a blank is
   the absence of one.
3. **Do not bypass a CAPTCHA, a queue, a block page or any other access control.**
4. **If an access challenge appears, record `CAPTCHA_OR_ANTIBOT_STOP` and stop
   for that source, that day.** Not retry. Not a different browser. Stop.

Rule 4 has no exception and no escalation path that involves getting past the
challenge. A challenge is a stop signal, not an obstacle.

---

## 1. What you collect, each day

| | |
|---|---|
| Route | **DEL → BOM**, one-way |
| Carrier | **IndiGo (6E)** only |
| Source | `indigo-direct` — the airline's own website |
| Passengers | **1 adult**, Economy |
| Stops | **Non-stop only** |
| Travel dates | **four** searches: today **+7**, **+15**, **+21**, **+30** days |
| Flights per search | **5**, chosen by the rule in §5 |
| Window | **21:00–22:00 IST**, every day |

A full day is **4 searches** and up to **20 fare rows**. Budget 20–30 minutes.

**On study days 1, 4, 7, 10, 13, 16 and 19** you repeat the whole thing at
**09:00–10:00 IST**. That second run is a separate `CollectionRun` with
`--window diagnostic_oq1`, it feeds **no index**, and it exists to answer OQ-1
(does the time of day matter?). See
[`ADR-0064`](../artifacts/decisions/ADR-0064-collection-window-design.md).

### Working out the four travel dates

If today is **2026-09-12**:

| Bucket | Travel date |
|---|---|
| T+7 | 2026-09-19 |
| T+15 | 2026-09-27 |
| T+21 | 2026-10-03 |
| T+30 | 2026-10-12 |

Count calendar days, not business days. **Getting this wrong is not recoverable**
— §A.3 assigns the advance-purchase bucket by **exact** lead time, so a quote
taken at 8 days matches no bucket and is inadmissible. It is stored and
excluded; it is never rounded into T+7.

---

## 2. How to open the source

1. Open an ordinary browser window.
2. Type `www.goindigo.in` into the address bar and press Enter.
3. If a cookie or consent banner appears, **decline non-essential cookies**.
4. Do not sign in. Do not use a saved profile with a logged-in session. A fare
   shown to a logged-in loyalty member may not be the fare a household sees.

**Use the same browser, the same machine and the same city/currency settings
every day.** Fares are personalised. Changing the environment mid-study changes
what is being measured, and §15 of the acquisition protocol treats that as
ending the window.

Do not use a VPN. Do not switch between devices. If you must change machines
permanently, record it in `--notes` and tell @slazyverse.

---

## 3. How to enter origin, destination and dates

1. Select **One Way**.
2. **From:** type `DEL` and choose *Delhi (DEL) — Indira Gandhi International*.
3. **To:** type `BOM` and choose *Mumbai (BOM) — Chhatrapati Shivaji Maharaj Intl*.
4. **Departure date:** open the calendar and click the travel date you computed
   in §1. **Click the date; never accept a default.** The calendar opens on
   today, and a mis-click lands on a neighbouring day — which silently changes
   the APW bucket.
5. **Passengers:** 1 Adult, 0 Children, 0 Infants.
6. **Currency:** INR. **Fare type:** Regular. Not Student, Armed Forces, Senior
   Citizen or any other concession — those are different products.
7. Search.

> **The "advance-purchase date" is not something you select.** It is
> `travel_date − collection_date`, computed from the two dates you already
> recorded. There is no field for it. You get the bucket right by getting the
> travel date right.

**Screenshot the results page now**, before you touch any filter. §9 says what
to name it.

---

## 4. Which flights are eligible

A flight is eligible if **all** of these hold:

- Marketed and operated by **IndiGo (6E)**. A codeshare on another carrier's
  metal is not eligible.
- **Non-stop.** Zero stops. A one-stop DEL–BOM is a different product, not a
  slower version of the same one.
- **DEL → BOM**, the exact airports. Not a nearby airport.
- Departs on the **travel date you searched for**. A flight shown as arriving
  the next day is fine; one *departing* the next day is not.

Everything else is ineligible and is simply not recorded. Ineligibility is not a
failure and gets no `CollectionOutcome` — the attempt covers the whole search,
not one flight.

---

## 5. How the 5 flights are selected — the rule that protects the data

> ## **Take the first 5 eligible flights by DEPARTURE TIME, earliest first.**
> ## **Never by price. Never "the cheapest 5". Never whatever the page shows first.**

IndiGo's results default to **cheapest-first**. Taking "the first five" off that
list selects *cheap flights* — and next week it selects a different five, from a
list sorted by a price that has moved. The index would then measure the
selection rule rather than the market, and **no downstream test can detect or
undo that bias**, because the data would be internally consistent and wrong.

**Do this, every single time:**

1. Find the sort control on the results page.
2. Set it to **Departure — Earliest first**.
3. Take the **top 5 eligible** flights in that order.

If fewer than 5 eligible flights exist, take all of them and record how many.
That is a market fact, not a shortfall.

If the sort control is missing or broken, **do not eyeball it**: read every
eligible flight's departure time, sort them yourself, and take the earliest 5.
Note it in `--notes`.

---

## 6. Which fare family you record

IndiGo presents several fare families per flight. Record **exactly one row per
flight**: the **cheapest fare that includes checked baggage**.

Apply that rule identically on every flight, every day.

- Copy the family's displayed name into `fare_family_raw` **verbatim** —
  `SAVER`, `FLEXI PLUS`, whatever it says. It is stored for audit and is
  **never** used for matching.
- The canonical fare class is derived from the three entitlement columns, not
  from that label (§B.4). One carrier's *saver* is another's *lite*.

**Record the entitlements from the fare rules, not from the family name:**

| Column | What to record |
|---|---|
| `checked_baggage_kg` | The **checked** allowance in kg. Hand baggage does not count. A hand-baggage-only fare is `0` |
| `change_permitted` | `FREE` (no charge), `FEE` (charge), or `NONE` (not permitted) |
| `cancellation_permitted` | Same three values |

A `0 kg` fare is a **different fare class**, not a cheaper version of the same
one. Recording it as `0` classifies it correctly on its own; recording it as
though it included baggage contaminates `STANDARD`.

---

## 7. How to record the fare

Open the flight's fare breakdown — the fare summary panel, or the fare-rules
link. Record what is **displayed**:

| Column | What it is |
|---|---|
| `payable_fare` | **The total a passenger actually pays**, all-inclusive, for 1 adult. Required |
| `base_fare` | Base fare, if shown |
| `taxes` | Taxes, if shown |
| `fees` | Fees and surcharges, if shown |
| `user_development_fee` | UDF / ADF, if shown |

### The blank-versus-zero rule

> **If the site does not show a component, leave the cell EMPTY.**
> **Never type `0`. Never estimate it. Never compute it from the others.**

An empty cell says *"the source did not render this"*. A `0` says *"this charge
is genuinely zero"*. They are different claims, and the second one is a
fabrication when you meant the first.

**Do not subtract to fill a gap.** If the page shows a total and a base fare but
no tax line, `taxes` is **empty** — not `total − base`. §A.4 is explicit that
*"the index is never blocked on a breakdown the site does not render"*: the
total enters the index either way, so there is nothing to gain by inventing the
parts and everything to lose.

The loader enforces the first half of this (an empty cell becomes `None`, never
`0`) and cannot enforce the second. **The second is on you.**

### Money formatting

Digits and a decimal point. `5432.00`. Commas and `₹` are stripped, so `₹5,432`
also works. Do not round. Do not convert currency.

### If a flight has no purchasable fare

Set `availability` to `SOLD_OUT` and **leave `payable_fare` empty**. Fill in the
flight's identity columns as normal.

A sold-out flight is *not* a missing price — it is a **disappeared item**
(§D.6). It is stored in its own table, `unpriced_flight`, precisely because it
has no fare and must never be given one. Keeping it matters: "sold out" and
"this flight does not operate" are different facts, and the difference is what
the coverage denominator turns on.

The loader rejects `SOLD_OUT` with a price, and rejects `AVAILABLE` without one.

---

## 8. How failures are classified

**Every search gets a row in `attempts.csv`, whether or not it produced a fare.**

This is the part people skip, and it is the part that makes coverage measurable.
A table of successful quotes cannot tell you *why* something is missing — in a
table of successes, every kind of absence looks identical. You cannot measure
missingness from a table of successes.

Pick the outcome by **what actually happened**:

| What you saw | `outcome` |
|---|---|
| Flights found, fares recorded | `SUCCESS` |
| Search ran; **IndiGo does not fly DEL–BOM on that date at all** | `NO_FLIGHT` |
| Route or flight has been **permanently withdrawn** | `STRUCTURAL_MISSING` |
| Page loaded, flights listed, but **no purchasable fare** (all sold out) | `TECHNICAL_FAILURE` |
| Site down, timed out, error page, rate-limit message | `SOURCE_UNAVAILABLE` |
| Page loaded but you **could not read** the fare — layout broke, fields missing | `PARSER_FAILURE` |
| **CAPTCHA, bot check, block page, "unusual traffic", access queue** | `CAPTCHA_OR_ANTIBOT_STOP` |

### The distinctions that matter

**`NO_FLIGHT` is the only outcome that removes the cell from the coverage
denominator.** It means *no service was scheduled* — so the cell was never
expected and its absence is not a gap. Every other outcome keeps the cell in the
denominator, because the cell **was** expected and something went wrong.

Use it only when you are sure. "I couldn't find a flight" is not `NO_FLIGHT`; it
is `PARSER_FAILURE` or `SOURCE_UNAVAILABLE`. **When in doubt, never choose
`NO_FLIGHT`** — over-using it inflates coverage by shrinking the denominator,
which is the one direction that flatters the index.

**`SOURCE_UNAVAILABLE`, `PARSER_FAILURE` and `CAPTCHA_OR_ANTIBOT_STOP` are our
failures**, not the market's. They are published separately from market absence,
because a coverage figure that blends the two overstates how thin the market is
and understates how unreliable collection was.

**A partly-recorded search:** if you recorded 3 of 5 flights and then the page
broke, the attempt is `SUCCESS` with 3 rows. `SUCCESS` means *the attempt
produced usable fares*, not *the attempt was perfect*. Put the shortfall in
`notes`. An attempt with **zero** rows is never `SUCCESS` — the loader rejects
that combination outright.

### When `CAPTCHA_OR_ANTIBOT_STOP` happens

1. **Stop.** Do not solve it. Do not refresh. Do not open a private window, a
   different browser, a different network or a VPN.
2. Screenshot the challenge page — that is the evidence.
3. Record `CAPTCHA_OR_ANTIBOT_STOP` for **that** search.
4. **Do not attempt any further search against that source today.** Record the
   remaining searches as `CAPTCHA_OR_ANTIBOT_STOP` too.
5. Tell @slazyverse the same day.

There is no version of this where the right answer is getting past the
challenge. If this repeats, the source may have to leave the register — which is
an acceptable outcome, and far better than the alternative.

### Rate limiting

Leave **at least 30 seconds** between searches. Four searches in the window is
nowhere near a burst, and pacing keeps it that way.

---

## 9. Screenshots and raw artifacts

**Take a screenshot of the results page for every search**, including failed
ones. It is the only evidence that the numbers you typed were the numbers on
screen.

Name it:

```
{YYYYMMDD}-{window}-{travel_date}.png
2026-09-12-primary-20260919.png
```

Put the day's screenshots in one folder and pass it with `--artifacts`. The
loader matches a screenshot to an attempt by the travel date in the filename, so
**the `-{travel_date}` part is load-bearing**. A name that matches no attempt —
or more than one — **fails the load** rather than being filed against a guess: a
screenshot attached to the wrong search is worse than no screenshot, because it
makes a false provenance claim that looks checkable.

Artifacts are stored content-addressed by SHA-256: identical bytes store once,
and an artifact cannot be edited without changing its own address. That is what
makes §P.3's bit-for-bit reproducibility claim checkable rather than asserted.

**Never edit, crop or re-encode a stored screenshot.** `verify()` will report it
as modified, and any publication that used it loses its reproducibility
guarantee.

Retain for **five years**.

**Do not commit the store or the screenshots to Git.** `data/collection/` is
gitignored deliberately: retention is not version control, and pushing a
carrier's own pages to a public remote would redistribute their content. Back
the directory up somewhere private. Whether APIx keeps a shareable evidence
archive is an owner decision that has not been taken.

---

## 10. Timestamps

| Column | What to record |
|---|---|
| `time_ist` in `attempts.csv` | Clock time you **started** that search, `HH:MM`, IST |
| `time_ist` in `fares.csv` | Clock time you **read that flight's fare**, `HH:MM`, IST |

Minute precision is enough; a fare that moves within a minute is not a fare the
index can measure anyway.

- Record **IST**, always, regardless of where you are.
- `collection_date` is the IST date of the **window**, passed once as `--date`.
  A session that starts 23:50 and ends 00:10 keeps **one** `collection_date` —
  the date the window belongs to, not the wall-clock date of each request.
- Every quote gets its own time. Do not copy the search's start time down the
  column: `verify()` checks each observation against the run's declared window,
  and a copied timestamp destroys the evidence that would answer OQ-1.

**If the session runs outside the declared window**, record the real times
anyway. A late quote is **stored and flagged, never discarded** (§A.5). Faking
the time to stay inside the window corrupts the record permanently; recording it
honestly costs one flagged row.

---

## 11. How duplicates are identified

Two rows are the same observation when **all** of these match (§D.4):

```
collection_date · source_id · origin · destination · carrier
flight_number · travel_date · departure_time_local · fare_family_raw
```

`origin` and `destination` are in that tuple deliberately — **AMB-3**. Without
them, a synthetic full-frame day collapsed from 2,800 admissible quotes to 140,
losing 95% of the data silently.

The store enforces this with a unique index. A second row on the same tuple
**raises and the load fails**; it is not silently replaced, because a duplicate
means either the same offer was recorded twice or two genuinely different offers
share an identity — and both need a person to look.

**What this means in practice:** if you record the same flight twice at two fare
families, the rows differ in `fare_family_raw` and both load. If you record the
same flight twice at the same family, the load fails. That is correct.

`flight_number` is **digits only** — `2045`, never `6E2045`. The carrier is
already its own column, and doubling it up creates two spellings of one flight
that the duplicate rule cannot see through.

---

## 12. Recording the day

Two CSV files per run. Templates:
[`templates/attempts.csv`](../tools/collection/templates/attempts.csv) ·
[`templates/fares.csv`](../tools/collection/templates/fares.csv)

**`attempts.csv` — one row per search (4 rows on a normal day)**

```
travel_date,source_id,time_ist,origin,destination,outcome,source_group,notes
```

**`fares.csv` — one row per flight (up to 20 on a normal day)**

```
travel_date,source_id,time_ist,origin,destination,carrier,flight_number,
departure_time,stops,duration_minutes,fare_family_raw,availability,
payable_fare,base_fare,taxes,fees,user_development_fee,
checked_baggage_kg,change_permitted,cancellation_permitted,source_group,notes
```

Leave `source_group` empty. Blank means **ungrouped, never independent** (§B.6)
— that is the safe default, and it is set from the register, not by hand.

Then:

```bash
python tools/collection/load_manual.py --store data/collection --date 2026-09-12 --window primary --collector "Your Name" --attempts day01_attempts.csv --fares day01_fares.csv --artifacts day01_screenshots/
```

The loader **validates everything before it writes anything**. A day loads whole
or not at all, because a half-loaded day is worse than an unloaded one: it looks
complete. On failure it prints the row number and the reason, writes nothing, and
you fix the CSV and re-run.

On success it prints the day's quality report and exits `0`. If `verify()` found
an inconsistency it still prints the report but exits `2` — **investigate before
the next run**.

---

## 13. What to do when something is wrong

| Situation | Do this |
|---|---|
| Missed the window entirely | Record nothing. Tell @slazyverse. **A missed day costs two weekly links**, not one — the index compares `t` against `t−7`, so a gap on day 19 breaks day 12 and day 26 |
| Ran late — 22:30 instead of 21:15 | Collect anyway, record the real times. Flagged, not lost |
| Only got through 2 of 4 searches | Load what you have. Record the other two with the outcome that describes what stopped you |
| Fare changed while you were typing | Record the one you first saw, and note it. Do not re-search to "get a better number" |
| Site shows a different currency or a foreign price | Stop, fix the locale, start the search again. Do not convert |
| Not sure which fare family qualifies | Screenshot all of them and ask. Do not guess — a wrong family is a silent fare-class error |
| Unsure between two outcomes | Choose the one that keeps the cell in the denominator. Never guess `NO_FLIGHT` |

**Never back-fill a missed day from a later search.** A fare seen on day 14 for a
day-12 lead time is a different product at a different advance-purchase
distance. §A.3's exactness is what makes the index mean anything.

---

## 14. Daily checklist

```
[ ] 21:00 IST, same browser, same machine, not signed in
[ ] Four travel dates computed:  today +7, +15, +21, +30
[ ] Per search:  DEL > BOM, one way, 1 adult, Economy, Regular fare
[ ] Sort set to DEPARTURE TIME — EARLIEST FIRST      <- the one that matters
[ ] Top 5 eligible non-stop 6E flights
[ ] Cheapest fare including checked baggage, one row per flight
[ ] Components recorded only where displayed — blanks left blank, never 0
[ ] Screenshot per search, named {date}-{window}-{travel_date}.png
[ ] Every search has an attempts.csv row, including failures
[ ] Times recorded in IST, per row, honestly
[ ] Loader run; exit 0; report read
```

---

## 15. Known limitation — raised, not resolved

The three entitlement columns are read by a person from the fare rules. A
misread produces a **wrong fare class**, and a wrong fare class puts the quote in
the wrong cell — where it is not obviously wrong, because a `HAND_ONLY` fare
recorded as `STANDARD` looks merely cheap.

Nothing downstream can detect this. The screenshot is the only check, which is
why §9 requires one even for a search that worked.

Raised for @Rexy-5097 as an open item; **not** resolved here.

---

## References

- [`acquisition-protocol.md`](acquisition-protocol.md) — the rules and their justification
- [`../source_registry/registry.yaml`](../source_registry/registry.yaml) — automation and manual gates
- [`../source_registry/collection-frame.md`](../source_registry/collection-frame.md) — why DEL–BOM / 6E
- [`../source_registry/collection-windows.yaml`](../source_registry/collection-windows.yaml) — declared windows
- [`ADR-0064`](../artifacts/decisions/ADR-0064-collection-window-design.md) — window design
- [`../src/apix/ingestion/storage-design.md`](../src/apix/ingestion/storage-design.md) — where the data goes
- `docs/methodology/apix_formula_spec_v1.md` §A.3, §A.4, §A.5, §B.4, §D.4, §D.6, §H.1
