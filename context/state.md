# Project State

> **Owner:** Rexy-5097 (update) · Everyone (read) | **MANDATORY first read for all agents**
> **Update:** Every session · Archive completed tasks
> **Cross-refs:** `context/decisions.md` · `context/vision.md` · `PROJECT_CONFIG.yaml`

---

## Snapshot

| Field | Value |
|-------|-------|
| **Date** | 2026-09-08 |
| **Phase** | Checkpoint 1A — statistical architecture + formula specification |
| **Health** | 🟢 GREEN — Checkpoint 0 merged; 1A PR open for review |
| **Next Milestone** | CHECKPOINT 2 — synthetic statistical core |
| **AgentOS profile** | `flagship` — 9 standards, 11 agents, 8 quality gates |
| **AgentOS grade** | 93/100 (upstream baseline; see below) |

---

## Active Work

| Task | Status | Owner | Blocked By | Priority |
|------|--------|-------|-----------|----------|
| CHECKPOINT 0 bootstrap | `DONE` | Rexy-5097 | — | — |
| Statistics package layout (ADR-0061) | `IN_REVIEW` | Rexy-5097 | — | High |
| Formula specification v1 (frozen) | `IN_REVIEW` | Rexy-5097 | — | High |
| Golden values + invariant tests | `IN_REVIEW` | Rexy-5097 | — | High |
| Audit of the formula spec by the human owner | `PENDING` | Human | 1A PR | High |

---

## Blockers

None.

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

## Completed This Session (Checkpoint 1A)

- [x] Verified Checkpoint 0 merged at `c267f12` — not assumed from the prior report
- [x] Measured the `statistics/` stdlib shadow (E1–E6); migrated to `src/apix/`
- [x] ADR-0061 with the evidence
- [x] **Froze `docs/methodology/apix_formula_spec_v1.md`** — sections A–T
- [x] 16 hand-calculated golden values in `tests/fixtures/statistical_golden_values.yaml`
- [x] 40 methodology invariant tests; INV-1 proven non-vacuous by corruption test
- [x] Adversarial review — 13 findings, 3 specification gaps closed before freezing
- [x] Confirmed no statistical implementation exists

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
