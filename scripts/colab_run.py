#!/usr/bin/env python3
"""Google Colab / Jupyter runner for the Data Stewardship Toolkit.

This module powers ``colab/data_stewardship_toolkit_colab.ipynb`` and can
also be used directly from a terminal:

    python scripts/colab_run.py --stage check
    python scripts/colab_run.py --stage templates
    python scripts/colab_run.py --stage preview
    python scripts/colab_run.py --stage upload --dataset sample_air_quality --actor you@example.org

Stages
------
``setup``      clone the repository (Colab) and install the toolkit
``check``      run every stewardship check and show the result table
``templates``  generate the headers-only CSV upload templates
``preview``    show which files need to be uploaded, with expected columns
``upload``     upload a filled template through the Colab upload widget
               and ingest it as a new dataset version
``dashboard``  regenerate and display the HTML stewardship dashboard
``all``        setup -> check -> templates -> preview

Every stage degrades gracefully outside Google Colab (plain Jupyter or a
terminal): widget calls become printed instructions, everything else is
identical.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:  # Google Colab detection - everything degrades gracefully elsewhere
    from google.colab import files as colab_files  # type: ignore
    from google.colab import userdata  # noqa: F401  (available for token auth)

    IN_COLAB = True
except ImportError:  # plain Jupyter / terminal
    colab_files = None  # type: ignore
    IN_COLAB = False

import pandas as pd  # Colab ships pandas; also a normal local dependency

DEFAULT_REPO_URL = "https://github.com/YOUR-USERNAME/data-stewardship-toolkit.git"
UPLOAD_DIR = Path("/content/uploads") if IN_COLAB else Path("uploads")


# --------------------------------------------------------------------------- #
# Stage: setup                                                                #
# --------------------------------------------------------------------------- #

def find_existing_repo() -> Path | None:
    """Return the toolkit root if this script already runs inside it."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src").is_dir():
            if (parent / "src" / "data_stewardship").is_dir():
                return parent
    return None


def ensure_toolkit(repo_url: str = DEFAULT_REPO_URL, target: str | None = None) -> Path:
    """Clone (when needed) and install the toolkit; return the repo root."""
    if target is None:
        target = "/content/data-stewardship-toolkit" if IN_COLAB else "./data-stewardship-toolkit"
    target_path = Path(target).resolve()

    if not target_path.exists():
        existing = find_existing_repo()
        if existing is not None:
            print(f"Using existing repository at {existing}")
            return existing
        print(f"Cloning {repo_url} ...")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(target_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Could not clone {repo_url}: {result.stderr.strip()}\n"
                "Fix REPO_URL in the setup cell (or upload the repository ZIP "
                "and unzip it to /content/data-stewardship-toolkit)."
            )
    else:
        print(f"Repository already present at {target_path}")

    print("Installing toolkit (pip install -e '.[dev]') ...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-e", f"{target_path}[dev]"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pip install failed:\n{result.stderr.strip()}")
    print("Toolkit ready.")
    return target_path


# --------------------------------------------------------------------------- #
# Stage: check                                                                #
# --------------------------------------------------------------------------- #

def run_checks(root: Path) -> pd.DataFrame:
    """Run ds-steward check --json and return a tidy per-check DataFrame."""
    root = Path(root)
    result = subprocess.run(
        [sys.executable, "-m", "data_stewardship.cli", "check", "--root", str(root), "--json"],
        capture_output=True, text=True,
    )
    payload = json.loads(result.stdout)
    rows = []
    for ds in payload["datasets"]:
        for check in ds["checks"]:
            rows.append(
                {
                    "dataset": ds["dataset_id"],
                    "check": check["name"],
                    "result": "PASS" if check["passed"] else "FAIL",
                    "detail": check["detail"],
                }
            )
    for check in payload["repo_checks"]:
        rows.append(
            {
                "dataset": "(repository)",
                "check": check["name"],
                "result": "PASS" if check["passed"] else "FAIL",
                "detail": check["detail"],
            }
        )
    frame = pd.DataFrame(rows)
    status = "COMPLIANT" if payload["ok"] else "NON-COMPLIANT"
    print(
        f"Stewardship result: {payload['passed']}/{payload['total']} checks passed "
        f"- repository is {status}"
    )
    return frame


# --------------------------------------------------------------------------- #
# Stage: templates + preview                                                  #
# --------------------------------------------------------------------------- #

def make_templates(root: Path) -> list:
    """Generate headers-only CSV templates for every dataset."""
    from data_stewardship.templates_csv import build_all_templates

    written = build_all_templates(Path(root))
    for path in written:
        print(f"Template ready: {path}")
    if not written:
        print("No templates generated (no datasets with a field dictionary).")
    return written


def preview_uploads(root: Path) -> pd.DataFrame:
    """Show which files need to be uploaded and with which columns."""
    from data_stewardship.templates_csv import upload_preview

    frame = pd.DataFrame(upload_preview(Path(root)))
    if frame.empty:
        print("Inventory is empty - register datasets first.")
        return frame
    print("FILES TO UPLOAD - one row per dataset:")
    return frame


def display_template_headers(root: Path) -> None:
    """Render every generated template (header row) as a small table."""
    from data_stewardship.templates_csv import template_dir

    for template in sorted(template_dir(Path(root)).glob("*_template.csv")):
        frame = pd.read_csv(template, nrows=0)
        print(f"\n{template.name} - columns ({len(frame.columns)}):")
        print("  " + " | ".join(map(str, frame.columns)))


# --------------------------------------------------------------------------- #
# Stage: upload + ingest                                                      #
# --------------------------------------------------------------------------- #

def download_template(root: Path, dataset_id: str) -> None:
    """Send a dataset's template to the browser (Colab) or print its path."""
    from data_stewardship.templates_csv import build_template, template_path

    path = template_path(Path(root), dataset_id)
    if not path.exists():
        built = build_template(Path(root), dataset_id)
        if built is None:
            print(f"No template for {dataset_id!r} (no field dictionary).")
            return
        path = built
    if IN_COLAB:
        colab_files.download(str(path))  # type: ignore[union-attr]
    else:
        print(f"Template available at: {path}")


def upload_and_ingest(
    root: Path,
    dataset_id: str,
    actor: str = "colab-user",
    bump: str = "minor",
    note: str = "",
) -> None:
    """Open the upload widget, then ingest the uploaded file as a new version.

    The uploaded CSV's header is validated against the dataset template;
    a mismatching file is rejected with a hint instead of being ingested.
    """
    from data_stewardship.ingest import StewardshipError, ingest_dataset
    from data_stewardship.templates_csv import template_path

    root = Path(root)
    if dataset_id is None:
        print("Select a dataset in the dropdown first.")
        return

    if IN_COLAB:
        print(f"Upload the filled template for '{dataset_id}' "
              f"(expected header file: {template_path(root, dataset_id).name}) ...")
        uploaded = colab_files.upload()  # type: ignore[union-attr]
        if not uploaded:
            print("Nothing uploaded.")
            return
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        sources = []
        for name, blob in uploaded.items():
            target = UPLOAD_DIR / name
            target.write_bytes(blob)
            sources.append(target)
    else:
        print(
            "Not running in Colab - no upload widget available.\n"
            f"Place your file next to this repository and run:\n"
            f"  ds-steward ingest --dataset {dataset_id} --file <path-to-csv> "
            f"--actor {actor} --bump {bump}"
        )
        return

    for source in sources:
        try:
            event = ingest_dataset(
                root, dataset_id=dataset_id, source_file=source,
                actor=actor, bump=bump, note=note or f"Uploaded via Colab ({source.name})",
            )
            print(
                f"Ingested {source.name} into {dataset_id} as version "
                f"{event['version']} (sha256 {event['sha256'][:12]}...)."
            )
        except StewardshipError as exc:
            print(f"REJECTED: {exc}")
    print("\nPost-ingestion verification:")
    print(run_checks(root).to_string(index=False))


# --------------------------------------------------------------------------- #
# Stage: dashboard                                                            #
# --------------------------------------------------------------------------- #

def refresh_dashboard(root: Path, output: str = "docs/dashboard.html") -> Path:
    """Regenerate the HTML dashboard and return its path."""
    from data_stewardship.report import generate_dashboard

    root = Path(root)
    out = Path(output)
    if not out.is_absolute():
        out = root / out
    generate_dashboard(root, out)
    print(f"Dashboard regenerated: {out}")
    return out


def show_dashboard(root: Path, output: str = "docs/dashboard.html",
                   download: bool = False) -> None:
    """Display the dashboard inline (notebook) or print its path."""
    from html import escape

    from IPython.display import HTML, display

    path = refresh_dashboard(Path(root), output)
    html = path.read_text(encoding="utf-8")
    if IN_COLAB or _in_notebook():
        display(
            HTML(
                '<iframe srcdoc="' + escape(html) + '" '
                'style="width:100%;height:640px;border:1px solid #ccc;border-radius:8px" '
                'sandbox="allow-same-origin"></iframe>'
            )
        )
    if download and IN_COLAB:
        colab_files.download(str(path))  # type: ignore[union-attr]
    else:
        print(f"Dashboard file: {path}")


def _in_notebook() -> bool:
    try:
        from IPython import get_ipython

        return get_ipython() is not None
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="colab_run", description="Run the Data Stewardship Toolkit stages "
        "in Google Colab or locally."
    )
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--root", default=None,
                        help="existing repository root (skips clone)")
    parser.add_argument("--stage", default="all",
                        choices=("setup", "check", "templates", "preview",
                                 "upload", "dashboard", "all"))
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--actor", default="colab-user")
    parser.add_argument("--bump", default="minor", choices=("patch", "minor", "major"))
    parser.add_argument("--note", default="")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else ensure_toolkit(args.repo_url)
    print(f"Repository root: {root}\n")

    if args.stage in ("setup", "all"):
        run_checks(root)
    if args.stage in ("check", "all"):
        frame = run_checks(root)
        print(frame.to_string(index=False, max_colwidth=60))
    if args.stage in ("templates", "all"):
        make_templates(root)
        display_template_headers(root)
    if args.stage in ("preview", "all"):
        print()
        preview_uploads(root)
        display_template_headers(root)
    if args.stage == "upload":
        upload_and_ingest(root, args.dataset, args.actor, args.bump, args.note)
    if args.stage == "dashboard":
        show_dashboard(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
