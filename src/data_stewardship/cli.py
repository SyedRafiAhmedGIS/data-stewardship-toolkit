"""Command line interface: the ``ds-steward`` command.

Subcommands
-----------
``check``      Run every stewardship compliance check (exit 1 on failure).
``ingest``     Ingest a data file into a dataset as a new version.
``figure``     Register a published figure against a versioned dataset input.
``dashboard``  Generate the self-contained HTML stewardship dashboard.
``version``    Print the toolkit version.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .checks import run_all_checks
from .ingest import StewardshipError, ingest_dataset, register_figure


def _print_report(report, root: Path) -> None:
    width = 72
    print("=" * width)
    print("DATA STEWARDSHIP CHECKS")
    print(f"Repository: {root.resolve()}")
    print("=" * width)
    for ds in report.dataset_reports:
        print(f"\n  dataset: {ds.dataset_id}")
        for check in ds.checks:
            mark = "PASS" if check.passed else "FAIL"
            print(f"    [{mark}] {check.name:<22} {check.detail}")
    if report.orphans:
        print(f"\n  orphan dataset folders: {', '.join(report.orphans)}")
    print()
    for check in report.repo_checks:
        mark = "PASS" if check.passed else "FAIL"
        print(f"  [{mark}] {check.name:<22} {check.detail}")
    print("-" * width)
    status = "COMPLIANT" if report.ok else "NON-COMPLIANT"
    print(
        f"SUMMARY: {report.passed_checks}/{report.total_checks} checks passed "
        f"- repository is {status}"
    )
    print("=" * width)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ds-steward",
        description=(
            "Data Stewardship Toolkit - enforce licences, metadata, checksums "
            "and versioned ingestion for every dataset."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="run all stewardship checks")
    p_check.add_argument("--root", default=".", help="repository root (default: .)")
    p_check.add_argument("--json", action="store_true", dest="as_json",
                         help="emit the report as JSON (machine readable)")

    p_ing = sub.add_parser("ingest", help="ingest a data file as a new dataset version")
    p_ing.add_argument("--dataset", required=True, help="dataset_id from the inventory")
    p_ing.add_argument("--file", required=True, help="source file to ingest")
    p_ing.add_argument("--actor", default="unknown", help="who performed the ingestion")
    p_ing.add_argument("--bump", choices=("major", "minor", "patch"),
                       default="patch", help="semantic version component to bump")
    p_ing.add_argument("--note", default="", help="free-text note recorded in provenance")
    p_ing.add_argument("--root", default=".", help="repository root (default: .)")

    p_fig = sub.add_parser("figure", help="register a figure against versioned inputs")
    p_fig.add_argument("--figure-id", required=True, help="unique figure identifier")
    p_fig.add_argument("--dataset", required=True, help="dataset_id the figure is based on")
    p_fig.add_argument("--output", required=True, help="path of the published figure")
    p_fig.add_argument("--script", required=True, help="script that produced the figure")
    p_fig.add_argument("--actor", default="unknown")
    p_fig.add_argument("--caption", default="", help="short figure caption")
    p_fig.add_argument("--root", default=".", help="repository root (default: .)")

    p_dash = sub.add_parser("dashboard", help="generate the HTML stewardship dashboard")
    p_dash.add_argument("--output", default="docs/dashboard.html",
                        help="output HTML path (default: docs/dashboard.html)")
    p_dash.add_argument("--root", default=".", help="repository root (default: .)")

    sub.add_parser("version", help="print the toolkit version")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(getattr(args, "root", ".")).resolve()

    try:
        if args.command == "version":
            print(f"data-stewardship-toolkit {__version__}")
            return 0

        if args.command == "check":
            report = run_all_checks(root)
            if args.as_json:
                payload = {
                    "ok": report.ok,
                    "passed": report.passed_checks,
                    "total": report.total_checks,
                    "orphans": report.orphans,
                    "datasets": [
                        {
                            "dataset_id": ds.dataset_id,
                            "ok": ds.ok,
                            "checks": [
                                {"name": c.name, "passed": c.passed, "detail": c.detail}
                                for c in ds.checks
                            ],
                        }
                        for ds in report.dataset_reports
                    ],
                    "repo_checks": [
                        {"name": c.name, "passed": c.passed, "detail": c.detail}
                        for c in report.repo_checks
                    ],
                }
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_report(report, root)
            return 0 if report.ok else 1

        if args.command == "ingest":
            event = ingest_dataset(
                root,
                dataset_id=args.dataset,
                source_file=Path(args.file),
                actor=args.actor,
                bump=args.bump,
                note=args.note,
            )
            print(
                f"Ingested {event['file']} into {args.dataset} "
                f"as version {event['version']} (sha256 {event['sha256'][:12]}...)."
            )
            print("Provenance event appended; checksum registry updated.")
            return 0

        if args.command == "figure":
            entry = register_figure(
                root,
                figure_id=args.figure_id,
                dataset_id=args.dataset,
                output_path=Path(args.output),
                script_path=Path(args.script),
                actor=args.actor,
                caption=args.caption,
            )
            n_inputs = len(entry["inputs"])
            print(
                f"Figure {args.figure_id} registered against {args.dataset} "
                f"version {entry['dataset_version']} ({n_inputs} versioned input(s), "
                f"chain of custody recorded)."
            )
            return 0

        if args.command == "dashboard":
            from .report import generate_dashboard

            output = Path(args.output)
            if not output.is_absolute():
                output = root / output
            generate_dashboard(root, output)
            print(f"Dashboard written to {output}")
            return 0

    except StewardshipError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return parser.error(f"unknown command {args.command!r}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
