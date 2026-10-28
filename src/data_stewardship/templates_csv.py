"""CSV data templates and upload preview.

Every dataset's ``metadata.yaml`` declares a ``fields`` list - the
canonical column dictionary for that dataset. This module turns that
dictionary into:

* **downloadable CSV templates** (header row only) that data providers
  fill in and upload, and
* an **upload preview** describing exactly which files need to be
  uploaded for each dataset, with the expected columns and their
  current data status.

Ingest-time header validation (:func:`data_stewardship.ingest.ingest_dataset`)
compares an uploaded CSV's header against the same ``fields`` list, so a
file that does not follow the template is rejected before it can pollute
a versioned dataset.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

TEMPLATES_CSV_DIR = "templates/csv"


def template_dir(root: Path) -> Path:
    return Path(root) / TEMPLATES_CSV_DIR


def template_path(root: Path, dataset_id: str) -> Path:
    return template_dir(root) / f"{dataset_id}_template.csv"


def expected_columns(metadata: dict) -> List[dict]:
    """The field dictionary declared in a dataset's metadata."""
    fields = metadata.get("fields") or []
    return [f for f in fields if isinstance(f, dict) and f.get("name")]


def csv_header_of(path: Path) -> Optional[List[str]]:
    """Read the header row of a CSV file (BOM-tolerant), or None."""
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if not row or all(not str(cell).strip() for cell in row):
                continue  # skip leading blank lines
            return [str(cell).strip() for cell in row]
    return None


def headers_match(metadata: dict, header: List[str]) -> bool:
    """True when a CSV header equals the metadata field names in order."""
    expected = [f["name"] for f in expected_columns(metadata)]
    return bool(expected) and [h.lower() for h in header] == [e.lower() for e in expected]


def build_template(root: Path, dataset_id: str) -> Optional[Path]:
    """Write a headers-only CSV template for *dataset_id*.

    Returns the path of the written template, or None when the dataset
    has no metadata or no field dictionary to derive headers from.
    """
    from .checks import load_metadata, read_inventory

    root = Path(root)
    row = next(
        (r for r in read_inventory(root) if r.get("dataset_id") == dataset_id), None
    )
    if row is None:
        return None
    metadata = load_metadata(root / row["path"]) or {}
    fields = expected_columns(metadata)
    if not fields:
        return None

    out = template_path(root, dataset_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([f["name"] for f in fields])
    return out


def build_all_templates(root: Path) -> List[Path]:
    """Build a CSV template for every dataset that declares fields."""
    from .checks import read_inventory

    root = Path(root)
    built: List[Path] = []
    for row in read_inventory(root):
        path = build_template(root, row.get("dataset_id", ""))
        if path is not None:
            built.append(path)
    return built


def upload_preview(root: Path) -> List[Dict[str, str]]:
    """Describe what still needs to be uploaded, one row per dataset.

    Rows carry: dataset_id, title, current version, template file,
    expected columns (name: description, pipe-separated) and the data
    files already under stewardship.
    """
    from .checks import data_files, load_metadata, read_inventory

    root = Path(root)
    rows: List[Dict[str, str]] = []
    for row in read_inventory(root):
        dataset_id = row.get("dataset_id", "")
        metadata = load_metadata(root / row.get("path", "")) or {}
        fields = expected_columns(metadata)
        present = [
            p.name for p in data_files(root / row.get("path", ""))
        ]
        rows.append(
            {
                "dataset_id": dataset_id,
                "title": row.get("title", ""),
                "version": row.get("version", ""),
                "template_file": template_path(root, dataset_id).name
                if fields
                else "(no field dictionary)",
                "expected_columns": "; ".join(
                    f"{f['name']} ({f.get('type', '?')})" for f in fields
                ),
                "data_files_present": ", ".join(present) if present else "-",
                "steward": row.get("steward", ""),
            }
        )
    return rows
