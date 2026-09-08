#!/usr/bin/env python3
"""Check that relative links in APIx-owned Markdown actually resolve.

Scope note
----------
The vendored AgentOS documentation is excluded. Upstream ``DOCUMENTATION_INDEX.md``
links its siblings with absolute ``file:///Users/soumyadebtripathy/...`` URLs
(defect UP-002 in docs/agentos/UPSTREAM_PATCHES.md), which cannot resolve
anywhere but the original author's machine. Those 75 broken references are
already reported by the AgentOS validator in the validate.yml workflow, so
failing this job on them too would add noise without adding signal — and would
block every APIx pull request on a defect APIx did not introduce and does not own.

This checker therefore covers documentation APIx is responsible for, and is a
hard failure there.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Directories owned by the vendored AgentOS template or by tooling.
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "artifacts",
    "checklists",
    "examples",
    "integrations",
    "lessons",
    "metrics",
    "production_certification",
    "production_validation",
    "profiles",
    "runtime",
    "standards",
    "templates",
    "validation",
    "workflows",
    "agents",
    "context",
}

# Root-level Markdown shipped by the AgentOS template.
EXCLUDED_FILES = {
    "AGENTOS.md",
    "ARCHITECTURE.md",
    "BOOTSTRAP.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "COMPATIBILITY.md",
    "DOCUMENTATION_INDEX.md",
    "ENGINEERING_PRINCIPLES.md",
    "INSTALL.md",
    "RELEASE_NOTES_v1.0.0.md",
    "REPOSITORY_HEALTH.md",
    "START_PROJECT.md",
    "SUPPORT.md",
    "SUPPORTED_VERSIONS.md",
    "TEAM_ONBOARDING_CHECKLIST.md",
    "TEAM_QUICKSTART.md",
    "VERSION_POLICY.md",
    "SECURITY.md",
}

# Markdown links that are not repository-relative paths.
EXTERNAL = re.compile(r"^(https?:|mailto:|file:|#)")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Fenced code blocks and inline code spans. Documentation *about* linking
# necessarily contains link examples — docs/agentos/UPSTREAM_PATCHES.md quotes
# `[AGENTOS.md](./AGENTOS.md)` as the fix upstream should apply — and those are
# illustrations, not links this repository makes. Stripping code first is what
# separates a documented example from a real dangling reference.
FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")


def strip_code(markdown: str) -> str:
    """Remove fenced blocks and inline code spans before link extraction."""
    return INLINE_CODE.sub("", FENCE.sub("", markdown))


def is_excluded(path: Path) -> bool:
    relative = path.relative_to(REPO_ROOT)
    if relative.parts and relative.parts[0] in EXCLUDED_DIRS:
        return True
    return len(relative.parts) == 1 and relative.name in EXCLUDED_FILES


def main() -> int:
    broken: list[str] = []
    checked = 0

    for path in sorted(REPO_ROOT.rglob("*.md")):
        if is_excluded(path):
            continue

        checked += 1
        content = strip_code(path.read_text(encoding="utf-8"))

        for target in LINK.findall(content):
            target = target.strip()
            if EXTERNAL.match(target):
                continue

            # Drop any anchor; only the file needs to exist.
            file_part = target.split("#", 1)[0]
            if not file_part:
                continue

            resolved = (path.parent / file_part).resolve()
            if not resolved.exists():
                rel = path.relative_to(REPO_ROOT).as_posix()
                broken.append(f"{rel}: broken link -> {target}")

    if broken:
        print(f"Checked {checked} APIx-owned Markdown files. Broken links found:")
        for entry in broken:
            print(f"  - {entry}")
        return 1

    print(f"Checked {checked} APIx-owned Markdown files. All internal links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
