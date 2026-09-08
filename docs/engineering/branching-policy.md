# Branching policy

`main` is the protected integration branch. It is never an ordinary working
branch.

Every merged pull request should leave `main` in a state a teammate could clone
and build. That is the whole point of the policy: a green `main` is the fallback
when something later goes wrong.

## The flow

```
feature branch
  → implementation
  → tests
  → self-review
  → pull request
  → CI
  → review
  → merge
  → known-safe checkpoint
```

No step is optional because a change looks small. The determinism boundary in
`tests/test_architecture.py` exists precisely because "obviously fine" changes
are how architectural guarantees erode.

## Branch naming

```
<type>/<contributor>/<scope>
```

`<type>` is one of `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.
`<contributor>` is the short handle: `rexy`, `slazy`, `basant`.
`<scope>` is a short kebab-case description of the change.

### Rexy-5097

```
feat/rexy/<scope>
fix/rexy/<scope>
docs/rexy/<scope>
test/rexy/<scope>
```

### slazyverse

```
feat/slazy/<scope>
fix/slazy/<scope>
docs/slazy/<scope>
test/slazy/<scope>
```

### Basant-creator

```
feat/basant/<scope>
fix/basant/<scope>
docs/basant/<scope>
test/basant/<scope>
```

Examples:

```
feat/rexy/jevons-elementary-relative
feat/slazy/indigo-collector
feat/basant/provenance-screen
docs/rexy/formula-spec-v1
test/slazy/parser-fixtures
```

The contributor segment must match the identity that authors the commits. A
branch named `feat/rexy/...` carrying commits authored by another contributor is
a policy violation, not a naming inconsistency.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <subject>

<body: why, not what — the diff already says what>

<footer: refs, breaking changes, co-authors>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`.

A change that alters what a published number means must say so in the body and
bump `methodology_version`. Dossier section 11 is explicit that a methodology
change does not revise the series — it creates a new one, published in parallel
with a linking factor.

Example:

```
feat(statistics): add Jevons elementary short relative

Implements dossier section 08 formula 1: the geometric mean of price
relatives over items matched in both t and t-7. Unmatched items enter
neither side, so the matched set is computed before the mean rather
than filtered after it.

Golden values were computed by hand before this implementation, per the
dossier section 15 risk "two developers implement the aggregation
differently".

Refs: CHECKPOINT-2
```

## Prohibited

- Force-pushing `main`.
- Rewriting shared `main` history.
- Committing directly to `main` — including for "trivial" documentation.
- Merging a PR whose CI is red.
- Merging your own PR without the required review once protection is enabled.

Force-pushing your **own** feature branch before review is fine. After a reviewer
has commented on it, prefer additional commits so their comments stay anchored.

## Merge strategy

**Squash and merge** into `main`.

One merged PR becomes one commit, so `main`'s history is a sequence of reviewed,
CI-verified states. That is what makes `git log main` a usable list of rollback
targets, and it is what lets a checkpoint be identified by a single SHA.

Keep the squash commit subject in Conventional Commits form; GitHub defaults to
the PR title, so PR titles follow the same convention.
