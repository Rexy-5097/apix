# Project Vision: APIx

> **Status:** Active | **Owner:** Rexy-5097
> **Source of truth:** `docs/dossier/APIx_Engineering_Dossier_v2.1.pdf`
> **Problem statement:** MoSPI 26056, Data Informatics & Innovation Division

---

## 1. Problem statement

A fare appearing on a website is an observation. It is not automatically a price
index observation.

Airfare is the weakest measurement point in the CPI transport basket. Every other
transport and communication item in CPI 2024 is priced from an administrative
source with a single authoritative provider — rail from the Ministry of Railways,
fuel from PPAC, telephone from operators and TRAI, postage from the Department of
Posts. Airfare is the exception: collected from commercial, dynamically-priced
consumer websites, with extreme heterogeneity, and with **no administrative feed
reporting the transacted consumer price**.

A single sector can vary 200–400% within a day. Much of that variation is **not
inflation** — it is product mix: quotes collected at different advance-purchase
windows, in different fare families, on different departure times, with different
baggage and refundability terms. A daily-chained index built on naive averages
accumulates those composition effects as **chain drift**, which is a bias, not
noise. It does not average out with more data.

APIx is the measurement, engineering and validation infrastructure that decides,
transparently and reproducibly, whether an observation is statistically
comparable — and how much it should contribute to a measure of inflation.

## 2. Who this is for

**Primary user:** a statistical analyst evaluating whether a series is adoptable
— someone who will ask what the elementary aggregate is, where the weights came
from, and what happens when a cell disappears. Every screen and every API field
is designed to answer that person without a phone call.

**Secondary user:** a monetary-policy economist who needs the series, its
revision status and its uncertainty.

**Explicitly not:** a fare-prediction tool for travellers, a price-comparison
service, or a regulatory compliance instrument. Anything that makes the system
more useful to a consumer and less legible to a statistician is out of scope by
construction.

## 3. The approach

Two estimators, one deterministic spine, computed from the same canonical
observations by parallel paths that are **never chained together**.

- **APIx-L** — the headline. Jevons short index at the elementary level, Young /
  Modified Laspeyres above it. This is the aggregation architecture MoSPI itself
  uses in CPI 2024. Deterministic, formula-transparent, no machine learning
  anywhere in the code path. Purpose: a series a statistical office could adopt
  without changing its methodology.
- **APIx-TPD** — a quote-level Time Product Dummy hedonic regression over a
  rolling window, spliced forward. An independent quality-adjusted estimate under
  a stated hedonic model. It is another estimator under assumptions, not a
  detector of what is "really" happening.

**The gap between the two series is the deliverable.**

## 4. The architectural commitment

```
STATISTICS CALCULATES.  ML/AI EXPLAINS.
```

Three layers with a hard boundary, enforced by a CI import check that fails the
build. The published index must be reproducible from
`(snapshot_id, methodology_version, weight_version, code_version)` alone.

Removal test: delete the Claude API integration and the entire analytics layer,
and the index must still publish.

## 5. Compliance position

No CAPTCHA solver, no fingerprint evasion, no identity rotation intended to
defeat access controls. An access challenge is a stop signal. A national
statistical instrument cannot rest on techniques that violate the terms of the
sources it depends on.

## 6. Success criteria

1. The controlled experiment shows measured drift in scenario A and **bounded,
   stated degradation in scenario F** — the misspecified case.
2. APIx-L is computable from real collected data at a declared matched-item tier.
3. Every published value walks down to the raw snapshot bytes that produced it.
4. Every threshold, weight source and formula is inspectable without reading code.
5. The statistics layer imports nothing stochastic, and CI proves it.
6. No figure marked *illustrative* or *indicative* survives into an external
   artifact.

## 7. Known-unresolved at bootstrap

Recorded here because the dossier records them, and inventing answers would be
worse than not having them.

- **Route weights** — DGCA city-pair passenger volumes may not be public at the
  assumed granularity. Fallback: scheduled seat capacity by city pair, with a
  stated and testable bias.
- **Advance-purchase weights** — no known public Indian booking lead-time
  distribution. v1 uses equal APW weights as a declared choice with a sensitivity
  band.
- **Matched-item tier** — whether flight identity is stable enough for Tier 1 is
  measured during the collection spike, not assumed. Gate 4 can reshape the
  design.
- **Benchmark granularity** — whether the CPI airfare item is published at item
  level with usable history. Handled by configuration, not code.

Dossier section 16 lists eleven such items in full.

## 8. Milestones

Checkpoints 0–6, defined in `docs/engineering/checkpoint-policy.md`.

Currently at **Checkpoint 0 — bootstrap**. No feature work has begun.
