# GeneralSearchEngine V4.3 Phase 6 canonical review

## Decision

Workflow run `34557940276`, attempt 1, produced the accepted three-member V4.3
fast-reopen canonical set. All members ran strictly serially from exact
protected-master source `1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6`, passed member
and aggregate validation, retained final evidence in GCS, and reported complete
resource cleanup. No member from a rejected run was reused.

The set is accepted for separate append-only registration as
`v4.3.0-fast-reopen-cloud`. It is evidence for the frozen V4.3 ten-cell matrix,
replacement-host path, published-4.2 control, and warm-reopen thresholds; it is not
an SLA or a portable hardware claim.

## Evidence identity

| Field | Reviewed value |
|---|---|
| Workflow run / attempt | `34557940276 / 1` |
| Source commit | `1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6` |
| Exact-master CI | `34550893252 / success` |
| Request | `canonical / 3 serial members / standard / c3d-standard-30 / 1800s / gcs` |
| Suite / preset | `v4.3-fast-reopen-suite-v1 / v4.3-fast-reopen-v1` |
| Zone | `us-west4-a` |
| Primary / target storage | distinct `pd-balanced` 200-GiB ext4 disks |
| Peak quota boundary | `30 vCPU / 400 GiB data + 100 GiB boot` |
| Published control | checksum-pinned GeneralSearchEngine `4.2.0` |
| Set status | `PASS / canonicalEligible=true / members=3` |
| Set warm/forced ratio | `median=0.256803 / maximum=0.260551` |
| Frozen thresholds | `median <= 0.50 / every member <= 0.65` |
| Set SHA-256 | `b91f780d8f630d626f8aec3bc090073a5c4bbd9273819bc437d07c10ff7200c4` |
| Registry name | `v4.3.0-fast-reopen-cloud` (accepted through PR #129) |

The downloaded member mirrors, checksum inventories, aggregate set, and cleanup
receipts passed independent local validation. The complete set is durably present
under the exact GCS prefix
`v4.3-fast-reopen/1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6/34557940276-1/canonical/`.
Raw evidence and workload payloads are not committed to the source repository.

## Independent-member controls

| Slot | Evidence SHA-256 | Backup identity | Warm/forced ratio | Cleanup |
|---:|---|---|---:|---|
| 1 | `5547f5ef8ab6de8e6747a9ab39a8391fc38a6df9439312bd4f0cf962cbf427a3` | `gse-backup-v3-ffe5a7c386309a5f74d6b861a0112b17e2b8b881bb09e180686202b9bd7e2f6c` | 0.256803 | PASS |
| 2 | `da9df81d062bab6f8c162cb62cf3792cc0353f3f217a18e3e0ed4f5a9b2c622a` | `gse-backup-v3-3bf358c2f8e4cf389f89e948934ac44f6e6c6f41d7b6cb2e00911940fb249ab4` | 0.243176 | PASS |
| 3 | `8f2c6b063b9e12251a0ca63c4b3f09976ee59b947ea48057cf02236bd0304121` | `gse-backup-v3-10dc4ea3fdf21b6f4c00fd2e2c132e9cec09078fdee564b77628b4ea7fdfec89` | 0.260551 | PASS |

Every member exercised all ten cells against one oracle: published-4.2 and current
forced rebuild, complete warm reopen, structured/text component fallback, catalog
fallback, checkpoint-plus-WAL, cold/warm restore, cold migration followed by
replacement-host warm reopen, and continued mutation/index lifecycle. Every member
reported `COMPLETE_WARM`, `PARTIAL_FALLBACK`, and `FULL_FALLBACK` where required,
recovered committed-WAL sequence `110`, and completed at sequence `112`.

## Measurement review

| Metric | Slot 1 | Slot 2 | Slot 3 |
|---|---:|---:|---:|
| Published-4.2 forced median | 1.883 s | 1.648 s | 1.585 s |
| Current forced median | 4.996 s | 5.397 s | 5.015 s |
| Complete-warm median | 1.283 s | 1.312 s | 1.307 s |
| Warm/forced ratio | 0.256803 | 0.243176 | 0.260551 |
| Backup elapsed | 3.225 s | 3.719 s | 3.300 s |
| Measurement duration | 1800.000 s | 1800.000 s | 1800.000 s |
| Measurement reads | 43.532 billion | 42.643 billion | 43.692 billion |

All members used 100,000 documents, 16 tokens per document, four built-in indexes,
and 10,000 mutations. Canonical bytes were `14,893,819`, complete derived bytes were
`23,209,229`, and the observed source temporary peak was `52,997,013` bytes in every
member. These bounded observations satisfy the frozen diagnostic
thresholds and authorize no semantics-changing optimization.

## Experiment and correction boundary

Accepted experiment run `34551484690`, attempt 1, used the same exact source with
`experiment / 1 / actions`. Its member and aggregate set independently validated,
its warm/forced ratio was `0.252796`, and all resources reported complete cleanup.

Rejected runs `34545524731` and `34548506759` are recorded in the
[Phase 6 baseline](PHASE_6_BASELINE.md). Neither contributes a member to the accepted
experiment or canonical set.

## Registration boundary

The canonical review merged through protected PR #128 as `ae25c80`; exact-master CI
run `34567122915` passed. The separate registration candidate appends exactly one
`v4.3.0-fast-reopen-cloud` entry binding the source, suite, preset, three-member set,
median ratio and digest above. It rejects duplicate or non-canonical input. Phase 7
may not start until that registration PR merges and exact-master CI passes.
