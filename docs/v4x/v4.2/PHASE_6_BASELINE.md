# GeneralSearchEngine V4.2 Phase 6 evidence baseline

- **Status:** Canonical evidence accepted; append-only registration pending
- **Canonical source:** `d0afbb593ab5df468c0b7c4b2622ebc6daa69317`
- **Reference:** Accepted Phase 5 commit
  `5687a05aa2f495f58d8acc904ab1e663361cf6e3`

## Focused gate

```bash
scripts/verify-v42-phase6-evidence.sh
```

The focused gate passed locally. It:

- builds the benchmark-only operational probe;
- verifies the pinned Maven Central `4.1.0` JAR checksum;
- compiles the rollback helper only against that published JAR;
- runs a bounded real `(1,0)` source, backup, typed migration, `(1,1)` target
  continuation/reopen and published-4.1 source rollback;
- validates checksummed source, migration, target, rollback and aggregate evidence;
- tests exact experiment/canonical/failure-drill plans and readable summaries;
- simulates a partial cloud-resource creation failure and proves cleanup ownership;
- validates strict serial/quota, GCS, workflow, registration and tamper boundaries;
- exercises all no-GCP fake profiles and the paid runner dry-run; and
- reruns the complete Phase 5/4/3/2 acceptance chain.

## Complete local acceptance

The clean reactor passed 500 core tests and 5 processor tests with no failures; only
the two published-artifact probes owned by the isolated compatibility profile were
skipped. The Phase 6 gate then rebuilt `target/benchmarks.jar` from the clean tree and
completed the full evidence chain described above.

## Local observations

- the source and target use distinct histories and directory identities;
- the source directory hash remains unchanged across migration and target operation;
- the target accepts continued writes and survives checkpoint plus second reopen;
- the untouched source reopens under the exact published `4.1.0` artifact;
- a simulated create-failed-after-allocation path deletes the discovered owned disk;
- canonical set assembly requires three serial comparable members with distinct plan
  and target-history identities; and
- duplicate registration and non-canonical registration fail closed.

No Google Cloud resource was created and no IAM or registry state was changed by this
local baseline. The tracked registry remains intentionally empty until the accepted
canonical review is registered through its separate protected PR.

## Protected implementation acceptance

Phase 6 implementation merged through protected PR #112 as
`2dd82e4ef8e88280aab65f498454e3cd154d1200`; exact-master CI run `33894383594`
passed. The archive-layout correction merged through protected PR #113 as
`a2d5ab95e3ce4da6a7c2bd848b5bc3b40505693c`; exact-master CI run `33900296949`
passed. Evidence-workspace housekeeping merged through protected PR #114 as
`d0afbb593ab5df468c0b7c4b2622ebc6daa69317`; exact-master CI run `33905418527`
passed.

The WIF condition retains the exact repository, repository ID, owner ID, protected
master ref, and `cloud-benchmark` environment predicates while adding only
`.github/workflows/v42-storage-evolution-evidence.yml@refs/heads/master`. A custom
role containing only `storage.objects.delete` is condition-bound to the exact
`v4.2-storage-evolution/` bucket prefix; create and read retain their existing
permissions.

## Accepted cloud evidence

| Evidence | Reviewed value |
|---|---|
| Experiment | `33900943921 / attempt 1 / a2d5ab9 / one member / actions` |
| Canonical | `33906942139 / attempt 1 / d0afbb5 / three serial members / gcs` |
| Machine / zone | `c3d-standard-30 / us-west4-a` |
| Workload | `100000 documents / 16 tokens / 10000 + 1000 mutations` |
| Measurement | `1800 seconds per member` |
| Source / target disks | two distinct `pd-balanced` 200-GiB ext4 disks |
| Suite / preset | `v4.2-storage-evolution-suite-v1 / v4.2-storage-evolution-v1` |
| Canonical set SHA-256 | `57abb5394a537faaf551b9182ae5a1669de4703689dfe91e6e08dcd4580f2d75` |
| Eventual baseline | `v4.2.0-migration-cloud` |

The experiment member, all three canonical members, and both aggregate sets passed
independent checksum and semantic validation. Canonical evidence proves an untouched
V1.0 source, a distinct V1.1 target opened and continued on a replacement host, a
second target reopen, and source rollback on a separate VM using only the pinned
published `4.1.0` JAR. All three VMs, both disks, and staging objects report complete
cleanup for every accepted member.

The canonical members are comparable and `canonicalEligible=true`; their evidence
digests, backup identities, plan digests, and target histories are all distinct. GCS
contains all three member mirrors and the aggregate set under the exact canonical
source/run/profile prefix. Detailed identities and bounded observations are recorded
in [`PHASE_6_CANONICAL_REVIEW.md`](PHASE_6_CANONICAL_REVIEW.md). These measurements
are diagnostic evidence on the pinned configuration, not an SLA.

## Rejected experiment attempts

### Missing V4.2 transport deletion authority

Run `33898099293` used source `2dd82e4ef8e88280aab65f498454e3cd154d1200`.
OIDC authentication and GCS create/read succeeded, but deletion of the payload-free
permission probe was denied before any VM or disk was created. Its receipt records
all compute resources `NOT_APPLICABLE`, `stagingObjectDeleted=FAIL`, and
`cleanup=FAIL`. The exact object was removed after adding a delete-only role restricted
to the V4.2 storage-evolution prefix. This run contributes no evidence member.

### Remote archive root mismatch

Run `33898434164` used the same source and passed the corrected permission probe. It
created the source VM and two data disks, completed source materialization and
migration, then failed closed because the remote tar nested
`source-migration-output` under an extra `source/` directory. Its receipt reports the
source VM, both disks, and staging objects deleted; replacement and rollback VMs were
not applicable; aggregate cleanup is `PASS`. Protected PR #113 flattened and
stage-bound source, target, and rollback archive roots and added regression coverage.
This run contributes no evidence member.

## Pending registration

The accepted set may now be registered exactly once as `v4.2.0-migration-cloud` in a
separate append-only protected PR. Phase 7 remains blocked until that registration
merges and exact-master CI passes.
