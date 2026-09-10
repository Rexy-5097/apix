# External reference data — feasibility audit

**Owner:** [@Rexy-5097](https://github.com/Rexy-5097) · **Checkpoint:** 2F · **Date:** 2026-09-10
**Bears on:** AMB-8, AMB-9, OQ-4, OQ-8 · **Register:** [`source_registry/registry.yaml`](../../source_registry/registry.yaml)

APIx needs three things no airfare quote contains: **how much traffic a route
carries** (route weights), **how a route's traffic splits across carriers**
(within-route weights), and **which cells were supposed to exist** (the coverage
denominator). This audits whether they are obtainable.

> **Nothing here resolves AMB-8 or AMB-9.** It establishes what could resolve
> them, and what would still be missing.

## The finding

**One source would unblock both open questions, and it is not a fare source.**

The DGCA-approved seasonal flight schedule — if it carries per-flight
days-of-operation in a machine-readable form — supplies AMB-8's expected-cell
frame *and* AMB-9's capacity fallback from the same file. Its availability is the
single most consequential unverified fact in this checkpoint, and one HTTP 403
stands between us and knowing.

The second finding is negative and load-bearing: **DGCA publishes city-pair
traffic and carrier traffic as two separate, uncrossed tables.** The
passenger-share route to AMB-9 does not exist in domestic data.

---

## A. DGCA city-pair domestic passenger traffic — for `w[r]` (OQ-4)

| | |
|---|---|
| **Available?** | **Yes** — published |
| **Granularity** | city pair × month; passengers, freight, mail |
| **Carrier dimension** | **Absent** |
| **Frequency** | Monthly |
| **Historical depth** | mid-2015 onwards |
| **Machine readable** | XLSX at source; CSV via third-party mirrors |
| **Usable for AMB-8?** | No |
| **Usable for AMB-9?** | **No — see below** |
| **Resolves** | **OQ-4 appears satisfiable** |

Spec G.2 records route weights as **EMPIRICAL / OPEN — OQ-4**, with the concern
that city-pair volumes *"may not be openly downloadable"*. On this evidence they
are. The declared capacity fallback may not be needed for `w[r]`.

**Limitation, and it is decisive for AMB-9.** The city-pair table has **no
carrier column**. City-pair and carrier are published as two separate series —
corroborated by an independent DGCA mirror whose README describes the domestic
tables as *"Monthly city-pair wise passenger, freight and mail traffic"* and,
separately, *"Monthly carrier-pair wise… traffic"*. The one **airline-wise ×
city-pair** resource located on data.gov.in is **International**, not domestic.

`w[r]` needs the city-pair table alone, so OQ-4 is unaffected by this.

**Still to verify.** The DGCA portal page was reached but rendered a navigation
shell; the structure above rests on a mirror's README and search metadata, not on
the primary file. **Download the primary XLSX and confirm the columns** before
this is treated as settled — including whether "city pair" is directional
(`DEL-BOM` ≠ `BOM-DEL`, as the APIx notation requires) or symmetric.

## B. DGCA carrier-wise domestic traffic — context only

Monthly, carrier × national totals, no route dimension.

**Not usable for AMB-9.** A national carrier share is not a within-route share.
Applying one as the other assumes every carrier has an identical route mix, which
is false by inspection for a network carrier versus a regional operator — and
would silently import that error into every route in the basket.

## C. DGCA approved flight schedule — for AMB-8, and for AMB-9's fallback

| | |
|---|---|
| **Available?** | **Appears published — not verified** |
| **Claimed granularity** | flight number · airline operator · aircraft type · operating frequency (days of operation) · origin · destination · scheduled departure and arrival times · effective date range |
| **Frequency** | Two seasons per year — Summer and Winter |
| **Machine readable** | **Not verified** |
| **Access** | `data.gov.in/resource/flight-schedule` returned **HTTP 403** to this audit |
| **Usable for AMB-8?** | **Yes, if the claimed granularity holds** |
| **Usable for AMB-9?** | **Yes, as the §G.2-pattern capacity fallback** |

DGCA approves and releases seasonal schedules. The Summer 2026 schedule
(29 Mar – 24 Oct 2026) covers **nine** scheduled domestic operators — Air India,
Air India Express, IndiGo, Akasa Air, SpiceJet, Alliance Air, FLY91, Star Air,
IndiaOne Air — at 23,049 weekly flights.

**Note the nine.** The dossier's frame names **five** carriers. Four scheduled
operators are outside it. On thin and regional routes the excluded four may be
most of the service, which bears directly on OQ-A1's *"carrier-specific cells too
thin on real routes"* — the dossier's own **dominant risk**.

**Why the days-of-operation field is the whole question.** A cell key is
`route × carrier × day_of_week × apw × fare_class × channel`. A schedule carrying
per-flight days of operation states which `(route, carrier, day_of_week)`
combinations *have scheduled service* — which is precisely §H.1's *"No flight —
no service scheduled on that weekday/slot; **cell not expected; excluded from
denominators of coverage**"*. That is AMB-8's missing denominator.

**Still to verify, in priority order:**

1. **Is days-of-operation per flight, or only an aggregate weekly count?** Press
   coverage reports totals (23,049 weekly flights). A total is useless here. A
   per-flight frequency field is everything.
2. Format and licence. The 403 blocked both.
3. Update cadence, and **whether mid-season revisions are published**. The Winter
   2025–26 schedule was curtailed mid-season after operational disruption at one
   carrier, so a schedule fetched once is a snapshot, not a standing truth — and
   an expected-cell frame built from a stale schedule would count cells that were
   withdrawn.
4. Whether `aircraft type` is populated, which decides §D below.

**The 403 was recorded and not worked around.** Retrieval should be retried from
an un-intercepted network, or the file obtained from DGCA's own portal path.

## D. Scheduled seat capacity — the declared fallback

Spec G.2 already declares it, for route weights:

> **Declared fallback (LOCKED):** scheduled **seat capacity** by city pair,
> derived from published airline schedules — a proxy for passenger volume **with
> a stated and testable bias**.

Capacity is not published as a table. It is **constructed**: schedule frequency
× seats per aircraft type. So it needs (a) §C's schedule with `aircraft_type`
populated, and (b) a seat-count mapping per aircraft type, which is a separate
lookup this audit did not attempt.

**Its significance is that it carries the carrier dimension the traffic tables
lack.** Frequency and aircraft type are per flight, and every flight has an
operator — so capacity share *within a route, by carrier* is constructible from
the same file that answers AMB-8, where passenger share is not.

Spec G.2's own words apply unchanged: a proxy **with a stated and testable
bias**. Capacity is not traffic. A carrier flying wide-bodies at low load factors
would be over-weighted relative to one flying full narrow-bodies. The bias
direction is stateable and the magnitude is measurable against the national
carrier totals in §B — which is exactly the *"stated and testable"* the spec asks
for, and it is available.

## E. Booking lead-time distribution — OQ-7

**Not found, and not sought in depth.** OQ-7 remains open, §G.4's equal APW
weights stand as the declared v1 choice with a sensitivity band, and no curve may
be invented.

## F. Licensed feeds — OQ-8

**Not verified.** Neither Amadeus Self-Service nor Travelpayouts had terms,
Indian domestic sector coverage or field availability confirmed.

This matters beyond compliance. The dossier describes Channel A as *"Structured
fares with base / tax / fee **already decomposed**"* — and if that holds it is
**the only known route to the spec A.4 decomposition**, which no portal is known
to render. §A.4 requires that split to be *"stored and reported"* where available.

Spec H.3 bounds the use: `AUTHORIZED_FEED` is never silently substituted for a
`LIVE_SCRAPE` observation being claimed. A licensed feed can supply the fee
decomposition as its own observation; it cannot quietly stand in for a portal
quote.

---

## Summary

| Source | Available | Granularity | AMB-8 | AMB-9 | Main limitation |
|---|---|---|---|---|---|
| **DGCA city-pair traffic** | **Yes** | city pair × month | No | **No** | **No carrier column.** Columns unconfirmed against the primary file |
| **DGCA carrier traffic** | Yes | carrier × month, national | No | **No** | No route dimension. National ≠ within-route |
| **DGCA flight schedule** | **Appears yes** | flight × days of operation, *claimed* | **Yes** | **Yes**, via capacity | **403.** Per-flight frequency unconfirmed; mid-season revisions unknown |
| **Scheduled capacity** | Constructible | carrier × route × weekday | — | **Yes** | Not a published table. Needs schedule + aircraft seat map. Proxy with a stated bias |
| **Lead-time distribution** | **No** | — | — | — | OQ-7 stays open |
| **Licensed feeds** | Unverified | — | — | — | OQ-8. May be the only source of the §A.4 fee split |

**Net.** OQ-4 looks satisfiable. AMB-9's passenger-share route is **closed** by
the absence of a carrier × city-pair domestic cross-tab; its capacity route is
**open but unverified**. AMB-8's frame is **obtainable in principle** from the
same file — and still needs one thing no external source can supply, which is the
attempt record in
[`compliance/collection-control-contract.md`](../../compliance/collection-control-contract.md)
§C-6.
