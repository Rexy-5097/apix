# ADR-0059: Enforce the statistics determinism boundary statically in CI

> **Status:** Accepted | **Date:** 2026-09-08 | **Decider:** Rexy-5097

---

## Context

Dossier section 05 states the engineering rule once and requires it enforced
everywhere: **statistics calculates, machine learning explains.** The published
index must be reproducible from
`(snapshot_id, methodology_version, weight_version, code_version)` alone.

A stochastic dependency anywhere under `statistics/` breaks that guarantee
silently — the code runs, the numbers look plausible, and reproducibility is
gone. The dossier sketches the enforcement as a CI import check with a forbidden
set of `sklearn`, `lightgbm`, `xgboost`, `torch`, `anthropic`, `openai`.

The question this ADR settles is *how* the check inspects imports.

## Decision

Implement the check as a **static AST parse** in `tests/test_architecture.py`,
run as its own CI job, and make it a required status check on `main`.

### Static, not import-based

The detector parses each `.py` file under `statistics/` with `ast` and never
imports it. An import-based check would need the package installable and
side-effect free, would execute module-level code in CI, and would miss imports
guarded behind `if` blocks or inside functions. Parsing sees every `import` and
`from ... import` statement regardless of whether it would execute.

### Extended beyond the dossier's set

The dossier lists six forbidden libraries. The check also forbids `statistics/`
importing `analytics/` or `ai/`. This is not a new rule — it is the dossier's own
**removal test** (section 12: delete the Claude API integration and the entire
analytics layer, and the index must still publish) expressed as something CI can
verify. Without it, the removal test is a claim nobody checks.

### The detector tests itself

Each forbidden import is planted into a temporary file and the detector is
asserted to catch it; `from sklearn.x import y` and relative imports are covered
separately. A boundary test that cannot fail is worse than no boundary test,
because it reports a safety it is not actually checking.

A separate test asserts `statistics/` still exists, so that renaming the
directory cannot make every other assertion vacuously pass.

## Consequences

- The boundary is verified on every pull request, and is listed as a required
  status check in `docs/engineering/branch-protection.json`.
- `.github/CODEOWNERS` assigns `tests/test_architecture.py` to Rexy-5097.
  Weakening the test silently removes a published methodology guarantee, so it is
  owner-gated like the statistics layer itself.
- `CLAUDE.md`, `CONTRIBUTING.md` and `statistics/README.md` all state that the
  test may not be weakened, skipped or marked advisory.
- The check was verified end-to-end during bootstrap: a planted
  `import sklearn` / `from anthropic import Anthropic` under
  `statistics/elementary/` failed the run with a precise message naming the file
  and the offending imports; removing it returned the suite to green.
- Cost: `statistics/` is walked on every CI run. At this tree size the run is
  well under a second.
