"""Scheduled collection — the layer PS 26056 asks for.

PS 26056 expects *"scheduled daily extraction from airline portals"*. This
package plans and executes that schedule over the route basket, the
advance-purchase window set and the registered sources.

**It runs to completion when nothing is cleared, which is the current state.**
Zero of thirty registered sources clear the live compliance gate, so a run today
attempts every planned search, is refused at the gate for every one, and records
:attr:`~apix.schemas.enums.CollectionOutcome.PERMISSION_BLOCKED` against each --
with no request made to any source.

That is the point. Spec H.1's design is that *"missingness cannot be measured
from a table of successes"*. Before ADR-0066 a gate refusal raised and the run
aborted, leaving no attempt row at all; a scheduled run over an uncleared
register produced an exception rather than a measurement. Now it produces a
complete attempt table in which every cell is accounted for and every absence is
attributed to us rather than to a thin market.
"""

from apix.scheduling.scheduler import (
    PlannedSearch,
    ScheduledRun,
    SchedulerConfig,
    SearchRecord,
    build_plan,
    execute_plan,
    run_id_for,
)

__all__ = [
    "PlannedSearch",
    "ScheduledRun",
    "SchedulerConfig",
    "SearchRecord",
    "build_plan",
    "execute_plan",
    "run_id_for",
]
