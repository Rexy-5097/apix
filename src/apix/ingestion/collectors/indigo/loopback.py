"""Drive the real browser adapter against a page THIS REPOSITORY serves.

Why this exists
---------------
``live.py`` has never run. The compliance gate refuses every source before the
adapter is constructed, so Playwright has never launched, never navigated,
never executed the extraction script and never produced a candidate. The code
was unit-tested; the *browser path* was not exercised at all. That was the one
claim in this project resting on nothing.

This module closes that gap without collecting from anybody. It points the same
``LiveIndigoAdapter`` at ``tools/collection/loopback_site.py`` -- a synthetic
page served on 127.0.0.1 by this repository -- and runs the contracted
navigation plan against it in a real Chromium.

What it proves, and what it does not
------------------------------------
**Proves:** the browser launches; the navigation plan's vocabulary (click, fill,
pick a date, set counts, choose, assert, submit, wait) drives a real DOM; the
extraction script runs in-page and returns an ``indigo-extract/1`` payload; the
parser turns that payload into typed candidates; evidence capture produces a
real screenshot, DOM and payload; an access challenge is detected and stops the
run; a changed DOM surfaces as ``UNRECOGNISED`` instead of a guess.

**Does not prove:** that ``navigation.SELECTORS`` and ``live.EXTRACT_SELECTORS``
match goindigo.in. They remain ``UNVERIFIED``. The fixture page implements the
selector contract *as written*, so this exercises the machine, not the mapping.
The mapping can only be verified against the real site, which requires the
authorization we do not have.

Safety
------
The adapter is constructed through
:func:`~apix.ingestion.collectors.gate.require_loopback_clearance`, which fails
unless the entry declares itself ``AUTOMATION_SELF_HOSTED`` and
``INADMISSIBLE_SYNTHETIC`` *and* the URL resolves to the loopback interface.
Those first two values are disjoint from ``LIVE_REQUIREMENTS``, so
:data:`LOOPBACK_ENTRY` can never clear the live gate and no registry source can
ever clear the loopback gate. :data:`LOOPBACK_ENTRY` is defined here rather than
in ``source_registry/registry.yaml`` precisely because it is not a source: the
register describes places that hold airfares, and this is our own test page.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from types import MappingProxyType
from typing import ClassVar

from apix.ingestion.collectors.contract import ist_now
from apix.ingestion.collectors.gate import (
    CollectionMode,
    GateDecision,
    require_loopback_clearance,
)
from apix.ingestion.collectors.indigo.live import LiveIndigoAdapter

#: The self-hosted page, as a gate entry. Not a source, and not in the register.
LOOPBACK_ENTRY: Mapping[str, object] = MappingProxyType(
    {
        "source_id": "apix-loopback-fixture",
        "display_name": "APIx loopback fixture site (this repository)",
        "channel": "SELF_HOSTED_FIXTURE",
        "automation_gate": "AUTOMATION_SELF_HOSTED",
        "automation_gate_basis": (
            "tools/collection/loopback_site.py is served by this repository on the "
            "loopback interface. There is no third party, no Terms of Service and "
            "no robots.txt to respect: we are the publisher."
        ),
        "data_admissibility": "INADMISSIBLE_SYNTHETIC",
        "data_admissibility_basis": (
            "Every fare on the page is invented. Nothing produced here may enter "
            "@primary or any index input."
        ),
        "operational_status": "EXERCISED",
    }
)


class LoopbackIndigoAdapter(LiveIndigoAdapter):
    """:class:`LiveIndigoAdapter` pointed at our own page, on 127.0.0.1.

    Same browser, same navigation plan, same extraction script, same parser.
    Only two things differ: which gate must clear, and which URL is loaded.
    """

    source_id: ClassVar[str] = "apix-loopback-fixture"
    registry_id: ClassVar[str] = "apix-loopback-fixture"

    def __init__(
        self,
        base_url: str,
        *,
        registry_entry: Mapping[str, object] = LOOPBACK_ENTRY,
        headless: bool = True,
        timeout_ms: int = 10_000,
        clock: Callable[[], datetime] = ist_now,
    ) -> None:
        super().__init__(
            registry_entry,
            headless=headless,
            timeout_ms=timeout_ms,
            clock=clock,
            base_url=base_url,
        )
        # Set after super().__init__, which sets LIVE: nothing this adapter
        # produces may be recorded as a live collection.
        self.mode = CollectionMode.LOOPBACK

    def _clear_gate(self, registry_entry: Mapping[str, object]) -> GateDecision:
        return require_loopback_clearance(registry_entry, self.base_url)

    def environment(self) -> dict[str, str]:
        return {
            **super().environment(),
            "mode": CollectionMode.LOOPBACK.value,
            "data_class": "SYNTHETIC",
            "selector_contract": (
                "implemented by the fixture page, NOT verified against goindigo.in"
            ),
        }


__all__ = ["LOOPBACK_ENTRY", "LoopbackIndigoAdapter"]
