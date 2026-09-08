# api/ — FastAPI and SDMX serialisation

**Owner:** [@Basant-creator](https://github.com/Basant-creator)

## Not yet implemented

Checkpoint 5. No API business logic has been written.

## What will live here

FastAPI application, SQLAlchemy models, and SDMX-JSON serialisers.

## Contracts this layer must honour

- **Vintages are retrievable.** Published values are never overwritten in place.
  Every revision creates a new vintage and the prior one remains retrievable, so
  a user who cited APIx last month can still reproduce exactly what they cited.
- **Provenance walks down to the bytes.** Any index value resolves through cell
  contributions, accepted quotes and raw quotes to SHA-256 snapshot hashes.
- **The version vector is on every response**: `snapshot · methodology · basket ·
  weight · parser · model · code · tier`.
- **Provisional and final are distinguishable.** Provisional publishes the same
  day; final at T+3 after the late-arrival window closes. Weekly and monthly
  aggregates are computed from **final daily values only**, never from
  provisional inputs.
- **`source_type` is never blended silently** — `LIVE_SCRAPE`,
  `AUTHORIZED_FEED`, `PUBLIC_DATASET`, `BACKFILLED`, `SYNTHETIC`.

## The benchmark mapping is configuration, not code

The CPI airfare item label, code, frequency and history are open verification
items. Nothing about them is hard-coded. The benchmark module reads a
configuration file so that if the item turns out to be published only at class or
sub-class level, the comparison degrades by changing one line rather than by
rewriting the validation layer.
