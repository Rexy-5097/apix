"""Daily, weekly and monthly period aggregation.

Periods are **derived from the dates of the points**, never from a display
setting. A weekly period is the ISO week the point falls in; a monthly period is
its calendar month. Nothing here is hard-coded to a display label.

**An index level is aggregated geometrically, and that is not a style choice.**
An index is a ratio scale: the arithmetic mean of ratios does not compose, so a
monthly level built from an arithmetic mean of daily levels is not the level of
anything. The geometric mean is the only aggregation consistent with the Jevons
elementary form the daily levels already use, and it makes the monthly change
equal the product of the daily changes it spans.

Coverage and effective sample size are carried through rather than recomputed:
they are properties of the underlying observations, and a period cannot acquire
evidence by being averaged.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import Enum


class Frequency(Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


@dataclass(frozen=True, slots=True)
class PeriodPoint:
    """One point of a period series.

    ``level`` is ``None`` when the period has no computable level. That is a real
    answer and is never rendered as zero: a zero index level would assert that
    fares went to nothing.
    """

    frequency: Frequency
    period: str
    period_start: date
    period_end: date
    level: float | None
    contributing_dates: tuple[date, ...]
    effective_n: int
    change_pct: float | None = None
    coverage_note: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "frequency": self.frequency.value,
            "period": self.period,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "level": self.level,
            "change_pct": self.change_pct,
            "contributing_dates": [d.isoformat() for d in self.contributing_dates],
            "effective_n": self.effective_n,
            "coverage_note": self.coverage_note,
        }


def period_key(when: date, frequency: Frequency) -> str:
    """The period label a date belongs to.

    Weekly uses ISO year-week, so the label is stable across year boundaries --
    a calendar-year label would put 29 December 2025 and 1 January 2026 in
    different years but the same week.
    """
    if frequency is Frequency.DAILY:
        return when.isoformat()
    if frequency is Frequency.WEEKLY:
        iso = when.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return f"{when.year}-{when.month:02d}"


def _bounds(points: Sequence[tuple[date, float | None]]) -> tuple[date, date]:
    dates = [d for d, _ in points]
    return min(dates), max(dates)


def aggregate(
    points: Sequence[tuple[date, float | None]],
    frequency: Frequency,
    *,
    effective_n: dict[date, int] | None = None,
) -> tuple[PeriodPoint, ...]:
    """Group dated index levels into periods, geometrically.

    ``points`` are ``(date, level)`` pairs; a ``None`` level contributes to the
    period's membership but not to its level, so a period built entirely from
    ``None`` has ``level=None`` rather than a spurious number.

    ``change_pct`` is the change against the previous period in the returned
    series, and is ``None`` wherever either side is missing -- a change against
    an absent period is not zero.
    """
    if not points:
        return ()

    grouped: dict[str, list[tuple[date, float | None]]] = {}
    for when, value in sorted(points):
        grouped.setdefault(period_key(when, frequency), []).append((when, value))

    counts = effective_n or {}
    out: list[PeriodPoint] = []
    previous: float | None = None

    for label in sorted(grouped):
        members = grouped[label]
        start, end = _bounds(members)
        levels = [lv for _, lv in members if lv is not None and lv > 0]

        level: float | None
        if levels:
            level = math.exp(sum(math.log(lv) for lv in levels) / len(levels))
            note = (
                f"geometric mean of {len(levels)} of {len(members)} dates"
                if len(levels) != len(members)
                else f"geometric mean of {len(levels)} dates"
            )
        else:
            level = None
            note = f"no computable level on any of {len(members)} dates in this period"

        change = None
        if level is not None and previous is not None and previous > 0:
            change = (level / previous - 1.0) * 100.0

        out.append(
            PeriodPoint(
                frequency=frequency,
                period=label,
                period_start=start,
                period_end=end,
                level=level,
                contributing_dates=tuple(d for d, _ in members),
                effective_n=sum(counts.get(d, 0) for d, _ in members),
                change_pct=change,
                coverage_note=note,
            )
        )
        if level is not None:
            previous = level

    return tuple(out)


__all__ = ["Frequency", "PeriodPoint", "aggregate", "period_key"]
