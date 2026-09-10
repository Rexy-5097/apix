"""The parent object — spec E.6, E.7 (methodology v2.1).

The parent supplies two quantities, and **they are different statistical objects
computed in opposite directions from different inputs**:

.. code-block:: text

    J(P,t)  parent fallback relative   Jevons over M(P,t)   BOTTOM-UP from raw
                                                            observations
                                       -> used by spec E.4 carry ONLY

    I(P,t)  parent reference level     weighted mean over    TOP-DOWN from child
                                       the independent-live  levels
                                       set
                                       -> used by spec J.1 entry ONLY

.. warning::

   ``I(P,t) = I(P,t-7) * J(P,t)`` is **FORBIDDEN**.

   The parent is not a chained index: it has no base period, no ``t0`` and no
   history of its own. Writing that equation would create two competing
   definitions of the parent level — one chained, one aggregated — which would
   diverge immediately and silently, and would make new-cell entry depend on a
   shadow series nothing else in the specification maintains. Any future decision
   to give the parent an independently chained level is a new methodology
   version, requiring its own ADR, amendment and audit.

This mirrors spec C.4 one level up: the construction is relative at the
elementary level and level at every level above it, and conflating the two is the
most common way it goes wrong.

The parent is a **computation stratum, never a publication stratum**. It carries
no weight, contributes no level to any aggregate, and is never published as an
index.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date

from apix.schemas.enums import Tier
from apix.schemas.keys import CellKey, ItemKey, ParentKey
from apix.schemas.observation import Observation
from apix.schemas.results import CellState, ParentRelativeResult
from apix.statistics.aggregation.weights import renormalise_over_live_set
from apix.statistics.elementary.jevons import compute_jevons
from apix.statistics.elementary.matching import build_matched_set, parent_key_for
from apix.statistics.elementary.sources import SourcePrecedence

__all__ = ["compute_parent_relative", "parent_key_for", "parent_level"]


def compute_parent_relative(
    observations_t: Iterable[Observation],
    observations_t_minus_7: Iterable[Observation],
    parent: ParentKey,
    tier: Tier,
    collection_date: date,
    *,
    source_precedence: SourcePrecedence,
    previous_selection: Mapping[ItemKey, str] | None = None,
) -> ParentRelativeResult:
    """``J(P,t)`` — the parent's own Jevons over its own matched items — spec E.6.

    The item definition is **identical** to the cell's (spec E.6.2); only the
    stratum over which items are pooled differs. Keeping one item definition is
    what makes a carried relative arithmetically comparable to a computed one.

    Because the parent pools carriers, the item key's ``carrier`` field is
    load-bearing here — without it ``6E101`` and ``AI101`` would collide.

    The matched set is built from **observations**, so items belonging to child
    cells that were themselves suppressed, carried or withheld still contribute.
    Building the parent from cell results would make the carry depend on the very
    failure it exists to repair.

    ``min_matched_items_per_cell`` applies unchanged — the same threshold, on a
    new object. No parent-specific value is invented.

    **Carrier mix is implicitly count-weighted, and that is disclosed rather than
    hidden.** ``J(P,t)`` weights each carrier in proportion to its count of
    matched items, and that count drifts week to week. This is the channel
    through which carrier-mix contamination re-enters a design that fixes carrier
    inside computing cells. ``carrier_count`` and ``carrier_concentration`` on
    the result exist to make the exposure measurable; whether either should
    become a rule is OQ-A8.
    """
    matched = build_matched_set(
        observations_t,
        observations_t_minus_7,
        parent,
        tier,
        source_precedence=source_precedence,
        previous_selection=previous_selection,
    )
    jevons = compute_jevons(parent, collection_date, matched.pairs)

    counts: dict[str, int] = {}
    for pair in matched.pairs:
        counts[pair.item.carrier] = counts.get(pair.item.carrier, 0) + 1
    total = sum(counts.values())
    concentration = (max(counts.values()) / total) if total else 0.0

    return ParentRelativeResult(
        parent=parent,
        tier=tier,
        jevons=jevons,
        matched_set=matched,
        carrier_count=len(counts),
        carrier_concentration=concentration,
    )


def independent_live_set(
    states: Sequence[CellState],
    entered_at_t: Iterable[CellKey],
) -> tuple[CellState, ...]:
    """Children whose level at *t* is determined without reference to ``I(P,t)``.

    Exactly one class is excluded: cells that **entered at *t* under spec J.1
    against this parent**, whose level *is* ``I(P,t)`` by construction. Including
    them would put ``I(P,t)`` on both sides of its own definition.

    **Carried children are NOT excluded.** A carry is
    ``I(c,t) = I(c,t-7) * J(P,t)``: it depends on the parent's *relative*,
    computed bottom-up from raw observations, and not on ``I(P,t)``. No recursion
    is created. Excluding carries would discard well-determined levels and, on
    thin routes where carry is normal, could empty this set almost always —
    converting a definitional safeguard into a systematic hold-out.

    The recursion is broken independently at every period: a cell that entered at
    ``t-7`` was excluded from ``I(P,t-7)`` *then*, and its level at *t* is
    ``I(P,t-7) * J(P,t)``, which references no current-period parent level. No
    recursion, direct or transitive, can arise.
    """
    excluded = set(entered_at_t)
    return tuple(
        state
        for state in sorted(states, key=lambda s: s.cell.sort_key)
        if state.is_live and state.cell not in excluded
    )


def parent_level(
    states: Sequence[CellState],
    cell_weights: Mapping[CellKey, float],
    *,
    entered_at_t: Iterable[CellKey] = (),
) -> float | None:
    """``I(P,t)`` — the parent's reference level — spec E.7.

    The weighted mean of the parent's **independent-live** child levels, with
    within-parent weights renormalised over that set exactly as spec F.4
    prescribes.

    Returns:
        The level, or **None** when the independent-live set is empty. None is a
        real answer: it means new-cell entry is impossible this period, so a
        candidate cell is *held out* per spec J.2 — a different quality event
        from suppression, since a suppressed cell was live and breached a
        threshold while a held-out cell was never live. Carries are unaffected,
        because they need ``J(P,t)`` rather than ``I(P,t)``.

    No fixed-point iteration is performed, and none is permissible: solving the
    recursion would let a new cell's own weight influence the level it enters at,
    which is precisely the spurious contribution spec J.1 exists to prevent.
    """
    live = independent_live_set(states, entered_at_t)
    if not live:
        return None

    # Renormalisation is keyed by the cell's deterministic id string, because
    # spec F.4's helper works over a total order and a CellKey carries enums that
    # do not define one. The ids come from sort_key, so id order and key order
    # agree (spec P.2).
    raw = {_cid(state.cell): cell_weights.get(state.cell, 0.0) for state in live}
    if sum(raw.values()) <= 0.0:
        # Equal weighting is the only non-arbitrary fallback when the parent's
        # children carry no configured weight, and it is applied explicitly
        # rather than by dividing by zero. Declared, not silent.
        share = 1.0 / len(live)
        return sum(state.level * share for state in live if state.level is not None)

    weights = renormalise_over_live_set(raw, list(raw))
    total = 0.0
    for state in live:
        if state.level is None:  # pragma: no cover - is_live guarantees otherwise
            continue
        total += weights[_cid(state.cell)] * state.level
    return total


def _cid(cell: CellKey) -> str:
    """A stable, sortable id for a cell, derived from its ``sort_key``."""
    return "|".join(str(part) for part in cell.sort_key)
