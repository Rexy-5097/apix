"""Closed vocabularies from the frozen specification.

Every enum here is LOCKED for `methodology_version 2.0`. Adding or removing a
member is a methodology change requiring an ADR and a version bump — not a code
change. See `docs/methodology/apix_formula_spec_v1.md`.
"""

from __future__ import annotations

from enum import Enum


class APWBucket(Enum):
    """Advance-purchase window buckets — spec A.3.

    Assignment is by **exact** ``lead_time_days`` equal to the bucket value. A
    quote whose lead time matches no bucket is not admissible for the index; it
    is stored and excluded.
    """

    T_PLUS_1 = 1
    T_PLUS_3 = 3
    T_PLUS_7 = 7
    T_PLUS_15 = 15
    T_PLUS_30 = 30
    T_PLUS_45 = 45
    T_PLUS_60 = 60

    @classmethod
    def from_lead_time(cls, lead_time_days: int) -> APWBucket | None:
        """Return the bucket for an exact lead time, or None if it matches none.

        None is a real answer, not an error: spec A.3 makes a non-matching lead
        time inadmissible rather than assigning it to the nearest bucket.
        """
        for bucket in cls:
            if bucket.value == lead_time_days:
                return bucket
        return None


class FareClass(Enum):
    """Canonical fare class — spec B.4.

    Derived from **entitlements, not labels**. One carrier's *saver* is
    another's *lite*; mapping by name is how an index quietly starts comparing a
    hand-baggage-only fare to a flexible one.
    """

    HAND_ONLY = "HAND_ONLY"
    STANDARD = "STANDARD"
    FLEX = "FLEX"


class ChangePolicy(Enum):
    """Change / cancellation entitlement — spec B.4."""

    NONE = "NONE"
    FEE = "FEE"
    FREE = "FREE"


class Channel(Enum):
    """Collection channel — spec A.2, B.5.

    Part of the cell key. An elementary cell never mixes channels, because
    averaging a carrier-direct fare with an aggregator fare that includes a
    convenience charge produces a number that is not the price of anything.
    """

    AIRLINE_DIRECT = "AIRLINE_DIRECT"
    AGGREGATOR = "AGGREGATOR"
    LICENSED_FEED = "LICENSED_FEED"
    DECLARED_TARIFF = "DECLARED_TARIFF"


class SourceType(Enum):
    """Provenance of a record — spec A.2, H.3.

    Never blended silently. `AUTHORIZED_FEED` and `BACKFILLED` values are never
    substituted for a `LIVE_SCRAPE` observation being claimed.
    """

    LIVE_SCRAPE = "LIVE_SCRAPE"
    AUTHORIZED_FEED = "AUTHORIZED_FEED"
    PUBLIC_DATASET = "PUBLIC_DATASET"
    BACKFILLED = "BACKFILLED"
    SYNTHETIC = "SYNTHETIC"


class Tier(Enum):
    """Matched-item tier — spec B.2.

    Selected per route by identity stability, and recorded per cell in the
    version vector. Tier 3 is never used silently.
    """

    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class Availability(Enum):
    """Whether a seat could be bought — spec D.6, H.1.

    ``SOLD_OUT`` exists as its own state because **a sold-out flight is not a
    missing price; it is a disappeared item**. Collapsing it into "missing"
    would let an ordinary-missing rule apply to it.
    """

    AVAILABLE = "AVAILABLE"
    SOLD_OUT = "SOLD_OUT"


class ExclusionReason(Enum):
    """Why an observation was excluded — spec A.6, D.4, D.7, H.1.

    Every exclusion is recorded rather than silently dropped: exclusion rate is
    published per source, and a rising rate is the earliest available signal
    that a site has been redesigned.
    """

    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    UNDETERMINABLE_ENTITLEMENTS = "UNDETERMINABLE_ENTITLEMENTS"
    LEAD_TIME_MATCHES_NO_BUCKET = "LEAD_TIME_MATCHES_NO_BUCKET"
    OUTSIDE_COLLECTION_WINDOW = "OUTSIDE_COLLECTION_WINDOW"
    DUPLICATE = "DUPLICATE"
    OUTLIER_FLAGGED = "OUTLIER_FLAGGED"
    SOLD_OUT = "SOLD_OUT"
    NON_POSITIVE_FARE = "NON_POSITIVE_FARE"
    UNMATCHED = "UNMATCHED"


class CellStatus(Enum):
    """Publication state of a cell — spec I.1."""

    PUBLISHED = "PUBLISHED"
    CARRIED = "CARRIED"
    SUPPRESSED = "SUPPRESSED"
    ENTERED = "ENTERED"
    HELD_OUT = "HELD_OUT"


class UndefinedRelativeReason(Enum):
    """Why J(c,t) is undefined — spec D.3, E.4.

    A distinct reason, never a silent substitution of 1.0. A relative of 1.0
    asserts "the price did not move"; undefined asserts "we cannot say".
    """

    NO_MATCHED_ITEMS = "NO_MATCHED_ITEMS"
    BELOW_MIN_MATCHED_ITEMS = "BELOW_MIN_MATCHED_ITEMS"
    NO_PRIOR_PERIOD = "NO_PRIOR_PERIOD"
