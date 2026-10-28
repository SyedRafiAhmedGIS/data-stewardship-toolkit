"""Shared pytest fixtures.

Two kinds of fixtures are provided:

* ``repo_root`` - the real repository, used for repository-level tests that
  guard the shipped demo datasets (so CI fails if someone adds a dataset
  without a licence, metadata or checksum).
* ``tmp_repo`` - a minimal, fully valid synthetic repository built with the
  toolkit's own API, which mutation tests then deliberately break.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


def build_minimal_repo(target: Path) -> Path:
    """Create the smallest fully compliant repository at *target*."""
    (target / "inventory").mkdir(parents=True)
    (target / "checksums").mkdir(parents=True)
    (target / "figures").mkdir(parents=True)
    dataset_dir = target / "datasets" / "test_ds"
    (dataset_dir / "data").mkdir(parents=True)

    (target / "inventory" / "datasets.csv").write_text(
        "dataset_id,title,path,version,licence_id,status,steward,updated,description\n"
        "test_ds,Test Dataset,datasets/test_ds,0.0.0,cc0_test,registered,"
        "steward@example.org,2024-01-01,A synthetic minimal dataset.\n",
        encoding="utf-8",
    )
    (target / "inventory" / "rights-register.csv").write_text(
        "licence_id,spdx,name,url,rights_holder,applies_to,notes\n"
        "cc0_test,CC0-1.0,CC0 1.0 Universal,https://creativecommons.org/publicdomain/zero/1.0/,"
        "Test Lab,datasets/test_ds,Demo licence\n",
        encoding="utf-8",
    )
    metadata = {
        "dataset_id": "test_ds",
        "title": "Test Dataset",
        "description": "A synthetic minimal dataset.",
        "version": "0.0.0",
        "created": "2024-01-01",
        "steward": "steward@example.org",
        "language": "en",
        "licence": {
            "licence_id": "cc0_test",
            "spdx": "CC0-1.0",
            "name": "CC0 1.0 Universal",
            "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        },
        "rights_holder": "Test Lab",
        "keywords": ["test"],
        "fields": [
            {"name": "date", "type": "date", "description": "Observation date"},
            {"name": "value", "type": "number", "description": "Measured value"},
        ],
        "files": [],
    }
    (dataset_dir / "metadata.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (dataset_dir / "data" / "values.csv").write_text(
        "date,value\n2024-01-01,1.5\n2024-01-02,2.5\n", encoding="utf-8"
    )

    # Register the seed file through the toolkit's own ingestion path so the
    # minimal repo starts fully compliant (checksum + provenance recorded).
    from data_stewardship.ingest import ingest_dataset

    ingest_dataset(
        target, "test_ds", dataset_dir / "data" / "values.csv",
        actor="fixture", bump="patch", note="initial seed ingestion",
    )
    return target


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """A valid minimal repository that tests may freely mutate."""
    return build_minimal_repo(tmp_path / "mini-repo")


@pytest.fixture()
def extra_raw_file(tmp_path: Path) -> Path:
    """A small raw file standing in for a real ingestion source."""
    raw = tmp_path / "values_v2.csv"
    raw.write_text("date,value\n2024-01-01,1.5\n2024-01-02,2.5\n2024-01-03,3.5\n", encoding="utf-8")
    return raw


def copy_repo(source: Path, target: Path) -> Path:
    """Copy a repository while ignoring caches and build artifacts."""
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.egg-info", ".pytest_cache", ".git", ".venv"
        ),
    )
    return target
