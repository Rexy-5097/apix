# Acquisition readiness — what must be true before day 1

**Owner:** [@Rexy-5097](https://github.com/Rexy-5097) · **Checkpoint:** 2F · **Date:** 2026-09-10
**Verdict:** **NOT READY — blocked by compliance.** No source is cleared, and three schema gaps stand.

Companion documents:
[`source_registry/registry.yaml`](../../source_registry/registry.yaml) ·
[`compliance/collection-control-contract.md`](../../compliance/collection-control-contract.md) ·
[`external-reference-feasibility.md`](external-reference-feasibility.md)

---

## 1. Collection duration — the dossier's own spike design cannot work

**Gate 7 of the dossier specifies:** *"Run the collection spike: one route, two
carriers, one aggregator, five advance-purchase buckets, **seven days**. Measure
retrieval success, base/tax decomposition availability, **flight identity
stability**… **The matched-item tier is set by the identity-stability number**."*

Seven days cannot produce that number. Measured by running the repository's own
shipped `identity_stability()` over a **perfectly stable synthetic schedule** —
the same five flight numbers every single day, zero churn:

```
  window  stability  tier     links/chain  chains linked
     1d       0.00  3                  0     0 of 1
     3d       0.00  3                  0     0 of 3
     7d       0.00  3                  0     0 of 7   <- the Gate-7 design
     8d       0.14  3                  0     1 of 7
    14d       1.00  1                  1     7 of 7
    21d       1.00  1                  2     7 of 7
    28d       1.00  1                  3     7 of 7
```

**A 7-day window reports Tier 3 on a flawless schedule.** The cause is
mechanical and sits in LOCKED text: §C.1 — *"A carrier's flight number on a given
weekday repeats every **seven days**"* — and `matching.py`, which counts a flight
as recurring only when seen on two collection dates **exactly seven days apart**.
Over days 0–6 no two dates are seven apart. §D.1's matched set needs items at `t`
**and** `t−7`, so the window also yields **zero relatives and zero links**.

The APW dimension does not rescue it: no two of §A.3's buckets
`{1,3,7,15,30,45,60}` differ by exactly 7, so the same `(flight, travel weekday)`
can never be reached from two collection dates 7 apart inside one week.

**This is not a weak measurement. It is a systematically wrong one** — it would
read as a catastrophic finding about Indian flight-number stability when it is an
artifact of the window.

| Window | Establishes | Cannot establish |
|---|---|---|
| **3–7 d** | Cross-sectional only: cell occupancy, fare-class prevalence (OQ-A4), raw cross-source spread, retrieval success, access-challenge frequency | **Everything weekly.** Stability 0.00 → Tier 3 for all. Zero matched sets, relatives, links |
| **8 d** | 1 of 7 chains links once; stability 0.14 — still Tier 3 | Six of seven chains invisible |
| **14 d** | **The floor.** Every chain links once. Tier measurable. First relatives, match coverage (OQ-2), OQ-A1's computes/carries ratio, OQ-A3, OQ-A7's band overlap, first carries | No *chained* level. No source transition. No freshness above 6 |
| **21 d** | **The right answer.** Two links per chain → `I(c,t) = I(c,t−7)·J(c,t)` actually executes. Source transitions **between links** (OQ-A9), carry sequences, the freshness 7–13 band, suppression at the ceiling | Seasonality; tier drift across months |

**21 consecutive days** — not "more is better". 28 days adds a third link and
little else, and tier drift is what §B.3's monthly re-measurement is for.

> **The dossier's §24 register and §B.3 carry the same defect**, assigning the
> "7-day spike" to OQ-A3 and to the MatchCoverage floor. Both need ≥14 days.
> Worth its own register entry once PR #6 merges — this checkpoint does not edit
> `OPEN-AMBIGUITIES-checkpoint-2.md` to avoid conflicting with it.

## 2. Schema readiness

Verified field by field against §A.2 (LOCKED) and the `Observation` dataclass on
`main`.

**Present and correct — the entire §A.2 required list:** `origin` ·
`destination` · `travel_date` · `departure_time_local` · `observation_ts` ·
`collection_date` · `carrier` · `flight_number` · `stops` · `duration_minutes` ·
`fare_family_raw` · `channel` · `source_id` · `entitlements` (baggage kg, change,
cancellation) · `payable_fare` · `source_type` · `availability`

**Derived, correctly not stored:** `lead_time_days` · `apw_bucket` ·
`fare_class` · `day_of_week` · `departure_hour_band` · `route`

**Not gaps:** *arrival timestamp* — §A.2 requires `duration_minutes`, not
arrival. *currency* — Notation fixes INR.

### The three real gaps

| Field | Classification | Basis |
|---|---|---|
| `base_fare`, `taxes`, `fees` | **REQUIRED BY LOCKED SPEC** | §A.4: *"Where a base/tax/fee split is available it is **stored and reported**."* No field exists. Also the only way to test whether channel fee structures drift differently — **the exact exposure §D.8's `SOURCE_TRANSITION` rule guards** |
| `source_group` | **REQUIRED BY LOCKED SPEC** | §B.6 and §D.8.1 step 1: *"Collapse sources into independent source groups."* `source_id` cannot express it and `sources.py` implements no grouping. **Effective sample size is uncomputable**, and OQ-A2 is defined *across groups* |
| collection-attempt / outcome record | **REQUIRED BY LOCKED SPEC** | §H.1: *"source-day recorded as a **retrieval failure**"*; parser failures *"excluded with reason code"*. `Availability` has 2 members, `ExclusionReason` has 9, **none is a retrieval or parser failure**. `src/apix/ingestion/` is empty |

### Proposed change — **not applied**

| Field | Type | Req'd | Justification | Safe to add now? |
|---|---|---|---|---|
| `base_fare` | `Decimal \| None` | Optional | §A.4, *stored where available* | **Yes** — optional, additive, no derived quantity changes |
| `taxes` | `Decimal \| None` | Optional | §A.4 | **Yes** |
| `fees` | `Decimal \| None` | Optional | §A.4 | **Yes** |
| `source_group` | `str \| None` | Optional now, required at index time | §B.6, §D.8.1 | **Yes as a field.** Its *values* need the register, and every group is currently `UNKNOWN` |
| `CollectionAttempt` record | new dataclass | New type | §H.1, control §C-6 | **Yes** — a new type touching no existing one |
| `AttemptOutcome` enum | new enum | New type | §H.1's five classes | **Yes** |

**None invents methodology.** Each is mandated by LOCKED text that the schema
currently cannot satisfy, and every addition is optional or a new type, so no
existing observation, golden value or test changes.

`src/apix/schemas/` is **jointly owned** by @Rexy-5097 and @slazyverse in
CODEOWNERS — it is the contract between collection and computation. Both must
approve, which is why this is a proposal and not a commit.

**Do not add:** a `sold_out_reason`, a `parser_confidence`, or any field without
a registered open question behind it. §C-7: storage is cheap, but every stored
field needs a stated purpose, and a hunch is not one.

## 3. Sampling frame — what is needed before choosing routes

The hypothesis under review was ~6–10 routes across dense/medium/thin, every
relevant carrier, ≥2 independent source groups, ≥2 channels.

**Partly validated, partly refuted by the repository.**

**Validated — stratification, not importance.** The dossier already specifies
strata: *"metro–metro trunk, metro–tier 2, tier 2–tier 2, and RCS/UDAN routes"*.
The question OQ-A1 asks is precisely *where carrier-specific cell density
collapses*, so a trunk-only sample would answer *"it's fine"* and be wrong.

**Refuted — the count cannot be chosen yet.** The dossier draws routes *"by
probability proportional to size on DGCA city-pair passenger traffic"* with
*"forced inclusion of the 78-route DGCA-aligned universe"*. **PPS sampling needs
the traffic file**, which §A of the feasibility audit says exists but was not
downloaded. Choosing 6–10 routes now would be choosing them by intuition and
calling it a frame.

**Refuted — "every relevant carrier" is under-specified.** The DGCA Summer 2026
schedule covers **nine** scheduled domestic operators; the dossier's frame names
**five**. On thin and RCS/UDAN routes the excluded four may be most of the
service — which is exactly where OQ-A1's dominant risk lives.

**Newly binding — the frame is constrained by what is collectable.** Four of the
six reachable web sources disallow their fare path. The channel-D half of *"≥2
channels"* may not be satisfiable at all, and that is a register question before
it is a sampling one.

### Required before route selection

1. The DGCA city-pair traffic file, downloaded and column-verified (PPS input).
2. The schedule file (which carriers actually serve which routes on which days).
3. A register with at least one cleared source per intended channel.
4. An owner ruling on five carriers versus nine.

### T+21 — collect it, do not adopt it

**Collect exploratory observations at T+21 alongside §A.3's seven buckets.**

§A.3 admits a quote only at an **exact** bucket lead time, so a T+21 observation
not taken during the spike **never existed** for that window and cannot be
retrofitted. **OQ-A6** asks whether to add T+21 so one APIx sub-index aligns with
MoSPI's 21-day domestic advance-purchase point (EG §3.9). Collecting keeps that
question answerable; not collecting forecloses it.

> **This is not adding a bucket.** T+21 observations are stored and **excluded
> from the index** exactly as §A.3 requires of any non-bucket lead time. Adopting
> T+21 would change the bucket set and move `α` from 1/7 to 1/8 — a methodology
> change, OQ-A6, and the owner's to make.

The same logic applies to **§A.5's collection window (OQ-1, still open)**: sample
at **more than one time of day**. The spike is the only thing that can inform the
window, and a single-time design forecloses it.

## 4. Day-1 preconditions

| # | Precondition | Status |
|---|---|---|
| 1 | At least one source with `tos_status` cleared and quoted evidence | **BLOCKED** — 0 of 14 |
| 2 | Per-source cadence declared where robots.txt is silent | **BLOCKED** — depends on 1 |
| 3 | `source_group` membership evidenced for every source collected | **BLOCKED** — only `mmt_group`, all others UNKNOWN |
| 4 | The three schema additions merged | **PROPOSED, not applied** |
| 5 | Collector honouring the control contract, incl. **§C-6 attempt records** | **NOT BUILT** |
| 6 | DGCA city-pair traffic downloaded and column-verified | **NOT DONE** |
| 7 | Schedule file retrieved; per-flight days-of-operation confirmed | **BLOCKED** — HTTP 403 |
| 8 | Route sample selected from 6 and 7 | **BLOCKED** — depends on both |
| 9 | Duration set to **21 consecutive days** | **DECIDED** — this document |
| 10 | Sampling includes T+21 and >1 time of day | **DECIDED** — this document |

**Nine of ten are open. Two of them (1 and 5) are absolute: without them no
collection may occur at all.**

## 5. What can proceed in parallel

| Work | Blocked by |
|---|---|
| **Re-audit the 5 unreachable sources; retrieve ToS** | Nothing — **the critical path** |
| **Download DGCA traffic; retrieve the schedule file** | Nothing |
| Schema additions (proposal above) | Joint CODEOWNERS review |
| Controlled experiments (dossier's six scenarios) | **Nothing** — synthetic, declares its own basket and weights |
| TPD, on its own branch | Nothing in code (§M.7: *"alternatives, not stages"*); its deliverable needs real data |
| Production pipeline | AMB-8, AMB-9 |
| The spike itself | Preconditions 1–8 |

**The spike does not block the pipeline** (the pipeline is blocked by rulings,
not data) and **the pipeline does not block the spike** (the spike is upstream of
the index). Serialising them would be an error.
