"""Source precedence and source transitions — spec D.8 (PROVISIONAL).

v2.0 defined no rule for reconciling several sources quoting the same item
inside one cell, so the implementation fell back to dictionary insertion order —
an arbitrary, undeclared rule. That is the one outcome unacceptable under any
resolution, and this module replaces it.

The rule, and the six properties it must have (spec D.8.2):

**Deterministic**
    an explicit total order, never dictionary or arrival order.

**Price-blind**
    selection never inspects the fare. No minimum, median or mean is taken, so
    the rule *cannot* bias the level by construction.

**Same-source-paired**
    the fare is taken from the highest-ranked source present in **both** *t* and
    *t-7*. Both legs of every relative therefore come from one source, and a
    cross-source ratio — a carrier-direct fare divided by an aggregator fare —
    is impossible.

**Versioned**
    ``SourcePrecedence.version`` is recorded in the version vector beside
    ``weight_version``.

**Auditable**
    the winning ``source_id`` is stored on each matched pair.

**Reversible**
    changing the list is a version-vector change, visible in every vintage.

**What the transition rule is actually for.** Same-source pairing already makes a
cross-source comparison impossible, and this module does not claim otherwise.
The exposure it guards is subtler: when the *selected* source changes between
consecutive links, the item's series is **spliced across two price bases**. Each
relative stays clean, but the chained level becomes A-based relatives followed by
B-based relatives, and if the two sources' fee structures drift differently the
cell's movement changes character with no disclosure at the point of change.
Excluding the transition link makes that splice explicit and countable rather
than silent.

**Cost, disclosed:** the rule withholds items exactly when source coverage is
weakest, which can push a thin cell below spec D.3 and increase carry. Its
frequency is unknown and is OQ-A9.

The permanent reconciliation *statistic* is deliberately **not** frozen. Median
across independent source groups is the leading v2.2 candidate and must be chosen
against measured spread (OQ-A2).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from apix.schemas.enums import Channel

#: Sort position for a source not named in the configured order. Unknown sources
#: rank after every known one and are ordered lexicographically among
#: themselves — deterministic, and still price-blind.
_UNKNOWN = 1 << 30


@dataclass(frozen=True, slots=True)
class SourcePrecedence:
    """An ordered, versioned source list per channel — spec D.8.1.

    Args:
        version: Identifier recorded in the version vector (spec O). Changing
            the order without changing this is a reproducibility defect.
        order: Per channel, the source ids in descending priority.

    A channel with no configured order is legal: every source in it is treated
    as unknown and ranked lexicographically, which is still deterministic and
    price-blind. It is, however, an undeclared choice, so callers that care
    should configure the channel explicitly.
    """

    version: str
    order: Mapping[Channel, tuple[str, ...]] = field(default_factory=dict)

    def rank(self, channel: Channel, source_id: str) -> tuple[int, str]:
        """Sort position of a source within a channel. Lower wins.

        Returns a tuple rather than an int so unknown sources have a total order
        among themselves without colliding.
        """
        configured = self.order.get(channel, ())
        if source_id in configured:
            return (configured.index(source_id), "")
        return (_UNKNOWN, source_id)

    def select(
        self,
        channel: Channel,
        sources_t: Iterable[str],
        sources_t_minus_7: Iterable[str],
    ) -> str | None:
        """The highest-ranked source present in **both** periods — spec D.8.1.

        Returns None when no source is present in both. That is not an error: the
        item is then **unmatched** and enters neither side of the ratio (spec
        D.1), which is the correct outcome — pairing across sources would compare
        two different price concepts.

        The fare is never consulted.
        """
        both = set(sources_t) & set(sources_t_minus_7)
        if not both:
            return None
        return min(sorted(both), key=lambda s: self.rank(channel, s))
