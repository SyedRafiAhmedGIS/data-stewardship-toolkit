# Dataset README: `<dataset_id>`

> Template - copy to `datasets/<dataset_id>/README.md`, delete this
> banner and fill every section. Keep it in sync with `metadata.yaml`;
> the toolkit checks the machine-readable sidecar, humans read this.

## Title

`<Human-readable title identical to metadata.yaml>`

## Description

`<One paragraph: what the data measures or describes, where, when, and
why it exists. State clearly if the data are synthetic or derived.>`

## Provenance

- **Origin:** `<who or what generated the data, instrument/survey/model>`
- **Method:** `<collection or generation method, calibration, exclusions>`
- **Processing:** `<transformations applied between raw capture and ingestion>`
- **Known limitations:** `<coverage gaps, sensor drift, quality caveats>`

## Files

| File | Content | Format |
|------|---------|--------|
| `data/<file>.csv` | `<short description>` | CSV, UTF-8, comma-delimited |

## Variables

| Variable | Type | Unit | Description |
|----------|------|------|-------------|
| `<name>` | `<type>` | `<unit>` | `<from metadata.yaml fields>` |

## Licence and citation

- **Licence:** `<SPDX id, e.g. CC0-1.0>` - rights holder: `<name>`
- **Recommended citation:**
  `<Creator> (<Year>). <Title>. Version <X.Y.Z>. <Repository/Publisher>. DOI: <doi>`

## Version history

| Version | Date | Change | Actor |
|---------|------|--------|-------|
| 1.0.0 | `<date>` | Initial ingestion | `<actor from provenance.jsonl>` |

## Contact

Data steward: `<email>` - requests and issues via the repository issue
tracker; incoming data follows `templates/data-request-form.md`.
