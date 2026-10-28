"""Tests for the stewardship compliance checks.

The first group runs against the *real* repository - this is what makes
CI a genuine gate: adding a dataset without a licence, metadata or
checksum breaks the build. The second group deliberately tampers with a
synthetic repository and asserts that each violation is detected.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from conftest import copy_repo

from data_stewardship.checks import (
    read_checksums,
    read_inventory,
    read_rights_register,
    run_all_checks,
)


# --------------------------------------------------------------------------- #
# Repository-level guard tests (run against the shipped repository)           #
# --------------------------------------------------------------------------- #

def test_shipped_repository_is_fully_compliant(repo_root: Path):
    report = run_all_checks(repo_root)
    assert report.ok, [
        c.detail
        for ds in report.dataset_reports
        for c in ds.failed
    ] + [c.detail for c in report.repo_checks if not c.passed]


def test_every_dataset_has_metadata_with_required_fields(repo_root: Path):
    import data_stewardship.checks as checks

    required = checks.REQUIRED_METADATA_FIELDS
    for row in read_inventory(repo_root):
        metadata = checks.load_metadata(repo_root / row["path"])
        assert metadata is not None, f"{row['dataset_id']}: metadata.yaml missing"
        missing = required - set(metadata)
        assert not missing, f"{row['dataset_id']}: metadata missing {missing}"


def test_every_dataset_licence_is_registered(repo_root: Path):
    register = read_rights_register(repo_root)
    assert register, "rights register must not be empty"
    for row in read_inventory(repo_root):
        assert row["licence_id"] in register, (
            f"{row['dataset_id']} uses unregistered licence {row['licence_id']}"
        )


def test_every_data_file_checksum_matches(repo_root: Path):
    checksums = read_checksums(repo_root)
    import data_stewardship.checks as checks

    for row in read_inventory(repo_root):
        for file_path in checks.data_files(repo_root / row["path"]):
            rel = file_path.resolve().relative_to(repo_root.resolve()).as_posix()
            assert rel in checksums, f"{rel} is not in checksums/sha256sums.txt"
            assert checks.sha256_of(file_path) == checksums[rel], f"{rel} checksum drift"


def test_every_dataset_is_cc0_licensed(repo_root: Path):
    register = read_rights_register(repo_root)
    for row in read_inventory(repo_root):
        spdx = register[row["licence_id"]]["spdx"]
        assert spdx == "CC0-1.0", f"{row['dataset_id']} demo data must stay CC0, found {spdx}"


# --------------------------------------------------------------------------- #
# Mutation tests (tamper with a synthetic repository)                         #
# --------------------------------------------------------------------------- #

def _copy_with_tamper(tmp_path: Path, repo: Path, mutate) -> Path:
    target = copy_repo(repo, tmp_path / "mutated")
    mutate(target)
    return target


def test_missing_metadata_is_detected(tmp_path, tmp_repo):
    def mutate(root: Path):
        (root / "datasets" / "test_ds" / "metadata.yaml").unlink()

    report = run_all_checks(_copy_with_tamper(tmp_path, tmp_repo, mutate))
    ds = report.dataset_reports[0]
    metadata_check = next(c for c in ds.checks if c.name == "Metadata file")
    assert not metadata_check.passed and not report.ok


def test_unregistered_licence_is_detected(tmp_path, tmp_repo):
    def mutate(root: Path):
        path = root / "datasets" / "test_ds" / "metadata.yaml"
        metadata = yaml.safe_load(path.read_text(encoding="utf-8"))
        metadata["licence"]["licence_id"] = "unknown_licence"
        path.write_text(yaml.safe_dump(metadata, sort_keys=False), encoding="utf-8")

    report = run_all_checks(_copy_with_tamper(tmp_path, tmp_repo, mutate))
    licence_check = next(
        c for ds in report.dataset_reports for c in ds.checks if c.name == "Licence and rights"
    )
    assert not licence_check.passed
    assert "not in rights-register" in licence_check.detail


def test_tampered_checksum_is_detected(tmp_path, tmp_repo):
    def mutate(root: Path):
        data_file = root / "datasets" / "test_ds" / "data" / "values.csv"
        data_file.write_text(
            data_file.read_text(encoding="utf-8") + "2024-01-03,99.0\n", encoding="utf-8"
        )

    report = run_all_checks(_copy_with_tamper(tmp_path, tmp_repo, mutate))
    checksum_check = next(
        c for ds in report.dataset_reports for c in ds.checks if c.name == "Checksums"
    )
    assert not checksum_check.passed
    assert "mismatch" in checksum_check.detail


def test_missing_checksum_entry_is_detected(tmp_path, tmp_repo):
    def mutate(root: Path):
        sums = root / "checksums" / "sha256sums.txt"
        lines = [l for l in sums.read_text(encoding="utf-8").splitlines()
                 if "values.csv" not in l]
        sums.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = run_all_checks(_copy_with_tamper(tmp_path, tmp_repo, mutate))
    checksum_check = next(
        c for ds in report.dataset_reports for c in ds.checks if c.name == "Checksums"
    )
    assert not checksum_check.passed
    assert "not listed" in checksum_check.detail


def test_orphan_dataset_folder_is_detected(tmp_path, tmp_repo):
    def mutate(root: Path):
        orphan = root / "datasets" / "sneaky_unregistered"
        (orphan / "data").mkdir(parents=True)
        (orphan / "data" / "x.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    report = run_all_checks(_copy_with_tamper(tmp_path, tmp_repo, mutate))
    assert "sneaky_unregistered" in report.orphans
    assert not report.ok


def test_empty_provenance_is_flagged_after_manual_data_drop(tmp_path, tmp_repo):
    """A data file added without ds-steward ingest breaks the provenance gate."""
    def mutate(root: Path):
        new_file = root / "datasets" / "test_ds" / "data" / "extra.csv"
        new_file.write_text("date,value\n2024-02-01,7.0\n", encoding="utf-8")

    report = run_all_checks(_copy_with_tamper(tmp_path, tmp_repo, mutate))
    checksum_check = next(
        c for ds in report.dataset_reports for c in ds.checks if c.name == "Checksums"
    )
    assert not checksum_check.passed  # no checksum recorded for extra.csv


# --------------------------------------------------------------------------- #
# Version bump rules                                                          #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("version", "bump", "expected"),
    [
        ("1.0.0", "patch", "1.0.1"),
        ("1.0.0", "minor", "1.1.0"),
        ("1.0.0", "major", "2.0.0"),
        ("0.0.0", "patch", "0.0.1"),
    ],
)
def test_bump_version(version, bump, expected):
    from data_stewardship.ingest import bump_version

    assert bump_version(version, bump) == expected


def test_bump_version_rejects_bad_input():
    from data_stewardship.ingest import StewardshipError, bump_version

    with pytest.raises(StewardshipError):
        bump_version("1.0", "patch")
    with pytest.raises(StewardshipError):
        bump_version("1.0.0", "mega")
