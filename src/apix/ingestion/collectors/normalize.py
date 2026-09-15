"""Selected flight + contract fare -> the existing canonical records.

The automated path produces **the same** :class:`~apix.schemas.observation.Observation`
and :class:`~apix.ingestion.store.UnpricedFlight` the manual loader produces.
There is no automation-specific observation type, so the statistics layer needs
no special path for it.

What distinguishes an automated observation is recorded where the store already
records provenance -- the run's ``collector_identity``, ``collector_version`` and
``parser_version`` -- and, for fixture runs, ``source_type=SYNTHETIC``. It is
never encoded by relabelling a manual observation.

Ids follow the Day-1 shape so waves are directly comparable::

    {collection_date}-{frame_tag}-{source_id}-{carrier}{flight}-{travel_date}-{fare_family_raw}
"""

from __future__ import annotations

from datetime import datetime

from apix.ingestion.collectors.contract import SearchParams
from apix.ingestion.collectors.fares import FareDecision, FareStatus
from apix.ingestion.store import UnpricedFlight
from apix.schemas.enums import Availability, Channel, SourceType
from apix.schemas.observation import Entitlements, Observation


def record_id(
    params: SearchParams, frame_tag: str, carrier: str, flight_number: str, family: str
) -> str:
    return (
        f"{params.collection_date:%Y%m%d}-{frame_tag}-{params.source_id}-"
        f"{carrier}{flight_number}-{params.travel_date:%Y%m%d}-{family}"
    )


def to_observation(
    decision: FareDecision,
    params: SearchParams,
    *,
    frame_tag: str,
    source_type: SourceType,
    observed_at: datetime,
) -> Observation:
    """Build the canonical observation for a PRICED decision."""
    if decision.status is not FareStatus.PRICED or decision.option is None:
        raise ValueError(f"only a PRICED decision becomes an observation, got {decision.status}")
    c, o = decision.candidate, decision.option
    # Eligibility and the fare decision guarantee every one of these is present.
    assert c.marketing_carrier and c.flight_number and c.departure_time
    assert c.origin and c.destination and c.stops is not None
    assert c.duration_minutes is not None and o.payable_fare is not None
    assert o.checked_baggage_kg is not None and o.change_policy and o.cancellation_policy
    return Observation(
        observation_id=record_id(
            params, frame_tag, c.marketing_carrier, c.flight_number, o.family_label
        ),
        origin=c.origin,
        destination=c.destination,
        travel_date=params.travel_date,
        departure_time_local=c.departure_time,
        observation_ts=observed_at,
        collection_date=params.collection_date,
        carrier=c.marketing_carrier,
        flight_number=c.flight_number,
        stops=c.stops,
        duration_minutes=c.duration_minutes,
        fare_family_raw=o.family_label,
        channel=Channel.AIRLINE_DIRECT,
        source_id=params.source_id,
        entitlements=Entitlements(
            checked_baggage_kg=o.checked_baggage_kg,
            change_permitted=o.change_policy,
            cancellation_permitted=o.cancellation_policy,
        ),
        payable_fare=o.payable_fare,
        source_type=source_type,
        availability=Availability.AVAILABLE,
        # Ungrouped, never assumed independent -- spec B.6, as the manual loader.
        source_group=None,
        fare_breakdown=o.breakdown,
    )


def to_unpriced(
    decision: FareDecision,
    params: SearchParams,
    *,
    frame_tag: str,
    run_id: str,
    attempt_id: str,
    observed_at: datetime,
) -> UnpricedFlight:
    """Build the unpriced-flight record for a SOLD_OUT decision -- spec D.6."""
    if decision.status is not FareStatus.SOLD_OUT:
        raise ValueError(
            f"only a SOLD_OUT decision becomes an unpriced flight, got {decision.status}"
        )
    c = decision.candidate
    assert c.marketing_carrier and c.flight_number and c.departure_time
    assert c.origin and c.destination
    family = decision.option.family_label if decision.option else params.contract.fare_family
    return UnpricedFlight(
        unpriced_id=record_id(params, frame_tag, c.marketing_carrier, c.flight_number, family),
        run_id=run_id,
        attempt_id=attempt_id,
        collection_date=params.collection_date,
        origin=c.origin,
        destination=c.destination,
        travel_date=params.travel_date,
        carrier=c.marketing_carrier,
        flight_number=c.flight_number,
        departure_time_local=c.departure_time,
        observation_ts=observed_at,
        source_id=params.source_id,
        availability=Availability.SOLD_OUT,
        detail=decision.detail,
    )


__all__ = ["record_id", "to_observation", "to_unpriced"]
