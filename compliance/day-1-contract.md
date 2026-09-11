# The Day-1 collection contract — FROZEN

> **Status:** FROZEN · **Frozen:** 2026-09-12 · **Checkpoint:** 2I
> **Authority:** [ADR-0065](../artifacts/decisions/ADR-0065-day-1-acquisition-decisions.md), [ADR-0064](../artifacts/decisions/ADR-0064-collection-window-design.md)
> **protocol_version:** `acquisition-protocol-2I`
> **Owner:** [@slazyverse](https://github.com/slazyverse)

Every value below is fixed for the whole 30-day window. **Changing any of them
during the study ends the window and restarts the study**, because day 1 and day
20 would no longer be measuring the same thing (acquisition protocol §15).

---

## The contract

| Parameter | Frozen value | Authority |
|---|---|---|
| **Acquisition method** | Manual, by a person, in an ordinary browser. No script, no agent, no headless browser | ADR-0065 §1 |
| **Source** | `indigo-direct` — goindigo.in | ADR-0065 §1 |
| **Route** | **DEL → BOM**, one-way, exact airports | ADR-0065 §3 |
| **Carrier** | **IndiGo (6E)** only; marketed *and* operated | ADR-0065 §3 |
| **Channel** | `AIRLINE_DIRECT` | ADR-0065 §3 |
| **Passengers** | 1 adult, Economy, Regular fare (no concession) | §A.1 |
| **Stops** | Non-stop only (`stops = 0`) | frame |
| **APW — index** | **T+7, T+15, T+30** (exact lead time) | §A.3 |
| **APW — exploratory** | **T+21** — collected, never admissible | ADR-0065 §5 |
| **Travel-date selection** | `collection_date + {7, 15, 21, 30}` calendar days. Clicked in the calendar, never defaulted | §A.3 |
| **Flight-selection rule** | **One flight per departure-hour band, bands 2–6, earliest departure within each band.** Never by price | ADR-0065 §4 |
| **N** | **5** (one per band; a band with no eligible flight yields no row) | ADR-0065 §4 |
| **Primary window** | **21:00–22:00 IST**, every collection day. Feeds the index | ADR-0064 |
| **Diagnostic window** | **09:00–10:00 IST** on study days 1, 4, 7, 10, 13, 16, 19. OQ-1 evidence only | ADR-0064 |
| **Fare family** | The cheapest fare **including checked baggage**, applied identically every time. `fare_family_raw` recorded verbatim, never used for matching | §B.4 |
| **Fare decomposition** | `base_fare`, `taxes`, `fees`, `user_development_fee` recorded **only where displayed**. Blank stays blank | §A.4 |
| **Total** | `payable_fare` — all-inclusive, 1 adult. Required for every AVAILABLE flight | §A.4 |
| **Failure taxonomy** | The seven `CollectionOutcome` values. Every search gets a row | §H.1 |
| **Raw artifacts** | One screenshot per search, including failures. Named `{YYYYMMDD}-{window}-{travel_date}.png`. Retained 5 years, never edited | §P.3 |
| **Storage** | `data/collection/` — SQLite + content-addressed artifacts, loaded by `tools/collection/load_manual.py` | ADR-0065 §6 |
| **Collector environment** | Same browser, same machine, same locale/currency, **not signed in**, no VPN, INR | ADR-0065 §1 |
| **`frame_id`** | `DEL-BOM/6E/AIRLINE_DIRECT/T7-T15-T21-T30@primary` (or `@diagnostic-oq1`) | ADR-0064 |
| **`basket_version`** | `2026-Q3` | — |
| **`source_precedence_version`** | `spike-single-source-v1` — vacuous with one source per channel | 2G |
| **`methodology_version`** | `2.1` | frozen |
| **`protocol_version`** | `acquisition-protocol-2I` | ADR-0065 §4 |

---

## The departure-hour bands

§B.2 anchors 3-hour bands at 00:00 IST. Take **the earliest eligible flight in
each of bands 2–6**:

| Band | Departure window | Take |
|---|---|---|
| 0 | 00:00–02:59 | — not collected |
| 1 | 03:00–05:59 | — not collected |
| **2** | **06:00–08:59** | earliest eligible |
| **3** | **09:00–11:59** | earliest eligible |
| **4** | **12:00–14:59** | earliest eligible |
| **5** | **15:00–17:59** | earliest eligible |
| **6** | **18:00–20:59** | earliest eligible |
| 7 | 21:00–23:59 | — not collected |

A band with no eligible flight simply yields no row. That is a market fact, not
a collector failure, and it needs no `CollectionOutcome` of its own — the attempt
covers the whole search.

**Sort the results by departure time before selecting.** IndiGo defaults to
cheapest-first; selecting from a price-sorted list is how an index quietly starts
measuring its own selection rule.

---

## What is deliberately NOT in this contract

| Not fixed | Why |
|---|---|
| The **published** collection window | That is **OQ-1**, still open. This contract fixes what the study *samples*, which is what makes OQ-1 answerable |
| `expected_cells` / the coverage denominator | **AMB-8**, open. No table enumerates it, because filling it from observed cells is circular |
| Carrier allocation weights | **AMB-9**, open. Moot at one carrier, and `within_route_weights` raises rather than assuming uniform |
| Whether T+21 joins production APW | **OQ-A6**, answered *after* the study from the data it collects |
| Route weights | Computable from the DGCA city-pair file, but moot at one route |
| Any index value | Publication prerequisites are not satisfiable from one route and one carrier |

---

## Daily obligations

1. Collect in the **primary** window, every day, without gaps. A missed day costs
   **two** weekly links, because the index compares `t` against `t−7`.
2. Load the same evening: the loader validates whole-or-nothing, and a defect
   found on day 1 is cheap while a defect found on day 20 is not.
3. Read the exit code. `0` clean · `2` integrity problems — **investigate before
   the next run**.
4. **Copy `data/collection/` somewhere else after each run.** It is gitignored
   and irreplaceable; a disk failure at day 25 destroys the study.

---

## What ends the window

Any of these restarts the 30 days:

- A change to the collection window, the selection rule, N, the fare-family rule,
  the frame, or the collector environment.
- A missed collection day.
- Loading a day whose integrity problems were not resolved before the next run.

And one that stops collection rather than restarting it:

- **`CAPTCHA_OR_ANTIBOT_STOP`.** Stop for that source, that day. Do not solve it,
  refresh, switch browser, switch network or use a VPN. Screenshot it, record it,
  report it. If it repeats, the source leaves the register — an acceptable
  outcome, and far better than the alternative.

---

## References

- [`manual-collection-procedure.md`](manual-collection-procedure.md) — how to execute this
- [`acquisition-protocol.md`](acquisition-protocol.md) — the rules and their justification
- [`ADR-0065`](../artifacts/decisions/ADR-0065-day-1-acquisition-decisions.md) — why each value
- [`ADR-0064`](../artifacts/decisions/ADR-0064-collection-window-design.md) — window design
