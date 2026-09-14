"""Fixture-mode IndiGo adapter: replays extraction payloads, requests nothing.

Visibly labelled at every level it reaches:

* the fixture file must declare ``data_class: SYNTHETIC_FIXTURE``;
* runs carry ``frame_id ... @fixture`` and ``collector_identity fixture:...``;
* every observation carries ``source_type = SYNTHETIC``.

A fixture run exercises the real rules, normalisation, store and evidence code.
It is not, and must never be described as, a collection from goindigo.in.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import ClassVar

from apix.ingestion.collectors.adapter import SourceAdapter
from apix.ingestion.collectors.candidates import Artifact, PageState, SearchResult
from apix.ingestion.collectors.contract import SearchParams, ist_now
from apix.ingestion.collectors.evidence import canonical_json
from apix.ingestion.collectors.gate import CollectionMode
from apix.ingestion.collectors.indigo.parse import PARSER_VERSION, parse_extracted

FIXTURE_DATA_CLASS = "SYNTHETIC_FIXTURE"


class FixtureError(ValueError):
    """A fixture file that does not declare itself as synthetic."""


class FixtureIndigoAdapter(SourceAdapter):
    source_id: ClassVar[str] = "indigo-direct"
    registry_id: ClassVar[str] = "indigo"
    adapter_version: ClassVar[str] = "0.1.0"
    parser_version: ClassVar[str] = PARSER_VERSION

    def __init__(
        self,
        fixture: Path | Mapping[str, object],
        *,
        clock: Callable[[], datetime] = ist_now,
    ) -> None:
        self.mode = CollectionMode.FIXTURE
        if isinstance(fixture, Path):
            self.fixture_name = fixture.name
            data = json.loads(fixture.read_text(encoding="utf-8"))
        else:
            self.fixture_name = "<in-memory>"
            data = dict(fixture)
        if data.get("data_class") != FIXTURE_DATA_CLASS:
            raise FixtureError(
                f"fixture must declare data_class={FIXTURE_DATA_CLASS!r}; got "
                f"{data.get('data_class')!r}. Recorded pages are not fixtures"
            )
        pages = data.get("pages")
        if not isinstance(pages, Mapping):
            raise FixtureError("fixture has no 'pages' mapping of travel_date -> payload")
        self.pages: Mapping[str, Mapping[str, object]] = pages
        self._clock = clock

    def environment(self) -> dict[str, str]:
        return {**super().environment(), "fixture": self.fixture_name, "browser": "none"}

    def search(self, params: SearchParams) -> SearchResult:
        started = self._clock()
        key = params.travel_date.isoformat()
        payload = self.pages.get(key)
        if payload is None:
            return SearchResult(
                params=params,
                page_state=PageState.UNRECOGNISED,
                started_ts=started,
                finished_ts=self._clock(),
                detail=f"FIXTURE_HAS_NO_PAGE_FOR_DATE: {key} not in {self.fixture_name}",
                environment=self.environment(),
            )
        evidence = canonical_json(
            {
                "data_class": FIXTURE_DATA_CLASS,
                "fixture": self.fixture_name,
                "travel_date": key,
                "payload": payload,
            }
        )
        parsed = parse_extracted(payload, params)
        return SearchResult(
            params=params,
            page_state=parsed.page_state,
            started_ts=started,
            finished_ts=self._clock(),
            displayed=parsed.displayed,
            candidates=parsed.candidates,
            artifacts=(Artifact("fixture_payload", evidence, "application/json"),),
            http_status=parsed.http_status,
            detail=parsed.detail,
            structural_issues=parsed.structural_issues,
            environment=self.environment(),
        )


__all__ = ["FIXTURE_DATA_CLASS", "FixtureError", "FixtureIndigoAdapter"]
