# ingestion/ — collectors, compliance gate, snapshot store

**Owner:** [@slazyverse](https://github.com/slazyverse)

Everything between a website and a canonical observation.

## What exists

- `store.py` — the SQLite store and content-addressed artifact directory
  (Checkpoint 2H). Every real observation reaches it through the **manual**
  loader, `tools/collection/load_manual.py`.
- `collectors/` — the automated-collection layer: a source-adapter interface, the
  compliance gate, eligibility, earliest-eligible-flight-per-band selection, the
  Saver fare decision, normalisation into the existing canonical `Observation`,
  and a run export with a SHA-256 manifest. See
  [`docs/engineering/automated-collection.md`](../../../docs/engineering/automated-collection.md).

| Adapter | Fixture mode | Live mode |
|---|---|---|
| IndiGo | implemented, tested on SYNTHETIC pages | implemented, **refused by the compliance gate** (`AUTOMATION_PROHIBITED`); has never run |
| Air India, Akasa Air, SpiceJet, Air India Express | — | not implemented |
| Aggregators | — | not implemented |

**No live automated collection has taken place.** Every real observation in
APIx was collected manually.

## The line this layer does not cross

There is **no CAPTCHA solver, no fingerprint evasion, and no identity rotation
intended to defeat access controls.** An access challenge is a stop signal: the
collector backs off, the event is logged, source confidence is reduced, and a
permitted alternate channel takes over.

A national statistical instrument cannot rest on techniques that violate the
terms of the sources it depends on. This is a design constraint, not a
limitation to apologise for.

## What will live here

- Four collection channels, ranked by evidential strength: licensed APIs
  (supplementary, backfill), declared tariff sheets (reference envelope), airline
  portals (**the primary observation channel**), and aggregator portals.
- The compliance gate: robots.txt parsing, crawl-delay, rate limiter, ToS
  register, circuit breaker.
- The source registry, recording what is committed for the prototype and what is
  **deferred rather than silently dropped**.
- Bronze / Silver medallion layers, normalisation, deduplication.
- The content-addressed snapshot store.

## Three rules that are easy to get wrong

- **Effective sample size is computed on independent sources, not source count.**
  Two aggregators reselling one inventory feed are one observation, not two.
- **Collection time is part of the observation.** All collection runs inside a
  fixed daily window, and the timestamp is recorded on every quote. A quote
  pulled at 03:00 and one pulled at 18:00 are two different prices, not two draws
  from the same one. Quotes outside the window are flagged and excluded from the
  index while remaining in the observation store.
- **Sampling uses fixed forward offsets, not fixed departure dates.** With fixed
  departure dates the advance-purchase window collapses as calendar time rises
  and becomes collinear with the time effect. The fix lives in the sampling
  frame, not the estimator.
