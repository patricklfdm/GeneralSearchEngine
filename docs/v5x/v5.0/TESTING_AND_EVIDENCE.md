# V5.0 testing and evidence plan

- **Status:** Accepted Phase 0 plan and Phases 1–5; public-admission contract accepted, Step A under review
- **Published control:** exact GeneralSearchEngine `4.4.0`
- **Planned evidence schema:** `gse-v50-replication-evidence-v1`
- **Planned suite:** `v5.0-replicated-single-shard-suite-v1`
- **Planned preset:** `v5.0-replicated-single-shard-v1`
- **Eventual baseline:** `v5.0.0-replicated-cloud`

## Evidence layers

The accepted [public-admission evidence matrix](PUBLIC_ADMISSION_ENTRY_PLAN.md)
adds typed bootstrap, publication/resume/cleanup and real three-JVM public consumers
before Phase 6. [Step A](PUBLIC_ADMISSION_FOUNDATION.md) supplies independent `1.1`
format fixtures and declaration checks. Actual offline/public runtime evidence remains
required in B/C; accepted Phase 1–5 internal gates do not supply those capabilities.

V5.0 requires independent evidence at five layers before release:

1. a small executable replicated-history model independent of production storage;
2. deterministic in-process network schedules with exact replay;
3. separate-JVM three-node crash/storage harness using real files and process kills;
4. no-GCP fake-cloud workflow validating topology, identity, retention and cleanup;
5. real concurrent three-node cloud experiment, failure-drill and canonical evidence.

Randomized/property schedules extend deterministic named scenarios. Random chaos can
discover a failure but cannot replace the minimized replay trace admitted as evidence.

## Phase 1 first-class infrastructure

Before production replication code, Phase 1 must provide:

- declaration-only API and consumer fixtures;
- an independent state model for promises, append, commit proof, apply and compaction;
- stable event schema and trace IDs;
- deterministic delivery/drop/delay/duplicate/reorder/disconnect controls;
- stable barriers for force, ACK, proof, apply, publication and response boundaries;
- three separate JVM workers with kill/restart and storage-fault commands;
- manifest/log/proof/snapshot fixture generators and independent inspectors;
- evidence bundle/checksum validators;
- fake cloud planning, cleanup receipts and failure-artifact retention; and
- exact published-4.4 control download/checksum verification.

The process harness owns fresh isolated directories, never kills by an unresolved
pattern, records exact PIDs/paths, and retains the workspace on failure. It must test
real abrupt termination rather than only exceptions or graceful close.

## Minimum deterministic safety matrix

Named scenarios include:

- normal entry/proof/apply/publication;
- duplicate and reordered entry/proof/commit messages;
- same-index different-content conflict;
- stale and conflicting leader incarnation;
- no quorum and one-follower-down operation;
- every crash boundary before/after entry force, entry quorum, proof force, proof
  quorum, apply, publication and response;
- leader restart with committed and uncommitted suffixes;
- permanent leader/follower disk loss and same-NodeId reconstruction;
- follower incremental catch-up and transition to snapshot transfer;
- interrupted/corrupt/oversized snapshot transfer;
- compaction recovery-floor enforcement;
- slow follower, full queues, bounded retry and disk-capacity failure;
- concurrent clients, atomic bulk and replicated index create/drop;
- checkpoint, application backup, close and cancellation interactions; and
- repeated restart with identical final oracle and digest.

Every scenario asserts committed-history prefix safety, at-most-once apply per entry,
ApplicationSequence mapping and equality with the V4.4 application-state oracle.

## Cloud topology and current quota envelope

Each evidence topology runs all three voters concurrently. Serial execution of three
single-node jobs is invalid replication evidence.

The existing project envelope is treated as a hard planning cap until an operator
records a quota increase:

| Resource | Per topology cap |
| --- | --- |
| Voters | exactly 3 concurrent VMs |
| CPU | at most 8 vCPU per VM / 24 vCPU total |
| Data disk | at most 100 GiB `pd-balanced` per voter / 300 GiB total |
| Boot disk | at most 50 GiB per voter / 150 GiB total |
| Provisioned regional disk | at most 450 GiB total |
| Network | private addresses; no public replication listener |
| Repetitions | topologies run serially; voters within a topology run concurrently |

This fits the known 32 global-vCPU and 500-GiB regional-disk ceilings with explicit
headroom. Phase 1 must verify an available Standard machine SKU and image in the
selected zone, then freeze exact SKU/image/JDK/filesystem/mount/disk identities before
any paid run. `c3d-standard-30` is explicitly invalid for a three-node topology under
the current CPU quota.

The Phase 1 candidate's read-only [availability receipt](cloud-availability.json)
records `n2-standard-8` in `us-west4-a` and the exact READY, non-deprecated Ubuntu
image. This proves catalog availability at the recorded time. Actual VM allocation,
current quota headroom, pricing, guest runtime and access preflights still precede
any paid execution; a catalog query does not reserve capacity.

## Planned profiles

| Profile | Independent topologies | Measurement | Retention |
| --- | ---: | ---: | --- |
| experiment | 1 | up to 300 seconds | GitHub Actions |
| failure-drill | 1 | up to 900 seconds | GitHub Actions |
| canonical | 3 serial repetitions | 1800 seconds each | GCS plus Actions summary |

The initial complete-run budget ceiling is USD 40 and maximum topology runtime is
5400 seconds. Phase 1 pricing/availability calibration may lower these values. Raising
resource, runtime or cost ceilings requires reviewed documentation before execution.

## Required cloud cells

The exact-source suite covers:

- published V4.4 single-node control on the selected leader-class host;
- healthy three-voter leader mutation latency/throughput;
- entry force, commit-proof force and end-to-end Future latency;
- one follower unavailable and one follower slow;
- follower lag, incremental catch-up and snapshot transfer;
- configured-leader process restart and quorum reconciliation;
- stale-incarnation fencing;
- permanent follower-disk replacement;
- bounded heap, queue, log, proof, snapshot, disk and network bytes; and
- identical committed application digest across all READY replicas.

Failure-drill must kill a process after durable entry quorum and before Future
completion, then independently prove recovery of the committed result. Canonical
requires every topology and aggregate set validation to pass; medians alone cannot
hide a failed member.

## Workflow readiness and cleanup

The future manual workflow must run only from exact protected `master`, under the
`cloud-benchmark` environment, with explicit paid-run confirmation. Before launch it
must validate Workload Identity workflow allowlisting, service-account permissions,
quota, zone capacity, image availability, unique resource names, private firewall and
the exact GCS prefix:

```text
gs://<evidence-bucket>/v5.0-replicated-single-shard/<source>/<run-attempt>/
```

IAM deletion is prefix-scoped. Cleanup is independent of run success and records all
VMs, disks, firewall resources and temporary objects. Failure artifacts and cleanup
receipts upload even when provisioning or a member fails. A later topology cannot
start until the preceding topology's resource deletion is verified.

## Admission sequence

No paid run occurs during Phases 0 or 1. Phase 6 paid execution requires, in order:

1. exact-master CI;
2. local model and process matrices;
3. production probe smoke evidence;
4. fake-cloud profile/set validation;
5. WIF/IAM/quota/image dry-run;
6. one experiment topology;
7. one failure-drill topology;
8. three canonical topology repetitions;
9. independent member/set validation and cleanup proof; and
10. append-only baseline registration through a separate protected PR.
