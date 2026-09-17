# Automated collection — architecture, status and the gate that blocks it

**Owner:** [@slazyverse](https://github.com/slazyverse) · **Branch:** `feat/slazy/automated-collection` · **Date:** 2026-09-15

> **Status, stated once and precisely.**
>
> | | |
> |---|---|
> | Automated collection layer (rules, normalisation, store, evidence) | **implemented and tested** |
> | IndiGo adapter — fixture mode | **works, on SYNTHETIC pages only** |
> | IndiGo adapter — live mode | **implemented, refused by the compliance gate, has never run** |
> | Other airline adapters | not implemented |
> | OTA adapters | not implemented |
>
> **APIx has not automatically collected any fare from any website.** Every real
> observation in the repository was collected manually and remains labelled so.

---

## 1. Why live collection is blocked

The collection brief asks for a live automated adapter for goindigo.in. The
project's own compliance record does not permit one today, and this branch
enforces that record rather than working around it.

| Evidence | Where | What it says |
|---|---|---|
| Source register | [`registry.yaml`](../../source_registry/registry.yaml) `indigo` | `automation_gate: AUTOMATION_PROHIBITED`, `manual_gate: MANUAL_PERMITTED`. The clause obtained prohibits "any automated use", "robots" and "any spider, robot … scraper"; it exempts "internet browser usage" by a person |
| Protocol | [`acquisition-protocol.md`](../../compliance/acquisition-protocol.md) §1 | "No automated run may start until a source reaches `AUTOMATION_ALLOWED` on positive, quoted evidence" |
| Control contract | [`collection-control-contract.md`](../../compliance/collection-control-contract.md) C-1 | Collection needs `tos_status` permitting it; IndiGo's is `NOT_VERIFIED` |
| Decision | [`ADR-0065`](../../artifacts/decisions/ADR-0065-day-1-acquisition-decisions.md) §1 | "Automating against a `PROHIBITED` one needs no discussion" |
| Network, 2026-09-15 | this branch | `curl https://www.goindigo.in/robots.txt` was reset by the server (`HTTP/2 stream … INTERNAL_ERROR`) in 0.06 s; a control fetch of `akasaair.com/robots.txt` returned 200. A fetch tool timed out on robots.txt and on the Terms path. Third reproduction after 2026-09-10 and 2026-09-12. **Not retried with other clients** — a server refusing non-browser clients is an access control, and getting past it is what C-0 forbids |

**The register's own caveat is live:** the prohibiting clause is from IndiGo's
loyalty-programme terms, and the general website Terms of Use remain unread. If
those terms turn out to permit automated collection, the rating can change —
through the register, on quoted evidence, as a reviewed change. Not in code.

`tests/test_collector_runner.py::test_no_source_in_the_register_is_cleared_for_live_collection`
fails the build the day a source clears, so this document cannot silently go stale.

## 2. Architecture

```
CollectionConfig (frozen contract + travel dates + window)
        │
        ├── LIVE only: gate.require_live_clearance(registry entry) ── refused → nothing requested, nothing written
        │
        ▼
SourceAdapter.search(params) ──► SearchResult        one per travel date; paced ≥30 s (live);
        │                        page state,          one retry after ≥60 s on a site error;
        │                        echoed search,       a challenge stops the source for the run
        │                        every returned flight,
        │                        raw artifacts
        ▼
eligibility.assess_all        carrier, operator, non-stop, exact airports, date, 06:00–20:59
        ▼
selection.select_earliest_per_band     departure time + flight number only — never price, never page order
        ▼
fares.choose_contract_fare    Saver; Lite never substituted; checked baggage; INR; not concession
        ▼
normalize.to_observation / to_unpriced ──► the EXISTING Observation / UnpricedFlight
        ▼
evidence.write_run_export     run.json · attempts.json · selection.json · observations.json · manifest.json
        ▼
CollectionStore (existing)    record_run / attempt / artifact / observation; verify()
        ▼
filter_admissible (existing)  unchanged; no automation-specific path
```

| Module | Responsibility |
|---|---|
| [`contract.py`](../../src/apix/ingestion/collectors/contract.py) | The frozen search contract as values; APW read from `APWBucket` (no T+21); bands 2–6 |
| [`candidates.py`](../../src/apix/ingestion/collectors/candidates.py) | The returned flight universe before any rule — kept whole for audit |
| [`eligibility.py`](../../src/apix/ingestion/collectors/eligibility.py) | Every ineligible flight carries its reasons |
| [`selection.py`](../../src/apix/ingestion/collectors/selection.py) | Earliest eligible flight per band; records eligible count per band |
| [`fares.py`](../../src/apix/ingestion/collectors/fares.py) | Saver decision, exclusions with reasons |
| [`normalize.py`](../../src/apix/ingestion/collectors/normalize.py) | Canonical records, Day-1 id shape |
| [`gate.py`](../../src/apix/ingestion/collectors/gate.py) | Compliance gate — no override |
| [`evidence.py`](../../src/apix/ingestion/collectors/evidence.py) | Deterministic JSON, SHA-256 manifest, export verification |
| [`runner.py`](../../src/apix/ingestion/collectors/runner.py) | Orchestration, outcome classification, store writes |
| [`adapter.py`](../../src/apix/ingestion/collectors/adapter.py) | The interface a future Air India / Akasa / OTA adapter implements |
| [`indigo/parse.py`](../../src/apix/ingestion/collectors/indigo/parse.py) | Display strings → typed candidates; DOM-change detection |
| [`indigo/navigation.py`](../../src/apix/ingestion/collectors/indigo/navigation.py) | The contracted search as ordered steps; selectors **UNVERIFIED** |
| [`indigo/fixture.py`](../../src/apix/ingestion/collectors/indigo/fixture.py) | Replays SYNTHETIC payloads |
| [`indigo/live.py`](../../src/apix/ingestion/collectors/indigo/live.py) | Playwright adapter; gate first, then import |

### What is deliberately *not* new

No new observation type, no schema change, no store change, no change to any
file under `src/apix/statistics/`, no methodology text touched. Automated
provenance is carried where the store already carries provenance:

| Field | Manual Day-1 run | Automated run |
|---|---|---|
| `collector_identity` | a person | `fixture:FixtureIndigoAdapter` / `live:LiveIndigoAdapter` |
| `collector_version` | `manual` | `0.1.0+<git sha>` |
| `parser_version` | `manual-1.0` | `indigo-extract-parser/1` |
| `protocol_version` | `acquisition-protocol-2I` | `automated-collection-trial-1` |
| `frame_id` suffix | `@primary` (index input) | `@fixture` / `@automated-trial` (**never** index input) |
| `source_type` | `LIVE_SCRAPE` | `SYNTHETIC` (fixture) / `LIVE_SCRAPE` (live) |

The automated collector writes to its own store, `data/collection-automated/`
(gitignored). It never writes to the manual study's `data/collection/`, so it
cannot disturb the 2026-09-19 matched pair ([procedure](../collection-2026-09-19.md)).

## 3. The rules, and where they come from

| Rule | Source | Enforced in |
|---|---|---|
| DEL→BOM exact, one-way, 1 adult, Economy, INR, Regular, signed out, nearby airports off | procedure §3, §4 | `CollectionContract` (any other value raises); page echo checked in `runner.echo_mismatches` |
| IndiGo marketed **and** operated, non-stop | procedure §4 | `eligibility` |
| Bands 2–6 (06:00–20:59); earlier and later departures never collected | ADR-0065 §4 | `eligibility`, `selection` |
| **Earliest eligible flight per band, never by price** | ADR-0065 §4, procedure §5 | `selection` — plus a property test and a test that fails if selection reads any fare |
| An empty band yields nothing; nothing is borrowed | procedure §5 | `selection` |
| Saver; Lite never substituted; must include checked baggage | brief; procedure §6 | `fares` — a cheaper checked-baggage family excludes the quote rather than recording Saver under a rule it fails |
| Entitlements from displayed text, never guessed | spec B.4 | `parse.parse_checked_baggage`, `parse_change_cancellation` — unknown text is `None` → excluded |
| Components only where displayed; blank is `None`, never `0` | spec A.4 | `parse.parse_breakdown` |
| Sold-out Saver → unpriced flight, not replaced | spec D.6 | `fares`, `normalize.to_unpriced` |
| Every search gets an attempt, including never-made ones | spec H.1 | `runner` |
| Never infer `NO_FLIGHT` | procedure §8 | a "no flights" page is `TECHNICAL_FAILURE` |
| Challenge = stop: no retry, remaining searches `NOT_ATTEMPTED` | C-0, procedure §8 | `runner`; `live.challenge_reason` |
| ≥10 s pacing floor, ≥60 s single retry | protocol §12 | `CollectionConfig`, `run_collection` |

**`Change and cancellation charges: Standard` → `FEE`/`FEE`.** That is how the
2026-09-12 manual collectors recorded the Saver line on all 30 primary rows.
Any other policy text not in `parse._POLICY_RULES` leaves the entitlement
undeterminable and the quote is excluded.

## 4. Outcomes

| Page | Outcome | Why |
|---|---|---|
| Results, ≥1 contract fare | `SUCCESS` | shortfall per band in `detail` |
| Results, every fare unreadable | `PARSER_FAILURE` | our failure |
| Results, every selected flight sold out | `TECHNICAL_FAILURE` | procedure §8 |
| Echoed search ≠ contract (currency, pax, airport, date, trip) | `PARSER_FAILURE` `SEARCH_PARAMETER_MISMATCH` | the search that ran is not the contracted one |
| Missing payload key | `PARSER_FAILURE` `DOM_CHANGED` | the extractor and page disagree |
| Unrecognised page, adapter exception | `PARSER_FAILURE` | our failure |
| Site error (after one retry) | `SOURCE_UNAVAILABLE` | our failure |
| "No flights" message | `TECHNICAL_FAILURE` | never `NO_FLIGHT` |
| Access challenge | `CAPTCHA_OR_ANTIBOT_STOP` | stop signal |

## 5. Evidence

```
data/collection-automated/
  collection.sqlite3                 existing schema, unchanged
  artifacts/{sha[:2]}/{sha}          existing content-addressed store
  runs/{run_id}/
    run.json            run record, environment, gate decision, contract, index_input: false
    attempts.json       every attempt with counts and the recorded search parameters
    selection.json      every returned flight, eligibility reasons, per-band eligible count and pick
    observations.json   canonical observations, unpriced flights, excluded selections with reasons
    manifest.json       sha256 of each document above and of every artifact
```

Each observation's `artifact_sha256` points at the evidence it was read from
(the screenshot in live mode, the payload in fixture mode). `verify_run_export`
re-hashes the documents and reads every artifact back through the store, which
detects an edited file. Identical inputs give byte-identical exports (tested).

## 6. How to run

Fixture mode — SYNTHETIC pages, no request made:

```bash
python tools/collection/collect_auto.py --mode fixture --fixture tests/fixtures/indigo/extract_2026-09-15.json --collection-date 2026-09-15 --travel-date 2026-09-22
```

```bash
python tools/collection/collect_auto.py --mode fixture --fixture tests/fixtures/indigo/extract_2026-09-15.json --collection-date 2026-09-15 --apw 1,3,7,15,30,45,60
```

Live mode — refused today with exit code `3`, before any request:

```bash
python tools/collection/collect_auto.py --mode live --apw 7
```

Exit codes: `0` clean · `1` configuration error · `2` integrity problems or not
loaded · `3` refused by the compliance gate · `4` stopped by an access challenge.

A fixture run executed outside 21:00–22:00 IST exits `2`: its timestamps are real,
and `verify()` correctly flags quotes outside the declared window (spec A.5).

## 7. What would unblock live collection

In order, and none of it is an engineering decision:

1. **Read IndiGo's general Terms of Use and robots.txt from a network that can
   reach them**, and record the quoted text in `registry.yaml`. If they prohibit
   automated collection, stop here — the adapter stays gated, and that is an
   acceptable end state.
2. If they permit it: set `tos_status`, `automated_collection_status`,
   `robots_status` and `automation_gate` on quoted evidence, reviewed by
   @slazyverse.
3. An ADR deciding whether an automated frame may ever become index input, and
   how it relates to the manual 30-day study (protocol §15 ends a study whose
   collection method changes).
4. One supervised live run, headful, to **verify the selectors** in
   `navigation.py` and `live.py`. Mismatches surface as `PARSER_FAILURE`; they are
   fixed in code, never filled in.
5. Only then a full seven-bucket live run.

## 8. Known limitations

- The live adapter's selectors and extraction script are **unverified placeholders**.
- The fixture's display formats come from 2026-09-12 screenshots; the fixture's
  flights (6E 9xxx) and prices are invented.
- The policy-text mapping covers only phrases seen or specified; anything else excludes.
- No circuit breaker persists across runs; a challenge stops the current run only.
- Air India, Akasa Air, SpiceJet, Air India Express and all OTAs: interface only.
