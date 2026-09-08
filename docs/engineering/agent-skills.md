# Agent Skills — the APIx engineering workflow

APIx uses [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)
as its engineering process. The skills are workflows with verification steps,
quality gates, anti-pattern checks and exit criteria — not prompt decoration.

## What is installed, and how

| Field | Value |
|---|---|
| Source | `addyosmani/agent-skills` |
| Plugin version | 0.6.9 |
| Install command | `npx skills add addyosmani/agent-skills --skill '*' --agent claude-code --copy -y` |
| Scope | Project-level, committed to the repository |
| Location | `.claude/skills/` (25 skills), `.claude/references/` (7 shared checklists) |
| Lock file | `skills-lock.json` |

Skills are **copied, not symlinked** (`--copy`). Symlinks do not survive a
Windows clone with `core.symlinks=false`, and this repository has contributors on
Windows. Copying also means the skills are pinned in Git: every contributor gets
the same workflow on clone, and a skill upgrade is a reviewable diff rather than
a silent change in behaviour.

### The `references/` gap, and what was done about it

A per-skill install copies `skills/<name>/` but not the repository-level
`references/` directory — the upstream README documents this, tracked as
[issue #361](https://github.com/addyosmani/agent-skills/issues/361).

Ten skills cite shared checklists as `../../references/<file>.md`. Left
uncorrected, every one of those links would dangle. The upstream README's
recommended remedy was applied: the seven shared checklists were copied to
`.claude/references/`, which is exactly where `../../references/` resolves from
`.claude/skills/<skill>/SKILL.md`. All citations were then verified to resolve.

### Reinstalling or updating

```bash
npx skills add addyosmani/agent-skills --skill '*' --agent claude-code --copy -y
npx skills update --project -y
```

After any update, re-copy the shared checklists and re-verify the links:

```bash
# from a clone of addyosmani/agent-skills
cp references/*.md /path/to/apix/.claude/references/
```

### Contributors on other agents

The skills CLI supports 70+ agents. The same skill set installs elsewhere with:

```bash
npx skills add addyosmani/agent-skills --skill '*' --agent <agent> --copy -y
```

`--agent` accepts `cursor`, `codex`, `gemini-cli`, `windsurf`, `opencode` and
others. Only the `claude-code` installation is committed, to avoid four copies
of 25 skills in the tree. This matches AgentOS's third law — vendor neutrality,
with vendor adapters kept isolated.

## The lifecycle

```
DEFINE → PLAN → BUILD → TEST → REVIEW → SHIP
```

No phase is skipped because an implementation appears to work. "It runs" is not
a verification result.

| Phase | Skill | What it produces |
|---|---|---|
| **DEFINE** | `spec-driven-development` | A specification with acceptance criteria before code exists |
| | `interview-me` | Requirements interrogation when the ask is underspecified |
| | `constraint-driven-development` | Explicit constraints, including statistical ones |
| **PLAN** | `planning-and-task-breakdown` | Atomic steps, dependencies, tests, rollback point |
| **BUILD** | `incremental-implementation` | Scoped changes; no unrelated refactors |
| **TEST** | `test-driven-development` | Red-green-refactor, enforced |
| **REVIEW** | `code-review-and-quality` | Five-axis review before merge |
| | `security-and-hardening` | Threat and hardening review |
| **SHIP** | `ci-cd-and-automation` | Pipeline and automation changes |
| | `shipping-and-launch` | Launch readiness |
| **META** | `using-agent-skills` | Which skill applies to the task at hand |

## Task-specific skills

Load the skill the task needs. Loading unrelated skills into every task wastes
context and dilutes the guidance that actually applies.

| Work | Skill | Typical owner |
|---|---|---|
| Dashboard, screens, charts | `frontend-ui-engineering` | Basant-creator |
| API routes, SDMX contracts | `api-and-interface-design` | Basant-creator |
| UI verification in a browser | `browser-testing-with-devtools` | Basant-creator |
| Collector failures, parser drift | `debugging-and-error-recovery` | slazyverse |
| Collection reliability, source health | `observability-and-instrumentation` | slazyverse |
| Bootstrap runtime, query cost | `performance-optimization` | Rexy-5097 |
| ADRs, methodology notes | `documentation-and-adrs` | Rexy-5097 |
| Branching, commits, releases | `git-workflow-and-versioning` | all |
| Methodology version transitions | `deprecation-and-migration` | Rexy-5097 |
| Claims needing a primary source | `source-driven-development` | Rexy-5097 |
| Checking a load-bearing assumption | `doubt-driven-development` | Rexy-5097 |

`source-driven-development` and `doubt-driven-development` deserve emphasis on
this project. Dossier section 16 lists eleven open verification items that
cannot be settled by design discussion — each needs a primary document or a live
collection run. That is exactly the failure mode those two skills guard against.

## How this composes with AgentOS

The two systems answer different questions and do not overlap.

- **AgentOS** governs *routing and gating*: which reviewer agent sees a change,
  which quality gate applies, which artifact gets written. Configured by
  `PROJECT_CONFIG.yaml` (profile `flagship`: all 9 standards, 11 agents, 8 gates).
- **Agent Skills** governs *how the work is done inside a phase*: how a spec is
  written, how tests are driven, what a review actually checks.

A task therefore runs the AgentOS lifecycle (`AGENTOS.md` section 13) and reaches
for the Agent Skill appropriate to the phase it is in.

## Where verification is non-negotiable

Two APIx-specific rules override any skill's default sense of "done":

1. **The statistics determinism boundary.** `tests/test_architecture.py` must
   pass. No skill's exit criteria supersede it — the boundary is a published
   methodology guarantee (dossier section 05).
2. **No unevidenced claim ships.** Figures marked *illustrative* or *indicative*
   in the dossier are placeholders. They must be replaced with measured values
   before any external artifact, and `source-driven-development` is the workflow
   for establishing that evidence.
