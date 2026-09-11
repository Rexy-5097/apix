# The collection frame — what we can legitimately sample, and why

**Owner:** [@slazyverse](https://github.com/slazyverse) · **Checkpoint:** 2G · **Date:** 2026-09-11
**Bears on:** AMB-8, OQ-A1, OQ-A3, OQ-2

A sampling frame is a claim about **what exists**. This records which parts of
that claim the sources in hand can support, and — more importantly — which they
cannot.

> **The frame below is an EMPIRICAL frame, not a basket.** It is designed to
> measure whether APIx's cell structure survives contact with Indian schedules.
> It cannot produce a published index, and §5 says exactly why.

---

## 1. What the available sources can define

| Question | Status | Source | What it actually says |
|---|---|---|---|
| **Route existence** — does this city pair carry scheduled service? | **CONFIRMED** | DGCA city-pair traffic (66,453 rows, Apr 2015→Jul 2026, 2,186 pairs) **and** IndiGo tariff sheet (4,729 directed routes, 100 cities) | Two independent sources agree DEL–BOM is served and is the densest domestic pair — 459,060 passengers in July 2026 |
| **Carrier existence on a route** — does *this* carrier fly it? | **PARTIAL** | IndiGo tariff sheet, 2026-09-01 | Confirmed **for IndiGo only**, from IndiGo's own published document. The other four carriers have published equivalents under DGCA Circular 02/2010; none has been obtained |
| **Flight existence** — which flight numbers operate? | **UNKNOWN** | — | No source in hand lists flight numbers. The tariff sheet is route-level: `Route / Type / Distance / Fare-1…Fare-14` |
| **Day-of-week operation** — does it fly on *Tuesdays*? | **UNKNOWN** | — | **Nothing we hold answers this.** See §2 |
| **Expected cells** — the spec I denominator | **UNKNOWN** | — | Cannot be constructed. AMB-8 remains open |

## 2. The IndiGo tariff sheet does **not** give day-of-week operation

Stated plainly because it is the obvious thing to over-read.

The sheet is `ONE WAY DIRECT ECONOMY FARES`, stamped `2026-09-01`, with columns
`Route / Type / Distance / Fare-1 … Fare-14`. It is a **declared fare schedule**
— the fare bands a carrier may charge on a route. It carries:

- ✅ which routes IndiGo serves
- ❌ **no flight numbers**
- ❌ **no days of operation**
- ❌ **no departure times**
- ❌ no aircraft type

A cell key is `route × carrier × day_of_week × apw × fare_class × channel`. The
tariff sheet fixes **one** of those six dimensions. It narrows the universe; it
does not enumerate it.

**What would answer it:** the DGCA-approved seasonal schedule, which is reported
to carry per-flight `days of operation`. It returned **HTTP 403** to the 2F
audit and remains unretrieved. That is the single external artifact standing
between this project and an expected-cell denominator.

## 3. Why the frame cannot be fabricated

The tempting move is to define expected cells as *"whatever we observed last
week"*. That is circular: coverage would then be measured against our own
success, could never fall, and would report 100% on a day the collector was
blocked. `calculate_apix_l` already guards the shape of that error — its
`expected = max(expected_cells, len(states))` fallback now emits a caveat naming
AMB-8 on every output that relies on it.

Spec S is the governing rule: *"None of these may be resolved by choosing a
plausible value."*

---

## 4. Smallest viable frame for the empirical study

| Dimension | Value | Why exactly this |
|---|---|---|
| **Route** | **DEL–BOM**, one-way | Densest domestic pair by DGCA traffic; named in the PS seed list; route existence **CONFIRMED** by two independent sources |
| **Carrier** | **IndiGo (6E)** | The only carrier whose terms have been read, and whose manual carve-out is explicit. Also the densest on this route — and density is the thing under test |
| **Channel** | **AIRLINE_DIRECT** | One channel, so `source_precedence` is vacuous and cannot affect a number (see `source_precedence.yaml`) |
| **APW buckets** | **T+7, T+15, T+30** | Three of the seven §A.3 buckets. Each is an independent weekly chain, so three buckets triples the evidence per collection day at no extra wall-clock |
| **Fare class** | Whatever the consistent selection rule yields | Derived from entitlements, never from the label (§B.4) |
| **Duration** | **30 consecutive days** | Measured, not assumed — see §4.1 |

### 4.1 Why 30 days and not 7

Run against the **shipped** `identity_stability()` on a schedule with **zero
churn** — the same five flight numbers every single day:

```
window   stability   tier    links/chain
   7d       0.00     Tier 3       0
   8d       0.14     Tier 3       0
  14d       1.00     Tier 1       1
  21d       1.00     Tier 1       2
  30d       1.00     Tier 1       4
```

A 7-day window reports **Tier 3 on a perfect schedule**. The cause is
mechanical: §C.1 matches `t` against `t−7`, and inside a 7-day window no two
collection dates are 7 days apart, so nothing recurs and no matched set exists.
**14 days is the floor for any tier measurement; 21 for a chained level and an
observable source transition; 30 also satisfies the PS's "at least 30 days".**

*Note for the register: the dossier's own gate list specifies a "seven days"
spike and says "the matched-item tier is set by the identity-stability number".
Those two cannot both hold. Raised, not silently corrected.*

### 4.2 What this frame yields

**Cells:** 1 route × 1 carrier × 1 channel × 3 APW × 7 weekday chains = **21
cells**, each linking **4 times** in 30 days.

**Density is the open question, not an assumption.** Each cell needs ≥3 matched
items (§D.3) and an item is a `carrier × flight_number`. Whether IndiGo runs ≥3
DEL–BOM flights per weekday per lead time is **exactly OQ-A1** — the dossier's
*dominant risk*. This frame is built to answer it, not to assume it.

---

## 5. What the study can and cannot produce

**CAN**

- Matched items per cell — **OQ-A1**, the dominant risk
- Identity stability per `(route, carrier)` → the tier — **OQ-A3, OQ-2**
- Fare-entitlement determinability, sold-out behaviour, retrieval success rate
- Base/tax/fee decomposition availability — §A.4, PS four-way split
- Freshness sequences `0…6`, carry behaviour, suppression — against real chains
- Intraday fare movement, if sampled at more than one time — **OQ-1**

**CANNOT**

- **A published APIx level.** Route weights need more than one route; carrier
  weights are **AMB-9** and have no source.
- **Route coverage.** The denominator is **AMB-8**.
- **Cross-source spread** — **OQ-A2** needs more than one independent source
  group, and the automation gate leaves one channel available.
- **Any claim about carriers other than IndiGo.**

> A single-route, single-carrier study is a **measurement of the method**, not a
> measurement of Indian airfares. Reporting it as the latter would be the error
> this document exists to prevent.

## 6. Growing the frame

In the order that adds the most evidence per unit of effort:

1. **Second carrier on DEL–BOM** once its terms are read → makes the parent
   stratum (§E.4) non-trivial and carry observable.
2. **Second route** → route weights become exercisable using the DGCA traffic
   already in hand.
3. **Second channel** → `source_precedence` stops being vacuous; **OQ-A2**
   becomes measurable once source groups are established.
4. **T+1 and T+3** → shorter chains, higher volatility, the sharpest test of
   whether the weekly matching holds.

**Sample T+21 alongside**, even though it is not an §A.3 bucket. **OQ-A6** asks
whether to add it so one APIx sub-index aligns with MoSPI's domestic
advance-purchase point — EG §3.9, verified verbatim: *"advance ticket purchase
as 21 days and 60 days for domestic and international travel respectively."*
§A.3 assigns by **exact** lead time, so a T+21 observation not collected during
the window can never be recovered. Collecting it keeps a registered open
question answerable; it does **not** adopt the bucket.
