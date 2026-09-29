# V5.1 Phase 6C3C21 — owned complete experiment

**Status:** accepted through PR #252 on master
`471a36eea31f6e7cd5cbbdf4cd963f352fb29059`,
[exact-master CI 36566870122](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36566870122)
attempt 1, all 29 jobs passed. Complete native-UID/mount experiment qualification
passed in 16m04s; the job including setup/upload took 17m02s. This is no-GCP owned
workload acceptance, not native cloud or paid admission.

## Scope and order

One modeled reservation, lease and three-node topology executes the frozen order:

| Cell | Owned work | Whole-cell ceiling |
| --- | --- | ---: |
| healthy | Published V4.4 local, published V5.0 configured, candidate V5.1 automatic; same immutable source; 90 calls per mode | 300s per mode, 900s total |
| leader-loss | Original leader SIGKILL, surviving majority progress, retained restart and rejoin | 120s |
| maintenance | Captured read across rejoin, release, checkpoint, backup and published V4.4 restore | 240s |
| no-quorum | All-node isolation, conservative refusals, heal and durable rejoin | 120s |

There are six fresh group identities, sixteen persistent services and three
package installations. Healthy uses the existing three-mode coordinator and
unchanged physical/history/backup validators. Fault cells each use an EMPTY
two-field bootstrap on their own receivers. A shared package pool consumes each
installation once; a lost submission reply only queries its original receipt.
The existing two-cell `--faults` entry remains a separately required gate.

No frozen workload, capacity, election, operation or preparation/validation/cleanup
budget changes. The 24-call ceiling, four fresh progress pairs, four final reads,
60-second progress/rejoin ceilings and all rejected attempts remain observable.

## Maintenance

A closed `pin` command consumes one public read intent and returns its original
operation identity while the callback remains paused at `READ_CAPTURED`.
`pin-state` observes the existing JVM/trace; it does not submit another read.
The same old-leader edge rules are installed in all three independent receivers
(request hooks execute on the sender). Only after this barrier do the two surviving voters prove
progress, and healing must yield an actual `REJOIN_INSTALLED` while that same read
is still pending. Its returned documents must equal the original seed view.

Only after release and a subsequent zero-pin sample may checkpoint and backup
run. They are each original operations, with no mutation retries. All voters
close before the backup owner runs a separately compiled V4.4-only consumer.
The retained export is restored again during independent controller replay.
Both restores must match the physically checked final view and backup sequence.
A 60-second emergency network heal makes validation fail; it cannot replace the
controller's recorded healing. The read hook retains its existing 60-second bound.

## Complete acceptance

`guest_experiment_evidence` requires all four original timelines, the same exact
request/source/package, six distinct groups and nonoverlapping cell intervals.
It replays the original three-mode healthy evidence plus every fault's original
receipts, complete exchanges, physical authority, force/proof/read history and
negative mutations. Combined compressed/expanded/file/trace budgets apply across
all sixteen guest collections. A healthy-only or two-fault receipt cannot close
this aggregate. Failed preparations, calls and partial collections remain retained.

`ownedExperimentQualified` denotes this offline owned workload assembly only.
`paidCloud` and `fullRemoteQualification` remain false. Provider identity, disks
and ledger/lease facts are modeled. Native IAP, real block writes, trusted
preflight, separate V5.1 cloud workflows and paid qualification remain open.

## Entry points and validation

```bash
python3 -m scripts.v51.guest_owned_qualification target/v51-owned-experiment \
  --bundle target/v51-experiment-package --source "$GITHUB_SHA" \
  --experiment --allow-sudo-namespace
```

The focused `--maintenance --fault-local` entry exercises real SSH and actual
JVMs at independent local paths without claiming mount isolation. Complete
experiment CI uses native UIDs and isolated mount views; it cannot fall back to
the local path qualifier. Complete healthy bootstrap requires identical mount
paths across receivers; separate local directories are deliberately rejected. All original lost package, source, launch, operation
and shutdown replies stay enabled in the complete experiment qualification.

The [CI partition](../../CI_V51_FOUNDATION_LANES.md) makes this aggregate an
independent required lane. The accepted CI establishes this source's full native-UID result and timing.
The [next candidate](PHASE_6_CLOUD_PREFLIGHT.md) adds read-only source/provider
observations and separate V5.1 manual workflows. Cloud runs still require
exact-request confirmation and user triggering.
