"""Period series and publication readiness.

PS 26056 asks for an index at *"daily, weekly and monthly frequencies"*. This
package derives those periods from index points and decides, separately and
explicitly, whether a series may be published.

The two concerns are kept apart on purpose. Period aggregation is arithmetic and
always succeeds given points. **Publication readiness is a judgement about
evidence, and it is allowed to say no.** Collapsing them is how a system ends up
publishing a monthly average of one observation.
"""

from apix.series.periods import (
    Frequency,
    PeriodPoint,
    aggregate,
    period_key,
)
from apix.series.readiness import (
    ReadinessState,
    SeriesReadiness,
    assess,
)

__all__ = [
    "Frequency",
    "PeriodPoint",
    "ReadinessState",
    "SeriesReadiness",
    "aggregate",
    "assess",
    "period_key",
]
