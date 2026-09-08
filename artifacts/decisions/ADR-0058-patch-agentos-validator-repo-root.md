# ADR-0058: Patch the AgentOS validator's repo root; report the other two defects

> **Status:** Accepted | **Date:** 2026-09-08 | **Decider:** Rexy-5097

---

## Context

`AGENTOS.md` section 2 step 8 requires a health score of 100/100 before
initialization may be declared complete, and section 12 states the expected
output is `Overall Grade: 100/100 | Final Status: PASS`.

Four defects in the vendored template were found. Three make that score
unreachable; the fourth is triggered by vendoring Agent Skills.

**UP-001 — blocking.** `tools/scripts/validate_agentos.py` line 16 hardcodes an
author-specific absolute path:

```python
REPO_ROOT = "/Users/soumyadebtripathy/WorkFlow/agentos-template"
```

Every path the validator checks resolves against that constant. On any other
machine the directory does not exist, so the validator reports **0/100 FAIL**
with 120+ warnings about files that are demonstrably present. As shipped, no
user anywhere can satisfy the framework's own initialization protocol.

**UP-002 — non-blocking.** `DOCUMENTATION_INDEX.md` links its siblings with
absolute `file:///Users/soumyadebtripathy/...` URLs: 15 links, counted 5 times
each, giving 75 broken references and `Cross-reference: 0/100`.

**UP-003 — non-blocking.** `production_validation/productivity_metrics.csv` is
absent from the shipped template, giving `Production: 80/100`.

**UP-004 — blocking once Agent Skills are vendored.** `validate_artifacts` walks
the entire repository and demands all twelve AgentOS metadata keys from any
Markdown file with YAML frontmatter. The 25 vendored `SKILL.md` files produce 300
phantom violations, flooring `Artifacts` at 0/100. Beyond the six points, a
floored category can no longer report a genuinely malformed APIx ADR.

The APIx bootstrap instruction is explicit: report inconsistencies, do not
silently fix them.

## Decision

**Patch UP-001 and UP-004. Report UP-002 and UP-003 without fixing them.**

UP-001 is patched because the framework cannot otherwise be verified at all, and
"AgentOS is genuinely initialized" is a success condition for this task. The
replacement uses the `__file__`-derived idiom already used by the sibling script
`bootstrap_project.py`, so the two agree on the repository root:

```python
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

The patch is **declared, not silent**: a comment block at the patch site states
what upstream shipped and why it was changed, and
`docs/agentos/UPSTREAM_PATCHES.md` records the defect, the measurement, the
reproduction steps and the recommendation to upstream it.

UP-002 is not patched because it is upstream documentation content APIx does not
own; rewriting 15 links would create merge conflicts on the next upgrade for no
operational gain.

UP-004 is patched for the same reason as UP-001: without it the validator
reports a number that is not about APIx, and the Artifacts category loses the
ability to signal a real defect. The patch only scopes the walk — it changes no
threshold and no rule.

UP-003 is **deliberately** not patched. The missing file is a metrics file.
Creating one to satisfy a checker would mean inventing productivity measurements
that were never taken — fabricating data to turn a gate green is precisely the
failure mode the APIx dossier is written against. A placeholder CSV would be no
better: it would report a passing gate that verifies nothing.

## Consequences

- APIx scores **93/100, FAIL** on the AgentOS validator. A pristine upstream
  clone with no APIx content scores **identically**, which is the evidence that
  APIx introduced no regression.
- `AGENTOS.md`'s stated 100/100 criterion is unreachable, so CI enforces
  **no regression below 93** via `AGENTOS_BASELINE_GRADE` in
  `.github/workflows/validate.yml`. That threshold is raised — never lowered — as
  upstream defects are fixed.
- `tools/ci/check_markdown_links.py` excludes vendored AgentOS documentation, so
  UP-002 does not block every APIx pull request on a defect APIx did not
  introduce. The AgentOS validator still reports it, so no signal is lost.
- Re-vendoring AgentOS requires re-applying UP-001 and UP-004.
- Recommended Task 1 follow-up: open issues on `raptors-way` for all four, and
  offer UP-001 and UP-004 as pull requests.
