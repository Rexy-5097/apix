# The acquisition protocol — Day 1 onward

**Owner:** [@slazyverse](https://github.com/slazyverse) · **Checkpoint:** 2G · **Date:** 2026-09-11
**Governs:** every collection run · **Companion:** [`collection-control-contract.md`](collection-control-contract.md)

This is the procedure a run follows. It is frozen **before** Day 1 on purpose:
changing the protocol mid-window changes what the 30 days measured, and a
mid-window change cannot be undone because the earlier days cannot be recollected.

> **The 30-day clock has not started.** Blockers are in §14.

---

## 1. Mode — manual, not automated

The Checkpoint 2G automation gate leaves **zero sources `AUTOMATION_ALLOWED`**.
Day 1 is therefore **collection by a person in a browser**, which is a different
activity and is separately gated:

- IndiGo's terms carve it out explicitly — *"Except as may be the result of
  standard search engine or **internet browser usage**"*.
- MoSPI's CPI does exactly this. Expert Group Report: *"Airfare data are to be
  collected by State Regional Offices from the **well-known websites**."*

**No automated run may start until a source reaches `AUTOMATION_ALLOWED` on
positive, quoted evidence.** `AUTOMATION_UNKNOWN` does not permit a trial run.

## 2. Collection window — §A.5

| | |
|---|---|
| Window | **One fixed 60-minute window per day**, the same clock time every day |
| Recommended | **21:00–22:00 IST** — a slot a person can actually hold |
| Recorded | `CollectionRun.collection_window_start` / `_end`, and `observation_ts` on **every** quote |
| Tolerance | A quote outside the window is **stored and flagged, never discarded** |

**The window's value is OQ-1 and still open** — §A.5 is *"LOCKED as a rule,
EMPIRICAL as a value"*. Recording the window actually used is the only way the
spike can inform it.

**Optional, and worth it:** a second window (e.g. 09:00–10:00) on a subset of
days. Fares move intraday — MoSPI's own report notes fares vary *"by booking
platform and **time slot**"* — and OQ-1 cannot be answered from one slot. A
second window makes it answerable; skipping it forecloses the question.

## 3. Advance-purchase buckets — §A.3

**T+7, T+15, T+30.** Assignment is by **exact** `lead_time_days`. A quote at 8
days matches no bucket and is **inadmissible** (§A.3) — stored, excluded, never
rounded into a neighbour.

**Also sample T+21.** Not an §A.3 bucket and **not adopted as one**. EG §3.9
places MoSPI's domestic collection at 21 days, and **OQ-A6** asks whether to add
it. §A.3's exactness makes an uncollected T+21 unrecoverable, so collecting it
keeps a registered question answerable at no methodological cost.

## 4. Route, carrier, channel

| | | Why |
|---|---|---|
| Route | **DEL–BOM**, one-way | Densest domestic pair; existence CONFIRMED by two sources |
| Carrier | **IndiGo (6E)** | Only carrier with terms read and a manual carve-out |
| Channel | **AIRLINE_DIRECT** | One channel ⇒ `source_precedence` vacuous ⇒ ordering cannot affect a number |
| Passengers | **1 adult, one-way, Economy** | §A.1 |
| Stops | **Non-stop only** (`stops = 0`) | A one-stop DEL–BOM is a different product |

Full justification and growth order: [`source_registry/collection-frame.md`](../source_registry/collection-frame.md).

## 5. Flight selection within a search — the rule that protects the data

> **Sort by DEPARTURE TIME. Take the earliest eligible flight in each
> departure-hour band 2–6. Never select by price.**

**N = 5** — one per band. §B.2 anchors 3-hour bands at 00:00 IST, so bands 2–6
span **06:00–21:00**. A band with no eligible flight yields no row; that is a
market fact, not a failure.

**Why never by price.** Results default to cheapest-first; taking "the first
five" from a price-sorted list **selects cheap flights**, and does so from a
differently sorted list next week. The index would then measure the selection
rule rather than the market — a bias no downstream test can detect or undo.

**Why bands rather than simply the earliest five** (amended at 2I, ADR-0065).
DEL–BOM carries roughly 15–25 IndiGo non-stops a day, so "the earliest five"
is every flight in the morning bank. `departure_hour_band` is part of the cell
key (§B.2), and it would have been **degenerate for the entire study** — a
dimension of the matched item left unexercised against real data for 30 days.
Banding costs nothing (same N, same burden), spans the commercial day, and keeps
every property that made the old rule safe: deterministic, reproducible, and
never involving price.

Bands 0, 1 and 7 (21:00–06:00) are excluded deliberately: they are
intermittently served, and an intermittently served band churns the matched set
— spending weekly links on the thinnest part of the schedule.

The rule must be identical on every collection day. If it changes, the window is
over.

## 6. Fare class — §B.4

Derived from **entitlements**, never from the marketing label. `fare_family_raw`
is stored verbatim for audit and never used for matching.

**Selection rule:** the cheapest fare **including checked baggage**, applied
consistently. A `0 kg` hand-baggage fare is a **different fare class**, not a
cheaper version of the same one — recording it as `checked_baggage_kg = 0`
classifies it correctly on its own rather than contaminating `STANDARD`.

*AMB-4 is confirmed-as-implemented: `HAND_ONLY` is evaluated first.*

## 7. Fare components — §A.4, PS four-way split

Record `base_fare`, `taxes`, `fees`, `user_development_fee` **where the source
renders them**.

**Unrendered is `None`, never `0`.** A zero asserts the charge does not exist; a
`None` says we could not see it. §A.4 is explicit that *"the index is never
blocked on a breakdown the site does not render"* — the total still enters the
index either way.

**Never estimate a component.** A blank is handled by a declared rule; an
invented one corrupts the index silently.

## 8. Duplicates — §D.4

Deduplicate on `(route, carrier, flight_number, travel_date,
departure_time_local, fare_class, channel, source_id)`.

`route` is in the tuple deliberately — **AMB-3**. Without it, a full-frame
synthetic day collapsed from 2,800 admissible quotes to 140, losing 95% silently.

## 9. Source transitions — §D.8.3

The fare is taken from the highest-ranked source present in **both** `t` and
`t−7`. When the selected source changes between consecutive links, the pair is
flagged `SOURCE_TRANSITION` and excluded for **exactly one link**, then resumes.

With one source per channel this cannot fire. Recorded so the rule is applied
rather than bypassed, and so frequency (**OQ-A9**) becomes measurable the moment
a second source is added.

## 10. Timestamps and identity

- `observation_ts` — the instant the quote was seen, **per quote**, IST.
- `collection_date` — the IST date of the **window** it belongs to, not the
  wall-clock date of the request. A run that crosses midnight keeps one
  `collection_date`.
- `observation_id` — stable and unique. Recommended:
  `{collection_date}-{source_id}-{carrier}{flight_number}-{travel_date}-{fare_class}`.
- `flight_number` — **digits only**. `2045`, never `6E2045`.

## 11. Failure handling — every attempt gets a record

One `CollectionAttempt` per `(source, route, travel_date)` **whether or not it
produced a fare**, classified by `CollectionOutcome`:

| Outcome | Meaning | Coverage denominator |
|---|---|---|
| `SUCCESS` | Quotes parsed | In |
| `NO_FLIGHT` | No service scheduled | **Out** — the only one |
| `STRUCTURAL_MISSING` | Route/flight retired | In → suppression |
| `TECHNICAL_FAILURE` | Ran fine, quote transiently absent | In → carry |
| `SOURCE_UNAVAILABLE` | Down, rate-limited, breaker open | In — **our failure** |
| `PARSER_FAILURE` | Fetched, unextractable | In — **our failure** |
| `CAPTCHA_OR_ANTIBOT_STOP` | Access challenge | In — **our failure, and a stop** |

**A collector failure is never recorded as an absent fare.** Without this record
"no service was scheduled" and "the site blocked us" are the same empty result,
and the §I denominator stays undefined however long collection runs. That is
AMB-8's missing input.

## 12. Retry, rate limiting, stop signals

| | |
|---|---|
| **Retry** | At most **one** retry per attempt, after ≥60 s. Then record the outcome and move on |
| **Never retried** | `CAPTCHA_OR_ANTIBOT_STOP`. **Zero retries.** Back off, log, stop that source for the run |
| **Rate limit** | ≥10 s between requests to one source group. Where a source states a cadence, the stated one wins |
| **Per group, not per source** | §B.6 — two sites sharing inventory hitting the same upstream at "polite" individual rates are not polite to that upstream. Most groups are `independence: UNKNOWN`, so **assume correlation** |
| **Circuit breaker** | Consecutive failures, a rising exclusion rate, or any access challenge opens it. It stays open until a **human** closes it |

> An access challenge is an **observation about the source**, not an obstacle.
> No CAPTCHA solving, no fingerprint evasion, no identity rotation. This does not
> bend for a deadline.

## 13. Raw artifact retention and reproducibility

**Retain the raw artifact for every successful attempt** — the rendered page or
response, content-addressed by SHA-256. §P.3 requires a publication to be re-run
and compared bit for bit; that is only possible if the bytes behind it still
exist. A parser fixed in week 3 can then be re-run over week 1.

Every observation and attempt carries: `run_id`, `collection_date`,
`source_precedence_version`, `basket_version`, `parser_version`,
`collector_version`.

Retention: **raw artifacts ≥ 90 days**; canonical observations and attempts
**indefinitely** — they are the vintage record (§R.3).

## 14. Before Day 1 — the remaining blockers

| # | Blocker | Cleared by |
|---|---|---|
| 1 | **Storage exists** — the schema is defined but nothing persists | Implementing [`storage-design.md`](../src/apix/ingestion/storage-design.md) |
| 2 | **Second collection window decided** (OQ-1) | An owner call: one slot or two |
| 3 | **Retention location agreed** for raw artifacts | An owner call |

**Not blockers for a manual run:** AMB-8 and AMB-9. Neither affects *collection*
— they gate *publication*, and the frame is single-carrier so AMB-9 cannot bind.

## 15. What ends the window

Any of these means the 30 days measured something other than what it claims,
and the window restarts:

- the flight-selection rule changed
- the collection window moved by more than ±30 minutes
- the route, carrier, channel or APW set changed
- more than **2 consecutive days** were missed

**A missed day costs two links**, not one: the index compares `t` against `t−7`,
so skipping the 19th breaks the link for both the 12th and the 26th.
