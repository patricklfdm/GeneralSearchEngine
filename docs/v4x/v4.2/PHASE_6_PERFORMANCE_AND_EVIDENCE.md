# GeneralSearchEngine V4.2 Phase 6 performance and evidence

- **Status:** Local implementation candidate; paid evidence not yet authorized
- **Predecessor:** Accepted Phase 5 commit
  `5687a05aa2f495f58d8acc904ab1e663361cf6e3`
- **Scope:** Scale, bounded resource evidence, replacement-host target verification,
  published-4.1 rollback, durable cloud evidence and append-only registration

## Evidence identity

Phase 6 uses a new evidence family and does not reuse V4.0 or V4.1 records:

```text
artifact schema  gse-v42-migration-evidence-v1
cloud suite      v4.2-storage-evolution-suite-v1
cloud preset     v4.2-storage-evolution-v1
baseline         v4.2.0-migration-cloud
```

The registry begins empty. Registration is a separate reviewed action after an
eligible canonical set exists; the workflow never registers automatically.

## Frozen member topology

Each paid member uses one `c3d-standard-30` Standard VM at a time and two independent
`pd-balanced` 200 GiB disks. The source and target writers never run concurrently.
Canonical members execute strictly serially so the peak project boundary remains 30
vCPU and the peak regional SSD boundary remains 400 GiB.

Each production member uses:

- 100,000 documents and exactly 16 tokens per document;
- 10,000 mutation elements before migration;
- 1,000 continued mutation elements on the target;
- 1,800 seconds of target read measurement;
- a 5,400-second maximum member runtime; and
- a USD 25 maximum complete-run budget.

`experiment` and `failure-drill` use one member. `canonical` requires three
independent members. Canonical evidence requires GCS retention; experiment and failure-drill use Actions.
GitHub artifacts remain a bounded 14-day mirror.

## Authority sequence

One member performs this exact sequence:

1. validate the exact protected-master source and frozen plan;
2. create distinct source and target disks;
3. materialize a published-compatible `(1,0)` source, mutate, checkpoint and close;
4. create and independently inspect a verified V1.0 backup;
5. record the source directory SHA-256 and complete logical oracle;
6. plan and apply the reviewed transform into an absent `(1,1)` target;
7. prove the source directory bytes are unchanged;
8. delete the source/migration VM;
9. attach only the target disk to a replacement VM, reopen, verify, continue,
   checkpoint, close and reopen again;
10. delete the target VM before rollback begins;
11. attach the untouched source disk to a separate rollback VM;
12. download the exact published `general-search-engine:4.1.0` JAR, verify SHA-256
    `36aa783cef653ead26d2500a847b70bb1f8222d224c8a83de55419de46814bcb`,
    and reopen the source using only that artifact and an independently compiled
    helper;
13. delete all owned VMs, both disks and any staging object; and
14. validate the checksummed member bundle before allowing the next serial member.

GCS is evidence transport and retention only. It is never live-store authority.
Target-only writes are not merged back into the source.

## Metrics and validation

The benchmark-only probe records source load, mutation, checkpoint, backup, planning,
apply, target first-open, continued mutation, checkpoint, second-open and sustained
read measurements. Evidence also binds source/target directory identities, backup
content identity, migration plan/projection/source-authority identities, sequences,
heap observations, authoritative bytes, predicted/peak target bytes and cleanup.

Passing evidence requires all of the following:

- source bytes before and after migration are identical;
- the backup independently validates and matches the recorded source sequence;
- the target starts at the source sequence and has a distinct history;
- continued target writes advance by the expected atomic batches;
- replacement-host open and second reopen both pass;
- published `4.1.0` reopens the untouched source with the same full oracle;
- every resource cleanup field is `PASS`; and
- canonical members have distinct plan digests and target histories.

Evidence files and logs are bounded. Raw downloaded artifacts remain under the
ignored `benchmark-results/` workspace and are not committed.

## Workflow and security boundary

`.github/workflows/v42-storage-evolution-evidence.yml` is manual-only. Its preflight
runs before OIDC authentication or paid provisioning and accepts only the exact
protected `origin/master` tip. The member matrix uses `max-parallel: 1`, validates a
GCS permission probe before compute creation, requires explicit paid-run confirmation,
and records cleanup even on failure.

After this implementation merges, the existing Workload Identity provider must be
expanded only to the exact workflow ref:

```text
patricklfdm/GeneralSearchEngine/.github/workflows/
v42-storage-evolution-evidence.yml@refs/heads/master
```

The inherited repository, repository ID, owner ID, `refs/heads/master`, and
`cloud-benchmark` environment conditions remain mandatory. No IAM mutation belongs
in the repository commit.

## Execution order

Paid execution is authorized only after the implementation PR merges, exact-master CI
passes, the WIF condition is reviewed, and the workflow dry-run summary is checked.
The order is:

1. one `experiment` member retained in Actions;
2. review source preservation, replacement-host target and cleanup evidence;
3. one three-member `canonical` run retained in GCS;
4. download and independently validate all members and the aggregate set;
5. review canonical comparability and identities; and
6. register `v4.2.0-migration-cloud` in a separate append-only PR.

`failure-drill` is available for an explicitly reviewed failure exercise; it is not
required merely because the lane exists.

## Non-goals

Phase 6 adds no production API, storage-format member, migration edge, cutover,
reverse merge, replication, multi-writer behavior or automatic baseline mutation.
The probe and workflow exercise the already accepted Phase 5 production contract.
