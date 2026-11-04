# Phase 3 interrupted original floor in a 5-REPLACE history

The [complete-original borrow](PHASE_3_PENDING_FLOOR_BORROW.md) component now has
an opt-in native history entry, `V53JointFloorRecoveryTest`. It reuses the actual
five-voter bootstrap, typed learner, old-majority INTENT and joining placement.
It does not manufacture a joint capsule or replace an original owner's directory.

At the existing seed-maintenance boundary, node-2 forces the four original copies
from node-1, node-2, node-3 and node-6. An injected I/O exception at
`FLOOR_COPIES_FORCED` stops before writing the FLOOR authority. The original
generation, proposal and all complete copy files remain retained. The fixture
closes node-2's endpoint, transport and journal, checks drained reservations, then
opens the same replica and application paths under the same permanent identity.
This is an exception/close/reopen cut; it is not a SIGKILL or power-loss experiment.

The actual joining owner temporarily serves its current prefix on its permanent
TCP endpoint before the normal joining initialization service takes that socket.
Native generation maintenance reacquires the three exact remote originals using
the complete retained bytes, re-forces the proposal/copies and writes authority
last. The original stage deadline remains unchanged. Normal maintenance then
reconciles the peer ledger and retires/releases the protected state. The existing
history proceeds through joining initialization, FINAL, the fresh stable BARRIER
and retaining cold reopen. The available old majority requires node-2.

Initial floor construction uses the existing seed fixture's original in-process
copy objects. Recovery uses real TCP and never receives those objects from the
fixture. This entry does not prove all controller overlap is reachable or a
simultaneous maximum of metadata, learner and receiving ownership.

## Independent evidence

`scripts.v53.joint_floor_recovery_evidence` checks the exact original proposal,
all four current generation inventories, the interrupted/cold-open bytes and
completed floor, observed resource charges, force order and fresh packet/generation
exchanges. It derives the original generations from the existing bootstrap-through-
INTENT physical reader and joining-placement reader, and invokes the independent
whole catalog, phased certificate and checkpoint chain through the final stable cut.
The old learner ledgers are derived from their original head-query/ACK exchanges
before the interrupted directory is compared. An explicit event-index boundary
allows node-2's cold callback lifetime; ordinary histories retain the existing
strict event shape. Neither observed ledgers nor producer labels supply expected
state.

Original evidence must pass before mutation. Missing originals or authority,
premature authority, altered close/reopen state, invented headroom, resource
overflow, missing force/delivery, changed packet bytes, altered scope, directory
lineage or deadline must be rejected for their specified reason. Relocation
does not change the original recorded directory identity.

Complete remote export-force causality and physical maintenance/retirement replay
remain separate obligations. A semantic history pass or a producer PASS does not
close these gaps or qualify Phase 3. Incomplete four-copy bodies at full capacity,
other interrupted cuts and final-source cohort execution remain open. The eleven
optional hosted subsets and 512 planned histories are unchanged.

See the [development receipt](phase3-evidence/joint-floor-recovery.json) for the
actual producer source, toolchain, executions, independently replayed results and
retained unsuccessful development attempts.

The native test completed in 1187.620 seconds (one JUnit test, no failures or
skips). Replay derives all eleven control slots, the bootstrap-through-INTENT
physical prefix, joining placement, four original floor copies and 66 fresh
request/reply exchanges. This history's observed peak is seven application images
and five SOURCE slots, not the conditional six-SOURCE plateau. Seventeen evidence
mutations must fail for their declared reasons. The initial fixture attempt was
stopped after discovering a missing parent-directory creation; its original
partial output is retained separately from the corrected execution.

## Entry points

Run the single native history in a prepared isolated checkout with Java 21:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  '-Dtest=V53JointFloorRecoveryTest#originalFourCopyFloorResumesOverTcpBeforeFinalAndStableBarrier' \
  -Dv53.joint.floor.recovery=true test
python3 -B -m scripts.v53.joint_floor_recovery_evidence \
  general-search-engine-replication/target/v53-native-dispatch/run-<original-id> --qualify
```

The JUnit entry is opt-in and adds no normal-CI duration. Do not combine an old
producer with new runtime code and call that final-source qualification.
