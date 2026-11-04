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

The additional `scripts.v53.joint_floor_maintenance_evidence` reader now composes
the original physical chain through initialization, FINAL, BARRIER and joining
recovery, comparing all 25 captured grants and 42 continuation owner snapshots.
Cold node-2 captures are bound to the explicit original reopen event; default
profile readers still require their ordinary owner lifetime. Multi-peer PREPARE
correlation accepts a contiguous sequence within a shared trace, as used by the
native round, as well as the earlier fixtures' separate traces. Response arrival
order is not assumed to equal request sequence.

The complete wire transcript (4,445 exchanges, 730 sessions) is causally paired.
Within the recovered floor, all six packet/metadata sessions and 66 request/reply
pairs are authorized against the physically derived, forced original generation
and its actual lifetime, including the temporary joining endpoint. The reader
derives both peer-ledger writes, the borrowed image, nine-member inactive
generation retirement, exact preserved source/journal and final floor release.
All 101 retirement/release callbacks and their ordering relative to durable floor
authority are checked. Fourteen targeted evidence mutations must reject for their
specified layer and reason after the unmodified original passes. Other physical
inputs are protected from each mutation.

That focused reader qualifies the recovered floor's exports and maintenance,
not all other floor transactions in the history. Transient generation-retirement-file bytes were not captured
at every callback; the reader checks their derived event sequence and exact final
state, without claiming those unobserved prefixes. Process death, remaining
partial-body/native interruption axes and final-source cohort execution remain
open. The eleven optional
hosted subsets and 512 planned histories are unchanged. See the additional
[maintenance replay receipt](phase3-evidence/joint-floor-maintenance.json) for the
original producer identity, current reader and retained development diagnostics.

### Complete interrupted-history composition

`scripts.v53.joint_history_evidence` additionally replays the unchanged native
original through every network, export, control and floor-maintenance lifetime.
The cold-owner boundary is explicit and checked against the original CURRENT
force sequence. All 4,445 completed exchanges, 730 transfer sessions, 33 owned
slot transactions and 5,100 slot-storage callbacks remain bound to original
bytes and durable ACK ordering. All 727 non-rejected content sessions are
accounted for by export or control authority. Ordinary readers keep their strict
default owner scopes.

Floor replay checks 52 network reservations and three direct reservations,
169 complete copy instances, 105 remote discovery/copy bindings and all 5,951
mutating floor callbacks. The two reservations for the interrupted floor are
one continuous recovery: the original writer prefix and the reacquired copies
must match exactly, both reservations' callbacks are consumed, and only the
recorded resumed reservation may overlap an active floor. Each of the 2,949
generation/source retirement callbacks must be protected by an active floor.
Forty-eight generation retirement sequences are checked. STATUS remains a hint;
complete original copies establish the governing majorities.

The same physical derivation now compares 21 source-retirement transactions and
all 315 captured intermediate source-retirement snapshots, including their
exact floor authority, journal and preserved/deleted members. Pre-grant
maintenance uses the independently derived first sufficient voter set; later
initialization uses its actual four-owner cohort. Captures do not select their
own expected floor. These recorded **source** retirement prefixes are distinct
from the still-unobserved transient **generation** retirement files above.

Whole-original acceptance precedes eleven targeted negative mutations. Each
mutation must change only its declared inputs and fail in its designated layer
for the exact reason; an earlier unrelated rejection cannot count as success.
The [whole-history receipt](phase3-evidence/joint-history.json) binds original
producer/build/raw evidence, the current Python reader, relocated optimized
replay and retained failed development probes. This extends evidence replay;
it does not rerun Java or change the native workload, runtime or limits.

Continuous whole-history peer/learner/future ledger composition, native
partial-body/process-death axes, other Phase 3 obligations and final-source
qualification remain open. Phase 3 is not closed by this one retained original.

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
python3 -B -m scripts.v53.joint_floor_maintenance_evidence \
  general-search-engine-replication/target/v53-native-dispatch/run-<original-id> --qualify
python3 -B -m scripts.v53.joint_history_evidence \
  general-search-engine-replication/target/v53-native-dispatch/run-<original-id> --qualify
```

The JUnit entry is opt-in and adds no normal-CI duration. Do not combine an old
producer with new runtime code and call that final-source qualification.
