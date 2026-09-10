# GeneralSearchEngine V4.3 Phase 3 local baseline

- **Branch:** `feat/v4.3-phase3-structured-images`
- **Base:** `e7d8be3580a8e007a1afcef099dcf2b7e61fdbba`
- **Version:** `4.3.0-SNAPSHOT`
- **Cloud/IAM/registry changes:** none
- **Protected acceptance:** PR #122, master
  `98527a2475d69673513addb15e5693bc197ddf2c`, CI `34454404406`

## Implemented evidence

The focused Java matrix proves:

- valid equality/range/prefix images produce `COMPLETE_WARM` reopen;
- post-checkpoint document mutations and dynamic index create/drop replay over the
  recovered checkpoint snapshot;
- one corrupt component produces `PARTIAL_FALLBACK`, while catalog corruption and
  absence produce `FULL_FALLBACK`;
- successful fallback refresh returns the store to independently inspected `VALID`;
- insufficient derived allowance cannot fail canonical checkpoint or reopen;
- direct `(1,0)` and `(1,1)` to `(1,2)` migrations publish cold targets;
- meaningful `(1,2)` to `(1,2)` migration preserves every source byte, while an
  unchanged request is rejected; and
- the Phase 2 mixed four-component fixture admits the three structured components,
  rebuilds text, and does not claim Phase 4 text publication.

The separate-JVM production harness covers four publication cut points using both
`Runtime.halt` and external kill. Every replacement JVM recovered the full query
oracle, preserved canonical file digests and left a valid derived generation.

## Executable gate

```bash
scripts/verify-v43-phase3-structured-images.sh
```

The gate runs the focused Java compatibility/migration matrix, independent Phase 2
Python parser tests, production child-process interruption cases, replacement-JVM
verification and checksummed evidence validation. CI also invokes it with
`--skip-build` after reactor tests and syntax-checks the shell/Python entry points in
the no-GCP lane.

The complete reactor passed `525` core tests with no failures/errors (`4`
published-artifact conditional skips) and all `5` processor tests. Exact published
`4.2.0` isolation, all independent consumers, the six release artifacts, two clean
reproducible builds and bounded JMH/inherited operational smoke also passed. No cloud
workflow, IAM policy, VM/disk, GCS object or baseline registration belongs to this
phase.
