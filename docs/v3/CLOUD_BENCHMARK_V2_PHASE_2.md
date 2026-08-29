# Cloud Benchmark V2 Phase 2 canonical set aggregation

## Status and authority

This document freezes the Phase 2 implementation contract before code is written. It
specializes the normative [Phase 0 evidence model](CLOUD_BENCHMARK_V2_PHASE_0.md) for
independent run-set execution, checkpointing, replacement, aggregation, and final set
artifacts. Phase 0 wins if the documents conflict; implementation must amend this
contract in review instead of silently choosing different semantics.

Phase 2 builds on the Phase 1 schema-1 run manifest and normalized metrics. It creates
no comparison policy, baseline registry, GCS object, GitHub paid workflow, performance
gate, or product optimization.

## Goals and boundaries

Phase 2 must provide:

- a thin `run-cloud-benchmark-set.sh` wrapper above the unchanged one-run V1 command;
- at least three fresh, sequential VM lifecycles for a canonical set;
- an atomic, resumable slot/attempt state machine;
- explicit and auditable infrastructure replacement without score selection;
- strict compatible-member validation;
- deterministic median and run-to-run variation evidence;
- an immutable final set manifest, aggregate metrics, and attempt audit.

The existing command remains the shortest single experiment path:

```bash
./run-cloud-benchmark.sh full
```

Phase 2 does not route an evidence profile through that command, run repeats inside one
VM, select the fastest member, discard a valid slow member, scrape benchmark console
logs for metrics, or authenticate to GCP in normal CI.

## User-facing commands

Start or validate a new set with:

```bash
./run-cloud-benchmark-set.sh \
  --dry-run \
  --evidence-profile canonical \
  --repeats 3 \
  full

./run-cloud-benchmark-set.sh \
  --evidence-profile canonical \
  --repeats 3 \
  --confirm-paid-run \
  full
```

Resume only pending slots in an existing workspace:

```bash
./run-cloud-benchmark-set.sh \
  --resume benchmark-results/v3-production/sets/in-progress/WORKSPACE \
  --confirm-paid-run
```

Authorize and run one replacement only after an eligible infrastructure failure:

```bash
./run-cloud-benchmark-set.sh \
  --replace benchmark-results/v3-production/sets/in-progress/WORKSPACE \
  --slot 2 \
  --reason 'VM terminated before evidence recovery' \
  --confirm-no-score-selection \
  --confirm-paid-run
```

New-set, `--resume`, and `--replace` forms are mutually exclusive. A reason is a
non-empty, single-line UTF-8 string of at most 500 characters. A command that may create
a VM requires `--confirm-paid-run`; dry run never creates local set state or a cloud
resource. Resume may finalize without that flag when no VM launch remains.

The Python utility owns canonical JSON, hashing, validation, state transitions, and
statistics. Internal state operations may be subcommands of
`scripts/cloud/benchmark_v2.py`; they are not a second user-facing orchestration API.

## Profiles, repeats, and modes

Canonical sets require:

- `evidenceProfile=canonical`;
- 3 through 10 declared slots;
- `full`, `concurrency`, `soak`, or `all` mode;
- Standard provisioning;
- a clean exact pushed commit;
- one exact image resolved before slot 1 and reused for every slot;
- one versioned workload preset;
- sequential execution in Phase 2.

Experiment sets accept 1 through 10 slots and any V1 mode. They remain
`VALID_EXPERIMENT_SET`, cannot be registered as a baseline, and may retain schema-0 or
Spot limitations as explicit warnings. Repeated experiment members are still separate
VM lifecycles; the wrapper never loops a workload inside one VM.

Phase 2 freezes these canonical preset IDs:

| Preset | Mode | Frozen workload controls |
|---|---|---|
| `v3-production-full-v1` | `full` | JMH `2/3/5/1s`; 100,000 concurrency documents; groups `1,1 4,1 16,1` |
| `v3-production-concurrency-v1` | `concurrency` | JMH `2/3/5/1s`; 100,000 documents; groups `1,1 4,1 8,1 16,1 24,1 30,1` |
| `v3-production-soak-v1` | `soak` | 1,800 seconds; 16 readers; 1 writer; 100,000 documents; one-second samples; top-K 10; `zipf-en-medium-4`; revision updates; index cycles enabled |
| `v3-production-all-v1` | `all` | full-v1 JMH and groups plus soak-v1 controls |

All presets use suite schema 1. Presets freeze workload controls, not hardware identity.
Machine, project, zone, and ordered JVM options are separately selected before the set
starts, recorded in the plan, and frozen across its slots; their defaults remain
`c3d-standard-30` and `-Xms8g -Xmx16g`. They may differ between separately named
canonical sets because the environment fingerprint prevents silent comparison. A
conflicting workload override fails before state or cloud mutation.

The current VM bootstrap installs Java from apt. The wrapper cannot know the exact JDK
build before the first VM. Every member records it, and exact Phase 1 environment
fingerprint equality remains mandatory. A package update between slots makes the set
incompatible rather than being normalized away.

The wrapper records the preset ID in new raw metadata. Phase 1 manifest derivation is
extended additively to expose and validate that ID for canonical members. Existing raw
runs without the field may remain experiments but cannot be selected into a Phase 2
canonical set.

## Preflight and dry-run contract

Before creating an in-progress workspace, the wrapper must:

1. validate its arguments and the profile/mode/repeat/preset combination;
2. require a clean repository and resolve the exact 40-character `HEAD` commit;
3. prove that commit is fetchable from the configured repository;
4. resolve project, zone, machine, network/SSH, exact image, JVM, and preset controls;
5. require Standard provisioning for canonical sets;
6. show slot count, per-slot V1 mode, maximum runtime, exact image, cleanup behavior,
   state destination, and worst-case VM count;
7. invoke only existing read-only V1/GCP validation in dry-run mode.

Dry run may use a temporary local directory and read-only `gcloud` calls but leaves no
set workspace, VM, disk, upload, IAM change, or tracked file.

## Exact V1 attempt binding

The set wrapper must never guess which orchestration record belongs to an invocation.
Phase 2 adds one backward-compatible local control-plane variable to V1:

```text
GSE_CLOUD_ORCHESTRATION_POINTER_FILE
```

When set, V1 validates that the target does not exist, its parent already exists, and
the target is not a symlink. Immediately after allocating its orchestration record, V1
atomically writes that record's absolute path to the pointer. The pointer is local
control state: it is not copied to the VM, raw metadata, fingerprints, or final set
identity. Ordinary V1 invocations without the variable are unchanged.

The attempt intent stores the pointer's workspace-relative path before V1 starts. After
V1 returns, the wrapper requires exactly that finalized record and uses its instance,
commit, mode, result path, lifecycle outcome, and digest. It then invokes Phase 1
manifest derivation with the matching raw run and explicit record. Console output is
retained only as an attempt log and is never a metric source.

## In-progress workspace

The mutable execution layout is:

```text
benchmark-results/v3-production/sets/in-progress/<workspace-id>/
  set-plan.json
  checkpoint.json
  attempts/slot-001/attempt-001.json
  replacements/slot-001/replacement-001.json
  control/slot-001-attempt-001.orchestration-pointer
  logs/slot-001-attempt-001.log
```

The workspace ID may contain UTC time and randomness. It is not a scientific identity
and never appears in a final set artifact. Absolute paths, local usernames, IPs, PIDs,
and temporary file names also stay out of final artifacts.

`set-plan.json` is immutable after initialization and has schema version 1. It records:

- profile, mode, preset ID, and declared slot count/order;
- source repository and exact target commit;
- frozen project, zone, machine, Standard/Spot model, exact image identity, JVM options,
  workload controls, and bounded maximum runtime;
- expected derived destinations and state schema versions.

`checkpoint.json` is mutable control state with schema version 1. It records a monotonic
revision, overall state, every slot state, next pending slot, current attempt intent,
and final set ID when complete. Updates use a same-directory temporary file, flush,
`fsync`, and atomic replace. The plan is hashed in every checkpoint.

Allowed overall states are `READY`, `RUNNING`, `BLOCKED_INFRASTRUCTURE`,
`BLOCKED_FAILURE`, `INCOMPATIBLE`, `UNRESOLVED`, and `COMPLETE`. After each valid member,
the wrapper compares it with prior selected members. A fingerprint, preset, metric, or
other member-compatibility mismatch moves the set to `INCOMPATIBLE`, returns exit `83`,
and launches no later slot. The individually valid member is retained and is not
replacement-eligible.

Finalized attempt and replacement records are immutable. Creating a new attempt first
checkpoints `RUNNING`; after V1 and analysis finish, the immutable result is written
before the checkpoint advances. A crash with a `RUNNING` attempt is reconciled only
from its exact pointer and orchestration record. If lifecycle/cleanup cannot be proven,
resume stops with `UNRESOLVED` and launches no VM.

## Slot state machine

Allowed slot states are:

```text
PENDING
RUNNING
VALID_MEMBER
INFRASTRUCTURE_INVALID
BENCHMARK_FAILURE
CONFIGURATION_FAILURE
EVIDENCE_INVALID
UNRESOLVED
```

Allowed transitions are:

```text
PENDING -> RUNNING -> VALID_MEMBER
                   -> INFRASTRUCTURE_INVALID
                   -> BENCHMARK_FAILURE
                   -> CONFIGURATION_FAILURE
                   -> EVIDENCE_INVALID
                   -> UNRESOLVED

INFRASTRUCTURE_INVALID -> replacement authorization -> RUNNING
```

Resume skips every `VALID_MEMBER`, never starts a second attempt for `RUNNING`, and
never crosses a blocked state implicitly. Successful slots continue sequentially.

V1 exits `10`, `20`, `40`, `50`, `60`, and `70` are
`INFRASTRUCTURE_INVALID` and replacement-eligible only through the explicit command.
V1 exit `30` is `BENCHMARK_FAILURE`; exit `2` is `CONFIGURATION_FAILURE`. Phase 1 exits
`80`, `81`, and `82` are `EVIDENCE_INVALID` and are not replacement-eligible in Phase 2
because silently rerunning could hide a schema, workload, or analyzer defect. Unknown,
lost, or contradictory process state is `UNRESOLVED`.

The wrapper checkpoints the classification and returns the underlying V1 or Phase 1
exit code. It does not translate a failed attempt into success. Python set validation
uses exit `83` for incomplete or incompatible set state.

## Replacement and anti-selection rule

Replacement is permitted only when the current slot is `INFRASTRUCTURE_INVALID` and no
later slot has started. Before a replacement VM is created, the wrapper atomically
writes an immutable authorization containing:

- slot and prior attempt ordinal;
- exact V1 exit and infrastructure category;
- orchestration/raw identities and digests when available;
- the user's reason;
- `confirmedWithoutScoreSelection=true`;
- the next attempt ordinal.

`--confirm-no-score-selection` is an explicit attestation that replacement was chosen
from infrastructure validity, not after selecting among benchmark scores. The previous
attempt, log, raw/partial/quarantined evidence, and orchestration record remain. A valid
slow member, benchmark failure, schema failure, metric conflict, or environment mismatch
is never replaceable in Phase 2.

## Member validation and independence

A final canonical set requires exactly one selected member for every declared slot and:

- at least three `VALID_CANONICAL_MEMBER` run manifests;
- the planned preset ID on every member;
- distinct raw run IDs, instance names, orchestration record digests, and member
  manifest digests;
- successful independent cleanup proof for every instance;
- identical repository, commit, mode, profile, suite/schema, environment fingerprint,
  and benchmark configuration fingerprint;
- identical metric ID sets and exact identity/unit/direction/policy metadata;
- a verified normalized-metrics digest matching each run manifest;
- no hidden slot, member, attempt, replacement, or metric exclusion.

Branch and timestamps are provenance and need not match. Different project IDs are not
fingerprint inputs, but the frozen execution plan requires one project for the set.
Exact JDK, image, kernel, zone, CPU/topology, normalized memory capacity, provisioning,
JVM, or configuration fingerprint mismatch makes the set incomplete with exit `83`.

JMH may omit `gc.time` when `gc.count` is zero. Derivation normalizes that exact shape
to `gc.time = 0 ms`, records the inference in the metric's `normalization` provenance,
and preserves a stable metric identity set across independent runs.
Missing `gc.time` with a non-zero `gc.count` remains invalid evidence; no other missing
profiler metric is manufactured.

An experiment set uses `VALID_EXPERIMENT` members, requires identical source/mode/config
fingerprints and metric identities, and requires environment fingerprints to be equal
when present. All-null legacy environment fingerprints are allowed with warnings; a
mix of null and non-null is incompatible. When it declares more than one slot, raw run
IDs, instance names, orchestration digests, and member manifest digests must also be
distinct.

## Deterministic set identity

The final set identity payload has schema version 1 and contains only:

```text
evidence profile
source commit
mode
suite name and schema version
environment fingerprint
benchmark configuration fingerprint
ordered slot identities
```

Each slot identity contains the slot number, selected raw run ID, instance name, member
manifest SHA-256, and a canonical per-slot attempt-audit SHA-256. The audit digest binds
invalid attempts and replacement decisions without including the temporary workspace
ID or local paths. The set ID is:

```text
gse-set-v1-<SHA-256 of canonical identity payload>
```

The ordered slot list prevents member reordering. Member manifest hashes prevent
substitution. Audit hashes prevent replacement history from disappearing. The final
directory is `benchmark-results/v3-production/sets/<set-id>/v1/`; an existing collision
succeeds only when every byte is identical.

## Aggregate metric schema version 1

`aggregate-metrics.json` contains the set ID, member count, suite identity, aggregation
method, and metrics sorted by the unchanged Phase 1 metric ID.

For every numeric metric it records:

```text
source metric identity, statistic, unit, and direction
ordered slot/run/value tuples
count
minimum
median
maximum
absoluteRange = maximum - minimum
relativeRangePct = absoluteRange / abs(median) * 100
```

The median sorts finite canonical run-level values. For an odd count it is the middle
value; for an even count it is the arithmetic mean of the two middle values. If median
is zero, `relativeRangePct` is `null` with
`relativeRangeUnavailableReason=median_zero`. There is no division by zero, member
trimming, fastest-run selection, fork pooling, percentile pooling, or invented
cross-run confidence interval.

A source sample percentile is labeled `median_of_run_percentile`, retains its original
percentile and semantics, and is not described as a pooled request percentile. Other
numeric metrics use `median_of_independent_run_values`. Diagnostic numeric metrics are
aggregated but remain diagnostic.

Categorical Boolean/string metrics use `aggregationKind=consensus`: ordered values,
distinct values, `allEqual`, and an optional unanimous value. They do not receive
numeric min/median/range or generic regression semantics. Numeric categorical validity
facts also use consensus so that counts such as errors are not presented as performance
improvements.

A missing metric, duplicate metric, non-finite canonical value, changed unit/identity,
or changed value type makes the set incomplete. Phase 2 never reduces the member count
for one metric.

## Final artifacts

One completed set writes:

```text
benchmark-results/v3-production/sets/<set-id>/v1/
  benchmark-set-manifest.json
  aggregate-metrics.json
  set-attempt-audit.json
  set-checksums.sha256
```

The set manifest has `schemaVersion=1`, `kind=benchmark-set`, and records:

- set ID, status (`VALID_CANONICAL_SET` or `VALID_EXPERIMENT_SET`), profile, and preset;
- source repository/commit, mode, suite, both fingerprints, and warnings;
- ordered members with slot, run ID, instance, portable derived-run reference, manifest
  digest, metrics digest, orchestration reference/digest, and slot-audit digest;
- aggregation method, metric count, relative aggregate path and digest;
- relative attempt-audit path and digest.

`set-attempt-audit.json` contains every declared slot, every finalized attempt outcome,
and every replacement authorization in order. It contains portable evidence references
and digests, not console metric values, timestamps generated by finalization, temporary
workspace IDs, or absolute paths.

All final JSON uses the Phase 0 canonical serialization. `set-checksums.sha256` covers
the three JSON files. Final artifacts are generated together, never written below raw
run directories, never mutate member manifests, and are byte-identical when all source
bytes and decisions are identical. The completed in-progress workspace is retained with
`state=COMPLETE` and its final set ID for audit/resume idempotence.

## Safety and no-cost implementation gates

Phase 2 implementation must not create a real VM. Tests use temporary result trees,
synthetic Phase 1 manifests/metrics, and a copied fake V1 runner. No test seam may allow
an arbitrary command from an untrusted environment variable in production mode.

Required tests include:

- canonical argument/preset/repeat validation and mutation-free dry run;
- exact orchestration pointer binding and ordinary V1 compatibility when unset;
- three distinct compatible members and deterministic set ID/artifacts;
- odd and even median, min/max/absolute/relative range, and zero-median reason;
- sample-percentile labeling, diagnostic numeric aggregation, and categorical consensus;
- exact metric-set, unit, type, source, profile, preset, commit, mode, suite, environment,
  and configuration mismatch rejection;
- fastest and slowest members both retained;
- checkpoint after every transition and idempotent resume skipping valid slots;
- eligible infrastructure stop, explicit replacement audit, and no-score attestation;
- benchmark/configuration/evidence failures not replaceable;
- unresolved `RUNNING` state launches nothing;
- crash-safe atomic checkpoint recovery and conflicting final artifact rejection;
- preservation of all existing Phase 1, fake-gcloud, soak, reactor, compatibility, and
  release gates.

## Phase 2 completion checklist

- [x] V1 one-run CLI remains behavior compatible.
- [x] Canonical presets and paid-run confirmation are enforced before mutation.
- [x] Set plans, checkpoints, attempts, and replacements follow versioned schemas.
- [x] Every V1 attempt binds to one exact orchestration record without log guessing.
- [x] Resume and replacement cannot rerun or silently discard valid evidence.
- [x] Three or more compatible independent members are required for canonical status.
- [x] Set identity binds ordered members and complete attempt audit.
- [x] Numeric and categorical aggregation follow the frozen semantics.
- [x] Raw runs and Phase 1 derived runs remain immutable.
- [x] Final artifacts are deterministic, portable, checksummed, and collision-safe.
- [x] All synthetic/no-cloud and existing repository gates pass.
- [x] No comparison, registry, GCS, workflow-dispatch, or product work is included.
