#!/usr/bin/env python3
"""Demo: build a published figure artifact and register its provenance.

Reads the versioned sample_air_quality dataset, computes a small summary
table (mean PM2.5 per monitoring site), writes it to figures/, and calls
``ds-steward figure`` so the output is traceable to a versioned input.

Run from the repository root:

    python scripts/demo_make_figure.py
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from data_stewardship.ingest import register_figure  # noqa: E402

DATASET_ID = "sample_air_quality"
FIGURE_ID = "fig01_air_quality_summary"
OUTPUT_REL = "figures/fig01_air_quality_summary.csv"
SCRIPT_REL = "scripts/demo_make_figure.py"


def main() -> int:
    data_dir = REPO_ROOT / "datasets" / DATASET_ID / "data"
    source_files = sorted(data_dir.glob("*.csv"))
    if not source_files:
        print(f"No data files under {data_dir}; ingest the dataset first.", file=sys.stderr)
        return 1

    totals: dict = defaultdict(lambda: [0.0, 0])
    for source in source_files:
        with open(source, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                site = row["site_id"]
                totals[site][0] += float(row["pm25_ugm3"])
                totals[site][1] += 1

    output_path = REPO_ROOT / OUTPUT_REL
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["site_id", "mean_pm25_ugm3", "n_observations", "source_dataset"])
        for site in sorted(totals):
            mean, n = totals[site]
            writer.writerow([site, f"{mean / n:.2f}", n, DATASET_ID])
    print(f"Wrote {OUTPUT_REL} ({len(totals)} sites).")

    entry = register_figure(
        REPO_ROOT,
        figure_id=FIGURE_ID,
        dataset_id=DATASET_ID,
        output_path=Path(OUTPUT_REL),
        script_path=Path(SCRIPT_REL),
        actor="demo-steward",
        caption="Mean PM2.5 per monitoring site, January 2024 (synthetic demo data)",
    )
    print(
        f"Registered {FIGURE_ID} against {DATASET_ID} version "
        f"{entry['dataset_version']} ({len(entry['inputs'])} versioned input(s))."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
