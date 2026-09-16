# ADR-0067 — Exercise the browser path against a page we serve ourselves

**Status:** Accepted · **Date:** 2026-09-16 · **Owner:** [@slazyverse](https://github.com/slazyverse)

## Context

`collectors/indigo/live.py` implements the Playwright adapter: launch Chromium,
run the contracted navigation plan, execute the extraction script, parse the
payload, capture evidence. The compliance gate refuses every source in the
register before the adapter is constructed, so **the adapter had never run**.
Not once. No browser had launched, no DOM had been navigated, no extraction
script had executed and no candidate had ever been produced by it.

Everything we said about that code path rested on reading it. That is the
weakest form of evidence in the repository, and it sat on the component the
problem statement cares about most.

The obvious ways to fix it were both unacceptable:

* Run it against goindigo.in — prohibited. `automation_gate:
  AUTOMATION_PROHIBITED`, and the protocol requires positive quoted permission
  we do not have.
* Loosen the gate "just for a test" — the gate is the load-bearing claim of the
  whole project. A test-only exemption is an exemption.

## Decision

Add a third collection mode, `CollectionMode.LOOPBACK`: the same adapter,
navigation plan, extraction script and parser, driven by a real Chromium against
**a page this repository serves on 127.0.0.1**
(`tools/collection/loopback_site.py`).

There is no third party. We are the publisher of that page, so there is no
Terms of Service to respect, no robots.txt to read, and nobody's service to
consume. The output is synthetic and is marked so.

Two structural guarantees, both tested:

1. **A loopback entry can never clear the live gate.** `LOOPBACK_REQUIREMENTS`
   and `LIVE_REQUIREMENTS` are disjoint on two independent fields —
   `automation_gate` (`AUTOMATION_SELF_HOSTED` vs `AUTOMATION_ALLOWED`) and
   `data_admissibility` (`INADMISSIBLE_SYNTHETIC` vs `ADMISSIBLE`). Editing one
   field is not enough to break through.
2. **No registered source can clear the loopback gate**, and the mode refuses
   any URL that is not loopback. The check parses the URL and range-checks the
   address, so `http://127.0.0.1.evil.test/` — a hostname somebody else owns —
   is refused.

`LOOPBACK_ENTRY` is defined in code, not in `source_registry/registry.yaml`,
because it is not a source. The register describes places that hold airfares.

## What this proves, and what it does not

**Proves** (`tests/test_loopback_browser_proof.py`, 9 tests):

| | |
|---|---|
| Chromium launches | `environment["browser"] == "chromium/153.0.8010.12"` |
| The navigation plan drives a real DOM | all 16 steps execute: cookie decline, signed-out assertion, one-way, both airports, calendar day, three pax counts, fare type, currency `select`, nearby-airports assertion, submit, wait, sort |
| The extraction script runs in-page | returns a valid `indigo-extract/1` payload |
| The parser types it | 3 candidates, carrier/number/airports/times/duration/stops, zero parse issues |
| Fares decompose and reconcile | base + tax == payable fare; absent UDF stays `None`, never `0` |
| Evidence is real | a genuine PNG (44 KB, verified by magic number), the DOM, the payload |
| A challenge stops the run | `ACCESS_CHALLENGE`, `detail="page text contains 'captcha'"`, no candidates, evidence still captured |
| A renamed selector fails loudly | `UNRECOGNISED`, `NAVIGATION_STEP_FAILED wait:results_list`, never a guessed value |

**Does not prove** — and the tests assert this rather than leaving it implied:
that `navigation.SELECTORS` and `live.EXTRACT_SELECTORS` match goindigo.in. They
stay `UNVERIFIED`. The fixture implements the selector contract *as written*, so
this exercises the machine, not the mapping. The mapping can only be verified
against the real site, which needs the authorization we do not have.

## Consequences

* The single largest unknown in the acquisition layer is closed. On the day a
  source is authorized, the remaining risk is selector mismatch — which surfaces
  as `UNRECOGNISED` and a `PARSER_FAILURE`, by design, not as a wrong fare.
* `live.py` gains one seam: a `base_url` parameter and a `_clear_gate` hook. The
  defaults are unchanged — the real base URL and the live gate — so
  `LiveIndigoAdapter` behaves exactly as before.
* CI has no browser, so `test_loopback_browser_proof.py` skips there. The safety
  invariants live in `test_loopback_gate.py` (21 tests), which needs no browser
  and runs everywhere.
* Running it locally needs `pip install -e .[collect]` and
  `playwright install chromium`.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| Run against the real site | Prohibited. This is the whole premise of the project's compliance position |
| A test-only gate bypass | An exemption is an exemption. The gate would no longer mean what we say it means |
| Record real traffic and replay it | We have no permission to generate the traffic in the first place |
| `file://` pages instead of a server | Would not exercise HTTP, navigation between pages, or form submission |
| Leave it unexercised and say so | We did say so. It was still the weakest claim in the repository |
