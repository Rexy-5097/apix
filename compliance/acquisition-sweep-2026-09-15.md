# Acquisition sweep — 2026-09-15

**Owner:** [@slazyverse](https://github.com/slazyverse) · **Date:** 2026-09-15 · **Register:** [`registry.yaml`](../source_registry/registry.yaml)
**Follows:** [`source-audit-2026-09-15.md`](source-audit-2026-09-15.md), the same day. That record asked
*which sources permit automation*. This one asks a different question and reaches a different kind of answer.

> **Question:** which source lets APIx demonstrate **automated acquisition today** — live, sandbox or
> otherwise — ranked by time-to-demo rather than by preference?
>
> **Answer:** none. Twelve acquisition classes and sixteen sources were swept. No source yields
> per-flight airfare observations automatically today by any route APIx may legitimately take.
>
> **And the reason is not the one we had been tracking.** Access was never the binding constraint.
> **Data rights are.** Several sources grant automated access and then forbid retaining the response.
> APIx cannot exist without retained evidence, so those sources are unusable however open their door.

This is an engineering compliance record, not legal advice. It authorises nothing: the gates in the
register do.

---

## Method, and what was deliberately not done

- Official documentation and published terms only. Where a portal is client-rendered it was read in a
  real browser; where a host refused a plain client, that was recorded as an outcome.
- **No search, results, fare or booking page was requested from any source.** No credentials were
  created, borrowed or guessed. No CAPTCHA, bot protection, authentication or rate limit was tested
  or circumvented.
- Refusals and timeouts were recorded and **not retried with a different client**
  ([C-0](collection-control-contract.md)).
- No endpoint, payload or schema was inferred. Where official material is unreadable the finding is
  `UNKNOWN`, never an assumption.

Evidence grades are the register's: `[DIRECT]` fetched from the source host during the sweep,
`[TOOL]` fetched by a web-reading tool that returned extracted wording, `[INDEX]` search-engine extract.

## The third gate — `data_rights`

The register carries two orthogonal gates: `automation_gate` (may we automate?) and
`data_admissibility` (is the result a price?). This sweep establishes that a third is needed, because
two sources passed the first and failed on a property neither existing gate captures.

```
data_rights: RETENTION_PERMITTED    the terms explicitly permit retaining responses and
                                    publishing derived works
data_rights: RETENTION_PROHIBITED   the terms explicitly forbid retaining response data, or
                                    forbid the derived or aggregated use APIx is
data_rights: RETENTION_UNKNOWN      terms unread or silent. BLOCKS use. THE DEFAULT
data_rights: NOT_APPLICABLE         no response data is obtained from this source
```

**Why this is load-bearing and not bookkeeping.** APIx publishes an index derived from retained,
hashed observations. A source that forbids retention cannot supply a canonical Observation at all —
not in production, not in sandbox, not once. That is a stricter exclusion than
`AUTOMATION_PROHIBITED`, which at least leaves a manual carve-out open.

Silence is not permission here either. `RETENTION_UNKNOWN` blocks, for the same reason
`NOT_VERIFIED` blocks.

## Result — sixteen sources, twelve classes

`L1` technically accessible · `L2` legitimately usable **with retention** · `L3` statistically
admissible under spec A.4, the household's displayed price. The three are independent, and a source
may pass one and fail the next.

| Source | Class | Access today | L1 | L2 | L3 | Decision |
|---|---|---|:--:|:--:|:--:|---|
| IndiGo NDC | airline API | portal HTTP 502, 4th reproduction | no | ? | ? | **BLOCKED** |
| IndiGo website | airline site | host refuses non-browser clients | no | no | yes | REJECT — automation prohibited |
| Air India NDC | airline API | host unreachable; **no schema published** | no | ? | ? | UNRESOLVED |
| AI Express · Akasa · SpiceJet · Alliance Air · Star Air · Fly91 | airline | **no API programme exists** | no | no | — | REJECT |
| Travelport | GDS API | **instant trial, no accreditation** | yes | **no** | no, agency channel | **REJECT — retention prohibited** |
| Sabre | GDS API | clientId needs an account manager; refs behind sign-in | no | ? | no, agency channel | REJECT — time to access |
| Amadeus Self-Service | GDS API | **deprecated**; also excluded low-cost carriers | no | no | no | REJECT |
| Duffel | B2B API | instant test token | yes | no | no | REJECT — no Indian carriers |
| TBO | B2B API | 1–2 working days to human onboarding | ? | ? | no, net fares | **DEFER — best real candidate** |
| Tripjack | B2B API | no public documentation; terms unreadable | ? | ? | no | DEFER |
| Kiwi Tequila | B2B API | portal client-rendered; partner host HTTP 503 | ? | ? | ? | UNKNOWN |
| Skyscanner Travel API | metasearch API | two-week review, eligibility screen | no | ? | no, indicative | REJECT — time to access |
| Travelpayouts | affiliate API | instant token | yes | no | no, cached | REJECT |
| data.gov.in / OGD | government | **open API, GODL licence** | yes | **yes** | no, **no fares** | Weights and context only |
| DGCA publications | government | no fare publication exists | yes | no | no | REJECT |
| MoSPI eSankhyiki | government | **already automated in this repository** | yes | yes | no, benchmark | Benchmark only |

## The findings that decided it

### Travelport — the door that opens, and the clause that shuts it

Travelport is the only source whose own documentation offers self-service credentials with no
accreditation and no contract: "Instant trial access • No payment required" `[TOOL]`. It publishes a
readable schema and a credential-free documentation mock server. It was the expected build target.

Its own terms disqualify it for APIx. The test-system terms of service state
**"You may not retain any data from a session"** `[TOOL]`, and the API and SDK terms of use prohibit
using "any automated process or tool to access and/or use the Service (such as a BOT or a spider)"
without written authorisation from Travelport `[TOOL]`.

A retained, automatically collected fare history is precisely what those two sentences address. The
honest next step is to request that written authorisation, not to begin polling. Separately the
offers are PCC-scoped agency-channel fares, which is a spec A.4 problem independent of permission.

### Amadeus Self-Service — dead twice over

The register already recorded decommissioning on 2026-07-17. That is now corroborated independently:
Amadeus' official developer-guides repository is titled "[DEPRECATED]" and states "The Amadeus for
Developers Self-Service offer has been deprecated", and the entire official `amadeus4dev`
organisation — guides, OpenAPI specifications and every SDK — was archived on **2026-07-17** `[TOOL]`.

A second, independent disqualification is worth recording because it would have applied even had the
programme survived: the documented dataset excluded low-cost carriers `[TOOL]`. IndiGo, SpiceJet and
Akasa are low-cost carriers. An Amadeus-sourced Indian domestic index could never have covered the
DEL–BOM pilot's own carrier.

### Duffel — instant, and empty for India

Signup is about a minute and a test token is immediate `[TOOL]`. But the published airline list
contains **no Indian carrier** — no IndiGo, Air India, SpiceJet, Akasa or Vistara `[TOOL]` — and test
mode returns Duffel's own synthetic carrier, of which the documentation says you "won't see realistic
flight schedules or prices" `[TOOL]`. Its services agreement additionally forbids using the services
"for metasearch purposes" `[TOOL]`, which reaches a published index.

### The Indian carriers — there is no programme to onboard to

Of the six carriers reachable in this sweep, **none operates a developer or partner API programme**
`[TOOL]`. What exists is human agent portals and application forms. Two publish terms that grant only
viewing: Akasa Air "authorises the customer to view the content available on the Website", and Fly91
"grants customers authorization to view the content available on the Website", both with personal,
non-commercial limitations `[TOOL]`.

Two carriers additionally disallow their own fare paths to automated clients in `robots.txt` —
SpiceJet disallows its `/api/v1` path, and Air India Express disallows `/flight-availability`
`[TOOL]`. Recorded because it settles any suggestion of using a site's internal JSON endpoints as a
fallback: for these two the carrier has declared those paths off-limits, and C-2 makes that decisive.

Two route facts also rule out carriers independently of access: Fly91 does not serve DEL, and Star Air
serves BOM but not DEL `[TOOL]`. Neither could serve the pilot route with credentials in hand.

Air India and IndiGo could not be reached at all — every request to both hosts timed out from two
independent networks, including a 200-byte `robots.txt` `[DIRECT]`. That is edge-level refusal of
non-browser clients, not slow pages. Not retried with another client.

### IndiGo NDC — an origin failure, not an access control

Every documented portal path returned **HTTP 502** again on 2026-09-15 `[DIRECT]`: `/`, `/ndcAPI`,
`/authentication`, `/FAQs`, `/airshopping`, `/offerPrice` and `/serviceList`. This is the fourth
reproduction after 2026-09-10 and 2026-09-12.

The failure is now characterised, which changes how it should be read. The host resolves through an
Akamai edge that is **healthy** and passing requests through, and the 502 body is emitted by
`Microsoft-Azure-Application-Gateway/v2` at the origin `[DIRECT]`. There is no 401, no 403, no 429,
no CAPTCHA and no bot challenge anywhere in the exchange.

**So this is not a permission problem, and not something APIx can influence.** It is the carrier's own
origin having no healthy backend. Nothing is being withheld from us; the portal is down. Re-check
periodically, do not escalate, and do not work around.

### Sabre — an account manager stands in the way

The portal renders and lists the relevant products, Bargain Finder Max and NDC AirShopping, but the
OAuth token documentation states that to provision a new clientId you "contact your account manager"
`[DIRECT]`, and reference documentation returns "You might need to Sign In to access this content"
`[DIRECT]`. No self-service path, and the schema is not publicly readable.

### Government open data — permissive licence, no fares

This is the one class whose licence is unambiguously on APIx's side, and the one with nothing to
license. The Government Open Data License – India grants "a worldwide, royalty-free, non-exclusive
license to use, adapt, publish", to "create derivative works (including products and services)",
"for all lawful commercial and non-commercial purposes", conditioned on attribution and
non-endorsement `[TOOL]`. A derived price index is squarely inside that grant.

There are **no airfare datasets to apply it to.** Across 287,820 platform resources, zero datasets
carry "airfare" in title or description, and the 373-resource Aviation sector contains no fare-titled
dataset at all `[TOOL]`. The Ministry of Civil Aviation series are departures, hours, kilometres,
passengers, available seat kilometres, load factors and cargo — capacity and traffic, not one
rupee-denominated fare — and most were last updated in 2018 `[TOOL]`. The single airfare-titled
resource on the platform is a 2022 Rajya Sabha answer annexure whose columns are airline against six
evacuation cities, created and last updated the same day `[TOOL]`.

DGCA publishes no fare or tariff series: its A–Z index and sitemap contain no tariff, fare or
fare-monitoring entry in any format `[TOOL]`, and its content carries an all-rights-reserved notice
with no reuse grant `[TOOL]`. **The premise that DGCA publishes route-wise tariff data is not
supported by its own site** — a regulator receiving data under a reporting mandate is not a
publication channel.

GODL is also **silent on automated retrieval**. It licenses what may be done with data already held,
not the act of crawling. So government data is `RETENTION_PERMITTED` and `AUTOMATION_UNKNOWN` at once.

## Decisions this record supports

| | |
|---|---|
| Today's demo source | **None available.** The gated fixture collector remains the only honest automated demonstration, and it is labelled synthetic |
| Best production candidate | **TBO** — the only source with real Indian low-cost-carrier content. Its retention and derived-data terms are unpublished and must be obtained in writing during onboarding |
| Fastest access, unusable | Travelport. Do not build against it before the written authorisation its own terms require |
| Do not pursue | Amadeus Self-Service (deprecated, and excluded low-cost carriers anyway), Duffel (no Indian content), Travelpayouts (cached, thin schema), Skyscanner (two-week review, indicative pricing) |
| Government data | Adopt for **route weights and context only**, under GODL with attribution. It cannot supply fare observations |
| The structural conclusion | Every commercial path requires purchasing the retention and republication rights APIx needs regardless. See [`acquisition-strategy.md`](../docs/engineering/acquisition-strategy.md) on the statutory route |

## What did not change

No source was cleared. No methodology, schema, store, collection window, APW vector, departure band,
publication guard or primary observation was touched. The manual Day-1 contract remains the only
collection mode in force, and no automated run has produced an APIx observation.

## Open items this sweep could not close

1. **Air India and IndiGo hosts** refuse non-browser clients from two networks. Their NDC terms,
   eligibility and any published schema are unread. Re-retrieve from a network the hosts serve.
2. **TBO and Tripjack retention terms** are not published, and Tripjack's terms are client-rendered
   and were not readable. Both must be asked directly during onboarding.
3. **Kiwi Tequila** could not be assessed: its portal is client-rendered and its partner host
   returned HTTP 503.
4. **The data.gov.in API key procedure and rate limits** could not be verified — the portal returned
   HTTP 403 to the audit client while the API host itself answered.
5. **Whether any automated channel may ever be index input** remains an owner decision requiring an
   ADR. Nothing in this sweep presumes it.
