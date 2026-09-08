# Contributing to APIx

APIx produces numbers that a statistical office is meant to be able to adopt.
That sets the bar: a change is finished when someone else can verify what it
does, not when it appears to work.

Read [`docs/dossier/APIx_Engineering_Dossier_v2.1.pdf`](docs/dossier/APIx_Engineering_Dossier_v2.1.pdf)
first. It is authoritative. If a change seems to require contradicting it,
**report the inconsistency** — do not silently resolve it.

## Before you start

1. [Set up your environment](docs/engineering/development-setup.md), including
   the per-repository Git identity.
2. Confirm you are the **owner** of the task
   ([ownership-policy.md](docs/engineering/ownership-policy.md)). If you are not,
   the task belongs to someone else.
3. Verify the checkout is healthy: `pytest tests/test_architecture.py`.

## The workflow

`DEFINE → PLAN → BUILD → TEST → REVIEW → SHIP`

These phases are not ceremony, and collapsing them into one unverified code dump
is the failure this project is least able to absorb. Details and the skill for
each phase: [agent-skills.md](docs/engineering/agent-skills.md).

### DEFINE

Understand the requirement. Write down the acceptance criteria, the constraints,
the owner, and which domains the change touches. If the requirement is unclear,
interrogate it before implementing it.

### PLAN

Break the work into small atomic steps. Identify dependencies, the tests that
will prove it, and the rollback point.

### BUILD

Implement incrementally. Keep changes scoped. **No unrelated refactors** — they
make a diff unreviewable and hide the change that matters inside noise.

### TEST

Run the relevant automated tests. Add invariant or property tests where they
apply. **Verify the failure cases**, not only the happy path. Confirm the
acceptance criteria from DEFINE.

For anything under `statistics/`, coverage is the wrong target. An index engine
can reach full line coverage while computing the wrong number. See the invariant
list in [CLAUDE.md](CLAUDE.md).

### REVIEW

Review your own diff before asking anyone else to. Consider architecture impact,
security implications, methodology implications and code quality.

### SHIP

Commit with the correct identity, push, open a PR with evidence attached, and
wait for review.

## Branches and commits

```
<type>/<contributor>/<scope>
```

`feat/rexy/jevons-elementary-relative`, `feat/slazy/indigo-collector`,
`feat/basant/provenance-screen`.

[Conventional Commits](https://www.conventionalcommits.org/). Squash merge.
Never force-push `main`. Full policy:
[branching-policy.md](docs/engineering/branching-policy.md).

## Pull requests

Fill in every section of the template. "N/A" is a fine answer — it records that
you considered the question. Deleting a section is not, because a reviewer
cannot distinguish "no methodology impact" from "nobody checked".

Attach **evidence**: command output, a CI link, screenshots for UI changes.
"Should work" is not verification.

**Do not open PRs to inflate a contribution count.** A merged PR should represent
a known-good project state.

## Rules that do not bend

### The statistics layer is deterministic

`statistics/` must never import `sklearn`, `lightgbm`, `xgboost`, `torch`,
`anthropic` or `openai`, nor `analytics/` nor `ai/`.

`tests/test_architecture.py` enforces this in CI. Do not weaken, skip, or mark
it advisory. If your change seems to need it, the change belongs in `analytics/`
or `ai/`.

### The formula specification comes first

`docs/methodology/apix_formula_spec_v1.md` must be frozen before the first line
of statistics code. Two developers reading the same statistical prose implement
two different indices; a frozen symbol table is what removes the interpretation.

### Commit identity is not negotiable

The Git identity must match the task's owner. Never fake authorship. Never
rewrite history to balance contribution statistics. If the required GitHub
identity is unavailable, **stop before commit and push** and report it.

### No bypass techniques

No CAPTCHA solver, no fingerprint evasion, no identity rotation to defeat access
controls. An access challenge is a stop signal. Do not propose or implement
otherwise.

### Placeholders never ship

Figures marked *illustrative* or *indicative* in the dossier must be replaced
with measured values before any external artifact. Dossier section 16 lists
eleven open verification items — none of them is settled by argument.

## Reporting inconsistencies

If the dossier, the code and the documentation disagree, that is a finding.
Open an issue describing what you observed, where, and what you expected.

The precedent for how to record one is
[docs/agentos/UPSTREAM_PATCHES.md](docs/agentos/UPSTREAM_PATCHES.md): three
defects found in the vendored AgentOS framework, one patched because the
framework could not otherwise be verified, two reported and deliberately left
alone. Each with measurements and reproduction steps.

## Questions

Open a [question issue](.github/ISSUE_TEMPLATE/question.md). Asking early is
cheaper than a rewrite.
