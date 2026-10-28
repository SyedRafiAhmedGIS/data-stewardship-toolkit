"""Tests for versioned ingestion and figure chain-of-custody."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from data_stewardship.checks import run_all_checks
from data_stewardship.ingest import (
    StewardshipError,
    ingest_dataset,
    next_version,
    register_figure,
)


# --------------------------------------------------------------------------- #
# Ingestion                                                                    #
# --------------------------------------------------------------------------- #

def test_ingest_bumps_version_and_updates_metadata(tmp_path, tmp_repo, extra_raw_file):
    event = ingest_dataset(
        tmp_repo, "test_ds", extra_raw_file, actor="tester", bump="minor", note="batch 2"
    )
    assert event["version"] == "0.1.0"
    metadata = yaml.safe_load(
        (tmp_repo / "datasets" / "test_ds" / "metadata.yaml").read_text(encoding="utf-8")
    )
    assert metadata["version"] == "0.1.0"
    assert any(f["path"] == "data/values_v2.csv" for f in metadata["files"])
    assert metadata["provenance"][-1]["sha256"] == event["sha256"]


def test_ingest_records_checksum_in_registry(tmp_path, tmp_repo, extra_raw_file):
    ingest_dataset(tmp_repo, "test_ds", extra_raw_file, actor="tester")
    sums = (tmp_repo / "checksums" / "sha256sums.txt").read_text(encoding="utf-8")
    event_sha = _extract_sha(sums, "values_v2.csv")
    assert event_sha
    assert event_sha == _sha256_of_file(tmp_repo / "datasets" / "test_ds" / "data" / "values_v2.csv")


def test_ingest_appends_provenance_event(tmp_path, tmp_repo, extra_raw_file):
    event = ingest_dataset(tmp_repo, "test_ds", extra_raw_file, actor="alice")
    lines = (tmp_repo / "datasets" / "test_ds" / "provenance.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    assert len(lines) == 2  # one seed event from the fixture + this ingestion
    stored = json.loads(lines[-1])
    for key in ("timestamp", "event", "version", "file", "sha256", "actor"):
        assert key in stored
    assert stored["actor"] == "alice"
    assert stored["sha256"] == event["sha256"]


def test_ingest_syncs_inventory_row(tmp_path, tmp_repo, extra_raw_file):
    ingest_dataset(tmp_repo, "test_ds", extra_raw_file, actor="tester", bump="major")
    inventory_text = (tmp_repo / "inventory" / "datasets.csv").read_text(encoding="utf-8")
    assert "1.0.0" in inventory_text


def test_repo_stays_compliant_after_ingestion(tmp_path, tmp_repo, extra_raw_file):
    ingest_dataset(tmp_repo, "test_ds", extra_raw_file, actor="tester", bump="minor")
    assert run_all_checks(tmp_repo).ok


def test_ingest_requires_inventory_entry(tmp_path, tmp_repo, extra_raw_file):
    with pytest.raises(StewardshipError, match="not in inventory"):
        ingest_dataset(tmp_repo, "ghost_dataset", extra_raw_file)


def test_reingesting_same_file_keeps_single_metadata_entry(tmp_path, tmp_repo, extra_raw_file):
    ingest_dataset(tmp_repo, "test_ds", extra_raw_file, actor="tester")
    ingest_dataset(tmp_repo, "test_ds", extra_raw_file, actor="tester", bump="minor")
    metadata = yaml.safe_load(
        (tmp_repo / "datasets" / "test_ds" / "metadata.yaml").read_text(encoding="utf-8")
    )
    entries = [f for f in metadata["files"] if f["path"] == "data/values_v2.csv"]
    assert len(entries) == 1
    assert metadata["version"] == "0.1.0"  # 0.0.1 (seed) -> patch -> minor


def test_next_version_previews_bump(tmp_repo):
    assert next_version(tmp_repo, "test_ds", "minor") == "0.1.0"
    assert next_version(tmp_repo, "missing_ds") is None


# --------------------------------------------------------------------------- #
# Figure chain of custody                                                      #
# --------------------------------------------------------------------------- #

def _sha256_of_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract_sha(sums_text: str, filename: str) -> str:
    for line in sums_text.splitlines():
        if filename in line:
            return line.split()[0]
    return ""


def test_registered_figure_passes_chain_of_custody(tmp_path, tmp_repo, extra_raw_file):
    ingest_dataset(tmp_repo, "test_ds", extra_raw_file, actor="tester")
    figure = tmp_repo / "figures" / "fig01.png"
    figure.write_bytes(b"PNG")
    register_figure(
        tmp_repo,
        figure_id="fig01_test",
        dataset_id="test_ds",
        output_path=Path("figures/fig01.png"),
        script_path=Path("scripts/make_fig01.py"),
        actor="tester",
    )
    report = run_all_checks(tmp_repo)
    figures_check = next(c for c in report.repo_checks if c.name == "Figure tracing")
    assert figures_check.passed, figures_check.detail


def test_tampered_figure_input_is_detected(tmp_path, tmp_repo, extra_raw_file):
    ingest_dataset(tmp_repo, "test_ds", extra_raw_file, actor="tester")
    manifest = tmp_repo / "figures" / "figure-manifest.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "registered": "2024-01-01T00:00:00Z",
                "figure_id": "fig_bad",
                "dataset_id": "test_ds",
                "dataset_version": "0.0.0",
                "inputs": [{"file": "datasets/test_ds/data/values.csv", "sha256": "0" * 64}],
                "script": "scripts/x.py",
                "output": "figures/x.png",
                "actor": "tester",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = run_all_checks(tmp_repo)
    figures_check = next(c for c in report.repo_checks if c.name == "Figure tracing")
    assert not figures_check.passed
    assert "chain of custody" in figures_check.detail


def test_figure_manifest_rejects_unknown_dataset(tmp_path, tmp_repo):
    manifest = tmp_repo / "figures" / "figure-manifest.jsonl"
    manifest.write_text(
        json.dumps(
            {
                "registered": "2024-01-01T00:00:00Z",
                "figure_id": "fig_ghost",
                "dataset_id": "ghost_ds",
                "dataset_version": "1.0.0",
                "inputs": [{"file": "datasets/ghost_ds/data/x.csv", "sha256": "a" * 64}],
                "script": "scripts/x.py",
                "output": "figures/x.png",
                "actor": "tester",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = run_all_checks(tmp_repo)
    figures_check = next(c for c in report.repo_checks if c.name == "Figure tracing")
    assert not figures_check.passed
    assert "not in inventory" in figures_check.detail
