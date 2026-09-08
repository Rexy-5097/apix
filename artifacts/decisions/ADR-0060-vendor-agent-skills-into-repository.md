# ADR-0060: Vendor Agent Skills into the repository

> **Status:** Accepted | **Date:** 2026-09-08 | **Decider:** Rexy-5097

---

## Context

APIx uses [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills)
v0.6.9 as its engineering process — 25 skills covering DEFINE → PLAN → BUILD →
TEST → REVIEW → SHIP.

The upstream README documents several installation routes:

1. `npx skills add addyosmani/agent-skills` — the skills CLI, 70+ agents
2. `/plugin marketplace add` + `/plugin install` — the Claude Code plugin marketplace
3. `git clone` + `claude --plugin-dir` — local development

Routes 2 and 3 install **per machine**. Three contributors would then each be
responsible for having the right skills at the right version, and a change in the
team's engineering process would not be visible in any diff.

## Decision

Install project-level with the skills CLI, **copying rather than symlinking**,
and commit the result:

```bash
npx skills add addyosmani/agent-skills --skill '*' --agent claude-code --copy -y
```

Committed: `.claude/skills/` (25 skills), `.claude/references/` (7 shared
checklists), and `skills-lock.json`.

### Why copy, not symlink

The CLI symlinks by default. Symlinks do not survive a Windows clone with
`core.symlinks=false`, which is the configuration on at least one contributor's
machine. Copying also makes a skill upgrade a **reviewable diff** rather than a
silent change in how the team works.

### Why only the `claude-code` agent

Installing for four agents would put four copies of 25 skills in the tree. Only
`claude-code` is committed; `docs/engineering/agent-skills.md` gives the
one-line command for any other agent. This matches AgentOS's third law — vendor
neutrality with adapters kept isolated.

### The `references/` gap

A per-skill install copies `skills/<name>/` but not the repository-level
`references/` directory — documented upstream, tracked as
[issue #361](https://github.com/addyosmani/agent-skills/issues/361). Ten skills
cite shared checklists as `../../references/<file>.md`, and all ten would dangle.

The upstream README's recommended remedy was applied: the seven shared
checklists were copied to `.claude/references/`, which is exactly where
`../../references/` resolves from `.claude/skills/<skill>/SKILL.md`. Every
citation was then verified to resolve.

## Consequences

- Every contributor gets an identical engineering process on clone, with no
  setup step and no version drift between machines.
- The skill set is pinned in Git and in `skills-lock.json`. Upgrading is a
  deliberate, reviewed act.
- After any `npx skills update`, the shared checklists must be re-copied and the
  links re-verified — recorded in `docs/engineering/agent-skills.md`.
- The repository carries roughly 25 skill directories of vendored Markdown. That
  is the cost of reproducibility, and it is small.
- Skills run with full agent permissions. They are vendored at a reviewed version
  rather than fetched at run time, which is the safer default for a repository
  three people push to.
