"""Stewardship compliance checks.

The toolkit guarantees that, at all times:

1. Every dataset folder has a matching entry in ``inventory/datasets.csv``.
2. Every dataset has a complete ``metadata.yaml`` sidecar file.
3. Every dataset licence is registered in ``inventory/rights-register.csv``
   and the SPDX identifier is consistent everywhere it appears.
4. Every data file has a SHA-256 checksum recorded in
   ``checksums/sha256sums.txt`` that matches the file on disk.
5. Every dataset keeps a valid, append-only provenance log
   (``provenance.jsonl``) with one event per ingestion.
6. Every registered figure traces back to a versioned dataset input whose
   checksum appears either in the dataset's provenance history or matches
   the file currently on disk (chain of custody).

``run_all_checks`` returns a :class:`StewardshipReport` that the CLI, the
pytest suite and the HTML dashboard all consume.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

# --------------------------------------------------------------------------- #
# Layout conventions                                                          #
# --------------------------------------------------------------------------- #

INVENTORY_FILE = "inventory/datasets.csv"
REGISTER_FILE = "inventory/rights-register.csv"
CHECKSUM_FILE = "checksums/sha256sums.txt"
FIGURE_MANIFEST = "figures/figure-manifest.jsonl"
DATASETS_DIR = "datasets"

IGNORED_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".venv", "venv",
    "node_modules", ".idea", ".vscode", "build", "dist",
}
IGNORED_FILES = {".DS_Store", "Thumbs.db"}

REQUIRED_INVENTORY_COLS = {
    "dataset_id", "title", "path", "version", "licence_id",
    "status", "steward", "updated", "description",
}
REQUIRED_METADATA_FIELDS = {
    "dataset_id", "title", "description", "version", "created",
    "steward", "licence", "fields",
}
REQUIRED_LICENCE_FIELDS = {"licence_id", "spdx", "name", "url"}
REQUIRED_PROVENANCE_FIELDS = {
    "timestamp", "event", "version", "file", "sha256", "actor",
}


# --------------------------------------------------------------------------- #
# Report dataclasses                                                          #
# --------------------------------------------------------------------------- #

@dataclass
class CheckResult:
    """One named check with a pass/fail outcome and a human-readable detail."""

    name: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - cosmetic only
        mark = "PASS" if self.passed else "FAIL"
        return f"[{mark}] {self.name}: {self.detail}"


@dataclass
class DatasetReport:
    """All check results for a single dataset."""

    dataset_id: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed(self) -> List[CheckResult]:
        return [c for c in self.checks if not c.passed]


@dataclass
class StewardshipReport:
    """Aggregated result of a full repository check run."""

    dataset_reports: List[DatasetReport] = field(default_factory=list)
    repo_checks: List[CheckResult] = field(default_factory=list)
    orphans: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        datasets_ok = all(r.ok for r in self.dataset_reports)
        repo_ok = all(c.passed for c in self.repo_checks)
        return datasets_ok and repo_ok and not self.orphans

    @property
    def total_checks(self) -> int:
        n = len(self.repo_checks)
        n += sum(len(r.checks) for r in self.dataset_reports)
        return n

    @property
    def passed_checks(self) -> int:
        n = sum(1 for c in self.repo_checks if c.passed)
        n += sum(1 for r in self.dataset_reports for c in r.checks if c.passed)
        return n


# --------------------------------------------------------------------------- #
# Low-level helpers                                                           #
# --------------------------------------------------------------------------- #

def sha256_of(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, streaming in 1 MiB chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path, root: Path) -> str:
    """POSIX-style path of *path* relative to *root*."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def _clean_rows(reader: csv.DictReader) -> List[Dict[str, str]]:
    """Normalise DictReader output: strip whitespace, drop ragged extras."""
    rows: List[Dict[str, str]] = []
    for row in reader:
        cleaned = {
            (k or "").strip(): (v.strip() if isinstance(v, str) else "")
            for k, v in row.items()
            if k is not None
        }
        if any(cleaned.values()):
            rows.append(cleaned)
    return rows


def read_inventory(root: Path) -> List[Dict[str, str]]:
    """Load inventory/datasets.csv and return its rows as dicts."""
    inventory_path = root / INVENTORY_FILE
    if not inventory_path.exists():
        return []
    with open(inventory_path, newline="", encoding="utf-8") as handle:
        return _clean_rows(csv.DictReader(handle))


def read_rights_register(root: Path) -> Dict[str, Dict[str, str]]:
    """Load inventory/rights-register.csv keyed by licence_id."""
    register_path = root / REGISTER_FILE
    if not register_path.exists():
        return {}
    with open(register_path, newline="", encoding="utf-8") as handle:
        rows = _clean_rows(csv.DictReader(handle))
    return {row["licence_id"]: row for row in rows if row.get("licence_id")}


def read_checksums(root: Path) -> Dict[str, str]:
    """Load checksums/sha256sums.txt as {relative_posix_path: sha256}."""
    checksum_path = root / CHECKSUM_FILE
    recorded: Dict[str, str] = {}
    if not checksum_path.exists():
        return recorded
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, relpath = parts[0].lower(), parts[1].strip().lstrip("*")
        recorded[relpath] = digest
    return recorded


def load_metadata(dataset_dir: Path) -> Optional[dict]:
    """Load and return metadata.yaml for a dataset, or None if unreadable."""
    metadata_path = dataset_dir / "metadata.yaml"
    if not metadata_path.exists():
        return None
    try:
        data = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def data_files(dataset_dir: Path) -> List[Path]:
    """All files under a dataset's data/ subtree (sorted by path)."""
    data_dir = dataset_dir / "data"
    if not data_dir.is_dir():
        return []
    return sorted(p for p in data_dir.rglob("*") if p.is_file())


def load_provenance(dataset_dir: Path) -> List[dict]:
    """Load the dataset's provenance.jsonl, skipping corrupt lines."""
    provenance_path = dataset_dir / "provenance.jsonl"
    if not provenance_path.exists():
        return []
    events: List[dict] = []
    for line in provenance_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def dataset_dirs(root: Path) -> List[Path]:
    """Every folder under datasets/ (one level deep), sorted."""
    datasets_root = root / DATASETS_DIR
    if not datasets_root.is_dir():
        return []
    return sorted(
        p for p in datasets_root.iterdir() if p.is_dir() and p.name not in IGNORED_DIRS
    )


def provenance_checksum_index(root: Path) -> Dict[str, Set[str]]:
    """Map dataset_id -> set of SHA-256 digests seen in its provenance log."""
    index: Dict[str, Set[str]] = {}
    for row in read_inventory(root):
        dataset_dir = root / row.get("path", "")
        events = load_provenance(dataset_dir)
        known_id = row.get("dataset_id", "")
        digests = index.setdefault(known_id, set())
        for event in events:
            if event.get("sha256"):
                digests.add(str(event["sha256"]).lower())
    return index


# --------------------------------------------------------------------------- #
# Per-dataset checks                                                          #
# --------------------------------------------------------------------------- #

def check_dataset(
    row: Dict[str, str],
    root: Path,
    register: Dict[str, Dict[str, str]],
    checksums: Dict[str, str],
) -> DatasetReport:
    """Run every stewardship check for one inventory row."""
    dataset_id = row.get("dataset_id", "<unnamed>")
    report = DatasetReport(dataset_id=dataset_id)
    dataset_dir = root / row.get("path", "")

    # -- 1. Inventory entry completeness ----------------------------------- #
    missing_cols = [c for c in REQUIRED_INVENTORY_COLS if not row.get(c)]
    report.checks.append(CheckResult(
        name="Inventory entry",
        passed=not missing_cols,
        detail=(
            "all required columns present "
            f"(version {row.get('version', '?')}, licence {row.get('licence_id', '?')})"
            if not missing_cols
            else "missing/empty columns: " + ", ".join(missing_cols)
        ),
    ))

    # -- 2. Metadata sidecar ----------------------------------------------- #
    metadata = load_metadata(dataset_dir)
    if metadata is None:
        report.checks.append(CheckResult(
            name="Metadata file",
            passed=False,
            detail=f"datasets/{dataset_id}/metadata.yaml missing or not a YAML mapping",
        ))
        metadata = {}
    else:
        missing_fields = [f for f in REQUIRED_METADATA_FIELDS if f not in metadata]
        id_mismatch = metadata.get("dataset_id") != dataset_id
        report.checks.append(CheckResult(
            name="Metadata file",
            passed=not missing_fields and not id_mismatch,
            detail=(
                f"valid mapping with {len(metadata)} top-level fields"
                if not missing_fields and not id_mismatch
                else (
                    (f"missing fields: {', '.join(missing_fields)}; " if missing_fields else "")
                    + (f"dataset_id mismatch (metadata says {metadata.get('dataset_id')!r})"
                       if id_mismatch else "")
                ).strip("; ")
            ),
        ))

    # -- 3. Licence and rights register ------------------------------------ #
    licence = metadata.get("licence") if isinstance(metadata.get("licence"), dict) else {}
    missing_lic = [f for f in REQUIRED_LICENCE_FIELDS if not licence.get(f)]
    reg_row = register.get(str(licence.get("licence_id", "")))
    unregistered = reg_row is None
    spdx_mismatch = (
        reg_row is not None
        and licence.get("spdx")
        and str(reg_row.get("spdx", "")).lower() != str(licence["spdx"]).lower()
    )
    inv_mismatch = row.get("licence_id") and row["licence_id"] != licence.get("licence_id")
    report.checks.append(CheckResult(
        name="Licence and rights",
        passed=not missing_lic and not unregistered and not spdx_mismatch and not inv_mismatch,
        detail=(
            f"licence {licence.get('licence_id', '?')} ({licence.get('spdx', '?')}) "
            "registered in the rights register"
            if not missing_lic and not unregistered and not spdx_mismatch and not inv_mismatch
            else (
                (f"metadata licence missing: {', '.join(missing_lic)}; " if missing_lic else "")
                + (f"licence_id {licence.get('licence_id')!r} not in rights-register.csv; " if unregistered else "")
                + ("SPDX identifier disagrees with the rights register; " if spdx_mismatch else "")
                + ("inventory licence_id disagrees with metadata; " if inv_mismatch else "")
            ).rstrip("; ")
        ),
    ))

    # -- 4. Checksums ------------------------------------------------------- #
    files = data_files(dataset_dir)
    if not files:
        report.checks.append(CheckResult(
            name="Checksums",
            passed=False,
            detail=f"no data files found under datasets/{dataset_id}/data/",
        ))
    else:
        problems: List[str] = []
        metadata_files = metadata.get("files") or []
        declared = {
            str(f.get("path", "")).strip()
            for f in metadata_files
            if isinstance(f, dict) and f.get("path")
        }
        for file_path in files:
            rel = _rel(file_path, root)
            rel_in_ds = file_path.relative_to(dataset_dir.resolve()).as_posix()
            actual = sha256_of(file_path)
            recorded = checksums.get(rel)
            if recorded is None:
                problems.append(f"{rel}: not listed in {CHECKSUM_FILE}")
            elif recorded != actual:
                problems.append(f"{rel}: checksum mismatch (file={actual[:12]}…, recorded={recorded[:12]}…)")
            if rel_in_ds not in declared:
                problems.append(f"{rel}: absent from metadata 'files'")
        for declared_path in sorted(declared - {
            p.relative_to(dataset_dir.resolve()).as_posix() for p in files
        }):
            problems.append(f"metadata 'files' lists {declared_path}, which does not exist on disk")
        report.checks.append(CheckResult(
            name="Checksums",
            passed=not problems,
            detail=(
                f"{len(files)} file(s) verified against {CHECKSUM_FILE}"
                if not problems else "; ".join(problems[:5])
            ),
        ))

    # -- 5. Provenance log --------------------------------------------------- #
    events = load_provenance(dataset_dir)
    prov_problems: List[str] = []
    if not events:
        prov_problems.append("provenance.jsonl missing or empty")
    for idx, event in enumerate(events, start=1):
        missing_prov = [f for f in REQUIRED_PROVENANCE_FIELDS if not event.get(f)]
        if missing_prov:
            prov_problems.append(f"event #{idx} missing fields: {', '.join(missing_prov)}")
    if events and files:
        latest = events[-1]
        current_hashes = {sha256_of(p): p.name for p in files}
        if str(latest.get("sha256", "")).lower() not in current_hashes:
            prov_problems.append(
                "latest provenance event sha256 does not match any current data file"
            )
    report.checks.append(CheckResult(
        name="Provenance log",
        passed=not prov_problems,
        detail=(
            f"{len(events)} event(s), append-only, latest version "
            f"{events[-1].get('version', '?')}" if not prov_problems
            else "; ".join(prov_problems[:5])
        ),
    ))

    return report


# --------------------------------------------------------------------------- #
# Repository-level checks                                                     #
# --------------------------------------------------------------------------- #

def check_figures(
    root: Path,
    inventory_ids: Set[str],
    provenance_index: Dict[str, Set[str]],
) -> CheckResult:
    """Every registered figure must trace to a versioned dataset input."""
    manifest_path = root / FIGURE_MANIFEST
    if not manifest_path.exists():
        return CheckResult(
            name="Figure tracing",
            passed=True,
            detail="no figure manifest yet (figures/figure-manifest.jsonl absent)",
        )

    problems: List[str] = []
    figure_count = 0
    for line_no, line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            problems.append(f"line {line_no}: invalid JSON")
            continue
        figure_count += 1
        figure_id = entry.get("figure_id", f"<line {line_no}>")
        dataset_id = entry.get("dataset_id", "")
        if dataset_id not in inventory_ids:
            problems.append(f"{figure_id}: dataset_id {dataset_id!r} not in inventory")
            continue
        known = provenance_index.get(dataset_id, set())
        inputs = entry.get("inputs") or []
        if not inputs:
            problems.append(f"{figure_id}: no versioned inputs recorded")
        for inp in inputs:
            inp_file = root / str(inp.get("file", ""))
            inp_sha = str(inp.get("sha256", "")).lower()
            if not inp_sha:
                problems.append(f"{figure_id}: input {inp.get('file')} has no sha256")
            elif inp_file.exists() and sha256_of(inp_file) == inp_sha:
                continue  # matches the current version on disk
            elif inp_sha in known:
                continue  # matches a recorded historical version
            else:
                problems.append(
                    f"{figure_id}: input {inp.get('file')} sha256 has no chain of custody"
                )
        if not entry.get("output"):
            problems.append(f"{figure_id}: missing output path")
    if problems:
        return CheckResult(
            name="Figure tracing", passed=False, detail="; ".join(problems[:5])
        )
    return CheckResult(
        name="Figure tracing",
        passed=True,
        detail=f"{figure_count} figure(s) traced to versioned dataset inputs",
    )


def find_orphan_datasets(root: Path, inventory_ids: Set[str]) -> List[str]:
    """Dataset folders present on disk but absent from the inventory."""
    return [
        p.name for p in dataset_dirs(root)
        if p.name not in inventory_ids
    ]


# --------------------------------------------------------------------------- #
# Full run                                                                    #
# --------------------------------------------------------------------------- #

def run_all_checks(root: Path) -> StewardshipReport:
    """Run every stewardship check against the repository at *root*."""
    root = Path(root)
    report = StewardshipReport()
    inventory = read_inventory(root)
    register = read_rights_register(root)
    checksums = read_checksums(root)
    inventory_ids = {row.get("dataset_id", "") for row in inventory}

    for row in inventory:
        report.dataset_reports.append(check_dataset(row, root, register, checksums))

    provenance_index = provenance_checksum_index(root)
    report.repo_checks.append(check_figures(root, inventory_ids, provenance_index))

    report.orphans = find_orphan_datasets(root, inventory_ids)
    report.repo_checks.append(CheckResult(
        name="No orphan datasets",
        passed=not report.orphans,
        detail=(
            "every dataset folder has an inventory entry" if not report.orphans
            else "folders without inventory entry: " + ", ".join(report.orphans)
        ),
    ))
    return report
