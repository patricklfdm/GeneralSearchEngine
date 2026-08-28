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
```

The in-progress workspace is resumable control state and remains after completion for
audit. A content-addressed set directory contains the deterministic set manifest,
aggregate metrics, complete attempt/replacement audit, and checksums. A comparison
directory contains canonical JSON, a deterministic Markdown rendering, and checksums.
See
[`docs/v3/CLOUD_PERFORMANCE_TESTING.md`](../../docs/v3/CLOUD_PERFORMANCE_TESTING.md)
for the canonical set and local comparison commands.
