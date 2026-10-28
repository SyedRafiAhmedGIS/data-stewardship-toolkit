# Contributing

Thanks for helping improve the Data Stewardship Toolkit. This repository
practices what it enforces - so contributions follow the same rules the
toolkit applies to data.

## Development setup

```bash
git clone https://github.com/YOUR-USERNAME/data-stewardship-toolkit.git
cd data-stewardship-toolkit
pip install -e ".[dev]"
pre-commit-free quality gate:  ds-steward check && pytest -v
```

Python >= 3.9 is required; the only runtime dependency is PyYAML.

## Ground rules

1. **Never break the compliance gate.** `ds-steward check` and
   `pytest` must pass on your branch. If your contribution changes the
   rules, update both the checks and the tests in the same PR.
2. **Datasets enter only via `ds-steward ingest`.** Hand-edited files
   under `datasets/<id>/data/`, `checksums/` or `provenance.jsonl`
   will fail CI.
3. **Licences first.** A new dataset needs a row in
   `inventory/datasets.csv` and its licence in
   `inventory/rights-register.csv` before ingestion.
4. **Templates are documentation debt.** If you change policy
   (versioning rules, release steps), update the matching template in
   `templates/` in the same PR.

## Adding a dataset

Follow `templates/sop-data-ingestion.md` end to end and attach a filled
`templates/data-request-form.md` plus `templates/intake-review-checklist.md`
to your pull request. A reviewer checks the intake list before merge.

## Code style

- Standard library first; keep the dependency footprint minimal.
- Every user-facing failure message should say what to do next.
- New behaviour needs a test; bug fixes need a regression test.

## Pull requests

- One logical change per PR; describe *what* and *why*.
- Include the `ds-steward check` output in the PR body when touching
  inventory, datasets or checks.
- CI must be green; the reviewer runs the intake checklist for dataset PRs.

## Reporting issues

Open a GitHub issue with: expected behaviour, actual behaviour, the
`ds-steward check --json` output (redact anything confidential), and
your Python version.
