# SOP: Data Ingestion

**SOP id:** SOP-ING-01 - **Version:** 1.0.0 - **Owner:** data steward
**Applies to:** every dataset entering this repository

## 1. Purpose

Ensure that every file entering the repository becomes a *versioned,
checksummed, documented* dataset input, with an audit trail that links
the event to a person, a timestamp and a SHA-256 digest. Following this
SOP guarantees that `ds-steward check` and CI remain green.

## 2. Scope and prerequisites

Covers ingestion of new data files into an existing dataset and creation
of brand-new datasets. You need:

- write access to the repository,
- the toolkit installed (`pip install -e ".[dev]"`),
- for a new dataset: an approved data request form and a completed
  intake review checklist.

## 3. Procedure - new dataset

1. **Register intent.** Add one row to `inventory/datasets.csv` with a
   unique `dataset_id`, a descriptive title, the path
   `datasets/<dataset_id>`, version `0.0.0`, the intended `licence_id`
   (must already exist in `inventory/rights-register.csv`), status
   `registered`, and the steward of record.
2. **Create the folder.** `datasets/<dataset_id>/data/` for data files;
   the folder must otherwise stay empty until ingestion.
3. **Create metadata.** Copy the field list from the data provider into
   a new `datasets/<dataset_id>/metadata.yaml` (model it on the shipped
   demo datasets) and add a dataset README from
   `templates/README-dataset-template.md`.
4. **Ingest.** From the repository root run:
   `ds-steward ingest --dataset <dataset_id> --file <raw file> --actor <you> --bump minor --note "initial ingestion"`
   The tool copies the file, computes SHA-256, records provenance and
   syncs the inventory.
5. **Verify.** `ds-steward check` must pass. Commit and push; CI will
   re-verify.

## 4. Procedure - add a file to an existing dataset

1. Choose the version bump: `patch` (correction), `minor` (addition),
   `major` (incompatible restructuring) - see SOP-CHK-01.
2. Run `ds-steward ingest` with `--file` pointing at the raw file.
3. Update the dataset README changelog and, if the dataset is already
   published, open the version bump decision in the pull request
   description so reviewers can object.

## 5. Quality rules

- Never edit files under `datasets/<id>/data/` by hand; always ingest a
  corrected copy as a new version so history stays reproducible.
- Never hand-edit `checksums/sha256sums.txt` or `provenance.jsonl`;
  both are maintained by the toolkit. Append-only provenance means
  corrections are new events, not rewrites.
- Raw source files live outside the repository (drop zone); only
  curated copies are ingested.

## 6. Records

The ingestion event (timestamp, actor, version, file, sha256, note) is
retained in `datasets/<id>/provenance.jsonl` for the life of the
dataset and mirrored into `metadata.yaml`.
