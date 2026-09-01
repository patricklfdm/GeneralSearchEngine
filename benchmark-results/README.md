# Benchmark result workspace

This directory keeps machine-specific benchmark output outside Maven `target/` so
that a clean build does not remove evidence that is still under review.

## Managed roots

- `v3-production/` is the historical runner output root for local and recovered Cloud
  Benchmark raw runs, derived evidence, sets, comparisons, and upload receipts. Its
  own [README](v3-production/README.md) and `.gitignore` define that layout.
- `v34-heap-evidence/` is a local download workspace for the independent final-source
  `4g`/`8g`/`16g` heap diagnostic.
- `v34-cloud-evidence/` is a local download workspace for lightweight GitHub Actions
  artifacts from the V3.4 two-hour experiment and canonical set.

The two V3.4 download workspaces are ignored by Git. They may contain large raw or
derived metrics, temporary instance descriptions, orchestration logs, and values that
are useful for local audit but unsuitable as permanent source files. Keep them intact
until their checksums, identities, upload receipts, and cleanup proof have been
reviewed.

For GCS-retained runs, the immutable upload receipt is the durable raw-evidence
binding. Git retains only curated review summaries and stable content identities; the
V3.4 summary is
[`docs/v3x/v3.4/PHASE_5_BASELINE.md`](../docs/v3x/v3.4/PHASE_5_BASELINE.md).

Do not use ignored local output as the only copy of required evidence. Do not force-add
raw benchmark directories to Git.
