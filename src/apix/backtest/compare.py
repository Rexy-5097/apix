"""Alignment and comparison metrics for a benchmark backtest.

Every metric here is standard and computed on **aligned pairs only** -- periods
present in both series. Alignment is reported alongside the metrics because a
correlation over three points is arithmetic, not evidence, and the reader needs
the count to judge it.

A metric over fewer than :data:`MIN_POINTS_FOR_METRICS` aligned pairs returns
``None`` rather than a number. This is not defensive coding: a Pearson
correlation over two points is exactly ±1 by construction and carries no
information, so reporting it would be actively misleading.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum

#: Below this many aligned pairs, metrics return None instead of a number.
MIN_POINTS_FOR_METRICS = 3

#: PS 26056 names DGCA monthly average-fare data as the benchmark. The
#: 2026-09-15 acquisition sweep enumerated DGCA's complete A-Z index and sitemap
#: and found no fare or tariff publication in any format.
DGCA_FARE_BENCHMARK_STATUS = "NOT_LOCATED"
DGCA_FARE_BENCHMARK_DETAIL = (
    "No published DGCA average-fare or tariff series was located. DGCA's complete A-Z index "
    "and sitemap were enumerated on 2026-09-15 [TOOL]: its air-transport statistical offering "
    "is the Handbook on Civil Aviation Statistics plus domestic and international traffic "
    "series -- departures, hours, kilometres, passengers, ASKM, load factors and cargo. No "
    "rupee-denominated fare field appears anywhere, and the site carries an all-rights-reserved "
    "notice with no reuse grant. A regulator receiving tariff data under a reporting mandate is "
    "not a publication channel."
)


class BacktestStatus(Enum):
    """Whether a comparison satisfies the PS requirement."""

    #: Aligned, sufficient points, benchmark comparable in kind.
    SATISFIED = "SATISFIED"
    #: The framework ran; the data cannot satisfy the requirement.
    INCOMPLETE = "INCOMPLETE"
    #: Nothing to compare — one side of the comparison is empty.
    NO_DATA = "NO_DATA"


@dataclass(frozen=True, slots=True)
class BenchmarkSeries:
    """A dated benchmark series, with what it actually measures.

    ``measures`` matters more than it looks. Comparing an airfare *index* with an
    average *fare in rupees* is a comparison of different quantities on different
    scales; the framework records the mismatch rather than dividing them.
    """

    benchmark_id: str
    publisher: str
    measures: str
    unit: str
    frequency: str
    points: Mapping[str, float]
    provenance: str
    is_index_number: bool


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """A comparison, its metrics, and an explicit verdict."""

    status: BacktestStatus
    benchmark_id: str
    aligned_periods: tuple[str, ...]
    apix_values: tuple[float, ...]
    benchmark_values: tuple[float, ...]
    correlation: float | None
    mae: float | None
    mape: float | None
    rmse: float | None
    directional_agreement: float | None
    reasons: tuple[str, ...]
    comparability: str

    @property
    def n(self) -> int:
        return len(self.aligned_periods)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "benchmark_id": self.benchmark_id,
            "n_aligned": self.n,
            "aligned_periods": list(self.aligned_periods),
            "apix_values": list(self.apix_values),
            "benchmark_values": list(self.benchmark_values),
            "metrics": {
                "correlation": self.correlation,
                "mae": self.mae,
                "mape": self.mape,
                "rmse": self.rmse,
                "directional_agreement": self.directional_agreement,
            },
            "reasons": list(self.reasons),
            "comparability": self.comparability,
        }


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson correlation, or None below the minimum point count."""
    n = len(xs)
    if n < MIN_POINTS_FOR_METRICS or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None  # a constant series has no correlation, not a correlation of 0
    return sxy / math.sqrt(sxx * syy)


def mae(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Mean absolute error. Meaningful only on comparable units."""
    if len(xs) < MIN_POINTS_FOR_METRICS or len(xs) != len(ys):
        return None
    return sum(abs(x - y) for x, y in zip(xs, ys, strict=True)) / len(xs)


def mape(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Mean absolute percentage error against ``ys``, skipping zero denominators."""
    if len(xs) < MIN_POINTS_FOR_METRICS or len(xs) != len(ys):
        return None
    pairs = [(x, y) for x, y in zip(xs, ys, strict=True) if y != 0]
    if len(pairs) < MIN_POINTS_FOR_METRICS:
        return None
    return 100.0 * sum(abs((x - y) / y) for x, y in pairs) / len(pairs)


def rmse(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Root mean squared error."""
    if len(xs) < MIN_POINTS_FOR_METRICS or len(xs) != len(ys):
        return None
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(xs, ys, strict=True)) / len(xs))


def directional_agreement(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Share of period-over-period changes that move the same way.

    Needs one more point than the other metrics, because it compares *changes*.
    A flat step on either side counts as disagreement unless both are flat --
    calling a flat move "agreement" with a rise would overstate the match.
    """
    if len(xs) < MIN_POINTS_FOR_METRICS + 1 or len(xs) != len(ys):
        return None
    agree = 0
    for i in range(1, len(xs)):
        dx, dy = xs[i] - xs[i - 1], ys[i] - ys[i - 1]
        if (dx > 0 and dy > 0) or (dx < 0 and dy < 0) or (dx == 0 and dy == 0):
            agree += 1
    return 100.0 * agree / (len(xs) - 1)


def compare(
    apix_points: Mapping[str, float],
    benchmark: BenchmarkSeries,
    *,
    apix_is_index_number: bool = True,
) -> BacktestResult:
    """Align two dated series and compute every metric that is meaningful.

    Level metrics (MAE, MAPE, RMSE) are suppressed when the two series measure
    different quantities -- an index number against an average fare in rupees.
    Correlation and directional agreement survive that mismatch because they are
    scale-free, so they are still reported.
    """
    reasons: list[str] = []
    shared = sorted(set(apix_points) & set(benchmark.points))
    xs = tuple(float(apix_points[p]) for p in shared)
    ys = tuple(float(benchmark.points[p]) for p in shared)

    if not shared:
        return BacktestResult(
            status=BacktestStatus.NO_DATA,
            benchmark_id=benchmark.benchmark_id,
            aligned_periods=(),
            apix_values=(),
            benchmark_values=(),
            correlation=None,
            mae=None,
            mape=None,
            rmse=None,
            directional_agreement=None,
            reasons=(
                f"no overlapping period: APIx has {len(apix_points)} point(s), "
                f"{benchmark.benchmark_id} has {len(benchmark.points)}",
            ),
            comparability="NOT_COMPARABLE — no aligned period",
        )

    same_kind = apix_is_index_number == benchmark.is_index_number
    if same_kind:
        comparability = "COMPARABLE IN KIND — both series are index numbers"
    else:
        comparability = (
            "NOT COMPARABLE IN LEVEL — APIx is an index number and "
            f"{benchmark.benchmark_id} measures {benchmark.measures} in {benchmark.unit}. "
            "Level metrics are suppressed; scale-free metrics are still reported."
        )
        reasons.append(
            "level metrics (MAE, MAPE, RMSE) suppressed: the two series measure different "
            "quantities on different scales"
        )

    if len(shared) < MIN_POINTS_FOR_METRICS:
        reasons.append(
            f"{len(shared)} aligned period(s); metrics need at least "
            f"{MIN_POINTS_FOR_METRICS} and directional agreement needs "
            f"{MIN_POINTS_FOR_METRICS + 1}"
        )

    status = (
        BacktestStatus.SATISFIED
        if same_kind and len(shared) >= MIN_POINTS_FOR_METRICS + 1
        else BacktestStatus.INCOMPLETE
    )
    if status is BacktestStatus.INCOMPLETE and not reasons:
        reasons.append("insufficient aligned periods to satisfy the requirement")

    return BacktestResult(
        status=status,
        benchmark_id=benchmark.benchmark_id,
        aligned_periods=tuple(shared),
        apix_values=xs,
        benchmark_values=ys,
        correlation=pearson(xs, ys),
        mae=mae(xs, ys) if same_kind else None,
        mape=mape(xs, ys) if same_kind else None,
        rmse=rmse(xs, ys) if same_kind else None,
        directional_agreement=directional_agreement(xs, ys),
        reasons=tuple(reasons),
        comparability=comparability,
    )


__all__ = [
    "DGCA_FARE_BENCHMARK_DETAIL",
    "DGCA_FARE_BENCHMARK_STATUS",
    "MIN_POINTS_FOR_METRICS",
    "BacktestResult",
    "BacktestStatus",
    "BenchmarkSeries",
    "compare",
    "directional_agreement",
    "mae",
    "mape",
    "pearson",
    "rmse",
]
