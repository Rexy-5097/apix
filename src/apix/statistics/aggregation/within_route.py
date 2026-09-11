"""Within-route weights ``v[c|r]`` — spec G.3, G.4, G.5.

$$v_{c\\mid r} = \\alpha_{apw} \\times \\beta_{fare\\_class\\mid r}
                 \\times \\delta_{channel\\mid r} \\Big/ \\text{normaliser}$$

**This module exists to make one omission impossible to commit by accident.**

The cell key has six dimensions (spec B.2.1); spec G.3's formula has terms for
three. The two absent dimensions are not equivalent, and the methodology treats
them differently:

``day_of_week`` — **RESOLVED, and deliberately omitted.** Methodology v2.1 §C.2
    states it: *"Because it is determined, it is not an independent weight
    dimension — §G.3 correctly omits it."* At a fixed ``(t, apw_bucket)`` the
    travel date and therefore the weekday are determined, so the weekday adds no
    observations and partitions nothing within a collection date. It carries no
    weight factor, and with spec G.5's ``Σv = 1`` the seven weekday variants of
    one ``(apw, fare_class, channel)`` group therefore divide that group's weight
    equally. **This module implements that, and it is a derivation, not a
    choice.**

``carrier`` — **OPEN. AMB-9.** Nothing in v2.0 or v2.1 says whether cells
    differing only by carrier carry equal weight. The omission is *unexplained*,
    unlike the weekday's, and the dimension is not determined: spec M.2
    conditions APIx-TPD on carrier precisely because it is price-determining.
    Allocating it uniformly would weight a carrier holding roughly 60% of a
    route's passengers identically to one holding 3% — a substantive choice with
    an unmeasured bias, and one no frozen text authorises.

So this module **refuses to guess**. A route carrying more than one carrier
requires ``carrier_shares`` to be declared by the caller. There is no default,
no fallback and no "reasonable" uniform assumption inserted quietly on the
publication path.

Two ways to satisfy it, both explicit:

* declare measured shares, recorded in ``weight_version``; or
* declare uniform shares *as a stated v1 choice* with a published sensitivity
  band, exactly the pattern spec G.4 already uses for ``alpha`` under OQ-7. That is
  the owner's ruling to make and to write down — not this module's.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum

from apix.schemas.enums import Channel, FareClass
from apix.schemas.keys import CellKey
from apix.statistics.aggregation.weights import EQUAL_APW_WEIGHT, WeightError, normalise


class CarrierAllocationBasis(Enum):
    """On what evidence a carrier allocation rests — AMB-9.

    The basis is recorded because the three are not interchangeable and a
    consumer of the index needs to know which one produced the weights.
    """

    #: Measured passenger shares per carrier on this route. **No official source
    #: is known to exist**: DGCA publishes city-pair traffic and carrier traffic
    #: as two separate, uncrossed tables, so a carrier's share OF A GIVEN ROUTE
    #: cannot be read from them.
    MEASURED_TRAFFIC = "MEASURED_TRAFFIC"
    #: Scheduled seat capacity per carrier per route, from published schedules.
    #: Spec G.2's declared fallback pattern — *"a proxy for passenger volume
    #: with a stated and testable bias"*. Constructible IF the DGCA schedule
    #: yields per-flight frequency and aircraft type. Currently unretrieved.
    CAPACITY_PROXY = "CAPACITY_PROXY"
    #: Equal weight per carrier, as a **declared, documented choice** with a
    #: published sensitivity band. This is spec G.4's own pattern for alpha
    #: under OQ-7: *"equal weights across APW buckets as a declared, documented
    #: choice, accompanied by a sensitivity analysis"*. Legitimate only WITH the
    #: band — see :class:`CarrierAllocation`.
    DECLARED_UNIFORM = "DECLARED_UNIFORM"


@dataclass(frozen=True, slots=True)
class CarrierAllocation:
    """A ratified rule for allocating ``v[c|r]`` across carriers — AMB-9.

    **This type is the seam, and it is deliberately hard to fill in.** Spec G.3
    defines no carrier term, so any allocation is a methodology decision the
    owner must make. Making it a versioned object rather than a loose mapping
    means a ratified rule drops into the pipeline without redesign, and an
    *unratified* one cannot drop in by accident.

    Two constraints are enforced rather than documented:

    1. **Ratification is required.** ``ratified_by`` and ``ratified_date`` must
       both be present. A weight vector with no owner behind it is an invention.
    2. **A uniform declaration requires its sensitivity band.** Spec G.4's
       precedent is equal weights *"accompanied by a sensitivity analysis
       showing how far the index moves under plausible alternative curves"*.
       Equal weights without the band is not the G.4 pattern — it is the guess
       the pattern exists to replace, and it would weight a carrier holding
       ~60% of a route's passengers identically to one holding 3%.

    ``shares`` need not sum to 1; it is normalised with everything else.
    """

    version: str
    basis: CarrierAllocationBasis
    shares: Mapping[str, float]
    ratified_by: str
    ratified_date: date
    #: Required when ``basis`` is DECLARED_UNIFORM. Identifies the published
    #: sensitivity analysis, per the spec G.4 pattern.
    sensitivity_band_ref: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.version:
            raise WeightError("carrier allocation must carry a version")
        if not self.ratified_by or not self.ratified_date:
            raise WeightError(
                f"carrier allocation {self.version!r} is not ratified. AMB-9 is an open "
                "methodology question and spec G.3 defines no carrier term, so an "
                "allocation without a named owner and date is an invention, not a rule"
            )
        if not self.shares:
            raise WeightError(f"carrier allocation {self.version!r} declares no shares")
        bad = sorted(k for k, v in self.shares.items() if v < 0 or v != v)
        if bad:
            raise WeightError(f"carrier shares must be finite and >= 0; bad: {bad}")
        if self.basis is CarrierAllocationBasis.DECLARED_UNIFORM and not self.sensitivity_band_ref:
            raise WeightError(
                f"carrier allocation {self.version!r} declares uniform weights with no "
                "sensitivity_band_ref. Spec G.4's precedent for an unavailable weight is "
                "equal weights as a declared choice ACCOMPANIED BY a published sensitivity "
                "band; without the band this is the guess that pattern exists to replace"
            )

    def share_for(self, carrier: str) -> float:
        """The declared share for one carrier.

        Raises rather than defaulting: a carrier absent from a ratified
        allocation is outside the rule's scope, and silently giving it zero
        would drop it from the index without saying so.
        """
        try:
            return self.shares[carrier]
        except KeyError:
            raise WeightError(
                f"carrier {carrier!r} has no share in ratified allocation "
                f"{self.version!r} (AMB-9); the allocation covers "
                f"{sorted(self.shares)}"
            ) from None


def _cell_id(cell: CellKey) -> str:
    """Match :func:`apix.statistics.index.apix_l.cell_id` without importing it.

    Duplicated deliberately: the weight layer must not depend on the index
    layer, and the join is one line whose agreement is asserted by
    ``tests/test_v2_1_invariants.py``.
    """
    return "|".join(str(part) for part in cell.sort_key)


def within_route_weights(
    cells: Sequence[CellKey],
    *,
    fare_class_shares: Mapping[FareClass, float],
    channel_shares: Mapping[Channel, float],
    carrier_allocation: CarrierAllocation | None = None,
) -> dict[str, float]:
    """Build ``v[c|r]`` for one route's cells — spec G.3.

    Args:
        cells: Every cell in the route's basket, suppressed ones included. Spec
            F.4 renormalises over the live set at publication time, so the
            vector built here is the *full* one.
        fare_class_shares: ``β``, observed composition shares in the weight
            reference period, held fixed for the index year (spec G.3, LOCKED).
        channel_shares: ``δ``, on the same basis.
        carrier_allocation: A **ratified** :class:`CarrierAllocation`.
            **Required whenever the route carries more than one carrier**,
            because spec G.3 defines no carrier term and the allocation is an
            open methodology question (AMB-9).

            A single-carrier route needs none: with one carrier there is no
            allocation to make, which is why the Checkpoint 2G empirical frame
            can run before AMB-9 is ruled on.

    Returns:
        ``v[c|r]`` keyed by cell id, summing to 1 (spec G.5, INV-1), in sorted
        key order so the reduction is bit-stable (spec P.2).

    Raises:
        WeightError: if ``cells`` is empty; if the cells span more than one
            route; if a fare class or channel present in the cells has no
            declared share; if the route carries several carriers and
            ``carrier_allocation`` is absent or does not cover them; or if the
            resulting vector is degenerate.

    ``alpha`` is spec G.4's LOCKED ``1/7`` per APW bucket — a declared v1 choice
    published with a sensitivity band, pending OQ-7. It is not measured and this
    module does not pretend otherwise.
    """
    if not cells:
        raise WeightError("no cells given; a route with no basket has no weight vector")

    routes = sorted({c.route for c in cells})
    if len(routes) > 1:
        raise WeightError(
            f"within-route weights are per route, but cells span {routes}; "
            "spec G.3 normalises v[c|r] inside one route"
        )

    carriers = sorted({c.carrier for c in cells})
    if len(carriers) > 1 and carrier_allocation is None:
        raise WeightError(
            f"route {routes[0]} carries {len(carriers)} carriers {carriers} and no "
            "ratified carrier_allocation was supplied. Spec G.3 defines v[c|r] as "
            "alpha_apw x beta_fare_class x delta_channel and has no carrier term, "
            "so the allocation across carriers is undetermined by the frozen "
            "methodology (AMB-9). Supply a ratified CarrierAllocation — measured "
            "shares, a capacity proxy, or uniform as a stated choice with a "
            "published sensitivity band per the spec G.4 pattern. It is never "
            "inserted silently here."
        )

    missing_fare = sorted(
        {c.fare_class.value for c in cells if c.fare_class not in fare_class_shares}
    )
    if missing_fare:
        raise WeightError(f"no beta (fare-class share) declared for {missing_fare} (spec G.3)")

    missing_channel = sorted({c.channel.value for c in cells if c.channel not in channel_shares})
    if missing_channel:
        raise WeightError(f"no delta (channel share) declared for {missing_channel} (spec G.3)")

    if carrier_allocation is not None:
        missing_carrier = sorted(c for c in carriers if c not in carrier_allocation.shares)
        if missing_carrier:
            raise WeightError(
                f"ratified allocation {carrier_allocation.version!r} has no share for "
                f"{missing_carrier} (AMB-9); it covers "
                f"{sorted(carrier_allocation.shares)}"
            )

    raw: dict[str, float] = {}
    for cell in sorted(cells, key=lambda c: c.sort_key):
        # alpha x beta x delta, per spec G.3. No day_of_week factor — v2.1 §C.2
        # rules it is not an independent weight dimension, so the seven weekday
        # variants of one (apw, fare_class, channel) group receive identical raw
        # weight and normalisation divides the group's share equally among them.
        weight = (
            EQUAL_APW_WEIGHT * fare_class_shares[cell.fare_class] * channel_shares[cell.channel]
        )
        if carrier_allocation is not None:
            weight *= carrier_allocation.share_for(cell.carrier)
        raw[_cell_id(cell)] = weight

    return normalise(raw)


__all__ = [
    "CarrierAllocation",
    "CarrierAllocationBasis",
    "WeightError",
    "within_route_weights",
]
