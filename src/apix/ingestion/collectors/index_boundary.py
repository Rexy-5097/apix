"""The index-input boundary: automated, sandbox and fixture runs never feed the index.

``collection-windows.yaml`` admits only ``@primary`` runs to the index, and the
only collection authorised for ``@primary`` is the manual Day-1 contract. This
module turns that rule into code that fails:

* :func:`assert_not_index_input` raises if an automated run carries the
  ``@primary`` suffix. The runner calls it before writing any evidence or any
  store row, so a mislabelled automated run cannot be persisted at all.
* :func:`is_index_input_run` answers "may this run feed the index?" -- only a
  ``@primary`` run made by the manual collector.
* :func:`index_input_observations` reads a store and returns only observations
  whose run passes that test. Anything that selects index input from a store
  should go through it.

Adopting any automated channel as index input is an owner decision recorded in
an ADR, which would change this module deliberately -- never a flag.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from apix.ingestion.store import CollectionStore
from apix.schemas.collection import CollectionRun
from apix.schemas.observation import Observation

PRIMARY_SUFFIX = "@primary"
#: ``collector_version`` written by ``tools/collection/load_manual.py``.
MANUAL_COLLECTOR_VERSION = "manual"


class IndexBoundaryError(RuntimeError):
    """An automated run was labelled as index input. Nothing was written."""


def is_index_input_run(run: CollectionRun) -> bool:
    """Only a ``@primary`` run made by the manual collector may feed the index."""
    return (
        run.frame_id.endswith(PRIMARY_SUFFIX) and run.collector_version == MANUAL_COLLECTOR_VERSION
    )


def assert_not_index_input(run: CollectionRun) -> None:
    """Refuse an automated run that claims the primary (index-input) frame."""
    if run.frame_id.endswith(PRIMARY_SUFFIX):
        raise IndexBoundaryError(
            f"automated run {run.run_id} carries frame {run.frame_id!r}; {PRIMARY_SUFFIX} is "
            "reserved for the manual Day-1 contract. Sandbox, fixture and automated-trial "
            "runs are never index input"
        )


def index_input_observations(
    store: CollectionStore, collection_date: date | None = None
) -> list[Observation]:
    """Observations from index-input runs only, in ``observation_id`` order."""
    admitted = {r.run_id for r in store.runs() if is_index_input_run(r)}
    with sqlite3.connect(store.db_path) as conn:
        run_of = dict(conn.execute("SELECT observation_id, run_id FROM canonical_observation"))
    return [
        o for o in store.observations(collection_date) if run_of.get(o.observation_id) in admitted
    ]


__all__ = [
    "MANUAL_COLLECTOR_VERSION",
    "PRIMARY_SUFFIX",
    "IndexBoundaryError",
    "assert_not_index_input",
    "index_input_observations",
    "is_index_input_run",
]
