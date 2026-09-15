"""Benchmark backtesting — the framework, and an honest verdict on the data.

PS 26056 requires the prototype to *"demonstrate at least 30 days of back-tested
results against publicly available DGCA monthly average-fare data."*

That sentence contains a contradiction the data cannot resolve, and the framework
reports it rather than papering over it:

* **30 days is a daily comparison. "Monthly average-fare data" is monthly.** A
  monthly series cannot supply 30 daily comparison points; it supplies one.
* **No published DGCA average-fare series was located.** The 2026-09-15
  acquisition sweep enumerated DGCA's complete A-Z index and sitemap and found
  no tariff, fare, airfare or fare-monitoring publication in any format. Its
  entire air-transport statistical offering is traffic and capacity.

So :data:`~apix.backtest.compare.DGCA_FARE_BENCHMARK_STATUS` is
``NOT_LOCATED``, and any comparison against it reports
``BACKTEST_INCOMPLETE``.

**What the framework does instead.** It is fully implemented -- alignment,
Pearson correlation, MAE, MAPE, RMSE and directional agreement -- and it runs
against the one public benchmark APIx does hold: the MoSPI eSankhyiki CPI
airfare item index, retrieved automatically by
``tools/analysis/pull_mospi_benchmark.py``. That is a monthly All-India index
number, not an average fare, so a comparison against it is **structural, not
statistical**, and the verdict says so.

No fabricated validation. The framework is real, the metrics are real, and the
verdict on the data is that the PS's stated benchmark does not exist in
published form.
"""

from apix.backtest.compare import (
    DGCA_FARE_BENCHMARK_STATUS,
    BacktestResult,
    BacktestStatus,
    BenchmarkSeries,
    compare,
    directional_agreement,
    mae,
    mape,
    pearson,
    rmse,
)

__all__ = [
    "DGCA_FARE_BENCHMARK_STATUS",
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
