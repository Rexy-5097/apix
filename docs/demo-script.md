# APIx — 4-minute demo script

> **Audience:** MoSPI internal hackathon jury, 15 September 2026.
> **Total:** 4:00. Rehearse to land under 5:00 including questions mid-flow.

## Before you start

Open these, in this order, and do not switch away from them:

| # | Surface | Command / file |
|---|---|---|
| 1 | Real-market dashboard | `data/dashboard.html` |
| 2 | Terminal, ready to run | `python tools/analysis/engine_demo.py` |
| 3 | Engine validation page *(optional backup)* | `data/engine-validation.html` |

**The one rule:** surfaces 1 and 3 must never be on screen at the same time. One
is real market data; the other is a synthetic fixture. Keeping them apart on
screen is the same discipline that keeps them apart in the repository.

**Do not say:** "our index", "our inflation number", "fares rose 38.6%",
"production-ready", "nationally representative".

---

## 0:00 – 0:40 · The problem

> "A fare on a website is an observation. It is not automatically a price index
> observation.
>
> Airfare is the weakest measurement point in the CPI transport basket. Rail,
> fuel, telephone, postage — all priced from an administrative source with one
> authoritative provider. Airfare is collected from commercial, dynamically
> priced consumer websites.
>
> A single sector can vary two to four hundred percent within a day. **Most of
> that is not inflation — it is product mix**: different booking horizons, fare
> families, departure times, baggage terms. An index built on naive daily
> averages accumulates that as chain drift, which is a bias, not noise. It does
> not average out with more data."

## 0:40 – 1:30 · Real market evidence

**Show: dashboard, section 01 (APW profile).**

> "This is real market data. 35 observations, DEL–BOM, IndiGo Saver, collected
> on 12 September under a fixed protocol. All seven frozen advance-purchase
> buckets — T+1 through T+60.
>
> **And immediately: this is descriptive evidence, not an index.**"

*(Point at the banner: DESCRIPTIVE APW PROFILE — NOT AN INDEX.)*

**Scroll to section 02 (confound) — do not skip this.**

> "Here is why. Each bucket sits on a different travel date. Seven buckets, five
> distinct weekdays — Sunday and Tuesday each appear twice. So lead time is
> confounded with travel date and day of week.
>
> The T+60 bucket is 38.6% above T+1. **That is a descriptive difference between
> two cross-sections, not a price movement, and not inflation.** T+60 falls days
> after Diwali. A return-travel peak is a hypothesis this panel cannot test."

## 1:30 – 2:15 · Evidence integrity

**Show: sections 03, 06, 07.**

> "T+3 has the widest dispersion — 24.9%, against 10.8% for the next widest. We
> report the dispersion and name the two flights behind it. **We do not call it
> an anomaly**, because no anomaly-detection definition is in force.
>
> 35 of 35 collection-plan slots filled. **Plan completion — not statistical
> coverage.** The methodology gates routes at 60% of *expected cells*, and
> nothing in the frozen spec defines an expected cell. That is AMB-8, open. We
> have not invented a denominator to make this look finished.
>
> Every fare reconciles: base plus tax equals total, 35 of 35, in exact decimal.
> 122 screenshots that did not become observations each carry a reason and an
> id — and for the mechanical ones that is no longer our word for it. We replay
> them through the frozen §A.3 and §B.2 code: **45 of 46 mechanically decidable
> exclusions reproduce the recorded verdict, zero disagreements**, one record has
> no readable departure time so no rule can decide it, and the same checks admit
> all 35 accepted observations with **zero false rejections**. The other 76 are
> selection-rule or unreadable-field records — the engine has no verdict on those
> and we don't claim one.
>
> Nine quotes fell outside our declared collection window — stored and flagged,
> never discarded.
>
> Provenance is not uniform: 30 observations are bound to SHA-256 hashed
> screenshots. Five — the T+45 bucket — arrived as chat images, so no bytes
> could be hashed. **We say so before you ask.**"

## 2:15 – 3:20 · The engine

**Switch to the terminal. Run it live.**

```bash
python tools/analysis/engine_demo.py
```

> "Everything so far was evidence. This is the engine.
>
> This runs the real index path over a **controlled synthetic fixture** — the
> same fixture CI runs on every commit. Nothing here is airfare.
>
> Matched sets at t and t−7. Jevons relatives: two links moved at exactly
> 1.040000 — the fixture scales every price by 1.04, and the Jevons of items all
> scaled by *k* is exactly *k*, so you can check it by hand. Three links flat at
> exactly 1.000000 — and note the engine reports 1.0, **not** 'undefined'. A
> measured no-change and an absent measurement are different statements.
>
> Then chaining across 14 consecutive publication dates. The level holds between
> weekly links and moves once per link. A seven-day relative applied daily would
> compound sevenfold; the test suite asserts that compounded value as forbidden.
>
> And last — the engine refusing. Feed it a state dated after the period being
> published and it raises, rather than inventing a level."

## 3:20 – 4:00 · Statistical integrity

**Switch back to the dashboard status strip.**

> "So: the engine is finished and we can run it for you right now.
> **What we will not do is run it on evidence that doesn't exist.**
>
> The methodology is frozen. §C.1 says the index at time *t* is the index at
> *t−7* times the Jevons relative. We hold one collection wave. One wave gives
> zero matched pairs. So APIx publishes **no index value**, and the dashboard
> says PENDING — not because the software is unfinished, but because the
> evidence the formula requires is not there.
>
> **The first real matched pair becomes available on 19 September** — seven days
> after the wave we hold. Same route, same carrier, same five bands, same
> protocol. Everything downstream of that is already implemented and tested.
>
> We would rather show you a system that refuses to publish than a number we
> cannot defend."

---

## If asked

**"Why not just show a number?"**
> Any number today would need either a changed formula or treating seven
> different products as one product observed seven times. Both are refused.

**"Is this MoSPI's methodology?"**
> No, and we do not claim it is. We follow MoSPI on Jevons at the elementary
> level and Young/Modified Laspeyres above it. The seven-bucket stratification
> is ours. MoSPI has not endorsed APIx. Our own spec records counter-evidence:
> MoSPI answers airfare sparsity by pooling *more* routes, the opposite
> direction to ours.

**"What about the quality-adjusted estimator?"**
> APIx-TPD is specified in §M and **not implemented** — that package is empty.
> The panel is also 35 quotes against a 1,500-quote threshold. Both are true and
> we state both.

**"Confidence intervals?"**
> None, anywhere. No estimator is implemented, and the collection design does
> not yet record the admissible-flight universe per band, so it does not carry
> the sampling-design information a conventional interval would need. We report
> observed dispersion, which assumes nothing. Capturing that universe is on the
> 19 September collection plan.

**"Is this nationally representative?"**
> No. One route, one carrier. Route and carrier weighting are implemented but
> not exercised, and AMB-9 — no carrier term in the within-route weight formula —
> is open and must be ruled on before any multi-carrier route.
