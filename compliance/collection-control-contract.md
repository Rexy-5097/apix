# The collection control contract

**Owner:** [@slazyverse](https://github.com/slazyverse) (per `.github/CODEOWNERS`)
**Status:** contract defined, **no collector implemented** · Checkpoint 2F

This defines what any APIx collector must do. It is not a collector, and
Checkpoint 2F builds none. It exists so that the collector, when written, is
written against a stated contract rather than against whatever the first
implementation happened to do.

The controls it names are the ones
[`context/architecture.md`](../context/architecture.md) already draws in Layer 1:

```
Compliance gate — robots.txt · crawl-delay · rate limiter · ToS register · circuit breaker
```

## C-0 — The line this layer does not cross

From [`CLAUDE.md`](../CLAUDE.md) and
[`src/apix/ingestion/README.md`](../src/apix/ingestion/README.md), unchanged:

> There is **no CAPTCHA solver, no fingerprint evasion, and no identity rotation
> intended to defeat access controls.** An access challenge is a stop signal: the
> collector backs off, the event is logged, source confidence drops, and a
> permitted alternate channel takes over.

**An access challenge is an observation about the source, not an obstacle.** It
is recorded as an outcome (C-6) and it lowers that source's confidence. It is
never something to get past.

This is not negotiable by cadence pressure, spike deadlines or coverage targets.
A national statistical instrument cannot rest on techniques that violate the
terms of the sources it depends on.

## C-1 — No collection from a source whose register entry is not cleared

A source is collectable only when `source_registry/registry.yaml` records, with
quoted evidence and a date:

- `robots_status` that does **not** disallow the path to be fetched; **and**
- `tos_status` of `CLEARLY_PERMITTED` or `PERMITTED_WITH_CONDITIONS`, with the
  conditions transcribed; **and**
- `automated_collection_status` consistent with both.

`NOT_VERIFIED` blocks collection. **Today every one of the 14 sources carries
`tos_status: NOT_VERIFIED`, so the contract currently clears none of them.**

Evidence goes stale. An entry older than the review interval the owner sets
reverts to `NOT_VERIFIED` and blocks until re-audited.

## C-2 — robots.txt is evaluated per path, most-specific wins

Not per domain, and not from the first matching line.

Cleartrip is the worked example and it is in the register: a blanket `Allow: /`
followed by `Disallow: /flights/search*`. **The general permission does not
survive the specific prohibition.** A parser that stops at the first match reads
this exactly backwards and collects the one path the site asked it not to.

Absolute-URL `Disallow` lines (SpiceJet writes three) are non-standard and most
parsers drop them. **Honour the intent anyway.** They are how that source said
its API is off limits, and "the standard let me ignore it" is not a defence
anyone should have to make.

## C-3 — Cadence is declared per source, never global

A crawl-delay applies to the agent it is scoped to. ixigo's `crawl-delay: 10`
sits under `User-agent: MSNBot` and says **nothing** about a general cadence —
reading it as a site-wide permission would be inventing one.

Where no cadence is stated, the collector does not choose an aggressive default.
The register records `NOT_STATED`, and the owner sets a conservative rate that is
written down as an APIx decision rather than inferred from silence.

Spec A.5 constrains this further: all collection runs inside a **fixed daily
window**, and `observation_ts` is recorded on every quote. The window's start and
end are **OQ-1, still open** — a published methodology parameter that is not yet
fixed. The spike is the only thing that can inform it, so the spike should
sample at more than one time of day (see the readiness note in
`docs/engineering/acquisition-readiness.md`).

## C-4 — Rate limiting is per source group, not per source

Spec B.6 collapses sources that share inventory into one group. Two sites in one
group hitting the same upstream inventory at "polite" individual rates are not
polite to that upstream.

Because most groups in the register are `independence: UNKNOWN`, **rate limiting
must currently assume correlation.**

## C-5 — Circuit breaker

Consecutive failures, a rising exclusion rate, or any access challenge opens the
breaker for that source. It stays open until a human closes it.

An open breaker is a **published quality event**, not a silent retry loop. Spec
H.1 already names the class: *"Unavailable source — Excluded; source-day recorded
as a retrieval failure. Never silently substituted from another channel."*

Spec H.3 states the substitution rule directly: `AUTHORIZED_FEED` and
`BACKFILLED` values are **never silently substituted** for a `LIVE_SCRAPE`
observation being claimed.

## C-6 — Every attempt has a recorded outcome, including the failures

**This is the control that does not currently exist anywhere, and it is the one
AMB-8 turns on.**

Spec H.1 requires a source-day to be *"recorded as a retrieval failure"* and
parser failures to be *"excluded with reason code"* that *"counts toward the
exclusion rate alarm"*. The schema has no way to express either: `Observation`
records successes, `Availability` has exactly two members (`AVAILABLE`,
`SOLD_OUT`), and `ExclusionReason` has nine, none of which is a retrieval or
parser failure.

Without an attempt record, these five §H.1 classes are the same empty result:

| §H.1 class | Belongs in the coverage denominator? |
|---|---|
| **No flight** — no service scheduled | **No** — *"Cell not expected; excluded from denominators of coverage"* |
| **Structural missing** — route or flight retired | Yes, then suppressed |
| **Technical missing** — transient | Yes, then carried (§E.4) |
| **Unavailable source** — down, rate-limited, breaker open | Yes — **our failure, not the market's** |
| **Parser failure** | Yes — **our failure, not the market's** |

> **You cannot measure missingness from a table of successes.** A spike run
> without this produces a dataset in which *"no flight was scheduled"* and
> *"we were blocked"* are the same absence — and AMB-8's denominator ends the
> spike exactly as undefined as it began.

The minimum record is one row per `(source, route, travel_date, apw, attempt)`
carrying: the attempt timestamp, the outcome class, the HTTP or transport status,
whether an access challenge was seen, and the count of quotes parsed. A schema
proposal is in `docs/engineering/acquisition-readiness.md`; it is **proposed, not
applied**.

## C-7 — Nothing is collected that the system cannot use or explain

Storage is cheap and a lost fortnight is not, so the spike should collect a
deliberate superset (see the readiness document). But every stored field needs a
stated purpose — a registered open question is a sufficient purpose, a hunch is
not.

## Where this lives

| Path | Owner | Holds |
|---|---|---|
| `/compliance/` | @slazyverse | this contract; future ToS transcripts and review records |
| `/source_registry/` | @slazyverse | `registry.yaml` — the per-source evidence log |
| `/src/apix/ingestion/` | @slazyverse | the collector and the gate that enforces this contract, **not yet written** |

All three paths are already reserved in `.github/CODEOWNERS`, which is where the
locations came from rather than from preference.
