# schemas/ — canonical contracts

**Owner:** [@Rexy-5097](https://github.com/Rexy-5097) and [@slazyverse](https://github.com/slazyverse) (joint, per CODEOWNERS)

Written **before any collector**. A schema change breaks either collection or
computation, which is why both domain owners review it.

## Not yet implemented

Checkpoint 1. Nothing here is written until the data contract is frozen.

## What will live here

- The canonical observation record, including `source_type`
  (`LIVE_SCRAPE`, `AUTHORIZED_FEED`, `PUBLIC_DATASET`, `BACKFILLED`, `SYNTHETIC`)
  — these are never blended silently.
- The version vector: `snapshot · methodology · basket · weight · parser ·
  model · code · tier`, carried on every output.
- The canonical fare concept: total payable by an adult passenger for one seat,
  inclusive of taxes, UDF, PSF and GST, and inclusive of platform charges where
  the channel imposes them — because that is what the household pays.
- The canonical fare class, mapped on **entitlements, not labels**. A quote whose
  entitlements cannot be determined is excluded, not guessed into the nearest
  class, and the exclusion rate is published per source.
- Cell keys. **Source is part of the cell key**: an elementary cell never mixes
  channels, so cross-channel differences become a measurable spread rather than
  a hidden contaminant.

Contracts are expressed with Pydantic v2 and Pandera.
