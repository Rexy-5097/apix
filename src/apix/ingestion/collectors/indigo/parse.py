"""IndiGo results page: displayed strings -> typed candidates.

The live adapter does not hand HTML to this module. It extracts an
**extraction payload** -- the strings the page displays, grouped per flight card
and fare tile -- and this module types them. The split is deliberate:

* the DOM-dependent part (selectors, clicks) is small, isolated in
  ``navigation.py`` / ``live.py``, and the part most likely to break on a redesign;
* the string parsing here is testable offline, and its formats are taken from
  what goindigo.in actually displayed in the 2026-09-12 manual screenshots
  (``6E 6218``, ``06:05``, ``02h 15m``, ``Non-stop``, ``Saver fare``,
  ``15 kg Check-in bag allowance``, ``Change and cancellation charges``,
  ``Base Airfare`` / ``Total Tax`` / ``TOTAL FARE``).

A string that does not parse becomes ``None`` plus a recorded parse issue. A
missing *key* in the payload means the extractor and the page no longer agree,
and is reported as a structural issue -- the DOM-change signal.

Payload schema ``indigo-extract/1``::

    {"schema": "indigo-extract/1",
     "page": {"kind": "results|no_flights|challenge|error", "http_status": 200,
              "message": "..."},
     "search_echo": {"origin": "DEL", "destination": "BOM", "date_label": "22nd Sep",
                     "passengers_label": "1 Passenger", "currency_label": "INR",
                     "trip_label": "One Way"},
     "flights": [{"flight_label": "6E 6218", "departure": "06:05", "arrival": "08:20",
                  "departure_day_offset": 0, "origin_label": "DEL, T1",
                  "destination_label": "BOM, T2", "duration": "02h 15m",
                  "stops": "Non-stop", "operated_by": "", "sold_out": false,
                  "fares": [{"family": "Saver fare", "price": "<rupee>6,530",
                             "available": true, "concession": false,
                             "entitlements": ["15 kg Check-in bag allowance"],
                             "policy": ["Change and cancellation charges: Standard"],
                             "breakdown": {"Base Airfare": "<rupee>5,065",
                                           "Total Tax": "<rupee>1,465"}}]}]}
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time, timedelta
from decimal import Decimal, InvalidOperation

from apix.ingestion.collectors.candidates import (
    DisplayedSearch,
    FareOption,
    FlightCandidate,
    PageState,
)
from apix.ingestion.collectors.contract import SearchParams
from apix.schemas.enums import ChangePolicy
from apix.schemas.observation import FareBreakdown

PARSER_VERSION = "indigo-extract-parser/1"
EXTRACT_SCHEMA = "indigo-extract/1"
RUPEE = "₹"

REQUIRED_PAGE_KEYS = ("schema", "page", "search_echo", "flights")
REQUIRED_ECHO_KEYS = (
    "origin",
    "destination",
    "date_label",
    "passengers_label",
    "currency_label",
    "trip_label",
)
REQUIRED_FLIGHT_KEYS = (
    "flight_label",
    "departure",
    "arrival",
    "origin_label",
    "destination_label",
    "duration",
    "stops",
    "operated_by",
    "sold_out",
    "fares",
)
REQUIRED_FARE_KEYS = (
    "family",
    "price",
    "available",
    "concession",
    "entitlements",
    "policy",
    "breakdown",
)

_MONTHS = {
    m: i
    for i, m in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        start=1,
    )
}
_CONCESSION_WORDS = ("student", "senior", "armed forces", "doctor", "nurse", "defence")


# ── display-string parsers ──────────────────────────────────────────────────


def parse_clock(text: str) -> time | None:
    """``06:05`` or ``6:05 PM``. Anything else is None."""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?\s*", text or "", re.IGNORECASE)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    meridiem = (m.group(3) or "").lower().replace(".", "")
    if meridiem:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def parse_duration(text: str) -> int | None:
    """``02h 15m`` -> 135, ``2h`` -> 120, ``45m`` -> 45."""
    m = re.fullmatch(
        r"\s*(?:(\d+)\s*h(?:rs?)?)?\s*(?:(\d+)\s*m(?:in)?)?\s*", text or "", re.IGNORECASE
    )
    if not m or (m.group(1) is None and m.group(2) is None):
        return None
    minutes = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    return minutes or None


def parse_flight_label(text: str) -> tuple[str, str] | None:
    """``6E 6218`` -> ``("6E", "6218")``. The number is digits only."""
    m = re.fullmatch(r"\s*([A-Z0-9]{2})\s*-?\s*(\d{1,4})\s*", (text or "").upper())
    if not m or not re.search(r"[A-Z]", m.group(1)):
        return None
    return m.group(1), m.group(2)


def parse_currency(text: str) -> str | None:
    t = (text or "").strip().upper()
    if t.startswith(RUPEE) or t.startswith("INR") or t.startswith("RS"):
        return "INR"
    if t.startswith("$") or t.startswith("USD"):
        return "USD"
    m = re.match(r"([A-Z]{3})\b", t)
    return m.group(1) if m else None


def parse_money(text: str) -> tuple[Decimal | None, str | None]:
    """``<rupee>6,530`` -> ``(Decimal("6530"), "INR")``. Unreadable amounts are None."""
    currency = parse_currency(text)
    digits = re.sub(r"[^0-9.]", "", re.sub(r"^\s*(INR|RS\.?|USD)", "", (text or "").upper()))
    if not digits:
        return None, currency
    try:
        return Decimal(digits), currency
    except InvalidOperation:
        return None, currency


def parse_airport_code(text: str) -> str | None:
    m = re.search(r"\b([A-Z]{3})\b", text or "")
    return m.group(1) if m else None


def parse_stops(text: str) -> int | None:
    t = (text or "").strip().casefold()
    if t in ("non-stop", "nonstop", "non stop", "direct"):
        return 0
    m = re.fullmatch(r"(\d+)\s*stops?", t)
    return int(m.group(1)) if m else None


def parse_checked_baggage(lines: Sequence[str]) -> int | None:
    """The CHECKED allowance. Cabin allowances are ignored. Unknown is None."""
    found: set[int] = set()
    for line in lines:
        t = line.casefold()
        if "cabin bag only" in t or re.search(r"no check-?\s*in bag", t):
            found.add(0)
            continue
        if "check-in" in t or "checkin" in t or "checked" in t:
            m = re.search(r"(\d+)\s*kg", t)
            if m:
                found.add(int(m.group(1)))
    return found.pop() if len(found) == 1 else None


#: (pattern, change, cancellation). Standard -> FEE is how the 2026-09-12 manual
#: collectors recorded the Saver line "Change and cancellation charges: Standard"
#: on all 30 primary rows. Anything not listed stays undeterminable.
_POLICY_RULES: tuple[tuple[str, ChangePolicy | None, ChangePolicy | None], ...] = (
    (r"change and cancellation charges\s*:?\s*standard", ChangePolicy.FEE, ChangePolicy.FEE),
    (r"free (date )?change", ChangePolicy.FREE, None),
    (r"change fee", ChangePolicy.FEE, None),
    (r"no changes? (permitted|allowed)", ChangePolicy.NONE, None),
    (r"free cancellation", None, ChangePolicy.FREE),
    (r"cancellation fee", None, ChangePolicy.FEE),
    (r"non-?refundable", None, ChangePolicy.NONE),
)


def parse_change_cancellation(
    lines: Sequence[str],
) -> tuple[ChangePolicy | None, ChangePolicy | None]:
    """Map displayed policy lines to entitlements. Conflicting lines give None."""
    change: set[ChangePolicy] = set()
    cancel: set[ChangePolicy] = set()
    for line in lines:
        t = line.casefold()
        for pattern, ch, ca in _POLICY_RULES:
            if re.search(pattern, t):
                if ch is not None:
                    change.add(ch)
                if ca is not None:
                    cancel.add(ca)
    return (
        change.pop() if len(change) == 1 else None,
        cancel.pop() if len(cancel) == 1 else None,
    )


def parse_breakdown(labels: Mapping[str, str]) -> FareBreakdown:
    """Components only where displayed. An absent label stays None, never 0."""
    values: dict[str, Decimal] = {}
    for label, raw in labels.items():
        key = label.strip().casefold()
        amount, _ = parse_money(str(raw))
        if amount is None:
            continue
        if key in ("base airfare", "base fare"):
            values["base_fare"] = amount
        elif key == "total tax":
            values["taxes"] = amount
        elif key in ("taxes & fees", "taxes and fees", "taxes"):
            values.setdefault("taxes", amount)
        elif key in ("user development fee", "udf"):
            values["user_development_fee"] = amount
    return FareBreakdown(**values)


def parse_day_month(label: str, reference: date) -> date | None:
    """``22nd Sep`` near ``reference`` -> the date. ISO strings are accepted too."""
    text = (label or "").strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})", text)
    if not m or m.group(2).casefold() not in _MONTHS:
        return None
    day, month = int(m.group(1)), _MONTHS[m.group(2).casefold()]
    options = []
    for year in (reference.year - 1, reference.year, reference.year + 1):
        try:
            options.append(date(year, month, day))
        except ValueError:
            continue
    return min(options, key=lambda d: abs((d - reference).days)) if options else None


def parse_passengers(label: str) -> int | None:
    m = re.search(r"(\d+)\s*(passenger|adult)", (label or "").casefold())
    return int(m.group(1)) if m else None


def parse_trip(label: str) -> str | None:
    t = (label or "").casefold()
    if re.search(r"one[\s-]?way", t):
        return "ONE_WAY"
    if "round" in t:
        return "ROUND_TRIP"
    return None


# ── payload parsing ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ParsedPage:
    page_state: PageState
    displayed: DisplayedSearch | None
    candidates: tuple[FlightCandidate, ...]
    structural_issues: tuple[str, ...]
    http_status: int | None
    detail: str


def _missing(obj: object, keys: Sequence[str]) -> list[str]:
    if not isinstance(obj, Mapping):
        return list(keys)
    return [k for k in keys if k not in obj]


def _fare(tile: Mapping[str, object], issues: list[str]) -> FareOption:
    family = str(tile["family"])
    amount, currency = parse_money(str(tile["price"]))
    if amount is None:
        issues.append(f"price unreadable for {family}: {tile['price']!r}")
    raw_entitlements = tile["entitlements"]
    entitlements = [str(x) for x in raw_entitlements] if isinstance(raw_entitlements, list) else []
    raw_policy = tile["policy"]
    policy = [str(x) for x in raw_policy] if isinstance(raw_policy, list) else []
    change, cancel = parse_change_cancellation(policy)
    raw_breakdown = tile["breakdown"]
    breakdown = parse_breakdown(
        {str(k): str(v) for k, v in raw_breakdown.items()}
        if isinstance(raw_breakdown, Mapping)
        else {}
    )
    concession = bool(tile["concession"]) or any(w in family.casefold() for w in _CONCESSION_WORDS)
    return FareOption(
        family_label=family,
        payable_fare=amount,
        currency=currency,
        available=bool(tile["available"]),
        checked_baggage_kg=parse_checked_baggage(entitlements),
        change_policy=change,
        cancellation_policy=cancel,
        breakdown=breakdown,
        concession=concession,
        displayed_terms=tuple(entitlements + policy),
    )


def _operator(text: str, marketing: str | None) -> str | None:
    t = (text or "").strip()
    if not t:
        return marketing
    return "6E" if "indigo" in t.casefold() else t


def parse_extracted(payload: Mapping[str, object], params: SearchParams) -> ParsedPage:
    """Type an ``indigo-extract/1`` payload. Never guesses a missing value."""
    missing = _missing(payload, REQUIRED_PAGE_KEYS)
    if missing:
        return ParsedPage(
            PageState.UNRECOGNISED, None, (), (f"PAGE_MISSING_KEYS:{missing}",), None, ""
        )
    if payload["schema"] != EXTRACT_SCHEMA:
        return ParsedPage(
            PageState.UNRECOGNISED, None, (), (f"SCHEMA_MISMATCH:{payload['schema']!r}",), None, ""
        )
    page = payload["page"]
    if not isinstance(page, Mapping) or "kind" not in page:
        return ParsedPage(PageState.UNRECOGNISED, None, (), ("PAGE_KIND_MISSING",), None, "")
    status_raw = page.get("http_status")
    http_status = int(status_raw) if isinstance(status_raw, int) else None
    message = str(page.get("message", ""))
    kind = page["kind"]
    states = {
        "challenge": PageState.ACCESS_CHALLENGE,
        "error": PageState.SITE_ERROR,
        "no_flights": PageState.NO_FLIGHTS_MESSAGE,
        "results": PageState.RESULTS,
    }
    if kind not in states:
        return ParsedPage(
            PageState.UNRECOGNISED, None, (), (f"UNKNOWN_PAGE_KIND:{kind!r}",), http_status, message
        )
    state = states[str(kind)]
    if state is not PageState.RESULTS:
        return ParsedPage(state, None, (), (), http_status, message)

    issues: list[str] = []
    echo = payload["search_echo"]
    echo_missing = _missing(echo, REQUIRED_ECHO_KEYS)
    displayed: DisplayedSearch | None = None
    if echo_missing:
        issues.append(f"SEARCH_ECHO_MISSING_KEYS:{echo_missing}")
    else:
        assert isinstance(echo, Mapping)
        displayed = DisplayedSearch(
            origin=parse_airport_code(str(echo["origin"])),
            destination=parse_airport_code(str(echo["destination"])),
            travel_date=parse_day_month(str(echo["date_label"]), params.travel_date),
            adults=parse_passengers(str(echo["passengers_label"])),
            currency=parse_currency(str(echo["currency_label"])),
            trip_type=parse_trip(str(echo["trip_label"])),
        )

    flights = payload["flights"]
    if not isinstance(flights, list):
        return ParsedPage(
            PageState.UNRECOGNISED, displayed, (), ("FLIGHTS_NOT_A_LIST",), http_status, message
        )

    candidates: list[FlightCandidate] = []
    for position, card in enumerate(flights):
        card_missing = _missing(card, REQUIRED_FLIGHT_KEYS)
        if card_missing:
            issues.append(f"FLIGHT_CARD_{position}_MISSING_KEYS:{card_missing}")
            continue
        assert isinstance(card, Mapping)
        tiles = card["fares"] if isinstance(card["fares"], list) else []
        tile_issue = [
            f"FARE_TILE_{position}.{i}_MISSING_KEYS:{m}"
            for i, tile in enumerate(tiles)
            if (m := _missing(tile, REQUIRED_FARE_KEYS))
        ]
        if tile_issue:
            issues.extend(tile_issue)
            continue

        parse_issues: list[str] = []
        label = str(card["flight_label"])
        ident = parse_flight_label(label)
        if ident is None:
            parse_issues.append(f"flight label unreadable: {label!r}")
        dep = parse_clock(str(card["departure"]))
        if dep is None:
            parse_issues.append(f"departure unreadable: {card['departure']!r}")
        duration = parse_duration(str(card["duration"]))
        if duration is None:
            parse_issues.append(f"duration unreadable: {card['duration']!r}")
        offset = card.get("departure_day_offset", 0)
        base_date = displayed.travel_date if displayed else None
        dep_date = (
            base_date + timedelta(days=int(offset))
            if base_date and isinstance(offset, int)
            else None
        )
        marketing = ident[0] if ident else None
        candidates.append(
            FlightCandidate(
                position=position,
                raw_label=label,
                marketing_carrier=marketing,
                operating_carrier=_operator(str(card["operated_by"]), marketing),
                flight_number=ident[1] if ident else None,
                origin=parse_airport_code(str(card["origin_label"])),
                destination=parse_airport_code(str(card["destination_label"])),
                departure_date=dep_date,
                departure_time=dep,
                arrival_time=parse_clock(str(card["arrival"])),
                duration_minutes=duration,
                stops=parse_stops(str(card["stops"])),
                sold_out=bool(card["sold_out"]),
                fares=tuple(_fare(t, parse_issues) for t in tiles if isinstance(t, Mapping)),
                parse_issues=tuple(parse_issues),
            )
        )
    return ParsedPage(
        PageState.RESULTS, displayed, tuple(candidates), tuple(issues), http_status, message
    )


__all__ = [
    "EXTRACT_SCHEMA",
    "PARSER_VERSION",
    "RUPEE",
    "ParsedPage",
    "parse_airport_code",
    "parse_breakdown",
    "parse_change_cancellation",
    "parse_checked_baggage",
    "parse_clock",
    "parse_currency",
    "parse_day_month",
    "parse_duration",
    "parse_extracted",
    "parse_flight_label",
    "parse_money",
    "parse_passengers",
    "parse_stops",
    "parse_trip",
]
