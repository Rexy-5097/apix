"""The egress policy, and the property that makes it more than a document.

An evasion system and a compliant collector can look identical at rest. The
difference is a single code path: whether a refusal -- a challenge, a block, an
HTTP 429, an unreachable source -- can influence which egress the next request
uses. These tests assert, statically over every function in ``src/apix/``, that
no such path exists, and that no proxy or rotation library is importable from
the package at all.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from apix.ingestion.collectors.egress import (
    DECLARED_EGRESS,
    EgressMode,
    EgressPolicy,
    RotationPolicy,
    select_egress,
)

APIX_ROOT = Path(__file__).resolve().parents[1] / "src" / "apix"

#: Identifiers whose presence in a function marks it as handling a refusal.
REFUSAL_SYMBOLS = frozenset(
    {
        "ACCESS_CHALLENGE",
        "CAPTCHA_OR_ANTIBOT_STOP",
        "SOURCE_UNAVAILABLE",
        "PERMISSION_BLOCKED",
        "GateRefused",
        "is_stop_signal",
        "CHALLENGED",
        "UNREACHABLE",
    }
)
#: Identifiers whose presence marks a function as touching egress selection.
EGRESS_SYMBOLS = frozenset({"select_egress", "EgressPolicy", "DECLARED_EGRESS", "egress_label"})
#: Third-party packages that exist to rotate identity. None may be imported.
ROTATION_LIBRARIES = frozenset(
    {
        "scrapy_rotating_proxies",
        "rotating_proxies",
        "fake_useragent",
        "stem",
        "torpy",
        "undetected_chromedriver",
        "playwright_stealth",
        "selenium_stealth",
        "puppeteer_extra",
        "proxybroker",
        "free_proxy",
    }
)


def _names_in(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def _functions() -> list[tuple[str, ast.AST]]:
    out: list[tuple[str, ast.AST]] = []
    for path in sorted(APIX_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                out.append((f"{path.relative_to(APIX_ROOT)}::{node.name}", node))
    return out


# ───────────────────────── the declared policy ─────────────────────────


def test_the_declared_policy_is_single_stable_and_never_rotates() -> None:
    assert DECLARED_EGRESS.mode is EgressMode.SINGLE_STABLE
    assert DECLARED_EGRESS.rotation is RotationPolicy.NEVER
    assert DECLARED_EGRESS.rotate_on_refusal is False
    assert DECLARED_EGRESS.identifying_user_agent is True


def test_rotation_on_refusal_cannot_be_declared() -> None:
    """The field exists so it can be asserted False, not so it can be set True."""
    with pytest.raises(ValueError, match="evasion"):
        EgressPolicy(
            policy_id="x",
            version="1",
            mode=EgressMode.SINGLE_STABLE,
            rotation=RotationPolicy.NEVER,
            egress_label="x",
            identifying_user_agent=True,
            rotate_on_refusal=True,
            authority="test",
        )


def test_never_is_the_only_rotation_policy() -> None:
    """The enum has one member. Adding another is a reviewed decision on record."""
    assert [m.value for m in RotationPolicy] == ["NEVER"]


def test_an_unidentified_collector_is_refused() -> None:
    with pytest.raises(ValueError, match="identify the project"):
        EgressPolicy(
            policy_id="x",
            version="1",
            mode=EgressMode.SINGLE_STABLE,
            rotation=RotationPolicy.NEVER,
            egress_label="x",
            identifying_user_agent=False,
            rotate_on_refusal=False,
            authority="test",
        )


# ───────────────────────── the structural guarantee ─────────────────────────


def test_select_egress_cannot_see_a_refusal() -> None:
    """The signature is the guarantee: no outcome, status or history parameter."""
    params = inspect.signature(select_egress).parameters
    assert list(params) == ["policy"], (
        f"select_egress takes {list(params)}; it must take only the policy, so nothing about "
        "a refusal can reach it"
    )
    assert select_egress() == DECLARED_EGRESS.egress_label
    assert select_egress() == select_egress(), "the answer never changes"


def test_no_function_both_handles_a_refusal_and_selects_egress() -> None:
    """The machine-checkable difference between this collector and an evasion system.

    Walks every function in ``src/apix/``. A function that references any
    refusal symbol AND any egress symbol is a path from a block to a change of
    identity, and fails the build.
    """
    offenders = []
    for name, fn in _functions():
        names = _names_in(fn)
        if names & REFUSAL_SYMBOLS and names & EGRESS_SYMBOLS:
            offenders.append(
                f"{name}: {sorted(names & REFUSAL_SYMBOLS)} with {sorted(names & EGRESS_SYMBOLS)}"
            )
    assert not offenders, (
        "a refusal handler reaches egress selection -- that is rotation on refusal:\n  "
        + "\n  ".join(offenders)
    )


def test_no_rotation_or_stealth_library_is_imported_anywhere() -> None:
    """Parsed statically, so a guarded or lazy import is still caught."""
    offenders = []
    for path in sorted(APIX_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module.split(".")[0]]
            for m in mods:
                if m in ROTATION_LIBRARIES:
                    offenders.append(f"{path.relative_to(APIX_ROOT)} imports {m}")
    assert not offenders, f"rotation/stealth library imported: {offenders}"


def test_the_browser_adapter_configures_no_proxy() -> None:
    """The Playwright adapter must launch with the machine's own identity."""
    live = (APIX_ROOT / "ingestion" / "collectors" / "indigo" / "live.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(live)
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in {"proxy", "proxies"}:
            pytest.fail("live.py passes a proxy option to the browser; the policy forbids it")
    assert "no proxy" in live.lower(), "live.py should state its no-proxy identity"
