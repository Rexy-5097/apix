# APIx formula specification — v2.1 amendment

> **Status:** FROZEN for `methodology_version` `2.1` · **IN FORCE**
> **Date frozen:** 2026-09-10 · **Checkpoint:** 2E · **Owner:** @Rexy-5097
> **Amends:** `apix_formula_spec_v1.md` (FROZEN, `methodology_version 2.0`)
> **Resolves:** [AMB-1](AMB-1-resolution.md), AMB-6 · confirms AMB-2, AMB-3, AMB-4
> **Leaves open:** AMB-5, and see
> [OPEN-AMBIGUITIES-checkpoint-2.md](OPEN-AMBIGUITIES-checkpoint-2.md) for
> AMB-7 … AMB-10
> **Decision records:** [`ADR-0062`](../../artifacts/decisions/ADR-0062-item-cell-separation.md)
> (the item/cell separation) · [`ADR-0063`](../../artifacts/decisions/ADR-0063-freeze-methodology-v2-1.md)
> (this freeze)
>
> **v2.0 is preserved unchanged.** This is a delta document.
> **Sections of v2.0 not named below are UNCHANGED** and remain authoritative.
>
> ### What the freeze asserts, and what it does not
>
> **Asserts.** Every rule below is in force and is implemented on `main`. The
> implementation shipped in PR #5 and was audited against this text at
> Checkpoint 2E; the one divergence found — §O's `source_precedence` field,
> absent from the version vector — was corrected before this freeze.
>
> **Does not assert.** Freezing this amendment settles **nothing** about
> `expected_cells` (AMB-8) or the allocation of `v[c|r]` across carriers
> (AMB-9). Both affect published values, neither is determined by v2.0 or by
> this document, and both are registered as OPEN rather than absorbed into the
> freeze. `min_route_coverage`, `max_cell_imputation` and every other §I
> threshold are **UNCHANGED** and remain exactly as v2.0 wrote them.
>
> Freezing this document does **not** create a parallel series under §R.2. No
> APIx series has been published under any `methodology_version`, so there is no
> continuity to protect and no linking factor to compute — see ADR-0063 for the
> governance reasoning against the spec's own rule.

## How to read this document

| Marker | Meaning |
|---|---|
| **NEW** | The rule did not exist in v2.0 |
| **CHANGED** | The rule existed and its content changes |
| **CLARIFIED** | Wording only — no implementation would produce a different number |
| **UNCHANGED** | Reproduced for context; v2.0 remains authoritative |

Every substantive claim carries **DIRECT MoSPI REQUIREMENT** · **INFERENCE** ·
**APIx DESIGN DECISION** · **EMPIRICAL / OPEN**.

---

## Summary of the amendment

```
v2.0                                    v2.1
────                                    ────
one key, called the CELL, also     →    TWO keys: an ITEM key and a CELL key
used as the item key

parent drops carrier, flight       →    parent drops CARRIER only
identity and (in the tuple)             (day_of_week retained)
day_of_week

parent relative undefined          →    Jevons over the parent's own matched
                                        items, computed from OBSERVATIONS

parent level undefined (AMB-6)     →    weighted mean over the INDEPENDENT-LIVE
                                        set of children — §J.1 entrants at t
                                        excluded, carried cells retained;
                                        I(P,t) = I(P,t-7)·J(P,t) FORBIDDEN

tier is a property of the ROUTE    →    (ROUTE, CARRIER) for cells;
                                        ROUTE for parents

Tier-2 item price undefined        →    geometric mean of that carrier's
                                        admissible fares in the band;
                                        Tier 2 relabelled an IDENTITY
                                        RELAXATION, not a fallback

multi-source reconciliation        →    ordered, versioned, price-blind
undefined (last-write-wins)             source_precedence; same source in
                                        both periods; a SOURCE_TRANSITION
                                        between links excludes that pair for
                                        exactly one link

new item and new cell              →    distinguished; §J fires only for a
indistinguishable                       genuinely new CELL
```

**Unchanged:** the Jevons form, chaining, carry arithmetic, Young/Modified
Laspeyres, the weight hierarchy, renormalisation, suppression thresholds, annual
linking, reproducibility, the architecture boundary.

---

## §B.1 — Why not "the flight" and why not "the cell" — **UNCHANGED**

Reproduced because it is the LOCKED rule v2.0 §B.2 violated:

> *"A specific flight on a specific departure date exists exactly once and never
> recurs, so the flight cannot be the item. But a cell holding one aggregated
> price per period is a **unit value**…"*

v2.1 satisfies both halves for the first time: the item is a recurring class, not
a departure; the cell holds many items, not one price. **INFERENCE.**

---

## §B.2 — The tier ladder — **CHANGED**

### §B.2.0 The item and the cell are different objects — **NEW**

$$\text{ITEM} \;\ne\; \text{CELL}$$

- The **ITEM** is the unit of **matching**: what must reappear at $t$ and $t-7$
  for a relative to exist. It carries no weight and has no level.
- The **CELL** is the unit of **averaging and weighting**: the elementary
  aggregate over which §D.2 takes a geometric mean, and the lowest level at which
  an index *level* $I(c,t)$ exists.

> **This is the correction that resolves AMB-1.** v2.0 §B.2 named one tuple and
> §D.1 used it for both roles, making §D.3 unsatisfiable. Proof:
> [AMB-1-resolution.md](AMB-1-resolution.md) §2.

**Support:** the elementary aggregate as a pool of *many individual price
quotations* is a **DIRECT MoSPI REQUIREMENT** (EG §4.6, §4.6.1.1, §4.2.1). The
specific field list below is an **APIx DESIGN DECISION**, constrained by the
dossier's *"cells that already hold carrier, fare class, channel and
advance-purchase window fixed"* (p. 18).

### §B.2.1 The CELL key — **NEW** (v2.0 never defined one)

$$c \;=\; (\text{route},\ \text{carrier},\ \text{day\_of\_week},\ \text{apw\_bucket},\ \text{fare\_class},\ \text{channel})$$

**LOCKED.** The cell key is **invariant across all three tiers**. A tier change
alters the ITEM definition only.

> **Why invariance is required.** §F.5 fixes weights for the index year. If the
> tier changed the cell key, a mid-year tier degradation would re-partition the
> cells and therefore re-derive $v_{c\mid r}$, violating §F.5. Under v2.1 a
> `(route, carrier)` pair may drop from Tier 1 to Tier 2 with **no change to any
> weight**. **INFERENCE.**

### §B.2.2 The ITEM key, by tier — **CHANGED** (v2.0's §B.2 tuple, relabelled and reduced)

| Tier | Trigger (§B.3) | ITEM key | Item price |
|---|---|---|---|
| **Tier 1** | stability $\ge 70\%$ | $(\text{carrier},\ \text{flight\_number})$ | the canonical payable fare (§A.4) |
| **Tier 2** | $[40\%,\ 70\%)$ | $(\text{carrier},\ \text{departure\_hour\_band})$ | **§B.2.3 band price** |
| **Tier 3** | $< 40\%$ | none — no within-cell item identity | the cell publishes a declared unit value |

**On the `carrier` field in the ITEM key — normative, not decorative.** Inside a
**cell**, `carrier` is constant, so its presence in the item key cannot change any
matched set or index value there. **At the PARENT (§E.6), carriers are pooled and
this field is what keeps `6E101` and `AI101` distinct.** The item key's `carrier`
field is therefore load-bearing and must not be removed as redundant.
**APIx DESIGN DECISION.**

`departure_hour_band` — **UNCHANGED**: 3-hour bands anchored at 00:00 IST.

> **Removed:** v2.0's implicit item identity by `departure_time_local`. It
> required the scheduled departure time to be identical to the second across
> seven days, so a ten-minute retiming unmatched a flight from itself.
> **CODE BUG, repaired incidentally.**

### §B.2.3 Tier-2 identity relaxation and band price — **NEW**

> ### Terminology — **LOCKED**
> **Tier 2 is an *identity relaxation*, not a *fallback*.** It relaxes how
> specifically an item is identified — from a flight number to a departure-hour
> slot — so a cell whose flight numbers churn can still form a matched set.
> **It does not relax §D.3, and it does not guarantee a larger matched sample. It
> can produce a smaller one.**
>
> The word *fallback* is reserved for the **runtime level fallback**
> `CELL → carrier-pooled PARENT → SUPPRESS` (§E.4.1). Use **"Tier-2 identity
> relaxation"** everywhere except when describing the tier-selection process
> itself.

A 3-hour band may contain several flights, so the band needs a price. v2.0 does
not define one; the question could not arise while the item key was the departure
time.

For carrier $k$, band $b$, period $t$, over that carrier's admissible flights
departing in that band:

$$p_{b,t} \;=\; \exp\!\left(\frac{1}{n_{b,t}}\sum_{j\,\in\,b,\,t}\ln p_{j,t}\right), \qquad n_{b,t} = \left|\{\text{admissible flights of } k \text{ in } b \text{ at } t\}\right|$$

**Band membership is scoped to a single carrier.** A band price is never computed
across carriers — that would be a cross-carrier unit value, forbidden by §B.1.
This matters at the parent (§E.6.3), where carriers are pooled.

**Why the geometric mean.** When the same flight set occupies the band at both
$t$ and $t-7$:

$$\ln p_{b,t} - \ln p_{b,t-7} \;=\; \frac{1}{n}\sum_{j}\left[\ln p_{j,t} - \ln p_{j,t-7}\right]$$

so §D.2 becomes a **two-stage geometric mean of matched flight ratios, equally
weighted per band**, and reduces *exactly* to the Tier-1 Jevons when every band
holds one flight. No other central-tendency measure has this property.

| Option | Verdict |
|---|---|
| **Geometric mean** | **ADOPTED** — the only choice consistent with the log-form Jevons above it |
| Arithmetic mean | **Rejected** — breaks the telescoping identity; arithmetic/geometric mismatch between adjacent stages |
| Median | **Rejected as primary** — inconsistent with Jevons, discontinuous in band membership, equal to the arithmetic mean at $n=2$; robustness is already supplied one level up by §D.7 |
| Rank-matching flights within a band | **Rejected** — pairs the cheapest to the cheapest, a systematic bias worse than the one it repairs |

**Composition exposure — LOCKED disclosure.** When band membership *differs*
between periods — which is why the pair is at Tier 2 — the band ratio is a
**unit-value ratio**. Worked example, with **no fare moving**:

```
t-7 : A ₹5,000  B ₹6,000                GM = 5,477.23
t   : A ₹5,000  B ₹6,000  C ₹4,000      GM = 4,932.42     ratio 0.9005  = -9.95%
```

Composition enters exactly to the extent that the flight set changes **and**
within-band fares are dispersed. Zero dispersion makes membership changes
harmless regardless of size — which is why both are published:

- $\text{band\_membership\_delta}(b,t) = n_{b,t} - n_{b,t-7}$
- $\text{band\_overlap}(b,t) = \dfrac{|S_t \cap S_{t-7}|}{\max(n_{b,t},\,n_{b,t-7})} \in [0,1]$; equals 1 **iff** the telescoping identity holds exactly
- within-band dispersion of log fares, $s_{b,t}$

all recorded per item per period and published as **distributions**, mirroring
the Tier-3 rule one level down.

**Quality standing.** Tier 2 is explicitly **lower quality than Tier 1**: Tier 1
is a pure matched-model relative, Tier 2 embeds a within-band unit value. Tier-2
relatives are dimensionless seven-day relatives and **must** be aggregated
together with Tier-1 relatives — but they are **comparable in units, not in
quality**. A cell whose tier changes mid-year keeps a continuous level series
(the cell key is tier-invariant) but **changes its estimator**; this is a *break
in estimator, not in identity* and must be flagged in the vintage metadata.

**Minimum sample.** A band is **one item** regardless of how many flights it
contains; $n_b \ge 1$ suffices to form a band price. §D.3's threshold applies to
the number of **matched bands** in the cell. ⚠️ **Structural consequence:** 3-hour
bands give at most **8** possible items per Tier-2 cell, and a realistic
05:00–23:00 operating day occupies about **6**. A carrier with four daily flights
clustered into two bands **fails §D.3 at Tier 2 though it would have passed at
Tier 1**. Tier 2 is not uniformly more permissive. **EMPIRICAL / OPEN —
OQ-A5, OQ-A7.**

Worked degradation, to make the asymmetry concrete:

```
Tier 1   6E on DEL-IXC, Monday, T+7, STANDARD, direct
         4 matched flight numbers      |M| = 4  >= 3   -> PUBLISHES

flight numbers churn; the (route, carrier) pair degrades to Tier 2

Tier 2   the same 4 flights occupy only 2 distinct 3-hour bands
         2 matched bands               |M| = 2  <  3   -> CARRIES
```

`min_matched_items_per_cell = 3` remains **LOCKED for v2.1** and is **not**
adjusted to compensate.

#### The Tier-2 estimand — **NEW**

> **The Tier-2 item represents the carrier's departure-hour slot rather than an
> individual flight identity. Its observed price is a *constructed* band-level
> price. The Tier-2 relative estimates the seven-day proportional change in the
> geometric-mean fare of that carrier's departures within that slot, on that
> route, weekday, advance-purchase window, fare class and channel.**

| Condition | What the relative measures |
|---|---|
| **Stable band membership** ($\text{band\_overlap}=1$) | Exactly the geometric mean of the matched **flight-level** relatives. Pure price movement; no composition component |
| **Changed band membership** ($\text{band\_overlap}<1$) | Price movement **plus a composition component**, bounded by the product of membership change and within-band dispersion |

**Tier 2 does not remove composition effects — it relocates them from the flight
identity into the band.** The residual is measured, not eliminated, by
`band_membership_delta`, `band_overlap` and within-band dispersion.

**Label: APIx DESIGN DECISION.** MoSPI has no analogue.

---

## §B.3 — Identity stability and match coverage — **CHANGED (unit only)**

**Thresholds 70% / 40% are UNCHANGED and remain LOCKED.**

**CHANGED — the unit over which identity stability is measured:**

$$\text{IdentityStability}(r,k) \;=\; \frac{\#\{\text{flight numbers of carrier } k \text{ on route } r \text{ recurring at the same weekday slot across the window}\}}{\#\{\text{scheduled flights of carrier } k \text{ on route } r\}}$$

- **Cells** take their tier from $\text{IdentityStability}(r,k)$ — the
  `route × carrier` pair.
- **Parents** take their tier from $\text{IdentityStability}(r)$ — the pooled
  route statistic, i.e. **exactly the v2.0 quantity, reused unchanged**.

> **Why the unit had to change.** Flight-number stability is a property of the
> entity that assigns flight numbers: the carrier. Once cells are carrier-specific
> (§B.2.1), a route-level tier applies one carrier's instability to every other
> carrier on the route. v2.0 §B.2 already promises *"the tier is recorded per cell
> in the version vector"*; a route-level statistic cannot populate a per-cell field
> faithfully. **INFERENCE.**

A route index may contain Tier-1 and Tier-2 cells simultaneously. Not a defect —
§I already publishes tier share **by weight**, which is the metric that matters.
**CLARIFIED.**

**Match coverage** — **UNCHANGED**. Its floor remains **EMPIRICAL / OPEN
(OQ-2)**, now to be measured jointly with OQ-A1. Empirical confirmation of the
unit change is **OQ-A3**.

---

## §B.4 — Entitlements define the fare class — **CLARIFIED** (resolves AMB-4)

The mapping table is **UNCHANGED**. What is added is the **evaluation order**,
which v2.0 left implicit:

$$\texttt{HAND\_ONLY} \;\rightarrow\; \texttt{STANDARD} \;\rightarrow\; \texttt{FLEX}$$

evaluated as an **ordered decision list**: the first matching condition wins.

**Why this order.** `FLEX`'s condition never mentions baggage, so the precedence
question is *"does `FLEX` become a baggage-mixed class?"*

| Order | Result |
|---|---|
| `FLEX` first | `FLEX` holds zero-baggage **and** checked-baggage flexible fares. **Baggage uncontrolled inside `FLEX`** |
| **`HAND_ONLY` first** | `FLEX` holds checked-baggage flexible fares only. **All three classes control baggage** |

The only order under which every class is baggage-homogeneous. It uses each
written condition exactly once and yields a total partition. **This confirms the
behaviour already implemented — no production code change.** **INFERENCE.**

**Deferred:** entitlements are two independent axes (baggage, flexibility)
compressed into three ordered classes. A 2-D
`(baggage_tier × flexibility_tier)` scheme is the statistically clean form and
would change §G.3's $\beta$. **OQ-A4 — deliberately not part of this amendment.**

---

## §B.5 — Channel is part of the cell key — **UNCHANGED (reaffirmed)**

$$\text{An elementary cell never mixes channels.}$$

Reaffirmed after explicit re-examination of the alternative. Worked example:

```
IndiGo direct ₹6000 · MakeMyTrip ₹6050 · Goibibo ₹6030 · Ixigo ₹6030
```

Three distinct problems, which must not be conflated:

| Problem | Answer |
|---|---|
| **Price concept** | ₹6000 and the aggregator quotes are **two different price concepts** — carrier-direct payable vs aggregator payable including a platform charge. Both are real transaction prices → **two cells** |
| **Source duplication** | MakeMyTrip and Goibibo share ownership and inventory → **one independent source group** (§B.6) → ~**2** groups, not 3 |
| **Statistical independence** | The remaining quotes are **repeated observations of one item**, not different products |

**4 quotes → 2 price concepts (2 cells) → within `AGGREGATOR`, 1 item observed
through ~2 independent source groups.**

**Recorded for the record:** MoSPI does the opposite — it *pools* booking
platforms *"to ensure representativeness"* (EG, **DIRECT MoSPI REQUIREMENT** for
their series). APIx separates them and publishes the gap as a diagnostic.
**This is an APIx DESIGN DECISION that departs from MoSPI's documented airfare
practice and must never be presented as alignment with it.**

---

## §B.6 — Independent sources — **UNCHANGED**, operationalised in §D.8

---

## §C.2 — Seven interleaved chains — **CLARIFIED**

`day_of_week` **remains in the cell key**. Its status is stated precisely because
at fixed $(t, \text{apw})$ it is mechanically determined, and a future reader
could delete it as redundant.

| Role | Status |
|---|---|
| Sampling stratifier | **No** |
| Conditioning characteristic that adds observations at $t$ | **No** — determined by $(t,\text{apw})$; it partitions nothing within a collection date, nor along a chain |
| **Chain and level identity** | **YES — load-bearing.** Remove it and one cell key names **seven different level sequences**, each updated on a different day; $I(c,t)$ would be overwritten daily by a level from a different chain |
| Audit / publication identity | **Yes** — a published series should be fully identified by one key |

**Verdict: technically and audit necessary; not statistically necessary as a
conditioning variable. INFERENCE.** Because it is determined, it is **not** an
independent weight dimension — §G.3 correctly omits it, **UNCHANGED**.

---

## §D.1 — The matched set — **CHANGED**

$$M(c,t) \;=\; \{\, i : i \in \text{admissible}(c,t) \ \wedge\ i \in \text{admissible}(c,t-7) \,\}$$

where an item's identity within a cell is its **ITEM key (§B.2.2)** — *not* the
cell key.

$$\boxed{\text{Unmatched items enter NEITHER side of the ratio.}}$$

— **UNCHANGED.**

**Consequence — NEW.** A flight appearing for the first time is a **new item, not
a new cell**. It contributes nothing on first sighting and begins contributing
from its first *matched pair*, one weekly link later. **§J does not fire.** See
§J.0.

**Support:** *"once at least two consecutive months' prices of the new
specification are available, the new specification will be fully incorporated
into the index compilation"* (EG §4.6.5.2(c)) — the same rule at monthly cadence.
**DIRECT MoSPI REQUIREMENT.**

---

## §D.2 — The relative — **UNCHANGED**

Log form remains normative; equal weight per matched item. **All existing golden
values at this layer remain valid.** The same estimator is used at the parent
level (§E.6.7).

---

## §D.3 / §D.7 — `|M(c,t)|` — **CLARIFIED** (resolves AMB-2)

- **§D.7** (outlier gate, $\ge 5$): $|M(c,t)|$ is the **candidate** set, before
  flagging.
- **§D.3** (minimum sample, $\ge 3$): the **surviving** set, after flagged items
  are excluded.

The §L.1 pipeline order (D.1 → D.7 → D.2) already determines this; the notation
is now explicit. **No behavioural change.**

`min_matched_items_per_cell = 3` is **UNCHANGED in v2.1 — deliberately.** It is
now **binding for the first time**, and it was locked against an object for which
no threshold was meaningful. Re-derivation against measured data is **OQ-A5**,
separately for Tier 1 (matched flights) and Tier 2 (matched bands, structurally
capped at ~6). It is the single parameter that determines what share of the index
computes rather than carries.

---

## §D.4 — Duplicates — **CLARIFIED** (resolves AMB-3)

The written tuple gains `route`:

$$(\text{route},\ \text{carrier},\ \text{flight\_number},\ \text{travel\_date},\ \text{departure\_time\_local},\ \text{fare\_class},\ \text{channel},\ \text{source\_id})$$

v2.0's parenthesised tuple omitted `route` while its own sentence scoped
duplicates to *"the same cell"*, and a cell key begins with the route. The
implementation already includes it (measured: without `route`, 2,800 admissible
quotes collapsed to 140). **Wording catches up with behaviour; no code change.**

---

## §D.8 — Source precedence — **NEW**

v2.0 defines no rule for reconciling several sources quoting the same item inside
one cell, so the implementation fell back to insertion order — an arbitrary,
undeclared rule. **That is the one outcome unacceptable under any resolution.**

### §D.8.1 The rule — **PROVISIONAL; the procedure is LOCKED**

1. Collapse sources into **independent source groups** per §B.6.
2. An ordered `source_precedence` list exists **per channel**, in configuration.
3. For each item and period, take the fare from the **highest-ranked source
   present in BOTH $t$ and $t-7$**. If no source is present in both, the item is
   **unmatched** and enters neither side (§D.1).
4. Record the winning `source_id` on the matched pair.
5. Retain all other sources and publish the **cross-source spread** diagnostic.

Applies identically at the parent level (§E.6.5).

### §D.8.2 Required properties — **LOCKED**

| Property | How it is met |
|---|---|
| **Deterministic** | An explicit total order, not dictionary or arrival order |
| **Price-blind** | Selection never inspects the fare. No minimum, median or mean is taken — **the rule cannot bias the level by construction** |
| **Same-source-paired** | Both legs of every relative come from one source, so a source switch can never masquerade as a price change |
| **Versioned** | `source_precedence` is recorded in the version vector (§O) beside `weight_version` |
| **Auditable** | The winning `source_id` is stored on each matched pair |
| **Reversible** | Changing the list is a version-vector change, visible in every published vintage |

### §D.8.3 Source transitions — **NEW; conservative and PROVISIONAL**

Selection can change **between consecutive links** even when every individual
pair is same-source:

```
link (t-7, t)     A available, B available    ->  A selected
link (t,  t+7)    A unavailable, B available  ->  B selected
```

Let $\sigma(i,t)$ be the source selected for the link ending at $t$. Define

$$\text{SOURCE\_TRANSITION}(i,t) \iff \sigma(i,t) \ne \sigma(i,t-7) \;\wedge\; \sigma(i,t-7)\text{ is defined}$$

**Rule — the procedure is LOCKED; the choice is PROVISIONAL.**

1. The pair is flagged **`SOURCE_TRANSITION`**.
2. It is **excluded from $M(c,t)$** — no relative is published for that item at
   that link.
3. Diagnostic metadata is retained: both `source_id`s, both prices, the implied
   cross-source gap.
4. The item **resumes automatically** at the first subsequent link where
   $\sigma$ is unchanged — i.e. once the new source has **two consecutive selected
   observations**.

Exclusion therefore lasts **exactly one link**; no manual intervention is
required.

**Explicitly forbidden:** bridge adjustments · blending sources · last-write-wins
· carrying the old source's price forward as if observed.

**Pipeline placement.** Source selection and transition flagging occur during
matched-pair formation, **before** §D.7's outlier gate, so a flagged pair never
enters the candidate set and cannot influence the median/MAD computation.

#### What this rule does and does not prevent — **stated accurately**

⚠️ The same-source-paired requirement (§D.8.1 step 3) **already makes a
cross-source price comparison impossible**: $p_B(t+7)/p_B(t)$ uses source B on
both legs, so a carrier-direct ₹6,000 can never be divided by an OTA ₹6,100.
**A cross-source ratio is not the failure mode this rule guards against, and this
specification does not claim that it is.**

The genuine exposure is subtler: **the item's series is spliced across two price
bases between consecutive links.** Each relative is clean, but the chained level
becomes a product of A-based relatives followed by B-based relatives. If the two
sources' fee structures drift differently, the cell's measured movement changes
character with no disclosure at the point of change. Excluding the transition link
makes that splice **explicit and countable rather than silent**.

**Cost, disclosed:** the rule withholds items precisely when source coverage is
weakest, which can push a thin cell below §D.3 and increase carry. Frequency is
unknown — **EMPIRICAL / OPEN, OQ-A9.**

**Attribution.** Mapping *outlet substitution* onto *source substitution* is an
**APIx DESIGN DECISION**. The two-consecutive-periods resumption condition it
borrows is a **DIRECT MoSPI REQUIREMENT** (EG §4.6.5.2(c): *"once at least two
consecutive months' prices of the new specification are available, the new
specification will be fully incorporated"*).

### §D.8.4 What is *not* decided — **EMPIRICAL / OPEN**

The permanent reconciliation **statistic** is not frozen. Median across
independent source groups is the leading v2.2 candidate and must be chosen
against the **measured** cross-source spread. **OQ-A2.** Whether the
transition exclusion of §D.8.3 can be relaxed once cross-source spread is known
to be small and stable belongs to the same question.

> **Rejected:** `source_id` in the item key — it would inflate effective $N$ with
> shared inventory, violating §B.6.

**APIx DESIGN DECISION, PROVISIONAL.**

---

## §E.4 — Carry rule when $J$ is undefined — **CHANGED**

$$I(c,t) \;=\; I(c,\,t-7)\ \cdot\ J(\text{parent}(c),\,t)$$

— the cell inherits the parent's **relative**, never its level. **UNCHANGED.**

$$\text{parent}(c) \;=\; (\text{route},\ \text{day\_of\_week},\ \text{apw\_bucket},\ \text{fare\_class},\ \text{channel})$$

i.e. **the cell key with `carrier` dropped.**

### Why this is the only admissible parent — **NEW**

A parent is useful only if it releases a dimension genuinely free at the
publication date. At fixed $(t,\text{apw})$, `travel_date` and `day_of_week` are
determined; the free dimensions are `carrier`, `fare_class`, `channel`, `route`.

| Candidate parent | Dimension released | Adds observations at $t$? |
|---|---|---|
| drop `day_of_week` only | **none — determined** | ❌ **No.** Its observation set is *identical to the cell's*. Whenever the child's relative is undefined the parent's is too. **A dead rule** |
| **drop `carrier`** | carrier | ✅ **Yes** — pools every carrier's cells on that route/weekday/APW/class/channel |
| drop `channel` | channel | ✅ yes, but pools **two price concepts** — forbidden by §B.5 |
| drop `fare_class` | fare class | ✅ yes, but pools different entitlement bundles — the comparison §B.4 prevents |

**Two v2.0 defects corrected.** Its prose (*"carrier and flight-identity
dropped"*) and its tuple (which additionally dropped `day_of_week`) disagreed.
Dropping `day_of_week` from the *parent* does not change $J(\text{parent},t)$ —
the matched pairs are identical — so it is numerically harmless, but it leaves the
parent naming seven interleaved chains under one key. Restored for identity
hygiene. **CLARIFIED (numerically) / CHANGED (key shape).**

### §E.4.1 — Runtime fallback ladder — **NEW (narrowing §E.4's terminal branch)**

$$\boxed{\text{CELL} \;\longrightarrow\; \text{carrier-pooled PARENT} \;\longrightarrow\; \text{SUPPRESS}}$$

**Exactly one carry level. No channel-pooled or route-level fallback ships.**

Reasons: deeper pooling buys coverage by violating a LOCKED homogeneity rule;
§I.1 already defines the terminal behaviour and §F.4 renormalises, so
**suppression is visible in published quality metrics** while a silent
third-level carry is not; and v2.0 §E.4 closes with *"Nothing more sophisticated
ships in v1."* **INFERENCE / APIx DESIGN DECISION.**

> **This is the complete runtime fallback.** Any alternative elementary design
> (see [AMB-1-resolution.md](AMB-1-resolution.md) §5.1) is a **separately
> versioned future methodology alternative**, not a runtime path, and is not
> reachable by any code path in v2.1.

**Honest limitation — LOCKED disclosure.** A carried cell inherits the parent's
relative, and the parent pools carriers. **Carrier-mix drift therefore enters the
carried strata (§E.6.9).** v2.1 *confines* carrier-mix contamination to carried
cells; it does not eliminate it. **The phrase "carrier mix is controlled by
construction" is incorrect and must not appear in APIx documentation,
presentations or the dashboard.**

---

## §E.6 — The parent object — **NEW**

*This section exists so an independent engineer can compute the parent relative
and the parent level without asking anyone.*

### §E.6.1 Parent ITEM

$$\text{item}_P = (\text{carrier},\ \text{flight\_number})$$

identical to the cell's Tier-1 item key. Because the parent pools carriers, the
`carrier` field is **essential** here — without it `6E101` and `AI101` collide.
**APIx DESIGN DECISION.**

### §E.6.2 It is not another object

The item definition is **identical** at cell and parent level; only the stratum
over which items are pooled differs. One item definition is what makes the
carried relative arithmetically comparable to the cell's own.

### §E.6.3 Parent Tier-2 item

$$\text{item}_P^{T2} = (\text{carrier},\ \text{departure\_hour\_band})$$

with the band price of §B.2.3 computed **per carrier**. A band price is never
formed across carriers.

### §E.6.4 Parent tier selection

From the **route-level** statistic $\text{IdentityStability}(r)$ (§B.3).
Thresholds 70% / 40% **UNCHANGED**.

**Two derived rules, both LOCKED:**

1. A parent's tier may differ from its children's. Both are **recorded on every
   carry** (`cell_tier`, `parent_tier`) so a reviewer can see which estimator
   produced the imputed movement.
2. **A Tier-3 parent has no matched set and therefore no relative.** If
   $\text{tier}(P)=3$ then $J(P,t)$ is undefined, the carry cannot occur, and the
   cell is **suppressed** (§I.1). Stated here so it is not discovered at runtime.

### §E.6.5 Parent matched set

$$M(P,t) = \{\, i : i \in \text{admissible}(P,t) \ \wedge\ i \in \text{admissible}(P,t-7) \,\}$$

where $\text{admissible}(P,t)$ is the set of admissible observations whose parent
key equals $P$ — the **union over carriers** of the observations in $P$'s child
cells.

> **Computed from OBSERVATIONS, never from cell results — LOCKED.** The parent's
> matched set includes items from child cells that were themselves suppressed,
> carried or withheld. Building the parent from cell outputs would make the carry
> depend on the very failure it exists to repair.

§D.4 deduplication and §D.8 source precedence apply identically.

### §E.6.6 Parent minimum-match rule

$$|M(P,t)| \;\ge\; \texttt{min\_matched\_items\_per\_cell} = 3$$

**The same threshold, applied to a new object. No parent-specific value is
invented.** Below it, $J(P,t)$ is undefined, the carry fails, and the cell is
suppressed.

**Known weakness, disclosed rather than patched.** Nothing requires the parent's
matched items to come from more than one carrier. A parent whose matched set is
entirely one carrier's flights imputes that carrier's movement to every other
carrier's cell. Two diagnostics are therefore **required**:

- `parent_carrier_count` — distinct carriers contributing matched items;
- `parent_carrier_concentration` — share of matched items from the dominant
  carrier.

Whether a minimum carrier count or a concentration ceiling should become a rule
is **EMPIRICAL / OPEN — OQ-A8**. **No threshold is invented here.**

### §E.6.7 Estimator — **identical to §D.2**

$$J(P,t) = \exp\!\left(\frac{1}{|M(P,t)|}\sum_{i \in M(P,t)}\left[\ln p_{i,t} - \ln p_{i,t-7}\right]\right)$$

§D.7's median/MAD outlier rule applies unchanged, gated at $\ge 5$ candidates,
in the §L.1 order D.1 → D.7 → D.2.

### §E.6.8 How carrier observations are combined

**They are not combined.** Each carrier's flights are separate items; their
log-relatives enter the same equal-weighted arithmetic mean in log space. No
carrier aggregate is formed at any point.

### §E.6.9 Carrier mix is implicitly count-weighted — **YES, disclosed**

$$J(P,t) = \exp\!\left(\sum_k \frac{n_k}{\sum_j n_j}\cdot \overline{\Delta \ln p}_k\right), \qquad n_k = \#\{\text{matched items of carrier } k\}$$

**The parent weights each carrier in proportion to its count of matched flights,
and $n_k$ drifts week to week.** If IndiGo contributes 12 matched flights and Air
India 3, the parent's movement is 80% IndiGo dynamics.

**This is the exact channel through which carrier-mix contamination re-enters.**
Exposure must be published: carried weight share, `parent_carrier_count`,
`parent_carrier_concentration`. **EMPIRICAL / OPEN — OQ-A8.**

### §E.6.10 The parent is a computation stratum, never a publication stratum

| Quantity | Exists? | Computed by | Used by |
|---|---|---|---|
| $J(P,t)$ — parent **relative** | **Yes** | §E.6.5–E.6.7, from observations | §E.4 carry **only** |
| $I(P,t)$ — parent **level** | **Yes** | §E.7 | §J.1 new-cell entry **only** |
| Parent weight | **No** | — | The parent never appears in §F.2 or §F.3 |
| Parent published series | **No** | — | Diagnostic only; not a vintage output |

---

## §E.7 — Parent LEVEL — **NEW** (resolves AMB-6)

§J.1 requires $I(\text{parent}(c),t)$, which v2.0 never defines.

### §E.7.1 The recursion that must be excluded

A definition over *all* live children is **self-referential**: a cell $C$
entering at $t$ under §J.1 has $I(C,t) = I(P,t)$ by definition, so including it
puts $I(P,t)$ on both sides —

$$I(P,t) = \tilde v_A I(A,t) + \tilde v_B I(B,t) + \tilde v_C\,I(P,t)$$

**This is excluded by definition, not solved as a fixed point.** A fixed-point
solution would let a new cell's own weight influence the level it enters at,
which is precisely the spurious contribution §J.1 exists to prevent.

### §E.7.2 The independent-live set — **LOCKED**

$$\mathcal{L}^{\text{ind}}(P,t) \;=\; \Bigl\{\, c \in \text{children}(P)\cap L_t \;:\; I(c,t) \text{ is determined without reference to } I(P,t) \,\Bigr\}$$

$$\boxed{\;I(P,t) \;=\; \sum_{c\,\in\,\mathcal{L}^{\text{ind}}(P,t)} \tilde{v}_{c\mid P}\cdot I(c,t), \qquad \tilde{v}_{c\mid P} = \frac{v_{c\mid r}}{\displaystyle\sum_{j\,\in\,\mathcal{L}^{\text{ind}}(P,t)} v_{j\mid r}}\;}$$

with within-parent weights renormalised over $\mathcal{L}^{\text{ind}}(P,t)$
exactly as §F.4 prescribes.

| Child's state at $t$ | Its level at $t$ | In $\mathcal{L}^{\text{ind}}$? |
|---|---|---|
| Computes its own relative — $I(c,t)=I(c,t-7)\cdot J(c,t)$ | independent | ✅ **Yes** |
| **Carries** (§E.4) — $I(c,t)=I(c,t-7)\cdot J(P,t)$ | independent | ✅ **Yes** — §E.7.3 |
| **Enters at $t$ under §J.1 against this parent** — $I(c,t)=I(P,t)$ | **recursive** | ❌ **No — the only exclusion** |
| Suppressed | no level | ❌ not live |

### §E.7.3 Carried cells are NOT excluded — **the precision that matters**

A carried cell's level depends on the parent's **relative** $J(P,t)$, computed
**bottom-up from raw observations** (§E.6) and wholly independent of $I(P,t)$.
**No recursion is created.** Excluding carried cells would discard well-determined
levels, shrink $\mathcal{L}^{\text{ind}}$ needlessly, and make hold-out far more
frequent than the mathematics requires — on thin routes, where carry is common,
it could empty the set almost always.

The recursion is broken independently at each period: a cell that entered at
$t-7$ was excluded from $I(P,t-7)$ *then*, and its level at $t$ is
$I(P,t-7)\cdot J(P,t)$, which references no current-period parent level. **No
recursion, direct or transitive, can arise.** **INFERENCE.**

### §E.7.4 Empty independent-live set — **LOCKED**

$$\mathcal{L}^{\text{ind}}(P,t) = \varnothing \;\;\Longrightarrow\;\; I(P,t) \text{ is UNDEFINED}$$

- **New-cell entry is impossible** → the candidate cell is **held out** per §J.2
  (*"held out until a parent level exists… never seeded at 100 inside a live
  aggregate"*). **Existing rule, newly reachable condition.**
- **Held out ≠ suppressed.** A suppressed cell was live and breached a threshold;
  a held-out cell was never live. Both are excluded from the live set and both
  have their weight renormalised away under §F.4, but they are **different quality
  events** and are reported separately: `held_out_weight_share` (**NEW
  diagnostic**) alongside §I's `suppressed_weight_share`.
  **APIx DESIGN DECISION.**
- **Carries are unaffected.** $I(P,t)$ is required only by §J.1; a cell carrying
  under §E.4 needs $J(P,t)$ and continues normally.

Frequency of this condition is **EMPIRICAL / OPEN — OQ-A9.**

### §E.7.5 The four objects, and the one equation that must never be written

$$\boxed{
\begin{aligned}
J(c,t) &\;=\; \textbf{cell relative} && \text{Jevons over } M(c,t) \text{ — raw observations}\\
I(c,t) &\;=\; \textbf{cell level} && \text{chained: } I(c,t-7)\cdot J(c,t)\\
J(P,t) &\;=\; \textbf{parent fallback relative} && \text{Jevons over } M(P,t)\text{ — raw observations, \textbf{bottom-up}}\\
I(P,t) &\;=\; \textbf{parent reference level} && \text{weighted mean over } \mathcal{L}^{\text{ind}}(P,t)\text{ — \textbf{top-down}}
\end{aligned}}$$

| | Computed from | Direction | Used by | Never used by |
|---|---|---|---|---|
| $J(P,t)$ | raw observations in the parent stratum | **bottom-up** | §E.4 **carry only** | anything producing a level |
| $I(P,t)$ | independently-determined child levels | **top-down** | §J.1 **new-cell entry only** | anything producing a relative |

> ### ⛔ FORBIDDEN
> $$I(P,t) \;\ne\; I(P,t-7)\cdot J(P,t)$$
>
> **The parent relative MUST NOT be used to independently chain the parent
> level.** The parent is not a chained index: it has no base period, no $t_0$ and
> no history of its own. Writing this equation would create **two competing
> definitions of the parent level** — one chained, one aggregated — which would
> diverge immediately and silently, and would make new-cell entry depend on a
> shadow series nothing else in this specification maintains.
>
> Any future decision to give the parent an independently chained level is a
> **new methodology version**, requiring its own ADR, amendment and audit.

**Why not chain it (the rejected alternative, for the record).** A
separately-chained parent level would drift away from its children's weighted
mean, so seeding a new cell there would inject **exactly the spurious jump §J.1
exists to prevent**. The parent level must be the level the aggregate already
reflects. **INFERENCE.**

This mirrors §C.4 one level up: *"the construction is relative at the elementary
level, level at every level above it."* Conflating a relative with a level is the
error §C.4 already names as the most common way this construction goes wrong.

---

## §I — Suppression thresholds — **UNCHANGED**

All six thresholds unchanged. Two notes:

- `min_matched_items_per_cell = 3` becomes **binding for the first time** (§D.3),
  at both cell and parent level. Expect a materially non-zero carry share; it is
  now measurable.
- Tier share by weight is computed over **cell** tiers, which after §B.3 may be
  mixed within a route. The metric definition is unchanged.

---

## §J.0 — New item vs new cell — **NEW**

v2.0 could not distinguish these: any key without a prior level looked new.

| # | Event | New item? | New cell? | New parent? | Basket event? | Enters at 100? | Inherits parent level? | Waits for a matched pair? |
|---|---|---|---|---|---|---|---|---|
| **1** | New flight number in an existing cell (`6E999`) | **Yes** | No | No | No | **No** | **No** | **Yes** — §D.1. **§J does not fire** |
| **2** | New fare class or channel for an existing carrier and route | Yes | **Yes** | No | No | No | **Yes** — §J.1 | Movement from its first defined $J$ (§J.2) |
| **3** | New channel with no existing stratum | Yes | Yes | **Yes** | No | No | **Held out** until a parent level exists (§E.7, §J.2) | Yes |
| **4** | New carrier on an existing route | Yes | **Yes** | No — the parent is carrier-pooled and already exists | No | No | **Yes**, at the parent's level | Yes |
| **5** | New route | Yes | Yes | Yes | **Yes** | No | No — only at a `basket_version` change with re-derived weights (§K) | n/a |

> **Case 1 is what v2.0 got wrong.** Under v2.1 it is invisible to §J entirely:
> **a newly appearing flight is not a price change, and it is not a new elementary
> aggregate either.**

§J.1 and §J.2 themselves are **UNCHANGED**; only the trigger is narrowed to cases
2–4.

---

## §O — Version vector — **CHANGED (field values and one addition)**

| Field | v2.1 |
|---|---|
| `methodology_version` | **`2.1`** |
| `source_precedence` | **NEW** — identifier of the ordered source list in force (§D.8) |
| `basket_version`, `weight_version`, `code_version`, `data_snapshot_id` | **UNCHANGED** |
| `model_version` | **UNCHANGED** — `N/A` for APIx-L |

Structure and rendering (§O.2) are **UNCHANGED**.

---

## Explicitly UNCHANGED

§A (observation contract, APW buckets, canonical fare, admissibility) · §B.5 ·
§B.6 · §C.1 · §C.3 · §C.4 · §D.2 · §D.5 · §D.6 · §D.7 · §E.1 · §E.2 · §E.3 ·
§F (all) · §G (all) · §H · §I thresholds · §J.1 · §J.2 · §K · §L · §M · §N ·
§P · §Q · §R

> **§E.5 note.** v2.0's §E.5 (*disappearance and resumption*) is **UNCHANGED**.
> The fallback ladder above is issued as **§E.4.1**, as this note required before
> the freeze, so no existing section number is displaced.

**§G.4 note (no change, restated for accuracy).** The seven APW buckets and
$\alpha = 1/7$ are **APIx DESIGN DECISIONS**. MoSPI's adopted domestic airfare
specification uses a **single 21-day advance-purchase point** (EG §3.9,
**DIRECT MoSPI REQUIREMENT**); 60 days is its *international* point, so APIx's
`T+60` must not be presented as alignment. **No APIx bucket currently equals 21
days.** Adding `T+21` would make one APIx sub-index directly comparable to CPI
2024's airfare specification, but it changes the bucket set and moves $\alpha$
from $1/7$ to $1/8$. **It is not part of this amendment** — it is separable from
AMB-1, and bundling two methodology changes into one audit weakens both.
**OQ-A6.**

**§S note.** OQ-1 … OQ-8 are unaffected. OQ-A1 … OQ-A8 are added by
[AMB-1-resolution.md](AMB-1-resolution.md) §24. OQ-2 is now coupled to OQ-A1.
**AMB-5 remains OPEN and untouched.**

---

## MoSPI position — what is theirs and what is ours

| MoSPI (**DIRECT MoSPI REQUIREMENT**) | APIx (**APIx DESIGN DECISION**) |
|---|---|
| Jevons short index at the elementary level | Finer airfare stratification than any MoSPI specification |
| Young / Modified Laspeyres above it | Seven APW buckets (MoSPI: one 21-day domestic point) |
| Elementary indices from individual price quotations | Carrier-specific cells (MoSPI: **UNKNOWN**, never mentioned) |
| Online collection of airfare from well-known platforms | Channel-specific cells (MoSPI **pools** platforms) |
| DGCA-provided most-popular routes | Daily publication |
| 21-day domestic advance-purchase point | Weekly-matched comparisons |
| Platform / time-window pooling for representativeness | The three-tier ladder, its unit, and its thresholds |
| New specification incorporated after two consecutive periods | Parent fallback design; Tier-2 band construction; source precedence |

**APIx is not identical to MoSPI and must never be presented as such.** Known
counter-evidence, recorded deliberately: EG §4.4.3–4.4.4 shows MoSPI responding to
airfare sparsity by **pooling more routes**, the opposite direction to APIx's
stratification. The defence is collection volume, not MoSPI precedent.

---

## Verification obligations before this amendment can be frozen

1. **E2E-01 … E2E-13** written against this document and **failing** before any
   implementation change (specification-first, per Checkpoint 1A). The four added
   by this revision:
   - **E2E-06b** — Tier-2 density regression: 4 matched flights collapse into 2
     bands → $|M|=2$ → the cell **carries**, proving the identity relaxation does
     not relax §D.3.
   - **E2E-11** — parent-level recursion: a cell entering at $t$ under §J.1 is
     **excluded** from $\mathcal{L}^{\text{ind}}(P,t)$, and $I(r,t)$ is unchanged
     by the entry.
   - **E2E-12** — a **carried** child **is** included in
     $\mathcal{L}^{\text{ind}}(P,t)$; and when $\mathcal{L}^{\text{ind}}$ is
     empty, the candidate is **held out**, not suppressed, while existing carries
     continue.
   - **E2E-13** — a source transition excludes exactly one link, records the
     diagnostic, and the item resumes at the next link automatically.
2. **New golden fixture cases** for cell assignment, items-per-cell, the parent
   relative (from observations) and the parent level (from the independent-live
   set).
   The existing 16 hand-calculated **values** remain valid — they exercise Jevons,
   chaining, aggregation and renormalisation, all at or above the cell *level*.
   Their **key literals** must be migrated to the new `CellKey` / `ItemKey`
   shapes. **That is a test-code change and must be reported as one, not as
   "tests untouched."**
3. **Items-per-cell reported as a benchmark metric**, not a comment.
4. **Permanent testing doctrine adopted:** unit tests verify functions;
   end-to-end statistical fixtures verify that the correct statistical objects
   reach those functions. Every methodology-bearing layer carries at least one
   observation-to-published-number fixture.

---

*DRAFT. Not frozen. No production code, production test, golden fixture, PR or
commit was changed in producing this document.*
