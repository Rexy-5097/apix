"""The run export and its hash manifest -- evidence as first-class data.

Raw bytes (screenshots, page HTML, extracted payloads) go into the existing
content-addressed :class:`~apix.ingestion.store.ArtifactStore`, exactly where the
manual loader puts screenshots. This module adds the *run export*: a directory of
deterministic JSON documents describing one run, plus a manifest that hashes
every document and names every artifact by SHA-256::

    {export_root}/{run_id}/
        run.json            the CollectionRun and the environment
        attempts.json       one record per search, with outcome and reason
        selection.json      the returned universe per band, and what was selected
        observations.json   canonical observations, unpriced flights, exclusions
        manifest.json       sha256 of every document above + every artifact

JSON is serialised with sorted keys and fixed separators, so identical inputs
produce identical bytes -- and therefore identical hashes -- on every run.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path

from apix.ingestion.store import ArtifactStore, StoreError

MANIFEST_VERSION = 1
MANIFEST_NAME = "manifest.json"


class ExportError(RuntimeError):
    """A run export that cannot be written or does not verify."""


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _default(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"cannot serialise {type(value).__name__} into evidence JSON")


def canonical_json(obj: object) -> bytes:
    """Deterministic JSON bytes: sorted keys, two-space indent, trailing newline."""
    text = json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, default=_default)
    return (text + "\n").encode("utf-8")


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """One raw artifact bound to the attempt that captured it."""

    attempt_id: str
    role: str
    sha256: str
    byte_size: int
    content_type: str
    captured_ts: datetime
    store_path: str

    def as_dict(self) -> dict[str, object]:
        return {
            "attempt_id": self.attempt_id,
            "role": self.role,
            "sha256": self.sha256,
            "byte_size": self.byte_size,
            "content_type": self.content_type,
            "captured_ts": self.captured_ts.isoformat(),
            "store_path": self.store_path,
        }


def build_manifest(
    run_id: str, documents: Mapping[str, bytes], records: Sequence[EvidenceRecord]
) -> dict[str, object]:
    """Hash every document and list every artifact, in a fixed order."""
    return {
        "manifest_version": MANIFEST_VERSION,
        "hash_algorithm": "sha256",
        "run_id": run_id,
        "documents": [
            {"name": name, "sha256": sha256_hex(content), "byte_size": len(content)}
            for name, content in sorted(documents.items())
        ],
        "artifacts": [
            r.as_dict() for r in sorted(records, key=lambda r: (r.attempt_id, r.role, r.sha256))
        ],
    }


def write_run_export(
    export_root: Path,
    run_id: str,
    documents: Mapping[str, bytes],
    records: Sequence[EvidenceRecord],
) -> tuple[Path, str]:
    """Write the export directory. Returns ``(directory, manifest_sha256)``.

    Refuses to write into an existing directory: an export is immutable once
    written, and silently replacing one would destroy the evidence it held.
    """
    if MANIFEST_NAME in documents:
        raise ExportError(f"{MANIFEST_NAME} is generated, not supplied")
    run_dir = Path(export_root) / run_id
    if run_dir.exists():
        raise ExportError(f"run export {run_dir} already exists; exports are never overwritten")
    run_dir.mkdir(parents=True)
    for name, content in sorted(documents.items()):
        (run_dir / name).write_bytes(content)
    manifest = canonical_json(build_manifest(run_id, documents, records))
    (run_dir / MANIFEST_NAME).write_bytes(manifest)
    return run_dir, sha256_hex(manifest)


def verify_run_export(run_dir: Path, artifacts: ArtifactStore) -> list[str]:
    """Check an export against its manifest and the artifact store. Empty when sound."""
    problems: list[str] = []
    manifest_path = Path(run_dir) / MANIFEST_NAME
    if not manifest_path.exists():
        return [f"{manifest_path} is missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for doc in manifest["documents"]:
        path = Path(run_dir) / doc["name"]
        if not path.exists():
            problems.append(f"document {doc['name']} is missing")
            continue
        actual = sha256_hex(path.read_bytes())
        if actual != doc["sha256"]:
            problems.append(
                f"document {doc['name']} hashes to {actual}, manifest says {doc['sha256']}"
            )
    for art in manifest["artifacts"]:
        try:
            content = artifacts.get(art["sha256"])
        except StoreError as exc:
            problems.append(str(exc))
            continue
        if len(content) != art["byte_size"]:
            problems.append(f"artifact {art['sha256']} size differs from its manifest entry")
    return problems


__all__ = [
    "MANIFEST_NAME",
    "MANIFEST_VERSION",
    "EvidenceRecord",
    "ExportError",
    "build_manifest",
    "canonical_json",
    "sha256_hex",
    "verify_run_export",
    "write_run_export",
]
