"""Versioned ingestion and figure registration.

Ingestion is *versioned*: every time a data file enters the repository the
toolkit

* copies it into ``datasets/<id>/data/``,
* computes its SHA-256 checksum,
* bumps the dataset's semantic version (major.minor.patch),
* appends an append-only event to ``datasets/<id>/provenance.jsonl``,
* refreshes ``checksums/sha256sums.txt`` for the dataset, and
* synchronises the dataset's row in ``inventory/datasets.csv``.

Because of this, every published figure can be traced to exactly one
versioned input: :func:`register_figure` records the figure's inputs
together with the SHA-256 digest of each input file at registration time,
and :mod:`data_stewardship.checks` verifies that chain of custody on
every run.
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from . import __version__
from .checks import (
    CHECKSUM_FILE,
    FIGURE_MANIFEST,
    INVENTORY_FILE,
    read_inventory,
    sha256_of,
)

VALID_BUMPS = ("major", "minor", "patch")


class StewardshipError(RuntimeError):
    """Raised when an ingestion or registration request cannot be honoured."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def bump_version(version: str, bump: str = "patch") -> str:
    """Bump a MAJOR.MINOR.PATCH version string.

    ``major`` = incompatible restructuring (schema change, redefinition),
    ``minor`` = additive change (new files/columns), ``patch`` = correction
    of existing content (typo fix, recalibrated value).
    """
    if bump not in VALID_BUMPS:
        raise StewardshipError(f"bump must be one of {VALID_BUMPS}, got {bump!r}")
    parts = str(version).strip().split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise StewardshipError(
            f"version {version!r} is not MAJOR.MINOR.PATCH; fix metadata.yaml first"
        )
    major, minor, patch = (int(p) for p in parts)
    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def _write_checksums(root: Path, checksums: Dict[str, str]) -> None:
    checksum_path = root / CHECKSUM_FILE
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{digest}  {relpath}" for relpath, digest in sorted(checksums.items())]
    checksum_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _sync_inventory_row(root: Path, dataset_id: str, version: str) -> None:
    inventory_path = root / INVENTORY_FILE
    with open(inventory_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    for row in rows:
        if row.get("dataset_id") == dataset_id:
            row["version"] = version
            row["updated"] = _today()
    with open(inventory_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ingest_dataset(
    root: Path,
    dataset_id: str,
    source_file: Path,
    actor: str = "unknown",
    bump: str = "patch",
    note: str = "",
) -> Dict:
    """Ingest *source_file* into *dataset_id* as a new dataset version.

    Returns the provenance event that was recorded. Raises
    :class:`StewardshipError` with an actionable hint when the dataset is
    not registered in the inventory or has no metadata.yaml yet.
    """
    root = Path(root)
    source_file = Path(source_file)
    if not source_file.is_file():
        raise StewardshipError(f"source file not found: {source_file}")

    row = next(
        (r for r in read_inventory(root) if r.get("dataset_id") == dataset_id), None
    )
    if row is None:
        raise StewardshipError(
            f"dataset_id {dataset_id!r} is not in {INVENTORY_FILE}. "
            "Register it there first (one row per dataset)."
        )

    dataset_dir = root / row["path"]
    metadata_path = dataset_dir / "metadata.yaml"
    if not metadata_path.exists():
        raise StewardshipError(
            f"{metadata_path} not found. Create it (see templates/) before ingesting."
        )
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
    if not isinstance(metadata, dict):
        raise StewardshipError(f"{metadata_path} is not a YAML mapping")

    # -- copy file and hash it ---------------------------------------------- #
    data_dir = dataset_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    dest = data_dir / source_file.name
    if not (dest.exists() and dest.samefile(source_file)):
        shutil.copy2(source_file, dest)
    digest = sha256_of(dest)
    rel_posix = dest.resolve().relative_to(root.resolve()).as_posix()

    # -- bump version and update metadata ------------------------------------ #
    new_version = bump_version(metadata.get("version", "0.0.0"), bump)
    timestamp = _now_iso()
    event = {
        "timestamp": timestamp,
        "event": "ingest",
        "version": new_version,
        "file": rel_posix,
        "sha256": digest,
        "actor": actor,
        "note": note or "Ingested via ds-steward",
        "tool": f"data-stewardship-toolkit {__version__}",
    }

    files: List[dict] = [f for f in (metadata.get("files") or []) if isinstance(f, dict)]
    files = [f for f in files if str(f.get("path", "")) != f"data/{source_file.name}"]
    files.append({"path": f"data/{source_file.name}", "sha256": digest, "bytes": dest.stat().st_size})
    metadata["version"] = new_version
    metadata["updated"] = _today()
    metadata["files"] = sorted(files, key=lambda f: str(f.get("path", "")))
    metadata.setdefault("provenance", []).append(
        {k: event[k] for k in ("timestamp", "event", "version", "file", "sha256", "actor")}
    )
    metadata_path.write_text(
        yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    # -- provenance log (append-only) ---------------------------------------- #
    provenance_path = dataset_dir / "provenance.jsonl"
    with open(provenance_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    # -- checksum registry ---------------------------------------------------- #
    # Replace only the entry for this specific file; other files of the
    # dataset (and all other datasets) keep their registered checksums.
    checksums = dict(_read_checksum_pairs(root))
    checksums.pop(rel_posix, None)
    checksums[rel_posix] = digest
    _write_checksums(root, checksums)

    # -- inventory synchronisation -------------------------------------------- #
    _sync_inventory_row(root, dataset_id, new_version)

    return event


def _read_checksum_pairs(root: Path) -> List[tuple]:
    from .checks import read_checksums

    return list(read_checksums(root).items())


def register_figure(
    root: Path,
    figure_id: str,
    dataset_id: str,
    output_path: Path,
    script_path: Path,
    actor: str = "unknown",
    caption: str = "",
) -> Dict:
    """Register a published figure against the current dataset version.

    The manifest entry stores, for every data file of the dataset, the
    SHA-256 digest observed at registration time. Checks later verify
    that each digest still matches the file on disk or appears in the
    dataset's provenance history - i.e. the figure can always be
    reproduced from a versioned input.
    """
    root = Path(root)
    row = next(
        (r for r in read_inventory(root) if r.get("dataset_id") == dataset_id), None
    )
    if row is None:
        raise StewardshipError(
            f"dataset_id {dataset_id!r} is not in {INVENTORY_FILE}; cannot register figure."
        )
    dataset_dir = root / row["path"]
    metadata_path = dataset_dir / "metadata.yaml"
    if not metadata_path.exists():
        raise StewardshipError(f"{metadata_path} not found; ingest the dataset first.")
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}

    from .checks import data_files

    inputs = [
        {
            "file": p.resolve().relative_to(root.resolve()).as_posix(),
            "sha256": sha256_of(p),
        }
        for p in data_files(dataset_dir)
    ]
    if not inputs:
        raise StewardshipError(
            f"dataset {dataset_id!r} has no data files; nothing to trace the figure to."
        )

    entry = {
        "registered": _now_iso(),
        "figure_id": figure_id,
        "dataset_id": dataset_id,
        "dataset_version": str(metadata.get("version", "0.0.0")),
        "inputs": inputs,
        "script": Path(script_path).as_posix(),
        "output": Path(output_path).as_posix(),
        "actor": actor,
        "caption": caption,
        "tool": f"data-stewardship-toolkit {__version__}",
    }
    manifest_path = root / FIGURE_MANIFEST
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def next_version(root: Path, dataset_id: str, bump: str = "patch") -> Optional[str]:
    """Preview the version that the next ingestion of *dataset_id* would get."""
    row = next(
        (r for r in read_inventory(root) if r.get("dataset_id") == dataset_id), None
    )
    if row is None:
        return None
    metadata_path = root / row["path"] / "metadata.yaml"
    version = "0.0.0"
    if metadata_path.exists():
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
        version = str(metadata.get("version", version))
    return bump_version(version, bump)
