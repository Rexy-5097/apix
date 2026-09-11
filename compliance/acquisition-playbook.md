# APIx acquisition playbook — the complete operational manual

> **Checkpoint:** 2J · **Date:** 2026-09-12 · **Owner:** [@slazyverse](https://github.com/slazyverse)
> **Status:** Reference manual. **The 30-day collection has NOT started.**
> **Companions:** [`day-1-contract.md`](day-1-contract.md) (frozen values) ·
> [`manual-collection-procedure.md`](manual-collection-procedure.md) (the rules) ·
> [`acquisition-protocol.md`](acquisition-protocol.md) (why)

**Division of labour.** You perform anything requiring a human in a browser. I do
processing, validation, storage, canonicalisation, statistics and analysis. This
manual is written so you never make a methodological decision.

---

## PART 1 — The problem statement's Dataset Link

`https://esankhyiki.mospi.gov.in`

Everything in this part was verified live on 2026-09-12 against the portal's own
API. Where I could not verify something, it says so.

### 1.1 What it is

eSankhyiki is **MoSPI's own data-dissemination portal** — the ministry that
issued PS 26056 publishing its own official statistics. Its API base is
`https://api.mospi.gov.in/api`, serving JSON without authentication.

### 1.2 Why the PS provided it

**INFERENCE, clearly labelled.** The PS does not state its reason, and I will not
invent one. What the resource *contains* supports exactly one role, and it is not
the obvious one:

> **It is a VALIDATION BENCHMARK. It is not, and cannot be, an input to APIx.**

The reason is decisive and structural. APIx measures **transaction-level airfare
at daily frequency with advance-purchase structure**. eSankhyiki publishes a
**monthly CPI index number** for airfare — one number per month for All India,
already aggregated, already weighted, with no route, no carrier, no flight, no
booking date and no fare. You cannot build a daily quality-adjusted index out of
a monthly index number; the information is gone before it reaches the portal.

What you *can* do — and what the dossier requires — is check whether APIx moves
in the same direction and by a comparable magnitude as the official series. That
is validation, and it is why the link is there.

### 1.3–1.4 The relevant dataset, and what it is *not*

| Endpoint | Level | Airfare content |
|---|---|---|
| `/cpi/getItemIndex` | **Item** | **"Air Fare (normal): Economy Class(adult)"** ← **this one** |
| `/cpi/getCpiIndex` | Group / Sub-group | "Transport and Communication" — too coarse |
| `/cpi/getCpiBaseYear` | Metadata | Base years, levels, series |

Answering 4(a)–(g) exactly:

- (a) raw airfare data — **NO**
- (b) **CPI airfare index — YES, this is it**
- (c) DGCA airfare data — **NO** (different agency, not on this portal)
- (d) route/traffic data — **NO**
- (e) weights — **NO** (CPI item weights are not exposed by these endpoints)
- (f) **validation data — YES, this is its role**
- (g) other — the portal carries many unrelated products (ASI, PLFS, NFHS, WPI, IIP, HCES, UDISE…)

### 1.5 Exact endpoints

```
GET https://api.mospi.gov.in/api/cpi/getCpiBaseYear
GET https://api.mospi.gov.in/api/cpi/getItemIndex
GET https://api.mospi.gov.in/api/cpi/getItemIndex?page=2
GET https://api.mospi.gov.in/api/cpi/getItemIndex?year=2024
```

**Verified behaviour, and it has sharp edges:**

- **No authentication.** Returns 200 with JSON.
- **It fail-opens.** A *wrong* endpoint returns the portal's HTML with HTTP 200,
  not a 404. `/cpi/getGroupIndex`, `/cpi/getCpiFilter` and `/v3/api-docs` all do
  this. **Never treat HTTP 200 as proof an endpoint exists — parse the body.**
- **Only `page` and `year` are honoured.** `month`, `item`, `itemName`,
  `itemCode`, `search`, `recordPerPage`, `baseyear`, `from`/`to` are all
  **silently ignored** — no error, just unfiltered data. Silent parameter
  rejection is the most dangerous behaviour here.
- **Page size is fixed at 10** and cannot be changed.
- **POST is rejected** (`Cannot POST`).

### 1.6 Item codes

**OPEN — corrected from an earlier claim.** A previous session recorded COICOP
codes `07.3.3.1.2.01` (base 2024) and `6.1.03.3.2.07.0` (base 2012). **That
evidence was never committed to the repository and I could not reproduce it
today.** `/cpi/getItemIndex` returns **no code field at all** — items are keyed by
their display string only.

So the operative identifier is the exact literal:

```
Air Fare (normal): Economy Class(adult)
```

I am not asserting the COICOP codes. They may be correct and served elsewhere;
they are not served here, and I will not restate an uncommitted figure as fact.

### 1.7 Date range — verified

**January 2011 → December 2025.** Earliest record (last page, 5743) is January
2011 under base 2010. `getCpiBaseYear` reports base years **2010, 2012, 2024**;
`getItemIndex` currently serves **base 2012** for airfare.

> **OPEN:** I could not get base-2024 item data out of this endpoint — `baseyear`
> is one of the silently-ignored parameters. Unresolved.

### 1.8 Geography

**All India only**, at item level. `getItemIndex` returns no state or sector
field. State/sector exist only at group level via `getCpiIndex`. **So the airfare
benchmark has no geography — a fact that matters, because APIx's frame is one
route and the benchmark is national.**

### 1.9 Fields returned

`baseyear · year · month · item · index · inflation · status`

Envelope: `data[]`, `meta_data{page, totalRecords, totalPages, recordPerPage}`,
`msg`, `statusCode`. Currently `totalRecords: 57423`, `totalPages: 5743`.

### 1.10 Concrete example — real, retrieved 2026-09-12

```json
{
  "baseyear": "2012",
  "year": 2025,
  "month": "December",
  "item": "Air Fare (normal): Economy Class(adult)",
  "index": "206.3",
  "inflation": "1.58",
  "status": "F"
}
```

Read: December 2025 airfare CPI = **206.3** (2012 = 100), year-on-year inflation
**+1.58%**, status **F** = Final.

### 1.11–1.12 How it enters APIx

**AUXILIARY / VALIDATION BENCHMARK. Never an input.** It touches no collector, no
canonical observation, no elementary aggregate, no weight and no published index
value. It is compared against APIx *after* APIx is computed.

### 1.13–1.14 Is this the "30-day DGCA backtest"?

**No, and conflating them would be a serious error.**

| | eSankhyiki CPI airfare | The 30-day study |
|---|---|---|
| Publisher | MoSPI | APIx (ours) |
| Frequency | Monthly | Daily |
| Unit | Index number | Fare in ₹ |
| Geography | All India | DEL–BOM |
| Advance purchase | None | T+7/15/21/30 |
| Role | Benchmark | **Input** |

They cannot be substituted for one another in either direction. Also note: this
is **short-window validation, not a back-test** — with 30 days you get at most
one or two monthly CPI points to compare against, and *n* must be stated
whenever the comparison is reported.

### 1.15–1.16 Sufficiency

**Satisfies:** the need for an official, citable external benchmark. It is
genuine first-party government data, free, unauthenticated, with a 15-year
history.

**Does not satisfy, and nothing here will:** actual airfare observations; route
or carrier detail; advance-purchase structure; CPI item weights; DGCA traffic;
DGCA average fares; flight schedules.

### The five things that must never be conflated

| Source | What it actually is | Role in APIx |
|---|---|---|
| **MoSPI CPI airfare** (eSankhyiki) | Monthly All-India index number, base 2012 | **Validation benchmark** |
| **DGCA average fare** | Periodic regulatory monitoring of fare levels | Reference envelope; *not* on eSankhyiki |
| **DGCA traffic** | City-pair passenger volumes | **Route weights** (§G) |
| **Airline tariff sheets** | Declared fare *categories* per DGCA direction | Sanity envelope. *"A declared fare category is not a transacted consumer price"* |
| **Observed airfare quotes** | What you collect | **The only index input** |

---

## PART 2 — Source register, verified 2026-09-12

Every robots.txt below was fetched today. **Rule of construction: a permissive
robots.txt grants nothing** — it is a crawling directive, not a licence. Terms are
binding. (Akasa proves it: cleanest robots of any source, strictest terms.)

Under APIx's own contract, a robots `Disallow` on a path we need ⇒
`AUTOMATION_PROHIBITED`, because *we* honour robots.txt by policy.

### Airlines

| | IndiGo |
|---|---|
| **Domain** | goindigo.in |
| **Search page** | `https://www.goindigo.in/` — **no safe deep link**; the booking widget is a JS SPA and a deep-linked search URL is not stable. Use the homepage + click path in Part 3 |
| **Terms** | `https://www.goindigo.in/information/terms-of-use.html` — **UNREACHABLE from my host** |
| **robots.txt** | `https://www.goindigo.in/robots.txt` — **UNREACHABLE** (timeout, 3 attempts, 2 sessions) |
| **Access** | Manual browser only |
| **Automation** | **PROHIBITED** — terms forbid *"any automated use"*, *"data mining tools, robots"*, *"unauthorized systematic retrieval"* |
| **Manual** | **PERMITTED** — same clause excepts *"standard search engine or internet browser usage"* |
| **Admissibility** | **ADMISSIBLE** — live transactable fares |
| **Captures** | Flight no., dep/arr, duration, stops, fare families, entitlements, total; components *if rendered* |
| **Missing** | Fee decomposition may not be itemised |
| **Restrictions** | Caveat: the quoted clause is from the **BluChip loyalty** T&Cs. The general Terms of Use remain unread because the host is unreachable |

| | Air India | Air India Express | Akasa Air | SpiceJet |
|---|---|---|---|---|
| **Domain** | airindia.com | airindiaexpress.com | akasaair.com | spicejet.com |
| **robots.txt** | `/robots.txt` — **connection reset** | `/robots.txt` — intermittent (200 once, then timeout) | `/robots.txt` — **fetched** | `/robots.txt` — **fetched** |
| **robots content** | unknown | not captured | `User-Agent: *` + 2 Sitemaps. **No Disallow** | `Disallow:` (empty) + `/cgi-bin/`, `/api/v1`, `/public/`, `/externalBooking`. **Search not disallowed** |
| **Terms** | `https://www.airindia.com/en-in/terms-and-conditions/` (unverified) | `https://www.airindiaexpress.com/terms-and-conditions` (unverified) | `https://www.akasaair.com/quick-links/terms-and-conditions` | `https://www.spicejet.com/terms-and-conditions` (unverified) |
| **Automation** | **UNKNOWN** | **PROHIBITED** (2G) | **PROHIBITED** | **UNKNOWN** |
| **Manual** | UNKNOWN | UNKNOWN | **UNKNOWN** | UNKNOWN |
| **Admissibility** | ADMISSIBLE (live) | ADMISSIBLE | ADMISSIBLE | ADMISSIBLE |
| **Note** | Host rejects non-browser clients | — | Terms bar copying *"in print, visual or electronic form, for any purpose whatsoever"*, **no browser carve-out** | **The only carrier whose robots permits search paths.** Terms unread ⇒ UNKNOWN, never ALLOWED |

### OTAs — robots.txt verified today

| Source | robots on flight search | Automation |
|---|---|---|
| **MakeMyTrip** | connection reset — unknown | **UNKNOWN** |
| **Yatra** | connection reset — unknown | **UNKNOWN** |
| **EaseMyTrip** | `Disallow: /flight-search/listing*` | **PROHIBITED** |
| **Cleartrip** | `Disallow: /flights/search*`, `/m/flights/search*` | **PROHIBITED** |
| **Ixigo** | `Disallow: /flights/search`, `/flights/review`, `/api/` | **PROHIBITED** |
| **Goibibo** | `Disallow: /flights/*?mode=*`, `/cheap/flight-tickets/` | **PROHIBITED** |

Terms URLs: `easemytrip.com/terms-and-conditions.html` ·
`cleartrip.com/legal/terms-of-service` · `ixigo.com/about/terms` ·
`goibibo.com/legal/` · `makemytrip.com/legal/` · `yatra.com/online/terms-and-conditions` —
**all unverified from this host; treat as click-paths, not citations.**

**Every OTA whose robots I could read disallows flight search.** That is not a
coincidence — search results are expensive to generate and universally excluded
from crawling.

### The bottom line

**IndiGo is the only source that is both permitted for the mode we use and
admissible as index input.** SpiceJet is the one worth re-auditing (clean robots,
unread terms) — a future checkpoint, not Day 1.

---

## PART 3 — Click-by-click, IndiGo

> **Honesty note, and it matters.** `goindigo.in` is unreachable from my host, so
> I **could not verify today's exact button labels**. Below, the *function* of
> each step is authoritative; the *label* is the expected wording. If a label
> differs, follow the function — and **on Day 1, screenshot the results page and
> the fare-detail panel and send them to me**. I will pin exact labels for days
> 2–30. Do not guess at methodology; guessing at which button says "Sort" is fine.

### Per search (repeat 4×, once per APW)

```
 1. Open  https://www.goindigo.in/
 2. Cookie banner → choose the REJECT / decline-non-essential option.
 3. Do NOT sign in. No saved logged-in profile.
 4. In the booking widget, select the "One Way" trip type.
 5. FROM field → type  DEL  → pick "Delhi (DEL)" from the dropdown.
 6. TO field   → type  BOM  → pick "Mumbai (BOM)" from the dropdown.
 7. DEPARTURE DATE → open the calendar → CLICK the exact travel date
    (Part 5 computes it). Never accept the default.
 8. PASSENGERS → 1 Adult, 0 Children, 0 Infants.
 9. Fare type → "Regular". NOT Student / Armed Forces / Senior Citizen.
10. Currency → INR.
11. Click SEARCH.
12. Wait for the results list to finish loading.
13. >>> SCREENSHOT the results page now, before touching any filter. <<<
14. Apply the NON-STOP filter (usually "Stops → Non-stop" / "0 stop").
15. Set SORT to "Departure — Earliest first".
16. Now select 5 flights, one per departure band (Part 4).
```

### Per selected flight (repeat 5×)

```
17. Read and record, from the results row:
      flight number     -> shown as "6E 2045"; record DIGITS ONLY -> 2045
      departure time    -> left of the row, e.g. 06:20
      duration          -> centre of the row, e.g. "2h 15m" -> record 135
      stops             -> must read "Non-stop" -> record 0
18. Click the fare-family selector for that flight (expands fare options).
19. Identify the CHEAPEST family that INCLUDES CHECKED BAGGAGE.
      - read the baggage line, e.g. "15 kg check-in"
      - a "cabin/hand baggage only" family is NOT it
20. Record the family's displayed name verbatim -> fare_family_raw (e.g. SAVER)
21. From that family's entitlement list record:
      checked_baggage_kg      e.g. 15
      change_permitted        FREE / FEE / NONE
      cancellation_permitted  FREE / FEE / NONE
22. Open the fare breakdown for that family — the fare summary panel, or the
    "Fare details" / "View fare breakup" link near the price.
23. Record ONLY what is displayed:
      base_fare             blank if not shown
      taxes                 blank if not shown
      fees                  blank if not shown
      user_development_fee  blank if not shown (may appear as UDF / ADF)
      payable_fare          the all-inclusive total for 1 adult  [REQUIRED]
24. >>> SCREENSHOT the fare-detail panel. <<<
25. Note the clock time (HH:MM IST) at which you read this fare -> time_ist
26. Close the panel. Next band.
```

**Never compute a missing component by subtraction.** If the page shows a total
and a base fare but no tax line, `taxes` is **blank**. §A.4 is explicit that the
index is never blocked on a breakdown the site does not render — the total enters
the index regardless, so there is nothing to gain by inventing the parts.

---

## PART 4 — The frame, verified against the repository

Every value you listed **matches** the frozen contract. Verified line by line
against [`compliance/day-1-contract.md`](day-1-contract.md) and
[`source_registry/collection-windows.yaml`](../source_registry/collection-windows.yaml).

| Your value | Repo | ✓ |
|---|---|---|
| DEL → BOM | day-1-contract.md | ✓ |
| IndiGo / AIRLINE_DIRECT / 1 adult / non-stop | day-1-contract.md | ✓ |
| 5 flights, bands 2–6 | day-1-contract.md; enforced in `load_manual.py` | ✓ |
| Earliest by departure time within each band | day-1-contract.md; ADR-0065 §4 | ✓ |
| T+7, T+15, T+30 index | day-1-contract.md | ✓ |
| T+21 exploratory | day-1-contract.md; ADR-0065 §5 | ✓ |
| Primary 21:00–22:00 IST | collection-windows.yaml | ✓ |
| Diagnostic 09:00–10:00 IST, days 1,4,7,10,13,16,19 | collection-windows.yaml:50 | ✓ |
| 30 consecutive days | implied, not literal — see below | ~ |

### Two discrepancies I must report rather than paper over

**1. The frozen contract is not on `main`.** It lives on branch
`feat/slazy/checkpoint-2i/day-1-acquisition` in **open PR #10**. It is frozen in
intent and reviewed-pending in fact. *Merging #10 before Day 1 is the clean
sequence.*

**2. "30 consecutive days" is implied, not stated.** `day-1-contract.md` says
*"the whole 30-day window"* and lists *"a missed collection day"* under what ends
the window. Consecutiveness follows from that, but the literal word is absent.
Your reading is correct; the wording is looser than your statement.

### The five bands

| Band | Departure between | Take |
|---|---|---|
| 2 | 06:00–08:59 | earliest eligible |
| 3 | 09:00–11:59 | earliest eligible |
| 4 | 12:00–14:59 | earliest eligible |
| 5 | 15:00–17:59 | earliest eligible |
| 6 | 18:00–20:59 | earliest eligible |

Before 06:00 and from 21:00 → **not collected**. An empty band → **no row**;
never pad from a neighbouring band. The loader **rejects** two different flights
in one band, and rejects any flight outside bands 2–6.

---

## PART 5 — What date do I search for?

### What "T" means

**T = `collection_date` = the IST calendar date of the collection window**, passed
to the loader as `--date`. It is *not* the travel date and *not* the wall-clock
date of each request.

```
travel_date = collection_date + N calendar days     N ∈ {7, 15, 21, 30}
```

Calendar days, not business days. In code: `lead_time_days = travel_date −
collection_date`, and §A.3 assigns the APW bucket by **exact** match.

### Worked example — collection_date = 2026-09-12

| APW | Arithmetic | **Travel date to search** | Weekday |
|---|---|---|---|
| T+7 | 12 Sep + 7 | **2026-09-19** | Saturday |
| T+15 | 12 Sep + 15 | **2026-09-27** | Sunday |
| T+21 | 12 Sep + 21 (Sep has 30 days → 33 − 30 = 3 Oct) | **2026-10-03** | Saturday |
| T+30 | 12 Sep + 30 (42 − 30 = 12 Oct) | **2026-10-12** | Monday |

### The rules around it

- **Inclusive?** The travel date is the **departure date itself**. T+7 from 12 Sep
  means a flight *departing* 19 Sep. Count forward 7 days from the collection
  date; do not add or subtract one.
- **Timezone.** Everything is **IST**, always, wherever you are. `collection_date`
  is the date of the *window*: a session running 23:50→00:10 keeps **one**
  `collection_date`.
- **Target date unavailable** (calendar won't allow it): record the attempt as
  `STRUCTURAL_MISSING` with a note, screenshot it, continue to the next APW.
  **Never substitute a neighbouring date** — a T+8 quote matches no bucket and is
  inadmissible; silently sliding it into T+7 corrupts the series permanently.
- **Flight does not operate** (no IndiGo DEL–BOM service that day at all):
  `NO_FLIGHT`. Use this **only** when you are sure — it is the one outcome that
  removes the cell from the coverage denominator, and over-using it inflates
  coverage, the one direction that flatters the index.
- **Flight sold out:** `availability = SOLD_OUT`, `payable_fare` **blank**, all
  identity fields filled. It is a *disappeared item* (§D.6), not a missing price.
  If **every** flight in the search is sold out, the attempt is
  `TECHNICAL_FAILURE`.

---

## PART 6 — Exactly what to record

| Field | Where to find it | Example | Req? | If missing |
|---|---|---|---|---|
| `origin` / `destination` | Your search input | `DEL` / `BOM` | ✅ | n/a — fixed |
| `carrier` | Flight row | `6E` | ✅ | n/a — fixed |
| `flight_number` | Flight row, "6E 2045" | `2045` | ✅ | **Digits only.** Never `6E2045` |
| `departure_time` | Flight row, left | `06:20` | ✅ | Cannot be missing; if unreadable → `PARSER_FAILURE` |
| `travel_date` | Your search date | `2026-09-19` | ✅ | n/a |
| `time_ist` | **Your clock**, when you read the fare | `21:15` | ✅ | Per row. Never copy down the column |
| `collection_date` | Passed as `--date` | `2026-09-12` | ✅ | n/a |
| `stops` | Flight row, "Non-stop" | `0` | ✅ | Non-stop only; else not eligible |
| `duration_minutes` | Flight row, "2h 15m" | `135` | ✅ | Convert to minutes |
| `fare_family_raw` | Fare-family tab label | `SAVER` | ✅ | Verbatim. Never used for matching |
| `availability` | Whether a seat is buyable | `AVAILABLE` / `SOLD_OUT` | ✅ | — |
| `payable_fare` | All-inclusive total, 1 adult | `5432.00` | ✅ if AVAILABLE | Blank **only** if `SOLD_OUT` |
| `base_fare` | Fare breakdown panel | `4100.00` | ❌ | **Leave blank. Never 0. Never subtract** |
| `taxes` | Fare breakdown panel | `1002.00` | ❌ | **Leave blank** |
| `fees` | Fare breakdown panel | *(blank)* | ❌ | **Leave blank** |
| `user_development_fee` | Breakdown, "UDF"/"ADF" | `330.00` | ❌ | **Leave blank** |
| `checked_baggage_kg` | Fare entitlements, "15 kg check-in" | `15` | ✅ | Hand-baggage-only = `0` |
| `change_permitted` | Fare rules | `FEE` | ✅ | `FREE`/`FEE`/`NONE`. Unreadable → screenshot, ask me |
| `cancellation_permitted` | Fare rules | `FEE` | ✅ | same |
| `source_id` | Fixed | `indigo-direct` | ✅ | n/a |
| `source_group` | **Leave blank** | *(blank)* | ❌ | Blank = ungrouped, never independent (§B.6) |
| `notes` | Free text | `band 4` | ❌ | — |

### Fields you must NOT record — I derive them

`fare_class` (from entitlements, §B.4) · `lead_time_days` · `apw_bucket` ·
`day_of_week` · `departure_hour_band` · `route` · `channel` · `source_type` ·
`observation_ts` · `observation_id`

**These are derived, never stored from input**, so they cannot contradict the
dates and entitlements they come from. If you typed `fare_class` yourself and
misread the baggage line, the error would agree with itself.

---

## PART 7 — Every failure case

| Situation | Record | `CollectionOutcome` | Screenshot | Retry | Continue | Successful attempt? |
|---|---|---|---|---|---|---|
| Operates + fare available | Full fare row | `SUCCESS` | ✅ fare panel | — | ✅ next band | ✅ |
| Operates + **sold out** | Row, `SOLD_OUT`, **blank fare** | `SUCCESS` if others priced; `TECHNICAL_FAILURE` if all sold out | ✅ | ❌ | ✅ | ✅ if ≥1 priced |
| **No flight at all** that date | No fare rows | `NO_FLIGHT` | ✅ empty results | ❌ | ✅ next APW | ❌ |
| Route/flight **permanently withdrawn** | No rows | `STRUCTURAL_MISSING` | ✅ | ❌ | ✅ | ❌ |
| **Page unavailable** / error / timeout | No rows | `SOURCE_UNAVAILABLE` | ✅ error page | **once**, after 60s | ✅ if recovered | ❌ |
| **Technical failure** (loads, quote absent, transient) | No rows | `TECHNICAL_FAILURE` | ✅ | once | ✅ | ❌ |
| **CAPTCHA** | No rows | `CAPTCHA_OR_ANTIBOT_STOP` | ✅ the challenge | ❌ **NEVER** | ❌ **STOP ALL** | ❌ |
| **Anti-bot / "unusual traffic" / queue** | No rows | `CAPTCHA_OR_ANTIBOT_STOP` | ✅ | ❌ **NEVER** | ❌ **STOP ALL** | ❌ |
| **Fare component hidden** | Row with that cell **blank** | `SUCCESS` | ✅ | ❌ | ✅ | ✅ |
| **Fare changes while inspecting** | The fare you **first saw**; note it | `SUCCESS` | ✅ | ❌ don't re-search | ✅ | ✅ |
| **Multiple fare families** | **One row** — cheapest with checked baggage | `SUCCESS` | ✅ all families | ❌ | ✅ | ✅ |
| **Flight disappears after search** | Skip it; note in `notes` | `SUCCESS` (others) | ✅ | ❌ | ✅ next band | ✅ |
| **Duplicate flight in results** | Record **once** | `SUCCESS` | ✅ | ❌ | ✅ | ✅ |
| **Different fare after clicking** | The **fare-detail** figure; note both | `SUCCESS` | ✅ **both** | ❌ | ✅ | ✅ |

### CAPTCHA / anti-bot — the one absolute rule

```
1. STOP.
2. Do NOT solve it. Do NOT refresh. Do NOT open a private window.
   Do NOT switch browser, network, device or VPN.
3. Screenshot the challenge — that is the evidence.
4. Record CAPTCHA_OR_ANTIBOT_STOP for that search.
5. Record the REMAINING searches for today as CAPTCHA_OR_ANTIBOT_STOP too.
6. Stop collecting from that source for the rest of the day. Tell me.
```

There is no version of this where the right answer is getting past the challenge.
If it repeats, the source leaves the register — an acceptable outcome, and far
better than the alternative.

**Pacing:** leave **≥30 seconds** between searches.

---

## PART 8 — Screenshots and raw artifacts

### The repository convention — use this exactly

```
{YYYYMMDD}-{window}-{travel_date}.png
```

```
20260912-primary-20260919.png          ← T+7  search on 12 Sep
20260912-primary-20260927.png          ← T+15
20260912-primary-20261003.png          ← T+21
20260912-primary-20261012.png          ← T+30
20260912-diagnostic_oq1-20260919.png   ← diagnostic days only
```

**The travel-date suffix is load-bearing.** The loader matches a screenshot to an
attempt by the travel date in the filename. A name matching **no** attempt, or
**more than one**, **fails the load** — deliberately: a screenshot filed against
the wrong search makes a false provenance claim that looks checkable.

### What to capture

| Artifact | How many | Required |
|---|---|---|
| **Search-results page** (after load, before filters) | **1 per search** = 4/day | ✅ **This is the one the loader ingests** |
| **Fare-detail panel** | 1 per flight = ~5/search | ✅ Keep; your evidence for components and entitlements |
| **Failure/challenge page** | 1 per failure | ✅ |

Only the results-page screenshot needs the strict filename. Name fare-detail
shots freely (e.g. `20260912-T7-band2-6E2045-fare.png`) and keep them in the same
folder — the loader ignores extras it cannot match **only if they contain no
attempt travel-date**, so **put fare-detail shots in a `details/` subfolder** to
be safe. The loader reads only the top level of `--artifacts`.

### Where to put them

```
D:\WorkSpace\SIH\Tulya\apix\collection-input\day01\
    day01_attempts.csv
    day01_fares.csv
    shots\
        20260912-primary-20260919.png     ← ingested
        ...
        details\                          ← kept, not ingested
            20260912-T7-band2-6E2045-fare.png
```

Artifacts are stored **content-addressed by SHA-256**: identical bytes store once,
and a file cannot be edited without changing its own address. **Never edit, crop
or re-encode** a screenshot after loading — `verify()` will report it as modified
and any publication that used it loses its reproducibility guarantee. Retain
**5 years**. URL capture is not required; the source is fixed by `source_id`.

---

## PART 9 — CSV entry

### `day01_attempts.csv` — one row per **search** (4 rows)

```
travel_date,source_id,time_ist,origin,destination,outcome,source_group,notes
```

```csv
travel_date,source_id,time_ist,origin,destination,outcome,source_group,notes
2026-09-19,indigo-direct,21:05,DEL,BOM,SUCCESS,,
2026-09-27,indigo-direct,21:14,DEL,BOM,SUCCESS,,
2026-10-03,indigo-direct,21:21,DEL,BOM,SUCCESS,,T+21 exploratory
2026-10-12,indigo-direct,21:29,DEL,BOM,NO_FLIGHT,,no 6E DEL-BOM service shown
```

`outcome` ∈ `SUCCESS` · `NO_FLIGHT` · `STRUCTURAL_MISSING` · `TECHNICAL_FAILURE` ·
`SOURCE_UNAVAILABLE` · `PARSER_FAILURE` · `CAPTCHA_OR_ANTIBOT_STOP`

### `day01_fares.csv` — one row per **flight** (≤5 per search)

```
travel_date,source_id,time_ist,origin,destination,carrier,flight_number,
departure_time,stops,duration_minutes,fare_family_raw,availability,
payable_fare,base_fare,taxes,fees,user_development_fee,
checked_baggage_kg,change_permitted,cancellation_permitted,source_group,notes
```

```csv
travel_date,source_id,time_ist,origin,destination,carrier,flight_number,departure_time,stops,duration_minutes,fare_family_raw,availability,payable_fare,base_fare,taxes,fees,user_development_fee,checked_baggage_kg,change_permitted,cancellation_permitted,source_group,notes
2026-09-19,indigo-direct,21:06,DEL,BOM,6E,2045,06:20,0,135,SAVER,AVAILABLE,5432.00,4100.00,1002.00,,330.00,15,FEE,FEE,,band2
2026-09-19,indigo-direct,21:08,DEL,BOM,6E,5011,09:45,0,140,SAVER,AVAILABLE,6110.00,,,,,15,FEE,FEE,,band3 total only
2026-09-19,indigo-direct,21:10,DEL,BOM,6E,6153,13:10,0,130,SAVER,SOLD_OUT,,,,,,15,FEE,FEE,,band4 sold out
```

### Representing things

| Case | How |
|---|---|
| **Missing component** | **Empty cell.** Never `0`, `-`, `N/A`, `null` |
| **Sold out** | `availability=SOLD_OUT`, `payable_fare` **empty**, identity fields filled |
| **Failed attempt** | Row in `attempts.csv` only; **no** row in `fares.csv` |
| Money | `5432.00`. `₹` and `,` are stripped, but **quote the cell** if you keep a comma |
| Times | `HH:MM`, 24-hour, IST |
| Dates | `YYYY-MM-DD` |

**Encoding:** save as UTF-8 CSV. Excel's "CSV UTF-8" is fine (a BOM is handled).

---

## PART 10 — Loading

### The exact command

```bash
python tools/collection/load_manual.py --store data/collection --date 2026-09-12 --window primary --collector "Your Name (manual, Chrome, Windows)" --attempts collection-input/day01/day01_attempts.csv --fares collection-input/day01/day01_fares.csv --artifacts collection-input/day01/shots
```

| Flag | Meaning |
|---|---|
| `--store` | Store root. **Always `data/collection`** — gitignored, holds SQLite + artifacts |
| `--date` | **The collection date (T)**, not a travel date. IST date of the window |
| `--window` | `primary` (index) or `diagnostic_oq1` (OQ-1 only). Must match `collection-windows.yaml` |
| `--collector` | **A real person's name** + environment. Manual runs must name a human to be auditable |
| `--attempts` / `--fares` | Your two CSVs |
| `--artifacts` | Folder of results-page screenshots |

### Exit codes

| Code | Meaning | Do |
|---|---|---|
| **0** | Loaded and `verify()` found nothing wrong | Back up, done |
| **1** | **Validation failed — NOTHING was written** | Fix the row it names, re-run. Safe to retry |
| **2** | Loaded, but `verify()` found integrity problems | **Send me the output before the next run** |

A day loads **whole or not at all** — a half-loaded day looks complete, which is
worse than an unloaded one.

### Then back up — every day

```bash
cp -r data/collection /your/backup/apix-collection-20260912
```

`data/collection/` is gitignored and irreplaceable. A disk failure at day 25
destroys a study that cannot be re-collected: §A.3 assigns by exact lead time, so
those flights, dates and prices are gone.

### What to send me

1. The **full JSON** the loader prints.
2. The **exit code**.
3. Any `LOAD FAILED` text.
4. **Day 1 only:** the results-page and fare-detail screenshots, so I can pin the
   exact UI labels for days 2–30.
5. Anything that surprised you.

---

## PART 11 — Automation, reassessed

A source is automation-ready **only if all three clear**.

| Source | Permission | Admissibility | Technical | **Automate?** |
|---|---|---|---|---|
| IndiGo | ❌ PROHIBITED | ✅ | ❌ unreachable | **NO** |
| Air India | ❓ UNKNOWN | ✅ | ❌ reset | **NO** |
| Air India Express | ❌ PROHIBITED | ✅ | ❓ | **NO** |
| Akasa Air | ❌ PROHIBITED | ✅ | ✅ | **NO** |
| SpiceJet | ❓ UNKNOWN | ✅ | ✅ | **NO** (unknown ⇒ no) |
| MakeMyTrip | ❓ UNKNOWN | ✅ | ❌ reset | **NO** |
| Yatra | ❓ UNKNOWN | ✅ | ❌ reset | **NO** |
| EaseMyTrip | ❌ robots | ✅ | ✅ | **NO** |
| Cleartrip | ❌ robots | ✅ | ✅ | **NO** |
| Ixigo | ❌ robots | ✅ | ✅ | **NO** |
| Goibibo | ❌ robots | ✅ | ✅ | **NO** |
| **Amadeus Self-Service** | ✅ **ALLOWED** | ❌ **cached, "prices aren't real"** | ✅ | **NO** |
| **Travelpayouts** | ✅ **ALLOWED** | ❌ cached 2–7 d; breaks §B.6 | ✅ | **NO** |
| **eSankhyiki CPI** | ✅ ALLOWED | ✅ **as a benchmark** | ✅ | ✅ **YES — I automate this** |

**Not one airfare source is automation-ready.** The two with explicit permission
do not sell a transactable price; the ones with real prices prohibit or have not
permitted automation. **Technical access is never a reason** — that Playwright
*can* open a page says nothing about whether we may.

**Only eSankhyiki I will automate**, and it is a benchmark, not an input.

---

## PART 12 — Architecture

```
┌─ PROBLEM STATEMENT DATASET LINK ────────────────────────────────────┐
│  https://esankhyiki.mospi.gov.in                                    │
│      └─ api.mospi.gov.in/api/cpi/getItemIndex                       │
│           └─ "Air Fare (normal): Economy Class(adult)"              │
│                monthly · All India · base 2012 · Jan 2011–Dec 2025  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │  NOT an input. Never enters the index.
                                ▼
                    ╔═══════════════════════╗
                    ║ VALIDATION BENCHMARK  ║ ◄──── compared AFTER computation
                    ╚═══════════════════════╝        (short-window, n stated)
                                ▲
                                │
┌─ COLLECTION SOURCES ────────────────────────────────────────────┐   │
│                                                                 │   │
│  Airline live search   ──► IndiGo DEL–BOM  [MANUAL, YOU]  ──┐   │   │
│  OTA search            ──► all PROHIBITED/UNKNOWN — unused  │   │   │
│  Airline tariff sheets ──► declared CATEGORIES ─────────┐   │   │   │
│  Licensed feeds        ──► cached — INADMISSIBLE        │   │   │   │
└─────────────────────────────────────────────────────────┼───┼───┘   │
                                                          │   │       │
                                    sanity envelope ◄─────┘   │       │
                                    (never an observation)    │       │
                                                              ▼       │
                                              ┌───────────────────────┴──┐
                                              │ RAW AIRFARE OBSERVATIONS │
                                              │ CSV + screenshots (SHA-256)
                                              └────────────┬─────────────┘
                                                           ▼
                                              ┌──────────────────────────┐
                                              │ CANONICAL OBSERVATION    │
                                              │ dedup §D.4 · admiss §A.6 │
                                              └────────────┬─────────────┘
                                                           ▼
                                              ┌──────────────────────────┐
                                              │ APIx DETERMINISTIC INDEX │
                                              │ Jevons → Young/Laspeyres │
                                              │ (APIx-TPD in parallel)   │
                                              └────────────┬─────────────┘
                                                           │
                                                           └──► compared ──┘

┌─ REFERENCE DATA (weights & frame, not observations) ────────────────┐
│  DGCA city-pair traffic  ──► ROUTE WEIGHTS (§G)                     │
│  DGCA schedules          ──► frame / expected cells (AMB-8, open)   │
│  DGCA average fare       ──► reference envelope. NOT on eSankhyiki   │
└─────────────────────────────────────────────────────────────────────┘
```

**Where each thing belongs, in one line each:**

| Thing | Belongs |
|---|---|
| **eSankhyiki CPI airfare** | Validation benchmark, after the index |
| **DGCA traffic** | Route weights (§G) |
| **DGCA schedule** | Frame / coverage denominator (AMB-8, open) |
| **Airline tariff sheets** | Sanity envelope only — a declared category is not a transacted price |
| **Airline live search** | **The only index input** |
| **OTA search** | Intended second channel; none currently usable |

---

## PART 13 — Day-1 checklist

```
BEFORE COLLECTION
[ ] PR #10 merged to main (or accept the contract is review-pending)
[ ] git pull
[ ] Compute the four travel dates from today  (+7, +15, +21, +30)
[ ] Write them down. Check the month rollover arithmetic.
[ ] Create  collection-input/day01/shots/details/
[ ] Copy both CSV templates from tools/collection/templates/, blank the rows
[ ] Same browser, same machine, INR, no VPN, NOT signed in
[ ] Clock shows 21:00-22:00 IST

FOR EACH APW  (4×: T+7, T+15, T+21, T+30)
[ ] Open https://www.goindigo.in/
[ ] Decline non-essential cookies
[ ] One Way · DEL · BOM · 1 Adult · Regular · INR
[ ] CLICK the exact travel date in the calendar
[ ] Search, wait for full load
[ ] SCREENSHOT results  ->  {YYYYMMDD}-primary-{travel_date}.png
[ ] Filter Non-stop
[ ] SORT = Departure, earliest first          <-- NEVER by price
[ ] Add one row to day01_attempts.csv with the outcome + start time
[ ] Wait 30s before the next search

FOR EACH FLIGHT  (5×: bands 06-09, 09-12, 12-15, 15-18, 18-21)
[ ] Take the FIRST eligible flight in the band (empty band -> no row, no padding)
[ ] Record flight number DIGITS ONLY, departure time, duration in minutes, stops=0
[ ] Pick the cheapest fare family INCLUDING CHECKED BAGGAGE
[ ] Record fare_family_raw verbatim
[ ] Record baggage kg, change, cancellation
[ ] Open fare breakdown -> SCREENSHOT to shots/details/
[ ] Record ONLY displayed components. Blank stays blank. NEVER 0. NEVER subtract.
[ ] Record payable_fare (required unless SOLD_OUT)
[ ] Record time_ist for THIS flight
[ ] Add the row to day01_fares.csv

AFTER COLLECTION
[ ] 4 rows in attempts.csv? (one per APW, including failures)
[ ] <=5 rows per APW in fares.csv, all in DIFFERENT bands?
[ ] Every blank truly blank, no zeros?
[ ] 4 results screenshots named correctly?
[ ] Files saved as UTF-8

LOAD
[ ] Run the Part 10 command
[ ] Read the exit code

VERIFY
[ ] Exit 0 -> back up data/collection/, send me the JSON
[ ] Exit 1 -> nothing written; fix the named row, re-run
[ ] Exit 2 -> send me the JSON BEFORE collecting tomorrow
[ ] Day 1 only: send screenshots so I can pin exact UI labels
```

---

## PART 14 — Final answers

1. **SITE FOR DAY 1** — IndiGo's own website. The only source both permitted for
   manual collection and admissible as index input.
2. **URL** — `https://www.goindigo.in/` (homepage + Part 3 click path; the search
   page is a JS SPA with no stable deep link)
3. **TERMS URL** — `https://www.goindigo.in/information/terms-of-use.html`
   *(unreachable from my host; unverified)*
4. **ROBOTS URL** — `https://www.goindigo.in/robots.txt` *(unreachable; NOT_VERIFIED)*
5. **SEARCH FLOW** — Part 3. One Way → DEL → BOM → click exact date → 1 Adult →
   Regular → INR → Search → screenshot → non-stop filter → **sort by departure
   time** → one flight per band 2–6.
6. **DATA TO RECORD** — Part 6. 20 typed fields + 1 note. Derived fields are mine.
7. **FLIGHTS** — **5 per search** (one per band 2–6), **4 searches**, so **≤20
   fare rows/day**. Empty band → fewer, never padded.
8. **APWs** — index **T+7, T+15, T+30**; exploratory **T+21** (inadmissible by
   construction, collected for OQ-A6).
9. **TRAVEL-DATE CALCULATION** — `travel_date = collection_date + {7,15,21,30}`
   calendar days. From 2026-09-12 → **19 Sep, 27 Sep, 3 Oct, 12 Oct 2026**.
10. **ARTIFACTS** — 4 results screenshots named
    `{YYYYMMDD}-primary-{travel_date}.png` (ingested), plus fare-detail shots in
    `shots/details/`. Never edited after loading.
11. **CSV FILES** — `day01_attempts.csv` (4 rows) and `day01_fares.csv` (≤20 rows),
    columns exactly as Part 9.
12. **LOAD COMMAND** — Part 10.
13. **ROLE OF eSankhyiki** — **VALIDATION BENCHMARK ONLY.** Monthly All-India CPI
    airfare index (base 2012, Jan 2011–Dec 2025), item *"Air Fare (normal):
    Economy Class(adult)"*, Dec 2025 = 206.3. It has no route, carrier, flight,
    booking date or fare, so it cannot be an input to a daily index. I pull it
    automatically; it never touches the index path.
14. **CAN CLAUDE AUTOMATE DAY 1** — **NO.**
15. **WHY** — Three independent reasons, each sufficient: **(a)** IndiGo's terms
    prohibit *"any automated use"* and carve out only *"standard search engine or
    internet browser usage"* — an agent driving a browser is the prohibited half;
    **(b)** `goindigo.in` is unreachable from my host (timeouts across three
    attempts and two sessions, while control fetches of other domains succeed);
    **(c)** no airfare source anywhere clears permission + admissibility +
    technical access together.
16. **WHAT YOU MUST DO** — Open the browser, run the 4 searches in the
    21:00–22:00 IST window, apply the band rule, read the fares, take the
    screenshots, fill the two CSVs, run the load command, back up the store.
17. **WHAT I DO AFTER** — Validate and canonicalise; derive fare class, APW,
    weekday and band; deduplicate (§D.4); run admissibility (§A.6); verify
    artifact hashes and window compliance; compute exclusion and coverage;
    monitor identity stability; build weekly Jevons links from day 8; run
    APIx-L and APIx-TPD when the window supports them; pull and align the
    eSankhyiki benchmark; report every figure with its *n*.

---

## Open items — stated, not hidden

| Item | Status |
|---|---|
| IndiGo general Terms of Use | **UNREAD** — host unreachable. Governing clause is from the loyalty T&Cs |
| IndiGo robots.txt | **NOT_VERIFIED** — timeout |
| CPI COICOP item codes | **UNVERIFIED** — not served by `getItemIndex`; earlier claim uncommitted and unreproduced |
| CPI base-2024 series | **UNRESOLVED** — `baseyear` silently ignored |
| Air India / MakeMyTrip / Yatra robots | **UNKNOWN** — connection reset |
| Air India Express robots | **PARTIAL** — one 200 response, content not captured |
| SpiceJet terms | **UNREAD** — the best automation candidate; robots permits search |
| Exact IndiGo UI labels | **UNVERIFIED** — pinned from your Day-1 screenshots |
| AMB-8 expected cells, AMB-9 carrier allocation, OQ-1 window | **OPEN** by design |
