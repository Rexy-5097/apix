"""The compliance gate every live or sandbox adapter must clear before any request.

Implements ``compliance/collection-control-contract.md`` C-1 and
``acquisition-protocol.md`` s1 against the entry in
``source_registry/registry.yaml``:

    No automated run may start until a source reaches AUTOMATION_ALLOWED on
    positive, quoted evidence. AUTOMATION_UNKNOWN does not permit a trial run.

LIVE -- production requests whose results could become market observations.
Both registry gates must clear -- permission (``automation_gate``) and data
validity (``data_admissibility``) -- and C-1 additionally requires the terms and
robots.txt to have been read with a permitting result.

SANDBOX -- requests to an official API's own test (UAT) environment. Narrower by
construction, and never a route to market data:

* only a programmatic channel qualifies (``robots_status: NOT_APPLICABLE``), so
  no website can be reached through it;
* the register must rate the channel ``AUTOMATION_ALLOWED`` or
  ``AUTOMATION_ALLOWED_WITH_PERMISSION`` -- the source publishes the channel and
  its own registration issues the keys;
* the keys must actually be present, i.e. the source's registration has issued
  them. APIx never creates, borrows or guesses credentials.

Sandbox results are not prices anyone paid or could pay, are labelled
``@sandbox``, and are refused as index input by ``index_boundary``.

**There is no override.** No flag, environment variable or argument makes a
refused source collectable. The only way to change the answer is to change the
evidence in the register, which is a reviewed change owned by @slazyverse.

This module evaluates a mapping and never reads YAML itself, so the ingestion
package keeps its standard-library-only runtime.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class CollectionMode(Enum):
    #: Real production requests to the source. Gated by LIVE_REQUIREMENTS.
    LIVE = "LIVE"
    #: Recorded or synthetic page data. No request is made; results are SYNTHETIC.
    FIXTURE = "FIXTURE"
    #: An official API's test environment. Gated by SANDBOX_REQUIREMENTS; never index input.
    SANDBOX = "SANDBOX"


_PERMITTING_TERMS = ("CLEARLY_PERMITTED", "PERMITTED_WITH_CONDITIONS")

#: (registry field, values that permit live automated collection). Order is the
#: order failures are reported in.
LIVE_REQUIREMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("automation_gate", ("AUTOMATION_ALLOWED",)),
    ("data_admissibility", ("ADMISSIBLE",)),
    ("tos_status", _PERMITTING_TERMS),
    ("automated_collection_status", _PERMITTING_TERMS),
    ("robots_status", ("NO_RELEVANT_DISALLOW",)),
)

#: (registry field, values that permit requests to an official API's sandbox).
SANDBOX_REQUIREMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("automation_gate", ("AUTOMATION_ALLOWED", "AUTOMATION_ALLOWED_WITH_PERMISSION")),
    ("robots_status", ("NOT_APPLICABLE",)),
)

_EVIDENCE_FIELDS = (
    "automation_gate_basis",
    "automation_gate_caveat",
    "automation_gate_date",
    "manual_gate",
    "robots_evidence",
    "tos_evidence",
    "evidence_date",
)


class GateRefused(RuntimeError):
    """A run was refused by the compliance gate. Nothing was requested."""

    def __init__(self, decision: GateDecision) -> None:
        self.decision = decision
        super().__init__(
            f"{decision.mode.value.lower()} collection from {decision.source_id!r} refused "
            "by the compliance gate: " + "; ".join(decision.failures)
        )


@dataclass(frozen=True, slots=True)
class GateDecision:
    source_id: str
    mode: CollectionMode
    allowed: bool
    failures: tuple[str, ...] = ()
    evidence: tuple[tuple[str, str], ...] = ()


def find_source(registry: Mapping[str, object], source_id: str) -> Mapping[str, object]:
    """Return one source entry from a parsed ``registry.yaml``."""
    sources = registry.get("sources")
    if isinstance(sources, list):
        for entry in sources:
            if isinstance(entry, Mapping) and entry.get("source_id") == source_id:
                return entry
    raise KeyError(f"source {source_id!r} is not in the source registry")


def _evaluate(
    entry: Mapping[str, object],
    requirements: tuple[tuple[str, tuple[str, ...]], ...],
    mode: CollectionMode,
    extra_failures: tuple[str, ...] = (),
) -> GateDecision:
    failures = [
        f"{name}={entry.get(name, 'ABSENT')!s} (requires {' or '.join(allowed)})"
        for name, allowed in requirements
        if str(entry.get(name, "")) not in allowed
    ]
    failures.extend(extra_failures)
    return GateDecision(
        source_id=str(entry.get("source_id", "")),
        mode=mode,
        allowed=not failures,
        failures=tuple(failures),
        evidence=tuple((name, str(entry[name])) for name in _EVIDENCE_FIELDS if name in entry),
    )


def evaluate_live_gate(entry: Mapping[str, object]) -> GateDecision:
    """Decide whether live automated collection from this source is permitted."""
    return _evaluate(entry, LIVE_REQUIREMENTS, CollectionMode.LIVE)


def require_live_clearance(entry: Mapping[str, object]) -> GateDecision:
    """Evaluate the live gate and raise :class:`GateRefused` unless it clears."""
    decision = evaluate_live_gate(entry)
    if not decision.allowed:
        raise GateRefused(decision)
    return decision


def evaluate_sandbox_gate(
    entry: Mapping[str, object], *, credentials_present: bool
) -> GateDecision:
    """Decide whether requests to this source's official sandbox are permitted."""
    extra = (
        ()
        if credentials_present
        else ("credentials=ABSENT (sandbox needs keys issued by the source's own registration)",)
    )
    return _evaluate(entry, SANDBOX_REQUIREMENTS, CollectionMode.SANDBOX, extra)


def require_sandbox_clearance(
    entry: Mapping[str, object], *, credentials_present: bool
) -> GateDecision:
    """Evaluate the sandbox gate and raise :class:`GateRefused` unless it clears."""
    decision = evaluate_sandbox_gate(entry, credentials_present=credentials_present)
    if not decision.allowed:
        raise GateRefused(decision)
    return decision


def fixture_decision(source_id: str) -> GateDecision:
    """Fixture mode makes no request, so there is nothing for the gate to refuse."""
    return GateDecision(source_id=source_id, mode=CollectionMode.FIXTURE, allowed=True)


__all__ = [
    "LIVE_REQUIREMENTS",
    "SANDBOX_REQUIREMENTS",
    "CollectionMode",
    "GateDecision",
    "GateRefused",
    "evaluate_live_gate",
    "evaluate_sandbox_gate",
    "find_source",
    "fixture_decision",
    "require_live_clearance",
    "require_sandbox_clearance",
]
