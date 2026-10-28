"""Tests for CSV upload templates and header validation."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from conftest import copy_repo

import data_stewardship.checks as checks
from data_stewardship.checks import run_all_checks
from data_stewardship.ingest import StewardshipError, ingest_dataset
from data_stewardship.templates_csv import (
    build_all_templates,
    build_template,
    csv_header_of,
    expected_columns,
    headers_match,
    upload_preview,
)


# --------------------------------------------------------------------------- #
# Template generation                                                         #
# --------------------------------------------------------------------------- #

def test_templates_generated_for_every_dataset(repo_root: Path, tmp_path: Path):
    repo = copy_repo(repo_root, tmp_path / "repo")
    built = build_all_templates(repo)
    ids = {row["dataset_id"] for row in checks.read_inventory(repo)}
    built_ids = {p.name.replace("_template.csv", "") for p in built}
    assert built_ids == ids
    for path in built:
        assert path.exists() and path.stat().st_size > 0


def test_shipped_templates_exist_and_match_metadata(repo_root: Path):
    for row in checks.read_inventory(repo_root):
        template = repo_root / "templates" / "csv" / f"{row['dataset_id']}_template.csv"
        assert template.exists(), f"shipped template missing: {template}"
        metadata = checks.load_metadata(repo_root / row["path"])
        expected = [f["name"] for f in expected_columns(metadata)]
        assert csv_header_of(template) == expected


def test_template_is_headers_only(repo_root: Path):
    template = repo_root / "templates" / "csv" / "sample_air_quality_template.csv"
    with open(template, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 1  # header row only, no example data rows
    assert rows[0][0] == "date"


def test_unknown_dataset_yields_no_template(tmp_repo: Path):
    assert build_template(tmp_repo, "ghost") is None


# --------------------------------------------------------------------------- #
# Header helpers                                                              #
# --------------------------------------------------------------------------- #

def test_headers_match_is_case_insensitive():
    metadata = {"fields": [{"name": "Date"}, {"name": "Value"}]}
    assert headers_match(metadata, ["date", "value"])
    assert not headers_match(metadata, ["date", "wrong"])
    assert not headers_match(metadata, ["date"])  # missing column


def test_csv_header_of_skips_blank_lines(tmp_path: Path):
    f = tmp_path / "x.csv"
    f.write_text("\n\na,b\n1,2\n", encoding="utf-8")
    assert csv_header_of(f) == ["a", "b"]


def test_upload_preview_lists_expected_columns(repo_root: Path):
    rows = {r["dataset_id"]: r for r in upload_preview(repo_root)}
    aq = rows["sample_air_quality"]
    assert "pm25_ugm3" in aq["expected_columns"]
    assert aq["template_file"] == "sample_air_quality_template.csv"
    assert "air_quality_daily_2024-01.csv" in aq["data_files_present"]


# --------------------------------------------------------------------------- #
# Ingest-time header gate                                                     #
# --------------------------------------------------------------------------- #

@pytest.fixture()
def wrong_header_file(tmp_path: Path) -> Path:
    f = tmp_path / "wrong.csv"
    f.write_text("date,temperature\n2024-02-01,8.1\n", encoding="utf-8")
    return f


def test_ingest_rejects_header_mismatch(tmp_repo: Path, wrong_header_file: Path):
    with pytest.raises(StewardshipError) as err:
        ingest_dataset(tmp_repo, "test_ds", wrong_header_file, actor="tester")
    assert "does not match the field dictionary" in str(err.value)
    assert "_template.csv" in str(err.value)  # points to the template
    # nothing was written: no provenance, no checksum, version unchanged
    assert not (tmp_repo / "datasets" / "test_ds" / "data" / "wrong.csv").exists()
    metadata = yaml.safe_load(
        (tmp_repo / "datasets" / "test_ds" / "metadata.yaml").read_text(encoding="utf-8")
    )
    assert metadata["version"] == "0.0.1"  # seed version, unchanged


def test_ingest_force_bypasses_header_gate(tmp_repo: Path, wrong_header_file: Path):
    event = ingest_dataset(
        tmp_repo, "test_ds", wrong_header_file, actor="tester",
        note="forced", validate_headers=False,
    )
    assert event["version"] == "0.0.2"  # 0.0.1 (seed) + default patch bump
    # ...but the repository-level header check now fails, as designed
    report = run_all_checks(tmp_repo)
    header_check = next(
        c for ds in report.dataset_reports for c in ds.checks if c.name == "Column headers"
    )
    assert not header_check.passed


def test_column_headers_check_detects_tampered_data_file(tmp_path, tmp_repo):
    data_file = tmp_repo / "datasets" / "test_ds" / "data" / "values.csv"
    data_file.write_text("date,renamed_column\n2024-01-01,1.5\n", encoding="utf-8")
    report = run_all_checks(tmp_repo)
    header_check = next(
        c for ds in report.dataset_reports for c in ds.checks if c.name == "Column headers"
    )
    assert not header_check.passed
    assert "does not match metadata fields" in header_check.detail
