# APIx formula specification v1

> **Status:** FROZEN for methodology_version `2.0` · **Owner:** @Rexy-5097
> **Date frozen:** 2026-09-08 · **Checkpoint:** 1A
> **Authority:** derived from `docs/dossier/APIx_Engineering_Dossier_v2.1.pdf`
>
> **AMENDED — read this first.** `methodology_version` **2.1** is in force. Its
> delta is [`apix_formula_spec_v2_1.md`](apix_formula_spec_v2_1.md), FROZEN
> 2026-09-10, which is **authoritative for every rule it names**. This document
> remains authoritative for every rule it does not, and its text below is
> unchanged from the 2026-09-08 freeze — the amendment is a separate file
> precisely so that this one never has to be edited to stay true.
>
> Open ambiguities against both documents:
> [OPEN-AMBIGUITIES-checkpoint-2.md](OPEN-AMBIGUITIES-checkpoint-2.md).

This is the authoritative mathematical contract for APIx v1. **No developer
should need to interpret dossier prose to implement the index.** Every symbol
below has a definition, a reference period and an edge-case rule.

Dossier section 13 requires this document to exist and be frozen *before the
index engine is written*, for a stated reason: two developers reading the same
statistical prose implement two different indices. A frozen symbol table removes
the interpretation.

### How to read the status labels

Every decision carries one of:

- **LOCKED** — fixed for `methodology_version 2.0`. Changing it changes the
  methodology version and creates a new parallel series (§R).
- **EMPIRICAL / OPEN** — the *rule* is locked, but a numeric input or a
  structural fact is not yet measured. These are listed in full in §S. **Do not
  resolve one by choosing a plausible value.**

### Changing this document

Any change to a LOCKED item requires: a new `methodology_version`, an ADR, an
update to the golden values in `tests/fixtures/statistical_golden_values.yaml`,
and a parallel-published series with a linking factor. It is not a code change.

---

## Notation

| Symbol | Meaning |
|---|---|
| $i$ | An admissible observation (a quote). §A |
| $c$ | An elementary cell — one recurring product class. §B |
| $r$ | A route (an ordered origin–destination city pair). |
| $t$ | A collection date (a calendar day, in IST). |
| $p_{i,t}$ | Payable fare of observation $i$ on date $t$, in INR. §A.4 |
| $M(c,t)$ | Matched set of cell $c$ between $t$ and $t-7$. §D.1 |
| $J(c,t)$ | Jevons elementary short-term **relative** for cell $c$. §D.2 |
| $I(c,t)$ | Cell index **level**. §E |
| $I(r,t)$ | Route index level. §F.2 |
| $\text{APIx}(t)$ | National APIx-L level. §F.3 |
| $v_{c\mid r}$ | Weight of cell $c$ within route $r$. §G.3 |
| $w_r$ | Weight of route $r$ nationally. §G.2 |
| $w'_r$ | Renormalised route weight over the live set. §F.4 |
| $L_t$ | Live (published, unsuppressed) set at $t$. §I |
| $\text{parent}(c)$ | The stratum a cell inherits from. §E.4 |
| $\gamma_t$ | TPD time-dummy coefficient. §M |

**Units.** All fares are INR, as an exact decimal with 2 places. Monetary
arithmetic uses decimal, never binary floating point, before the log transform.
Index levels are dimensionless, base 100.

---

## A. Data unit — the admissible observation

### A.1 Definition — **LOCKED**

An **observation** (equivalently, a **quote**) is one displayed, transactable
offer for **one adult passenger, one seat, one-way, economy cabin**, captured
from one channel at one instant.

> **Scope, stated explicitly (dossier §06): one-way economy fares only in v1.**
> Round-trip fares are **not** 2 × one-way and are deferred rather than assumed.

### A.2 Required fields — **LOCKED**

An observation is **admissible** only if all of these are present and valid.

| Field | Type | Definition |
|---|---|---|
| `origin` | IATA(3) | Departure airport. |
| `destination` | IATA(3) | Arrival airport. |
| `travel_date` | date | Scheduled local departure date. |
| `departure_time_local` | time | Scheduled local departure time. |
| `observation_ts` | timestamp (IST) | Instant the quote was captured. |
| `collection_date` $t$ | date | IST date of the collection window the quote belongs to. |
| `lead_time_days` | int | $\text{travel\_date} - t$, in whole days. |
| `apw_bucket` | enum | §A.3. |
| `carrier` | IATA(2) | Marketing carrier. |
| `flight_number` | string | Marketing flight number, digits only, no carrier prefix. |
| `stops` | int | 0 for non-stop. |
| `duration_minutes` | int | Scheduled elapsed time. |
| `fare_family_raw` | string | The label the source displayed, stored verbatim. |
| `fare_class` | enum | Canonical class, derived from entitlements. §B.4. |
| `channel` | enum | `AIRLINE_DIRECT`, `AGGREGATOR`, `LICENSED_FEED`, `DECLARED_TARIFF`. |
| `source_id` | string | The specific source within the channel. |
| `entitlements` | struct | §B.4. |
| `payable_fare` | decimal(2) | §A.4. |
| `source_type` | enum | `LIVE_SCRAPE`, `AUTHORIZED_FEED`, `PUBLIC_DATASET`, `BACKFILLED`, `SYNTHETIC`. |

### A.3 Advance-purchase buckets — **LOCKED**

$$\text{APW} \in \{ \text{T+1},\ \text{T+3},\ \text{T+7},\ \text{T+15},\ \text{T+30},\ \text{T+45},\ \text{T+60} \}$$

Assignment is by **exact** `lead_time_days` equal to the bucket value. A quote
whose lead time matches no bucket is **not admissible for the index** and is
stored but excluded.

*Rationale (dossier §06).* Each collection date samples departures at **fixed
forward offsets**, so advance-purchase varies cross-sectionally *within* every
period as well as across it. With fixed departure dates, APW would fall
mechanically as calendar time rises and become collinear with the time effect —
the model would return numbers that do not mean what they appear to mean. **The
fix lives in the sampling frame, not the estimator.**

### A.4 The canonical fare concept — **LOCKED**

$$p_{i,t} = \text{total payable by one adult passenger for one seat}$$

Inclusive of **base fare, all taxes, UDF, PSF, GST**, and **inclusive of platform
convenience charges where the channel imposes them** — because that is what the
household pays.

- **Decomposition is recorded, not required.** Where a base/tax/fee split is
  available it is stored and reported. Where it is not, the total still enters
  the index. **The index is never blocked on a breakdown the site does not
  render.**
- Ancillaries that are *not* required to occupy the seat (paid seat selection,
  meals, extra bags) are **excluded**.

### A.5 The collection window — **LOCKED as a rule, EMPIRICAL as a value**

All collection runs inside a **fixed daily window**. `observation_ts` is recorded
on every quote. Quotes outside the window are **flagged and excluded from the
index while remaining in the observation store**.

*Rationale.* Fares move intraday. A quote at 03:00 and one at 18:00 are two
different prices, not two draws from the same price. If one source is collected
in the morning and another in the evening, a between-source comparison measures
the clock as much as the market.

> **EMPIRICAL / OPEN — OQ-1.** The window's start and end times are a
> **published methodology parameter** and are not yet fixed. See §S.

### A.6 Inadmissibility — **LOCKED**

An observation is rejected from the index (and retained in the store with a
reason code) if any of: a required field in §A.2 is missing; entitlements are
undeterminable (§B.4); `lead_time_days` matches no bucket; `observation_ts` falls
outside the collection window; it is a duplicate (§D.5); or it fails the outlier
rule (§D.7).

**Exclusion rate is published per source.** A rising exclusion rate is the
earliest available signal that a site has been redesigned.

---

## B. The recurring product class

### B.1 Why not "the flight" and why not "the cell" — **LOCKED**

A matched-model index requires the same item observed at $t$ and $t-1$. **A
specific flight on a specific departure date exists exactly once and never
recurs**, so the flight cannot be the item.

But a cell holding one aggregated price per period is a **unit value**, and unit
values are biased whenever the items inside are heterogeneous — the exact
condition that holds for airfares.

APIx therefore defines a **recurring product class**: a bundle of stable
observable characteristics that reappears on a fixed cycle.

> **This is an approximation to matched-model comparability, not literal
> identity.** A Monday flight and the same flight number seven days later are
> different departures under different inventory conditions. This document uses
> "recurring product class" throughout and **never claims the items are the
> same**, because that claim would not survive a statistician's first question.

### B.2 The tier ladder — **LOCKED (rule) / EMPIRICAL (tier assignment)**

**Tier 1 — flight-identity match**

$$c = (\text{carrier},\ \text{flight\_number},\ \text{day\_of\_week},\ \text{apw\_bucket},\ \text{fare\_class},\ \text{channel})$$

Used when flight-number identity is stable across the observation window for
**≥ 70%** of scheduled flights on the route.

**Tier 2 — schedule-slot match**

$$c = (\text{carrier},\ \text{departure\_hour\_band},\ \text{day\_of\_week},\ \text{apw\_bucket},\ \text{fare\_class},\ \text{channel})$$

Used when identity stability falls in **[40%, 70%)**. If flight numbers churn but
the schedule is stable, the recurring product is the slot rather than the number.

**Tier 3 — declared unit value**

Used below **40%** stability. The cell price becomes an **explicit unit value,
published as such**, with within-cell price dispersion reported alongside it as
evidence for or against the homogeneity the fallback assumes.

> **Tier 3 is never used silently.** The tier is recorded per cell in the version
> vector, and Tier-3 weight share is a headline quality metric (§I).

`departure_hour_band` — **LOCKED**: 3-hour bands anchored at 00:00 IST, i.e.
`[00:00,03:00)`, `[03:00,06:00)`, …, `[21:00,24:00)`.

### B.3 Identity stability and match coverage are different quantities — **LOCKED**

Both are needed, and conflating them is a known failure mode (dossier §14).

$$\text{IdentityStability}(r) = \frac{\#\{\text{flight numbers on } r \text{ recurring at the same weekday slot across the window}\}}{\#\{\text{scheduled flights on } r\}}$$

$$\text{MatchCoverage}(r) = \frac{\#\{\text{matched items surviving fare class, APW, channel and entitlement conditioning}\}}{\#\{\text{expected recurring items}\}}$$

> **Stability says the product recurs; coverage says enough of it survives to
> compute a relative from.** Flight numbers can be perfectly stable while the
> usable matched set collapses after conditioning. **Match coverage is the
> statistic-driving metric.**

- **IdentityStability** selects the tier. Thresholds 70% / 40% are **LOCKED**.
- **MatchCoverage** has a floor that is **EMPIRICAL / OPEN — OQ-2**: it is set
  from the seven-day collection spike, *not invented now*.

Tier is a property of **each route**, measured during the spike and **re-measured
monthly**. A route whose tier degrades is flagged.

### B.4 Entitlements define the fare class, not labels — **LOCKED**

One carrier's *saver* is another's *lite* is an aggregator's *cheapest
available*. These labels are marketing artifacts and change without notice.
**Mapping them by name is how an index quietly starts comparing a
hand-baggage-only fare to a flexible one.**

`fare_class` is derived from the entitlement triple:

| Entitlement | Domain |
|---|---|
| `checked_baggage_kg` | int ≥ 0 (0 = hand baggage only) |
| `change_permitted` | `NONE` \| `FEE` \| `FREE` |
| `cancellation_permitted` | `NONE` \| `FEE` \| `FREE` |

$$\text{fare\_class} = f(\text{checked\_baggage\_kg},\ \text{change\_permitted},\ \text{cancellation\_permitted})$$

**LOCKED mapping:**

| `fare_class` | Condition |
|---|---|
| `HAND_ONLY` | `checked_baggage_kg == 0` |
| `STANDARD` | `checked_baggage_kg > 0` **and** not `FLEX` |
| `FLEX` | `change_permitted == FREE` **and** `cancellation_permitted ∈ {FREE, FEE}` |

> A quote whose entitlements cannot be determined is **excluded, not guessed
> into the nearest class**, and the exclusion rate is published per source.

*Note:* `fare_family_raw` is stored for audit and never used for matching.

### B.5 Channel is part of the cell key — **LOCKED**

$$\text{An elementary cell never mixes channels.}$$

Channel C returns a carrier-direct fare; channel D returns the same seat plus a
platform convenience charge; channel A returns a GDS fare with its own fee
structure. **Averaging them produces a number that is not the price of
anything.** Making source part of the cell key turns cross-channel differences
into a **measurable spread** rather than a hidden contaminant.

The carrier-direct versus aggregator gap is published as a **diagnostic series**.
It is interesting in its own right and it exposes parser drift early.

### B.6 Independent sources, not source count — **LOCKED**

Effective sample size is computed on **independent source groups**. Two
aggregators reselling one inventory feed are **one** observation, not two.
Platforms sharing corporate ownership and inventory are collapsed into one group
before any count is reported.

---

## C. Matching frequency — the seven-day comparison

### C.1 Why seven days — **LOCKED**

A carrier's flight number on a given weekday repeats every seven days. Comparing
$t$ with $t-7$ gives price relatives between comparable product classes at
**weekly frequency** — the same frequency at which CPI 2024 collects online
prices.

$$\boxed{\text{APIx is a weekly-matched index published on a rolling daily basis, not a daily-matched one.}}$$

**That distinction is stated, not blurred.**

### C.2 Seven interleaved chains — **LOCKED**

Because the matched item includes `day_of_week`, **each cell advances on its own
seven-day chain**. The daily series is an aggregate over **seven interleaved
weekday chains**, each contributing its most recent level.

> **A Monday and a Tuesday observation are never differenced against each
> other.** Any implementation that differences adjacent calendar days is wrong.

### C.3 Chain freshness — **LOCKED**

For cell $c$ at publication date $t$, define

$$\text{freshness}(c,t) = t - \max\{\,s \le t : J(c,s) \text{ was computed}\,\}$$

measured in days, $\in [0, 6]$ under normal operation.

- `freshness` is **recorded per cell** and published as a distribution.
- A cell whose freshness exceeds **13 days** (two missed weekly links) is
  **suppressed** (§I), not carried further.

### C.4 Relative versus level — the most common implementation error — **LOCKED**

$$J(c,t) \ \text{is a RELATIVE (dimensionless ratio,} \approx 1).$$
$$I(c,t) \ \text{is a LEVEL (base 100).}$$

> The construction is **relative at the elementary level, level at every level
> above it**. Jevons produces a short-term relative; that relative chains into a
> cell index level; **levels are aggregated**.
>
> **Aggregating relatives directly, or dividing one short-term relative by
> another, does not produce an index** and is the most common way this
> construction goes wrong.

---

## D. Jevons elementary short-term relative

### D.1 The matched set — **LOCKED**

$$M(c,t) = \{\, i : i \in \text{admissible}(c,t) \ \wedge\ i \in \text{admissible}(c,t-7) \,\}$$

where an item's identity within a cell is its **matching key** (§B.2).

$$\boxed{\text{Unmatched items enter NEITHER side of the ratio.}}$$

An item present at $t$ but not $t-7$ contributes nothing — it does not enter the
numerator, and it does not enter as a new item at 100.

### D.2 The relative — **LOCKED**

$$J(c,t) \;=\; \prod_{i \in M(c,t)} \left( \frac{p_{i,t}}{p_{i,t-7}} \right)^{\frac{1}{|M(c,t)|}}$$

Equivalently, computed in logs for numerical stability (**required**):

$$J(c,t) \;=\; \exp\!\left( \frac{1}{|M(c,t)|} \sum_{i \in M(c,t)} \left[ \ln p_{i,t} - \ln p_{i,t-7} \right] \right)$$

**Implementation requirement — LOCKED.** The log form is normative. Direct
multiplication of ratios overflows and loses precision for large $|M|$, and two
implementations must agree bit for bit (§P).

### D.3 Minimum sample — **LOCKED**

$$|M(c,t)| \ \ge\ \texttt{min\_matched\_items\_per\_cell} = 3$$

Below this, $J(c,t)$ is **undefined** and the cell publishes no relative. The
carry rule in §E.4 applies.

### D.4 Duplicates — **LOCKED**

Two observations in the same cell at the same $t$ with identical
$(\text{carrier}, \text{flight\_number}, \text{travel\_date},
\text{departure\_time\_local}, \text{fare\_class}, \text{channel},
\text{source\_id})$ are **duplicates**. Deduplication keeps the observation with
the **latest `observation_ts` within the collection window**; the others are
stored with a duplicate reason code. Deduplication happens **before** $M(c,t)$ is
formed.

### D.5 Missing observations — **LOCKED**

An item absent at $t$ or at $t-7$ is simply not in $M(c,t)$. **No imputation
occurs at the item level.** Imputation is a cell-level concept only (§H).

### D.6 Sold-out observations — **LOCKED (rule) / EMPIRICAL (its effect)**

$$\boxed{\text{A sold-out flight is not a missing price. It is a disappeared item.}}$$

It is recorded as `SOLD_OUT` and **excluded from $M(c,t)$**, exactly as any other
unmatched item.

> Treating a sell-out as an ordinary missing value can bias the index **downward**
> where low availability is systematically associated with higher prices.
>
> **EMPIRICAL / OPEN — OQ-3.** That association is *plausible but not assumed*.
> It is tested by comparing realised prices in cells shortly before and after
> sell-out, and **the test result is reported**. No correction is applied in v1.

### D.7 Outliers — **LOCKED**

Applied to log price relatives $\ln(p_{i,t}/p_{i,t-7})$ **within a cell**, before
§D.2:

$$\text{flag } i \iff \left| \ln\frac{p_{i,t}}{p_{i,t-7}} - \operatorname{med}_c \right| > 5 \times \operatorname{MAD}_c$$

where $\operatorname{med}_c$ and $\operatorname{MAD}_c$ are the median and median
absolute deviation of log relatives within cell $c$ at $t$. Flagged observations
are **excluded from $M(c,t)$**, retained in the store, and **counted in a
published flag rate**.

The rule is applied only when $|M(c,t)| \ge 5$; below that the dispersion
estimate is not meaningful and **no flagging occurs**.

**Degenerate dispersion — LOCKED.** If $\operatorname{MAD}_c = 0$ (more than half
the log relatives are identical), the threshold collapses to zero and *every*
non-identical observation would be flagged. That is a detector destroying the
data it is meant to protect. **When $\operatorname{MAD}_c = 0$, no flagging
occurs.**

*This case is not hypothetical: a cell in which a fare is unchanged across most
matched items — common at long lead times — produces exactly it. The dossier does
not state a rule here; this fills the gap explicitly rather than leaving it to
whoever writes the estimator.*

*Median/MAD, not mean/SD, because the estimator must not be dragged by the very
contamination it is detecting.* MAD is **not** rescaled by 1.4826; the threshold
5 is expressed in raw MAD units. **This is a definitional choice and must be
implemented exactly as written.**

---

## E. Cell index level

### E.1 Base — **LOCKED**

$$I(c, t_0) = 100$$

where $t_0$ is the cell's **own** first publishable date — the first $t$ at which
$J(c,t)$ is defined.

### E.2 The chain — **LOCKED**

$$I(c,t) \;=\; I(c,\,t-7)\ \cdot\ J(c,t)$$

Note the lag is **7 days**, not one period. Each cell advances on its own weekly
chain (§C.2).

### E.3 First observation — **LOCKED**

A cell observed for the first time has no $I(c,t-7)$. It is **not published**
until either (a) it accumulates a defined $J(c,t)$ and takes $I=100$ per §E.1 as
a *standalone* cell, or (b) it enters against an existing parent per §J. **Rule
(b) takes precedence whenever a parent exists**, because entering at 100 inside a
live aggregate injects a spurious jump (§J).

### E.4 Carry rule when $J$ is undefined — **LOCKED**

If $J(c,t)$ is undefined (no matched items, or $|M| < 3$):

$$I(c,t) \;=\; I(c,\,t-7)\ \cdot\ J(\text{parent}(c),\,t)$$

The cell inherits the **price relative of its parent stratum**, not the parent's
level.

$$\text{parent}(c) = (\text{route},\ \text{apw\_bucket},\ \text{fare\_class},\ \text{channel})$$

i.e. the cell key with carrier and flight-identity dropped.

If $J(\text{parent}(c),t)$ is also undefined, the cell is **suppressed** (§I).
**Nothing more sophisticated ships in v1.**

### E.5 Disappearance and resumption — **LOCKED**

A cell that produces no defined $J$ and cannot carry is suppressed. If it later
reappears:

- resumption **within 13 days** of its last published level → the chain resumes
  from $I(c, t_{\text{last}})$;
- resumption **after 13 days** → the cell is treated as **new** and enters per
  §J.

*The 13-day boundary is two missed weekly links (§C.3). Beyond it, the assumption
that the same product class is being tracked is no longer defensible.*

---

## F. Young / Modified Laspeyres aggregation

> **Terminology — LOCKED.** The dossier specifies **Young / Modified
> Laspeyres**. The term *Lowe* is **not** used in APIx, and an implementation or
> document that introduces it is non-conforming.

### F.1 Form — **LOCKED**

Aggregation is a **weighted arithmetic mean of index LEVELS**, with weights fixed
from a reference period that is **prior to and independent of** the comparison
period.

$$\text{Aggregate}(t) = \sum_k \omega_k \cdot I(k,t), \qquad \sum_k \omega_k = 1$$

*This is the Young form: fixed reference-period expenditure shares applied to
current index levels. It is what MoSPI itself uses in CPI 2024, which is the
point — APIx-L must be adoptable without a methodology change.*

### F.2 Route index — **LOCKED**

$$I(r,t) \;=\; \sum_{c \in r \cap L_t} v_{c\mid r} \cdot I(c,t), \qquad \sum_{c \in r \cap L_t} v_{c\mid r} = 1$$

### F.3 National index — **LOCKED**

$$\boxed{\ \text{APIx}(t) \;=\; \sum_{r \in L_t} w'_r \cdot I(r,t)\ }$$

### F.4 Renormalisation on suppression — **LOCKED**

Let $L_t$ be the live set at $t$. Then

$$w'_r \;=\; \frac{w_r}{\sum_{j \in L_t} w_j} \qquad \text{for } r \in L_t$$

and identically for $v_{c\mid r}$ within a route.

> **This is the subtle one.** Dropping a route without renormalising **silently
> reweights everything else**. The weight vector is asserted to sum to one in a
> unit test that runs on **every publication** (§Q, INV-1).

### F.5 Period structure — **LOCKED**

- Weights $w_r$, $v_{c\mid r}$ are **fixed for the index year** and do not vary
  with $t$.
- Levels $I(c,t)$ vary daily (each on its own weekly chain).
- Therefore **only levels move within a year**; weights move only at the annual
  update (§K).

---

## G. Weight hierarchy

### G.1 The three tiers — **LOCKED**

```
CPI 2024 expenditure weight  (COICOP 2018, Division 07 Transport, weight 8.796)
  from HCES 2023–24                                    ← NOT OURS TO SET
        │
        ▼
  Airfare item index  ← APIx sits here
        │
        ▼
  w[r]   route weights      — DGCA passenger shares    ← §G.2
        │
        ▼
  v[c|r] within-route       — APW × fare class × channel composition  ← §G.3
```

> **Household expenditure weights sit above APIx and are not ours to set.**
> Conflating the two invites the question of why aviation traffic data is
> weighting a consumption index. DGCA passenger shares weight routes **within**
> APIx; they never touch the expenditure weight above it.

### G.2 Route weights $w_r$ — **EMPIRICAL / OPEN — OQ-4**

**Intended source (LOCKED as intent):** DGCA city-pair passenger traffic,
**prior calendar year, lagged and held fixed** for the index year.

> **OPEN.** DGCA publishes monthly traffic statistics, but city-pair-level
> passenger volumes at the granularity this design assumes **may not be openly
> downloadable**. This is a gate-1 item.
>
> **Declared fallback (LOCKED):** scheduled **seat capacity** by city pair,
> derived from published airline schedules — a proxy for passenger volume **with
> a stated and testable bias**. If the fallback is used, `weight_version` records
> it and the bias direction is published alongside the index.

### G.3 Within-route weights $v_{c\mid r}$ — **PARTLY LOCKED**

$$v_{c\mid r} \;=\; \underbrace{\alpha_{\text{apw}}}_{\text{§G.4}} \times \underbrace{\beta_{\text{fare\_class}\mid r}}_{\text{observed share}} \times \underbrace{\delta_{\text{channel}\mid r}}_{\text{observed share}} \Big/ \text{(normalising constant)}$$

$\beta$ and $\delta$ are **observed composition shares in the weight reference
period**, held fixed for the index year — **LOCKED**.

### G.4 Advance-purchase weights $\alpha_{\text{apw}}$ — **LOCKED as a declared v1 choice**

$$\alpha_{\text{apw}} = \tfrac{1}{7} \quad \text{for each of the 7 APW buckets}$$

> **A booking-curve weighting requires a lead-time distribution that no public
> Indian source is known to publish. Inventing one would be worse than not having
> one.**
>
> v1 therefore uses **equal weights across APW buckets as a declared, documented
> choice**, accompanied by a **sensitivity analysis** showing how far the index
> moves under plausible alternative curves. **Booking-curve weighting is claimed
> only once a data source for it exists.**

**Sensitivity band — LOCKED procedure.** The index is recomputed under at least
three alternative APW curves (front-loaded, uniform, back-loaded), and the
**maximum absolute deviation in month-on-month growth** is published as the APW
weighting sensitivity band. The alternatives are labelled *illustrative
alternatives*, never as estimates of the true curve.

### G.5 Invariants — **LOCKED**

- $\sum \omega = 1$ at every level, **before and after** suppression and
  renormalisation.
- $\omega_k \ge 0$ for all $k$. A negative weight is a defect, not a value.
- Weights are **fixed within the index year**.

---

## H. Missing and sold-out data

### H.1 Taxonomy — **LOCKED**

| Class | Definition | v1 treatment |
|---|---|---|
| **Technical missing** | Collection ran, source reachable, quote absent for a transient reason. | Item excluded from $M$. Cell-level carry (§E.4) if $J$ undefined. |
| **Structural missing** | The product no longer exists (route dropped, flight retired). | Cell suppressed (§I). **Not** carried indefinitely. |
| **Sold out** | Flight exists, no seat available at any fare in the class. | Recorded `SOLD_OUT`, excluded from $M$. §D.6. |
| **No flight** | No service scheduled on that weekday/slot. | Cell not expected; excluded from denominators of coverage. |
| **Unavailable source** | Source down, rate-limited, or circuit-breaker open. | Excluded; **source-day recorded as a retrieval failure**. Never silently substituted from another channel. |
| **Parser failure** | Page fetched, fields unextractable. | Excluded with reason code; **counts toward the exclusion rate alarm**. |

### H.2 The imputation rule — **LOCKED**

$$\boxed{\text{Imputation is deliberately conservative and deterministic.}}$$

A missing cell inherits the **price relative of its parent stratum** where one is
available (§E.4). Where none is, the cell is **suppressed** and the **coverage
loss is published**.

> **Nothing more sophisticated ships in v1.** Model-based completion — temporal
> matrix factorisation and similar — is a **fitted, stochastic method** and
> belongs in the analytics layer as a candidate improvement evaluated against the
> deterministic rule, **not embedded in the index path where it would quietly
> break the reproducibility guarantee**.

### H.3 Never blend source types — **LOCKED**

`source_type` is carried on every record and rendered distinctly.
`AUTHORIZED_FEED` and `BACKFILLED` values are **never silently substituted** for
a `LIVE_SCRAPE` observation being claimed.

---

## I. Suppression thresholds

**All LOCKED** (dossier §08).

| Rule | Threshold | Action on breach |
|---|---|---|
| `min_matched_items_per_cell` | **3** | Cell publishes no relative; carry per §E.4. |
| `max_cell_imputation` | **40%** of a cell's periods in the trailing 8 weeks | Cell **suppressed rather than imputed**. |
| `min_route_coverage` | **60%** of expected cells | **Route suppressed**, weights renormalised (§F.4). |
| `max_suppressed_weight` | **15%** of total weight | APIx **publishes with a quality caveat**. |
| `max_tier3_weight` | **25%** of total weight | **Unit-value caveat shown on the headline.** |
| `freshness` | **> 13 days** | Cell suppressed (§C.3). |

### I.1 Publish / suppress / carry / re-enter — **LOCKED**

- **Publishes** — $J(c,t)$ defined with $|M| \ge 3$, freshness ≤ 13 d, cell
  imputation ≤ 40%.
- **Carries** — $J$ undefined but the parent relative exists and the imputation
  and freshness limits still hold.
- **Suppressed** — any threshold above is breached, or the parent relative is
  also undefined.
- **Re-enters** — per §E.5: resume the chain within 13 days, otherwise enter as a
  new cell per §J.

Suppression **never** silently removes weight: §F.4 renormalisation is
mandatory, and the suppressed weight share is published.

---

## J. New cell entry

### J.1 The rule — **LOCKED**

$$\boxed{\ I(c_{\text{new}},\,t) \;=\; I(\text{parent}(c_{\text{new}}),\,t)\ }$$

**A new cell enters at its parent's current level, never at 100.**

> Entering at 100 **injects a spurious jump into the aggregate**: a newly
> appearing fare would be recorded as though the price had moved from the base
> period to the parent's level in a single step. **A newly appearing fare is not
> a price change.**

### J.2 Consequences — **LOCKED**

- On the entry date, the new cell contributes **no** price movement — it
  contributes a level identical to its parent, so $I(r,t)$ is unchanged by the
  entry itself.
- The cell begins contributing movement from its **first defined $J$**, one weekly
  link later.
- If the parent is itself unavailable, the cell is **held out** until a parent
  level exists. It is never seeded at 100 inside a live aggregate.

---

## K. Annual linking

### K.1 Within-year chaining vs. year-to-year linking — **LOCKED**

These are different operations and must not be conflated:

- **Within-year chaining** (§E.2) — $I(c,t) = I(c,t-7) \cdot J(c,t)$. Continuous,
  weekly, per cell.
- **Year-to-year linking** (§K.2) — a **single** re-referencing at the index-year
  boundary when weights are updated.

### K.2 The linking factor — **LOCKED**

$$LF = \frac{\text{mean level of the new reference year}}{\text{mean level of the old reference year}}$$

$$I_{\text{linked}}(t) = I_{\text{old}}(t) \cdot LF$$

This is the same discipline CPI uses across base revisions.

### K.3 Historical continuity — **LOCKED**

- Published historical values are **never overwritten in place**. The linked
  series is a **new vintage**; the prior vintage remains retrievable (§R).
- `weight_version` and `basket_version` both change at a link.
- A link is **not** a revision (§R.2). It is applied **forward from a stated
  date**.

---

## L. APIx-L — the deterministic pipeline

### L.1 The pipeline — **LOCKED**

```
raw observations
   │  §A.2/A.6  admissibility filter
   ▼
admissible observations
   │  §D.4      deduplication
   ▼
deduplicated observations
   │  §B.2      cell assignment at the route's tier
   ▼
cells
   │  §D.1      matched set M(c,t) against t-7
   │  §D.7      outlier flagging within cell
   ▼
   │  §D.2      Jevons relative  J(c,t)          ← RELATIVE
   ▼
   │  §E.2/E.4  chain / carry    I(c,t)          ← LEVEL
   │  §J        new-cell entry
   │  §I        suppression
   ▼
   │  §F.2      Young / Mod. Laspeyres over cell LEVELS  → I(r,t)
   │  §F.4      renormalisation over the live set
   ▼
   │  §F.3      Young / Mod. Laspeyres over route LEVELS → APIx(t)
   ▼
APIx-L(t)  +  version vector  §O
```

### L.2 Determinism requirement — **LOCKED**

$$\text{APIx-L} = g\big(\text{snapshot\_id},\ \text{methodology\_version},\ \text{basket\_version},\ \text{weight\_version},\ \text{code\_version}\big)$$

$g$ is a **pure function**. It contains no random number generation, no fitted
model, no wall-clock or locale dependence, and no iteration over an unordered
collection whose order affects the result (§Q, INV-5).

**No import of `sklearn`, `lightgbm`, `xgboost`, `torch`, `anthropic` or
`openai` may appear anywhere under `src/apix/statistics/`** — enforced by
`tests/test_architecture.py`.

### L.3 APIx-L chains too, and this document says so — **LOCKED**

> This methodology argues that daily chaining of naive averages accumulates
> composition effects. **APIx-L is itself a chained index, and intellectual
> honesty requires saying that it is therefore not drift-free by construction.**
>
> What differs is the **exposure**. Naive chaining links *unmatched aggregates*,
> so every change in the quote mix enters the link. APIx-L links **matched items
> only**, at weekly frequency, within cells that already hold carrier, fare class,
> channel and advance-purchase window fixed.
>
> The residual drift is **bounded by matching quality and measured rather than
> asserted**: controlled-experiment scenario A reports the terminal value **for
> APIx-L as well as** for the naive index.

---

## M. APIx-TPD

### M.1 Specification — **LOCKED**

$$\ln P_{i,t} \;=\; \alpha \;+\; \sum_{t} \gamma_t D_t \;+\; \sum_k \beta_k X_{i,k} \;+\; \varepsilon_{i,t}$$

$$\text{index}_t = \exp(\gamma_t)$$

- **Dependent variable:** $\ln P_{i,t}$, the natural log of the payable fare
  (§A.4) of an individual **quote** — the estimation is on the **quote-level
  panel**, not on cell aggregates.
- $D_t$ — time dummies; one period omitted as the reference.
- $X_{i,k}$ — product characteristics (§M.2).
- Estimator: OLS. **Standard errors clustered by route** — LOCKED.

### M.2 Included characteristics — **LOCKED**

Route · carrier · stops · departure-hour band · flight duration · day-of-week
type · advance-purchase bucket · baggage allowance · refundability · fare family
· channel.

### M.3 Deliberately excluded characteristics — **LOCKED**

$$\boxed{\text{seats remaining · availability signals · promotion flags · inventory-depth proxies}}$$

> These are **plausibly jointly determined with demand and fare formation**.
> Conditioning on them would **absorb the very movement being measured**.
>
> Adding any of them is a **methodology change**, not a modelling improvement.

### M.4 Estimation thresholds — **LOCKED**

Fixed before implementation. **A window failing any threshold produces no
published TPD value for that period; the failure and its reason are recorded.**

| Guard | Threshold | Action on breach |
|---|---|---|
| `window_length` | **21 days** default; swept over **15 / 21 / 25 / 31** | Spread across windows **published, not hidden** |
| `min_quotes_window` | **1,500** | Window **rejected** |
| `min_quotes_per_level` | **30** per characteristic level | Level pooled into an `other` category; **pooling recorded** |
| `min_quotes_per_route` | **60** per window | Route **excluded from that window's estimation** |
| `condition_number` | reject above **30** | Window **rejected as near-singular** |
| `max_missing_characteristic` | **10%** of quotes | Characteristic **dropped from the specification**; drop recorded in the version vector |
| `min_periods_overlap` | **7 days** for splicing | Splice **deferred**; previous window **extended** |

### M.5 Splice — **LOCKED**

Windows are joined by **mean splicing** over the overlap, so that **published
values are not revised**.

For consecutive windows $W_{j}$, $W_{j+1}$ with overlap $O$ (at least
`min_periods_overlap` = 7 days):

$$\text{splice factor} \;=\; \exp\!\left( \frac{1}{|O|} \sum_{t \in O} \left[ \ln \text{index}^{W_j}_t - \ln \text{index}^{W_{j+1}}_t \right] \right)$$

$$\text{APIx-TPD}(t) = \text{index}^{W_{j+1}}_t \times \text{splice factor} \quad \text{for } t \text{ beyond } W_j$$

If $|O| < 7$, the splice is **deferred and the previous window extended**.

### M.6 Failure behaviour — **LOCKED**

A rejected window yields **no published TPD value** for its periods — not an
interpolated one. The rejection and its reason are recorded and published.

### M.7 The estimators are alternatives, not stages — **LOCKED**

$$\boxed{\text{TPD output must NEVER feed APIx-L. Jevons output must NEVER feed the TPD regression.}}$$

> Feeding Jevons output into TPD would **strip the within-cell variation the
> hedonic model needs and double-count the aggregation**.

Enforced structurally: `src/apix/statistics/tpd/` and
`src/apix/statistics/elementary/` do not import from each other, and
`src/apix/statistics/index/` composes them without cross-feeding.

### M.8 Comparing the two series — **LOCKED**

$$\boxed{\text{Compare GROWTH RATES, never LEVELS.}}$$

> The two estimators accumulate along different paths, so a **level gap between
> them is an artifact of divergence since the base period**, not a monthly
> composition effect.

The published quantity is **method divergence** = (APIx-L growth) − (APIx-TPD
growth), in percentage points, over a stated horizon.

---

## N. Bootstrap uncertainty

### N.1 Resampling unit — **LOCKED**

$$\text{The ELEMENTARY CELL is the resampling unit.}$$

Cells are resampled **with replacement**.

### N.2 Complete-path recomputation — **LOCKED**

For each draw, **the entire index path is recomputed — chain included**, so the
serial dependence the chain creates is **carried into the interval rather than
ignored**.

> **Bootstrapping single days and reporting the result as an interval on a growth
> rate would be wrong, and is a common error.**

### N.3 Draws, seed and interval — **LOCKED**

| Parameter | Value |
|---|---|
| `n_draws` | **1000** |
| Interval | **percentile** (2.5th, 97.5th) → nominal 95% |
| Reported on | **both levels and growth rates** |
| Seed | derived **deterministically from the version vector** and recorded with the output |

$$\text{seed} = \text{SHA256}\big(\text{snapshot\_id} \Vert \text{methodology\_version} \Vert \text{basket\_version} \Vert \text{weight\_version} \Vert \text{code\_version}\big) \bmod 2^{32}$$

> **Two runs of the same publication reproduce the same interval to the last
> digit. A confidence interval that moves between runs of identical inputs is a
> defect, not sampling variation.**

### N.4 Runtime budget — **EMPIRICAL / OPEN — OQ-5**

One thousand draws, each recomputing the full path and refitting TPD over the
rolling window, **is not free**.

> The cost is **measured on synthetic data of realistic size during the
> verification gate, before the interval is promised on screen**. If the run
> exceeds the publication window, `n_draws` is **reduced and the resulting
> interval-width penalty is reported — not the interval quietly dropped**.

---

## O. Version vector

### O.1 Fields — **LOCKED**

Carried on **every** published output.

| Field | Meaning | Affects APIx-L | Affects APIx-TPD |
|---|---|---|---|
| `data_snapshot_id` | Content-addressed id of the immutable observation snapshot | ✅ | ✅ |
| `methodology_version` | This document's version | ✅ | ✅ |
| `basket_version` | Route/cell universe in force | ✅ | ✅ |
| `weight_version` | Weight vector in force (§G) | ✅ | ➖ (TPD is unweighted) |
| `parser_version` | Extraction logic that produced the observations | ✅ | ✅ |
| `model_version` | TPD specification version | **N/A** | ✅ |
| `code_version` | Git commit of the statistics layer | ✅ | ✅ |
| `tier` | Matched-item tier, **recorded per cell** | ✅ | ➖ |

$$\boxed{\text{For APIx-L, } \texttt{model\_version} = \text{N/A. This is a load-bearing assertion, not a formatting detail.}}$$

An APIx-L output carrying a non-null `model_version` means a fitted model has
entered the deterministic path, and it is a **defect**.

### O.2 Rendering — **LOCKED**

```
snapshot 20260906 · methodology v2.0 · basket 2026-Q3 · weight dgca-2026-09 ·
parser 2.4 · model N/A · code 7f3a91c · tier 1
```

---

## P. Reproducibility

### P.1 The guarantee — **LOCKED**

$$\text{same } (\text{snapshot\_id},\ \text{methodology\_version},\ \text{basket\_version},\ \text{weight\_version},\ \text{code\_version}) \implies \text{bit-identical APIx-L}$$

### P.2 What this forbids — **LOCKED**

- Wall-clock or timezone-dependent behaviour inside the statistics layer.
- Iteration over an unordered container where order affects the result. Cells and
  routes are processed in a **stable, explicitly sorted key order**.
- Locale-dependent number parsing or formatting.
- Any unseeded stochastic procedure (§N.3).
- Parallelism whose reduction order is nondeterministic. Floating-point addition
  is not associative; a parallel sum that reduces in a varying order **breaks
  bit-identity**. Reductions are ordered.

### P.3 Verification — **LOCKED**

A publication is re-run from its recorded version vector and compared **bit for
bit** against the stored output. This runs on every publication, not only in CI.

---

## Q. Invariants

These must hold for **any** correct implementation. Line coverage is the wrong
target: **an index engine can reach full coverage while computing the wrong
number.**

> **REPORTED INCONSISTENCY (dossier §13).** The dossier's invariant list states:
> *"Scaling every price by k scales the index by k; the price relatives are
> unchanged."* Those two clauses cannot both hold. If every price in both periods
> is scaled, the relatives are unchanged **and so is the index**. If only the
> current period is scaled, the index scales by $k$ **but the relatives change**.
> The sentence conflates two distinct and individually correct properties.
>
> This specification does **not** silently pick one. It splits them into
> **INV-4a** (scale invariance) and **INV-4b** (homogeneity), both of which are
> true, testable, and separately covered by golden values G-04 and G-15. This is
> raised for the dossier author's confirmation.

| ID | Invariant |
|---|---|
| **INV-1** | Weight vectors sum to 1, **before and after** any suppression and renormalisation. |
| **INV-2** | All weights are $\ge 0$. |
| **INV-3** | Identical prices in both periods produce an index of **exactly 100** (and $J = 1$). |
| **INV-4a** | *Scale invariance.* Scaling every price in **both** periods by $k > 0$ leaves $J$ and every index level **unchanged**. |
| **INV-4b** | *Homogeneity.* Scaling every price in the **current** period only by $k > 0$ multiplies $J(c,t)$ by exactly $k$. |
| **INV-5** | Reordering observations within a period changes **no** output. |
| **INV-6** | The index equals **100 in the base period by construction**. |
| **INV-7** | Missing cells follow the declared rule (§E.4/§H.2) and nothing else; **a cell is never silently dropped**. |
| **INV-8** | Every threshold in §I and §M.4 has a test that crosses it in **both** directions. |
| **INV-9** | Recomputing from the same version vector reproduces the published value **bit for bit**. |
| **INV-10** | A new cell entering changes **no** aggregate level on its entry date (§J.2). |
| **INV-11** | `src/apix/statistics/` imports nothing from `analytics`, `ai`, or the forbidden library set. |
| **INV-12** | For APIx-L outputs, `model_version` is `N/A`. |

### Q.1 Comparison tolerance — **LOCKED**

Invariants INV-3, INV-4a, INV-6 and INV-10 are *exact* statements about real
arithmetic but are evaluated in binary floating point after the log transform
(§D.2). They are asserted to a **relative tolerance of 1e-12**, not to bit
equality.

*This is not a loosening. It was measured: the INV-10 golden case (G-09)
evaluates to `106.00000000000001` against an exact `106.0` — a 1-ulp artifact of
representing 0.32 in binary, not a methodology error. Asserting exact equality
there would produce a permanently failing test that a future maintainer would
"fix" by weakening the invariant.*

**INV-9 (reproducibility) is the exception and is asserted bit for bit** (§P.1).
It compares two runs of the *same* computation, where any difference is a defect
rather than representation noise.

---

## R. Publication, vintages and revision

### R.1 Release calendar — **LOCKED**

| Stage | Timing | Status |
|---|---|---|
| Collection window | Fixed daily window (OQ-1) | Quotes outside it flagged and excluded |
| Data cutoff | Close of the collection window | Late arrivals **stored, not included** |
| **Provisional** | Same day, within hours of cutoff | Carries its own quality triad |
| **Final** | **T+3 days**, after the late-arrival window closes | Not revised except per §R.2 |
| Weekly / monthly aggregates | Computed from **final daily values only** | **Never** built on provisional inputs |

### R.2 Revision triggers — **LOCKED**

**Revises the series:** a parser defect that produced wrong values, once
corrected; a source correcting data it previously served; an annual weight
update, applied **forward from a stated date**.

**Does *not* revise the series:** a **methodology change** — that creates a new
`methodology_version` and a **new series published in parallel with a linking
factor**, the same discipline CPI uses across base revisions; late-arriving
quotes after T+3; a better model becoming available.

### R.3 Vintages — **LOCKED**

> **Published values are never overwritten in place.** Every revision creates a
> **new vintage**; the prior vintage remains retrievable through the API. A user
> who cited APIx last month can still reproduce exactly what they cited.

---

## S. Open empirical questions

**None of these may be resolved by choosing a plausible value.** Each requires a
primary document or a live collection run.

| ID | Question | Blocks | Status |
|---|---|---|---|
| **OQ-1** | Exact collection window start/end (IST). | Publication calendar (§A.5, §R.1) | **OPEN** |
| **OQ-2** | Tier-1 match-coverage floor, after full conditioning. | Tier assignment (§B.3) | **OPEN** — set from the 7-day spike, *not invented now* |
| **OQ-3** | Is low availability systematically associated with higher prices? | Sell-out bias direction (§D.6) | **OPEN** — tested and reported; **no correction in v1** |
| **OQ-4** | Are DGCA city-pair passenger volumes public at the required granularity? | Route weights (§G.2) | **OPEN** — capacity-proxy fallback is locked |
| **OQ-5** | Bootstrap runtime at 1000 draws on realistic data. | Interval promise (§N.4) | **OPEN** — measured before the interval is shown |
| **OQ-6** | CPI airfare item label, code, frequency, history. | Benchmark comparison | **OPEN** — benchmark is **configuration, not code** |
| **OQ-7** | Any published Indian domestic booking lead-time distribution. | APW weights (§G.4) | **OPEN** — equal weights declared for v1 |
| **OQ-8** | Licensed-feed coverage of Indian domestic sectors and field availability. | Channel A role | **OPEN** — supplementary/backfill only, **never a silent substitute** |

---

## T. Glossary

| Term | Definition |
|---|---|
| **Observation / quote** | One displayed, transactable offer for one adult, one seat, one-way, economy, at one instant from one channel. §A.1 |
| **Fare** | The monetary amount. Unqualified, it means the **payable fare** of §A.4. |
| **Offer** | A fare together with its product characteristics and entitlements. |
| **Product** | The bundle of characteristics that makes two offers comparable. |
| **Recurring product class** | A bundle of stable observable characteristics that reappears on a fixed weekly cycle. **An approximation to matched-model comparability, not literal identity.** §B.1 |
| **Cell** | An elementary aggregate: one recurring product class at one tier. §B.2 |
| **Elementary index** | The index computed at cell level from matched items — Jevons. §D |
| **Relative** | A dimensionless ratio between two periods, $\approx 1$. $J(c,t)$. §C.4 |
| **Level** | A base-100 index value. $I(c,t)$, $I(r,t)$, $\text{APIx}(t)$. §C.4 |
| **Route index** | Weighted mean of cell **levels** within a route. §F.2 |
| **APIx-L** | Headline deterministic index: Jevons → Young/Modified Laspeyres. §L |
| **APIx-TPD** | Quality-adjusted estimate: quote-level Time Product Dummy, rolling window, mean-spliced. §M |
| **Product composition** | The mix of products contributing observations in a period. Changes in it are what a naive index mistakes for price change. |
| **Estimator divergence** | (APIx-L growth) − (APIx-TPD growth), in percentage points. **Growth rates, never levels.** §M.8 |
| **Suppression** | Withholding a cell or route from publication when a threshold is breached; requires weight renormalisation. §I |
| **Imputation** | Carrying a parent stratum's **relative** into a cell with no defined relative. Deterministic and conservative. §H.2 |
| **Vintage** | An immutable published version of the series. Never overwritten. §R.3 |
| **Publication** | The act of releasing a vintage, provisional or final, with its version vector. §R.1 |
| **Identity stability** | Share of scheduled flights whose flight number recurs at the same weekday slot. Selects the tier. §B.3 |
| **Match coverage** | Share of expected recurring items surviving full conditioning. **The statistic-driving metric.** §B.3 |
| **Version vector** | The tuple that identifies a computation exactly. §O |
| **Chain freshness** | Days since a cell's last computed relative. §C.3 |
