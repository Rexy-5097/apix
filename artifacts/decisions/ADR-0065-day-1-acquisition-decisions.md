# ADR-0065: The Day-1 acquisition decisions

> **Status:** Accepted | **Date:** 2026-09-12
> **Decider:** @slazyverse, under decision authority delegated by the project owner at Checkpoint 2I
> **Checkpoint:** 2I | **Bears on:** OQ-1, OQ-8, OQ-A6, §A.3, §A.5, §B.2, §B.6, §H.3
> **Supersedes in part:** ADR-0064 (ratified here), `acquisition-protocol.md` §5

---

## Summary of decisions

| # | Question | Decision |
|---|---|---|
| 1 | Acquisition method | **Manual, IndiGo direct.** No source is cleared for automation — now on evidence, not on absence of evidence |
| 2 | Collection window | **ADR-0064 B-minimal, ratified.** Primary 21:00–22:00 daily; diagnostic 09:00–10:00 on 7 days |
| 3 | Frame | **Unchanged.** DEL→BOM, 6E, AIRLINE_DIRECT |
| 4 | N and its selection rule | **N = 5, one flight per departure-hour band 2–6, earliest within each band.** Replaces "first 5 by departure time" |
| 5 | T+21 | **Collected, exploratory only.** Contamination is structurally impossible, not merely forbidden |
| 6 | Storage | **Unchanged.** SQLite + content-addressed artifacts is sufficient |

---

## 1. Acquisition method — manual, and now for a better reason

Checkpoint 2G rated 0 of 14 sources `AUTOMATION_ALLOWED`, but 9 of those were
`AUTOMATION_UNKNOWN` — which is not a finding, it is an absence of one. 2I closed
the four that could change the answer. **All four are now closed on the merits,
and three are closed on grounds stronger than "we did not read the licence."**

### Amadeus Self-Service API — REJECTED on data validity

The dossier (p.11) describes this as the one route to the §A.4 fee
decomposition, and OQ-8 asked whether it covers Indian domestic sectors. The
coverage question turns out not to be the binding one.

- **Test tier:** automation is expressly permitted — it is an API — but *"most of
  the APIs in the test environment use static cached data"* and *"prices aren't
  real."* A cached, non-transactable price cannot be a §A.1 observation
  (*"one displayed, transactable offer"*). Using it would be fabrication with an
  API key attached.
- **Production tier:** real data, but *"a signed contract with an airline
  consolidator is required before production access is granted."*

So the licensed feed fails at priority 1 (scientific validity) in test, and at
priority 2 (compliance) in production, where it becomes a commercial negotiation
with a lead time measured in weeks. **It is not a Day-1 path.** It remains the
strongest *medium-term* path and the only known route to §A.4 components.

### Travelpayouts — REJECTED on data validity *and* independence

Its Data API *"transfers data from the cache based on user search history"*,
retained 2–7 days. Two independent disqualifications:

1. A 2-to-7-day-old cache of what users happened to search is not a price at an
   instant; it is a biased sample of demand. Fails §A.1.
2. It is Aviasales inventory — the same feed reaching the aggregators. Treating
   it as a separate source would assert independence that does not exist, which
   is exactly what §B.6 exists to prevent, and it inflates effective N in the
   direction that flatters the index.

This resolves the registry's open question about its group membership: **it is
not independent of the aggregator channel.**

### Akasa Air — the instructive one

Akasa's `robots.txt` was fetched successfully and is **completely permissive**:

```
User-Agent: *
Sitemap: https://www.akasaair.com/sitemap.xml
Sitemap: https://www.akasaair.com/book-flight-tickets/sitemap_index.xml
```

No `Disallow`. No `Crawl-delay`. On robots.txt alone, Akasa would be the one
automatable carrier.

Its Terms and Conditions say otherwise, and say it more broadly than IndiGo's:

> *"not permitted to copy, replicate, modify, derivative, display, perform,
> create derivative works from, transfer or sell any information obtained from
> the Website, whether in print, visual or electronic form, **for any purpose
> whatsoever**, without the prior written permission of Akasa Air."*

That reaches further than an anti-automation clause: it restricts copying
information from the site in *any* form, and — unlike IndiGo — **carries no
carve-out for ordinary browser use.**

**The lesson is load-bearing for the whole register: a permissive robots.txt
grants nothing.** robots.txt expresses a crawling preference; the Terms are the
binding instrument. Any future source review that rates a source on robots.txt
alone is doing the wrong check.

### IndiGo — automation prohibited, manual expressly carved out

The 2G rating stands, and the scope caveat recorded against it (that the general
Terms of Use, not the loyalty T&Cs, are the governing document) **could not be
resolved**: `goindigo.in` timed out from this host on both
`/robots.txt` and the Terms of Use path, reproducing the 2F failure. A control
fetch of `akasaair.com/robots.txt` succeeded, so this is **specific to
goindigo.in from this host**, not a general network fault.

That is recorded as an unresolved verification item, not as a finding either
way. What is *not* in doubt is the clause actually in hand, which prohibits
automated access while expressly excepting *"standard search engine or internet
browser usage."*

### Decision

**Manual collection, IndiGo direct.** Among every source reviewed, it is the
only one carrying an **affirmative, quoted permission for the collection mode
actually being used**. Every other candidate is prohibited, unknown, or
technically disqualified.

Automating against an `AUTOMATION_UNKNOWN` source would be fabricating
permission. Automating against a `PROHIBITED` one needs no discussion.

---

## 2. Collection window — ADR-0064 ratified, with its arithmetic corrected

**Decision: Option B-minimal, as specified in ADR-0064.** Primary 21:00–22:00
IST daily, feeding the index. Diagnostic 09:00–10:00 IST on study days
1, 4, 7, 10, 13, 16, 19, feeding OQ-1 evidence only.

### Why the alternatives lose

**One window (Option A)** cannot answer OQ-1, and **OQ-1 is unrecoverable after
the fact** — §A.3 assigns by exact lead time, so a time of day not sampled
during the window is gone with the flights and the prices. §A.5 already asserts
that a 03:00 quote and an 18:00 quote are *"two different prices, not two draws
from the same price"*; Option A would leave that assertion unmeasured for the
entire study. MoSPI's own CPI collects airfare *"across different time
windows to ensure representativeness"*, so the national statistical office
treats intraday variation as real enough to sample around.

**Two windows every day (Option B)** doubles a manual burden for 30 consecutive
days. The realistic failure mode is attrition, and **a missed day costs two
weekly links, not one** — the index compares `t` against `t−7`, so a gap at day
19 breaks day 12 and day 26 alike. A design likely to be abandoned in week three
is worse than a smaller one that completes. The marginal evidence from days 8–30
of paired sampling is also low: seven paired days on a +3 stride cover every
weekday exactly once, and if the first seven show material movement the owner
can extend.

### Correction to ADR-0064

ADR-0064 costed the diagnostic window at **21 extra searches**. That was computed
against three searches per day, before T+21 was added to the frame. The correct
figure is **7 days × 4 searches = 28 extra searches**, taking the study from 120
to **148 searches**. The conclusion is unchanged — 23% more effort, not 100% —
but the number in the ADR was wrong and is corrected there.

### Statistical consequence

Only `@primary` runs are index input. The diagnostic window cannot contaminate a
published number, because the separation is structural — a distinct
`CollectionRun` with its own `frame_id` suffix — rather than a flag every
downstream consumer must remember to honour. At study end, the paired
observations give the distribution of `log(fare at 09:00) − log(fare at 21:00)`
over the same (flight, travel_date, fare_class), which is what turns §A.5's
assertion into a measurement.

### Reproducibility consequence

Each run records the window **actually used**, not the one planned. A session
that ran 21:05–21:40 records 21:05–21:40, and `verify()` checks every quote
against its own run's declared bounds. A late quote is stored and flagged, never
discarded or back-dated.

### Effect on the 30-day clock

None. The diagnostic window adds no days; it adds ~28 searches spread over the
first 19.

### On ratification

ADR-0064 was filed `AWAITING_OWNER_RATIFICATION`. It is ratified here on two
grounds: @Rexy-5097 approved PR #9, whose description explicitly asked them to
*"ratify or reject ADR-0064"* with the ADR in the diff; and the project owner
delegated methodology decisions for this checkpoint explicitly.

**This ratifies a sampling design, not a methodology parameter.** OQ-1 — the
*published* window value — remains open and is resolved after the study, from
the evidence the study gathers. No frozen methodology text is touched.

---

## 3. Frame — unchanged

**DEL→BOM · IndiGo (6E) · AIRLINE_DIRECT · one adult · one-way · Economy ·
non-stop only.**

- **DEL–BOM** is the densest domestic pair, route existence CONFIRMED by two
  sources. Density is the point: more daily frequencies means more matched items
  per search and the strongest identity-linking power available anywhere in the
  network.
- **IndiGo** is the largest domestic carrier *and* the only source with manual
  permission in hand. Those two facts pointing the same way is why this frame is
  not a compromise.
- **One channel** makes `source_precedence` vacuous, so ordering cannot affect a
  number and AMB-10 cannot bite during the study.

### Why not expand

**A second route** would let the Young/Modified Laspeyres layer run on real data
rather than synthetic — genuinely attractive, and the DGCA city-pair file
recovered at 2F means route weights are now computable. It is still rejected:
it doubles the daily burden, and attrition is the single largest threat to the
study. The aggregation layer is already invariant-tested; what real data
principally buys is at the **elementary** level — matching, identity stability,
availability, fare-class derivation — all of which is within-route. A completed
one-route study beats a two-route study abandoned at day 18, which yields
nothing at all.

**A second carrier** would produce data the index cannot aggregate: AMB-9 is
open, there is no ratified `CarrierAllocation`, and `within_route_weights`
raises rather than defaulting to a uniform split. Collecting it would be
collecting for a drawer.

Expansion is a post-study decision, taken on measured stability rather than
estimated.

---

## 4. N and the selection rule — changed

**Previous rule (protocol §5):** *take the first N flights by departure time,
N = 5.*

**New rule: N = 5 — one flight per departure-hour band, bands 2 through 6,
taking the earliest departure within each band.**

§B.2 anchors 3-hour bands at 00:00 IST, so bands 2–6 span **06:00 to 21:00**.

### Why the old rule was wrong

It is price-blind, which is the property that matters most and which the new rule
keeps. But "the earliest 5 on a dense route" is **every flight in the morning
bank**. DEL–BOM runs roughly 15–25 IndiGo non-stops a day; the earliest five all
land in bands 2–3.

Two consequences, one of which is serious:

1. **`departure_hour_band` is in the cell key (§B.2) and would have been
   degenerate for the entire study.** A dimension of the matched item would go
   unexercised — and untested against real data — for 30 days.
2. The sample would represent early-morning DEL–BOM, which is business-heavy and
   priced differently, rather than DEL–BOM. This does not bias the *change* a
   matched-model index measures, so it is not fatal, but it narrows what the
   study can support a claim about.

### Why the new rule is better at identical cost

Same N, same 20 rows per day, same burden — and it spans the commercial day,
exercises the band dimension, and keeps every property that made the old rule
safe: deterministic, reproducible, and **never involving price**.

Bands 0, 1 and 7 (21:00–06:00) are excluded deliberately. They are intermittently
served, and an intermittently served band churns the matched set — which costs
weekly links for evidence about the thinnest part of the schedule. A band with no
eligible flight is a market fact recorded on the attempt, not a collector
failure.

### Consequence for the protocol

`acquisition-protocol.md` §5 and `manual-collection-procedure.md` §5 are amended,
and `protocol_version` becomes `acquisition-protocol-2I`. **This change is made
before Day 1 and may never be made during the window** — protocol §15 is explicit
that changing the selection rule mid-study ends it.

---

## 5. T+21 — exploratory, and structurally quarantined

**Decision: collect T+21 throughout the study. Do not add it to the production
APW set.**

The production set is §A.3's `{1, 3, 7, 15, 30, 45, 60}`, frozen. The frame
samples T+7, T+15, T+30 from it, plus T+21 outside it.

**Contamination is impossible by construction, not by discipline.** §A.3 assigns
by *exact* lead time, so `APWBucket.from_lead_time(21)` returns `None`, the
observation is inadmissible, and it cannot reach a Jevons relative. The Day-1
smoke run demonstrates the guarantee rather than asserting it: four travel dates
loaded, `apw_buckets: [7, 15, 30]` — T+21 stored and absent from the index path.

The reason to collect it is OQ-A6. MoSPI's Expert Group places domestic airfare
collection at **21 days**, so whether APIx should adopt T+21 is a live question,
and §A.3's exactness makes an uncollected T+21 permanently unrecoverable. One
extra search per day buys a registered question a real answer.

---

## 6. Storage — unchanged, and deliberately small

SQLite plus a content-addressed artifact directory satisfies every Day-1
requirement: raw evidence preserved and hash-verified on read; provenance from
run to attempt to observation to artifact; reproducibility anchored by the
version vector on each run; attempt logging that makes missingness measurable;
canonical observations; run identification. `verify()` checks three independent
invariants and 43 tests cover it.

**No new infrastructure.** PostgreSQL can replace the file later without
changing a call site, because the calls are the contract. Adding it now would be
operational cost bought with nothing.

One **operational** gap, which is a procedure line and not infrastructure:
`data/collection/` is gitignored, so a disk failure at day 25 destroys an
irreplaceable study. The procedure now requires a copy of the store directory
after each run.

---

## Consequences

**Good**

- Every acquisition decision now rests on evidence obtained and quoted, not on
  an unfilled cell in the register.
- OQ-8 is closed for both licensed feeds, on validity grounds that no amount of
  licence-reading would change.
- The band-stratified rule exercises a cell-key dimension that would otherwise
  have gone untested for the whole study, at zero extra cost.
- Nothing in the frozen methodology is amended.

**Bad, and accepted**

- Manual collection caps the study at one route and one carrier, so the
  aggregation layer stays synthetic-tested for now.
- The §A.4 fee decomposition depends on what IndiGo renders. The only known
  source that guarantees it is Amadeus production, which is weeks away.
- IndiGo's general Terms of Use remain unread, because the host cannot reach
  them. The clause in hand is from the loyalty agreement.

**Neutral**

- `protocol_version` advances to `acquisition-protocol-2I`, which is recorded per
  run, so runs under different protocol versions are distinguishable rather than
  silently pooled.

## References

- [`ADR-0064`](ADR-0064-collection-window-design.md) — window design, ratified here
- [`../../compliance/acquisition-protocol.md`](../../compliance/acquisition-protocol.md) §5, §15
- [`../../compliance/day-1-contract.md`](../../compliance/day-1-contract.md) — the frozen values
- [`../../source_registry/registry.yaml`](../../source_registry/registry.yaml) — updated gates and evidence
- `docs/methodology/apix_formula_spec_v1.md` §A.1, §A.3, §A.5, §B.2, §B.6, §H.3
- Amadeus Self-Service environment documentation; Travelpayouts Aviasales Data API
  documentation; Akasa Air `robots.txt` and Terms and Conditions — all retrieved 2026-09-12
