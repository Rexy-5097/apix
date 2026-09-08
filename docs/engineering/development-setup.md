# Development setup

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12+ | Dossier section 13 specifies 3.12. `pyproject.toml` sets `requires-python = ">=3.12"` |
| Node.js | 20+ | Dashboard (Next.js) and the Agent Skills CLI |
| Git | 2.40+ | |
| GitHub CLI (`gh`) | 2.60+ | Required for the multi-account workflow |

## Clone and install

```bash
git clone https://github.com/Rexy-5097/apix.git
cd apix
```

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

```bash
pip install -e ".[dev]"
```

## Verify the checkout

Run these before your first change. If any fails, fix that before writing code.

```bash
# 1. The determinism boundary — the one check that must never be skipped
pytest tests/test_architecture.py

# 2. Full test suite
pytest

# 3. Lint and types
ruff check .
mypy schemas ingestion statistics analytics ai api experiments

# 4. AgentOS health
python tools/scripts/validate_agentos.py
python tools/scripts/bootstrap_project.py --self-test
```

### What "healthy" looks like for AgentOS

The validator reports **93/100, Final Status: FAIL**, and that is the expected
baseline — not a problem with your checkout.

Two upstream defects in the vendored framework account for the missing 7 points,
and they are present in a pristine upstream clone with no APIx content at all.
Both are documented in [../agentos/UPSTREAM_PATCHES.md](../agentos/UPSTREAM_PATCHES.md).
CI enforces *no regression below 93* rather than an unreachable 100.

If you see a grade **below 93**, something in your change regressed the
framework. Investigate before pushing.

## Agent Skills

Already committed under `.claude/skills/`. Nothing to install for Claude Code.

On another agent:

```bash
npx skills add addyosmani/agent-skills --skill '*' --agent <agent> --copy -y
```

See [agent-skills.md](agent-skills.md).

## Multi-account Git and GitHub

Three contributors share this repository, and **the commit identity must match
the owner of the task** — see [ownership-policy.md](ownership-policy.md).

### Never rely on a global identity

A global `user.name` is how work gets committed under the wrong contributor.
Set identity per repository instead:

```bash
cd /path/to/apix
git config user.name  "Rexy-5097"
git config user.email "<the GitHub email for that account>"
```

Confirm before every first commit of a session:

```bash
git config user.name
git config user.email
```

### Which email

Use the account's own address, or its GitHub-provided no-reply address so GitHub
attributes the commit correctly:

```
<user-id>+<username>@users.noreply.github.com
```

Find yours at **GitHub → Settings → Emails**. Using a placeholder, or another
contributor's address, is falsified authorship — Git does not verify these
fields, which is exactly why the rule matters.

### Switching the authenticated GitHub account

`gh` holds several accounts at once and switches between them:

```bash
gh auth login                    # once per contributor account
gh auth status                   # shows every authenticated account
gh auth switch --user <account>  # make one active
```

**Before committing or pushing, confirm both** the Git identity and the active
`gh` account correspond to the task's owner. If the required identity is not
available, **stop before commit and push** and report it. Do not substitute
another contributor.

### Working on a machine with only one account

Push a branch owned by a contributor you cannot authenticate as, and GitHub will
either reject it or record the wrong author. If you cannot be the owner, do not
make the commit — hand the task to the owner instead.

### Enable the commit-identity guard

Do this once per clone, before your first commit:

```bash
git config core.hooksPath .githooks
```

`.githooks/pre-commit` refuses a commit when the identity is not one of the three
contributors, when the identity does not match the branch owner, or when the
target is `main`. Git does not verify author fields, so without this the
ownership policy is only a convention — and its usual failure is silent, with
work landing under whichever identity happened to be configured globally.

`--no-verify` bypasses it. That is deliberate: the guard prevents accidents, it
is not a security control. Using it to commit under another contributor's
identity is a policy violation regardless.

## Editor

`.editorconfig` and `.pre-commit-config.yaml` are inherited from the AgentOS
template and apply repository-wide.

```bash
pip install pre-commit
pre-commit install
```

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'yaml'` | AgentOS tooling needs PyYAML. `pip install -e ".[dev]"` |
| AgentOS validator reports 0/100 | You are running an unpatched upstream `validate_agentos.py`. See UP-001 in [../agentos/UPSTREAM_PATCHES.md](../agentos/UPSTREAM_PATCHES.md) |
| AgentOS validator reports 93/100 FAIL | Expected. That is the documented baseline |
| `make` targets fail with `python3: not found` | The Makefile is inherited from AgentOS and hardcodes `python3`, which does not exist on a standard Windows install. Call the scripts directly: `python tools/scripts/validate_agentos.py` |
| `pytest` collects nothing | Run from the repository root; `testpaths` is `tests` |
| Commits show the wrong author | A global `user.name` is leaking in. Set it per repository, as above |
