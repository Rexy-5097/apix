# Checkpoint policy

A checkpoint is a known-safe project state: a commit on `main` that a
contributor can return to when something later goes wrong, knowing it builds,
its tests pass, and its behaviour was reviewed.

Checkpoints are the rollback targets named in every pull request. A PR that
cannot name one has no recovery plan.

## What makes a state known-safe

All of the following, or it is not a checkpoint:

1. Merged into `main` through a reviewed pull request.
2. CI green — including `tests/test_architecture.py`, the determinism boundary.
3. The milestone's exit condition met, as listed below.
4. Tagged, so it can be found without reading the log.

## Planned checkpoints

| # | Name | Contents | Primary owner |
|---|---|---|---|
| **CHECKPOINT 0** | Repository + AgentOS + Agent Skills bootstrap | Repository baseline, AgentOS initialisation, Agent Skills workflow integration, CI baseline, CODEOWNERS, PR/issue templates, engineering documentation. No APIx feature code. | Rexy-5097 |
| **CHECKPOINT 1** | Contracts and methodology specification | Canonical schemas frozen. `docs/methodology/apix_formula_spec_v1.md` frozen, symbol by symbol, before any statistics code exists. | Rexy-5097 |
| **CHECKPOINT 2** | Synthetic statistical core | Jevons, Young / Modified Laspeyres, the tier ladder, invariant property tests, the six controlled experiments, bootstrap timing — all on synthetic data. | Rexy-5097 |
| **CHECKPOINT 3** | Live collection vertical slice | One collector, Bronze → Silver → Gold, tier assignment, one API route, one chart. One real index number from one real collection run, rendered in a browser. | slazyverse |
| **CHECKPOINT 4** | Complete index/statistics pipeline | Remaining collectors, compliance gate, outlier and imputation modules, TPD with thresholds, bootstrap intervals. Both estimators publish. | Rexy-5097 |
| **CHECKPOINT 5** | API/dashboard integration | Five screens, SDMX endpoint, methodology switchboard, provenance walk, vintage history, ablations. | Basant-creator |
| **CHECKPOINT 6** | Demo freeze | No code changes. Rehearsals. Placeholder sweep — no figure marked *illustrative* or *indicative* survives in any external artifact. | Rexy-5097 |

The checkpoint sequence follows the dossier's build sequence (section 14), which
is gated rather than linear: a gate that fails selects a pre-designed branch
instead of stopping the project. Checkpoint 2 in particular exists before
Checkpoint 3 because the dossier is explicit that the statistical core is proven
on synthetic data, where the true answer is known by construction, before any
collector is trusted.

## Tagging

```bash
git tag -a checkpoint-0 -m "CHECKPOINT 0: repository + AgentOS + Agent Skills bootstrap"
git push origin checkpoint-0
```

Tag only after the PR is merged and CI is green on `main`. Tagging a branch tip
records a state nobody reviewed.

## Rolling back

Identify the last known-safe checkpoint:

```bash
git tag --list 'checkpoint-*' --sort=-creatordate
git log --oneline --decorate main
```

Recover forward, never by rewriting shared history:

```bash
git revert <bad-merge-sha> -m 1
```

`git reset --hard` on `main` is prohibited. It destroys a history other
contributors have already pulled, which turns one person's bad merge into
everyone's broken clone.

## Relationship to AgentOS quality gates

AgentOS quality gates (QG-001 … QG-008) verify a *change*. Checkpoints verify a
*project state*. A checkpoint is reached when its milestone's work has passed the
relevant gates and landed on `main`.

The APIx profile is `flagship`, which enables all eight gates. QG-002
(`checklists/pull_request.md`) applies to every PR; the rest apply at the
milestones where they are meaningful.
