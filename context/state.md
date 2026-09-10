# Project State

> **Owner:** Rexy-5097 (update) · Everyone (read) | **MANDATORY first read for all agents**
> **Update:** Every session · Archive completed tasks
> **Cross-refs:** `context/decisions.md` · `context/vision.md` · `PROJECT_CONFIG.yaml`

---

## Snapshot

| Field | Value |
|-------|-------|
| **Date** | 2026-09-10 |
| **Phase** | Checkpoint 2E — v2.1 freeze and the AMB-7 publication layer |
| **Health** | 🟡 AMBER — Checkpoints 0, 1A, 2, 2C merged. `methodology_version 2.1` is FROZEN and in force. **AMB-8 and AMB-9 block the production pipeline** and cannot be closed in code |
| **Methodology** | `2.1` — [`apix_formula_spec_v2_1.md`](../docs/methodology/apix_formula_spec_v2_1.md), frozen 2026-09-10 ([ADR-0063](../artifacts/decisions/ADR-0063-freeze-methodology-v2-1.md)) |
| **Next Milestone** | Owner rulings on AMB-8 and AMB-9, then the production pipeline |
| **AgentOS profile** | `flagship` — 9 standards, 11 agents, 8 quality gates |
| **AgentOS grade** | 93/100 (upstream baseline; see below) |

---

## Active Work

| Task | Status | Owner | Blocked By | Priority |
|------|--------|-------|-----------|----------|
| CHECKPOINT 0 bootstrap | `DONE` | Rexy-5097 | — | — |
| CHECKPOINT 1A methodology freeze | `DONE` | Rexy-5097 | — | — |
| Deterministic APIx-L core (PR #3) | `DONE` | Rexy-5097 | — | — |
| AMB-1 resolution, methodology v2.1 (PR #4) | `DONE` | Rexy-5097 | — | — |
| v2.1 implementation (PR #5) | `DONE` | Rexy-5097 | — | — |
| CHECKPOINT 2E — v2.1 freeze + AMB-7 layer | `IN_REVIEW` | Rexy-5097 | — | High |
| **Rule on AMB-8 — `expected_cells`** | `OPEN` | Rexy-5097 (methodology) | — | **BLOCKER** |
| **Rule on AMB-9 — carrier allocation of `v[c\|r]`** | `OPEN` | Rexy-5097 (methodology) | — | **BLOCKER** |
| Production Observation→ApixLResult pipeline | `NOT_STARTED` | Rexy-5097 | AMB-8, AMB-9 | High |
| TPD estimator | `NOT_STARTED` | Rexy-5097 | — (independent workstream) | — |
| Bootstrap / uncertainty | `NOT_STARTED` | Rexy-5097 | pipeline | — |

---

## Blockers

**Two, and neither is an engineering blocker.** Both are methodology questions
the frozen specification does not answer, both change published values, and §S
forbids resolving either by choosing a plausible value.

| ID | Question | Why it blocks |
|---|---|---|
| **AMB-8** | What counts as an `expected_cell` in `min_route_coverage = 60%`? | Gates every route on every date. Undefined, so route suppression — and therefore the national level — is undetermined |
| **AMB-9** | How is `v[c\|r]` allocated across carriers, given §G.3 has no carrier term? | No weight vector can be constructed; `renormalise_over_live_set` raises on any live cell without a weight |

Both are held at the code boundary rather than defaulted: `within_route_weights`
raises, and any output relying on the observed-count coverage denominator carries
a caveat naming AMB-8. See
[`OPEN-AMBIGUITIES-checkpoint-2.md`](../docs/methodology/OPEN-AMBIGUITIES-checkpoint-2.md).

All three GitHub identities are authenticated and API-verified:

| Account | `gh api user` login | id |
|---------|---------------------|-----|
| Rexy-5097 | `Rexy-5097` | 177911845 |
| slazyverse | `slazyverse` | 188746735 |
| Basant-creator | `Basant-creator` | 177188658 |

Git commit identity is set **per repository**, never globally, and is checked by
`.githooks/pre-commit` before every commit.

---

## Technical Debt / Open empirical questions

Eight open empirical questions are tracked in `docs/methodology/apix_formula_spec_v1.md` §S.
**None may be resolved by choosing a plausible value.**

| Item | Severity | Notes |
|------|----------|-------|
| OQ-1…OQ-8 | Various | Collection window, match-coverage floor, sell-out bias, DGCA weights, bootstrap runtime, CPI benchmark, lead-time distribution, licensed feed |
| **R-12** — dossier invariant self-contradictory | Medium | *"Scaling every price by k scales the index by k; the price relatives are unchanged."* Split into INV-4a/INV-4b. **Awaiting dossier author's confirmation** |
| CODEOWNERS self-approval deadlock | Medium | `*` and most paths are owned by @Rexy-5097, who authors most PRs. GitHub forbids self-approval, so a code-owner requirement cannot be met by the author |
| AgentOS UP-002 / UP-003 | Low | Upstream, reported not patched |
| AgentOS `Makefile` hardcodes `python3` | Low | Call scripts directly on Windows |

---

## Recent Decisions

| ADR | Decision | Date |
|-----|----------|------|
| [ADR-0057](../artifacts/decisions/ADR-0057-adopt-agentos-flagship-profile.md) | Adopt AgentOS with the `flagship` profile | 2026-09-08 |
| [ADR-0058](../artifacts/decisions/ADR-0058-patch-agentos-validator-repo-root.md) | Patch the AgentOS validator; report the other defects | 2026-09-08 |
| [ADR-0059](../artifacts/decisions/ADR-0059-enforce-statistics-determinism-in-ci.md) | Enforce the determinism boundary statically in CI | 2026-09-08 |
| [ADR-0060](../artifacts/decisions/ADR-0060-vendor-agent-skills-into-repository.md) | Vendor Agent Skills into the repository | 2026-09-08 |
| [ADR-0061](../artifacts/decisions/ADR-0061-statistics-package-layout.md) | **Statistics package layout — adopt `src/apix/`** | 2026-09-08 |

---

## Completed This Session (Checkpoint 2)

- [x] Verified Checkpoint 1A merged at `530ef1a` — not assumed from the prior report
- [x] Typed domain models for spec A, B, O — `src/apix/schemas/`
- [x] Admissibility, deduplication, matching primitives, tier ladder
- [x] Jevons elementary relative in the normative log form, plus the median/MAD rule
- [x] Cell chaining, carry, freshness, suppression and new-cell entry
- [x] Young / Modified Laspeyres with live-set renormalisation
- [x] Deterministic APIx-L assembly with quality metrics and the version vector
- [x] Annual linking, isolated from the per-period path
- [x] All 16 golden values reproduced by the production code
- [x] 155 tests: every locked threshold crossed in both directions, property-based coverage
- [x] Bit-identical reproducibility verified across 8 input permutations
- [x] **Found and fixed a real defect**: deduplication omitted route, collapsing
      2,800 quotes to 140 on a full-frame day. Caught by the benchmark, not by a
      unit test — every dedup test used a single route
- [x] Performance measured: 1.03s for 15,120 quotes / 72 routes

---

## Next Actions

1. Review the bootstrap PR — slazyverse, Basant-creator
2. Merge once CI is green and review is complete — Rexy-5097
3. Tag `checkpoint-0` on `main` after merge — Rexy-5097
4. Confirm branch protection is in force; record what GitHub actually allowed — Rexy-5097
5. Begin Checkpoint 1: freeze `docs/methodology/apix_formula_spec_v1.md` — Rexy-5097

**Task 1 does not begin until the bootstrap checkpoint is reviewed.**

---

## AgentOS health note

The validator reports **93/100, FAIL**, and that is the expected baseline. A
pristine upstream clone with no APIx content scores identically — the missing 7
points are entirely upstream defects UP-002 and UP-003. APIx introduced no
regression. CI enforces no-regression below 93 rather than an unreachable 100.

---

*Updated: Task 0 bootstrap · 2026-09-08*
