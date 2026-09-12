# APIx production acquisition strategy

> **Checkpoint:** 2K · **Date:** 2026-09-12 · **Owner:** [@slazyverse](https://github.com/slazyverse)
> **Status:** Strategy. **No code changes. Manual bulk collection is stopped.**
> **Methodology:** unchanged — v2.1 frozen. Departure bands unchanged. Fare-family rule unchanged.

---

## The finding that determines everything below

Every structured airfare source — NDC direct, NDC aggregator, GDS — gates access
on **being an accredited seller of travel**, not on technical capability.

> AirGateway *"typically requires an IATA, TIDS or IATAN number to provide access,
> **as airline NDC programmes are linked to agency identity**."*

APIx is a statistical instrument, not a travel seller. That is not a gap in our
engineering; it is a category mismatch between what NDC is for and what APIx is.

It follows that **no structured source can be unblocked by writing code.** Each
requires a signature, an accreditation, or a commercial contract. The engineering
question ("can we call the API?") is settled and uninteresting; the real question
is which agreement the project should pursue, and that is an owner decision.

A second finding cuts across the first, and it is the one to read carefully:

> **A publicly documented API with a free sandbox is not an authorized source.**
> Air India's NDC portal is public, documented and registerable — and its terms
> restrict use to *"testing our API products in a trial environment… and for no
> other purpose."*

---

## 1. Source matrix

`automation_gate` and `data_admissibility` follow the registry's two-gate model:
both must clear. `technical_access` is deliberately **not** a gate — that a client
*can* connect says nothing about whether it may.

| source | channel | automation_gate | data_admissibility | technical_access | coverage | fare_detail | licensing_status | credentials_required | production_ready | APIX_recommendation |
|---|---|---|---|---|---|---|---|---|---|---|
| **IndiGo NDC** | NDC_DIRECT | **UNKNOWN** | **ADMISSIBLE** *(real priced offers)* | Portal reachable; API unverified | 6E network | NDC-structured, richest available | **Terms gated behind registration — unread** | API key + almost certainly a distribution agreement | **NO** | **PURSUE FIRST.** Highest value; needs a human to register and read the licence |
| **Air India NDC** | NDC_DIRECT | **PROHIBITED** *(for the portal)* | **ADMISSIBLE** | Portal times out from this host | AI network, NDC 21.3 | NDC-structured | **READ — decisive.** Trial-only purpose; §7(m),(p) bar automated *and manual* extraction without written permission; §8: *"bound by separate agreements"* | Separate signed agreement | **NO** | **PURSUE SECOND** via `ndcdistribution@airindia.com`. Terms are clear, so the ask is clean |
| **Akasa Air** | AIRLINE_DIRECT | **PROHIBITED** | ADMISSIBLE | Site reachable | QP network | Website only | Terms bar copying *"in print, visual or electronic form, for any purpose whatsoever"*, **no browser carve-out** | — | **NO** | **EXCLUDE.** No distribution API found; terms are the strictest audited |
| **SpiceJet** | AIRLINE_DIRECT | **UNKNOWN** | ADMISSIBLE | Site reachable; **robots permits search paths** | SG network | Website only | **Terms unread** | — | **NO** | **AUDIT.** Best remaining manual candidate after IndiGo — read the terms |
| **Air India Express** | AIRLINE_DIRECT | **PROHIBITED** (2G) | ADMISSIBLE | robots intermittent | IX network | Website only | Prohibited per 2G | — | **NO** | **EXCLUDE** unless folded into an Air India agreement |
| **Amadeus Self-Service** | LICENSED_FEED | **ALLOWED** | **INADMISSIBLE** *(test tier)* | Excellent | Global GDS subset | Decomposed | Test tier open; production needs *"a signed contract with an airline consolidator"* | API key; consolidator contract for production | **NO** | **PURSUE THIRD.** Only path where the *data* question is already answered — production is admissible |
| **Amadeus + IndiGo NDC** | LICENSED_FEED | UNKNOWN | **ADMISSIBLE** | — | 6E via Amadeus Travel Platform | NDC-structured | Requires Amadeus seller agreement | Seller agreement | **NO** | **STRONG OPTION** — IndiGo NDC is live on Amadeus; one contract, two problems solved |
| **Travelpayouts** | LICENSED_FEED | ALLOWED | **INADMISSIBLE** | Excellent | Aviasales cache | Total only | Open | API key | **NO** | **EXCLUDE.** 2–7-day cache of user searches; also fails §B.6 independence |
| **Duffel** | NDC_AGGREGATOR | UNKNOWN | **ADMISSIBLE** | Sandbox public | Holds **own IATA accreditation**, settles for agencies | NDC-structured | Commercial agreement | Agreement; Duffel's own IATA covers settlement | **NO** | **EVALUATE.** Lowest accreditation burden of the aggregators |
| **AirGateway / Verteil** | NDC_AGGREGATOR | UNKNOWN | **ADMISSIBLE** | Sandbox public | Multi-carrier NDC | NDC-structured | **Requires IATA / TIDS / IATAN number** | Agency identity | **NO** | **EVALUATE** only if APIx obtains a TIDS |
| **Sabre / Travelport** | GDS | UNKNOWN | ADMISSIBLE | — | Broad | GDS-structured | Agency accreditation + contract | Accreditation | **NO** | **DEFER.** Heaviest onboarding, no advantage over Amadeus here |
| **MakeMyTrip / Yatra** | AGGREGATOR | **UNKNOWN** | ADMISSIBLE | **Host resets connections** | Multi-carrier | Website only | Unread | — | **NO** | **EXCLUDE** for now |
| **EaseMyTrip / Cleartrip / Ixigo / Goibibo** | AGGREGATOR | **PROHIBITED** *(robots)* | ADMISSIBLE | Reachable | Multi-carrier | Website only | robots disallows flight search | — | **NO** | **EXCLUDE** |
| **Airline tariff sheets** | DECLARED_TARIFF | UNKNOWN | **INADMISSIBLE as observation** | Monthly PDFs | 4,729 6E routes | Fare *bands* | Public regulatory publication | — | n/a | **KEEP as envelope.** A declared category is not a transacted price |
| **eSankhyiki CPI** | REFERENCE | **ALLOWED** | **ADMISSIBLE as benchmark** | Excellent | All-India monthly | Index only | Open government data | None | **YES** | **AUTOMATE NOW.** Validation only — never an index input |
| **DGCA city-pair traffic** | REFERENCE | ALLOWED | ADMISSIBLE as **weights** | Obtained (66,453 rows) | All domestic pairs | n/a | Public | None | **YES** | **USE** for route weights (§G) |
| **IndiGo browser (manual)** | AIRLINE_DIRECT | **PROHIBITED** for automation; **PERMITTED** manual | **ADMISSIBLE** | Unreachable from CI host; fine for a person | DEL–BOM frame | **8-line breakdown, reconciles exactly** | Browser carve-out quoted | None | **YES (human)** | **RETAIN as fallback + validation channel** |

### Per-source detail against A–M

Rather than repeat thirteen columns thirteen times, the dimensions that actually
separate these sources:

**D. Coverage.** NDC direct covers one carrier each. Aggregators and GDS cover
many but only those carriers who have signed with them — and Indian LCC content
has historically been thinner in GDS than full-service content. **No single
structured source covers all five PS-named carriers.** A multi-carrier index will
need either several agreements or one aggregator with verified Indian coverage,
and that verification is itself an owner-gated task.

**E. Fare-family availability.** NDC returns fare families as structured
`OfferItem`s with explicit service definitions — strictly better than parsing
"Saver fare" off a page, and it removes the entire class of human misread that
[the procedure flags as its known limitation](../../compliance/manual-collection-procedure.md).

**F. Fare-component availability.** The manual channel already delivers this and
we now have proof: IndiGo's web breakdown itemises **eight** lines that reconcile
to the total exactly. NDC would deliver the same or better as structured tax/fee
codes. **This retires the assumption that Amadeus production was the only route
to §A.4 decomposition.**

**G. Baggage / H. Flight metadata.** NDC carries both as structured fields. The
web channel carries both as text requiring interpretation.

**I. Timestamp/freshness.** NDC shopping responses are live and quotable at the
instant of request — a genuine §A.1 offer. This is the dimension on which every
*cached* feed fails, and it is not recoverable by any amount of engineering.

**J–L. Licensing, authentication, production access.** The common shape: public
docs → free sandbox → **contract wall** → production. Every structured source sits
behind that wall. Section 8 lists each wall precisely.

**M. APIX suitability.** Ranked in section 2.

---

## 2. Recommended acquisition hierarchy

```
TIER 0   REFERENCE & VALIDATION                      ← automate immediately
         eSankhyiki CPI · DGCA city-pair traffic
         No credentials. No contract. Not index input.

TIER 1   AUTHORIZED STRUCTURED  (target state)       ← owner action required
         1a  IndiGo NDC via Amadeus Travel Platform   ← best single move
         1b  IndiGo NDC direct
         1c  Air India NDC direct
         1d  NDC aggregator (Duffel first)
         All ADMISSIBLE. All contract-gated. None unblockable by code.

TIER 2   LICENSED FEED (production tier)             ← owner action required
         Amadeus Self-Service production
         Admissible; needs an airline-consolidator contract.

TIER 3   MANUAL BROWSER  (fallback + validation)     ← available today
         IndiGo direct, DEL-BOM, per the frozen contract.
         The ONLY channel currently both permitted and admissible.

EXCLUDED  Cached feeds (Amadeus test, Travelpayouts) - inadmissible at any price
          robots-disallowed OTAs - prohibited
          Akasa - terms bar copying in any form
          Declared tariff sheets - envelope only, never an observation
```

**The single highest-value move is 1a.** IndiGo's NDC content is already live on
the Amadeus Travel Platform, so one Amadeus seller agreement plausibly delivers
both the largest domestic carrier *and* a production-tier licensed feed — turning
two blockers into one negotiation.

**Tier 3 is retained deliberately, not merely tolerated.** Even after Tier 1
lands, the manual channel is the independent check on it: a structured feed can
drift, mis-map a fare family, or quietly serve stale cache, and the only way to
catch that is a human reading the same fare off the public website. Spec §H.3
already forbids silently substituting an `AUTHORIZED_FEED` observation for a
`LIVE_SCRAPE` one, which is exactly this concern written into the methodology.

---

## 3. Canonical observation schema

**Design rule: the statistics layer must not be able to tell where an observation
came from.** Channel-specific detail lives in provenance; the fields the index
reads are identical regardless of source. Nothing below changes the methodology —
these are additive provenance and evidence fields.

### What already works unchanged

`Observation` is largely channel-agnostic today. `origin`, `destination`,
`travel_date`, `departure_time_local`, `carrier`, `flight_number`, `stops`,
`duration_minutes`, `fare_family_raw`, `entitlements`, `payable_fare`,
`availability`, `channel`, `source_id`, `source_group` mean the same thing whether
a person read them or an NDC response carried them. `source_type` already
distinguishes `LIVE_SCRAPE` / `AUTHORIZED_FEED` / `PUBLIC_DATASET` /
`DECLARED_TARIFF`, and `fare_class` is derived from entitlements, never from a
label — which is exactly what makes NDC and web observations comparable.

### Three additions, all additive

**(a) `AcquisitionMode`** — how the bytes were obtained, distinct from `channel`
(market position) and `source_type` (authority):

```
MANUAL_BROWSER · NDC_API · GDS_API · LICENSED_FEED_API · PUBLIC_DATASET_API
```

Needed because the evidence artifact differs by mode — a screenshot versus a
request/response pair — and because §H.3's no-substitution rule needs a field to
test.

**(b) `FareComponent` — the lossy-roll-up fix.** The current four-way breakdown
cannot hold what sources actually render. IndiGo's web panel shows **eight**
lines; NDC carries structured tax/fee codes. Squashing eight into four discards
evidence that only the screenshot preserves.

```
FareComponent:
    label_raw        str            verbatim from the source
    amount           Decimal
    canonical        ComponentClass  BASE | TAX | FEE | UDF | UNCLASSIFIED
    code             str | None      NDC/ATPCO tax code where given
```

`FareBreakdown` keeps its four canonical fields **exactly as they are** — the
methodology reads those and nothing changes — and gains
`components: tuple[FareComponent, ...]` as the faithful record. The roll-up
becomes derivable from and checkable against the components.

*Worked against real evidence — IndiGo 6E 6218, Lite fare, ₹6,357:*

| label_raw | amount | canonical |
|---|---|---|
| Regular Fare | 4,900 | BASE |
| Cute Charge | 50 | FEE |
| Regional Connectivity Charge | 50 | FEE |
| Fuel Charge | 600 | FEE |
| Aviation Security Fee | 236 | FEE |
| User Development fee | 152 | UDF |
| Arrival User Development Fee | 89 | UDF |
| GST for Delhi | 280 | TAX |

Rolls up to base 4,900 · fees 936 · UDF 241 · tax 280 = **6,357 ✓ exact**.

> **REGISTERED AMBIGUITY — AMB-11.** §A.4's four-way split does not anticipate a
> *second* User Development Fee (arrival as well as departure). Both lines are
> literally UDF, so summing them is more faithful than discarding one into a
> generic bucket — but the spec does not say so. Raised for @Rexy-5097; **not
> treated as settled.** The component list makes the decision reversible either
> way, which is the main reason to add it now rather than later.

**(c) `AcquisitionProvenance`** — one object, mode-appropriate contents:

```
acquisition_mode      AcquisitionMode
artifact_sha256       str | None     screenshot (manual) or response body (API)
request_sha256        str | None     API only — the request that produced it
offer_id              str | None     NDC OfferID / OfferItemID
response_ts           datetime       when the source produced it
api_version           str | None     e.g. "NDC 21.3"
```

`offer_id` matters more than it looks: it makes an NDC observation traceable back
to a specific quotable offer, which is the API-channel equivalent of a screenshot
and what makes §P.3 bit-for-bit replay possible without one.

### What must NOT change

Cell key, fare-class derivation, APW assignment by exact lead time, departure-band
definitions, the duplicate tuple, Jevons/Young-Laspeyres, TPD. **A new channel is
a new way to fill the same schema, never a reason to alter it.** If a source
cannot populate these fields, that source is inadmissible — the schema does not
bend to accommodate it.

---

## 4. Proposed 30-day sampling design

**Production APWs (frozen, §A.3): T+1, T+3, T+7, T+15, T+30, T+45, T+60.**
**T+21 remains exploratory** — it matches no bucket, so `from_lead_time(21)`
returns `None` and it is structurally inadmissible. Collected for OQ-A6 only.

### An arithmetic constraint worth stating before anyone designs around it

```
{1, 3, 7, 15, 30, 45, 60}  mod 7  =  {1, 3, 0, 1, 2, 3, 4}   → 5 distinct offsets
```

On any single collection date the seven buckets land on only **five distinct
weekdays**. Because day-of-week is part of the cell key, **no single date can
observe all seven weekly chains.** Over 30 consecutive dates every weekday is
covered, but only because the collection date itself advances — which is another
reason a missed day is expensive and why consecutiveness is not optional.

### Frame A — manual, executable today

| | |
|---|---|
| Route | DEL–BOM |
| Carrier | 6E |
| APW | 7 production + T+21 = **8 searches/day** |
| Flights | 5 (bands 2–6, earliest in each) |
| Window | 21:00–22:00 IST daily; 09:00–10:00 on days 1,4,7,10,13,16,19 |

**This doubles the frozen Day-1 contract's four searches to eight**, because the
contract samples T+7/15/21/30 only. That is a real increase in burden and a
contract amendment — see section 8.

### Frame B — structured, on Tier 1 landing

| | |
|---|---|
| Routes | Top 8–10 domestic city-pairs by DGCA passenger volume |
| Carriers | Every carrier the agreement covers |
| APW | All 7 production + T+21 |
| Flights | **All** eligible non-stop departures, bands 2–6 |

Bands stay **unchanged** — 2–6, as frozen. An API removes the manual cost of
*transcription*, not the methodological reason for the band definition. What it
removes is the one-flight-per-band sampling compromise: with an API we take every
flight in each band, so the band becomes a stratum rather than a sample of one.

---

## 5. Expected observation volume

### Frame A — manual

| | Per day | 30 days |
|---|---|---|
| Searches | 8 | 240 |
| Observations | 8 × 5 = **40** | **1,200** |
| Diagnostic (7 days) | +40 | +280 |
| **Total** | | **≈ 1,480** |

Manual effort: ~8 searches × ~6 min ≈ **50 min/day**, ~100 min on paired days —
roughly **30 hours across the month**. That is a real and, in my judgement,
serious attrition risk; section 8 puts the choice in front of you rather than
absorbing it silently.

### Frame B — structured

Assume 10 routes × 3 carriers × 8 APW × ~6 eligible flights per band-set:

| | Per day | 30 days |
|---|---|---|
| Shopping requests | 10 × 3 × 8 = **240** | 7,200 |
| Observations | ≈ 240 × 6 = **1,440** | **≈ 43,000** |

**~29× the manual volume**, and with structured fare families and tax codes
rather than transcription. Sufficient to exercise the full ladder — elementary
Jevons, within-route aggregation, route weights from the DGCA file, and TPD with
a usable panel — rather than the elementary level alone.

### What volume does *not* fix

More observations do not resolve AMB-8 (what `expected_cells` is), AMB-9 (carrier
allocation), or OQ-1 (the published window). Those are rulings, not sample-size
problems, and they will still be open at 43,000 observations.

---

## 6. Raw artifact storage design

The existing content-addressed store is **already channel-agnostic** and needs no
structural change — `ArtifactStore.put()` takes bytes and a content type and
addresses them by SHA-256. What changes is what we put in it.

| Mode | Artifact(s) | Content type |
|---|---|---|
| `MANUAL_BROWSER` | Results screenshot (ingested) + fare-detail shots | `image/png` |
| `NDC_API` | **Request body** + **response body**, stored separately | `application/xml` / `application/json` |
| `GDS_API` / `LICENSED_FEED_API` | Same pair | `application/json` |
| `PUBLIC_DATASET_API` | Response body | `application/json` |

**Store request and response as two artifacts, not one.** `request_sha256` and
`artifact_sha256` are separate fields because §P.3 replay needs to reconstruct
*what was asked*, not only what came back — and because an identical request
returning different bytes on two days is exactly the drift signal we would want
to detect.

**Three rules carry over unchanged and one is new:**

- Content addressing means identical bytes store once and nothing can be edited
  in place without changing its own address. `verify()` re-hashes on read.
- Never edit, crop or re-encode a stored artifact.
- Retain 5 years.
- **New — redaction before storage.** API responses may carry credentials, tokens
  or agency identifiers in headers. **Store bodies only; never store
  `Authorization` headers or API keys.** This must be enforced at the collector,
  because a secret written into a content-addressed store cannot be deleted
  without breaking every hash that referenced it.

Volume estimate for Frame B: ~7,200 request/response pairs per 30 days at a few
KB each ≈ **well under 1 GB**. SQLite plus a directory remains adequate; PostgreSQL
and object storage can replace them later without changing a call site.

---

## 7. Missingness / outcome taxonomy

The seven `CollectionOutcome` values are **sufficient for structured sources
without modification**, and deliberately so — a taxonomy that changed per channel
would make cross-channel coverage incomparable, which is the one thing it exists
to prevent.

| Outcome | Manual | Structured API |
|---|---|---|
| `SUCCESS` | Fares recorded | Offers returned and parsed |
| `NO_FLIGHT` | No service that date | Empty result, **no error** — service not offered |
| `STRUCTURAL_MISSING` | Route withdrawn | Route/carrier no longer in the frame |
| `TECHNICAL_FAILURE` | Loaded, no purchasable fare | 200 with zero *priced* offers; all sold out |
| `SOURCE_UNAVAILABLE` | Site down, timeout | 5xx, 429, circuit open, **auth expired** |
| `PARSER_FAILURE` | Couldn't read the fare | Schema mismatch, unparseable response |
| `CAPTCHA_OR_ANTIBOT_STOP` | Challenge shown | **403 / WAF / access revoked** — a policy event |

Three properties hold across both channels and must keep holding:

- `NO_FLIGHT` alone leaves the coverage denominator. Everything else stays in.
- `SOURCE_UNAVAILABLE`, `PARSER_FAILURE` and `CAPTCHA_OR_ANTIBOT_STOP` are **our**
  failures, published separately from market absence — blending them overstates
  how thin the market is and understates how unreliable collection was.
- `CAPTCHA_OR_ANTIBOT_STOP` is a **stop signal**. On an API this maps to 403 or a
  revoked key: stop, do not retry, do not rotate credentials, escalate to a human.

**One addition needed for structured sources:** an authenticated API can fail in a
way the web cannot — **quota exhaustion**. A 429 is `SOURCE_UNAVAILABLE` (transient,
back off), but a *hard monthly quota* is closer to a stop signal: continuing to
call burns a contractual allowance and may breach it. Proposed
`QUOTA_EXHAUSTED` as an eighth value, `is_collector_failure = True`,
`is_stop_signal = True`. **Registered as a proposal, not implemented** — this
document changes no code, and adding a `CollectionOutcome` member is a schema
change requiring @Rexy-5097's ruling because it touches the coverage denominator.

---

## 8. Blockers requiring human credentials, contracts, or owner decisions

Ordered by value-per-unit-effort. **None of these is an engineering task.**

### Contracts and credentials — only you can obtain these

| # | Blocker | Action | Who | Effort |
|---|---|---|---|---|
| **B1** | **IndiGo NDC terms are behind registration.** I cannot register — that means creating an account and accepting terms on your behalf | Register at `developer.goindigo.in`, read the API licence, send me the use-restriction clauses | You | ~1 hour |
| **B2** | **Air India NDC production needs a separate agreement.** Portal terms are trial-only and bar extraction *"by any automated means or any manual process… without our express written permission"* | Contact `ndcdistribution@airindia.com`. State the purpose plainly: a public statistical price index, not travel sales | You / owner | Weeks |
| **B3** | **Amadeus production needs an airline-consolidator contract** | Commercial negotiation. **Highest leverage** — IndiGo NDC is already live on Amadeus, so this plausibly solves B1 and B3 together | Owner | Weeks–months |
| **B4** | **Aggregators need agency identity** (IATA / TIDS / IATAN). Duffel holds its own accreditation and is the lowest bar | Decide whether APIx should obtain a **TIDS number** | Owner | Weeks |
| **B5** | **SpiceJet terms unread** — the only carrier whose robots.txt permits search paths | Read `spicejet.com` terms | You | ~30 min |
| **B6** | **IndiGo general Terms of Use unread** — the governing document; the clause in hand is from the *loyalty* T&Cs, and `goindigo.in` is unreachable from my host | Open it in your browser and paste the automation/browser clauses | You | ~15 min |

### Owner methodology decisions

| # | Decision | Why it cannot wait indefinitely |
|---|---|---|
| **B7** | **AMB-11 — two UDF lines.** Does `user_development_fee` take departure UDF only, or departure + arrival? | Affects every observation collected. The component list makes it reversible, but only if we record components from day one |
| **B8** | **Frame A doubles the manual burden** — 4 searches/day → 8, ~50 min/day, ~30 h/month. Attrition is the largest risk to any 30-day study, and a missed day costs **two** weekly links | You must choose: full 7-bucket frame, or keep the frozen 4-bucket contract and accept the APW gap |
| **B9** | **`QUOTA_EXHAUSTED` outcome** — proposed, not implemented | Touches the coverage denominator |
| **B10** | AMB-8 (expected cells), AMB-9 (carrier allocation), OQ-1 (published window) | Open by design. Not blockers for acquisition; blockers for *publication* |

### The institutional option — worth raising explicitly

Every path above treats APIx as a commercial travel seller negotiating for
distribution access. **It may not have to be.**

PS 26056 is a **MoSPI** problem statement, and MoSPI is the ministry that
compiles the CPI. A national statistical office can obtain data from carriers
under statutory authority — the **Collection of Statistics Act, 2008** — rather
than by commercial agreement, and MoSPI's own CPI already collects airfare from
*"well-known websites"* under that footing. DGCA likewise receives route-wise
tariff data from carriers monthly by direction.

If an institutional data-sharing route is available, it is **strictly better than
every commercial option**: no accreditation, no consolidator contract, no
purpose-limitation clause written for travel agencies, and a provenance story far
stronger for a published national statistic.

I cannot evaluate whether that route is open — it depends on the project's
relationship to MoSPI, which I have no visibility into. **Raising it as the
question worth asking before signing anything commercial.**

---

## Recommendation

1. **Now, no approval needed:** automate Tier 0 (eSankhyiki CPI benchmark, DGCA
   weights). Keep manual collection **stopped**.
2. **This week, you:** B1, B5, B6 — three documents, under two hours total. B1
   alone could change the entire plan.
3. **Decide:** B8 (frame size) and the institutional question.
4. **Then:** pursue B3/B1 as one negotiation.

**Manual collection stays designed, frozen and ready as Tier 3** — the fallback
if no agreement lands, and the independent validation channel if one does.

---

## References

- [`compliance/day-1-contract.md`](../../compliance/day-1-contract.md) · [`acquisition-playbook.md`](../../compliance/acquisition-playbook.md)
- [`source_registry/registry.yaml`](../../source_registry/registry.yaml) — two-gate model
- [`ADR-0065`](../../artifacts/decisions/ADR-0065-day-1-acquisition-decisions.md)
- Air India API Website Terms of Use, retrieved 2026-09-12 · IndiGo Developer Portal ·
  Amadeus–IndiGo NDC partnership announcement · AirGateway platform documentation
- `docs/methodology/apix_formula_spec_v1.md` §A.1, §A.3, §A.4, §B.2, §B.6, §G, §H.1, §H.3, §P.3
