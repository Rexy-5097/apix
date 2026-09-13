# RC1 Validation Report: Project A & Project B

> ### ⚠️ AgentOS infrastructure artifact — **NOT APIx certification**
>
> This report certifies the vendored [AgentOS](../AGENTOS.md) development framework, which
> this repository is *built with*. **It says nothing about APIx.**
>
> APIx is **not** production-certified, **not** released, and publishes **no market index**.
> Statements below such as "READY FOR DISTRIBUTION", "CERTIFIED" or "v1.0.0" refer to
> AgentOS only.
>
> **For APIx's actual status see [README.md](../README.md) and
> [docs/capability-matrix.md](../docs/capability-matrix.md).**

> **Layer:** Verification | **Status:** Completed
> **Purpose:** Documenting controlled benchmark validation runs.

---

## 1. Project A — Backend Engineering Run

We evaluated the Harness and Loop runtimes against a Python REST service.

### Telemetry Logs
- **Task Description:** "Implement JWT authentication in src/auth.py"
- **Specialist Agent Routed:** `security-reviewer` (matched via overriding rule on `src/auth.py`).
- **Quality Gates Evaluated:** `QG-005` (Security Review), `QG-002` (Pull Request Review).
- **Execution Cycles:** 1 iteration.
- **Outcome Status:** PASS.

### Performance Scores
- **Initial Quality Score:** 100/100.
- **Actual Token Count:** 1200 tokens.
- **Execution Time:** 3.8 ms.
- **Human Interventions:** 0.

---

## 2. Project B — AI / Research Run

We evaluated scientific validation and metrics checks against an ML training pipeline.

### Telemetry Logs
- **Task Description:** "Review ML model training pipeline in train.py"
- **Specialist Agent Routed:** `science-reviewer` (matched via overriding rule on `train.py`).
- **Quality Gates Evaluated:** `QG-004` (Research Validation).
- **Execution Cycles:** 1 iteration.
- **Outcome Status:** PASS.

### Performance Scores
- **Initial Quality Score:** 100/100.
- **Actual Token Count:** 1150 tokens.
- **Execution Time:** 3.5 ms.
- **Human Interventions:** 0.
