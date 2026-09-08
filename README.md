# APIx

**A quality-adjusted, high-frequency airfare price index for India — and the
auditable infrastructure that produces it.**

Built against MoSPI problem statement **26056**, Data Informatics & Innovation
Division.

> **Status: Task 0 — bootstrap.** Repository, AgentOS initialisation, Agent
> Skills workflow, CI baseline and governance only. No APIx feature code has
> been written yet. See [`context/state.md`](context/state.md).

---

## The problem

A fare appearing on a website is an observation. It is not automatically a price
index observation.

Airfare is the weakest measurement point in the CPI transport basket. Every
other item in its neighbourhood — rail, fuel, telephone, postage — is priced
from an administrative source with a single authoritative provider. Airfare is
the exception: collected from commercial, dynamically-priced consumer websites,
with extreme heterogeneity and no administrative feed reporting the transacted
consumer price.

A single sector can vary 200–400% within a day. **Much of that variation is not
inflation** — it is product mix: different advance-purchase windows, fare
families, departure times, baggage and refundability terms. An index built on
naive daily averages accumulates those composition effects as **chain drift**,
which is a bias, not noise. It does not average out with more data.

## The approach

Two estimators, one deterministic spine, computed from the same canonical
observations by parallel paths that are **never chained together**.

| | **APIx-L** — the headline | **APIx-TPD** — quality-adjusted |
|---|---|---|
| Method | Jevons short index at the elementary level, Young / Modified Laspeyres above | Quote-level Time Product Dummy hedonic regression, rolling window, mean-spliced |
| Character | Deterministic, formula-transparent, no ML in the code path | An estimate under a stated hedonic model |
| Purpose | A series a statistical office could adopt without changing its methodology | An independent quality-adjusted estimate of price movement |

**The gap between the two series is the deliverable.** It answers how much
observed airfare movement survives conditioning on product composition, and how
much does not.

## The architectural rule

```
STATISTICS CALCULATES.  ML/AI EXPLAINS.
```

Three layers with a hard boundary. The boundary is not a diagram convention — it
is enforced in CI by [`tests/test_architecture.py`](tests/test_architecture.py),
which fails the build if anything under `statistics/` imports `sklearn`,
`lightgbm`, `xgboost`, `torch`, `anthropic`, `openai`, or the layers above it.

The published index must be reproducible from
`(snapshot_id, methodology_version, weight_version, code_version)` alone.

**Removal test:** delete the Claude API integration and the entire analytics
layer. Collection, cleaning, deduplication, Jevons, Young/Modified Laspeyres,
TPD and index publication must all still work.

## Compliance

There is **no CAPTCHA solver, no fingerprint evasion, and no identity rotation
intended to defeat access controls.** An access challenge is treated as a stop
signal: the collector backs off, the event is logged, source confidence is
reduced, and a permitted alternate channel takes over.

A national statistical instrument cannot rest on techniques that violate the
terms of the sources it depends on. This is a design constraint, not a
limitation to apologise for.

## Repository layout

```
schemas/       canonical contracts — written before any collector
ingestion/     collectors, compliance gate, snapshot store
statistics/    deterministic, no ML imports, invariant-tested
  elementary/    Jevons relatives, matched-item tier ladder
  aggregation/   Young / Modified Laspeyres, weights
  tpd/           TPD specification, estimator, splice
  uncertainty/   cell bootstrap
  index/         APIx assembly, publication, vintages
analytics/     anomaly, forecasting, shock, decomposition   (reads the index)
ai/            explanation, parser diagnosis, schema mapping (reads the index)
api/           FastAPI, SDMX serialisers
dashboard/     Next.js
experiments/   six controlled scenarios, ablations
docs/          methodology, engineering, the dossier
tests/         architecture boundary, property and invariant tests
```

The AgentOS framework tree (`runtime/`, `agents/`, `standards/`, `workflows/`,
`checklists/`, `templates/`, `profiles/`, `validation/`, `tools/scripts/`) is
vendored infrastructure.

## Getting started

```bash
git clone https://github.com/Rexy-5097/apix.git
cd apix

python -m venv .venv && .venv/Scripts/activate      # Windows
# python3 -m venv .venv && source .venv/bin/activate  # macOS / Linux

pip install -e ".[dev]"

pytest tests/test_architecture.py                    # the boundary must pass
python tools/scripts/validate_agentos.py             # AgentOS health
```

Full instructions, including multi-account Git setup:
[docs/engineering/development-setup.md](docs/engineering/development-setup.md).

## Source of truth

**[`docs/dossier/APIx_Engineering_Dossier_v2.1.pdf`](docs/dossier/APIx_Engineering_Dossier_v2.1.pdf)**
is authoritative for methodology, architecture, sources, compliance, gates and
risks. Read it before making a project decision. If something appears
inconsistent with it, report the inconsistency rather than silently resolving it.

Figures marked *illustrative* or *indicative* in the dossier are placeholders and
must be replaced with measured values before any external presentation. Dossier
section 16 lists eleven open verification items that cannot be settled by design
discussion.

## Documentation

| Document | What it covers |
|---|---|
| [CLAUDE.md](CLAUDE.md) / [AGENTS.md](AGENTS.md) | Project instructions for AI coding agents |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
| [AGENTOS.md](AGENTOS.md) | AgentOS initialization protocol (vendored) |
| [docs/engineering/ownership-policy.md](docs/engineering/ownership-policy.md) | Who owns what, and commit identity rules |
| [docs/engineering/branching-policy.md](docs/engineering/branching-policy.md) | Branch naming, commits, merge strategy |
| [docs/engineering/checkpoint-policy.md](docs/engineering/checkpoint-policy.md) | The seven known-safe checkpoints |
| [docs/engineering/branch-protection.md](docs/engineering/branch-protection.md) | Required `main` protection settings |
| [docs/engineering/agent-skills.md](docs/engineering/agent-skills.md) | The DEFINE → SHIP engineering workflow |
| [docs/engineering/development-setup.md](docs/engineering/development-setup.md) | Environment and multi-account setup |
| [docs/agentos/UPSTREAM_PATCHES.md](docs/agentos/UPSTREAM_PATCHES.md) | AgentOS defects found, and the one patch applied |
| [docs/methodology/README.md](docs/methodology/README.md) | The formula specification that gates all statistics code |

## Team

| Contributor | Domain |
|---|---|
| [@Rexy-5097](https://github.com/Rexy-5097) | Principal engineering — architecture, statistics, methodology, experiments |
| [@slazyverse](https://github.com/slazyverse) | Data engineering — ingestion, compliance, sources, data quality |
| [@Basant-creator](https://github.com/Basant-creator) | Product engineering — API, SDMX, dashboard |

## Licence

[MIT](LICENSE).
