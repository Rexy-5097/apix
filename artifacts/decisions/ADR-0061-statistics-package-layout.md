# ADR-0061: Statistics package layout — adopt `src/apix/`

> **Status:** Accepted | **Date:** 2026-09-08 | **Decider:** Rexy-5097

---

## Context

Checkpoint 0 created the APIx layers at the repository root, mirroring the tree
printed in dossier section 13:

```
apix/
├── schemas/
├── ingestion/
├── statistics/
│   ├── elementary/
...
```

It was flagged at the time — in `src/apix/statistics/README.md`, the bootstrap
commit message and the Checkpoint 0 PR — that a root-level `statistics/`
directory shadows Python's standard-library `statistics` module, and that this
had to be settled deliberately before the first module landed there.

That is this decision.

## Problem

Python puts the current directory first on `sys.path` for `python -c`, `python
-m`, and scripts run from the repository root. A root-level package named
`statistics` therefore wins over the standard library.

## Evidence

Measured on this repository at commit `c267f12`, before any change:

**E1 — the shadow is real.**

```
$ cd apix && python -c "import statistics; print(statistics.__file__)"
D:\WorkSpace\SIH\Tulya\apix\statistics\__init__.py
```

**E2 — the standard library becomes unusable, and CPython says so.**

```
$ python -c "import statistics; statistics.mean([1,2,3])"
AttributeError: module 'statistics' has no attribute 'mean'
(consider renaming '...\statistics\__init__.py' since it has the same name as
 the standard library module named 'statistics' and prevents importing that
 standard library module)
```

The interpreter emits a rename hint. That is the language itself calling this a
mistake.

**E3 — it is directory-dependent, which is worse than a consistent failure.**

From any other working directory the same import resolves to
`C:\Python313\Lib\statistics.py`. So the bug appears and disappears depending on
where the process was started: green in one developer's terminal, red in
another's, and potentially different again in CI.

**E4 — the standard library itself imports it.** `C:\Python313\Lib\random.py`
line 955: `from statistics import stdev, fmean as mean`.

**E5 — that particular import is not currently fatal.** It sits inside
`random.py`'s `__main__` self-test block, so `import random` and
`random.gauss()` still work under the shadow. Measured, not assumed.

**E6 — no *currently installed* third-party package imports `statistics`**, so
nothing is broken today.

### What the evidence does and does not establish

It does **not** establish that the root layout breaks the build today. It does
not. E5 and E6 are honest about that.

It establishes something worse: the failure is **latent and conditional**. The
dossier's section 13 stack still has to be installed — SciPy, statsmodels,
Polars, PyArrow, Pandera, Hypothesis, FastAPI. Any one of them, in any future
version, may add `import statistics`. The failure would then surface as an
`AttributeError` deep inside a third-party library, on some machines only,
during the statistics layer's own development.

Betting the deterministic index engine on "no dependency will ever import a
standard-library module" is not a bet worth taking when the alternative costs
one directory move before any statistics code exists.

## Options

**Option A — keep `statistics/` at the repository root.** Matches the dossier
tree literally. Rejected: E1–E3 are unresolved, and the cost of the collision
only rises once modules exist and are imported across the codebase.

**Option B — `src/apix/statistics/` (chosen).** The layers move under a `src/`
directory as the `apix` package. Imports become `apix.statistics.elementary`,
which cannot collide with any standard-library name.

**Option C — rename the directory, e.g. `stats/` or `index_engine/`, at the
root.** Resolves the collision but silently renames a layer the dossier names
explicitly, and leaves every other layer un-namespaced at the root, where
`schemas`, `api` and `types`-adjacent names invite the next collision.

## Decision

**Adopt Option B.** All Python layers move to `src/apix/`:

```
src/apix/{schemas,ingestion,statistics/{elementary,aggregation,tpd,uncertainty,index},analytics,ai,api,experiments}/
dashboard/   # Next.js, not a Python package
tests/       # stays at the root, conventional
docs/
```

### This follows the dossier rather than departing from it

The dossier's tree is rooted at **`apix/`**, not at the repository root. The
directories it lists are the contents of `apix/` — that is, of the `apix`
package. Placing them at the repository root was Checkpoint 0's interpretation,
not the dossier's instruction. `src/apix/statistics/` preserves the dossier's
own logical path, `apix/statistics`, exactly; it adds only the `src/` prefix
that is standard Python packaging convention.

The dossier's CI snippet reads `walk_imports("apix/statistics")` — a path
containing `apix/`, which the root layout did not actually produce and this
layout does.

**Reported for the record:** the on-disk tree now differs from the dossier's
printed listing by one `src/` level. The logical package path is unchanged.

### AgentOS is unaffected

The AgentOS validator checks for its own layer directories — `workflows`,
`agents`, `tools`, `context`, `standards`, `checklists`, `metrics`, `templates`,
`profiles`, `integrations`, `artifacts`. APIx's product layers are not part of
that contract. Verified: the grade is 93/100 before and after the move,
unchanged.

## Consequences

- Imports are absolute from the package root: `from apix.statistics.elementary
  import jevons`. No `sys.path` manipulation, no implicit namespace packages.
- The package is properly installable (`pip install -e .`) with
  `package-dir = {"" = "src"}`. Verified: `import apix.statistics.elementary`
  succeeds and `statistics.mean([1,2,3])` returns `2` in the same interpreter.
- **Tests import the installed package, not the source tree.** This is the real
  ongoing benefit of a `src/` layout: a module missing from the wheel fails in
  CI instead of silently working because the source directory happened to be on
  `sys.path`. For a project whose central claim is bit-for-bit reproducibility,
  the packaged artifact and the tested artifact must be the same thing.
- `tests/test_architecture.py` now walks `src/apix/statistics`. Its
  `test_statistics_root_exists` guard means a future move cannot make the
  determinism boundary pass vacuously — verified: the test is non-vacuous after
  this migration.
- Updated together: `pyproject.toml` (packages, `mypy_path`, the
  `apix.statistics.*` strictness override), `.github/CODEOWNERS`,
  `.github/workflows/ci.yml` (`mypy src/apix`), `README.md`, `CLAUDE.md`,
  `AGENTS.md`, `context/architecture.md`, `CONTRIBUTING.md`, and the layer
  READMEs.
- Migration cost was near zero because every layer module is still an empty
  `__init__.py`. Deferring this decision past Checkpoint 2 would have meant
  rewriting imports across the index engine instead.
