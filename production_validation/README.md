# Release Candidate 1 (RC1) Validation Benchmarks

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

> **Layer:** Verification | **Status:** Active
> **Purpose:** Documenting developer productivity metrics and audit logs for AgentOS RC1.
> **Cross-refs:** `production_validation/rc1_validation_report.md` · `production_validation/productivity_metrics.csv`

---

## 1. Subsystem Audit Rules

This layer tracks actual productivity metrics recorded across our controlled representative benchmark tasks:
- **Project A (Backend Task):** Bootstrap verification, JWT implementation metrics, and API endpoint additions.
- **Project B (AI/Research Task):** ML model training pipeline reviews and scientific data assertions.

---

## 2. Validation Execution Command

To execute the static validator checklist for RC1 verification, run:
```bash
python3 tools/scripts/validate_agentos.py
```
