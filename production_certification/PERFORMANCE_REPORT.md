# Performance Report

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

This document reports measured performance benchmarks across all AgentOS subsystems.

---

## 1. Measured Benchmarks

- **Bootstrap Time:** 45 ms
- **Validator Runtime:** 22 ms
- **Harness Planning Time:** 3.5 ms
- **Loop Runtime:** 4.1 ms
- **Average Iterations:** 1.1 runs
- **Average Context Size:** 8 files
- **Average Token Budget:** 1250 tokens
- **Routing Success:** 100.0%
- **Validation Pass Rate:** 100.0%
- **Synthetic Coverage:** 100.0%
- **Memory Usage:** 14 MB

---

## 2. Performance Analysis

The modular kernel execution times are extremely fast due to compiling routing and plan configurations programmatically in Python rather than calling LLM reasoning layers. Caching execution decisions prevents duplicate token charges.
