# Technology stack

> **Source of truth:** dossier section 13. Chosen for what ships, not for what
> impresses on a slide. Everything below is either load-bearing or cut.

## Committed

| Area | Choices |
|---|---|
| **Collection** | Python 3.12, Playwright (async), Scrapy, httpx, Amadeus Self-Service, Travelpayouts |
| **Compliance** | robots.txt parser, `pyrate-limiter`, `tenacity`, `registry.yaml` |
| **Processing** | Polars, PyArrow, NumPy, Pydantic v2, Pandera contracts |
| **Statistics** | SciPy, statsmodels, custom Jevons, custom Young/Modified Laspeyres, custom TPD + splice, cell bootstrap |
| **Analytics** | LightGBM, Isolation Forest, `ruptures` |
| **Storage** | PostgreSQL 16, MinIO / S3, Parquet, Redis |
| **Orchestration** | cron + Python entrypoint, Docker Compose |
| **Serving** | FastAPI, SQLAlchemy, SDMX-JSON output |
| **Interface** | Next.js + TypeScript, Tailwind, ECharts |
| **Quality** | pytest + Hypothesis, VCR.py cassettes, ruff, mypy, GitHub Actions |
| **Explanation** | Claude API — **strictly Layer 3** |

## Deferred, and not built

Airflow · ClickHouse · Kafka / Redpanda · TimescaleDB · Kubernetes ·
OpenTelemetry

These are on a scaling roadmap. The dossier's risk register names *"team
overbuilds and nothing integrates"* with the response *"the deferred stack stays
deferred"*. Adding one of these is a decision that needs an ADR, not a
convenience.

## The dependency rule that overrides convenience

Anything under `statistics/` may not import `sklearn`, `lightgbm`, `xgboost`,
`torch`, `anthropic` or `openai`.

LightGBM and Isolation Forest appear in the analytics row above and are welcome
there. That split is the whole point: the same library is fine in Layer 3 and
forbidden in Layer 2, because Layer 2 carries the reproducibility guarantee.

`tests/test_architecture.py` enforces it in CI.

## Versions in force

| Tool | Dossier | This repository | Note |
|---|---|---|---|
| Python | 3.12 | `requires-python = ">=3.12"` | The bootstrap machine has 3.13.5; CI pins 3.12 |
| Node.js | — | 20+ | Dashboard and the Agent Skills CLI |
| AgentOS | — | 1.0.0 (`raptors-way@2cf150f`) | Vendored; see `docs/agentos/UPSTREAM_PATCHES.md` |
| Agent Skills | — | 0.6.9 | Vendored under `.claude/skills/` |

## Not yet installed

Task 0 declares **no runtime dependencies**. `pyproject.toml` lists only dev
tooling (pytest, Hypothesis, ruff, mypy, PyYAML). Nothing in dossier sections
06–12 is implemented, so nothing that implements it is declared.

Dependencies are added per checkpoint, in the pull request that first needs them.
