# V5.1 Phase 6C2B: frozen fault JVM workloads

**Status:** accepted through PR #225 at master
`22328ed4dc358e0adc7fde1399528295ebf8d2a3`.
[Exact-master CI 35989431966](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35989431966)
passed all 21 jobs, including this twelve-cell gate and Required. This accepts the
fault-document amendment and local fault qualification; full 6C remains open.

The [approved document-size amendment](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md#approved-fault-document-amendment)
adds only encoded-document ceilings of 4100 bytes for interrupted-transfer and
20004 bytes for minority-capacity. The original values remain 4096 and 20000
bytes; the codec adds the four-byte key. All other frozen parameters remain
unchanged. Current plan SHA-256:
`f0e964ba12fea8702a40082d4a01a85d6d3eb1bf7fe3fecf8778c899af44bea7`.
Historical calibration retains its original hash and measurement identities.

## Scope and remaining exit

This gate implements all twelve two-field fault cells from the
[6B contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md). Receipts identify
`local-guest-faults-only`, `paidCloud=false`, `fullRemoteQualification=false`.
Each scenario owns fresh authority, three actual TCP JVMs, its original deadlines
and all attempted public calls. These are local guest-path observations; they
supply neither GCP network performance nor a failover SLA.

The separate 512-slot full-size basis/wire/transfer/re-proposal/pinning and
**two-generation retention** boundary now has a separate [component candidate](PHASE_6_FULL_SIZE.md).
Protected acceptance and public-runtime integration remain open. Small fault histories and the
older synthetic encoding calculation cannot close it. The 6C3 provider adapter,
source-bound identity/configuration review and remote failure matrix also remain
open. Full 6C and paid preparation stay blocked on those exits.

## Public execution and fixed fault ownership

[`remote_faults.py`](../../../scripts/v51/remote_faults.py) submits one durable
`fault` command for each cell through the 6C1 command store. A lost command reply
has the existing query-only semantics; it cannot rerun a cell. The trusted handler
starts persistent public-API JVM consumers and records every command, outcome,
disconnect, PID, Linux start tick, process generation, stopped-authority archive,
network rule and resource boundary. No external request supplies an executable.
Cancellation retains the consumed command and stops owned voters.

Each cell predeclares 24 logical call IDs and the fixed seed/target/progress/refusal
tags. Seeds are exactly three two-document ADD_ALL calls with 64-byte values,
then a strong read. Each later bulk uses fresh keys. At most four progress pairs
and four final read attempts may occur, within the total 24-operation cap.
Checkpoint and backup count against that cap. Status queries do not fabricate
application calls or successful barriers. An uncertain mutation is never replayed.

All voters use the same frozen 1200/3600/6000/9600-ms policy, four pending calls,
1-MiB frames, 4096-byte chunks and common 64-MiB replica limits. Only the declared
node-3 128-KiB minority bound and document exceptions differ. The worker emits its
actual configured getters; the validator checks every voter and restart. It uses
the frozen JVM flags and application queue/planner/storage bounds. Test observers
and consumers compile outside production JARs.

| Scenario | Concrete observation |
| --- | --- |
| leader-loss | Seed-read leader is SIGKILLed; fresh majority progress precedes retained restart/rejoin. |
| isolated-old-leader | Bidirectional drops, minority refusals and majority progress, followed by heal. |
| asymmetric-requests / responses | Exact direction/barrier drops and reverse traffic; response drops require the peer's original reply. |
| slow-follower | The actual selected voting follower delays ACCEPT/PROOF force by 1500 ms; begin/end timestamps, progress and recovered prefix are retained. |
| interrupted-transfer | Isolate the follower outside the selected healthy pair; force the large source, pause the first durable 4096-byte transfer progress, SIGKILL, archive and reopen the original partial authority. |
| entry-chosen / proof-quorum | Actual acknowledgement cuts precede SIGKILL; the disconnected target remains uncertain and its forced quorum/proven prefix is independently reconstructed. |
| group-restart | All original processes stop before any retained replacement starts. |
| maintenance | A paused captured read crosses majority progress and retained rejoin; its original view survives release. Public checkpoint/backup is restored in a separate pinned V4.4 JVM. |
| no-quorum | All directions drop for 15 seconds; conservative refusals precede fresh write/read progress after heal. |
| minority-capacity | Healthy-pair activation under bounded PREPARE routing, removal of routing faults, exact large bulks, real reservation rejection and healthy reads after both retained restarts. |

The minority fixture starts the healthy pair before node 3, within the original
cell startup budget; all three processes overlap before the common seed/fault.
It preserves node 3's election policy. PREPARE rules are removed before seed work
and before requiring its catch-up. Waiting for node 3 to adopt a ballot while
blocking the PREPARE needed to adopt it would deadlock the controller.

Fifteen-second network/slow-force intervals use an independent timer. Waiting for
an election or API response cannot extend the injection. A single directed graph
need not allow a complete two-way basis exchange: directional cells keep actual
traffic and all failed attempts, heal on schedule, and allow any valid leader
after heal. Fresh progress still has the original sixty-second ceiling. Selecting
only the old leader's peers forever after heal would incorrectly reject a valid
new campaign won by that voter.

First progress and retained rejoin each remain within sixty seconds, clipped to
the original 120/180/240-second whole-cell ceiling. Startup, control, pause, drain,
close and separate restore time remain charged. Cleanup runs on failure as well;
passing a later operation never removes a prior failed attempt.

## Independent qualification and evidence

[`remote_fault_evidence.py`](../../../scripts/v51/remote_fault_evidence.py) checks
exact payloads and predeclared IDs, conservative availability combinations, process
lifetimes, actual loaded JAR hashes, frozen configuration, per-second resource
samples, queue/permit/disk bounds, closed reservations and the original clocks.
The existing exhaustive two-field history checker and physical decoder separately
validate forced votes, proofs, selected/transferred bases, publication and captured
read bytes. A status `LEADER_READY` or controller `EXECUTED` alone cannot pass.

The common authority decoder now accepts an explicit no-restart mode for scenarios
that intentionally use three processes. Its default still requires the earlier
four-process retained-restart evidence. This gate separately checks exact process
and archive requirements for each scenario; it cannot pass a crash case with
three processes. There is no dummy restart to satisfy a historical checker shape.

Stopped authority is archived under unique node/generation paths. The validator
checks every member, digest and unchanged bootstrap identity before recognizing
rejoin. Interrupted-transfer additionally matches the original partial file to
actual wire chunks and its durable 4096-byte progress record. Capacity evidence
must exceed the real sealed retained bound; unrelated rejection reasons do not
substitute for resource pressure. Once an actual recovery-write capacity rejection
quarantines node 3, the public facade reports `STORAGE_FAILURE` for subsequent
calls. This is recognized only for its two declared refusal calls, after the same
process's original `CAPACITY_EXCEEDED` wire reply, with matching retained inventory
and real over-budget arithmetic. It is not an allowed general recovery outcome.
A quarantined runtime rejects public enqueue while its owned control thread still
runs. The fault-only diagnostic method places a read-only observation in that
thread's bounded mailbox after confirming this exact closing condition. It never
submits an engine mutation, clears quarantine or hides the public failure. Other
performance probes retain their existing diagnostic entry point. A required
`resource-rejected` sample exercises this path before the minority refusal calls.
Maintenance compares the separate published V4.4 restore with the final captured
public state.

The gate retains complete bounded traces and histories, rejects missing fault
witnesses, changed seed values, extended progress times and altered causal/physical
facts, then packs binary parts and independently replays an extracted bundle at a
new path. Parts/member/trace/response ceilings inherit 6B; no truncation can produce
PASS. Failed raw evidence remains available for the workflow's always-upload step.

## Reproduction and CI

### Local candidate validation

The complete gate passed at `target/v51-remote-faults/run.IXwmZn/evidence`:
twelve cells, 105 public calls and 41 evidence-negative variants. Two binary
parts retained 2136 files; independent validation passed again after extraction
at a different path, including the final stricter trace and process checks.
`target/v51-remote-faults/validation-summary.json` records the receipt digest,
current plan hash and individual cell durations. Earlier failed development
evidence remains retained separately.

All 431 V5.1 Python tests and 27 CI/toolchain fixture tests passed. Workflow YAML,
all 120 shell blocks and documentation checks passed. External Java adapters were
compiled and executed against the packaged PR #224 runtime artifacts; production
Java is unchanged. This batch did not rerun the complete Maven reactor locally.
The candidate subsequently passed protected CI as recorded above.

### Commands

```bash
scripts/verify-v51-phase6-remote-faults.sh
# With fresh candidate JARs already packaged:
scripts/verify-v51-phase6-remote-faults.sh --skip-build
```

The independent `V5.1 frozen fault workloads (no GCP)` job now restores the [shared verification build](../../CI_V51_BUILD_DOMAIN.md),
has a sixty-minute job backstop and always-uploaded fourteen-day
local evidence under `target/v51-remote-faults`. `Required` includes this lane;
documentation-only changes preserve the existing skips. Paid retention remains
a separate thirty-day requirement. Commit, push, PR and cloud dispatch remain
operator actions.
