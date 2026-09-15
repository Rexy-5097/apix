"""Which fare is recorded for a selected flight -- procedure s6, spec B.4.

The contract takes the **Saver** family for every selected flight. Two frozen
rules constrain that choice and are checked rather than assumed:

* The procedure's rule is *the cheapest fare that includes checked baggage*.
  On the 2026-09-12 panel that fare was Saver on all 30 primary rows. If the
  page ever offers a cheaper checked-baggage family, Saver is no longer the
  contracted fare and the quote is **excluded with a reason**, not recorded
  under a rule it does not satisfy.
* **Lite is never substituted.** A flight whose Saver is missing is excluded;
  a flight whose Saver is sold out is recorded as unpriced. Neither borrows a
  price from another family.

This is the one place the collector reads prices before recording them, and it
reads them only *within* a flight that has already been selected. Flight
selection (``selection.py``) never sees a fare.

Entitlements are read from what the page displays. A value the page did not show
makes the quote undeterminable and it is excluded -- spec B.4, "not guessed into
the nearest class".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from apix.ingestion.collectors.candidates import FareOption, FlightCandidate
from apix.ingestion.collectors.contract import CollectionContract


class FareStatus(Enum):
    PRICED = "PRICED"
    SOLD_OUT = "SOLD_OUT"
    EXCLUDED = "EXCLUDED"


class FareExclusion(Enum):
    """Why a selected flight produced no recordable contract fare."""

    #: A field every observation needs (e.g. duration) was not readable.
    REQUIRED_FIELD_UNREADABLE = "REQUIRED_FIELD_UNREADABLE"
    #: No Saver tile on the flight. Lite is never substituted.
    FARE_FAMILY_NOT_OFFERED = "FARE_FAMILY_NOT_OFFERED"
    #: More than one tile normalises to Saver; which one is unknowable.
    FARE_FAMILY_AMBIGUOUS = "FARE_FAMILY_AMBIGUOUS"
    FARE_UNREADABLE = "FARE_UNREADABLE"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    CONCESSION_FARE = "CONCESSION_FARE"
    ENTITLEMENTS_UNDETERMINABLE = "ENTITLEMENTS_UNDETERMINABLE"
    #: Saver shown with no checked bag -- it is not the contracted product.
    NO_CHECKED_BAGGAGE = "NO_CHECKED_BAGGAGE"
    #: A cheaper family also includes checked baggage, so Saver fails procedure s6.
    CHEAPER_CHECKED_BAGGAGE_FARE = "CHEAPER_CHECKED_BAGGAGE_FARE"


@dataclass(frozen=True, slots=True)
class FareDecision:
    candidate: FlightCandidate
    status: FareStatus
    option: FareOption | None = None
    exclusion: FareExclusion | None = None
    detail: str = ""


def normalise_family_label(label: str) -> str:
    """``"Saver fare"``, ``"SAVER"`` and ``" saver "`` all normalise to ``"saver"``."""
    text = re.sub(r"\s+", " ", label.strip().casefold())
    return re.sub(r"\s*fare$", "", text).strip()


def _excluded(
    candidate: FlightCandidate, why: FareExclusion, detail: str, option: FareOption | None = None
) -> FareDecision:
    return FareDecision(candidate, FareStatus.EXCLUDED, option, why, detail)


def choose_contract_fare(candidate: FlightCandidate, contract: CollectionContract) -> FareDecision:
    """Decide what, if anything, is recorded for one selected flight."""
    if candidate.duration_minutes is None:
        return _excluded(
            candidate, FareExclusion.REQUIRED_FIELD_UNREADABLE, "duration not readable"
        )

    families = ", ".join(sorted(o.family_label for o in candidate.fares)) or "none rendered"
    if candidate.sold_out:
        return FareDecision(candidate, FareStatus.SOLD_OUT, detail="flight shown as sold out")

    wanted = normalise_family_label(contract.fare_family)
    matches = [o for o in candidate.fares if normalise_family_label(o.family_label) == wanted]
    if not matches:
        return _excluded(
            candidate,
            FareExclusion.FARE_FAMILY_NOT_OFFERED,
            f"{contract.fare_family} not offered; families shown: {families}. Not substituted",
        )
    if len(matches) > 1:
        return _excluded(
            candidate,
            FareExclusion.FARE_FAMILY_AMBIGUOUS,
            f"{len(matches)} tiles normalise to {contract.fare_family}",
        )
    saver = matches[0]

    if not saver.available:
        return FareDecision(
            candidate,
            FareStatus.SOLD_OUT,
            option=saver,
            detail=f"{saver.family_label} not purchasable; families shown: {families}",
        )
    if saver.concession:
        return _excluded(candidate, FareExclusion.CONCESSION_FARE, saver.family_label, saver)
    # Readability before currency: an unreadable price string yields no currency
    # either, and reporting that as a currency mismatch would turn a collector
    # failure into a statement about the market.
    if saver.payable_fare is None or saver.payable_fare <= 0:
        return _excluded(
            candidate, FareExclusion.FARE_UNREADABLE, f"payable_fare={saver.payable_fare}", saver
        )
    if saver.currency is None:
        return _excluded(candidate, FareExclusion.FARE_UNREADABLE, "currency not displayed", saver)
    if saver.currency != contract.currency:
        return _excluded(
            candidate,
            FareExclusion.CURRENCY_MISMATCH,
            f"currency={saver.currency} expected {contract.currency}",
            saver,
        )
    missing = [
        name
        for name, value in (
            ("checked_baggage_kg", saver.checked_baggage_kg),
            ("change_policy", saver.change_policy),
            ("cancellation_policy", saver.cancellation_policy),
        )
        if value is None
    ]
    if missing:
        return _excluded(
            candidate,
            FareExclusion.ENTITLEMENTS_UNDETERMINABLE,
            f"not displayed or not recognised: {missing}",
            saver,
        )
    if saver.checked_baggage_kg == 0:
        return _excluded(
            candidate, FareExclusion.NO_CHECKED_BAGGAGE, f"{saver.family_label} shows 0 kg", saver
        )

    cheaper = sorted(
        o.family_label
        for o in candidate.fares
        if o is not saver
        and o.available
        and not o.concession
        and o.currency == contract.currency
        and o.payable_fare is not None
        and o.payable_fare < saver.payable_fare
        and (o.checked_baggage_kg or 0) > 0
    )
    if cheaper:
        return _excluded(
            candidate,
            FareExclusion.CHEAPER_CHECKED_BAGGAGE_FARE,
            f"{cheaper} include checked baggage and cost less than "
            f"{saver.family_label}; procedure s6 contract rule not met",
            saver,
        )
    return FareDecision(candidate, FareStatus.PRICED, option=saver)


__all__ = [
    "FareDecision",
    "FareExclusion",
    "FareStatus",
    "choose_contract_fare",
    "normalise_family_label",
]
