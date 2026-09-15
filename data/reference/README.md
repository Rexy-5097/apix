# `data/reference/` — reference sources. NOT airfare observations.

> ## ⚠ NOTHING IN THIS DIRECTORY IS AN AIRFARE OBSERVATION
>
> These files hold **published reference material** retrieved from official sources. They are inputs
> to *context* — weights, tax structures, benchmarks — and they are **never** inputs to the index.
>
> **No file here may become an `Observation`, enter an APW cell or a departure band, contribute to a
> price relative or a Jevons index, or be written to the collection store.**
>
> The canonical airfare panel is [`../panel.json`](../panel.json): **35 real observations**, DEL–BOM /
> IndiGo, collected manually on 2026-09-12. Nothing in this directory is part of it, adds to it, or
> substitutes for it.

---

## Why the boundary is structural, not a convention

A declared tariff and an airfare observation are different kinds of thing, and conflating them would
put numbers into the index that nobody was ever quoted.

| | An airfare observation (spec A.1) | A declared tariff |
|---|---|---|
| What it is | A **displayed, transactable offer** for one flight on one date | A **fare structure** — the levels a carrier may charge |
| Flight number | Yes | **No** |
| Departure time | Yes — so it can be banded (§B.2.2) | **No** |
| Travel date | Yes — so lead time is computable | **No** |
| Advance-purchase window | Yes — assigned by exact lead time (§A.3) | **No** |
| Can form a cell key | Yes (§B.2.1) | **No** |
| Register rating | `ADMISSIBLE` where terms permit | **`INADMISSIBLE`** — the register names "declared tariff categories" |

With no flight, no departure time and no travel date, a tariff row **cannot** be assigned to an APW
bucket or a band. The impossibility is structural. There is no flag that makes it admissible.

## How the boundary is enforced

Three mechanisms, none of which is a comment:

1. **Location.** The acquisition code lives in `tools/analysis/`, **outside `src/apix/`**. The
   statistics layer imports from `apix.*`; code that is not in `apix.*` cannot be imported by it,
   whatever anyone writes later.
2. **Tests.** [`tests/test_reference_tariff.py`](../../tests/test_reference_tariff.py) asserts that
   the adapter is outside the package, that no module under `src/apix/` imports it, that the record
   declares `is_apix_input: false`, and that **no observation-shaped key appears at any nesting
   depth** of the output.
3. **Self-declaration.** Every record carries `role: REFERENCE_ONLY`, `admissibility: INADMISSIBLE`,
   an `admissibility_basis`, and a `must_never` list, so a reader who opens the file alone still
   cannot mistake it.

## Contents

| File | Source | Role | Acquisition |
|---|---|---|---|
| `alliance_air_tariff.json` | Alliance Air published domestic tariff sheet | Tax/fee structure · **AMB-11 evidence** | **Automated** — [`pull_alliance_tariff.py`](../../tools/analysis/pull_alliance_tariff.py) |

Related, and deliberately kept separate from the panel for the same reason:
[`../mospi_cpi_airfare.json`](../mospi_cpi_airfare.json) — the MoSPI CPI airfare series, a monthly
All-India index number used as an external **benchmark only**.

### `alliance_air_tariff.json`

Regenerate:

```bash
pip install -e ".[reference]"
python tools/analysis/pull_alliance_tariff.py
```

Provenance recorded on every run: source URL, landing page, UTC retrieval timestamp, HTTP status,
content type, content length, **SHA-256 of the retrieved bytes**, the user agent sent, and the
document's own declared effective date.

The PDF itself is **not committed** — `data/reference/.cache/` is gitignored, on the same policy as
`collection-input/raw/`. The bytes are provenance, not product; the hash is what makes them
verifiable.

**What it does and does not contain.** 92 of 92 sector rows parse, 2 flagged `suspect` with reasons
rather than dropped, and no numbered line goes unreported. **Table 2, the station-level fee grid, is
deliberately empty**: that table's text layer interleaves adjacent rows at character level, so no
station-to-fee mapping is recoverable. Three extraction strategies were tried and are recorded in the
output under `station_fees`. Nothing is emitted, because emitting anything would mean guessing which
column a number belongs to — spec A.4 requires components "only where displayed; blank is `None`,
never `0`".

## What this directory does not establish

- **It is not automated airfare acquisition.** APIx has automatically collected **zero fares** from
  any airline or travel website. Retrieving a published document at a fixed URL is a different
  activity from collecting quotes from a fare search, and the register records it as such.
- **It does not resolve AMB-11.** The tariff sheet is quoted evidence that arrival UDF is charged at
  DEL, BOM, JAI and GAU. The ruling on whether `user_development_fee` takes departure UDF only, or
  departure plus arrival, is a methodology decision owned by
  [@Rexy-5097](https://github.com/Rexy-5097) and cannot be closed by an adapter.
- **It does not extend coverage.** Alliance Air does not serve DEL–BOM, and is a different carrier
  class from the ones the pilot measures.
