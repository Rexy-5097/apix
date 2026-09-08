"""Cell chaining, carry, suppression and new-cell entry — spec E, I, J.

The distinction this module turns on (spec C.4):

    J(c,t) is a RELATIVE (a dimensionless ratio, ~1)
    I(c,t) is a LEVEL    (base 100)

and the rule that protects the aggregate (spec J.1):

    A NEW CELL ENTERS AT ITS PARENT'S CURRENT LEVEL, NEVER AT 100.

Entering at 100 inside a live aggregate injects a spurious jump: a newly
appearing fare would be recorded as though the price had moved from the base
period to the parent's level in a single step. **A newly appearing fare is not a
price change.**
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from apix.schemas.enums import CellStatus
from apix.schemas.keys import CellKey, ParentKey
from apix.schemas.results import BASE_INDEX_LEVEL, CellState, JevonsResult

# Spec C.3 / I — LOCKED. Two missed weekly links.
MAX_FRESHNESS_DAYS = 13

# Spec I — LOCKED. Share of a cell's periods in the trailing 8 weeks that were
# imputed (carried) rather than computed from the cell's own matched set.
MAX_CELL_IMPUTATION = 0.40


@dataclass(frozen=True, slots=True)
class ChainInputs:
    """Everything needed to advance one cell by one period.

    ``previous`` is the cell's state at ``t - 7`` — its own weekly chain, not
    the previous calendar day (spec C.2). ``parent_relative`` is
    ``J(parent(c), t)`` for the carry rule (spec E.4); ``parent_level`` is
    ``I(parent(c), t)`` for new-cell entry (spec J.1). They are different
    quantities and are deliberately separate parameters: inheriting the parent's
    *level* on a carry would teleport the cell onto the parent's path and erase
    its own accumulated history.
    """

    cell: CellKey
    collection_date: date
    jevons: JevonsResult
    previous: CellState | None = None
    parent_relative: float | None = None
    parent_level: float | None = None
    imputation_rate: float = 0.0

    def __post_init__(self) -> None:
        if self.jevons.cell != self.cell:
            raise ValueError(
                f"JevonsResult is for cell {self.jevons.cell.sort_key}, not {self.cell.sort_key}"
            )
        if self.jevons.collection_date != self.collection_date:
            raise ValueError(
                f"JevonsResult is for {self.jevons.collection_date}, not {self.collection_date}"
            )


def freshness_days(collection_date: date, last_matched: date | None) -> int | None:
    """Days since a relative was last computed for this cell — spec C.3.

        freshness(c,t) = t - max{ s <= t : J(c,s) was computed }

    Returns None when no relative has ever been computed, which is a different
    state from "stale" and must not be collapsed into a large number.
    """
    if last_matched is None:
        return None
    return (collection_date - last_matched).days


def _suppressed(
    inputs: ChainInputs, reason: str, *, last_matched: date | None, freshness: int | None
) -> CellState:
    return CellState(
        cell=inputs.cell,
        collection_date=inputs.collection_date,
        level=None,
        status=CellStatus.SUPPRESSED,
        last_matched_date=last_matched,
        freshness_days=freshness,
        parent=inputs.cell.parent(),
        suppression_reason=reason,
    )


def _enter_or_hold(inputs: ChainInputs, parent: ParentKey) -> CellState:
    """Handle a cell with no usable prior level — spec E.3, J.

    Rule (b) — entry against an existing parent — **takes precedence whenever a
    parent exists** (spec E.3). Only when no parent level exists at all may the
    cell take the base 100, and then only if its own relative is defined.
    """
    if inputs.parent_level is not None:
        # Spec J.1. On the entry date the cell contributes a level identical to
        # its parent, so the aggregate is unchanged by the entry itself (J.2).
        return CellState(
            cell=inputs.cell,
            collection_date=inputs.collection_date,
            level=inputs.parent_level,
            status=CellStatus.ENTERED,
            last_relative=None,
            last_matched_date=(inputs.collection_date if inputs.jevons.is_defined else None),
            freshness_days=0 if inputs.jevons.is_defined else None,
            parent=parent,
        )

    if inputs.jevons.is_defined:
        # Spec E.1/E.3(a): a standalone cell with no parent takes the base. This
        # is the system-bootstrap case — there is no live aggregate to distort.
        return CellState(
            cell=inputs.cell,
            collection_date=inputs.collection_date,
            level=BASE_INDEX_LEVEL,
            status=CellStatus.PUBLISHED,
            last_relative=inputs.jevons.relative,
            last_matched_date=inputs.collection_date,
            freshness_days=0,
            parent=parent,
        )

    # Spec J.2: never seeded at 100 inside a live aggregate. Held out until a
    # parent level exists or the cell earns its own relative.
    return CellState(
        cell=inputs.cell,
        collection_date=inputs.collection_date,
        level=None,
        status=CellStatus.HELD_OUT,
        parent=parent,
        suppression_reason=(
            "no prior level, no parent level to enter at, and no defined "
            "relative of its own (spec E.3, J.2)"
        ),
    )


def advance_cell(inputs: ChainInputs) -> CellState:
    """Advance one cell by one weekly link — spec E, I, J.

    Args:
        inputs: The cell, its period, its relative, its state at ``t - 7``, and
            the parent quantities needed for carry and entry.

    Returns:
        The cell's new :class:`CellState`. A suppressed or held-out cell has
        ``level is None`` and does not contribute to aggregation; its weight is
        renormalised away (spec F.4) rather than counted as zero.

    Failure conditions: none raised. Every path returns a state with an explicit
    status and, where relevant, a suppression reason — a cell is never silently
    dropped (INV-7).

    Decision order:

    1. **Imputation ceiling** (spec I) — a cell carried for more than 40% of its
       trailing periods is suppressed rather than imputed further.
    2. **Resumption window** (spec E.5) — a gap over 13 days means the claim
       that the same product class is being tracked is no longer defensible, so
       the cell re-enters as new rather than resuming its chain.
    3. **Own relative** (spec E.2) — chain it.
    4. **Parent relative** (spec E.4) — carry it.
    5. Otherwise suppress.
    """
    parent = inputs.cell.parent()
    previous = inputs.previous
    prior_level = previous.level if previous is not None else None
    last_matched = previous.last_matched_date if previous is not None else None

    if inputs.imputation_rate > MAX_CELL_IMPUTATION:
        return _suppressed(
            inputs,
            f"cell imputation rate {inputs.imputation_rate:.2%} exceeds the "
            f"{MAX_CELL_IMPUTATION:.0%} ceiling; suppressed rather than imputed (spec I)",
            last_matched=last_matched,
            freshness=freshness_days(inputs.collection_date, last_matched),
        )

    if prior_level is None:
        return _enter_or_hold(inputs, parent)

    staleness = freshness_days(inputs.collection_date, last_matched)

    # Spec E.5 — resumption after more than 13 days is a NEW cell, not a
    # resumed chain. Checked before the freshness suppression so a returning
    # cell re-enters at its parent's level instead of being suppressed forever.
    if staleness is not None and staleness > MAX_FRESHNESS_DAYS:
        if inputs.parent_level is not None or inputs.jevons.is_defined:
            return _enter_or_hold(inputs, parent)
        return _suppressed(
            inputs,
            f"freshness {staleness}d exceeds {MAX_FRESHNESS_DAYS}d and no parent "
            "level exists to re-enter at (spec C.3, E.5)",
            last_matched=last_matched,
            freshness=staleness,
        )

    if inputs.jevons.is_defined:
        assert inputs.jevons.relative is not None  # narrowed by is_defined
        return CellState(
            cell=inputs.cell,
            collection_date=inputs.collection_date,
            level=prior_level * inputs.jevons.relative,
            status=CellStatus.PUBLISHED,
            last_relative=inputs.jevons.relative,
            last_matched_date=inputs.collection_date,
            freshness_days=0,
            parent=parent,
        )

    # Spec E.4 — inherit the parent's RELATIVE, never its level.
    if inputs.parent_relative is not None:
        return CellState(
            cell=inputs.cell,
            collection_date=inputs.collection_date,
            level=prior_level * inputs.parent_relative,
            status=CellStatus.CARRIED,
            last_relative=None,
            last_matched_date=last_matched,
            freshness_days=staleness,
            parent=parent,
        )

    why = inputs.jevons.undefined_reason
    return _suppressed(
        inputs,
        "own relative undefined and parent relative also undefined "
        f"({why.value if why else 'unknown'}); "
        "nothing more sophisticated ships in v1 (spec E.4, H.2)",
        last_matched=last_matched,
        freshness=staleness,
    )
