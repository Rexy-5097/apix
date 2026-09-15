"""The representative route basket — versioned, with declared weight provenance.

PS 26056 asks for *"a basket of representative city-pairs ... selected on the
basis of DGCA passenger-traffic data"*.

**APIx does not hold those weights.** OQ-4 is open: the DGCA city-pair table was
located but its primary file has never been downloaded and column-verified, and
the register records that verification as still required. So this module carries
the **structure** a DGCA-weighted basket needs, and refuses to pretend it holds
the weights.

The refusal is enforced, not documented. Every :class:`RouteWeight` carries a
``weight_source``, and every :class:`RouteBasket` carries a
:class:`BasketStatus`. A basket whose status is not ``OFFICIAL`` answers False to
:meth:`RouteBasket.is_publication_grade`, and the publication layer asks.

**Why weights are not simply invented.** Spec G.2 route weights determine how
much each sector moves the national index. Equal weights across an arbitrary six
routes is not a neutral choice -- it is a strong claim that DEL-BOM and
BLR-HYD contribute equally to household airfare expenditure, which is false and
unmeasured. The dossier's honesty rule is explicit: *"Do not invent a curve."*
The same applies to a weight vector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class BasketStatus(Enum):
    """What kind of weights a basket is holding.

    Only ``OFFICIAL`` may inform a published national index.
    """

    #: Weights derived and verified from DGCA city-pair passenger traffic.
    OFFICIAL = "OFFICIAL"
    #: Structure is real; weights are a declared placeholder pending OQ-4.
    PROVISIONAL = "PROVISIONAL"
    #: Exists to exercise the pipeline. Never a claim about the market.
    DEMO = "DEMO"


@dataclass(frozen=True, slots=True)
class RouteWeight:
    """One route in the basket, with the provenance of its weight."""

    route_id: str
    origin: str
    destination: str
    weight: Decimal
    weight_source: str
    effective_date: date
    note: str = ""

    def __post_init__(self) -> None:
        for code, label in ((self.origin, "origin"), (self.destination, "destination")):
            if len(code) != 3 or not code.isupper():
                raise ValueError(f"{label} {code!r} must be a 3-letter uppercase IATA code")
        if self.origin == self.destination:
            raise ValueError(f"route {self.route_id!r} has origin == destination")
        if self.weight <= 0:
            raise ValueError(
                f"route {self.route_id!r} has weight {self.weight}; a zero or negative route "
                "weight is not a weight. Omit the route instead."
            )
        if not self.weight_source.strip():
            raise ValueError(
                f"route {self.route_id!r} has no weight_source. Spec G.2 weights move the "
                "national index; an unattributed weight is not usable."
            )

    @property
    def pair(self) -> str:
        """The canonical ``DEL-BOM`` form used as a route key elsewhere."""
        return f"{self.origin}-{self.destination}"


@dataclass(frozen=True, slots=True)
class RouteBasket:
    """A versioned set of weighted routes.

    Weights are normalised to sum to one on construction, because spec G.5
    requires it and because a basket that does not sum to one silently rescales
    the index.
    """

    basket_version: str
    methodology_version: str
    status: BasketStatus
    effective_date: date
    routes: tuple[RouteWeight, ...]
    authority: str
    caveat: str = ""
    _normalised: tuple[Decimal, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        if not self.routes:
            raise ValueError(f"basket {self.basket_version!r} is empty")
        ids = [r.route_id for r in self.routes]
        if len(ids) != len(set(ids)):
            raise ValueError(f"basket {self.basket_version!r} repeats a route_id")
        if self.status is not BasketStatus.OFFICIAL and not self.caveat.strip():
            raise ValueError(
                f"basket {self.basket_version!r} is {self.status.value} and carries no caveat. "
                "A non-official basket must say so in words, not only in an enum."
            )

    @property
    def normalised_weights(self) -> dict[str, Decimal]:
        """Route id to weight, renormalised to sum to exactly one — spec G.5."""
        total = sum(r.weight for r in self.routes)
        return {r.route_id: r.weight / total for r in self.routes}

    @property
    def is_publication_grade(self) -> bool:
        """Whether these weights may inform a published national index.

        False for anything but ``OFFICIAL``. The publication layer asks this
        rather than inspecting the status itself, so the rule lives in one place.
        """
        return self.status is BasketStatus.OFFICIAL

    def route(self, route_id: str) -> RouteWeight:
        for r in self.routes:
            if r.route_id == route_id:
                return r
        raise KeyError(f"route {route_id!r} is not in basket {self.basket_version!r}")

    def as_dict(self) -> dict[str, object]:
        weights = self.normalised_weights
        return {
            "basket_version": self.basket_version,
            "methodology_version": self.methodology_version,
            "status": self.status.value,
            "is_publication_grade": self.is_publication_grade,
            "effective_date": self.effective_date.isoformat(),
            "authority": self.authority,
            "caveat": self.caveat,
            "route_count": len(self.routes),
            "routes": [
                {
                    "route_id": r.route_id,
                    "origin": r.origin,
                    "destination": r.destination,
                    "pair": r.pair,
                    "weight_declared": str(r.weight),
                    "weight_normalised": str(weights[r.route_id]),
                    "weight_source": r.weight_source,
                    "effective_date": r.effective_date.isoformat(),
                    "note": r.note,
                }
                for r in self.routes
            ],
        }


_OQ4 = (
    "PROVISIONAL, pending OQ-4. Not derived from DGCA passenger traffic. The DGCA city-pair "
    "table is located but its primary XLSX has never been downloaded and column-verified, so "
    "no traffic-derived weight exists. This weight must NOT be presented as official."
)

#: The route APIx has actually measured. One route, so its weight is 1 by
#: arithmetic rather than by choice — which is the only reason it is safe.
PILOT_BASKET = RouteBasket(
    basket_version="pilot-2026Q3",
    methodology_version="2.1",
    status=BasketStatus.PROVISIONAL,
    effective_date=date(2026, 9, 12),
    authority="The 2026-09-12 Day-1 collection contract (ADR-0065)",
    caveat=(
        "One route. Its weight is 1.0 by arithmetic, not by a weighting decision -- with a "
        "single route any allocation rule gives the same answer, exactly as the single-carrier "
        "case does for AMB-9. This basket establishes NO national representativeness."
    ),
    routes=(
        RouteWeight(
            route_id="DEL-BOM",
            origin="DEL",
            destination="BOM",
            weight=Decimal("1"),
            weight_source="Sole route in the frozen Day-1 contract; weight is degenerate at n=1",
            effective_date=date(2026, 9, 12),
            note="The 35 real observations are all on this route.",
        ),
    ),
)

#: The six city-pairs PS 26056 names, to exercise multi-route code paths.
#: Equal weights, declared as a placeholder. NOT a claim about the market.
DEMO_BASKET = RouteBasket(
    basket_version="demo-ps26056",
    methodology_version="2.1",
    status=BasketStatus.DEMO,
    effective_date=date(2026, 9, 15),
    authority="City-pairs named in PS 26056; weights are NOT from PS 26056",
    caveat=(
        "DEMO ONLY. These are the city-pairs the problem statement lists as examples, with "
        "EQUAL weights because APIx holds no DGCA traffic data (OQ-4). Equal weighting is a "
        "placeholder, not a finding: it asserts every sector contributes equally to household "
        "airfare expenditure, which is false and unmeasured. Exists to exercise multi-route "
        "aggregation, the heatmap and the API. It must never inform a published index, and "
        "is_publication_grade returns False."
    ),
    routes=tuple(
        RouteWeight(
            route_id=f"{o}-{d}",
            origin=o,
            destination=d,
            weight=Decimal("1"),
            weight_source="EQUAL PLACEHOLDER — no traffic data held",
            effective_date=date(2026, 9, 15),
            note=_OQ4,
        )
        for o, d in (
            ("DEL", "BOM"),
            ("DEL", "BLR"),
            ("BOM", "BLR"),
            ("DEL", "CCU"),
            ("BLR", "HYD"),
            ("MAA", "DEL"),
        )
    ),
)

_BASKETS = {b.basket_version: b for b in (PILOT_BASKET, DEMO_BASKET)}


def basket(basket_version: str) -> RouteBasket:
    """Look up a declared basket. Unknown versions raise rather than default."""
    try:
        return _BASKETS[basket_version]
    except KeyError:
        raise KeyError(
            f"unknown basket {basket_version!r}; declared baskets are {sorted(_BASKETS)}"
        ) from None


def declared_baskets() -> tuple[RouteBasket, ...]:
    return (PILOT_BASKET, DEMO_BASKET)


__all__ = [
    "DEMO_BASKET",
    "PILOT_BASKET",
    "BasketStatus",
    "RouteBasket",
    "RouteWeight",
    "basket",
    "declared_baskets",
]
