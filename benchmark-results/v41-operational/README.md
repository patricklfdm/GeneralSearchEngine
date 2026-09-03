# V4.1 operational evidence workspace

This directory is the local download and review workspace for V4.1 source-loss and
replacement-host evidence. Raw experiment, canonical, failure-drill, cleanup and
aggregate-set artifacts are ignored by Git and remain outside Maven `target/`.

Keep every run and attempt in a distinct directory. Validate member checksums with
`scripts.v41.operational_evidence`, validate aggregate sets with
`scripts.v41.operational_cloud_set`, and compare each cleanup receipt before recording
any conclusion. Do not mix members across source commits, run attempts or profiles.

Git contains only curated conclusions and the append-only registration in
[`docs/v4x/v4.1/cloud-benchmark-baselines.json`](../../docs/v4x/v4.1/cloud-benchmark-baselines.json).
Canonical and failure-drill evidence must also remain durably retained in GCS. This
directory is a local audit mirror and must never contain long-lived credentials or be
force-added to Git.
