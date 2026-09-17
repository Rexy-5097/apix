# Source discovery audit — 2026-09-15

**Owner:** [@slazyverse](https://github.com/slazyverse) · **Date:** 2026-09-15 · **Register:** [`registry.yaml`](../source_registry/registry.yaml) `last_audit_date: 2026-09-15`

> **Question:** which source lets APIx demonstrate automated airfare acquisition
> *defensibly*?
>
> **Answer:** no website audited permits automated fare collection. The
> defensible automated route is a carrier's own NDC API under a partner
> agreement, IndiGo's first. No source is cleared today.

This is an engineering compliance record, not legal advice. It authorises
nothing: the gates in the register do.

> **Superseded in part, the same day.** [`acquisition-sweep-2026-09-15.md`](acquisition-sweep-2026-09-15.md)
> swept twelve acquisition classes and sixteen sources and found a **third gate this
> record does not apply: `data_rights`.** Several sources permit automated access and
> then forbid retaining the response, which disqualifies them for APIx regardless of
> `automation_gate`. Read both. Where they differ on a source, the sweep is later.

---

## Method

- `robots.txt` fetched once from each of the 15 web domains, with an
  identifying user agent.
- Terms read directly where the host served them; otherwise through a
  web-reading tool or a search-engine extract. Each finding in the register
  carries its grade: `[DIRECT]`, `[TOOL]` or `[INDEX]`.
- **No search, results, fare or booking page was requested from any source.**
  CAPTCHA behaviour was therefore not probed; probing it would itself be the
  automated access under review.
- Refusals were recorded and not retried with a different client
  ([C-0](collection-control-contract.md)).

## Result

| Source | Kind | Gate (register) | Data | Evidence grade |
|---|---|---|---|---|
| IndiGo — website | airline | `AUTOMATION_PROHIBITED` | ADMISSIBLE | register + INDEX |
| **IndiGo — NDC API** | airline API | **`AUTOMATION_ALLOWED_WITH_PERMISSION`** | NOT_ASSESSED | INDEX; portal HTTP 502 |
| Air India — website | airline | `AUTOMATION_PROHIBITED` (manual needs permission too) | — | INDEX |
| **Air India — NDC API** | airline API | **`AUTOMATION_ALLOWED_WITH_PERMISSION`** | NOT_ASSESSED | INDEX |
| Air India Express | airline | `AUTOMATION_PROHIBITED` | — | DIRECT robots + INDEX terms |
| Akasa Air | airline | `AUTOMATION_PROHIBITED` | NOT_ASSESSED | register |
| SpiceJet | airline | `AUTOMATION_PROHIBITED` (was UNKNOWN) | — | DIRECT |
| Alliance Air | airline | `AUTOMATION_UNKNOWN` | NOT_ASSESSED | DIRECT |
| Star Air | airline | `AUTOMATION_UNKNOWN` | NOT_ASSESSED | DIRECT |
| Fly91 | airline | `AUTOMATION_PROHIBITED` | NOT_ASSESSED | DIRECT robots + TOOL terms |
| Cleartrip | OTA | `AUTOMATION_PROHIBITED` | — | DIRECT |
| MakeMyTrip | OTA | `AUTOMATION_UNKNOWN` (host refuses plain clients) | — | DIRECT refusal |
| Goibibo | OTA | `AUTOMATION_UNKNOWN` | — | DIRECT |
| EaseMyTrip | OTA | `AUTOMATION_PROHIBITED` | — | DIRECT robots + TOOL terms |
| ixigo | OTA | `AUTOMATION_PROHIBITED` | — | DIRECT robots + TOOL terms |
| Yatra | OTA | `AUTOMATION_PROHIBITED` (was UNKNOWN) | — | INDEX |
| Google Flights | metasearch | `AUTOMATION_PROHIBITED` | INADMISSIBLE | DIRECT robots + TOOL terms |
| **Travelport uAPI** | GDS API | **`AUTOMATION_ALLOWED_WITH_PERMISSION`** | NOT_ASSESSED | TOOL |
| **TBO / Tripjack** | B2B API | **`AUTOMATION_ALLOWED_WITH_PERMISSION`** | NOT_ASSESSED | INDEX |
| Skyscanner Partners | metasearch API | `AUTOMATION_ALLOWED_WITH_PERMISSION` | INADMISSIBLE | INDEX |
| Kiwi Tequila | aggregator API | `AUTOMATION_ALLOWED_WITH_PERMISSION` | NOT_ASSESSED | INDEX |
| Duffel | aggregator API | `AUTOMATION_UNKNOWN` | INADMISSIBLE (no Indian carriers) | TOOL |
| Amadeus Self-Service | GDS API | `AUTOMATION_UNKNOWN` — **decommissioned 2026-07-17** | INADMISSIBLE | INDEX |
| Travelpayouts | affiliate API | `AUTOMATION_ALLOWED` | INADMISSIBLE | register |
| SerpApi (Google Flights) | scraping service | `AUTOMATION_PROHIBITED` — vendor defeats anti-bot challenges (C-0) | INADMISSIBLE | INDEX + TOOL |

`AUTOMATION_ALLOWED_WITH_PERMISSION` is new vocabulary, defined in the register
header. It **blocks collection** exactly as `AUTOMATION_UNKNOWN` does, until the
agreement text is recorded.

## Decisions this record supports

| | |
|---|---|
| Best candidates | 1. IndiGo NDC API · 2. Air India NDC API · 3. an agency API (Travelport or TBO/Tripjack), after a comparability study |
| Hackathon demo | IndiGo NDC **UAT/sandbox**, if portal registration issues keys — labelled SANDBOX, never index input. Otherwise the gated fixture collector (PR #26) |
| Production | Direct NDC with IndiGo and Air India, each under a written data-use agreement covering shop-without-book, retention, and publication of a derived index |
| API vs scraping | An official API: explicit permission, structured fare family / baggage / tax fields, no DOM breakage or challenge pages |

## Open items this audit could not close

1. **IndiGo developer portal** returned HTTP 502 on every page all day. Eligibility,
   UAT scope, NDC version, authentication details and data-use terms are unread.
2. **Air India, Air India Express, MakeMyTrip, Yatra** refuse plain HTTP clients at
   the edge; their terms rest on search-engine extracts. Re-read from a network the
   hosts serve before relying on exact wording.
3. **Channel mapping** of NDC offers (`AIRLINE_DIRECT` vs `LICENSED_FEED`) is a
   methodology ruling. The register records `LICENSED_FEED` as *provisional* so NDC
   quotes cannot silently pool with website quotes.
4. **Agency-channel comparability**: agent, private and corporate fares are not the
   household's displayed price (spec A.4).

## What did not change

No source was cleared. No methodology, schema, store, collection window, APW vector
or manual study was touched. The manual Day-1 contract remains the only collection
mode in force.
