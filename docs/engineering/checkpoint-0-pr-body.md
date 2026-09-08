## Summary

Establishes the APIx repository baseline against the v2.1 engineering dossier
(MoSPI problem statement 26056): AgentOS initialisation, the Agent Skills
engineering workflow, the deterministic-statistics CI boundary, contributor
governance, and the directory structure from dossier section 13.

**No APIx feature code.** No scraping, adapters, parsing, matching, Jevons,
Young/Modified Laspeyres, TPD, bootstrap, forecasting, anomaly detection,
dashboard or API business logic.

## Problem

APIx is a three-contributor project whose output is meant to be adoptable by a
statistical office. That needs an engineering baseline before any feature work:
a framework that routes and gates changes, a workflow contributors follow, a
mechanically-enforced architectural boundary, and unambiguous ownership.

The dossier also imposes a constraint no ordinary scaffold would: the statistics
layer must be reproducible from `(snapshot_id, methodology_version,
weight_version, code_version)` alone. That guarantee has to be enforced from the
first commit, because it is far harder to restore than to keep.

## Scope

**Included:** AgentOS initialisation (`flagship`); Agent Skills 0.6.9 vendored;
repository structure (empty, with per-layer READMEs); `tests/test_architecture.py`;
CI (`ci.yml`, `validate.yml`, `lint.yml`); CODEOWNERS; PR template;
`.githooks/pre-commit` identity guard; `.gitattributes`; engineering docs;
ADR-0057…0060; the dossier vendored to `docs/dossier/`; `main` branch protection.

**Intentionally excluded:** every APIx feature. `docs/methodology/apix_formula_spec_v1.md`
is **not** written — it is Checkpoint 1, and dossier section 13 requires it frozen
before the first line of statistics code.

## Owner

- Primary owner: @Rexy-5097
- Cross-domain reviewers requested: @slazyverse, @Basant-creator

## Verification

```
pytest                    11 passed
ruff check .              All checks passed
link check                67 files, all internal links resolve
AgentOS validator         93/100  (pristine upstream clone: 93/100 — no regression)
bootstrap --self-test     PASS — all 8 profiles verified
```

**Negative control on the architecture boundary.** A planted
`import sklearn` / `from anthropic import Anthropic` under `statistics/elementary/`
failed the suite with a message naming the file and the offending imports;
removing it returned the suite to green. The check also self-tests by planting
each forbidden import into a temporary file.

**Commit-identity guard**, four cases: unrecognised identity → blocked; correct
owner on their own branch → allowed; one contributor on another's branch →
blocked; any contributor committing to `main` → blocked.

### On the AgentOS score

`AGENTOS.md` requires 100/100, which the shipped template cannot produce on any
machine. Four defects were found:

| ID | Defect | Status |
|---|---|---|
| UP-001 | `validate_agentos.py` hardcodes `/Users/soumyadebtripathy/...` → 0/100 everywhere | **Patched** |
| UP-002 | `DOCUMENTATION_INDEX.md` absolute `file:///` links → 75 broken refs | Reported |
| UP-003 | `production_validation/productivity_metrics.csv` absent → 80/100 | Reported |
| UP-004 | Artifact validator walks the repo unscoped; 25 vendored `SKILL.md` files → 300 phantom violations | **Patched** |

UP-001 and UP-004 are patched because without them the validator reports a number
that is not about APIx. UP-003 is deliberately **not** patched: satisfying it
means inventing productivity measurements that were never taken, and fabricating
data to turn a gate green is the failure mode this project is written against.

Full measurements and reproduction steps: `docs/agentos/UPSTREAM_PATCHES.md`.

## Methodology impact

- [x] No methodology impact

No statistics code exists. The boundary test enforces an existing dossier
guarantee rather than introducing a new rule.

## Data contract impact

- [x] No schema change

`schemas/` is created empty. The canonical contract is Checkpoint 1.

## API impact

- [x] No external API change

## Risk

- ~~Branch protection is not yet applied~~ — **applied and verified** on
  2026-09-08. PR required, 1 approval, CODEOWNER review required, stale reviews
  dismissed, all 7 checks required and strict, force-push and deletion blocked,
  linear history, conversation resolution, enforced for admins.
- **`statistics/` shadows the stdlib `statistics` module.** The dossier specifies
  this layout, so it is flagged rather than unilaterally changed. CI is
  unaffected — the boundary check is static and never imports the package — but
  it must be settled before the first module lands there. **Checkpoint 1
  decision.**
- **Re-vendoring AgentOS drops UP-001 and UP-004**, silently returning the
  validator to a meaningless score.
- **The AgentOS Makefile hardcodes `python3`**, which does not exist on a
  standard Windows install. Call the scripts directly.

## Rollback

No prior checkpoint — this is the repository's first commit. Rollback is
declining to merge.

## Screenshots

N/A — no UI in this change.

---

### Reviewer notes

Worth a close look:

1. **`tests/test_architecture.py`** — the guarantee everything else rests on.
2. **`docs/agentos/UPSTREAM_PATCHES.md`** — the two patches applied to vendored
   framework code, and the reasoning for the two left alone.
3. **`docs/engineering/ownership-policy.md`** and `.github/CODEOWNERS` — confirm
   the domain boundaries match how you expect to work.
4. **`.githooks/pre-commit`** — it will block your commits if your identity or
   branch is wrong. That is intended; check the mapping is right for you.

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
