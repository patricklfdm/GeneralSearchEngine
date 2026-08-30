# V3 production performance results

The runner creates one timestamped directory here for every local execution. Raw JMH
JSON, console logs, environment metadata, soak CSV/properties, completion status, and
checksums are ignored by Git but remain outside Maven's `target/`, so `mvn clean` does
not remove them.

Keep a result directory unchanged until it has been reviewed. A stable, curated
summary may then be added to `docs/v3/`; raw machine-specific output should normally
remain local.

Cloud Benchmark V2 keeps derived evidence beside, never inside, immutable raw runs:

```text
derived/runs/<raw-run-id>/v1/
sets/in-progress/<workspace-id>/
sets/<gse-set-v1-id>/v1/
comparisons/<gse-comparison-v1-id>/v1/
upload-receipts/<gse-upload-receipt-v1-id>/v1/
```

The root name remains historical infrastructure naming. Raw members identify their
actual suite in metadata: existing lanes use `v3-production`, while the isolated V3.1
feature lane uses `v3.1-ranked-suite-v1`. Derivation and comparison fail closed on a
suite mismatch.

The in-progress workspace is resumable control state and remains after completion for
audit. A content-addressed set directory contains the deterministic set manifest,
aggregate metrics, complete attempt/replacement audit, and checksums. A comparison
directory contains canonical JSON, a deterministic Markdown rendering, and checksums.
An upload-receipt directory is a separate immutable binding between local evidence and
verified create-only GCS object generations; source manifests are never amended with a
storage location.
See
[`docs/v3/CLOUD_PERFORMANCE_TESTING.md`](../../docs/v3/CLOUD_PERFORMANCE_TESTING.md)
for the canonical set and local comparison commands.
