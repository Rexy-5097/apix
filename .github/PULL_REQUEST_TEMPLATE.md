<!--
APIx pull request template.

Every substantive PR fills every section. "N/A" is an acceptable answer and a
useful one — it records that the author considered the question. Deleting a
section is not, because a reviewer cannot tell the difference between "no
methodology impact" and "nobody checked".

Scope of "substantive": anything that changes behaviour, contracts, published
numbers, or the build. A typo fix does not need the full form.
-->

## Summary

<!-- What changed? One paragraph, plain language. -->

## Problem

<!-- Why was the change required? Link the issue, checkpoint, gate or dossier
     section that motivates it. -->

## Scope

**Included:**

**Intentionally excluded:**

<!-- Deferred work belongs here rather than in a follow-up nobody files. -->

## Owner

<!-- Assigned contributor from docs/engineering/ownership-policy.md.
     If this PR crosses domains, name the PRIMARY owner here and request review
     from the affected domain owner. -->

- Primary owner: @
- Cross-domain reviewers requested: @

## Verification

<!-- Evidence, not intent. Paste command output or link the CI run.
     "Should work" is not verification. -->

- [ ] `pytest` passes locally
- [ ] `pytest tests/test_architecture.py` passes (statistics determinism boundary)
- [ ] `ruff check .` clean
- [ ] `mypy` clean on touched layers
- [ ] CI green on this branch

Manual verification performed:

Experiments or invariant tests run:

## Methodology impact

<!-- Does this change what a published number MEANS? -->

- [ ] No methodology impact
- [ ] Methodology impact — `methodology_version` bumped, and the change is
      documented in `docs/methodology/`

<!-- Dossier section 11: a methodology change does NOT revise the series. It
     creates a new methodology_version and a parallel series with a linking
     factor. If you ticked the second box, say which. -->

## Data contract impact

<!-- Does this affect canonical schemas in schemas/? -->

- [ ] No schema change
- [ ] Schema change — migration and version bump described below

## API impact

<!-- Does this change an external contract: REST routes, SDMX output, field
     names, or the version vector? -->

- [ ] No external API change
- [ ] Breaking change — described below, with the consumer impact

## Risk

<!-- What can break, and what would the first symptom be? -->

## Rollback

<!-- The last known-safe checkpoint to return to. See
     docs/engineering/checkpoint-policy.md. -->

Last known-safe checkpoint:

## Screenshots

<!-- Required for any UI change. Before and after. -->

---

### Reviewer checklist

- [ ] Diff reviewed, not just the summary
- [ ] Architecture impact considered (layer boundaries intact)
- [ ] Security implications considered
- [ ] Methodology implications considered
- [ ] Tests actually exercise the change, including its failure cases
- [ ] No `illustrative` or placeholder figure has leaked into an external artifact
