# GeneralSearchEngine V4.2 Phase 6 canonical review

## Decision

Workflow run `33906942139`, attempt 1, produced the accepted three-member V4.2
storage-evolution canonical set. All members ran strictly serially from exact
protected-master source `d0afbb593ab5df468c0b7c4b2622ebc6daa69317`, passed member
and aggregate validation, retained final evidence in GCS, and reported complete
resource cleanup. No member from a rejected experiment was reused.

The set is accepted for separate append-only registration as
`v4.2.0-migration-cloud`. It is evidence for the frozen V4.2 offline migration,
replacement-host target, and published-4.1 rollback topology; it is not an SLA or a
portable hardware claim.

## Evidence identity

| Field | Reviewed value |
|---|---|
| Workflow run / attempt | `33906942139 / 1` |
| Source commit | `d0afbb593ab5df468c0b7c4b2622ebc6daa69317` |
| Exact-master CI | `33905418527 / success` |
| Request | `canonical / 3 serial members / standard / c3d-standard-30 / 1800s / gcs` |
| Suite / preset | `v4.2-storage-evolution-suite-v1 / v4.2-storage-evolution-v1` |
| Zone | `us-west4-a` |
| Source / target storage | distinct `pd-balanced` 200-GiB ext4 disks |
| Peak quota boundary | `30 vCPU / 400 GiB regional SSD` |
| Set status | `PASS / canonicalEligible=true / members=3` |
| Set SHA-256 | `57abb5394a537faaf551b9182ae5a1669de4703689dfe91e6e08dcd4580f2d75` |
| Registry name | `v4.2.0-migration-cloud` (candidate under protected review) |

The downloaded member mirrors, checksum inventories, aggregate set, and cleanup
receipts passed independent local validation. The complete set is durably present
under the exact GCS prefix
`v4.2-storage-evolution/d0afbb593ab5df468c0b7c4b2622ebc6daa69317/33906942139-1/canonical/`.
Raw evidence and workload payloads are not committed to the source repository.

## Independent-member controls

| Slot | Evidence SHA-256 | Backup identity | Plan digest | Target history | Cleanup |
|---:|---|---|---|---|---|
| 1 | `f6423958077277829f4a6cd9355985731e28806314dc737568e6a0b64b87e0dc` | `gse-backup-v1-71d02011bab4eff6316abf39bf8add830a261b88d366c5f99cc6eb0a073a9608` | `gse-migration-plan-v1-9cfb7a0576762e5a0b729911a69db8ac2da37d19436dd2cae89b5861dfde722c` | `711c8701-fae6-4dcf-8183-0528eef9e259` | PASS |
| 2 | `fda66ad325d32e8f59bea4460fc3d0183c4787e47837c3df45fda66d692e03ed` | `gse-backup-v1-401c3bcacaea511464859fb80392da99bdab33257eb6dd64ee90372ddabb6bd9` | `gse-migration-plan-v1-8d0df4f777d5b3bcb315cbb39dbdebeaeaf277688ac2ececb486a12b0bb406b1` | `e406f9a0-7306-4806-b259-db27c8826d6a` | PASS |
| 3 | `eb789ecec8823dc92b568f9c152f44c8569ca0c45372145b7b5a66bfeb605fbb` | `gse-backup-v1-7b74c2ddc03c999622ecc9b540efd51250d7ca3b683954a8c1ff0b0dde5a998d` | `gse-migration-plan-v1-5c2df20b5b184ea8d6068c7276fc7d07285a3c3970eeda95ffda2e30d08ac4d4` | `69a943c9-e2a2-41f7-b557-08d0a5f2ce1e` | PASS |

Every member materialized an exact V4.1-compatible source, verified its backup,
planned and applied migration to an absent target, proved source bytes unchanged,
opened and continued the V1.1 target on a replacement VM, checkpointed and reopened
it a second time, stopped the target writer, and reopened the untouched source on a
separate rollback VM using only the checksum-pinned published `4.1.0` JAR. Source,
target, and rollback VMs, both data disks, and staging objects all report `PASS`
cleanup.

## Measurement review

| Metric | Slot 1 | Slot 2 | Slot 3 |
|---|---:|---:|---:|
| Backup elapsed | 2.078 s | 2.022 s | 2.047 s |
| Plan elapsed | 1.956 s | 1.956 s | 1.931 s |
| Apply elapsed | 4.761 s | 4.692 s | 4.673 s |
| First target open | 713 ms | 705 ms | 719 ms |
| Second target open | 431 ms | 444 ms | 691 ms |
| Measurement duration | 1800.000 s | 1800.000 s | 1800.000 s |
| Measurement reads | 29.840 billion | 30.790 billion | 29.612 billion |

All members used 100,000 documents, 16 tokens per document, 10,000 pre-migration
mutations, and 1,000 continued target mutations. Source sequence `110` became target
sequence `111`; the source stayed at sequence `110` and reopened under published
4.1. The authoritative migration input was `14,289,639` bytes and the recorded peak
target footprint was `1,088,031,463` bytes in every member. These bounded observations
show no evidence-integrity or lifecycle outlier and authorize no semantics-changing
optimization.

## Experiment and correction boundary

Accepted experiment run `33900943921` used source
`a2d5ab95e3ce4da6a7c2bd848b5bc3b40505693c` with `experiment / 1 / actions`.
Its member and set validated independently and all resources reported complete
cleanup. The later canonical source differs only by the evidence-workspace
housekeeping merged through PR #114.

Rejected runs `33898099293` and `33898434164` are recorded in the
[Phase 6 baseline](PHASE_6_BASELINE.md). Neither contributes a member to this set.

## Registration boundary

The separate registration candidate appends exactly one `v4.2.0-migration-cloud`
entry binding the source, suite, preset, three-member set, and set digest above. It
rejects duplicate or non-canonical input. Phase 7 may not start until that
registration PR merges and exact-master CI passes.
