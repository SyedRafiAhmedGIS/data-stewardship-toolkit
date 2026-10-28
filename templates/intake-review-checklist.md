# Intake Review Checklist

> The reviewer completes this checklist **before** a new dataset is
> ingested (or before an existing dataset is republished). One checklist
> per dataset version that changes structure or licensing. File the
> completed checklist with the dataset's pull request.

**Dataset:** `<dataset_id>` - **Version under review:** `<X.Y.Z>`
**Reviewer:** `<name>` - **Date:** `<YYYY-MM-DD>`

## A. Registration and identity

- [ ] `dataset_id` is unique, stable and descriptive (no spaces).
- [ ] Inventory row exists in `inventory/datasets.csv` with title, path,
      steward and intended licence.
- [ ] A completed data request form (or equivalent record) is on file.

## B. Content and documentation

- [ ] Data dictionary available; every column is described in the
      `fields` block of `metadata.yaml` with type and unit.
- [ ] Value ranges plausible; obvious outliers explained or annotated.
- [ ] Encoding, delimiter and null-value conventions documented and
      consistent with the rest of the repository.
- [ ] Dataset README created from `templates/README-dataset-template.md`.

## C. Legal and ethical

- [ ] Licence identified and present in `inventory/rights-register.csv`;
      SPDX identifier matches `metadata.yaml`.
- [ ] Ownership or permission documented for third-party content.
- [ ] Privacy screening completed; no personal data in the open pipeline
      (or lawful basis and restrictions recorded and honoured).

## D. Technical integrity

- [ ] Ingestion performed via `ds-steward ingest` (no manual file drops).
- [ ] Checksums recorded in `checksums/sha256sums.txt` and verified.
- [ ] Provenance event recorded with actor, timestamp and note.
- [ ] Version bump chosen deliberately per SOP-CHK-01 and justified in
      the pull request description.

## E. Decision

- [ ] Approved for ingestion/publication as version `<X.Y.Z>`.
- [ ] Rejected - remediation required (list):
  1.
  2.

**Reviewer signature:** ____________________  **Date:** __________
