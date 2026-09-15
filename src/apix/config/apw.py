"""Advance-purchase window sets — versioned configuration, not methodology.

**The frozen vector is not changed here, and cannot be.** Spec A.3 is LOCKED at

.. code-block:: text

    APW in {T+1, T+3, T+7, T+15, T+30, T+45, T+60}

and lives in :class:`~apix.schemas.enums.APWBucket`. This module reads that enum;
it never redefines it. Changing the production vector is a methodology change
requiring an ADR and a version bump, exactly as ``enums.py`` says.

**Why this module exists.** PS 26056 asks for five windows:

.. code-block:: text

    T+1, T+7, T+15, T+30, T+45

APIx froze seven. The PS set is a strict subset of ours -- T+3 and T+60 are APIx
additions (AMB-1 resolution: *"Lead time is the strongest price driver in
revenue-managed inventory, and a single point measures one place on a moving
curve"*). So APIx collects a superset and can report the PS set exactly, with no
methodology change and no loss.

Keeping both declared, versioned and named prevents the two failure modes that
would otherwise be tempting on a deadline: quietly dropping T+3 and T+60 to
"match the PS", or quietly presenting seven windows as though the PS asked for
them.

Nothing downstream hard-codes a window. A caller states which set it wants.
"""

from __future__ import annotations

from dataclasses import dataclass

from apix.schemas.enums import APWBucket


@dataclass(frozen=True, slots=True)
class ApwWindowSet:
    """A named, versioned set of advance-purchase windows.

    ``days`` is always a tuple of exact lead times in ascending order. Assignment
    remains spec A.3's exact match: a set may narrow which buckets are
    *reported*, never how a lead time is *assigned*.
    """

    set_id: str
    version: str
    days: tuple[int, ...]
    authority: str
    note: str = ""

    def __post_init__(self) -> None:
        if not self.days:
            raise ValueError(f"window set {self.set_id!r} is empty")
        if list(self.days) != sorted(set(self.days)):
            raise ValueError(
                f"window set {self.set_id!r} must be ascending and unique, got {self.days}"
            )
        unknown = [d for d in self.days if APWBucket.from_lead_time(d) is None]
        if unknown:
            raise ValueError(
                f"window set {self.set_id!r} names lead times {unknown} that match no frozen "
                "APWBucket. Spec A.3 is LOCKED: a configuration set may only SELECT from the "
                "frozen vector, never extend it. Adding a bucket is a methodology change."
            )

    @property
    def buckets(self) -> tuple[APWBucket, ...]:
        """The frozen buckets this set selects, in ascending order."""
        return tuple(b for b in APWBucket if b.value in self.days)

    def covers(self, other: ApwWindowSet) -> bool:
        """Whether every window in ``other`` is also in this set."""
        return set(other.days) <= set(self.days)

    def as_dict(self) -> dict[str, object]:
        return {
            "set_id": self.set_id,
            "version": self.version,
            "days": list(self.days),
            "authority": self.authority,
            "note": self.note,
        }


#: The frozen APIx production vector — spec A.3, LOCKED. Read from the enum.
APIX_FROZEN_WINDOWS = ApwWindowSet(
    set_id="apix-frozen",
    version="2.1",
    days=tuple(b.value for b in APWBucket),
    authority="docs/methodology/apix_formula_spec_v1.md spec A.3 (LOCKED)",
    note=(
        "The production vector. Seven buckets. T+3 and T+60 are APIx additions over the PS "
        "set, recorded as an APIx design decision in docs/methodology/AMB-1-resolution.md. "
        "This tuple is derived from APWBucket and cannot drift from it."
    ),
)

#: The window set PS 26056 names. A strict subset of the frozen vector.
PS_26056_WINDOWS = ApwWindowSet(
    set_id="ps-26056",
    version="1.0",
    days=(1, 7, 15, 30, 45),
    authority="MoSPI PS 26056, detailed description",
    note=(
        "PS 26056: 'multiple advance-purchase windows (T+1, T+7, T+15, T+30, T+45 days)'. "
        "A strict subset of the frozen APIx vector, so APIx reports it exactly without any "
        "methodology change. T+3 and T+60 are collected in addition, never instead."
    ),
)

_SETS = {s.set_id: s for s in (APIX_FROZEN_WINDOWS, PS_26056_WINDOWS)}


def window_set(set_id: str) -> ApwWindowSet:
    """Look up a declared window set by id. Unknown ids raise rather than default."""
    try:
        return _SETS[set_id]
    except KeyError:
        raise KeyError(
            f"unknown APW window set {set_id!r}; declared sets are {sorted(_SETS)}"
        ) from None


def declared_sets() -> tuple[ApwWindowSet, ...]:
    """Every declared set, for display and for the API's metadata block."""
    return (APIX_FROZEN_WINDOWS, PS_26056_WINDOWS)


__all__ = [
    "APIX_FROZEN_WINDOWS",
    "PS_26056_WINDOWS",
    "ApwWindowSet",
    "declared_sets",
    "window_set",
]
