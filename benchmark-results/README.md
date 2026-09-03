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
- `v4-durable/` is the local download and review workspace for V4 durable experiment,
  canonical, replacement-VM failure-drill, quota-failure, cleanup, and checksum
  evidence. Its own [README](v4-durable/README.md) and `.gitignore` define that
  boundary.
- `v41-operational/` is the local download and review workspace for V4.1 backup,
  true source-loss, replacement-host, aggregate-set and cleanup evidence. Its own
  [README](v41-operational/README.md) and `.gitignore` keep raw artifacts untracked.

The V3.4 and V4 download workspaces are ignored by Git. They may contain large raw or
derived metrics, temporary instance descriptions, orchestration logs, and values that
are useful for local audit but unsuitable as permanent source files. Keep them intact
until their checksums, identities, upload receipts, and cleanup proof have been
reviewed.

For GCS-retained runs, the immutable upload receipt is the durable raw-evidence
binding. Git retains only curated review summaries and stable content identities; the
V3.4 summary is
[`docs/v3x/v3.4/PHASE_5_BASELINE.md`](../docs/v3x/v3.4/PHASE_5_BASELINE.md).
The accepted V4 durable set is summarized in
[`docs/v4/PHASE_6_CANONICAL_REVIEW.md`](../docs/v4/PHASE_6_CANONICAL_REVIEW.md).
V4.1 conclusions belong in
[`docs/v4x/v4.1/PHASE_6_BASELINE.md`](../docs/v4x/v4.1/PHASE_6_BASELINE.md).

Do not use ignored local output as the only copy of required evidence. Do not force-add
raw benchmark directories to Git.
