# Backward Compatibility & Upgrade Specification

> ### ⚠️ This file documents **AgentOS**, not APIx
>
> [AgentOS](AGENTOS.md) is the vendored development/review framework this repository is
> *built with*. It is **not part of the APIx statistical product** and produces none of
> APIx's published numbers. Its version numbers, release notes and readiness statements
> describe **AgentOS**, never APIx.
>
> **For APIx — the airfare price index — see [README.md](README.md) and
> [docs/capability-matrix.md](docs/capability-matrix.md).**

This document codifies the compatibility rules and upgrade policies of AgentOS after its stable **v1.0.0** release.

---

## 1. Compatibility Policy

- **Minor Version (v1.x):** Non-breaking additions are allowed. Core policies and checklist rules remain backward compatible.
- **Major Version (v2.0):** Breaking changes to directory layouts, standard keys, or runtime state transitions are permitted.

---

## 2. Upgrade Path

To upgrade an existing project's AgentOS modules from `1.x` to `1.y`:
1. Keep the custom `PROJECT_CONFIG.yaml` config intact.
2. Back up `context/state.md` and custom checklists.
3. Overwrite the `runtime/` and `tools/scripts/` folders.
4. Run `python3 tools/scripts/validate_agentos.py` to confirm compatibility setup.

---

## 3. Deprecated Components

No components are deprecated as of v1.0.0. All active layers are certification targets.
