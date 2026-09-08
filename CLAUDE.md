# APIx — project instructions for AI coding agents

> Vendor-neutral copy: [AGENTS.md](AGENTS.md). Keep the two in sync.

## The source of truth

**`docs/dossier/APIx_Engineering_Dossier_v2.1.pdf` is authoritative.**

Read it before making any project decision. It governs the product thesis,
statistical architecture, source strategy, compliance boundaries, comparability,
the matched-item ladder, APIx-L, APIx-TPD, the experiments, validation,
publication and revision policy, provenance, technology choices, gates, risks
and open verification items.

**Do not silently alter a decision the dossier has made.** If something appears
inconsistent — with the dossier, with the code, or with itself — report it.
Do not quietly fix it and move on.

## What APIx is

A quality-adjusted, high-frequency airfare price index for India, and the
auditable infrastructure that produces it. Built against MoSPI problem statement
26056, Data Informatics & Innovation Division.

Two estimators are published from the same canonical observations, computed by
parallel paths that are **never chained together**:

- **APIx-L** — the headline. Jevons short index at the elementary level, then
  Young / Modified Laspeyres above it. Deterministic, formula-transparent, no
  machine learning anywhere in the code path.
- **APIx-TPD** — a quote-level Time Product Dummy hedonic regression over a
  rolling window, spliced forward. A quality-adjusted estimate under a stated
  model, not a detector of what is "really" happening.

The gap between them is the deliverable.

The primary user is a statistical analyst deciding whether the series is
adoptable. Anything that makes the system more useful to a consumer and less
legible to a statistician is out of scope by construction.

## The rule that is enforced, not just stated

```
STATISTICS CALCULATES.  ML/AI EXPLAINS.
```

`statistics/` must never import:

```
sklearn   lightgbm   xgboost   torch   anthropic   openai
```

nor `analytics/` nor `ai/`.

The published index must be reproducible from
`(snapshot_id, methodology_version, weight_version, code_version)` alone.

This is enforced by `tests/test_architecture.py`, which runs in CI and fails the
build. **Do not weaken, skip or mark that test advisory.** If a change seems to
require it, the change belongs in `analytics/` or `ai/` instead.

Removal test: delete the Claude API integration and the whole analytics layer.
Collection, cleaning, deduplication, Jevons, Young/Modified Laspeyres, TPD and
index publication must all still work.

## Before you write statistics code

`docs/methodology/apix_formula_spec_v1.md` must be **frozen first** — the
methodology symbol by symbol, not prose about it. The dossier is explicit about
why: two developers reading the same statistical prose implement two different
indices.

If that file is not frozen, writing index code is out of order. Say so.

## Repository layout

```
schemas/       canonical contracts — written before any collector
ingestion/     collectors, compliance gate, snapshot store
statistics/    deterministic, no ML imports, invariant-tested
  elementary/    jevons.py, matching.py (tier ladder)
  aggregation/   young_laspeyres.py, weights.py
  tpd/           specification.py, estimator.py, splice.py
  uncertainty/   bootstrap.py
  index/         apix.py, publication.py, vintages.py
analytics/     anomaly, forecasting, shock, decomposition
ai/            explanation, parser diagnosis, schema mapping
api/           FastAPI, SDMX serialisers
dashboard/     Next.js
experiments/   the six controlled scenarios, ablations
docs/          methodology, engineering, dossier
tests/         incl. test_architecture.py, property tests
```

The AgentOS framework tree (`runtime/`, `agents/`, `standards/`, `workflows/`,
`checklists/`, `templates/`, `profiles/`, `validation/`, `tools/scripts/`) is
vendored infrastructure. See [docs/agentos/UPSTREAM_PATCHES.md](docs/agentos/UPSTREAM_PATCHES.md)
before editing anything in it.

## Testing means invariants, not coverage

An index engine can reach full line coverage while computing the wrong number.
The statistics layer is held to invariants that must hold for any correct
implementation (dossier section 13):

- Identical prices in both periods produce an index of exactly 100.
- Scaling every price by *k* leaves the index unchanged; relatives are invariant.
- The index equals 100 in the base period by construction.
- Weight vectors sum to one, before and after suppression and renormalisation.
- Reordering observations within a period changes no output.
- Missing cells follow the declared rule and nothing else; no cell is silently dropped.
- Every threshold in dossier section 08 has a test crossing it in both directions.
- Recomputing from the same version vector reproduces the published value bit for bit.

## Ownership and identity

Three contributors, one primary owner per task. The Git identity used for a
commit **must** be the owner of that task.

| Domain | Owner |
|---|---|
| Statistics, methodology, experiments, architecture | [@Rexy-5097](https://github.com/Rexy-5097) |
| Ingestion, compliance, sources, data quality | [@slazyverse](https://github.com/slazyverse) |
| API, SDMX, dashboard, product surface | [@Basant-creator](https://github.com/Basant-creator) |

Never default to Rexy-5097 because Rexy-5097 owns the repository. Never fake
authorship. Never rewrite history to balance contribution statistics.

**If the required GitHub identity is unavailable, STOP before commit and push.**
Report the blocker instead of substituting another contributor.

Full matrix: [docs/engineering/ownership-policy.md](docs/engineering/ownership-policy.md).

## Workflow

`main` is protected. Work happens on `<type>/<contributor>/<scope>` branches —
see [docs/engineering/branching-policy.md](docs/engineering/branching-policy.md).
Conventional Commits. Squash merge. Never force-push `main`.

Engineering process is the Agent Skills lifecycle, DEFINE → PLAN → BUILD → TEST
→ REVIEW → SHIP: [docs/engineering/agent-skills.md](docs/engineering/agent-skills.md).
Do not collapse those phases into one unverified code dump.

AgentOS governs routing and gating. Read `AGENTOS.md`, then `context/state.md`
and `PROJECT_CONFIG.yaml`, at the start of a session.

## Compliance is a design constraint, not an obstacle

There is **no CAPTCHA solver, no fingerprint evasion, and no identity rotation
intended to defeat access controls.** An access challenge is a stop signal: the
collector backs off, the event is logged, source confidence drops, and a
permitted alternate channel takes over.

A national statistical instrument cannot rest on techniques that violate the
terms of the sources it depends on. Do not propose or implement bypass
techniques.

## Honesty rules specific to this project

- Figures marked *illustrative* or *indicative* in the dossier are placeholders.
  They must never reach an external artifact unmeasured.
- Dossier section 16 lists eleven open verification items. Each needs a primary
  document or a live collection run. Do not treat any of them as settled.
- Two weight sources are **not secured**: DGCA city-pair passenger volumes, and
  a booking lead-time distribution. v1 uses equal APW weights as a declared
  choice with a sensitivity band. Do not invent a curve.
- Validation against published CPI is **short-window validation, not a
  back-test**, at n = 2 monthly points. Report direction agreement and magnitude
  gap with n stated.
- Never claim success without evidence. If tests fail, say so with the output.

## Current phase

Task 0 — bootstrap. See `context/state.md`.

**No APIx feature work has started.** Scraping, adapters, parsing, matching,
Jevons, Young/Modified Laspeyres, TPD, bootstrap, forecasting, anomaly
detection, dashboard and API business logic are all out of scope until the
bootstrap checkpoint is reviewed.
