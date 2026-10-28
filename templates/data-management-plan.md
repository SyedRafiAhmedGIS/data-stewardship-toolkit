# Data Management Plan (DMP)

> Template version 1.0.0 - adapt freely. Structure follows common
> Science Europe / DMPonline practice: answer each section for *your*
> project before data collection starts, and revisit the plan at every
> milestone. Keep the completed plan at the repository root or link it
> from the README, and state where it is stored in Section 8.

**Project / collection:** `<name>`
**Prepared by:** `<name, role>` - **Date:** `<YYYY-MM-DD>`
**Steward of record:** `<email>`

---

## 1. Data description and collection

- What data will be collected, generated or reused? List each dataset
  (or planned dataset) with its `dataset_id` as used in
  `inventory/datasets.csv`.
- Which formats will you use? Prefer open, lossless, long-lived formats
  (CSV, JSON, Parquet, GeoTIFF, NetCDF) over proprietary ones; justify
  any exception.
- What is the expected volume of each dataset, and how does volume
  affect storage, sharing and preservation choices?
- For reused data: record the source, the version ingested and the
  licence under which reuse is permitted (mirror it in the rights
  register).

## 2. Documentation and metadata

- Which metadata standard applies (for example DataCite, Dublin Core,
  ISO 19115 for geospatial, Darwin Core for biodiversity)?
- Every dataset MUST carry a completed `metadata.yaml` sidecar; list the
  additional project-specific fields you will add beyond the toolkit
  minimum (dataset_id, title, description, version, licence, fields).
- How are field definitions, units and controlled vocabularies
  documented (see the `fields` block of `metadata.yaml`)?
- Who is responsible for keeping metadata current at ingestion time
  (the toolkit's `ds-steward ingest` command enforces this).

## 3. Storage, backup and security

- Where is the master copy kept (this repository, institutional storage,
  cloud object store)? Which copy is authoritative?
- Backup regime: frequency, retention, restore test schedule.
- Access control during the active phase; who may ingest, who may
  approve (`ds-steward ingest` records the `actor` for every event).
- Checksum policy: SHA-256 for every data file via
  `checksums/sha256sums.txt`; verification is automated in CI.

## 4. Legal and ethical compliance

- Licence under which each dataset is released (record in
  `inventory/rights-register.csv`); recommend CC0-1.0 or CC-BY-4.0 for
  data, MIT/Apache-2.0 for code.
- Personal data: is any dataset personal or sensitive? If yes, state
  the lawful basis, anonymisation or pseudonymisation steps, and the
  access restrictions that apply. Datasets containing personal data
  must not be published through the open pipeline.
- Third-party rights: data you do not own must carry documented
  permission or licence terms in the rights register before ingestion.

## 5. Sharing and access

- Where will data be published (institutional repository, Zenodo,
  domain repository)? Record the DOI concept and versioning approach.
- Under what conditions (open, embargoed, restricted, controlled)?
- How are citations formed (recommended citation string per dataset,
  stored in the dataset README)?

## 6. Preservation and retention

- Which datasets must be preserved long-term, in what format, and by whom?
- Retention schedule per dataset (retention period after project end,
  and the review date that triggers deletion or archiving).
- How are preservation copies verified (checksum revalidation, e.g. by
  running `ds-steward check` against the archive).

## 7. Roles and responsibilities

| Role | Responsibility | Named person |
|------|----------------|--------------|
| Data steward | Inventory, metadata, licence register, ingestion reviews | |
| Data creator | Produces and documents data, runs `ds-steward ingest` | |
| Reviewer | Approves intake checklist and publication releases | |
| PI / owner | Accountable for legal and ethical compliance | |

## 8. Budget and review

- Costs for storage, personnel time, repository fees or long-term
  preservation charges.
- Review schedule: the DMP is reviewed at `<milestone dates>` and after
  any change to datasets, licences or legal context. Record revision
  history below.

| Date | Revision | Author |
|------|----------|--------|
| | | |
