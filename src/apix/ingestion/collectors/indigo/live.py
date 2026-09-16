"""Live IndiGo adapter (Playwright). GATED -- it has never run.

The constructor evaluates the compliance gate **before** it imports Playwright,
launches a browser or resolves a hostname. As of the register on this branch
IndiGo is ``AUTOMATION_PROHIBITED``, so construction raises
:class:`~apix.ingestion.collectors.gate.GateRefused` and this code cannot reach
the site. That is the intended behaviour, not a missing feature.

When the register clears on quoted evidence, the adapter:

* uses Playwright's default Chromium with no user-agent override, no stealth
  plugin, no fingerprint changes and no proxy -- the same identity on every run;
* follows :func:`~apix.ingestion.collectors.indigo.navigation.build_navigation_plan`;
* checks for an access challenge after every step and returns
  ``ACCESS_CHALLENGE`` with a screenshot at the first sign of one -- never
  retrying, waiting it out, reloading or solving it;
* captures a full-page screenshot, the page HTML and the extraction payload for
  every search, including failed ones where the page allows.

**The selectors and the extraction script are UNVERIFIED** (see
``navigation.py``). A selector that does not match surfaces as ``UNRECOGNISED``
and is recorded as a ``PARSER_FAILURE``; it is never filled in by guessing.

Install for a cleared source: ``pip install -e .[collect]`` then
``playwright install chromium``.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, ClassVar

from apix.ingestion.collectors.adapter import SourceAdapter
from apix.ingestion.collectors.candidates import Artifact, PageState, SearchResult
from apix.ingestion.collectors.contract import SearchParams, ist_now
from apix.ingestion.collectors.gate import (
    CollectionMode,
    GateDecision,
    require_live_clearance,
)
from apix.ingestion.collectors.indigo.navigation import (
    BASE_URL,
    SELECTOR_STATUS,
    SELECTORS,
    NavStep,
    build_navigation_plan,
)
from apix.ingestion.collectors.indigo.parse import PARSER_VERSION, parse_extracted

#: Text that marks an access challenge. Seeing any of it stops the source.
CHALLENGE_MARKERS = (
    "captcha",
    "verify you are human",
    "unusual traffic",
    "access denied",
    "request blocked",
    "are you a robot",
    "bot detection",
)
CHALLENGE_STATUSES = frozenset({403, 429})

#: Reads the results DOM into an ``indigo-extract/1`` payload. UNVERIFIED.
EXTRACT_SCRIPT = """
(sel) => {
  const q = (root, s) => root.querySelector(s);
  const txt = (root, s) => { const n = q(root, s); return n ? n.innerText.trim() : ""; };
  const all = (root, s) => Array.from(root.querySelectorAll(s));
  const body = document.body.innerText.toLowerCase();
  if (sel.no_flights && q(document, sel.no_flights)) {
    return {schema: "indigo-extract/1",
            page: {kind: "no_flights", message: txt(document, sel.no_flights)},
            search_echo: {}, flights: []};
  }
  const cards = all(document, sel.flight_card);
  return {
    schema: "indigo-extract/1",
    page: {kind: cards.length ? "results" : "unknown", message: ""},
    search_echo: {
      origin: txt(document, sel.echo_origin), destination: txt(document, sel.echo_destination),
      date_label: txt(document, sel.echo_date), passengers_label: txt(document, sel.echo_pax),
      currency_label: txt(document, sel.echo_currency), trip_label: txt(document, sel.echo_trip)
    },
    flights: cards.map(card => ({
      flight_label: txt(card, sel.card_flight), departure: txt(card, sel.card_departure),
      arrival: txt(card, sel.card_arrival), origin_label: txt(card, sel.card_origin),
      destination_label: txt(card, sel.card_destination), duration: txt(card, sel.card_duration),
      stops: txt(card, sel.card_stops), operated_by: txt(card, sel.card_operated_by),
      departure_day_offset: 0, sold_out: !!q(card, sel.card_sold_out),
      fares: all(card, sel.fare_tile).map(tile => ({
        family: txt(tile, sel.fare_family), price: txt(tile, sel.fare_price),
        available: !q(tile, sel.fare_unavailable), concession: false,
        entitlements: all(tile, sel.fare_entitlement).map(n => n.innerText.trim()),
        policy: all(tile, sel.fare_policy).map(n => n.innerText.trim()),
        breakdown: Object.fromEntries(all(tile, sel.fare_breakdown_row).map(r =>
          [txt(r, sel.fare_breakdown_label), txt(r, sel.fare_breakdown_value)]))
      }))
    }))
  };
}
"""

#: Result-page selectors used by EXTRACT_SCRIPT. UNVERIFIED placeholders.
EXTRACT_SELECTORS: dict[str, str] = {
    "no_flights": "[data-testid='no-flights']",
    "flight_card": "[data-testid='flight-card']",
    "echo_origin": "[data-testid='summary-origin']",
    "echo_destination": "[data-testid='summary-destination']",
    "echo_date": "[data-testid='summary-date']",
    "echo_pax": "[data-testid='summary-pax']",
    "echo_currency": "[data-testid='summary-currency']",
    "echo_trip": "[data-testid='summary-trip']",
    "card_flight": "[data-testid='flight-number']",
    "card_departure": "[data-testid='departure-time']",
    "card_arrival": "[data-testid='arrival-time']",
    "card_origin": "[data-testid='departure-airport']",
    "card_destination": "[data-testid='arrival-airport']",
    "card_duration": "[data-testid='duration']",
    "card_stops": "[data-testid='stops']",
    "card_operated_by": "[data-testid='operated-by']",
    "card_sold_out": "[data-testid='sold-out']",
    "fare_tile": "[data-testid='fare-tile']",
    "fare_family": "[data-testid='fare-name']",
    "fare_price": "[data-testid='fare-price']",
    "fare_unavailable": "[data-testid='fare-unavailable']",
    "fare_entitlement": "[data-testid='fare-baggage']",
    "fare_policy": "[data-testid='fare-policy']",
    "fare_breakdown_row": "[data-testid='fare-breakdown-row']",
    "fare_breakdown_label": "[data-testid='fare-breakdown-label']",
    "fare_breakdown_value": "[data-testid='fare-breakdown-value']",
}


class AdapterUnavailable(RuntimeError):
    """Playwright is not installed. Raised only after the gate has cleared."""


def challenge_reason(status: int | None, title: str, text: str) -> str | None:
    """Return why a page is an access challenge, or None if it is not one."""
    if status in CHALLENGE_STATUSES:
        return f"http_status={status}"
    haystack = f"{title}\n{text}".casefold()
    for marker in CHALLENGE_MARKERS:
        if marker in haystack:
            return f"page text contains {marker!r}"
    return None


class LiveIndigoAdapter(SourceAdapter):
    source_id: ClassVar[str] = "indigo-direct"
    registry_id: ClassVar[str] = "indigo"
    adapter_version: ClassVar[str] = "0.1.0"
    parser_version: ClassVar[str] = PARSER_VERSION

    def __init__(
        self,
        registry_entry: Mapping[str, object],
        *,
        headless: bool = False,
        timeout_ms: int = 45_000,
        clock: Callable[[], datetime] = ist_now,
        base_url: str = BASE_URL,
    ) -> None:
        self.mode = CollectionMode.LIVE
        self.base_url = base_url
        # FIRST: the gate. Nothing below runs for a source that is not cleared.
        self.gate = self._clear_gate(registry_entry)
        try:
            self._sync_api: Any = importlib.import_module("playwright.sync_api")
        except ImportError as exc:
            raise AdapterUnavailable(
                "Playwright is not installed: "
                "pip install -e .[collect] && playwright install chromium"
            ) from exc
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._clock = clock
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

    def _clear_gate(self, registry_entry: Mapping[str, object]) -> GateDecision:
        """The clearance this adapter requires. Overridden only by LOOPBACK mode.

        A seam, not a switch: the default is the live gate and no argument can
        change it. :class:`~apix.ingestion.collectors.indigo.loopback.LoopbackIndigoAdapter`
        overrides it with a gate that *cannot* clear a real source.
        """
        return require_live_clearance(registry_entry)

    def environment(self) -> dict[str, str]:
        env = {
            **super().environment(),
            "selector_status": SELECTOR_STATUS,
            "base_url": self.base_url,
        }
        if self._browser is not None:
            env["browser"] = f"chromium/{self._browser.version}"
        return env

    def _ensure_browser(self) -> Any:
        if self._context is None:
            self._playwright = self._sync_api.sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            # Locale and timezone match the manual collector. No UA override.
            self._context = self._browser.new_context(locale="en-IN", timezone_id="Asia/Kolkata")
        return self._context

    def close(self) -> None:
        for handle in (self._context, self._browser):
            if handle is not None:
                handle.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._context = self._browser = self._playwright = None

    def _run_step(self, page: Any, step: NavStep) -> None:
        if step.action == "goto":
            return
        selector = SELECTORS[step.target]
        if step.action == "click":
            locator = page.locator(selector).first
            if step.value == "if_present" and locator.count() == 0:
                return
            locator.click(timeout=self.timeout_ms)
        elif step.action == "assert_signed_out":
            if page.locator(selector).count():
                raise RuntimeError("session appears signed in; the contract requires signed out")
        elif step.action == "fill_airport":
            page.locator(selector).first.fill(step.value, timeout=self.timeout_ms)
            page.locator(SELECTORS["airport_option"].format(code=step.value)).first.click(
                timeout=self.timeout_ms
            )
        elif step.action == "pick_date":
            page.locator(SELECTORS["date_input"]).first.click(timeout=self.timeout_ms)
            page.locator(selector.format(iso=step.value)).first.click(timeout=self.timeout_ms)
        elif step.action == "set_count":
            page.locator(selector).first.fill(step.value, timeout=self.timeout_ms)
        elif step.action == "choose":
            locator = page.locator(selector).first
            if locator.evaluate("n => n.tagName") == "SELECT":
                locator.select_option(step.value, timeout=self.timeout_ms)
            else:
                locator.click(timeout=self.timeout_ms)
        elif step.action == "assert_off":
            toggle = page.locator(selector)
            if toggle.count() and toggle.first.is_checked():
                raise RuntimeError("nearby-airports option is on; the contract requires it off")
        elif step.action == "submit":
            page.locator(selector).first.click(timeout=self.timeout_ms)
        elif step.action == "wait":
            page.locator(selector).first.wait_for(timeout=self.timeout_ms)
        else:  # pragma: no cover - the plan is a closed vocabulary
            raise ValueError(f"unknown navigation action {step.action!r}")

    def search(self, params: SearchParams) -> SearchResult:
        started = self._clock()
        page = self._ensure_browser().new_page()
        artifacts: list[Artifact] = []
        status: int | None = None

        def capture() -> None:
            try:
                artifacts.append(
                    Artifact("results_screenshot", page.screenshot(full_page=True), "image/png")
                )
                artifacts.append(
                    Artifact("results_dom", page.content().encode("utf-8"), "text/html")
                )
            except Exception:  # evidence capture must not mask the original outcome
                pass

        def finish(state: PageState, detail: str, **kw: Any) -> SearchResult:
            return SearchResult(
                params=params,
                page_state=state,
                started_ts=started,
                finished_ts=self._clock(),
                artifacts=tuple(artifacts),
                http_status=status,
                detail=detail,
                environment=self.environment(),
                **kw,
            )

        try:
            try:
                response = page.goto(
                    self.base_url, wait_until="domcontentloaded", timeout=self.timeout_ms
                )
            except Exception as exc:
                capture()
                return finish(
                    PageState.SITE_ERROR,
                    f"navigation to {self.base_url} failed: {type(exc).__name__}",
                )
            status = response.status if response is not None else None
            for step in build_navigation_plan(params):
                if step.action != "goto":
                    try:
                        self._run_step(page, step)
                    except Exception as exc:
                        capture()
                        reason = challenge_reason(status, page.title(), page.inner_text("body"))
                        if reason:
                            return finish(PageState.ACCESS_CHALLENGE, reason)
                        return finish(
                            PageState.UNRECOGNISED,
                            f"NAVIGATION_STEP_FAILED {step.action}:{step.target} "
                            f"({type(exc).__name__}); selectors are {SELECTOR_STATUS}",
                        )
                reason = challenge_reason(status, page.title(), page.inner_text("body"))
                if reason:
                    capture()
                    return finish(PageState.ACCESS_CHALLENGE, reason)

            payload = page.evaluate(EXTRACT_SCRIPT, EXTRACT_SELECTORS)
            capture()
            artifacts.append(
                Artifact(
                    "extracted_payload",
                    json.dumps(payload, sort_keys=True).encode("utf-8"),
                    "application/json",
                )
            )
            if not isinstance(payload, dict):
                return finish(PageState.UNRECOGNISED, "extraction returned no payload")
            parsed = parse_extracted(payload, params)
            return finish(
                parsed.page_state,
                parsed.detail,
                displayed=parsed.displayed,
                candidates=parsed.candidates,
                structural_issues=parsed.structural_issues,
            )
        finally:
            page.close()


__all__ = [
    "CHALLENGE_MARKERS",
    "AdapterUnavailable",
    "LiveIndigoAdapter",
    "challenge_reason",
]
