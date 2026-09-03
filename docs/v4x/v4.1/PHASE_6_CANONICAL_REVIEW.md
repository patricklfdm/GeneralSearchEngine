# GeneralSearchEngine V4.1 Phase 6 canonical review

## Decision

Protected workflow run `33758217508`, attempt 1, produced the accepted three-member
canonical set for V4.1 operational safety. All three serial members used exact
protected-master source `88205cf28f1aa80f8ea7ccf1bada723b3205215c`, completed on
their first attempt, passed member and set validation, retained final evidence in GCS
and reported complete resource cleanup. No member from a rejected run was selected,
replaced or reused.

The set is accepted for append-only registration as
`v4.1.0-operational-cloud`. Registration records evidence for the frozen V4.1
source-loss and replacement-host topology; it is not an SLA or a portable hardware
claim.

## Evidence identity

| Field | Reviewed value |
|---|---|
| Workflow run / attempt | `33758217508 / 1` |
| Source commit | `88205cf28f1aa80f8ea7ccf1bada723b3205215c` |
| Request | `canonical / 3 serial members / standard / c3d-standard-30 / 1800s / gcs` |
| Suite / preset | `v4.1-operational-safety-suite-v1 / v4.1-operational-safety-v1` |
| Zone | `us-west4-a` |
| Source / restore storage | distinct `pd-balanced` 200-GiB ext4 disks |
| Set status | `PASS / canonicalEligible=true / comparable=true / members=3` |
| Set SHA-256 | `bede37bfd7c37bd7da891461a5d91d8dc6bdc3a085d2b873c739cc723ca68f27` |
| Registry name | `v4.1.0-operational-cloud` |

The downloaded member mirrors, checksum inventories, assembled set and cleanup
receipts passed independent local validation. Final GCS retention is part of the
workflow result; raw evidence and workload payloads are not committed to the source
repository.

## Independent-member controls

| Slot | Evidence SHA-256 | Backup content identity | Restored history | Cleanup |
|---:|---|---|---|---|
| 1 | `76b39f15282801057314c3ca5c82db9edc2009d4c4805b8ff0b92325955f7dcb` | `gse-backup-v1-fb719bb8e79e5631168afc9d1f82d86f249be40d9fd6e25e7183ba57f833d949` | `ac4865fb-f6c1-40d2-bb1b-3b05e2f60440` | PASS |
| 2 | `de6a8b9aebd2ca7c741b45225efde63be214a405a41d0e9aa33499992a508f25` | `gse-backup-v1-dd8dc05586a5741609f56f20de69758c5cb2fb40f369253bd4dcf114e959942c` | `beeea977-5120-4c72-8a8d-e929e1bc5541` | PASS |
| 3 | `3abc5b3f04b26121211a43894d7d603dffaa2857a06c4e8b9e4c7e5c1552082e` | `gse-backup-v1-962bc951ed8f1c6861ea7a158697a44b85b9dd8f52f1f49e533326a2ad981eac` | `00d2e535-8181-4ac5-a9d8-090041daf7c2` | PASS |

Every member proved source deletion before replacement provisioning, independently
verified the transported immutable bundle, restored into a new history, matched the
complete oracle, excluded the post-cut mutation, continued mutation, checkpointed,
closed and reopened successfully. Source VM/disk, replacement VM/disk and staging
object cleanup all report `PASS`.

## Measurement review

| Metric | Slot 1 | Slot 2 | Slot 3 |
|---|---:|---:|---:|
| Backup elapsed | 2.114 s | 2.168 s | 2.076 s |
| Restore elapsed | 4.299 s | 4.302 s | 4.277 s |
| Semantic verification | 2.146 s | 2.143 s | 2.144 s |
| First open | 270 ms | 326 ms | 264 ms |
| Second open | 187 ms | 183 ms | 187 ms |
| Measurement duration | 1800.000 s | 1800.000 s | 1800.000 s |
| Measurement reads | 42.419 billion | 46.789 billion | 46.470 billion |

All members reported structural `VALID`, semantic `SEMANTICALLY_VALID`, sequence
`110` at the backup cut and final sequence `111` after continued mutation. The
authoritative bundle size was `12,389,514` bytes and the observed source-plus-backup
peak was `26,011,282` bytes in every member. The narrow backup/restore shape and
positive long-run progress expose no evidence-integrity or lifecycle outlier and
justify no semantics-changing optimization.

## Registration boundary

The append-only registry binds `v4.1.0-operational-cloud` to the exact source, suite,
preset, member count and set digest above. Future comparisons must materialize and
validate this V4.1 set before use. They must not conflate this operational-safety
evidence with the V4.0 durable performance family or any V3 in-memory baseline.

The successful experiment run `33754116526` and the three rejected infrastructure or
measurement attempts remain recorded in the
[Phase 6 baseline](PHASE_6_BASELINE.md).
