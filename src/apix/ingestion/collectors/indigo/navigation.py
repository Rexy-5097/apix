"""The contracted IndiGo search, as an ordered navigation plan.

The plan restates ``compliance/manual-collection-procedure.md`` s2-s3 step for
step, so the automated search and the manual one are the same search:

    open goindigo.in -> decline non-essential cookies -> stay signed out
    -> One Way -> From DEL -> To BOM -> click the travel date -> 1 adult
    -> Regular fare (no concession) -> INR -> nearby airports off -> Search
    -> wait for results -> sort by departure, earliest first

No step selects by price, signs in, solves a challenge or changes identity.

**Selector status: UNVERIFIED.** No automated client has ever loaded
goindigo.in from this project's host: ``/robots.txt`` and the home page time out
or reset for non-browser clients (registry audits 2026-09-10 and 2026-09-12, and
again 2026-09-15), and the compliance gate prohibits live automated collection.
The selectors below are therefore **placeholders written against the procedure,
not against the live DOM**. They must be verified in the first gated live run
after the register clears, and a mismatch surfaces as ``UNRECOGNISED`` /
``PARSER_FAILURE`` rather than as a guessed value.
"""

from __future__ import annotations

from dataclasses import dataclass

from apix.ingestion.collectors.contract import SearchParams

BASE_URL = "https://www.goindigo.in/"
SELECTOR_STATUS = "UNVERIFIED"


@dataclass(frozen=True, slots=True)
class NavStep:
    #: ``goto`` | ``click`` | ``fill_airport`` | ``pick_date`` | ``set_count`` |
    #: ``choose`` | ``assert_off`` | ``assert_signed_out`` | ``submit`` | ``wait``
    action: str
    target: str
    value: str = ""


#: Logical target -> CSS selector. UNVERIFIED placeholders; see module docstring.
SELECTORS: dict[str, str] = {
    "cookie_decline": "[data-testid='cookie-reject'], button:has-text('Reject')",
    "sign_in_state": "[data-testid='user-signed-in']",
    "trip_one_way": "[data-testid='trip-type-oneway'], label:has-text('One Way')",
    "origin_input": "[data-testid='origin-input'], input[placeholder*='From']",
    "destination_input": "[data-testid='destination-input'], input[placeholder*='To']",
    "airport_option": "[data-testid='airport-option-{code}']",
    "date_input": "[data-testid='departure-date']",
    "calendar_day": "[data-date='{iso}']",
    "adults_count": "[data-testid='pax-adult-count']",
    "children_count": "[data-testid='pax-child-count']",
    "infants_count": "[data-testid='pax-infant-count']",
    "fare_type_regular": "[data-testid='special-fare-none'], label:has-text('Regular')",
    "currency_select": "[data-testid='currency-select']",
    "nearby_airports_toggle": "[data-testid='nearby-airports']",
    "search_button": "[data-testid='search-flights'], button:has-text('Search')",
    "results_list": "[data-testid='flight-results']",
    "sort_departure": "[data-testid='sort-departure-earliest']",
}


def build_navigation_plan(params: SearchParams) -> tuple[NavStep, ...]:
    """The contracted search for one travel date. Deterministic."""
    c = params.contract
    return (
        NavStep("goto", "home", BASE_URL),
        NavStep("click", "cookie_decline", "if_present"),
        NavStep("assert_signed_out", "sign_in_state"),
        NavStep("click", "trip_one_way"),
        NavStep("fill_airport", "origin_input", c.origin),
        NavStep("fill_airport", "destination_input", c.destination),
        NavStep("pick_date", "calendar_day", params.travel_date.isoformat()),
        NavStep("set_count", "adults_count", str(c.adults)),
        NavStep("set_count", "children_count", str(c.children)),
        NavStep("set_count", "infants_count", str(c.infants)),
        NavStep("choose", "fare_type_regular", c.fare_type),
        NavStep("choose", "currency_select", c.currency),
        NavStep("assert_off", "nearby_airports_toggle"),
        NavStep("submit", "search_button"),
        NavStep("wait", "results_list"),
        # Evidence only: the screenshot then shows departure order. Selection
        # re-sorts by departure itself and never trusts the page's order.
        NavStep("click", "sort_departure", "if_present"),
    )


__all__ = ["BASE_URL", "SELECTORS", "SELECTOR_STATUS", "NavStep", "build_navigation_plan"]
