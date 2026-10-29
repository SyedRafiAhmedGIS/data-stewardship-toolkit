# Data Stewardship Toolkit

[![CI](https://github.com/SyedRafiAhmedGIS/data-stewardship-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/SyedRafiAhmedGIS/data-stewardship-toolkit/actions/workflows/ci.yml)
[![code licence: MIT](https://img.shields.io/badge/code%20licence-MIT-green.svg)](LICENSE)
[![demo data licence: CC0-1.0](https://img.shields.io/badge/demo%20data-CC0--1.0-blue.svg)](inventory/rights-register.csv)
[![python: 3.9+](https://img.shields.io/badge/python-3.9%2B-informational.svg)](pyproject.toml)
[![tests: pytest](https://img.shields.io/badge/tests-pytest-6769ab.svg)](tests/)

A small, dependency-light toolkit that makes **reproducible data
stewardship automatic**: every dataset in the repository has an inventory
entry, complete metadata, a registered licence and a verified checksum -
and every published figure traces back to a versioned dataset input. If
any of that stops being true, CI fails.

The toolkit ships with three CC0-licensed synthetic demo datasets so the
pipeline is green out of the box: clone, install, and watch every check
pass.

## What the toolkit guarantees

| Guarantee | Enforced by |
|-----------|-------------|
| Every dataset is listed in the inventory (`inventory/datasets.csv`) | `ds-steward check`, `tests/test_checks.py` |
| Every dataset has a complete `metadata.yaml` sidecar (id, title, description, version, steward, licence, field dictionary) | `ds-steward check`, pytest |
| Every licence is recorded in the rights register (`inventory/rights-register.csv`) with a consistent SPDX identifier | `ds-steward check`, pytest |
| Every data file has a SHA-256 checksum in `checksums/sha256sums.txt` that matches the file on disk | `ds-steward check`, pytest |
| Every dataset keeps an append-only provenance log (`provenance.jsonl`) | `ds-steward check`, pytest |
| No orphan dataset folders outside the inventory | `ds-steward check` |
| Every registered figure traces to a versioned input (chain of custody via `figures/figure-manifest.jsonl`) | `ds-steward check`, pytest |
| Ingestion is always versioned: copy + hash + semver bump + provenance event + inventory sync, in one atomic command | `ds-steward ingest`, pytest |

## Repository layout

```
data-stewardship-toolkit/
├── .github/workflows/ci.yml    # CI: checks + pytest + dashboard artifact
├── src/data_stewardship/       # the toolkit (checks, ingest, cli, report)
├── tests/                      # pytest suite incl. tamper-detection tests
├── inventory/
│   ├── datasets.csv            # dataset inventory (one row per dataset)
│   └── rights-register.csv     # licence & rights register
├── datasets/                   # one folder per dataset
│   └── <dataset_id>/
│       ├── metadata.yaml       # machine-readable metadata sidecar
│       ├── data/               # checksummed, versioned data files
│       └── provenance.jsonl    # append-only ingestion audit trail
├── checksums/sha256sums.txt    # SHA-256 registry for every data file
├── figures/                    # published figures + figure-manifest.jsonl
├── scripts/                    # figure scripts (traced) + colab_run.py runner
├── colab/                      # Google Colab notebook (upload widgets + templates)
├── templates/                  # DMP, SOPs, intake forms, dataset README
│   └── csv/                    # headers-only upload templates per dataset
└── docs/dashboard.html         # generated stewardship dashboard
```

## Quickstart

```bash
git clone https://github.com/SyedRafiAhmedGIS/data-stewardship-toolkit.git
cd data-stewardship-toolkit
pip install -e ".[dev]"

ds-steward check        # every licence / metadata / checksum rule
pytest -v               # the same rules, as a test suite
ds-steward dashboard    # regenerate docs/dashboard.html
```

## Run in Google Colab

`colab/data_stewardship_toolkit_colab.ipynb` runs the whole pipeline
interactively - no local install needed. Open it via
*GitHub → colab.research.google.com → upload*, or from Colab's *File →
Upload notebook*. The notebook:

1. **sets up automatically** (clones your repo, `pip install -e ".[dev]"`),
2. **runs every stewardship check** and shows the result table,
3. **generates and downloads the CSV upload templates** - headers-only
   files derived from each dataset's metadata field dictionary - with a
   preview of **which files to upload and with which columns**,
4. gives you an **upload widget button** (per-dataset dropdown + version
   bump selector): your filled template is validated against the header
   template and ingested as a **new dataset version** with checksum and
   provenance recorded - mismatches are rejected with a hint,
5. **re-verifies everything and renders the dashboard** inline.

The same stages work from a terminal (or any Jupyter):
`python scripts/colab_run.py --stage all` (see `--help` for
`check/templates/preview/upload/dashboard`).

## Daily workflow

**1. Register a new dataset** - add one row to
`inventory/datasets.csv` (follow `templates/sop-data-ingestion.md`),
create `datasets/<id>/metadata.yaml` and a README from the templates.

**2. Ingest data, versioned**

Download the headers-only template for the dataset, fill it in, and
upload it (Colab widget or CLI). The CSV header is validated against
the template on every ingestion - mismatched files are rejected before
they touch the dataset.

```bash
ds-steward template --dataset sample_air_quality   # write the CSV template
ds-steward ingest --dataset sample_air_quality \
    --file data/raw/air_quality_feb_2024.csv \
    --actor your.name@example.org --bump minor \
    --note "February 2024 batch"                   # add --force to skip header validation
```

One command: copies the file, computes SHA-256, bumps the semantic
version, appends a provenance event, refreshes the checksum registry and
syncs the inventory.

**3. Publish a figure with provenance**

```bash
ds-steward figure --figure-id fig02_pm25_trend \
    --dataset sample_air_quality --output figures/fig02.png \
    --script scripts/make_fig02.py --actor your.name@example.org
```

The manifest records which input files (and digests) produced the
figure. Checks verify that chain of custody on every run - figures can
always be traced to a versioned input, and CI blocks any figure whose
inputs cannot be traced.

**4. Verify before every push**

```bash
ds-steward check --json   # exit code 1 on any violation
```

## CLI reference

| Command | Purpose |
|---------|---------|
| `ds-steward check [--json]` | Run all stewardship checks; exit 1 on failure |
| `ds-steward ingest --dataset ID --file F [--actor A] [--bump patch\|minor\|major] [--note N] [--force]` | Versioned ingestion of one data file (header-validated against the template) |
| `ds-steward template --dataset ID \| --all` | Generate headers-only CSV upload templates |
| `ds-steward figure --figure-id ID --dataset ID --output O --script S [--caption C]` | Register a figure against versioned inputs |
| `ds-steward dashboard [--output docs/dashboard.html]` | Regenerate the self-contained HTML dashboard |
| `ds-steward version` | Print the toolkit version |

## Dashboard

`docs/dashboard.html` is a single self-contained file (no external
assets) with live check results, the inventory and rights register, a
collapsible repository tree and copy-paste usage commands. Regenerate it
after changing data: `ds-steward dashboard`. CI uploads it as an
artifact on every run, and it renders on GitHub Pages if you publish the
`docs/` folder.

## CI

`.github/workflows/ci.yml` runs on every push and pull request:

1. installs the toolkit (`pip install -e ".[dev]"`),
2. runs `ds-steward check` (compliance gate),
3. runs `pytest` (unit + tamper-detection tests),
4. regenerates `docs/dashboard.html` and uploads it as an artifact.

A pull request that adds a dataset without a licence, metadata or
checksum **cannot merge**.

## Templates included

- `templates/data-management-plan.md` - Science Europe style DMP.
- `templates/sop-data-ingestion.md` - from raw file to versioned dataset.
- `templates/sop-checksum-and-versioning.md` - SHA-256 + semver policy.
- `templates/sop-publication-release.md` - pre-release checklist, DOI archiving.
- `templates/data-request-form.md` - intake form for incoming data.
- `templates/intake-review-checklist.md` - reviewer gate before acceptance.
- `templates/README-dataset-template.md` - per-dataset documentation.

## Adapting the toolkit

- Replace the demo datasets with real ones (follow the SOPs) and delete
  the demos when ready - the checks make migration failures visible.
- Extend `REQUIRED_METADATA_FIELDS` in `src/data_stewardship/checks.py`
  to enforce additional metadata for your domain.
- Add licence rules (for example "open datasets only") as new checks;
  mirror them in `tests/test_checks.py`.
- Point the CI badge and homepage URLs to your GitHub organisation.

## Publishing this repository to GitHub

```bash
git init
git add .
git commit -m "Data stewardship toolkit: inventory, rights register, checks, versioned ingestion"
git branch -M main
git remote add origin https://github.com/SyedRafiAhmedGIS/data-stewardship-toolkit.git
git push -u origin main
```

Then update `SyedRafiAhmedGIS` in the badge URLs above and in
`pyproject.toml` project URLs.

## Licence

Toolkit code, templates and documentation: **MIT** (see `LICENSE`).
The shipped demo datasets are **CC0-1.0** - synthetic, no real persons
or places, free to reuse without restriction. Real datasets you add
carry their own licences via the rights register.
