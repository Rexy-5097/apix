"""What a source returned, before any APIx rule has been applied.

These are **not** observations. A ``FlightCandidate`` is a flight card as the
page rendered it, typed but unjudged: it may be a codeshare, a one-stop, a 05:00
departure or a flight from an alternate airport. Keeping the whole returned
universe -- rather than only what was selected -- is what lets a reviewer check
that the selection rule was applied, and what records the eligible-flight count
per band that ``docs/collection-2026-09-19.md`` s2.1 asks for.

A field the page did not show is ``None``. Nothing here is ever guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum

from apix.ingestion.collectors.contract import SearchParams
from apix.schemas.enums import ChangePolicy
from apix.schemas.observation import NO_BREAKDOWN, FareBreakdown


class PageState(Enum):
    """What kind of page the search produced."""

    #: A results page with flight cards.
    RESULTS = "RESULTS"
    #: The site explicitly said there are no flights. Never read as NO_FLIGHT.
    NO_FLIGHTS_MESSAGE = "NO_FLIGHTS_MESSAGE"
    #: CAPTCHA, bot check, block page, queue. A stop signal.
    ACCESS_CHALLENGE = "ACCESS_CHALLENGE"
    #: Timeout, error page, network failure.
    SITE_ERROR = "SITE_ERROR"
    #: A page the parser does not recognise -- the DOM-change signal.
    UNRECOGNISED = "UNRECOGNISED"


@dataclass(frozen=True, slots=True)
class FareOption:
    """One fare family offered on one flight, as displayed."""

    #: Verbatim label, e.g. ``"Saver fare"``. Audit only; never used for matching.
    family_label: str
    payable_fare: Decimal | None
    currency: str | None
    available: bool
    #: Checked (not cabin) allowance. ``0`` only when the page says none is included.
    checked_baggage_kg: int | None
    change_policy: ChangePolicy | None
    cancellation_policy: ChangePolicy | None
    breakdown: FareBreakdown = NO_BREAKDOWN
    concession: bool = False
    #: The displayed entitlement and policy lines, verbatim, for audit.
    displayed_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FlightCandidate:
    """One flight card from the returned universe."""

    #: Order the page rendered the card in. Evidence only; selection never reads it.
    position: int
    raw_label: str
    marketing_carrier: str | None
    operating_carrier: str | None
    #: Digits only -- ``"6218"``, never ``"6E6218"``.
    flight_number: str | None
    origin: str | None
    destination: str | None
    departure_date: date | None
    departure_time: time | None
    arrival_time: time | None
    duration_minutes: int | None
    stops: int | None
    sold_out: bool = False
    fares: tuple[FareOption, ...] = ()
    parse_issues: tuple[str, ...] = ()

    @property
    def flight_key(self) -> str:
        dep = self.departure_time.strftime("%H:%M") if self.departure_time else "??:??"
        return f"{self.marketing_carrier or '?'}{self.flight_number or '?'}@{dep}"


@dataclass(frozen=True, slots=True)
class DisplayedSearch:
    """The search parameters as the results page echoes them back.

    Checked against what was requested. A page showing USD, two passengers or a
    different date means the search that ran is not the search the contract
    specifies, whatever was typed into the form.
    """

    origin: str | None
    destination: str | None
    travel_date: date | None
    adults: int | None
    currency: str | None
    trip_type: str | None


@dataclass(frozen=True, slots=True)
class Artifact:
    """Raw evidence bytes captured during a search."""

    role: str
    content: bytes
    content_type: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Everything one search produced, success or failure."""

    params: SearchParams
    page_state: PageState
    started_ts: datetime
    finished_ts: datetime
    displayed: DisplayedSearch | None = None
    candidates: tuple[FlightCandidate, ...] = ()
    artifacts: tuple[Artifact, ...] = ()
    http_status: int | None = None
    detail: str = ""
    #: Page-level signals that the layout is not the one the parser was written for.
    structural_issues: tuple[str, ...] = ()
    #: Browser, adapter and parser details for reproducibility.
    environment: dict[str, str] = field(default_factory=dict)

    @property
    def latency_ms(self) -> int:
        return int((self.finished_ts - self.started_ts).total_seconds() * 1000)


__all__ = [
    "Artifact",
    "DisplayedSearch",
    "FareOption",
    "FlightCandidate",
    "PageState",
    "SearchResult",
]
