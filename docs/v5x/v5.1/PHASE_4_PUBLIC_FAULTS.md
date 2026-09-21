# V5.1 Phase 4D: public fencing and mutation fault matrix

**Status:** implemented and locally qualified on
`test/v5.1-phase4-public-fault-matrix`, based on accepted Batch C master
`6d3fbb7ae149222903eba4ccbce0cab5cafb1cf4` (PR #194, exact-master CI `35560692475`).
Protected Batch D and complete Phase 4 acceptance remain open.

## Public process boundary

Run `scripts/verify-v51-phase4-public-faults.sh --skip-build` after packaging current
sources. The complete gate contains 19 cases, each with three simultaneous public
JVM voters and a retained-directory restart in a fourth process. The external
consumer compiles against candidate JARs outside implementation packages. Bootstrap,
start, mutations, strong reads and close all use the public API.

A separate observer owns network fault injection and precise pauses/crashes. It can
drop real outbound requests/responses, pause an application observation point, halt
a worker or let the controller SIGKILL it. It cannot call private activation,
initialize voters, mutate authority files or force a ballot on the engine's behalf.
Election and higher promises are produced by the running protocol.

## Three partition and read-fence cases

| Case | Schedule and expected public result |
| --- | --- |
| Isolated old leader | Split the old leader from both peers; the surviving majority elects and acknowledges a tagged atomic bulk. Later old-leader reads fail and the subsequent mutation is NOT_SUBMITTED. Heal and reopen the retained old node; the acknowledged application survives. |
| Promise before capture | Pause after a read's NO_OP publication but before its current-ballot/cut check. Partition, let the other majority write, briefly heal to deliver higher-ballot traffic, observe an actual forced higher promise, isolate again and release the pause. The read returns STALE_EPOCH without invoking its query callback. |
| Promise after capture | Pause after the validated view is captured. Repeat the majority write and forced higher-promise crossing. The pending read completes with its earlier captured documents; its invocation overlaps the later write. A new old-leader read still fails. |

The fixture freezes a 60-second operation deadline through public bootstrap, while
keeping heartbeat/election/transport settings unchanged. This gives the controller
time to exercise the ballot boundary explicitly; it is not a production default or
performance claim. A cached LEADER_READY hint alone is not treated as proof of a
currently reachable quorum. Actual strong-read outcomes and decoded force records
establish the safety property.

The runtime emits an observation-only validation record under the protocol monitor,
then exposes the pausable capture event after releasing it. The physical oracle
checks the validation record against the latest local forced promise at that point.
A later promise may legally precede the pausable observation or the view's release;
moving it before validation must fail the independent check. A separate crossing
check requires the higher forced promise strictly
inside the pause interval; removing that record must invalidate the evidence.

Capture also rechecks cancellation, close and the finite deadline after acquiring
the protocol monitor. Waiting for that monitor can outlive the initial check. A
Java regression pauses before capture until the public deadline expires, releases
the pause and proves that the query callback is never invoked; a following mutation
drains the same application worker successfully.

## Sixteen public mutation interruption cases

Each boundary below runs once with `Runtime.halt(71)` and once with SIGKILL:

1. Before local ACCEPT write.
2. After local ACCEPT force.
3. After receiving the remote ACCEPT receipt.
4. Before local PROOF write.
5. After local PROOF force.
6. After receiving the remote PROOF receipt.
7. Before application publication.
8. After application publication, before client completion.

The observer records forces before exposing their corresponding post-force cut.
After arming a crash, other observed paths in that JVM cannot race past the cut
while the controller delivers SIGKILL. A read pause remains cooperative and permits
the control thread to process a higher promise. These observer gates are test-only.

Every interrupted mutation stays pending in the controller history. No uncertain
operation is retried. The independent cut audit binds the interrupted payload to
its actual entry, receipts, proof and publication. Once a remote ACCEPT receipt
establishes the entry quorum, the tagged value must survive failover, even if its
original proof or response was absent. Before quorum, inclusion is checked as an
allowed uncertain outcome rather than falsely counted as an acknowledged success.

Each crash retains its requested/observed boundary, PID, generation and exit code,
plus a verified exact-file inventory/archive before reopening. Source inventories,
candidate JAR hashes, controller intervals, complete wire/force traces, per-case
receipts and failures are always retained by CI. The inherited bounded history and
chosen-prefix oracles both run; stale/partial/reordered results and missing evidence
must still fail their negative checks.

## Scope and remaining Phase 4 work

This batch extends E03/E05/E09/E10 with public process evidence. It preserves the
existing bounded model, storage inspector and internal runtime coverage without
relabeling them as public execution. Remaining public scenarios include imported
genesis failover, missing/copied authority, cancellation/close schedules, cursor
continuity across rebuild, and the remaining partition/selection/exhaustion/mixed-mode
mapping in E01–E12. Those cases and protected acceptance remain separate work.

The production changes are package-private observation points and the capture-time
cancellation/deadline recheck; the rest is test/evidence tooling. Public
API descriptors, authority formats, configured 1.1 behavior, versions, dependencies
and paid-cloud settings are unchanged.

## Local validation

Base `6d3fbb7ae149222903eba4ccbce0cab5cafb1cf4` plus this batch, 2026-09-20:

- Targeted reactor package passed 16 tests: 12 public-runtime regressions, including
  the new expired-capture callback test, and four internal-runtime regressions.
  This is a targeted package/test result, not a full-reactor claim.
- Final fault matrix:
  `target/v51-public-faults/run.JGuWO6/evidence/receipt.json` — all 19 cases and
  250 controller-recorded client calls passed both independent oracles. Every case
  retained four voter process instances. Exact mutation-stage audits, crossing-promise
  negatives and the allowed delayed-capture-observation fixture passed.
- Existing qualification:
  `target/v51-public-qualification/run.URdRUq/evidence/receipt.json` — all six
  read/response crashes, their independent negative checks and the separate
  published V4.4 rich-query/backup comparison passed on the final JARs.
- Foundation:
  `target/v51-foundation/run.fOZC9B/evidence/receipt.json` — all 64 Python tests,
  external consumers, API checks and published V5.0 compatibility passed.
- CI YAML/retention entry, shell/Python syntax, V5 documentation contract,
  changed Markdown links/anchors/fences and whitespace checks passed.

Final replication JAR SHA-256:
`0f3426cf8bcde213b5b75c12c4aa369fb9826ee68749d04fa04cb07238c40064`.
Exploratory receipts retain their original source/JAR identities; only the final
receipts above qualify this implementation. The initial driver incorrectly waited
for an isolated node's cached role hint to change without issuing a read. The final
case instead verifies the actual fresh-barrier rejection, as the contract requires.

Receipts retain the source inventory at execution time. This summary is written
after execution; protected acceptance awaits the user's merge and exact-master CI.
