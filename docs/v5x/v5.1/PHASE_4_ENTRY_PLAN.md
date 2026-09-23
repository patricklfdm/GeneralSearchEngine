# V5.1 Phase 4: public automatic lifecycle

**Status:** Batch A accepted through PR #192 at
`fce35d955e0b6b973014959e23fc38eb95dd2745` (exact-master CI `35547603482`).
[Batch B public runtime](PHASE_4_PUBLIC_RUNTIME.md) is accepted through PR #193 at
`6ca9418ae14bb3434e3ee2aa8dcc6ba2cd7e45b6` (exact-master CI `35554352587`).
[Batch C qualification](PHASE_4_PUBLIC_QUALIFICATION.md) is accepted through PR #194
at `6d3fbb7ae149222903eba4ccbce0cab5cafb1cf4` (exact-master CI `35560692475`).
[Batch D faults](PHASE_4_PUBLIC_FAULTS.md) is accepted through PR #195 at
`da9f3e9fe957e61c0fe45cf041431a5c4c74cd79` (exact-master CI `35570118695`).
[Batch E](PHASE_4_PUBLIC_RECOVERY.md) is accepted through PR #196 at
`15eb04054f28ecb52b896eedb79775c257736e00` (exact-master CI `35579584390`).
[Batch F](PHASE_4_PUBLIC_PROTOCOL.md) is accepted through PR #197 at
`764cbf4a41bd6afc79e39cb3f97e612a3d66d39d` (exact-master CI `35591386329`).
[Batch G](PHASE_4_PUBLIC_RECLAMATION.md) is accepted through PR #198 at
`4833bddf08b95a9cd28d63ee0b1c78e2e3de16dc` (exact-master CI `35664882661`).
[Batch H](PHASE_4_PUBLIC_BOUNDS.md) is accepted through PR #199 at
`fdf9482781e04727e20326fa0e32bcd281242f04` (exact-master CI `35688926607`).
[Batch I](PHASE_4_PUBLIC_PROMISES.md) is accepted through PR #200 at
`6a781ac33945016645961ec1c6564d8975cd82fd` (exact-master CI `35693468905`).
[Batch J](PHASE_4_PUBLIC_CANDIDATES.md) is accepted through PR #201 at
`04106a0c2e88010c2c14c43ad485bc3113ed1d05` (exact-master CI `35698045261`).
[Batch K](PHASE_4_PUBLIC_PRESSURE.md) is accepted through PR #202 at
`3bb84b250800c7871745450491e56b6821195d1d` (exact-master CI `35705020751`).
[Batches L](PHASE_4_RESOURCE_LIMITS.md) and [M](PHASE_4_BACKPRESSURE.md) are
accepted through PR #205, exact-master CI `35753082195`.
[Batch N](PHASE_4_PUBLIC_SELECTION.md) is accepted through PR #206, exact-master
CI `35779031221`. [Batch O](PHASE_4_LIFECYCLE_HARDENING.md) is accepted through
PR #207, exact-master CI `35794875603`. [Batch P](PHASE_4_FINAL_COVERAGE.md) adds final coverage;
complete Phase 4 acceptance remains pending. Phase 3 is [accepted](PHASE_3_CHECKLIST.md) at
`263c488fa3d1b0f78ff8a4a4454d7b3b7ff0bfab` (PR #191, CI `35542143840`).
The [checklist](PHASE_4_CHECKLIST.md) separates local qualification from protected acceptance.

The [accepted API contract](API_FORMAT_AND_COMPATIBILITY.md) and
[evidence matrix](TESTING_AND_EVIDENCE.md) govern this phase. The user performs
commit, push and PR. Cloud experiments remain manually triggered by the user.

## Batch A — offline admission

- Enable all six existing `AutomaticReplicationStorageOperations` methods: plan,
  apply, resume, read result, plan cleanup, apply cleanup.
- Import EMPTY and verified V4.4-compatible backups, preserving source bytes,
  sequence, active indexes and document order in a fresh automatic history.
- Force three preparations before one global decision and publish self-contained
  local seals. Keep cleanup limited to exact pre-COMMITTING output.
- Bind complete local materialization settings and parent filesystem identities;
  see the [additive format decision and implementation](PHASE_4_BOOTSTRAP.md).
- Validate through Java regressions, an external consumer compiled against the
  packaged JARs, published V4.4 imports, real halt/SIGKILL and an independent oracle.

## Batch B — runtime façade and reads

Enable the frozen automatic builder only after its admission validates local seal,
application/configuration and ownership without a live bootstrap coordinator.
Implement the complete inherited application and lifecycle façade, status/fencing,
callback ownership and close/cancellation. Each successful strong read requires
a fresh chosen/published NO_OP and one pinned application view, including page,
ranking, highlight and explain variants. Handle all retry outcomes explicitly.

Replace compile-only public-runtime coverage with a real external consumer doing
bootstrap, concurrent start, election, application operations, reads, checkpoint,
backup and close; the controller may not initialize voters or privately activate a leader.
Then run the full Phase 4 evidence matrix and obtain protected acceptance.

Batch A acceptance covers offline admission. Batch B implements the runtime façade
and its first public process gate; the remaining complete public history/crash
matrix is explicitly tracked in the [runtime record](PHASE_4_PUBLIC_RUNTIME.md#remaining-phase-4-qualification).

## Batch C — independent public qualification

Run bounded concurrent atomic bulk/read histories across real public JVM failover,
with an independent client-interval linearizability search and a separately decoded
chosen-prefix/captured-view oracle. Interrupt read capture, view release and client
response delivery with both halt and SIGKILL; preserve bytes before retained restart.
Compare rich query, ranking, paging, highlight, explain, index lifecycle and backup
semantics against a separately compiled and executed published V4.4 control.
Track the remaining E01–E12 public scenarios explicitly rather than inferring full
acceptance from the internal protocol matrix.

## Batch D — public fencing and mutation interruption

Isolate the current public leader while the surviving majority activates and
acknowledges a tagged write. Verify that subsequent old-leader calls cannot succeed.
Hold a read before/after capture, deliver naturally generated higher-ballot traffic,
and independently establish whether its callback was rejected or completed on the
already captured view. Exercise public writes at ACCEPT, PROOF and publication
boundaries with halt/SIGKILL, then inspect retained bytes and recover through public
start/election. No controller activation or authority repair is permitted.

## Batch E — public recovery and lifecycle

Import a separately produced published V4.4 backup and preserve its sequence,
indexes and ordered documents through public JVM interruption/election/restart.
Reject missing/copied authority through new public processes while preserving the
rejected bytes. Exercise cancellation before dispatch and after force, plus close
with a pinned read and retained directory ownership. Compare cursor continuation
across NO_OP versus mutation/reconstruction with the published V4.4 behavior.

## Batch F — public protocol and recovery faults

Allow all three isolated voters to campaign, then heal; exercise asymmetric
request and response loss with the reverse direction still active. Interrupt a
locally accepted minority tail and recover both with and without its voter in the
next quorum. Bind retention/discard to independently decoded frozen selections and
distinguish immutable entry origin from higher acceptance ballots. Interrupt basis
chunk transfer, durable snapshot progress and snapshot selector publication with
halt/SIGKILL; retain exact pre-reopen bytes and recover through public startup.
Keep two-source floor/deletion interruptions, selection ambiguity, exhaustion and
mixed-mode rejection in the remaining full public mapping.

## Batch G — public two-source reclamation

Block recovery-source exchanges while a public quorum continues serving, and
verify that no floor or physical retirement is established. Heal, establish two
complete agreeing sources, then interrupt floor write/force/publication and old
generation file/directory/root-journal retirement with halt and SIGKILL. Preserve
exact bytes before public restart, retain root promises and all acknowledged data,
and require the recovered voter to participate in a later majority and advance
its own floor through a new source download. Compare actual deleted bytes with
the durable floor and retained retirement inventory independently.

The matrix also requires selection to defer under generation-slot pressure and
an interrupted retirement to finish before its deleted directory can be reused.

## Batch H — public capacity and rejection

Seal tiny public admission/payload/application bounds, hold actual read and write
boundaries, and require structured rejection with no accepted mutation. Release
capacity, acknowledge fresh work and reopen a retained voter. Start one voter
without peers, reject client calls, then gain service by starting the other two.
Probe incompatible configuration and both public modes in independent JVMs, and
send incompatible wire headers/envelopes to a live public endpoint. Inspect exact
authority inventories and raw replies; a connection timeout alone is insufficient.
Preserve the remaining promise/ancestry exhaustion, full control-queue schedules
and complete E01–E12 mapping as explicit work before full Phase 4 acceptance.

## Batch I — public promise crash boundaries

Crash a public peer voter before/after promise write, after force, before the
storage return, after frozen-basis publication and before the actual PROMISE
reply. Exercise both halt and SIGKILL, archive exact authority before retained
public restart, and require that restarted voter in a later read/write majority.
Independently bind raw journal prefixes, monotonic ballots, force order and frozen
basis/image/reply identity. Keep candidate-side epoch selection, resource
exhaustion and full Phase 4 acceptance as separate remaining work.

## Batch J — public candidate interruption and fresh campaigns

Interrupt the candidate's own promise write/force/return, frozen self basis,
PREPARE dispatch and positive peer reply with halt/SIGKILL. Inspect and archive
retained authority before public restart. Require a fresh self campaign above
all retained epochs with an unused incarnation, then acknowledged reads/writes while the
original leader stays absent. Independently check dispatch/peer-force/reply order,
exact journal prefix retention and controller-clock recovery intervals. Pre-force
bytes and unwritten volatile ballots must not be described as durable promises.

## Batch K — public transport pressure and delayed force

Hold both outbound reservations toward a non-quorum peer and all eight inbound
connections at that peer. Prove actual rejection while all reservations are held,
continued public quorum service, exact release accounting and retained restart.
Pause ACCEPT/PROOF before force at the actual selected quorum peer, and ACCEPT on
the leader. Preserve conservative uncertain outcomes across the request deadline,
resolve them with fresh public reads without replay, and test bounded client
admission while the leader is paused. Inspect raw reservations/frames/force bytes
independently; do not infer full runtime mailbox or storage exhaustion coverage.

## Batch L — resource exhaustion and evidence reconciliation

Reach the real 10,000-promise limit through forced store operations and verify
exact retries/reopen without append/reset. Check retained bytes, full-image transfer
reservation, entry/ancestry counts and ranked-epoch overflow in separate internal
JVM fixtures. Keep their evidence identity separate from public execution.

Seal a small staging or retained-byte budget on one public voter, retain a healthy
two-voter quorum, and fill the bounded voter through normal public work/recovery.
Observe the actual capacity check, conservative local rejection, continued quorum
reads/writes and retained restarts without enlarging limits or repairing authority.
Consolidate [E01–E12 status](PHASE_4_EVIDENCE_STATUS.md), preserving explicit gaps.

## Batch M: runtime backpressure and callbacks

[Batch M](PHASE_4_BACKPRESSURE.md) follows accepted Batch L (PR #203, exact-master
CI `35712922357`). Qualify public queued deadlines, callback reentrancy and
completion-permit ownership; retain separate internal evidence for fixed mailbox
boundaries. Preserve conservative outcomes, raw authority and retained restart.
Use the [current evidence map](PHASE_4_EVIDENCE_STATUS.md) for remaining work.

## Batch N — public selection and recovery fencing

[Batch N](PHASE_4_PUBLIC_SELECTION.md) follows accepted Batch M and its transport
completion correction. Qualify exact duplicate-PREPARE replies, delayed ACCEPT/PROOF
across higher promises, hidden proof, a lagging candidate adopting a higher proven
prefix, and epoch change during partial basis download. Bind all outcomes to actual
raw wire/force/basis evidence and public service. Map existing conflict-selection
fixtures at their internal layer; retain the remaining E01–E12 acceptance review.

## Batch O — pinned recovery and bounded failure cleanup

[Batch O](PHASE_4_LIFECYCLE_HARDENING.md) follows accepted Batch N. Hold an old
query while a newer recovery snapshot arrives and reconstruction queues behind it;
require the old view to finish before application replacement. Inject real partial
ACCEPT/PROOF channel writes and require quarantine, unchanged rejected restarts and
remaining-majority service. Repeat public queued deadlines and real transport
timeouts with independent reservation/counter evidence. Preserve the difference
between finite public schedules and an unbounded resource proof.

## Batch P — final coverage reconciliation

Add real delayed HEARTBEAT request/ACK schedules across a higher durable promise,
one/two unavailable authority directories, rejected same-group startup and a
verified-backup transition to a new GroupId. Compare the backup with published
V4.4, preserve separate old/new chosen histories and archive bytes, and retain
meaningful causal negatives. Complete the E01–E12, runtime-method and bidirectional
format compatibility maps in [the final coverage record](PHASE_4_FINAL_COVERAGE.md).
Protected full CI and a separate Phase 4 acceptance record remain required.
