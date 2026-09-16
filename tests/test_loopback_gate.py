"""The LOOPBACK gate, and the wall between it and live collection.

These tests need no browser, so they run everywhere the rest of the suite runs.
They are the safety half of the loopback work: whatever the browser proof shows,
the mode must never become a route to somebody else's site, and its synthetic
output must never become admissible.

The browser proof itself is ``test_loopback_browser_proof.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apix.ingestion.collectors.gate import (
    LIVE_REQUIREMENTS,
    LOOPBACK_REQUIREMENTS,
    CollectionMode,
    GateRefused,
    evaluate_live_gate,
    evaluate_loopback_gate,
    is_loopback_url,
    require_loopback_clearance,
)
from apix.ingestion.collectors.indigo.loopback import LOOPBACK_ENTRY, LoopbackIndigoAdapter

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "source_registry" / "registry.yaml"
LOCAL = "http://127.0.0.1:8765/"


def registry_sources() -> list[dict]:
    return list(yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["sources"])


# ────────────────────────────────────────────────── the wall, in both directions


def test_the_loopback_entry_can_never_clear_the_live_gate() -> None:
    """Our own fixture is not a source, and must not be usable as one."""
    decision = evaluate_live_gate(LOOPBACK_ENTRY)
    assert decision.allowed is False
    # Two independent reasons, so editing one field is not enough to break through.
    assert any("automation_gate" in f for f in decision.failures)
    assert any("data_admissibility" in f for f in decision.failures)


def test_no_registered_source_can_clear_the_loopback_gate() -> None:
    """The loopback gate is not a back door to any registered source."""
    for entry in registry_sources():
        decision = evaluate_loopback_gate(entry, LOCAL)
        assert decision.allowed is False, f"{entry.get('source_id')} cleared the loopback gate"


def test_the_two_requirement_sets_are_disjoint_by_construction() -> None:
    """Not a coincidence of today's values: the required values cannot overlap."""
    live = dict(LIVE_REQUIREMENTS)
    loop = dict(LOOPBACK_REQUIREMENTS)
    shared = set(live) & set(loop)
    assert shared, "the two gates must constrain at least one common field"
    for field in shared:
        assert not (set(live[field]) & set(loop[field])), (
            f"{field} accepts a value that satisfies both gates"
        )


# ─────────────────────────────────────────────────────────── the loopback check


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8765/",
        "http://localhost:8765/?scenario=results",
        "http://[::1]:8765/",
        "http://127.2.3.4:9/",
    ],
)
def test_loopback_urls_are_recognised(url: str) -> None:
    assert is_loopback_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://www.goindigo.in/",
        "http://127.0.0.1.evil.test/",  # a hostname somebody else owns
        "http://localhost.evil.test/",  # ditto
        "http://169.254.169.254/",  # cloud metadata, not loopback
        "http://10.0.0.1/",
        "http://0.0.0.0/",
        "not a url",
        "",
    ],
)
def test_non_loopback_urls_are_refused(url: str) -> None:
    """Parsed and range-checked, never matched as a substring."""
    assert is_loopback_url(url) is False
    decision = evaluate_loopback_gate(LOOPBACK_ENTRY, url)
    assert decision.allowed is False
    assert any("not a loopback address" in f for f in decision.failures)


def test_the_adapter_refuses_to_construct_against_a_real_host() -> None:
    """The refusal happens in the constructor, before any browser exists."""
    with pytest.raises(GateRefused) as exc:
        LoopbackIndigoAdapter("https://www.goindigo.in/")
    assert "not a loopback address" in str(exc.value)


def test_the_adapter_refuses_an_entry_that_is_not_self_hosted() -> None:
    entry = {**dict(LOOPBACK_ENTRY), "automation_gate": "AUTOMATION_ALLOWED"}
    with pytest.raises(GateRefused):
        LoopbackIndigoAdapter(LOCAL, registry_entry=entry)


# ───────────────────────────────────────────────────── what the mode may produce


def test_the_loopback_entry_declares_itself_synthetic_and_inadmissible() -> None:
    assert LOOPBACK_ENTRY["data_admissibility"] == "INADMISSIBLE_SYNTHETIC"
    assert LOOPBACK_ENTRY["automation_gate"] == "AUTOMATION_SELF_HOSTED"
    assert LOOPBACK_ENTRY["source_id"] == "apix-loopback-fixture"


def test_the_loopback_entry_is_not_in_the_source_register() -> None:
    """The register describes places that hold airfares. This is our test page."""
    sources = registry_sources()
    ids = {e.get("source_id") for e in sources}
    assert LOOPBACK_ENTRY["source_id"] not in ids
    # Deliberately not a hardcoded count: the register grows as sources are
    # audited, and this test is about what must never be IN it.
    assert len(ids) == len(sources), "duplicate source_id in the register"


def test_a_cleared_loopback_gate_reports_the_loopback_mode() -> None:
    decision = require_loopback_clearance(LOOPBACK_ENTRY, LOCAL)
    assert decision.allowed is True
    assert decision.mode is CollectionMode.LOOPBACK
    assert decision.mode is not CollectionMode.LIVE


def test_the_fixture_site_binds_loopback_only() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "tools" / "collection"))
    import loopback_site

    with pytest.raises(ValueError, match="loopback only"):
        loopback_site.serve(0, host="0.0.0.0")
