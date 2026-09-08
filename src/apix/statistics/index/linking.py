"""Annual re-referencing — spec K.

Within-year chaining and year-to-year linking are **different operations and
must not be conflated** (spec K.1):

* Within-year chaining (spec E.2) — ``I(c,t) = I(c,t-7) * J(c,t)``. Continuous,
  weekly, per cell. Lives in :mod:`apix.statistics.index.chaining`.
* Year-to-year linking (spec K.2) — a **single** re-referencing at the index-year
  boundary when weights are updated. Lives here.

Boundary note. Linking is *not* part of the per-period APIx-L computation and is
deliberately isolated from it: :func:`~apix.statistics.index.apix_l.calculate_apix_l`
never calls this module. A link is applied forward from a stated date by the
publication layer, changes ``weight_version`` and ``basket_version``, and creates
a new vintage. It is not a revision (spec K.3, R.2).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


class LinkingError(ValueError):
    """A linking factor that cannot be computed."""


@dataclass(frozen=True, slots=True)
class LinkResult:
    """A linking factor and the means it was derived from — spec K.2."""

    linking_factor: float
    mean_level_old_reference_year: float
    mean_level_new_reference_year: float

    def apply(self, level: float) -> float:
        """Re-reference one published level: ``I_linked(t) = I_old(t) * LF``."""
        return level * self.linking_factor


def mean_level(levels: Sequence[float]) -> float:
    """Arithmetic mean of a reference year's published levels.

    Summed in the order given; callers pass levels in date order, which is a
    stable order (spec P.2).

    Raises:
        LinkingError: on an empty sequence. A reference year with no published
            levels cannot anchor a link.
    """
    if not levels:
        raise LinkingError("cannot take the mean level of an empty reference year")
    total = 0.0
    for value in levels:
        total += value
    return total / len(levels)


def linking_factor(
    old_reference_year_levels: Sequence[float],
    new_reference_year_levels: Sequence[float],
) -> LinkResult:
    """Compute the annual linking factor — spec K.2.

        LF = mean level of the new reference year / mean level of the old

    Args:
        old_reference_year_levels: Published levels across the old reference year.
        new_reference_year_levels: Published levels across the new reference year.

    Returns:
        A :class:`LinkResult` carrying the factor and both means, so the
        derivation is publishable rather than an unexplained multiplier.

    Raises:
        LinkingError: if either year is empty, or the old year's mean is not
            positive. A non-positive mean level is not a small index — it is a
            corrupt series, and dividing by it would hide that.
    """
    old_mean = mean_level(old_reference_year_levels)
    new_mean = mean_level(new_reference_year_levels)

    if old_mean <= 0:
        raise LinkingError(
            f"old reference year mean level is {old_mean}; an index level must be "
            "positive, so this is a corrupt series rather than a linkable one"
        )

    return LinkResult(
        linking_factor=new_mean / old_mean,
        mean_level_old_reference_year=old_mean,
        mean_level_new_reference_year=new_mean,
    )
