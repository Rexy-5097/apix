# APIx

**A quality-adjusted, high-frequency airfare price index for India — and the
auditable infrastructure that produces it.**

Built against MoSPI problem statement **26056**, Data Informatics & Innovation
Division.

> **Status — hackathon prototype, 15 September 2026.** APIx is a
> frozen-specification airfare index **engine** with a real-market evidence
> pipeline. The complete seven-bucket advance-purchase panel for DEL–BOM has
> been collected and audited under a fixed collection protocol. The engine is
> implemented and tested, but **APIx deliberately does not publish a market
> index yet**, because the longitudinal evidence the frozen methodology requires
> does not exist. See [`context/state.md`](context/state.md).
>
> | | State |
> |---|---|
> | Real observations | **35** · 7/7 frozen APW buckets · DEL–BOM · IndiGo · collected 2026-09-12 |
> | APIx-L engine | **implemented, tested** — verified end to end over 14 consecutive publication dates |
> | APIx-L index value | **PENDING** — §C.1 needs matched `t / t−7`; one wave held. Unlocks 2026-09-19 |
> | APIx-TPD | **specified (§M), NOT implemented** — no estimator exists |
> | Uncertainty / CI | **NOT implemented** — no interval is reported anywhere |
> | National representativeness | **not established** — 1 route, 1 carrier |

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
| **Status** | **Engine implemented and tested.** No index value published — see above | **Specified (§M). Estimator NOT implemented.** |

**Design intent — not a present deliverable.** The gap between the two series is
what APIx is ultimately for: it answers how much observed airfare movement
survives conditioning on product composition, and how much does not.
**That comparison cannot be produced today.** APIx-L is blocked on a second
collection wave, and APIx-TPD has no estimator — `src/apix/statistics/tpd/` is an
empty package. Nothing in this repository currently computes a two-estimator
divergence, and no such figure is published anywhere.

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
layer. Collection, cleaning, deduplication, Jevons, Young/Modified Laspeyres and
index publication must all still work — they do, and `test_architecture.py`
enforces it. (TPD is named in this rule by design, but is not implemented yet,
so it is not part of what the test currently exercises.)

## Compliance

There is **no CAPTCHA solver, no fingerprint evasion, and no identity rotation
intended to defeat access controls.** An access challenge is treated as a stop
signal: the collector backs off, the event is logged, source confidence is
reduced, and a permitted alternate channel takes over.

A national statistical instrument cannot rest on techniques that violate the
terms of the sources it depends on. This is a design constraint, not a
limitation to apologise for.

## Repository layout

Every row states what is actually on disk today. **`EMPTY` means the package
exists as a namespace and contains no implementation** — it is a reserved slot,
not working code.

```
src/apix/
  schemas/       IMPLEMENTED  collection, enums, keys, observation, results,
                              version_vector
  ingestion/     IMPLEMENTED  store.py (SQLite snapshot store)
  statistics/    deterministic, no ML imports, invariant-tested
    elementary/  IMPLEMENTED  jevons, matching, admissibility, bands, dedup,
                              outliers, sources
    aggregation/ IMPLEMENTED  young_laspeyres, weights, within_route
    index/       IMPLEMENTED  apix_l, chaining, linking, parent, publication
    tpd/         EMPTY        SPECIFIED in methodology §M; estimator NOT written
    uncertainty/ EMPTY        bootstrap SPECIFIED; estimator NOT written
  analytics/     EMPTY        anomaly, forecasting, shock, decomposition — planned
  ai/            EMPTY        explanation, parser diagnosis — planned
  api/           EMPTY        FastAPI, SDMX serialisers — planned
  experiments/   EMPTY        six controlled scenarios — planned
dashboard/       README only  the delivered dashboard is generated HTML, below
docs/            methodology, engineering, the dossier
tests/           architecture boundary, property and invariant tests
tools/analysis/  panel + dashboard generators, engine demo
```

**The dashboard is generated, never hand-authored:**

```
data/collection/collection.sqlite3          the store (real observations)
  -> tools/analysis/build_panel_json.py
  -> data/panel.json                        the contract every renderer reads
  -> tools/analysis/build_dashboard.py      -> data/dashboard.html
  -> tools/analysis/panel_report.py         -> data/panel_report.txt

tools/analysis/engine_demo.py               engine run on a SYNTHETIC fixture
  -> data/engine-validation.html            separate file, never merged above
```

The dossier's section 13 tree is rooted at `apix/`, so those layers are the
contents of the `apix` **package**. A `src/` prefix makes that literal and stops
`statistics/` shadowing Python's standard-library module — see
[ADR-0061](artifacts/decisions/ADR-0061-statistics-package-layout.md).

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
