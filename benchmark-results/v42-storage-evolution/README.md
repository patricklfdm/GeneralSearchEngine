# V4.2 storage-evolution evidence workspace

This directory is the local download and review workspace for V4.2 source-to-target
storage migration, replacement-host verification, published-4.1 rollback, cleanup,
and aggregate-set evidence. Raw experiment, canonical, and failure-drill artifacts
are ignored by Git and remain outside Maven `target/`.

Keep every run and attempt in a distinct directory. Validate member checksums with
`scripts.v42.migration_performance`, validate aggregate sets with
`scripts.v42.migration_cloud_set`, and inspect every cleanup receipt before recording
a conclusion. Do not combine members across source commits, attempts, or profiles.

Git contains only curated conclusions and the append-only registration in
[`docs/v4x/v4.2/cloud-benchmark-baselines.json`](../../docs/v4x/v4.2/cloud-benchmark-baselines.json).
Canonical evidence must also remain durably retained in GCS. This directory is a
local audit mirror and must never contain long-lived credentials or be force-added
to Git.
