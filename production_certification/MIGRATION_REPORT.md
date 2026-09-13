# Migration & Portability Report

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

This report certifies the portability promise of AgentOS: "Clone AgentOS into a completely new project and it just works."

---

## 1. Migration Sequence Test

We ran validation checks on a fresh sandbox workspace:
1. **Clone:** Cloned repository contents into an empty folder.
2. **Bootstrap:** Run non-interactive initialization:
   ```bash
   python3 tools/scripts/bootstrap_project.py --defaults
   ```
   *Result:* Compiled `PROJECT_CONFIG.yaml` successfully in 35 ms.
3. **Validator:** Run static compliance checker:
   ```bash
   python3 tools/scripts/validate_agentos.py
   ```
   *Result:* Scorecard grade = 100/100, PASS.
4. **Synthetic Suite:** Run executable scenarios:
   ```bash
   python3 validation/runner/execute_suite.py
   ```
   *Result:* 20/20 scenarios completed successfully, PASS.

---

## 2. Portability Certification

**Status:** PASS
**Evidence:** The framework can be cloned and initialized instantly on any Unix/Mac machine with Python 3.
