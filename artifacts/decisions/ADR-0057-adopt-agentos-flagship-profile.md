# ADR-0057: Adopt AgentOS with the flagship profile

> **Status:** Accepted | **Date:** 2026-09-08 | **Decider:** Rexy-5097

---

## Context

APIx needs an engineering operating system that routes work to the right
reviewer, applies the right standard, and gates milestones — across three
contributors working in three different domains, on a project whose output is
meant to be adoptable by a statistical office.

AgentOS ([Rexy-5097/raptors-way](https://github.com/Rexy-5097/raptors-way)) is a
**template repository**: you clone it, run `tools/scripts/bootstrap_project.py`
in place, and the project is built inside the resulting tree. It ships eight
profiles, from `hackathon` (2 standards, 1 agent, 2 gates) to `flagship` (all 9
standards, all 11 agents, all 8 gates).

## Decision

Vendor the AgentOS template at commit `2cf150ff771a9b230bae4602cab83ac2c7a686d8`
(`VERSION` 1.0.0), remove its `.git`, and initialise APIx inside it through the
supported bootstrap workflow:

```bash
python tools/scripts/bootstrap_project.py --config apix_bootstrap.yaml
```

Select the **`flagship`** profile.

`apix_bootstrap.yaml` is committed, so the initialisation is reproducible rather
than a one-off interactive session.

### Why flagship

APIx spans every domain the profile system distinguishes:

- deterministic statistics and research validity → `research`, `ai_ml`
- ingestion, medallion layers, data contracts → `data_engineering`
- FastAPI and SDMX contracts → `api_design`
- a Next.js dashboard → `ui_ux`
- compliance and source terms → `security`

A narrower profile would disable the reviewer for at least one domain that
carries real risk. `ai_project`, the default, enables neither `data_engineering`
nor `api_design` nor `ui_ux` — three of APIx's four delivery surfaces.

The eight quality gates matter for the same reason: QG-004 (research validation)
and QG-005 (security review) map directly onto the dossier's controlled
experiments and its compliance position.

## Consequences

- All 9 standards, 11 agents and 8 gates are active. `PROJECT_CONFIG.yaml`
  records this and is read at the start of every session.
- The APIx repository contains the AgentOS framework tree (`runtime/`, `agents/`,
  `standards/`, `workflows/`, `checklists/`, `templates/`, `profiles/`,
  `validation/`, `tools/scripts/`) as vendored infrastructure, plus 56 upstream
  ADRs. APIx ADRs continue the numbering from 0057.
- Upstream defects become APIx's problem to work around — see
  [ADR-0058](ADR-0058-patch-agentos-validator-repo-root.md).
- Upgrading AgentOS means re-vendoring and re-applying the recorded patch.
  `docs/agentos/UPSTREAM_PATCHES.md` is the complete list of what to re-apply.
- The `flagship` profile is heavier than a hackathon timeline would choose. That
  is deliberate: the dossier's own risk register names *"team overbuilds and
  nothing integrates"*, and the counter-measure is the gate discipline, not a
  lighter profile.
