# V5.1 Phase 3 entry: automatic protocol and runtime

**Status:** Batches A/B accepted; the user entered `feat/v5.1-phase3-rejoin` and
authorized Batch C. Local qualification passed; Phase 3 awaits protected acceptance.
**Accepted base:** [PR #189](https://github.com/patricklfdm/GeneralSearchEngine/pull/189),
`bc78f6587fee2c3c80ce3198230cfcfb13316f9f`,
[exact-master CI 35527143425](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35527143425).
All six jobs passed, including the actual foundation, storage/recovery, protocol and runtime gates.

The [contract](PHASE_0_CONTRACT.md), [protocol](LEADERSHIP_AND_RECOVERY.md),
[frozen format catalog](PHASE_1_FORMAT_CATALOG.md) and [evidence matrix](TESTING_AND_EVIDENCE.md)
govern this phase. Public automatic factories/bootstrap remain guarded until Phase 4.
The user performs commit, push and PR; no paid execution or release is part of this work.

## A — transition kernel, election and activation (accepted)

- A package-private state machine backed by the real sealed `AutomaticStore`.
  Elapsed monotonic ticks and independently chosen bounded delays schedule campaigns;
  ranked overflow-checked epochs and fresh incarnations never revive a prior leader.
- Force the local promise/basis before sending PREPARE. Freeze one two-voter quorum,
  independently verify its bases, persist selection, and adopt a longer proven prefix.
  Carry exact accepted ENTRY bytes before a separate fresh campaign NO_OP.
- Use the same local/remote voters for ACCEPT and PROOF. Bind exact receipts and
  discard retired responses. Emit publication only after proof quorum; readiness
  and success wait for local publication completion under the current promise.
- Emit bounded transport/reconstruction/publication/completion actions. The control
  monitor performs no network wait or user callback. Higher PREPARE revokes readiness
  while old network work is pending; reconstruction remains outside the monitor.
- Exact retries, bounded exchanges/deadlines, heartbeat replay/progress rules,
  conservative cancellation outcomes, restart and close ownership tests.
- Real-store deterministic delivery tests plus a fresh JVM per retained-evidence
  scenario. Python independently checks actual frames, forces, receipts, application
  projection and publication order; modified evidence must fail.

See [implementation and limits](PHASE_3_PROTOCOL.md) and the [checklist](PHASE_3_CHECKLIST.md).

## B — transport and application integration (accepted)

The [runtime implementation](PHASE_3_RUNTIME.md) now connects the kernel to real
TCP and V4 application staging/publication. Reviewing the frozen catalog found that
it could not represent the complete selected quorum at the receiving voter; the
[explicit additive extension](PHASE_3_WIRE_EXTENSION.md) records that gap and the
new kind 24. Original fixture bytes remain fixed. This runtime/format batch and its
independent three-JVM evidence were accepted in PR #189.

The original mapping requirements remain:

Map assembled internal actions to the reviewed 1.2 wire schema and bounded chunk
transfers. In particular, the receiver must reconstruct and verify the complete
selected basis pair before accepting `selectedDigest`; a digest-only installation
is insufficient. Review that mapping against the frozen catalog before writing an
adapter; an unrepresentable contract requires an explicit catalog decision, not an
unreviewed extra envelope field.

## C — retained-disk rejoin, source floors and remaining qualification (current)

The [implementation record](PHASE_3_REJOIN.md) covers passive proven-state transfer,
complete source exchange, two-source retirement and the explicit additive wire mapping.

Probe and reconcile the third voter, retrieve real peer recovery-source packets,
and advance two-source floors before reclaiming generation slots. Batch A's
synthetic application and assembled in-memory messages cannot satisfy these checks.

Require concurrent real-voter JVMs, socket faults and retained-disk restart evidence
against the independent model. No generic network/automatic-service acceptance is
inferred from passing transition tests. Phase 4 owns public bootstrap, façade,
strong-read pins and end-to-end public readiness/outcome obligations.

## Exit

Accept the complete Phase 3 only after all batches, exact-master CI, independent
history checks and required process/network cuts pass. Keep all configured 1.1
compatibility gates and frozen fixture bytes. Missing/corrupt authority, exhausted
capacity or ambiguous I/O must remain unavailable rather than silently repair a voter.
