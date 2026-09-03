# GeneralSearchEngine V4.1 Phase 6 operational evidence baseline

## Entry

Phase 6 starts from accepted Phase 5 protected-master commit
`5f1c750bd360716506a732e301ed52493650837e` (PR #98), whose exact-master CI run
`33730252965` passed. All active coordinates remain `4.1.0-SNAPSHOT`.

## Local evidence

The bounded smoke path uses real production backup, structural verification, typed
semantic verification and restore through the benchmark-only probe. It removes the
source store before restore, invokes the independent Python byte inspector, checks the
complete restored checksum and equality retrieval, proves the post-cut mutation is
absent, continues mutation, checkpoints, closes and successfully reopens a second
time. Its output uses the frozen checksummed evidence schema and exact cleanup.

The Phase 1 fake control plane still passes experiment, canonical and failure-drill
topologies without invoking GCP. Phase 6 adds strict plan validation, readable Job
Summary rendering, shell syntax gates, a dry-run member plan, independent-set
aggregation and append-only registration tooling.

## Commands

```bash
scripts/verify-v41-phase6-evidence.sh
./mvnw -f reactor/pom.xml clean test
./mvnw -Dmaven.repo.local=/tmp/gse-v41-phase6-m2 clean -Partifact-compat verify
scripts/verify-consumer-projects.sh
./mvnw -Dmaven.repo.local=/tmp/gse-v41-phase6-m2 -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh
scripts/verify-reproducible-build.sh
```

## Outcomes

- Focused Phase 6 evidence: PASS.
- Full reactor: PASS, 471 core tests and 5 processor tests.
- Artifact compatibility: PASS.
- V1-, V2- and V3-style consumer projects: PASS.
- Release profile and six-JAR integrity: PASS.
- Reproducible release artifacts: PASS.

The two release builds produced these identical SHA-256 digests:

```text
48e303e013b43c39a6aa73b265b5ca1328b80c28cc4462a3b0ddb8c326cba4b1  general-search-engine-4.1.0-SNAPSHOT-javadoc.jar
d40c44c548712f7770752f00d75ea4e910cd055a1bb9d16ed10d6107e744e9b2  general-search-engine-4.1.0-SNAPSHOT-sources.jar
804877c78f9b6fa1ca72ad5014d09c68c92c21f1bc1f0587450b567df66a470f  general-search-engine-4.1.0-SNAPSHOT.jar
a23f53c1291779a83028cbba53babdcd385b9cd696987dc444e7f33511ed7dfa  general-search-engine-processor-4.1.0-SNAPSHOT-javadoc.jar
ebe12fae31fbe20a73aa1ab69368f7fed15f8a26c7da60e13d081caede64dcb3  general-search-engine-processor-4.1.0-SNAPSHOT-sources.jar
2b353c06890b6f6d29ee3ca0e288cb16de2a9aa916a684cf0f3f5693021249da  general-search-engine-processor-4.1.0-SNAPSHOT.jar
```

## Accepted cloud evidence

The final corrections merged through protected PRs #99–#102. Both accepted runs use
exact protected-master source
`88205cf28f1aa80f8ea7ccf1bada723b3205215c`; no failed-attempt member was reused.

| Evidence | Reviewed value |
|---|---|
| Experiment run | `33754116526 / attempt 1 / one member / actions` |
| Canonical run | `33758217508 / attempt 1 / three serial members / gcs` |
| Machine / zone | `c3d-standard-30 / us-west4-a` |
| Corpus / mutations | `100000 documents / 10000 before backup / 1000 after restore` |
| Measurement | `1800 seconds per member` |
| Source / restore disks | distinct `pd-balanced` 200-GiB ext4 disks |
| Suite / preset | `v4.1-operational-safety-suite-v1 / v4.1-operational-safety-v1` |
| Canonical set SHA-256 | `bede37bfd7c37bd7da891461a5d91d8dc6bdc3a085d2b873c739cc723ca68f27` |
| Registered baseline | `v4.1.0-operational-cloud` |

The experiment member and all three canonical members passed independent byte and
semantic validation, true source-loss proof, replacement-host proof, complete-oracle
comparison, post-cut exclusion, continued mutation, checkpoint and second reopen.
Every member checksum inventory passed. All source VMs/disks, replacement VMs/disks
and staging objects have explicit `PASS` cleanup receipts.

The canonical set is comparable and `canonicalEligible=true`. Its three members have
distinct backup content identities and restored history identities. Each measurement
ran for at least 1,800 seconds, with 42.419–46.789 billion reads. Backup elapsed time
was 2.076–2.168 seconds and restore elapsed time was 4.277–4.302 seconds. These are
diagnostic observations on the pinned cloud configuration, not an SLA, and they do
not authorize a production optimization.

Only the append-only metadata registry and this review are tracked. Downloaded
Actions/GCS evidence and workload payloads remain outside Git. The registry and
review merged through protected PR #103 as `049b232`; exact-master CI run
`33809198755` passed and established the Phase 7 entry boundary.

## Rejected experiment attempts

### Missing transport deletion authority

Workflow run `33737706926` attempted the experiment profile at protected-master source
`fde792c856e2e276b85a5d4a9e14821fed2a85a6`. Source backup, temporary transport and
replacement-host execution progressed, but final transport cleanup failed closed with
exit code `40`: the environment service account lacked `storage.objects.delete`.
This run is not acceptable operational evidence and makes no performance or recovery
claim. The operator removed the exact failed-run transport remnants and added a custom
delete-only role restricted to the `v4.1-operational-safety/` object prefix.

The runner now proves create/read/delete access with a payload-free object before
creating any VM or disk. It also blocks project-wide SSH keys on every VM and confines
ephemeral workflow keys to instance metadata. This correction merged through protected
PR #100 as `22c4c956ff91b454ee26e1519cabd9965bee8fe9`.

### Zero asynchronous peak sample

Workflow run `33744312340` attempted the experiment profile at protected-master source
`22c4c956ff91b454ee26e1519cabd9965bee8fe9`. The transport permission preflight passed,
the source and replacement-host topology ran, and cleanup removed the source VM/disk,
replacement VM/disk and staging object. Its receipt records `runStatus=FAIL` with all
five deletion checks and aggregate `cleanup=PASS`.

Evidence assembly nevertheless rejected the run because `backup.peakObservedBytes`
was zero. The downloaded artifact contains only the cleanup receipt and two bounded
16-KiB remote logs; it contains no backup or corpus payload. This run is not eligible
evidence and makes no performance, backup or recovery claim.

The probe now takes a positive synchronous `source.bytesBeforeBackup` measurement
before starting backup, seeds the observed peak with that value and lets the concurrent
monitor raise it. The source stage fails closed before reporting `PASS`, and evidence
validation independently requires both values to be positive and the peak to be at
least the synchronous baseline. Protected PR #101 merged this correction as
`b777e54e0ce37ed169dd1b19c74fec6c588e2625`; later accepted runs supersede this
failed attempt without reusing it.

### Mount-root traversal failure

Workflow run `33750556738` attempted the experiment profile at protected-master source
`b777e54e0ce37ed169dd1b19c74fec6c588e2625`. Transport permission probing passed and
the source disk and VM were created, but the source stage failed before backup when
the synchronous sampler walked the ext4 mount root and encountered the root-owned
`lost+found` directory. The remote stage returned exit code `20`.

The failure receipt records the source VM and source disk as deleted; replacement
resources and staging transport were never created. The old receipt aggregation
reported `cleanup=FAIL` only because it did not treat `NOT_APPLICABLE` as complete.
The artifact contains the receipt and one bounded remote log, with no backup or corpus
payload. This run is not eligible evidence and makes no operational claim.

Sampling is now restricted to the owned source-store and backup directories. Expected
atomic disappearance of checkpoint staging paths is ignored, while other checked or
unchecked background I/O failures are propagated. The local gate includes an
inaccessible `lost+found` sibling that must remain outside the sampling boundary.
Cleanup aggregation accepts `PASS` or `NOT_APPLICABLE`, while every actual `FAIL`
remains fail-closed. Protected PR #102 merged this correction as
`88205cf28f1aa80f8ea7ccf1bada723b3205215c`; the accepted experiment and canonical
runs use exactly that source.
