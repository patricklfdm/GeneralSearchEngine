# V4.4 final-durable evidence workspace

This ignored workspace holds downloaded V4.4 experiment, failure-drill and canonical
member artifacts plus their aggregate sets. Keep every run, attempt and profile in a
separate directory. Validate member bundles with `scripts.v44.cloud_evidence`, sets
with `scripts.v44.cloud_set`, and inspect every cleanup receipt before recording a
conclusion.

Do not combine sources, attempts, profiles or member slots. Canonical evidence is
retained in GCS; Git tracks only curated conclusions and the eventual append-only
registry under `docs/v4x/v4.4/`. Never force-add raw evidence, remote logs, workload
payloads or credentials.
