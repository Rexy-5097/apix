"""As-of publication of the daily live set — spec C.1, C.2, C.3, F.2.

**This module closes AMB-7.** The frozen methodology defines a daily estimand:

    APIx is a weekly-matched index published on a rolling daily basis, not a
    daily-matched one.                                              — spec C.1

    The daily series is an aggregate over seven interleaved weekday chains,
    each contributing its most recent level.                        — spec C.2

Every cell advances on its own seven-day chain (spec E.2), and under spec A.3's
exact lead-time assignment the seven APW buckets fall on only **five** distinct
weekday offsets, so at most five of the seven chains can hold an observation on
any single collection date. At least two must therefore contribute a level from
an earlier link. Spec C.2 is unsatisfiable otherwise, and spec C.3 measures
freshness *at the publication date* with a normal range of ``[0, 6]`` — a range
reachable only when a chain contributes between its links.

What was missing was not a rule. It was a **layer**:

    link day        chaining.advance_cell   ← "one cell by one weekly link"
                            │
                            ▼
    (nothing existed here)  ← latest state per CellKey, as-of the publication
                              date, freshness-checked
                            ▼
    publication     apix_l.calculate_apix_l ← weighted mean of cell LEVELS

`advance_cell` was already correct and already link-scoped. `calculate_apix_l`
was already correct and differences nothing. Between them, nothing assembled the
live set at a publication date from states produced on different link dates, and
an equality assertion stood in its place.

**The rule this module must never break (spec C.4, E.2).** A cell that does not
link on ``t`` contributes its most recent level **repeated, never multiplied**.
``J(c,t)`` is a *seven-day* relative; multiplying it on each of seven days
compounds it sevenfold — a 1% weekly move becomes 7.2%. That is why roll-forward
is a *selection* here and never a call into :func:`~apix.statistics.index.chaining.advance_cell`.
This module contains no multiplication of any kind.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date

from apix.schemas.enums import CellStatus, Tier
from apix.schemas.results import ApixLResult, CellState
from apix.schemas.version_vector import VersionVector
from apix.statistics.index.apix_l import ApixLError, calculate_apix_l, cell_id
from apix.statistics.index.chaining import MAX_FRESHNESS_DAYS


class PublicationError(ValueError):
    """A publication that cannot be assembled. Never silently repaired."""


def publication_freshness(state: CellState, publication_date: date) -> int | None:
    """``freshness(c,t)`` at the **publication** date — spec C.3.

        freshness(c,t) = t - max{ s <= t : J(c,s) was computed }

    Args:
        state: The cell's most recent state on or before ``publication_date``.
        publication_date: The period *t* being published.

    Returns:
        Days since the cell's last computed relative, or ``None`` when no
        relative has ever been computed for it. ``None`` is a different state
        from "stale" and must not be collapsed into a large number: a cell that
        entered at its parent's level (spec J.1) has no relative of its own yet
        and is not stale.

    This is deliberately **not** :attr:`CellState.freshness_days`. That field
    records freshness as at the cell's own link date, which is the honest value
    for a day on which the cell had an event. On a day when it had none, the
    freshness that matters is measured from the publication date, and only this
    function knows it.
    """
    if state.last_matched_date is None:
        return None
    return (publication_date - state.last_matched_date).days


def latest_states_as_of(
    states: Sequence[CellState], publication_date: date
) -> tuple[CellState, ...]:
    """Each cell's most recent state on or before ``publication_date`` — spec C.2.

    Args:
        states: Cell states from any number of link dates. States for the same
            cell on different dates are expected; that is the whole point.
        publication_date: The period *t* being published.

    Returns:
        One state per :class:`~apix.schemas.keys.CellKey`, the most recent at or
        before ``t``, in sorted cell-key order (spec P.2). A cell whose only
        states are later than ``t`` is absent — it did not exist yet.

    States dated **after** ``t`` are excluded rather than rejected, and that is
    load-bearing rather than lenient. Spec P.3 requires a publication to be
    *"re-run from its recorded version vector and compared bit for bit"*, and
    spec R.3 keeps every prior vintage retrievable. Both mean replaying an
    earlier date against a store that has since grown. Raising here would make
    a vintage rebuild impossible without the caller reimplementing this filter,
    and a filter reimplemented at each call site is a filter that will differ at
    one of them.

    The low-level guard remains: :func:`~apix.statistics.index.apix_l.calculate_apix_l`
    rejects a future-dated state outright, because by the time a set reaches it
    the selection has already happened and a later date is a defect.

    The selection is a **pure lookup**. No level is recomputed, no relative is
    applied, and no state is fabricated for a day on which the cell had no
    event.
    """
    as_of = [s for s in states if s.collection_date <= publication_date]

    newest: dict[str, CellState] = {}
    for state in sorted(as_of, key=lambda s: (s.cell.sort_key, s.collection_date)):
        # Sorted ascending by (cell, date), so the last write per cell is the
        # most recent one. Ordered rather than max()-based so the reduction is
        # bit-stable regardless of input order (spec P.2, INV-5).
        newest[cell_id(state.cell)] = state

    return tuple(newest[key] for key in sorted(newest))


def apply_freshness_ceiling(
    states: Sequence[CellState], publication_date: date
) -> tuple[CellState, ...]:
    """Suppress cells stale beyond the spec C.3 ceiling — spec C.3, I.

    Args:
        states: The as-of live candidates for ``publication_date``.
        publication_date: The period *t* being published.

    Returns:
        The same cells in the same order, with any whose freshness at ``t``
        exceeds **13 days** replaced by a suppressed state. Their weight is
        renormalised away by spec F.4 rather than counted as zero, and the
        suppressed share is published (spec I).

    Thirteen days is two missed weekly links (spec C.3, E.5). Beyond it the
    assumption that the same product class is being tracked is no longer
    defensible, so the cell leaves the live set rather than contributing a level
    nothing has confirmed for a fortnight.

    A cell with no relative yet (``last_matched_date is None``) is **not**
    suppressed here: it is held out or entered at its parent's level under spec
    J, which is a different condition with its own status.
    """
    checked: list[CellState] = []
    for state in states:
        stale = publication_freshness(state, publication_date)
        if stale is not None and stale > MAX_FRESHNESS_DAYS:
            checked.append(
                replace(
                    state,
                    level=None,
                    status=CellStatus.SUPPRESSED,
                    freshness_days=stale,
                    suppression_reason=(
                        f"freshness {stale}d at publication date {publication_date} "
                        f"exceeds the {MAX_FRESHNESS_DAYS}d ceiling — two missed "
                        "weekly links (spec C.3, E.5); the cell leaves the live set"
                    ),
                )
            )
        else:
            checked.append(state)
    return tuple(checked)


def publish(
    *,
    states: Sequence[CellState],
    publication_date: date,
    cell_weights: Mapping[str, float],
    route_weights: Mapping[str, float],
    version_vector: VersionVector,
    expected_cells_by_route: Mapping[str, int],
    route_tiers: Mapping[str, Tier] | None = None,
    cell_tiers: Mapping[str, Tier] | None = None,
) -> ApixLResult:
    """Publish APIx-L for one date from states of many link dates — spec L.1.

    The production entry point. It composes what spec L.1 draws:

        states from every link date
          │  spec C.2   as-of selection: each chain's most recent level
          ▼
        live candidates at t
          │  spec C.3   freshness ceiling, 13 days
          ▼
        live set L_t
          │  spec F.2   Young / Modified Laspeyres over cell LEVELS
          │  spec F.4   renormalisation over the live set
          ▼
        spec F.3        national aggregation  →  APIx-L(t)

    Args:
        states: Cell states from any number of link dates, as produced by
            :func:`~apix.statistics.index.chaining.advance_cell`. The caller
            keeps them; this function does not mutate them.
        publication_date: The period *t*.
        cell_weights: ``v[c|r]`` keyed by :func:`~apix.statistics.index.apix_l.cell_id`.
            Build them with
            :func:`~apix.statistics.aggregation.within_route.within_route_weights`,
            which refuses to invent the allocation spec G.3 does not define.
        route_weights: ``w[r]`` keyed by route.
        version_vector: Spec O. Must carry ``model_version`` N/A **and**
            ``source_precedence``, which spec O.1 (v2.1) carries on every
            published output.
        expected_cells_by_route: The spec I coverage denominator. **Required, with
            no default**, because ``expected_cells`` is an open methodology
            question (**AMB-8**) and the optimistic observed-count fallback in
            :func:`~apix.statistics.index.apix_l.calculate_apix_l` must never
            become production behaviour by omission. Supplying it is an assertion
            about the basket, and the caller has to make it out loud.
        route_tiers: Tier per route, for display and as the coarse fallback.
        cell_tiers: Tier per cell. Preferred — see ``calculate_apix_l``.

    Returns:
        The :class:`~apix.schemas.results.ApixLResult` for ``publication_date``.

    Raises:
        PublicationError: on a future-dated state, or a version vector with no
            ``source_precedence``.
        ApixLError: propagated from ``calculate_apix_l``.
    """
    if not version_vector.source_precedence:
        raise PublicationError(
            "version vector carries no source_precedence; methodology v2.1 §O.1 "
            "records the ordered source list in force on every published output, "
            "and spec D.8 prices every matched pair from it"
        )

    as_of = latest_states_as_of(states, publication_date)
    live_set = apply_freshness_ceiling(as_of, publication_date)

    return calculate_apix_l(
        live_set,
        cell_weights,
        route_weights,
        version_vector,
        publication_date,
        route_tiers=route_tiers,
        cell_tiers=cell_tiers,
        expected_cells_by_route=expected_cells_by_route,
    )


__all__ = [
    "ApixLError",
    "PublicationError",
    "apply_freshness_ceiling",
    "latest_states_as_of",
    "publication_freshness",
    "publish",
]
