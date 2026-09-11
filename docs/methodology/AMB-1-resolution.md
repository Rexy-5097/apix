# AMB-1 — formal resolution

> **Status:** FORMAL DRAFT — reasoning audited in principle; awaiting final
> methodology audit by @Rexy-5097 (owner)
> **Checkpoint:** 2B · **Date:** 2026-09-09
> **Amends:** `apix_formula_spec_v1.md` (FROZEN, `methodology_version 2.0`) — **untouched**
> **Amendment (FROZEN, v2.1):** [`apix_formula_spec_v2_1.md`](apix_formula_spec_v2_1.md)
> **Decision record:** [`ADR-0062`](../../artifacts/decisions/ADR-0062-item-cell-separation.md)
>
> No production code, production test, golden fixture, PR or commit was changed
> in producing this document.

**Label key.** Every methodology decision below carries one of:
**DIRECT MoSPI REQUIREMENT** · **INFERENCE** · **APIx DESIGN DECISION** ·
**EMPIRICAL / OPEN**.

---

## 1. Problem

v2.0 uses **one key for two incompatible statistical roles**:

- §B.2 defines a tuple and calls it the **cell** — the elementary aggregate that
  carries a weight and a level;
- §D.1 says an item's identity within a cell **is that same tuple** — making it
  also the **matching** key;
- §D.3 requires `|M(c,t)| >= 3`.

The three cannot hold together. Under the literal reading **no Tier-1 cell can
ever publish a relative**, so APIx-L cannot be computed at its preferred tier.

---

## 2. Mathematical proof

**Given** (v2.0, all LOCKED): §A.3 exact APW assignment · §B.2 cell key ·
§D.1 item identity = §B.2 key · §D.3 `|M| >= 3` · §D.4 same-source duplicates
collapsed · §A.4 one canonical fare per quote.

**Lemma 1 — travel date determined.** $\text{travel\_date} = t + a$, exactly one
date.

**Lemma 2 — weekday determined.** $\text{day\_of\_week} = \text{weekday}(t+a)$.
A function of $(t,a)$, not a free coordinate.

**Lemma 3 — one departure per cell.** Fixing route, carrier, flight number and
(Lemma 1) travel date names **one scheduled departure**. Fixing fare class and
channel selects at most one canonical fare, after §D.4.

**Theorem.**

$$|\text{admissible}(c,t)| \le 1 \;\Longrightarrow\; |M(c,t)| \le 1 < 3$$

for every Tier-1 cell at every $t$. §D.3 is **unsatisfiable**, not merely hard to
satisfy. $J(c,t)$ is undefined everywhere, §E.4 carry fires universally, and no
Tier-1 relative is ever computed. $\blacksquare$

**Structural, not empirical.** The result follows from the *exactness* of §A.3
alone. No volume of data can produce a second item, because a second item would
be the same flight on the same date in the same fare class through the same
channel from the same source — which §D.4 defines as a duplicate and removes.

**Reproduced:** 2,800 admissible observations → 2,800 cells → **1.000 matched
items per cell**; every route level returned the harness fallback `100.0000`.

**Scope.** The pathology is Tier-1-specific. At Tier 2 the implementation's
`ItemKey` is `departure_time_local` while the cell carries an hour band, so two
flights in one band are two items. **The implementation only works where item and
cell already differ** — itself evidence that they were meant to.

---

## 3. Independent second contradiction

§B.1 is **LOCKED**:

> *"a cell holding one aggregated price per period is a **unit value**, and unit
> values are biased whenever the items inside are heterogeneous — the exact
> condition that holds for airfares."*

Under §B.2 the cell holds exactly one price per period. **§B.2 constructs
precisely the object §B.1 prohibits.** This holds even if
`min_matched_items_per_cell` were 1, so it is independent of §D.3. **Two LOCKED
sections contradict each other.**

The dossier anticipated it (v2.1, p. 17):

> *"the flight cannot be the item. But the cell cannot simply be substituted for
> it either: if a cell holds one aggregated price per period, a geometric mean
> across quotes inside it is a unit value, not a Jevons index."*

### Two further v2.0 defects found while proving the above

**D-1 — §E.4 contradicts itself.** Prose: *"the cell key with carrier and
flight-identity dropped"*. Tuple: `(route, apw_bucket, fare_class, channel)` —
which additionally drops `day_of_week`.

> ⚠️ **Correction to an earlier analysis in this checkpoint.** It was argued that
> §E.4 was written for the corrected cell and therefore proved the authors meant
> the item/cell split. **That is not supportable.** *"carrier **and
> flight-identity** dropped"* presupposes a cell key that *contains* flight
> identity — the literal §B.2 cell. §E.4 is evidence **for** the broken reading.
> Consequence: AMB-1 is a methodology **change**, not a clarification, so the
> version bump is mandatory.

**D-2 — `ItemKey = departure_time_local` (CODE BUG, independent).** Matching
required the scheduled departure time to be identical to the second across seven
days; a ten-minute retiming unmatched a flight from itself. Repaired
incidentally.

### AMB-6 — **NEW sub-ambiguity discovered during this resolution**

§J.1 requires $I(\text{parent}(c),t)$ — a **parent level** — but neither v2.0 nor
the first draft of this resolution defines how a parent level is computed. §E.4
separately requires a **parent relative**. These are two different objects and
v2.0 defines neither construction. **Resolved in §11 below.**

### 3.4 Attribution register — **the single authoritative list**

Every design element APIx adds beyond what a primary source requires, in one
place, so no presentation, deck or dashboard caption can attribute one of them to
MoSPI by omission.

| # | Element | Label | MoSPI's actual position |
|---|---|---|---|
| 1 | **Carrier in the CELL** | **APIx DESIGN DECISION** | **UNKNOWN** — the airfare specification never mentions carrier |
| 2 | **Channel in the CELL** | **APIx DESIGN DECISION** — *departs from MoSPI* | MoSPI **pools** platforms *"to ensure representativeness"* (EG) |
| 3 | **Seven APW buckets** (`T+1 … T+60`), $\alpha = 1/7$ | **APIx DESIGN DECISION** | A **single 21-day domestic point** (EG §3.9); 60 days is the *international* point |
| 4 | **Daily publication** | **APIx DESIGN DECISION** | Monthly CPI release; weekly online price collection |
| 5 | **The three-tier ladder** (Tier 1 / 2 / 3 and its 70% / 40% thresholds) | **APIx DESIGN DECISION** | No analogue |
| 6 | **Tier unit `(route, carrier)`** | **APIx DESIGN DECISION** | No analogue |
| 7 | **Tier-2 band price** (geometric mean over the band) | **APIx DESIGN DECISION** | No analogue |
| 8 | **Parent fallback design** (`CELL → carrier-pooled PARENT → SUPPRESS`), incl. $J(P,t)$ and $I(P,t)$ | **APIx DESIGN DECISION** | Imputation by a related stratum exists in principle (EG §4.6.1.2(3)); this specific hierarchy does not |
| 9 | **Source precedence** (ordered, versioned, price-blind) | **APIx DESIGN DECISION, PROVISIONAL** | No analogue for online multi-source airfare |
| 10 | **Source-transition treatment** (§15.1) | **APIx DESIGN DECISION** for the *mapping*; the two-consecutive-periods resumption rule it borrows is a **DIRECT MoSPI REQUIREMENT** (EG §4.6.5.2(c)) | Outlet/specification substitution, at monthly cadence |

**Also APIx's own, for completeness:** weekly-matched comparison published daily;
entitlement-derived fare classes and their precedence; the `held_out_weight_share`
diagnostic; `band_overlap` / `band_membership_delta` / within-band dispersion.

**Nothing in this table may be described as a MoSPI rule.** The four elements
APIx *does* take directly from MoSPI are listed in §3.1: Jevons at the elementary
level, Young/Modified Laspeyres above it, elementary indices built from individual
price quotations, and the two-consecutive-periods rule for a new specification.

---

## 4. Observation / Item / Cell / Parent hierarchy — **APIx DESIGN DECISION**, constrained by **DIRECT MoSPI REQUIREMENT** (elementary aggregates pool many quotations)

| | **OBSERVATION** | **ITEM** | **CELL** | **PARENT** | **ROUTE** | **NATIONAL** |
|---|---|---|---|---|---|---|
| **Contains** | one canonical fare, one flight, one source, one instant | `carrier × flight_number` (T1) / `carrier × departure_hour_band` (T2) | `route × carrier × day_of_week × apw × fare_class × channel` | `route × day_of_week × apw × fare_class × channel` | all cells on a route | all routes |
| **Does not contain** | index meaning | a weight; a level | flight identity; source identity | carrier | — | — |
| **Purpose** | raw datum; admissibility; dedup | **matching** across $t$ and $t-7$ | **Jevons averaging + weighting + level** | supplying a **relative** for carry (§E.4) and a **level** for entry (§J.1) | route publication | headline |
| **Matched** | no | **yes** | no (chained) | **yes**, over its own items | no | no |
| **Weighted** | no | **no** — equal weight inside Jevons | **yes** — $v_{c\mid r}$ | **no** — a computation stratum, never a publication stratum | yes — $w_r$ | — |
| **Can recur** | no | **yes, by definition** | yes, weekly on its own chain | yes | yes | yes |
| **Enters** | n/a | on first sighting; contributes from first *matched pair* | at parent's **level** (§J.1) | when its first child exists | at a `basket_version` change | n/a |
| **Exits** | n/a | silently (unmatched → neither side) | suppression (§I), weight renormalised (§F.4) | when no live children remain | basket change | n/a |

### The five-flight test

`DEL-BOM · 6E · Monday · T+7 · STANDARD · AIRLINE_DIRECT`, flights
`6E101 · 6E205 · 6E317 · 6E421 · 6E509`:

> **5 observations → 5 ITEMS → 1 CELL → 1 Jevons relative → 1 cell level → 1 weight.**

Under v2.0 they are **5 cells of 1 item each**, `|M| = 1` in all five, `J`
undefined in all five, and five weights attached to five permanently-carried
levels.

---

## 5. Candidate analysis

| | **A — ADOPTED** | **B** | **C** | **D** |
|---|---|---|---|---|
| ITEM | `carrier × flight_number` | same | same | same |
| CELL | `route × carrier × dow × apw × class × channel` | channel removed | **carrier pooled** | carrier pooled |
| Elementary estimator | unweighted Jevons | unweighted Jevons | unweighted Jevons | **weighted** Jevons, fixed DGCA carrier shares |
| Cells (synthetic frame) | **700** | 700 | **140** | 140 |
| Items/cell (synthetic) | **4.000** | 4.000 × sources | **20.000** | 20.000 |
| Carrier control | fixed weights between cells | fixed weights | ❌ implicit count-weighting, drifts | explicit intra-cell weights |
| Channel control | ✅ | ❌ reverses LOCKED §B.5 | ✅ | ✅ |
| Verdict | **ADOPTED** | **REJECTED** | **not adopted — see §5.1** | **REJECTED** |

**B — REJECTED on evidence.** §B.5 is LOCKED: *"An elementary cell never mixes
channels… Averaging them produces a number that is not the price of anything."*
It also violates §B.6 by multiplying shared inventory into independent
observations.

**D — REJECTED.** It would give both density and explicit carrier control, but
MoSPI's elementary index is an **unweighted** geometric mean of quotations
(EG §4.6.1.1) — a departure at the one level where APIx currently matches MoSPI
exactly — and it requires carrier-share weights of unproven availability.

### 5.1 Candidate C — status, stated precisely

> **Candidate C is a separately versioned future methodology alternative that may
> be evaluated if empirical density under Candidate A is inadequate.**

It is **not** a runtime fallback, not a degradation path, and not reachable by
any code path in v2.1.

```
Runtime APIx behaviour (v2.1):     CELL  ->  PARENT  ->  SUPPRESS
Candidate C:                       future methodology alternative,
                                   would require its own version bump,
                                   ADR, spec amendment and audit
```

Adopting C would be a **new methodology version**, not a configuration change.
Its merits (closer to MoSPI's airfare specification, which never mentions
carrier; materially denser) and its cost (the elementary relative becomes
implicitly count-weighted by carrier) are recorded so a future evaluation starts
from evidence rather than from scratch. Trigger for evaluating it: **OQ-A1**.

### 5.2 Attack log on Candidate A

| # | Objection | Severity | Mitigation | Remaining risk |
|---|---|---|---|---|
| 1 | Mixes unlike products (06:00 vs 21:30 departures) | Low | Jevons averages *relatives*; each matches one flight to itself. MoSPI's own aggregate pools time windows | Time-of-day *mix*. **EMPIRICAL** |
| 2 | Hidden unit value | None at Tier 1 | Unit values require averaging *levels* | Tier 2 (§14) and Tier 3, both declared |
| 3 | Carrier-mix contamination not eliminated | **Medium — CONCEDED** | Confined to carried strata; carry share and parent carrier concentration published | **Real.** See §11.9 |
| 4 | Carrier-specific cells too thin on real routes | **HIGH — dominant risk** | Parent carry, then suppression with published weight share | **Unquantified. OQ-A1** |
| 5 | Carrier exit creates weight shifts | Low | §F.4; exit surfaces as *suppressed weight* | Choice-set change uncaptured. Inherent to matched-model. **Disclosed** |
| 6 | Parent economically heterogeneous | Medium | Pools *relatives*, not levels; fallback only | Carry share published. **EMPIRICAL** |
| 7 | Source duplication inflates effective $N$ | HIGH before §15 | Price-blind versioned precedence | Single-source dependence; spread published |
| 8 | Flight churn breaks matching | Low | Tier ladder; tier published per cell | Selection in surviving set. **OQ-2** |
| 9 | Sell-outs remove dear or cheap quotes | Medium | Excluded and counted | Direction untested. **OQ-3** |
| 10 | Tier-3 dominance | Medium | `max_tier3_weight = 25%` headline caveat | Magnitude unknown. **OQ-A1** |
| 11 | Cell too narrow for a meaningful weight | Low | $\alpha \times \beta \times \delta$ computable at this granularity | Weight concentration. **EMPIRICAL** |
| 12 | `min_matched_items = 3` never calibrated | **HIGH — CONCEDED** | Retained unchanged; one change at a time | **Binding for the first time. OQ-A5** |

Candidate A survives. Objections **3, 4, 7 and 12 are conceded, not answered**;
4 and 12 gate the design on measurement.

---

## 6. Carrier ruling

**Carrier is in the CELL. It is also written into the ITEM key, where it is
load-bearing at the parent level.**

| Aspect | Label |
|---|---|
| MoSPI specifies carrier for airfare | **UNKNOWN** — the airfare specification never mentions it. RBI proposed carrier-level detail (EG §4.5.4); the record does not show it adopted |
| Carrier in the APIx cell | **APIx DESIGN DECISION** |
| Dossier support | *"cells that already hold **carrier**, fare class, channel and advance-purchase window fixed"* (p. 18) — **SOURCE (dossier)** |
| Statistical reason | Carrier is price-determining (APIx's own TPD conditions on it, §M.2). In the cell, a carrier-mix shift moves **fixed weights between cells**; in the item, it moves the **implicit count-weighting inside a cell**, and nothing fixes matched-flight counts — **INFERENCE** |

⚠️ **Corrected wording.** An earlier draft said carrier in the *item* key is
"descriptive and inert because it is constant within a cell." That is true inside
a **cell** and **false at the PARENT**, where carriers are pooled and the item
key's carrier field is what keeps `6E101` and `AI101` distinct. The item key's
carrier field is therefore **normative**, not decorative.

---

## 7. Channel ruling

**Channel stays in the CELL.** §B.5 reaffirmed after explicit re-examination.

```
IndiGo direct ₹6000 · MakeMyTrip ₹6050 · Goibibo ₹6030 · Ixigo ₹6030
```

Three distinct problems, which must not be conflated:

| Problem | Answer |
|---|---|
| **Price concept** | ₹6000 vs the aggregator quotes are **two different price concepts** — carrier-direct payable vs aggregator payable including a platform charge. Both are real transaction prices → **two cells** |
| **Source duplication** | MakeMyTrip and Goibibo share ownership and inventory → **one independent source group** (§B.6) → ~**2** groups, not 3 |
| **Statistical independence** | The remaining quotes are **repeated observations of one item**, not different products |

**4 quotes → 2 price concepts (2 cells) → within `AGGREGATOR`, 1 item observed
through ~2 independent source groups.**

| Aspect | Label |
|---|---|
| Channel in the cell | **APIx DESIGN DECISION that departs from MoSPI** |
| MoSPI practice | *"Since airfares vary by booking platform and time slot, prices were compiled from well-known websites across different time windows to ensure representativeness"* — MoSPI **pools** platforms. **DIRECT MoSPI REQUIREMENT** for their series, not ours |

---

## 8. APW ruling

| Claim | Label |
|---|---|
| MoSPI domestic advance purchase = **21 days**; international = 60 days (EG §3.9) | **DIRECT MoSPI REQUIREMENT** |
| APIx's seven buckets `T+1, T+3, T+7, T+15, T+30, T+45, T+60` | **APIx DESIGN DECISION** |
| $\alpha_{\text{apw}} = 1/7$ | **APIx DESIGN DECISION**, declared in §G.4 pending OQ-7 |
| APW belongs in the CELL (a conditioning characteristic carrying a weight) | **INFERENCE** |

**Why stratify at all.** Lead time is the strongest single price driver in
revenue-managed inventory; a single lead time measures one point on a booking
curve whose *shape* moves. Stratifying and weighting prevents lead-time mix from
entering the index. **INFERENCE — not a MoSPI rule.**

**No APIx bucket currently equals 21 days.** `T+15` and `T+30` straddle it, and
`T+60` coincides with MoSPI's *international* point — which must never be
presented as alignment. Adding `T+21` would make one APIx sub-index directly
comparable to CPI 2024's airfare specification but changes the bucket set and
moves $\alpha$ to $1/8$. **Deliberately excluded from this amendment** —
separable from AMB-1, and bundling two methodology changes into one audit weakens
both. **OQ-A6.**

---

## 9. Day-of-week ruling — **INFERENCE**

`day_of_week` **remains in the cell key**.

| Role | Status |
|---|---|
| Sampling stratifier | **No** |
| Conditioning characteristic adding observations at $t$ | **No** — determined by $(t, \text{apw})$ (Lemma 2). It partitions nothing within a collection date, nor along a chain |
| **Chain and level identity** | **YES — load-bearing.** Remove it and one cell key names **seven different level sequences**, each updated on a different day; $I(c,t)$ would be overwritten daily by a level from a different chain |
| Audit / publication identity | **Yes** — a published series should be fully identified by one key |

**Verdict: technically and audit necessary; not statistically necessary as a
conditioning variable.** Recorded so it is not later deleted as redundant.
Because it is determined, it is **not** an independent weight dimension — §G.3
correctly omits it.

---

## 10. Parent ruling

$$\text{parent}(c) = (\text{route},\ \text{day\_of\_week},\ \text{apw\_bucket},\ \text{fare\_class},\ \text{channel})$$

the cell key with **`carrier` dropped**.

**Why it is the only admissible parent.** A parent is useful only if it releases
a dimension genuinely free at the publication date. At fixed $(t,\text{apw})$,
`travel_date` and `day_of_week` are determined (Lemma 2); the free dimensions are
`carrier`, `fare_class`, `channel`, `route`.

| Candidate parent | Released | Adds observations at $t$? |
|---|---|---|
| drop `day_of_week` only | **none — determined** | ❌ **No.** Its observation set is *identical to the cell's*; whenever the child's relative is undefined the parent's is too. **A dead rule** |
| **drop `carrier`** | carrier | ✅ **Yes** |
| drop `channel` | channel | ✅ but pools two price concepts — forbidden by §B.5 |
| drop `fare_class` | fare class | ✅ but pools entitlement bundles — the comparison §B.4 prevents |

**Fallback ladder — exactly one carry level:**

$$\text{CELL} \;\longrightarrow\; \text{carrier-pooled PARENT} \;\longrightarrow\; \text{SUPPRESS}$$

Reasons: deeper pooling buys coverage by violating a LOCKED homogeneity rule;
§I.1 already defines the terminal behaviour and §F.4 renormalises, so
**suppression is visible in published quality metrics** while a silent
third-level carry is not; and v2.0 §E.4 closes with *"Nothing more sophisticated
ships in v1."* **INFERENCE / APIx DESIGN DECISION.**

---

## 11. Parent matching object — **NEW, fully specified**

*An independent engineer must be able to compute the parent relative from this
section alone.*

### 11.1 Parent ITEM

$$\text{item}_P = (\text{carrier},\ \text{flight\_number}) \quad \text{— identical to the cell's Tier-1 item key}$$

The parent pools carriers, so the item key's `carrier` field is **essential**
here: without it `6E101` and `AI101` would collide. **This is where the item
key's carrier field earns its place. APIx DESIGN DECISION.**

### 11.2 Is it another object?

**No.** The item definition is identical at cell and parent level. Only the
*stratum over which items are pooled* differs. Keeping one item definition is
what makes the carry arithmetically comparable to the cell's own relative.

### 11.3 Parent Tier-2 item

$$\text{item}_P^{T2} = (\text{carrier},\ \text{departure\_hour\_band})$$

**Band membership is scoped to a single carrier.** A band price is never computed
across carriers — that would be a cross-carrier unit value, which §B.1 forbids.

### 11.4 Parent tier selection

The parent takes its tier from the **route-level** identity stability
$\text{IdentityStability}(r)$ — exactly the v2.0 quantity, reused unchanged.
Thresholds 70% / 40% **UNCHANGED**.

**Derived rules, both LOCKED:**

1. A parent's tier may differ from its children's. Both tiers are **recorded on
   every carry** (`cell_tier`, `parent_tier`) so a reviewer can see which
   estimator produced the imputed movement.
2. **A Tier-3 parent has no matched set and therefore no relative.** If
   $\text{tier}(P) = 3$ then $J(P,t)$ is undefined, the carry cannot occur, and
   the cell is **suppressed** (§I.1). This follows from §B.2 and is stated so it
   is not discovered at runtime.

### 11.5 Parent matched set

$$M(P,t) = \{\, i : i \in \text{admissible}(P,t) \ \wedge\ i \in \text{admissible}(P,t-7) \,\}$$

where $\text{admissible}(P,t)$ is the set of admissible observations whose parent
key equals $P$ — that is, the **union over carriers** of the observations in
$P$'s child cells.

> **Computed from OBSERVATIONS, never from cell results.** The parent's matched
> set includes items from child cells that were themselves suppressed, carried or
> excluded from publication. Building the parent from cell outputs would make the
> carry depend on the very failure it exists to repair. **LOCKED.**

Source precedence (§15) and deduplication (§D.4) apply identically at the parent.

### 11.6 Parent minimum-match rule

$$|M(P,t)| \;\ge\; \texttt{min\_matched\_items\_per\_cell} = 3$$

**The same threshold, applied to a new object.** No parent-specific value is
invented. Below it, $J(P,t)$ is undefined, the carry fails and the cell is
suppressed.

**Known weakness, disclosed rather than patched.** Nothing in this rule requires
the parent's matched items to come from **more than one carrier**. A parent whose
matched set is entirely one carrier's flights imputes that carrier's movement to
every other carrier's cell. Two diagnostics are therefore **required**, not
optional:

- `parent_carrier_count` — distinct carriers contributing matched items;
- `parent_carrier_concentration` — share of matched items from the dominant
  carrier.

Whether a minimum carrier count or a concentration ceiling should become a rule
is **OQ-A8**. **No threshold is invented here.**

### 11.7 Estimator

**Identical to §D.2** — the log-form Jevons, equal weight per matched item:

$$J(P,t) = \exp\!\left(\frac{1}{|M(P,t)|}\sum_{i \in M(P,t)}\left[\ln p_{i,t} - \ln p_{i,t-7}\right]\right)$$

§D.7's median/MAD outlier rule applies unchanged, gated at $\ge 5$ candidates.
§D.3's ordering (D.1 → D.7 → D.2) applies unchanged.

### 11.8 How carrier observations are combined

**They are not combined.** Each carrier's flights are separate items; their
log-relatives enter the same equal-weighted arithmetic mean in log space. No
carrier aggregate is formed at any point.

### 11.9 Is carrier mix implicitly count-weighted? — **YES**

$$J(P,t) = \exp\!\left(\sum_k \frac{n_k}{\sum_j n_j} \cdot \overline{\Delta \ln p}_k\right), \qquad n_k = \#\{\text{matched items of carrier } k\}$$

**The parent's relative weights each carrier in proportion to its count of
matched flights.** If IndiGo contributes 12 matched flights and Air India 3, the
parent's movement is 80% IndiGo dynamics — and $n_k$ **drifts week to week**.

**This is the exact channel through which carrier-mix contamination re-enters
Candidate A.** Consequences, stated for the record:

1. Candidate A **confines** carrier-mix drift to carried strata. It does **not**
   eliminate it.
2. **The phrase "carrier mix is controlled by construction" is incorrect and is
   forbidden in APIx documentation, presentations and the dashboard.** The
   accurate claim is *"controlled where the cell computes its own relative;
   confined and measured where it carries."*
3. Exposure is measurable and must be published: carried weight share,
   `parent_carrier_count`, `parent_carrier_concentration`.

**EMPIRICAL / OPEN — OQ-A8.**

### 11.10 The parent is a computation stratum, never a publication stratum

| Quantity | Exists? | How computed | Used by |
|---|---|---|---|
| $J(P,t)$ — parent **relative** | **Yes** | §11.5–11.7, from observations | §E.4 carry **only** |
| $I(P,t)$ — parent **level** | **Yes** | §11.11 below | §J.1 new-cell entry **only** |
| Parent weight | **No** | — | The parent never appears in §F.2 or §F.3 |
| Parent published series | **No** | — | Not a vintage output; available as a diagnostic only |

The parent has no weight, contributes no level to any aggregate, and is never
published as an index.

### 11.11 Parent LEVEL — resolves AMB-6 — **NEW**

§J.1 requires $I(\text{parent}(c),t)$, which v2.0 never defines.

#### 11.11.1 The circularity, stated

A naive definition over *all* live children is **self-referential**. If cell $C$
enters at $t$ under §J.1 with $I(C,t) = I(P,t)$, then including $C$ gives

$$I(P,t) = \tilde v_A I(A,t) + \tilde v_B I(B,t) + \tilde v_C \underbrace{I(P,t)}_{\text{the quantity being defined}}$$

with $I(P,t)$ on both sides. **This must be excluded by definition, not solved as
a fixed point** — a fixed-point solution would make a new cell's own weight
influence the level it enters at, which is exactly the spurious contribution §J.1
exists to prevent.

#### 11.11.2 The independent-live set — **LOCKED**

$$\mathcal{L}^{\text{ind}}(P,t) \;=\; \Bigl\{\, c \in \text{children}(P)\cap L_t \;:\; I(c,t) \text{ is determined without reference to } I(P,t) \,\Bigr\}$$

$$\boxed{\;I(P,t) \;=\; \sum_{c\,\in\,\mathcal{L}^{\text{ind}}(P,t)} \tilde{v}_{c\mid P}\cdot I(c,t), \qquad \tilde{v}_{c\mid P} = \frac{v_{c\mid r}}{\displaystyle\sum_{j\,\in\,\mathcal{L}^{\text{ind}}(P,t)} v_{j\mid r}}\;}$$

Weights are renormalised over $\mathcal{L}^{\text{ind}}(P,t)$ exactly as §F.4
prescribes.

**Which children are excluded — exactly one class.**

| Child's state at $t$ | Its level | In $\mathcal{L}^{\text{ind}}$? |
|---|---|---|
| **Computes its own relative** — $I(c,t)=I(c,t-7)\cdot J(c,t)$ | independent | ✅ **Yes** |
| **Carries** (§E.4) — $I(c,t)=I(c,t-7)\cdot J(P,t)$ | independent | ✅ **Yes** — see 11.11.3 |
| **Enters at $t$ under §J.1 against this parent** — $I(c,t)=I(P,t)$ | **recursive** | ❌ **No — the only exclusion** |
| Suppressed | no level | ❌ not live at all |

#### 11.11.3 Why carried cells are *not* excluded — **the precision that matters**

A carried cell's level depends on the parent's **relative** $J(P,t)$, which is
computed **bottom-up from raw observations** (§11.5–11.7) and is entirely
independent of $I(P,t)$. **No recursion is created.** Excluding carried cells
would discard perfectly well-determined levels, shrink
$\mathcal{L}^{\text{ind}}$ unnecessarily, and make hold-out far more frequent
than the mathematics requires — on thin routes, where carry is common, it could
empty the set almost always.

The recursion is broken independently at every period: a cell that entered at
$t-7$ was excluded from $I(P,t-7)$ *then*, and its level at $t$ is
$I(P,t-7)\cdot J(P,t)$, which references no current-period parent level. **No
recursion, direct or transitive, can arise.** **INFERENCE.**

#### 11.11.4 Empty independent-live set — **LOCKED**

$$\mathcal{L}^{\text{ind}}(P,t) = \varnothing \;\;\Longrightarrow\;\; I(P,t) \text{ is UNDEFINED}$$

Consequences, stated precisely:

- **New-cell entry is impossible.** The candidate cell is **held out** per §J.2 —
  *"If the parent is itself unavailable, the cell is held out until a parent
  level exists. It is never seeded at 100 inside a live aggregate."* **Unchanged
  rule, newly reachable condition.**
- **Held out is not the same as suppressed.** A suppressed cell was live and
  breached a threshold; a held-out cell was never live. Both are excluded from
  the live set and both have their weight renormalised away under §F.4, but they
  are **different quality events** and are reported separately:
  `held_out_weight_share` (**NEW diagnostic**) alongside §I's
  `suppressed_weight_share`. **APIx DESIGN DECISION.**
- **Carries are unaffected.** $I(P,t)$ is required only by §J.1. A cell carrying
  under §E.4 needs $J(P,t)$, not $I(P,t)$, and continues normally.

#### 11.11.5 Why not chain the parent's own relative

$I(P,t) = I(P,t-7)\cdot J(P,t)$ from an independent base is **rejected**: a
separately-chained parent level would drift away from its children's weighted
mean, and seeding a new cell there would inject **exactly the spurious jump §J.1
exists to prevent**. The parent level must be the level the aggregate already
reflects. **INFERENCE.** See the boxed distinction in §11.12.

### 11.12 The four objects, and the one equation that must never be written — **NEW**

$$\boxed{
\begin{aligned}
J(c,t) &\;=\; \textbf{cell relative} && \text{Jevons over } M(c,t) \text{ — raw observations} \\
I(c,t) &\;=\; \textbf{cell level} && \text{chained: } I(c,t-7)\cdot J(c,t) \\
J(P,t) &\;=\; \textbf{parent fallback relative} && \text{Jevons over } M(P,t) \text{ — raw observations, \textbf{bottom-up}} \\
I(P,t) &\;=\; \textbf{parent reference level} && \text{weighted mean over } \mathcal{L}^{\text{ind}}(P,t) \text{ — \textbf{top-down}}
\end{aligned}}$$

$J(P,t)$ and $I(P,t)$ are **different statistical objects computed in opposite
directions from different inputs**, and they serve different rules:

| | Computed from | Direction | Used by | Never used by |
|---|---|---|---|---|
| $J(P,t)$ | raw observations in the parent stratum | **bottom-up** | §E.4 **carry only** | anything that produces a level |
| $I(P,t)$ | independently-determined child levels | **top-down** | §J.1 **new-cell entry only** | anything that produces a relative |

> ### ⛔ FORBIDDEN
> $$I(P,t) \;\ne\; I(P,t-7)\cdot J(P,t)$$
>
> **The parent relative MUST NOT be used to independently chain the parent
> level.** The parent is not a chained index and has no base period, no
> $t_0$ and no history of its own. Writing this equation would create **two
> competing definitions of the parent level** — one chained, one aggregated —
> which would diverge immediately and silently, and would make new-cell entry
> depend on a shadow series nothing else in the specification maintains.
>
> Any future decision to give the parent an independently chained level is a
> **new methodology version**, requiring its own ADR, amendment and audit.

This mirrors §C.4 one level up: *"the construction is relative at the elementary
level, level at every level above it."* Conflating a relative with a level is the
error §C.4 already names as the most common way this construction goes wrong.

---

## 12. Tier-unit ruling — **INFERENCE**

$$\text{IdentityStability}(r,k) = \frac{\#\{\text{flight numbers of carrier } k \text{ on route } r \text{ recurring at the same weekday slot across the window}\}}{\#\{\text{scheduled flights of carrier } k \text{ on route } r\}}$$

- **Cells** take their tier from $(r,k)$ — the `route × carrier` pair.
- **Parents** take their tier from $r$ — the pooled route statistic (§11.4).

**Thresholds 70% / 40% UNCHANGED and remain LOCKED.**

Flight-number stability is a property of the entity that assigns flight numbers:
the carrier. Once cells are carrier-specific, a route-level tier applies one
carrier's instability to every other carrier on the route. v2.0 §B.2 already
promises *"the tier is recorded per cell in the version vector"*; a route-level
statistic cannot populate a per-cell field faithfully.

A route index may contain Tier-1 and Tier-2 cells simultaneously. Not a defect —
§I already publishes tier share **by weight**. **APIx DESIGN DECISION**;
empirical confirmation is **OQ-A3**.

---

## 13. Fare-class ruling — **INFERENCE**

Evaluation order, as an **ordered decision list** (first match wins):

$$\texttt{HAND\_ONLY} \;\rightarrow\; \texttt{STANDARD} \;\rightarrow\; \texttt{FLEX}$$

`FLEX`'s condition **never mentions baggage**, so the precedence question is
really *"does `FLEX` become a baggage-mixed class?"*

| Order | Result |
|---|---|
| `FLEX` first | `FLEX` holds zero-baggage **and** checked-baggage flexible fares. **Baggage uncontrolled inside `FLEX`** |
| **`HAND_ONLY` first** | `FLEX` holds checked-baggage flexible fares only. **All three classes control baggage** |

The only order under which every class is baggage-homogeneous. It also uses each
written condition exactly once and yields a total partition. **Confirms the
behaviour already implemented — no production code change.** Resolves AMB-4.

**Deferred:** entitlements are two independent axes compressed into three ordered
classes. A 2-D `(baggage_tier × flexibility_tier)` scheme is the clean form and
would change §G.3's $\beta$. **OQ-A4** — deliberately not in this amendment.

---

## 14. Tier-2 identity relaxation and band-price ruling — **APIx DESIGN DECISION**

### 14.0 What Tier 2 is, and what it is not — **terminology, LOCKED**

> **Tier 2 is an *identity relaxation*, not a *fallback*.**

It relaxes how specifically an item is identified — from a flight number to a
departure-hour slot — so that a cell whose flight numbers churn can still form a
matched set. **It does not relax the sample requirement, and it does not
guarantee a larger matched sample. It can produce a smaller one** (§14.10).

The word *fallback* is reserved in v2.1 for the **runtime level fallback**
`CELL → carrier-pooled PARENT → SUPPRESS` (§10). Calling Tier 2 a fallback
implies a relaxation of the threshold that does not exist and a gain in density
that is not guaranteed. **Use "Tier-2 identity relaxation" everywhere except when
describing the tier-selection process itself.**

**The four Tier-2 quantities, defined once — index:**

| Term | Definition | Where |
|---|---|---|
| **Stable band membership** | $S_t = S_{t-7}$ for the band, equivalently $\text{band\_overlap}=1$. The condition under which §D.2 telescopes exactly into a flight-level Jevons and the relative carries **no** composition component | §14.2–14.3, §14.11 |
| **`band_overlap`** | $\dfrac{\lvert S_t \cap S_{t-7}\rvert}{\max(n_{b,t},\,n_{b,t-7})} \in [0,1]$ — the direct measure of distance from a true matched model | §14.6 |
| **`band_membership_delta`** | $n_{b,t} - n_{b,t-7}$ — signed change in the band's admissible flight count | §14.6 |
| **Within-band dispersion** | $s_{b,t}$, the standard deviation of $\ln p$ within the band; bounds how far a membership change can move the band price | §14.7 |

All four are recorded per item per period and published as **distributions**
(P10/P25/median/P75/P90), never as means alone.

### 14.1 Definition

For carrier $k$, band $b$, period $t$, over the admissible fares of that
carrier's flights departing in that band:

$$p_{b,t} \;=\; \exp\!\left(\frac{1}{n_{b,t}} \sum_{j \,\in\, b,\,t} \ln p_{j,t}\right), \qquad n_{b,t} = |\{\text{admissible flights of } k \text{ in } b \text{ at } t\}|$$

Computed in log form, consistent with §D.2's normative requirement.

### 14.2 When band membership is unchanged

If the same flight set $\{1,\dots,n\}$ occupies the band at both $t$ and $t-7$:

$$\ln p_{b,t} - \ln p_{b,t-7} = \frac{1}{n}\sum_{j} \ln p_{j,t} - \frac{1}{n}\sum_{j} \ln p_{j,t-7} = \frac{1}{n}\sum_{j}\left[\ln p_{j,t} - \ln p_{j,t-7}\right]$$

The band log-relative is **exactly the arithmetic mean of the individual flights'
log-relatives** — i.e. the log of the geometric mean of their price ratios.

### 14.3 Why the ratio telescopes

Substituting into §D.2:

$$J(c,t) = \exp\!\left(\frac{1}{|M|}\sum_{b \in M}\left[\ln p_{b,t} - \ln p_{b,t-7}\right]\right) = \exp\!\left(\frac{1}{|M|}\sum_{b \in M}\frac{1}{n_b}\sum_{j \in b}\left[\ln p_{j,t} - \ln p_{j,t-7}\right]\right)$$

a **two-stage geometric mean of matched flight ratios, equally weighted per
band**. When every band holds one flight this is *identical* to the Tier-1
Jevons. **No other central-tendency measure has this property** — which is the
whole argument for the geometric mean:

| Option | Verdict |
|---|---|
| **Geometric mean** | **ADOPTED** — the only choice consistent with the log-form Jevons above it |
| Arithmetic mean | **Rejected** — breaks the telescoping identity; creates an arithmetic/geometric mismatch between adjacent stages |
| Median | **Rejected as primary** — inconsistent with Jevons, discontinuous in band membership, and equal to the arithmetic mean for $n=2$. Robustness is already supplied one level up by §D.7 |
| Redefine Tier 2 (rank-match flights within a band) | **Rejected** — rank matching pairs the cheapest to the cheapest, introducing a systematic bias worse than the one it repairs |

### 14.4 When band membership changes

The two band prices are computed over **different flight sets**, so the band ratio
is a **unit-value ratio** and composition enters directly.

**Worked example — zero true price change, large spurious movement.**

```
t-7 : A = ₹5,000   B = ₹6,000                 GM = 5,477.23
t   : A = ₹5,000   B = ₹6,000   C = ₹4,000    GM = 4,932.42
```

$$\text{band relative} = 4{,}932.42 / 5{,}477.23 = 0.9005 \;\Rightarrow\; -9.95\%$$

**No fare moved.** A new cheap flight entered the band. This is the composition
effect in its purest form, and it is not hidden: it is why the diagnostics below
are mandatory rather than optional.

### 14.5 How composition enters

$$\ln p_{b,t} - \ln p_{b,t-7} = \underbrace{\frac{1}{n_t}\sum_{j \in b,t}\ln p_{j,t}}_{\text{over set } S_t} - \underbrace{\frac{1}{n_{t-7}}\sum_{j \in b,t-7}\ln p_{j,t-7}}_{\text{over set } S_{t-7}}$$

Composition enters exactly to the extent that $S_t \ne S_{t-7}$ **and** the fares
within the band are dispersed. If within-band dispersion is zero, membership
changes are harmless regardless of how large they are. That is why dispersion and
membership are published together — neither alone bounds the effect.

### 14.6 `band_membership_delta`

$$\text{band\_membership\_delta}(b,t) = n_{b,t} - n_{b,t-7}$$

recorded per item per period and published as a **distribution**. Alongside it:

$$\text{band\_overlap}(b,t) = \frac{|S_t \cap S_{t-7}|}{\max(n_{b,t},\, n_{b,t-7})} \;\in\; [0,1]$$

$\text{band\_overlap} = 1 \iff$ the telescoping identity of §14.3 holds exactly.
It is the direct measure of how far a Tier-2 relative is from a true matched
model.

### 14.7 Dispersion published

Within-band dispersion of log fares, per band per period:

$$s_{b,t} = \sqrt{\frac{1}{n_{b,t}}\sum_{j \in b,t}\left(\ln p_{j,t} - \overline{\ln p}_{b,t}\right)^2}$$

published as a distribution (P10/P25/median/P75/P90). This mirrors the Tier-3
rule one level down, where §B.2 already requires within-cell dispersion as
*"evidence for or against the homogeneity the fallback assumes."*

### 14.8 Is Tier 2 lower quality than Tier 1? — **Yes, explicitly**

Tier 1 is a pure matched-model relative: every ratio compares one flight to
itself. Tier 2 is matched at the **slot** level and embeds a within-band unit
value whose exposure is bounded by `band_overlap` and $s_{b,t}$. The tier is
recorded per cell and tier share **by weight** is a headline quality metric (§I).

### 14.9 Can Tier 2 be compared directly with Tier 1?

**Comparable in units; not comparable in quality.** Both are dimensionless
seven-day relatives and both must be aggregated into the same route and national
levels — that is required, not optional. But:

- a route's tier composition must accompany any cross-route comparison;
- **a cell whose tier changes mid-year changes its estimator.** The level series
  stays continuous (the cell key is tier-invariant), but the estimator behind it
  does not. This is a **break in estimator, not in identity**, and must be flagged
  in the vintage metadata. **LOCKED disclosure.**

### 14.10 Fewer than three flights in a band; and the threshold

**A band is one item regardless of how many flights it contains.** $n_b \ge 1$
suffices to form a band price. `min_matched_items_per_cell = 3` applies to the
number of **matched bands** in the cell, not to flights within a band. **The same
threshold applies at every tier — UNCHANGED.**

⚠️ **Structural consequence, newly identified.** Three-hour bands anchored at
00:00 give at most **8** possible items per Tier-2 cell, and a realistic
05:00–23:00 operating day occupies about **6**. A Tier-2 cell therefore needs one
carrier's flights spread across **≥3 distinct 3-hour bands in both weeks**. A
carrier with four daily flights clustered into two bands **fails the threshold at
Tier 2 even though it would have passed at Tier 1**. Tier 2 is not uniformly a
more permissive tier. Folded into **OQ-A5** and **OQ-A7**.

**Worked degradation, to make the asymmetry concrete:**

```
Tier 1   6E on DEL-IXC, Monday, T+7, STANDARD, direct
         4 matched flight numbers        |M| = 4  >= 3   -> PUBLISHES

flight numbers churn; the (route, carrier) pair degrades to Tier 2

Tier 2   the same 4 flights occupy only 2 distinct 3-hour bands
         2 matched bands                 |M| = 2  <  3   -> CARRIES
```

`min_matched_items_per_cell = 3` remains **LOCKED for v2.1** and is **not**
adjusted to compensate. Re-evaluation, separately for flights and for bands, is
**OQ-A5** with **OQ-A7** supplying the band-occupancy evidence.

### 14.11 The Tier-2 estimand — **stated precisely**

> **The Tier-2 item represents the carrier's departure-hour slot rather than an
> individual flight identity. Its observed price is a *constructed* band-level
> price — the geometric mean of that carrier's admissible fares departing in the
> band. The Tier-2 relative therefore estimates the seven-day proportional change
> in the geometric-mean fare of that carrier's departures within that slot, on
> that route, weekday, advance-purchase window, fare class and channel.**

| Condition | What the relative measures |
|---|---|
| **Stable band membership** ($\text{band\_overlap}=1$) | Exactly the geometric mean of the matched **flight-level** relatives (§14.3). Pure price movement; no composition component |
| **Changed band membership** ($\text{band\_overlap}<1$) | Price movement **plus a composition component**, whose magnitude is bounded by the product of membership change and within-band dispersion (§14.5) |

**Tier 2 does not remove composition effects. It relocates them from the flight
identity into the band.** The residual is measured, not eliminated, by
`band_membership_delta`, `band_overlap` and within-band dispersion — all
published as distributions.

**Quality standing, restated:** Tier 2 is **lower quality than Tier 1**. Tier-2
and Tier-1 relatives are **comparable in price units** and must be aggregated
together, but they are **not assumed to have equal statistical quality**. Tier
share by weight is a headline quality metric (§I), and a mid-year tier change is
a **break in estimator, not in identity**, flagged in vintage metadata.

---

## 15. Source-precedence ruling — **APIx DESIGN DECISION, PROVISIONAL**

v2.0 defines no reconciliation rule, so the implementation fell back to insertion
order — an arbitrary, undeclared rule. **That is the one outcome unacceptable
under any resolution.**

**The rule.**

1. Collapse sources into **independent source groups** per §B.6.
2. An ordered `source_precedence` list exists **per channel**, in configuration.
3. For each item and period, take the fare from the **highest-ranked source
   present in BOTH $t$ and $t-7$**. If no source is present in both, the item is
   **unmatched** and enters neither side (§D.1).
4. Record the winning `source_id` on the matched pair.
5. Retain all other sources and publish the **cross-source spread** diagnostic.

**Required properties — LOCKED.**

| Property | How met |
|---|---|
| Deterministic | An explicit total order, not dictionary or arrival order |
| **Price-blind** | Selection never inspects the fare. No minimum, median or mean — the rule cannot bias the level by construction |
| **Same-source-paired** | Both legs of a relative come from one source, so a source switch can never masquerade as a price change |
| Versioned | Recorded in the version vector beside `weight_version` |
| Auditable | Winning `source_id` stored per matched pair |
| Reversible | Changing the list is a version-vector change, visible in every vintage |

### 15.1 Source transitions — **NEW, conservative and provisional**

Selection can change between consecutive links even when every individual pair is
same-source. Example:

```
link (t-7, t)     A available, B available   ->  A selected
link (t,  t+7)    A unavailable, B available ->  B selected
```

Define, for item $i$ at $t$:

$$\text{SOURCE\_TRANSITION}(i,t) \iff \sigma(i,t) \ne \sigma(i,t-7) \;\wedge\; \sigma(i,t-7) \text{ is defined}$$

where $\sigma(i,t)$ is the source selected for the link ending at $t$.

**Rule — LOCKED as a procedure, PROVISIONAL as a choice.**

1. The pair is flagged `SOURCE_TRANSITION`.
2. It is **excluded from $M(c,t)$** — no relative is published for that item at
   that link.
3. Diagnostic metadata is retained: both `source_id`s, both prices, the implied
   cross-source gap.
4. The item **resumes automatically** at the first subsequent link where
   $\sigma(i,t') = \sigma(i,t'-1\text{ link})$ — i.e. once the new source has two
   consecutive selected observations.

Exclusion therefore lasts **exactly one link**, and no manual intervention is
required.

**Explicitly forbidden:** bridge adjustments · blending sources · last-write-wins
· carrying the old source's price forward as if observed.

**Placement in the pipeline.** Source selection and transition flagging occur
during matched-pair formation, i.e. **before** §D.7's outlier gate. A
transition-flagged pair therefore never enters the candidate set and cannot
influence the median/MAD computation.

#### ⚠️ What this rule does and does not prevent — stated accurately

The same-source-paired requirement in step 3 of §15 **already makes a
cross-source price comparison impossible**. The relative
$\tfrac{p_B(t+7)}{p_B(t)}$ uses source B on both legs; a carrier-direct ₹6,000
can never be divided by an OTA ₹6,100. **A cross-source ratio is not the failure
mode this rule guards against, and the amendment must not claim it is.**

The real exposure is subtler and still worth a conservative rule: **the item's
series is spliced across two price bases between consecutive links.** Each
relative is clean, but the chained level is a product of A-based relatives
followed by B-based relatives. If the two sources' fee structures drift
differently, the cell's measured movement changes character with no disclosure at
the point of change. Excluding the transition link makes the splice explicit and
countable rather than silent.

**Cost, disclosed:** the rule removes items from $M$ precisely when source
coverage is weakest, which can push a thin cell below §D.3 and increase carry.
The frequency of this is unknown and must be measured — **OQ-A9**.

**MoSPI support — the structure, not the specific rule.** EG §4.6.5.2(c) treats a
disappearing specification the same way: *"the missing price should be imputed for
that month… From the subsequent month onwards, once at least two consecutive
months' prices of the new specification are available, the new specification will
be fully incorporated."* Our two-consecutive-observations resumption condition is
the same structure at weekly cadence. **The mapping of "outlet substitution" onto
"source substitution" is an APIx DESIGN DECISION**; the waiting rule it borrows is
a **DIRECT MoSPI REQUIREMENT**.

**Not decided.** The permanent reconciliation *statistic* is not frozen. Median
across independent source groups is the leading v2.2 candidate and must be chosen
against **measured** spread. **OQ-A2.** Whether the transition exclusion should be
relaxed once cross-source spread is known to be small and stable is part of the
same question.

Rejected: `source_id` in the item key — it would inflate effective $N$ with
shared inventory, violating §B.6.

---

## 16. New-item / new-cell ruling — **DIRECT MoSPI REQUIREMENT** (the waiting rule)

| # | Event | New item? | New cell? | New parent? | Basket event? | Enters at 100? | Inherits parent level? | Waits for a matched pair? |
|---|---|---|---|---|---|---|---|---|
| **1** | New flight number in an existing cell (`6E999`) | **Yes** | No | No | No | **No** | **No** | **Yes** — §D.1. **§J does not fire** |
| **2** | New fare class or channel for an existing carrier/route | Yes | **Yes** | No | No | No | **Yes** — §J.1 | Movement from its first defined $J$ |
| **3** | New channel with no existing stratum | Yes | Yes | **Yes** | No | No | **Held out** until a parent level exists | Yes |
| **4** | New carrier on an existing route | Yes | **Yes** | No — parent is carrier-pooled and exists | No | No | **Yes**, at the parent's level | Yes |
| **5** | New route | Yes | Yes | Yes | **Yes** | No | No — only at a `basket_version` change | n/a |

**Case 1 is what v2.0 got wrong**, because any key without a prior level looked
new. Under v2.1 it is invisible to §J entirely: **a newly appearing flight is not
a price change, and it is not a new elementary aggregate either.**

**MoSPI support:** *"once at least two consecutive months' prices of the new
specification are available, the new specification will be fully incorporated
into the index compilation"* (EG §4.6.5.2(c)) — the same rule at monthly cadence.
**DIRECT MoSPI REQUIREMENT.**

---

## 17. Estimand

> **$J(c,t)$ estimates the mean proportional change, over seven days, in the
> payable fare for a seat on a scheduled IndiGo flight departing Delhi for Mumbai
> on a Monday, purchased exactly seven days before departure, in the
> checked-baggage non-flexible entitlement class, from the carrier's own website
> — averaged geometrically, with equal weight per flight, over those of the
> carrier's Monday flights that were on sale in both weeks.**

| Component | Definition |
|---|---|
| **Population** | IndiGo's scheduled Monday DEL–BOM service in the `STANDARD` entitlement class, quoted at lead time exactly 7 on `AIRLINE_DIRECT` |
| **Sample** | Those flights observed and admissible at $t$ from the precedence-selected source |
| **Matched subset** | $M(c,t)$ — flights admissible at **both** $t$ and $t-7$ **from the same source** |
| **Conditioning characteristics** | route, carrier, departure weekday, exact advance-purchase window, entitlement-derived fare class, channel, source — all identical on both sides of every ratio |
| **Period comparison** | $t$ against $t-7$; never $t-1$ (§C.1–C.2) |
| **Estimator** | log-form Jevons, equal weight per matched item (§D.2) |

**"Comparable" is operationally defined** as: identical route, carrier, weekday,
APW bucket, fare class, channel and source, with the same item key present in
both periods. Nothing else is assumed comparable.

**It is not** the change in the average fare *paid*, and it is not a
passenger-weighted price.

---

## 18. Bias map

| Source of movement | Status |
|---|---|
| Carrier mix — computing cells | **STRUCTURAL CONTROL** (cell key + fixed weights) |
| Carrier mix — carried cells | **UNCONTROLLED, DISCLOSED, MEASURED** (§11.9; OQ-A8) |
| Fare-class mix | **STRUCTURAL CONTROL** |
| APW mix | **STRUCTURAL CONTROL** (cell key + fixed $\alpha$; $\alpha$ itself declared, OQ-7) |
| Weekday mix | **STRUCTURAL CONTROL** |
| Channel mix | **STRUCTURAL CONTROL** |
| Time-of-day mix (Tier 1) | **EMPIRICAL** — affects which relatives are averaged, never levels |
| Time-of-day mix (Tier 2, within band) | **UNCONTROLLED, DISCLOSED** (§14.4–14.7) |
| Flight churn | **STRUCTURAL CONTROL** via the tier ladder |
| Schedule changes | **EMPIRICAL** — matched-model; unmatched items enter neither side |
| Source duplication | **STRUCTURAL CONTROL** via §B.6 + §15; **DIAGNOSTIC** spread published |
| Sell-outs | **EMPIRICAL** — OQ-3, direction untested, **no correction in v1** |
| Selection bias in the surviving matched set | **EMPIRICAL** — OQ-2, measured as match coverage |
| Thin-route coverage | **EMPIRICAL** — OQ-A1, the dominant risk |
| Tier-3 unit-value dominance | **STRUCTURAL** alarm (`max_tier3_weight`), **EMPIRICAL** magnitude |
| Source transition between links | **STRUCTURAL CONTROL** — transition pairs excluded (§15.1); **DIAGNOSTIC** gap recorded; **EMPIRICAL** frequency (OQ-A9) |
| Parent hold-out (empty independent-live set) | **STRUCTURAL** — §J.2 hold-out; **DIAGNOSTIC** `held_out_weight_share`; **EMPIRICAL** frequency (OQ-A9) |
| Carrier exit / choice-set change | **UNCONTROLLED, DISCLOSED** — inherent to any matched-model index |
| Residual quality change | **TPD LATER** (§M) |

**No bias is claimed eliminated where it is merely measured.**

---

## 19. Observability requirements

**SYNTHETIC EVIDENCE** — the benchmark frame is uniform by construction
(4 flights per `route × carrier × apw`), giving 20·5·7 = **700 cells at 4.000
items each** under v2.1 versus **2,800 cells at 1.000** under v2.0. This proves
Candidate A **can** satisfy `|M| >= 3`. **It proves nothing about Indian
schedules.**

**REAL INDIAN AIRFARE EVIDENCE** — none yet exists. It must come from the
seven-day collection spike.

**Metrics required from the spike — as distributions (P10 / P25 / median / P75 /
P90), never as means alone:**

| Metric | Why |
|---|---|
| Items per cell | The AMB-1 metric itself |
| **Matched** items per cell | What §D.3 actually gates on |
| Cell viability rate | Share of cells computing their own relative |
| **Weight viability rate** | **The decisive number** — 90% of cells failing matters little if they carry 5% of weight |
| Tier 1 / 2 / 3 share **by weight** | Headline quality metrics (§I) |
| Parent carry share by weight | Size of the §11.9 contamination channel |
| `parent_carrier_count`, `parent_carrier_concentration` | OQ-A8 |
| Suppressed weight share | §I `max_suppressed_weight` |
| Match coverage | OQ-2 |
| Identity stability, per `route` **and** per `route × carrier` | OQ-A3 |
| Cross-source spread, within and across independent groups | OQ-A2 |
| `band_overlap`, `band_membership_delta`, within-band dispersion | OQ-A7 |
| **Source-transition rate** per item and per cell (§15.1) | OQ-A9 — how often the conservative exclusion bites |
| **`held_out_weight_share`** — weight blocked by an empty independent-live set (§11.11.4) | OQ-A9 |
| Band occupancy — distinct 3-hour bands occupied per `(route, carrier, weekday)` | OQ-A7, and the direct input to the Tier-2 density question |

> ### Weight viability is the decision metric, not cell count
>
> **`weight_viability` is more decision-relevant than raw cell count** and is the
> number the go/no-go decision turns on. A design can lose most of its cells and
> remain sound if those cells carry little weight; it can retain most of its cells
> and be unusable if the failures are concentrated in heavy strata.
>
> ```
> cell viability 42%  ·  weight viability 91%   ->  potentially acceptable
> cell viability 81%  ·  weight viability 38%   ->  serious failure
> ```
>
> Both must be published together. Neither alone is interpretable.

**No number in this table may be resolved by choosing a plausible value.**

---

## 20. End-to-end fixtures (specified, not implemented)

| ID | Assertion | Would it have caught AMB-1? |
|---|---|---|
| **E2E-01** | ≥3 recurring Tier-1 items in one valid cell → $J$ defined | **Yes — on day one** |
| **E2E-02** | Some items disappear, ≥3 remain → $J$ defined from survivors only | Yes |
| **E2E-03** | <3 remain → $J$ undefined; carrier-pooled parent carry fires | Yes |
| **E2E-04** | Two carriers' flights on one route land in **different cells** | Partially |
| **E2E-05** | Monday observations never pair with Tuesday | No |
| **E2E-06** | Tier-2 identity relaxation: numbers churn, bands recur → $J$ defined; `band_overlap` recorded | Yes |
| **E2E-06b** | Tier-2 **density regression**: 4 matched flights collapse into 2 bands → $\|M\|=2$ → cell **carries**, proving the relaxation does not relax the threshold | New (§14.10) |
| **E2E-07** | Tier-3 declared unit value + dispersion published | Yes |
| **E2E-08** | **Items-per-cell distribution** on a full-frame day, asserting a stated floor | **Yes — this is the fixture whose absence is the root cause** |
| **E2E-09** | Parent relative computed from **observations**, not from cell results — a suppressed child still contributes its items to $M(P,t)$ | New (§11.5) |
| **E2E-10** | Parent **level** equals the renormalised weighted mean of live children, and a new cell entering there moves $I(r,t)$ by zero | New (§11.11, AMB-6) |

### Permanent testing doctrine — **to be adopted repository-wide**

> **Unit tests verify functions. End-to-end statistical fixtures verify that the
> correct statistical objects reach those functions.**
>
> Every methodology-bearing layer must carry **at least one fixture that runs raw
> observations through to a published number.**

AMB-1 survived 16 hand-calculated golden values, an invariant suite and a
12-dimension adversarial review because **not one of them started from an
observation**. The benchmark found it because it was the first thing to run the
pipeline end to end.

---

## 21. Hostile MoSPI review

1. **"Why this cell?"** It is the coarsest grouping holding every price-determining characteristic we observe identical, and the finest carrying a weight — matching EG §4.2.1's *"smallest groups… for which expenditure data are available."* Conceded: far finer than your airfare aggregate.
2. **"Why is a flight number an item?"** Because it is what recurs. §B.1 states explicitly that it is a recurring product class, **not** the same physical flight.
3. **"Why carrier in the cell?"** **UNKNOWN in your methodology — this is ours.** Justified because a full-service and a low-cost seat are different products and our own hedonic model conditions on carrier.
4. **"Why channel in the cell?"** Also ours, and it **departs from you**: you pool platforms for representativeness; we separate them because a carrier-direct fare and an aggregator fare differ by a convenience charge, and we publish the gap.
5. **"Why seven APW buckets?"** Ours. You use one 21-day domestic point. Lead time is the strongest price driver in revenue-managed inventory, and a single point measures one place on a moving curve.
6. **"Why not simply your 21-day method?"** No APIx bucket currently equals 21 days — a real gap. We have recorded adding `T+21` as OQ-A6 precisely so one sub-index becomes directly comparable to CPI 2024.
7. **"Why do you stratify finely when we pool more under sparsity (EG §4.4.3–4.4.4)?"** **Accepted as the strongest objection.** Our answer is volume, not principle: ~15,000–35,000 quotes/day against a handful per route per month. If measured density does not support it, Candidate C is documented as a future methodology alternative — not as a runtime escape hatch.
8. **"Why is three matched items enough?"** It is not derived. It was locked against an object for which no threshold was meaningful, and it is now binding for the first time. **OQ-A5.**
9. **"What happens when the cell is thin?"** It carries the carrier-pooled parent's relative; if that is also undefined it suppresses, weight renormalises, and the suppressed share is published.
10. **"When a carrier disappears?"** Its cells suppress and surface as suppressed weight. We do **not** capture the price effect of losing a cheap option — no matched-model index does, and we say so.
11. **"When a flight changes schedule?"** Under v2.1 the item is the flight number, so a retiming no longer unmatches it. Persistent renumbering drops the `(route, carrier)` pair down the tier ladder.
12. **"What exactly does Tier 2 measure?"** The seven-day change in the geometric-mean fare of one carrier's flights within a 3-hour departure band. It embeds a within-band unit value whose exposure is `band_overlap` and within-band dispersion, both published.
13. **"What exactly does Tier 3 measure?"** A declared unit value for one carrier, one route, one weekday, one lead time, one class, one channel, with within-cell dispersion published and a headline caveat above 25% weight share.
14. **"Is source precedence introducing bias?"** Yes — single-source dependence. It is **price-blind**, so it cannot bias the level by construction; the exposure is a parser or fee change at one source, which the published cross-source spread is designed to expose.
15. **"How do you know these prices are comparable?"** "Comparable" is defined operationally in §17 as an explicit list of identical characteristics plus same-source pairing. Nothing beyond that list is assumed.
16. **"How do you separate composition from price movement?"** Within a cell, by item-to-item matching. Between cells, by weights fixed for the index year. What remains is selection in the surviving matched set, and carrier mix inside carried strata — both **measured, not assumed away**.
17. **"What evidence will prove this works on Indian data?"** None yet. OQ-A1 through OQ-A8 and OQ-2 are the tests, and the seven-day spike is where they are answered.

---

## 22. Final recommendation

```
ITEM      Tier 1 : carrier × flight_number
          Tier 2 : carrier × departure_hour_band
                   band price = geometric mean of that carrier's admissible
                   fares in the band (§14)
          Tier 3 : none — declared unit value

CELL      route × carrier × day_of_week × apw_bucket × fare_class × channel
          invariant across all three tiers

PARENT    route × day_of_week × apw_bucket × fare_class × channel
          J(P,t) : Jevons over the parent's own matched items, computed
                   BOTTOM-UP from OBSERVATIONS         -> §E.4 carry only
          I(P,t) : weighted mean over the INDEPENDENT-LIVE set, computed
                   TOP-DOWN from child levels          -> §J.1 entry only
                   (§J.1 entrants at t are excluded; carried cells are NOT)
                   empty independent-live set -> I(P,t) undefined -> hold out
          FORBIDDEN: I(P,t) = I(P,t-7) x J(P,t)
          never weighted, never published as an index

TIER UNIT cells: (route, carrier)    parents: route    thresholds 70/40 UNCHANGED

RUNTIME FALLBACK      CELL -> carrier-pooled PARENT -> SUPPRESS

CHANNEL   inside the CELL (§B.5 reaffirmed)
APW       7 buckets, alpha = 1/7; T+21 NOT added (OQ-A6)
DAY OF WEEK   in the CELL as the chain identifier
FARE CLASS    HAND_ONLY -> STANDARD -> FLEX
SOURCE        versioned, price-blind, per-channel, same source in both periods;
              a SOURCE_TRANSITION between links excludes that pair for exactly
              one link and is recorded as a diagnostic (§15.1)
TIER 2        identity relaxation, NOT a threshold relaxation; band price =
              geometric mean; can yield FEWER matched items than Tier 1
NEW ITEM      not a cell event; waits for its first matched pair
NEW CELL      enters at the parent's LEVEL, never at 100
JEVONS        UNCHANGED at both cell and parent level

METHODOLOGY VERSION   2.0 -> 2.1
```

**Why this design was selected.**

> **Candidate A is the selected v2.1 APIx design because it provides a coherent
> interpretation of the amended specification while preserving the strongest
> comparability controls available to APIx.**

It is **not** presented as derived from MoSPI. The supporting points, each
labelled: it is the only reading under which §B.1, §B.2, §D.1 and §D.3 of the
**APIx specification** hold simultaneously (**INFERENCE**, about our own document,
not MoSPI's); it preserves MoSPI's elementary structure — an
unweighted Jevons over many individual matched quotations (**DIRECT MoSPI
REQUIREMENT**); the dossier's only cell-constraining sentence lists carrier, fare
class, channel and APW and omits flight number (**SOURCE — dossier**); its
new-item rule is MoSPI's own replacement rule (**DIRECT MoSPI REQUIREMENT**); the
cell is tier-invariant so weights cannot reshuffle mid-year (**INFERENCE**); its
parent is the only one that adds observations (**proved**); and its failure mode
is bounded and visible (**INFERENCE**).

---

## 23. Version decision

**`methodology_version 2.0 → 2.1` is REQUIRED.**

The test is whether **identical observations can produce different statistical
results** under the amended definitions. They can: different cells, different
matched sets, different relatives, different levels, different weight vectors,
different tier assignments. A patch-level bump would falsely assert
reproducibility across 2.0 and 2.0.x.

It is a **METHODOLOGY CHANGE, not a WORDING CLARIFICATION**, because §E.4's prose
shows the v2.0 authors did intend the tier key as the cell (§3, D-1). We are
changing the methodology, not restoring an intended one.

A **minor** bump rather than major is correct: the index construction, formula
family, weight hierarchy, publication cadence and version-vector structure are
all unchanged. The elementary unit is redefined; the index is not replaced.

---

## 24. Open empirical questions

| ID | Question | Blocks | Path |
|---|---|---|---|
| **OQ-A1** | Distribution of matched items per cell on real Indian schedules; **share of cell weight that computes rather than carries** | Whether Candidate A holds or Candidate C is evaluated | 7-day spike |
| **OQ-A2** | Cross-source spread within and across independent source groups | Freezing the permanent reconciliation statistic | 7-day spike |
| **OQ-A3** | Identity stability per `(route, carrier)` vs per `route` | Confirms or refutes the tier-unit change | 7-day spike |
| **OQ-A4** | Prevalence of zero-baggage flexible fares | Whether a 2-D fare-class taxonomy is warranted | 7-day spike |
| **OQ-A5** | Re-derivation of `min_matched_items_per_cell`, separately for Tier 1 (flights) and Tier 2 (bands, capped at ~6 realistic) | The computed/carried ratio | After OQ-A1 |
| **OQ-A6** | Add `T+21` so one APIx bucket aligns with MoSPI's domestic point? | CPI airfare benchmark comparability (relates to OQ-6) | Owner decision, **separable from AMB-1** |
| **OQ-A7** | Tier-2 `band_overlap`, `band_membership_delta` and within-band dispersion | Whether the geometric-mean band price holds or Tier 2 needs redefinition | 7-day spike |
| **OQ-A8** | Parent carrier count and concentration on carries — is a minimum carrier count or concentration ceiling needed? | Size of the §11.9 contamination channel | 7-day spike |
| **OQ-A9** | **NEW.** Frequency of (a) source transitions under §15.1 and (b) empty independent-live sets under §11.11.4 — how often do the two conservative rules withhold data, and does either concentrate in heavy strata? | Whether the transition exclusion and the hold-out rule are affordable as written | 7-day spike |

v2.0 §S OQ-1 … OQ-8 are unaffected. **OQ-2 is now tightly coupled to OQ-A1** and
should be measured in the same pass.

**AMB-2** and **AMB-3** are resolved as wording clarifications in the amendment.
**AMB-4** is confirmed as implemented. **AMB-5** (MAD exact-zero guard) remains
**OPEN and untouched**. **AMB-6** (parent level undefined) is resolved in §11.11.

---

*No production code, production test, golden fixture, PR, commit or push was
made in producing this document.*
