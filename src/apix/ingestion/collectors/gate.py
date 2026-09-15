"""The compliance gate every live adapter must clear before any request.

Implements ``compliance/collection-control-contract.md`` C-1 and
``acquisition-protocol.md`` s1 against the entry in
``source_registry/registry.yaml``:

    No automated run may start until a source reaches AUTOMATION_ALLOWED on
    positive, quoted evidence. AUTOMATION_UNKNOWN does not permit a trial run.

Both registry gates must clear -- permission (``automation_gate``) and data
validity (``data_admissibility``) -- and C-1 additionally requires the terms and
robots.txt to have been read with a permitting result.

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
    #: Real requests to the source. Gated.
    LIVE = "LIVE"
    #: Recorded or synthetic page data. No request is made; results are SYNTHETIC.
    FIXTURE = "FIXTURE"


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

_EVIDENCE_FIELDS = (
    "automation_gate_basis",
    "automation_gate_caveat",
    "automation_gate_date",
    "manual_gate",
    "robots_evidence",
    "evidence_date",
)


class GateRefused(RuntimeError):
    """A live run was refused by the compliance gate. Nothing was requested."""

    def __init__(self, decision: GateDecision) -> None:
        self.decision = decision
        super().__init__(
            f"live collection from {decision.source_id!r} refused by the compliance gate: "
            + "; ".join(decision.failures)
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


def evaluate_live_gate(entry: Mapping[str, object]) -> GateDecision:
    """Decide whether live automated collection from this source is permitted."""
    source_id = str(entry.get("source_id", ""))
    failures = [
        f"{name}={entry.get(name, 'ABSENT')!s} (requires {' or '.join(allowed)})"
        for name, allowed in LIVE_REQUIREMENTS
        if str(entry.get(name, "")) not in allowed
    ]
    evidence = tuple((name, str(entry[name])) for name in _EVIDENCE_FIELDS if name in entry)
    return GateDecision(
        source_id=source_id,
        mode=CollectionMode.LIVE,
        allowed=not failures,
        failures=tuple(failures),
        evidence=evidence,
    )


def require_live_clearance(entry: Mapping[str, object]) -> GateDecision:
    """Evaluate the gate and raise :class:`GateRefused` unless it clears."""
    decision = evaluate_live_gate(entry)
    if not decision.allowed:
        raise GateRefused(decision)
    return decision


def fixture_decision(source_id: str) -> GateDecision:
    """Fixture mode makes no request, so there is nothing for the gate to refuse."""
    return GateDecision(source_id=source_id, mode=CollectionMode.FIXTURE, allowed=True)


__all__ = [
    "LIVE_REQUIREMENTS",
    "CollectionMode",
    "GateDecision",
    "GateRefused",
    "evaluate_live_gate",
    "find_source",
    "fixture_decision",
    "require_live_clearance",
]
