"""Tests for the ds-steward command line interface."""

from __future__ import annotations

import json
from pathlib import Path

from data_stewardship import __version__
from data_stewardship.cli import main


def test_version_flag(capsys):
    assert main(["version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_check_command_passes_on_shipped_repo(repo_root: Path, capsys):
    exit_code = main(["check", "--root", str(repo_root)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "COMPLIANT" in out
    assert "[FAIL]" not in out


def test_check_json_report_is_parseable(repo_root: Path, capsys):
    exit_code = main(["check", "--root", str(repo_root), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["passed"] == payload["total"]
    assert {d["dataset_id"] for d in payload["datasets"]} >= {
        "sample_air_quality", "sample_biodiversity", "sample_water_quality",
    }


def test_check_command_fails_on_broken_repo(tmp_path, tmp_repo, capsys):
    (tmp_repo / "datasets" / "test_ds" / "metadata.yaml").unlink()
    exit_code = main(["check", "--root", str(tmp_repo)])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "NON-COMPLIANT" in out


def test_ingest_command_end_to_end(tmp_path, tmp_repo, extra_raw_file, capsys):
    exit_code = main(
        [
            "ingest", "--root", str(tmp_repo), "--dataset", "test_ds",
            "--file", str(extra_raw_file), "--actor", "cli-tester",
            "--bump", "minor", "--note", "cli round trip",
        ]
    )
    assert exit_code == 0
    assert "0.1.0" in capsys.readouterr().out


def test_figure_command_end_to_end(tmp_path, tmp_repo, capsys):
    figure = tmp_repo / "figures" / "fig_cli.png"
    figure.write_bytes(b"PNG")
    exit_code = main(
        [
            "figure", "--root", str(tmp_repo), "--figure-id", "fig_cli",
            "--dataset", "test_ds", "--output", "figures/fig_cli.png",
            "--script", "scripts/make_fig_cli.py", "--actor", "cli-tester",
        ]
    )
    assert exit_code == 0
    assert "registered" in capsys.readouterr().out


def test_dashboard_command_generates_html(tmp_path, tmp_repo):
    output = tmp_path / "dash.html"
    assert main(["dashboard", "--root", str(tmp_repo), "--output", str(output)]) == 0
    html = output.read_text(encoding="utf-8")
    assert "Data Stewardship Toolkit" in html
    assert "Automated check results" in html
    assert "<!DOCTYPE html>" in html


def test_dashboard_on_shipped_repo_mentions_datasets(repo_root: Path, tmp_path):
    output = tmp_path / "dash.html"
    main(["dashboard", "--root", str(repo_root), "--output", str(output)])
    html = output.read_text(encoding="utf-8")
    for dataset_id in ("sample_air_quality", "sample_biodiversity", "sample_water_quality"):
        assert dataset_id in html
