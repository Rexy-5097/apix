# IndiGo NDC — automated acquisition through the official API channel

**Owner:** [@slazyverse](https://github.com/slazyverse) · **Branch:** `feat/slazy/indigo-ndc` (child of `feat/slazy/automated-collection`) · **Date:** 2026-09-15

> **Status, stated once.**
>
> | | |
> |---|---|
> | `UAT_ACCESS_STATUS` | **BLOCKED** — developer portal HTTP 502 all day; no credentials held |
> | Official request/response model | **UNCONFIRMED** — nothing implemented that depends on it |
> | Sandbox gate, credential handling, index-input boundary, CLI | **built and tested** |
> | NDC request builder, parser, fixture, OfferPrice handling | **not built** — each would have to invent undocumented details |
> | Requests sent to IndiGo | **none** |
> | Production authorisation | **none** — register rates the channel `AUTOMATION_ALLOWED_WITH_PERMISSION` (PR #27) |
>
> Nothing on this branch lets APIx claim automated acquisition from IndiGo. The
> permitted wording, once a sandbox run succeeds, is: *"Automated acquisition
> demonstrated against the official IndiGo NDC interface in sandbox/UAT mode."*

---

## 1. What is known, and how

| Fact | Source | Grade |
|---|---|---|
| Portal home, `ndcAPI`, `FAQs`, `airshopping`, `authentication`, `login`, `serviceList`, `offerPrice` all return **HTTP 502** (Azure Application Gateway) | direct requests, 2026-09-15, repeated | DIRECT |
| Shopping is an `IATA_AirShoppingRQ` answered by a **Navitaire NDC Gateway** with `IATA_AirShoppingRS` | search-engine extract of `developer.goindigo.in/airshopping` | INDEX |
| Developers **sign up to get API keys** | extract of the portal home | INDEX |
| An NDC token is generated from a **subscription key** and an **authorization key** | extract of `developer.goindigo.in/authentication` | INDEX |
| The portal lists AirShopping, ServiceList, SeatAvailability, OrderCreate, OrderRetrieve, OrderChange pages | search-engine result titles | INDEX |

## 2. What is not known — and therefore not implemented

- UAT and production base URLs; token endpoint; header names; token lifetime
- NDC schema version; JSON or XML payloads
- The AirShopping request for a one-way, 1-adult, Economy, INR search
- Where fare brand, base/tax/total, checked baggage and change/cancel conditions sit in the response
- Whether `OfferPrice` is needed for the final payable total, or `ServiceList` for baggage
- Eligibility for UAT keys, rate limits, look-to-book limits, and response-retention terms

The IATA schema is a public standard, but IATA's schema viewer returned 403 to this
host, and IndiGo's implementation choices (version, profile, JSON binding) cannot be
inferred from the standard. Building a fixture from memory of the standard would be
the invented response the task forbids.

## 3. What is built

| Piece | Where | Behaviour |
|---|---|---|
| `CollectionMode.SANDBOX` | [`gate.py`](../../src/apix/ingestion/collectors/gate.py) | Sandbox gate: register must rate the channel `AUTOMATION_ALLOWED` or `AUTOMATION_ALLOWED_WITH_PERMISSION`, it must be an API channel (`robots_status: NOT_APPLICABLE`, so no website qualifies), and source-issued keys must be present. No override. |
| Live gate | same | Unchanged. `AUTOMATION_ALLOWED_WITH_PERMISSION` never clears it. |
| Index-input boundary | [`index_boundary.py`](../../src/apix/ingestion/collectors/index_boundary.py) | Only a `@primary` run made by the manual collector is index input. The runner refuses — before writing evidence or store rows — any automated run labelled `@primary`. `index_input_observations(store)` returns only manual primary observations. |
| Sandbox labelling | [`runner.py`](../../src/apix/ingestion/collectors/runner.py) | Frame suffix `@sandbox`, `collector_identity sandbox:<Adapter>`, `source_type AUTHORIZED_FEED`. An import-time assertion forbids any automated mode mapping to `@primary`. No schema change. |
| Credentials | [`indigo/ndc.py`](../../src/apix/ingestion/collectors/indigo/ndc.py) | Read from the environment only: `INDIGO_NDC_BASE_URL` (https), `INDIGO_NDC_SUBSCRIPTION_KEY`, `INDIGO_NDC_AUTHORIZATION_KEY`. Names are **provisional** until the authentication page is readable. `repr`/`str` redact both keys; errors name variables, never values; `.env` files are gitignored. |
| APW check | [`contract.py`](../../src/apix/ingestion/collectors/contract.py) | Given both `--travel-date` and `--apw`, they must agree exactly; neither is rewritten. T+21 is refused. |
| CLI | [`collect_auto.py`](../../tools/collection/collect_auto.py) | `--source indigo-ndc` with `--mode fixture | sandbox | live`. Prints `SOURCE: INDIGO NDC` and `MODE: …`. |

## 4. Running it

```bash
python tools/collection/collect_auto.py --source indigo-ndc --mode sandbox --collection-date 2026-09-15 --travel-date 2026-09-22 --apw 7
```

| Situation | Exit | Message |
|---|---|---|
| `indigo_ndc` not in the register (true until PR #27 merges) | `3` | refused by the compliance gate |
| In the register, keys absent | `3` | `credentials=ABSENT`, lists the variable names |
| In the register, keys present | `5` | `BLOCKED: … request/response model is UNCONFIRMED … No request was sent` |
| `--mode fixture` | `5` | no NDC fixture exists without the official schema |
| `--mode live` | `3` | `AUTOMATION_ALLOWED_WITH_PERMISSION` does not clear the live gate |

## 5. Mapping plan — to confirm, not assumed

When the official response is readable, each field is mapped explicitly or the
observation is excluded:

| Canonical field | To locate in the NDC response | If absent |
|---|---|---|
| flight number, carriers, departure/arrival, duration, stops | segment / journey data | flight ineligible |
| fare brand → `fare_family_raw` | price-class or brand data | excluded; *Saver* in NDC is not assumed equal to the website's *Saver fare* |
| `payable_fare`, base, taxes | offer price; `OfferPrice` if AirShopping totals are indicative | excluded |
| checked baggage | baggage allowance or `ServiceList` | `ENTITLEMENTS_UNDETERMINABLE` |
| change / cancellation | penalty or fare-rule data | `ENTITLEMENTS_UNDETERMINABLE` |
| channel | register records `LICENSED_FEED`, **provisional** | never pooled with website quotes without a methodology ruling |

Eligibility, earliest-flight-per-band selection, fare decision, normalisation, the
store and the evidence manifest are the existing PR #26 code, unchanged.

## 6. To unblock, in order

1. **You** register at `developer.goindigo.in` once the portal responds. Account
   creation is a person's action, not the collector's.
2. Share the official material — Swagger/OpenAPI export, the authentication page,
   sample `AirShoppingRQ`/`RS` (and `OfferPriceRQ`/`RS` if documented) — with any
   keys removed. Keys go only into local environment variables.
3. Record the UAT terms (retention, rate limits, permitted use) in `registry.yaml`.
4. Then: request builder, parser, a sanitised fixture derived from the official
   sample, `OfferPrice` only if the documentation requires it, and a sandbox run.
5. Production stays blocked until a written agreement is recorded and an ADR decides
   whether any automated channel may ever be index input.

## 7. Unchanged

Methodology, APW, departure bands, fare definitions, the publication guard, the 35
primary observations, the 19 September protocol, the schemas and the store.
