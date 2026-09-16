"""The browser path, exercised for real against a page this repository serves.

Before this file existed, ``live.py`` had never run. The compliance gate refuses
every source before the adapter is constructed, so Playwright had never
launched, never navigated, never executed the extraction script and never
produced a candidate. Every claim about the browser path rested on code review
alone.

These tests drive the *same* adapter, navigation plan, extraction script and
parser against ``tools/collection/loopback_site.py`` on 127.0.0.1.

What is proven here: the browser launches; the plan's whole vocabulary drives a
real DOM; the extraction script runs in-page; the parser types the payload into
candidates; evidence is captured as real bytes; an access challenge stops the
run; a renamed selector surfaces as UNRECOGNISED.

What is NOT proven here, and is stated in the assertions themselves: that the
selectors match goindigo.in. They remain UNVERIFIED. The fixture implements the
selector contract as written, so this exercises the machine, not the mapping.

Skipped wherever Chromium is absent -- including CI. The safety invariants that
must hold everywhere live in ``test_loopback_gate.py``, which needs no browser.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from apix.ingestion.collectors.candidates import PageState, SearchResult
from apix.ingestion.collectors.contract import CollectionContract, SearchParams
from apix.ingestion.collectors.gate import CollectionMode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "collection"))

pytest.importorskip("playwright.sync_api", reason="pip install -e .[collect]")

import loopback_site  # noqa: E402

from apix.ingestion.collectors.indigo.loopback import LoopbackIndigoAdapter  # noqa: E402

PARAMS = SearchParams(
    source_id="apix-loopback-fixture",
    contract=CollectionContract(),
    collection_date=date(2026, 9, 15),
    travel_date=date(2026, 9, 22),
)


def _chromium_available() -> bool:
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _chromium_available(), reason="chromium is not installed (playwright install chromium)"
)


@pytest.fixture(scope="module")
def site() -> Iterator[str]:
    """The fixture site, on an ephemeral loopback port."""
    httpd = loopback_site.serve(0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    finally:
        httpd.shutdown()
        httpd.server_close()


def run(site: str, scenario: str) -> SearchResult:
    url = f"{site}?scenario={scenario}"
    with LoopbackIndigoAdapter(url, headless=True, timeout_ms=8_000) as adapter:
        return adapter.search(PARAMS)


@pytest.fixture(scope="module")
def results(site: str) -> SearchResult:
    return run(site, "results")


# ───────────────────────────────────────────────────────────── the happy path


def test_the_browser_completes_the_contracted_navigation_plan(results: SearchResult) -> None:
    """Every step of the plan executed against a real DOM, in order."""
    assert results.page_state is PageState.RESULTS, results.detail
    assert results.structural_issues == ()
    assert results.environment["browser"].startswith("chromium/")
    assert results.environment["mode"] == CollectionMode.LOOPBACK.value
    assert results.latency_ms > 0


def test_the_extraction_script_and_parser_produce_typed_candidates(
    results: SearchResult,
) -> None:
    assert len(results.candidates) == len(loopback_site.FLIGHTS) == 3
    first = results.candidates[0]
    assert first.marketing_carrier == "6E"
    assert first.flight_number == "9001"
    assert (first.origin, first.destination) == ("DEL", "BOM")
    assert first.departure_time is not None and first.departure_time.hour == 6
    assert first.duration_minutes == 135
    assert first.stops == 0
    assert first.parse_issues == ()


def test_fares_are_decomposed_from_the_rendered_page(results: SearchResult) -> None:
    """Base, tax and total come off the DOM and reconcile, as the schema requires."""
    fare = results.candidates[0].fares[0]
    assert fare.family_label == "Saver fare"
    assert fare.currency == "INR"
    assert fare.checked_baggage_kg == 15
    assert fare.concession is False
    base, tax = fare.breakdown.base_fare, fare.breakdown.taxes
    assert base is not None and tax is not None
    assert base + tax == fare.payable_fare
    assert fare.breakdown.user_development_fee is None, "absent stays None, never 0"


def test_the_displayed_search_echo_is_read_back_from_the_page(results: SearchResult) -> None:
    """What the page says it searched for, parsed -- not what we asked it to."""
    shown = results.displayed
    assert shown is not None
    assert (shown.origin, shown.destination) == ("DEL", "BOM")
    assert shown.travel_date == PARAMS.travel_date
    assert shown.adults == 1
    assert shown.currency == "INR"
    assert shown.trip_type == "ONE_WAY"


def test_evidence_is_captured_as_real_bytes(results: SearchResult) -> None:
    roles = {a.role: a for a in results.artifacts}
    assert set(roles) == {"results_screenshot", "results_dom", "extracted_payload"}
    shot = roles["results_screenshot"]
    assert shot.content_type == "image/png"
    assert shot.content[:8] == b"\x89PNG\r\n\x1a\n", "not a real PNG"
    assert len(shot.content) > 5_000
    dom = roles["results_dom"].content.decode("utf-8")
    assert "SYNTHETIC FIXTURE PAGE" in dom, "the evidence must show what page this was"
    payload = json.loads(roles["extracted_payload"].content)
    assert payload["schema"] == "indigo-extract/1"
    assert len(payload["flights"]) == 3


def test_nothing_produced_here_is_admissible(results: SearchResult) -> None:
    """The whole point of the mode: a real browser run that is still synthetic."""
    assert results.environment["data_class"] == "SYNTHETIC"
    assert results.environment["mode"] != CollectionMode.LIVE.value
    assert "NOT verified against goindigo.in" in results.environment["selector_contract"]


def test_the_selectors_are_still_recorded_as_unverified(results: SearchResult) -> None:
    """Driving our own page does not verify the mapping to the real site."""
    assert results.environment["selector_status"] == "UNVERIFIED"


# ───────────────────────────────────────────────── the two failure paths that matter


def test_an_access_challenge_stops_the_run_in_a_real_browser(site: str) -> None:
    """Detect, stop, record, defer. No solver, no retry, no second request."""
    result = run(site, "challenge")
    assert result.page_state is PageState.ACCESS_CHALLENGE
    assert "captcha" in result.detail
    assert result.candidates == ()
    assert result.displayed is None
    # Evidence of the challenge is still captured, so the refusal is auditable.
    assert {a.role for a in result.artifacts} == {"results_screenshot", "results_dom"}


def test_a_renamed_selector_surfaces_as_unrecognised_not_as_a_guess(site: str) -> None:
    """One renamed attribute is what a site redesign looks like. Never fill it in."""
    result = run(site, "dom_change")
    assert result.page_state is PageState.UNRECOGNISED
    assert "NAVIGATION_STEP_FAILED wait:results_list" in result.detail
    assert "UNVERIFIED" in result.detail
    assert result.candidates == ()
