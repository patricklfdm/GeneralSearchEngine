# Native process loss during an unreturned write

This gate extends the [completed-DATA process history](PHASE_3_NODE_PROCESS.md)
to the actual leader's ACCEPT and PROOF parent-force boundaries. Each of the
four cut/mode combinations owns an independent bootstrap-to-close history.
It does not close Phase 3, qualify host power loss or imply autonomous failover.
The [source-bound receipt](phase3-evidence/node-inflight.json) retains each
execution, complete original replay, exact negative result and archive digest.

## Original history and recovery

`V53NodeInFlightTest` uses the real private `MembershipNodeOwner`, native TCP
and storage, with node 1 in a child JVM and the other two owners remaining live.
The first child completes election and BARRIER 1, then starts DATA 2. At exactly
`ACCEPT_PARENT_FORCED` or `PROOF_PARENT_FORCED`, the acknowledged observation
pipe records the boundary before `Runtime.halt(73)` or external SIGKILL.
The lock probe requires the specific ownership exception before death and
successful acquisition after death. No close method stands in for the crash.

The first DATA has no successful client completion. Its original bytes remain
on the same disk. A fresh child opens those exact paths in state NEW, discovers
the original retained tail and starts a higher-ballot election. Recovery must:

1. Install the independently derived original source and selected tail.
2. Reaccept the exact old DATA 2 under the new ballot, preserving its ENTRY
   origin, payload, previous digest and identity.
3. Establish the durable floor after that new ACCEPT, then force PROOF,
   application, retention authority and publication for DATA 2.
4. Publish a separate fresh-origin BARRIER 3 before READY, then accept DATA 4.

This is protocol recovery of one selected value; the client does not resubmit
its interrupted mutation. Both leader lifetimes use the existing 180-second
fixture budget and default transport bounds. Instrumentation adds overhead;
these observations are not a throughput or failover-latency measurement.

## Independent validation

`node_inflight_evidence.py` derives the original ACCEPT/PROOF contents before
reopen, the fresh frozen bases, selected tail, installed generations and all
sixteen snapshot groups. It validates complete original request/response and
source bytes across seven phases: first activation, BARRIER 1, interrupted
DATA 2, second activation, carried DATA 2, BARRIER 3 and DATA 4.

An ACCEPT cut permits no PROOF or publication. A PROOF cut requires the actual
remote ACCEPT and its delivered receipt before the leader's original PROOF;
that proof has not yet been dispatched. The successor's selected sources must
agree on the retained value. Old entry origin is preserved while new ACCEPT,
PROOF and the readiness barrier belong to the new ballot.

Process validation requires distinct child identities, observed exit codes,
original paths, exact child/merged event equality and an instrumentation record
ending at the declared durable boundary. READY cannot be copied from the first
lifetime. Neither a missing new ACCEPT nor floor retirement before it qualifies.
Reopen forces the exact retained pending phase: ACCEPT for an ACCEPT cut, PROOF
for a PROOF cut. The initial PROOF replay rejected that distinction because it
reused the completed-DATA fixture's ACCEPT expectation. The reader correction
follows `MembershipPendingAccept.sealActive`; an exact negative rejects a
substituted phase, and the original failed replay remains retained.

The shared cold-reopen readers retain their default non-carried behavior.
Existing completed-DATA process histories and the retained same-process native
history provide regression coverage for those defaults. Original validation
precedes every evidence mutation; only its exact expected rejection counts.

## Local qualification

All six native JVM tests passed without skips: four in-flight combinations and
the two existing completed-DATA cases. The 27 focused Python tests passed.
Complete original replay plus all 158 exact negatives passed in 201.493 seconds:
20 for each in-flight history, 15 for each completed-DATA history and 48 for the
unchanged retained cold-reopen history. The latter is a reader regression against
its original producer, not a new workload execution.

| In-flight cut | Process mode | Original request writes | Original responses | Exact negatives |
| --- | --- | ---: | ---: | ---: |
| ACCEPT parent forced | SIGKILL | 549 | 510 | 20 |
| ACCEPT parent forced | halt | 521 | 509 | 20 |
| PROOF parent forced | halt | 525 | 513 | 20 |
| PROOF parent forced | SIGKILL | 524 | 512 | 20 |

An attempted write is not an observed response or delivery. Every unanswered
attempt is classified from its exact original bytes and phase; it grants no
quorum authority. The receipt/archive retain producer snapshots, raw histories,
initial failed reader diagnostics, corrected reader sources, test reports and
per-file hashes without JARs or class files.

[Rename-boundary process recovery](PHASE_3_NODE_RENAME_PROCESS.md) extends this
reader to the earlier atomic-replacement boundary while retaining these original
parent-forced case results. Its process-loss evidence cannot infer a directory
force or host power-loss durability.

## Remaining scope and rollback

Other installation/publication crash cuts, competing automatic candidates,
membership transitions and the seven-profile matrix remain required. Keep each
bootstrap/crash/restart history on one original filesystem and runner; only
independent complete histories may be parallelized in hosted acceptance.

Rollback removes the in-flight fixture and reader and the optional carried/cut
parameters in the existing readers. This batch changes no production Java,
public API, POM, workflow, persisted format or frozen resource/time limit.
