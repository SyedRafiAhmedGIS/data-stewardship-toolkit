# SOP: Checksums and Versioning

**SOP id:** SOP-CHK-01 - **Version:** 1.0.0 - **Owner:** data steward
**Applies to:** all datasets and published figures

## 1. Purpose

Define the integrity and versioning policy that makes every published
figure traceable to a versioned input. The toolkit automates the
mechanics; this SOP defines the *decisions* humans must make.

## 2. Checksum policy

- Algorithm: **SHA-256** for every file under `datasets/<id>/data/`.
- Registry: `checksums/sha256sums.txt`, one line per file in standard
  `sha256sum` format (`<digest>  <path-relative-to-repo-root>`).
- Written exclusively by `ds-steward ingest`; never by hand.
- Verified: by `ds-steward check` locally, by pytest in CI, and
  opportunistically before any publication release (SOP-PUB-01).
- A mismatch is treated as data corruption or tampering: quarantine the
  file, investigate, and restore from the authoritative source with a
  new versioned ingestion. Never overwrite the registry line to make
  the check pass.

## 3. Semantic versioning for datasets

Dataset versions follow `MAJOR.MINOR.PATCH` and live in both
`metadata.yaml` and `inventory/datasets.csv` (kept in sync by the tool).

| Bump | When to use | Examples |
|------|-------------|----------|
| `major` | Incompatible restructuring: schema change, redefinition of a variable, unit change, site renumbering | `1.4.2` -> `2.0.0` |
| `minor` | Additive change: new files, new columns or rows appended, new sites added | `1.4.2` -> `1.5.0` |
| `patch` | Correction of existing content: typo fixes, recalibrated values, re-export of identical schema | `1.4.2` -> `1.4.3` |

Rule of thumb: *could a figure published against the old version still
be reproduced from this version unchanged?* If not, it is a major bump.

## 4. Figure chain of custody

1. Any published figure (chart, map, summary table) is registered with
   `ds-steward figure --figure-id <id> --dataset <id> --output <figure path> --script <script path>`.
2. The manifest `figures/figure-manifest.jsonl` records, per figure:
   dataset id and version, the SHA-256 of every input file, the
   generating script and output path, and the actor.
3. `ds-steward check` verifies that each recorded digest either matches
   the file currently on disk or appears in the dataset's provenance
   history. A figure whose inputs cannot be traced fails CI.

## 5. Reproducing an old figure

1. Find the figure in `figures/figure-manifest.jsonl`; note the input
   files and digests.
2. Check out the repository commit whose `provenance.jsonl` contains
   those digests (or restore the referenced dataset version from the
   archive copy).
3. Re-run the recorded script against those inputs; the regenerated
   output must match the published artifact byte-for-byte for tabular
   outputs, or visually for rendered graphics.
