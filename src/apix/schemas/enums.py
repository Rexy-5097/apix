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


class CollectionOutcome(Enum):
    """What happened on one collection attempt — spec H.1.

    **The distinction this enum exists to preserve.** Spec H.1 names five ways a
    quote can be absent, and only ONE of them means the cell was never expected:

    ==================  ==============================
    H.1 class           In the coverage denominator?
    ==================  ==============================
    No flight           **No** -- "cell not expected"
    Structural missing  Yes, then suppressed
    Technical missing   Yes, then carried (spec E.4)
    Unavailable source  Yes -- **our** failure
    Parser failure      Yes -- **our** failure
    ==================  ==============================

    A quote table records only successes, so in a quote table all five look
    identical: an empty result. **Missingness cannot be measured from a table of
    successes**, which is why every attempt gets a record whether or not it
    produced a fare.

    That distinction is exactly what **AMB-8** turns on. Without it, "no service
    was scheduled" and "the site blocked us" are the same absence, and the
    spec I coverage denominator stays undefined however long collection runs.
    """

    #: Quotes retrieved and parsed.
    SUCCESS = "SUCCESS"
    #: No service scheduled on that weekday/slot. Spec H.1: *"Cell not expected;
    #: excluded from denominators of coverage."* The ONLY outcome that leaves
    #: the denominator.
    NO_FLIGHT = "NO_FLIGHT"
    #: The product no longer exists -- route dropped, flight retired. Spec H.1:
    #: cell suppressed, **not** carried indefinitely.
    STRUCTURAL_MISSING = "STRUCTURAL_MISSING"
    #: Collection ran, source reachable, quote absent for a transient reason.
    #: Spec H.1: item excluded from M, cell-level carry per spec E.4.
    TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
    #: Source down, rate-limited, or circuit-breaker open. Spec H.1: *"source-day
    #: recorded as a retrieval failure. Never silently substituted from another
    #: channel."*
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    #: Page fetched, fields unextractable. Spec H.1: excluded with a reason code;
    #: *"counts toward the exclusion rate alarm."*
    PARSER_FAILURE = "PARSER_FAILURE"
    #: An access challenge was presented. **A stop signal, never an obstacle.**
    #: Recorded separately from SOURCE_UNAVAILABLE because it is a *policy*
    #: event with a compliance meaning, not a transient outage.
    CAPTCHA_OR_ANTIBOT_STOP = "CAPTCHA_OR_ANTIBOT_STOP"

    @property
    def excludes_cell_from_expectation(self) -> bool:
        """Whether this outcome removes the cell from the spec I denominator.

        True for ``NO_FLIGHT`` alone. Every other absence keeps the cell in the
        denominator, because the cell *was* expected and something went wrong --
        either in the market or in our collection.
        """
        return self is CollectionOutcome.NO_FLIGHT

    @property
    def is_collector_failure(self) -> bool:
        """Whether the absence is **ours**, not the market's.

        These must never be read as an absent fare. A blocked collector that
        silently became "no quote" would understate coverage loss and, worse,
        would look like a price signal.
        """
        return self in (
            CollectionOutcome.SOURCE_UNAVAILABLE,
            CollectionOutcome.PARSER_FAILURE,
            CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP,
        )

    @property
    def is_market_fact(self) -> bool:
        """Whether the absence says something true about the market."""
        return self in (
            CollectionOutcome.NO_FLIGHT,
            CollectionOutcome.STRUCTURAL_MISSING,
            CollectionOutcome.TECHNICAL_FAILURE,
        )

    @property
    def is_stop_signal(self) -> bool:
        """Whether the collector must back off rather than retry.

        An access challenge is a stop signal (CLAUDE.md, dossier section 05).
        There is no CAPTCHA solver, no fingerprint evasion and no identity
        rotation intended to defeat access controls. Retrying past this is
        prohibited, not merely discouraged.
        """
        return self is CollectionOutcome.CAPTCHA_OR_ANTIBOT_STOP
