# tests/

## What exists today

`test_architecture.py` — the deterministic statistics boundary from dossier
section 05, enforced in CI and required by branch protection.

```bash
pytest tests/test_architecture.py -v
```

Two design choices worth knowing:

- **It is static.** It parses every module under `statistics/` with `ast` and
  never imports them. Importing the layer to inspect its imports would require
  the package to be installable and side-effect free, would execute module-level
  code in CI, and would miss imports guarded behind `if` blocks. Parsing sees
  every import statement regardless of whether it would execute.
- **It tests itself.** Each forbidden import is planted into a temporary file and
  the detector is asserted to catch it. A boundary test that cannot fail is worse
  than no boundary test, because it reports a safety it is not actually checking.

It also verifies `statistics/` still exists, so that renaming the directory
cannot make every assertion vacuously pass.

## What will be added

Property tests over generated inputs (Hypothesis), plus **golden values computed
by hand before either implementation exists**, covering the invariants that must
hold for *any* correct implementation:

- Identical prices in both periods produce an index of exactly 100.
- Scaling every price by *k* leaves the index unchanged; the price relatives are
  unchanged.
- The index equals 100 in the base period by construction.
- Weight vectors sum to one, before and after any suppression and
  renormalisation.
- Reordering observations within a period does not change any output.
- Missing cells follow the declared rule and nothing else; a cell is never
  silently dropped.
- Every threshold in dossier section 08 has a test that crosses it in **both**
  directions.
- Recomputing from the same version vector reproduces the published value bit for
  bit.

Line coverage is the wrong target: an index engine can reach full coverage while
computing the wrong number.

## Markers

Declared in `pyproject.toml`:

| Marker | Meaning |
|---|---|
| `invariant` | Must hold for any correct implementation |
| `golden` | Values computed by hand before implementation |
| `slow` | Excluded from the fast pre-merge run |
