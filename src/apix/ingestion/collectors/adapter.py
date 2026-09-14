"""The source-adapter interface.

An adapter does one thing: run one contracted search against one source and
return a :class:`~apix.ingestion.collectors.candidates.SearchResult` describing
what the page showed. It does **not** apply eligibility, select flights, choose
fares or write to the store -- those are source-independent and live in
``eligibility``, ``selection``, ``fares``, ``normalize`` and ``runner``, so every
adapter is held to the same rules by the same code.

Adapter contract
----------------
* ``search`` never raises for a problem *at the source*. A timeout, error page,
  block page or unrecognised layout is returned as a ``PageState`` with whatever
  evidence was captured. Exceptions are for defects in the collector itself.
* An access challenge is returned as ``ACCESS_CHALLENGE`` and never retried,
  solved or worked around.
* A LIVE adapter must clear :func:`~apix.ingestion.collectors.gate.require_live_clearance`
  in its constructor, before it can make any request.

Status of adapters (see ``docs/engineering/automated-collection.md``):

==============  ==========================================================
IndiGo          fixture mode implemented; live mode implemented and GATED
                (registry: AUTOMATION_PROHIBITED) -- has never run live
Air India       not implemented
Akasa Air       not implemented (registry: AUTOMATION_PROHIBITED)
OTAs            not implemented
==============  ==========================================================
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from apix.ingestion.collectors.candidates import SearchResult
from apix.ingestion.collectors.contract import SearchParams
from apix.ingestion.collectors.gate import CollectionMode


class SourceAdapter(ABC):
    #: ``source_id`` written on observations, e.g. ``"indigo-direct"``.
    source_id: ClassVar[str]
    #: Key of the source's entry in ``source_registry/registry.yaml``.
    registry_id: ClassVar[str]
    adapter_version: ClassVar[str]
    parser_version: ClassVar[str]

    mode: CollectionMode

    @abstractmethod
    def search(self, params: SearchParams) -> SearchResult:
        """Run one contracted search and report what the source returned."""

    def environment(self) -> dict[str, str]:
        """Reproducibility details recorded on the run."""
        return {
            "adapter": f"{type(self).__name__}/{self.adapter_version}",
            "parser_version": self.parser_version,
            "mode": self.mode.value,
        }

    def close(self) -> None:  # noqa: B027 -- optional hook, deliberately a no-op
        """Release any browser or file handles."""

    def __enter__(self) -> SourceAdapter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


__all__ = ["SourceAdapter"]
