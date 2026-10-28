# SOP: Publication and Release

**SOP id:** SOP-PUB-01 - **Version:** 1.0.0 - **Owner:** data steward
**Applies to:** public releases of datasets, figures or the toolkit itself

## 1. Purpose

Guarantee that anything published from this repository is complete,
licensed, traceable and archived in a citable form.

## 2. Pre-release checklist

Run through every item; the release is blocked while any box is open.

- [ ] `ds-steward check` passes locally and CI is green on the release commit.
- [ ] Every dataset in the release has status `published` in
      `inventory/datasets.csv` and a complete `metadata.yaml`.
- [ ] Every licence appears in `inventory/rights-register.csv`; SPDX
      identifiers are consistent; third-party data have documented
      permission.
- [ ] No personal or sensitive data are included; the DMP (Section 4)
      has been reviewed for this release.
- [ ] Every published figure is registered in
      `figures/figure-manifest.jsonl` and its inputs pass chain-of-custody.
- [ ] Dataset READMEs carry a recommended citation and a version history
      section current for this release.
- [ ] The dashboard is regenerated (`ds-steward dashboard`) and reviewed
      for stale titles or licences.

## 3. Tagging and release notes

1. Tag the release commit `data-release-vX.Y.Z` (or `toolkit-vX.Y.Z`
   for toolkit releases) and write release notes listing: datasets
   included, their versions, figures registered, and any licence or
   access changes.
2. Attach the generated dashboard and, for toolkit releases, the
   repository ZIP to the GitHub release.

## 4. Archiving and citation

- Deposit the release (or the datasets individually) in an archive that
  issues DOIs (for example Zenodo); link the repository to the DOI
  concept so every release mints a versioned DOI.
- Record the archive DOI in the dataset README and in the release
  notes; recommend a citation string of the form:
  `Creator (Year). Title. Version X.Y.Z. <Repository>. DOI.`
- Keep the archived copy's checksums (export `sha256sums.txt` together
  with the deposit) so long-term integrity can be re-verified.

## 5. After the release

- Announce to stakeholders; update the DMP review log.
- Any post-release correction follows SOP-CHK-01: new versioned
  ingestion, new release tag, never a silent replacement of files.
