# V5.1 Phase 3A automatic transition kernel

**Status:** accepted through [PR #188](https://github.com/patricklfdm/GeneralSearchEngine/pull/188),
master `cf13a87e84a25ed1470f8e6de307e53b0d67424c`;
[CI 35507802486](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35507802486)
passed all six jobs and executed the protocol gate. Subsequent transport/application
work is recorded in [the runtime batch](PHASE_3_RUNTIME.md).
**Boundary:** this record covers internal protocol transitions over real durable
authority. Actual wire/application execution is recorded separately in the
[runtime batch](PHASE_3_RUNTIME.md); remaining admission is tracked in the
[phase entry](PHASE_3_ENTRY_PLAN.md).

## Execution and authority

`AutomaticProtocol` serializes transitions under a local monitor. It emits immutable
`Send`, `Reconstruct`, `Publish` and `Completed` actions for a driver to execute
outside that monitor. There are no sockets, blocking network futures, Query/codec
callbacks or future-completion callbacks on the control path. `tick` consumes elapsed
monotonic milliseconds; the future driver supplies the actual clock and scheduling.

The policy is read from the admitted local seal. An election derives the next ranked
epoch above the greatest observed/durable epoch and obtains a fresh nonzero incarnation.
The local frozen basis is forced before outbound PREPARE. The first complete remote
basis freezes the quorum; later responses cannot change it. Both voters verify the
same selected pair and persist its binding. The receiving voter checks its supplied
basis against its own frozen descriptor.

A local proven prefix already equal to the selection is retained directly. Only a
longer prefix needs a generation installation. Exact selection retries after later
commits re-force the original binding and cannot roll back those commits. This avoids
spending generation slots on equal-prefix elections or lost installation replies.
Physical reclamation still requires the existing two-source floor; this batch adds
no deletion permission. Repeated imports which exhaust the retained slots fail closed
until the next batch integrates genuine source exchange and reclamation.

The single consensus operation accepts locally, verifies the remote ACCEPT receipt,
constructs and forces the exact two-voter proof, then verifies that same remote
voter's PROOF receipt. A selected older value keeps its immutable origin. Its
publication is followed by a separate current-campaign NO_OP. Only completion of
that fresh NO_OP's local publication can enter `LEADER_READY`.

Reconstruction receives a bounded immutable snapshot plus only proven entries.
It produces the canonical image off the control path; publication completion is a
separate event. Neither issuing the action nor storing a local proof is a successful
publication. Higher PREPARE, expired deadlines, cancellation and late callbacks
cannot restore an abandoned campaign's readiness or client success.

## Bounds and failure behavior

- One campaign, one unresolved consensus operation and one reconstruction/publication
  action of each kind. Normal submissions are rejected while a prior operation is pending.
- At most two outstanding exchanges per peer and 32 queued actions; callers must drain
  actions before supplying more input. Typed requests retain their original identity
  and deadline across the configured finite number of retransmissions.
- Heartbeats have fresh monotonically increasing sequences. Activated idle-leader
  traffic resets suspicion; before activation only advancing recovery progress does.
  Replayed or unchanged recovery traffic cannot indefinitely defer elections.
- The reconstructed input is capped at 64 MiB and the two frozen images count against
  the sealed staging budget. Whole assembled records are internal transfer results,
  not permission to put complete images in a wire message.
- Pre-admission rejection is `NOT_SUBMITTED`. Once local acceptance may have occurred,
  retirement reports `INDETERMINATE`. Cancellation is not rollback.
- Failed application reconstruction or ambiguous storage I/O prevents readiness.
  Close retains the store lock until outstanding application actions quiesce; a later
  close can release ownership. Restart begins as a non-ready follower.

## Evidence and limits

`V51AutomaticProtocolTest` uses three separately locked, sealed real stores and a
deterministic action driver. It covers normal activation/write ordering, missing
entry/proof replies, entry-chosen recovery, hidden proof, higher-ballot fencing,
retained restart, repeated equal-prefix elections, heartbeat replay, no quorum,
forged receipts, cancellation, callback failure, deadline, force and close cuts.

`scripts/verify-v51-phase3-protocol.sh --skip-build` starts fresh JVMs for healthy,
entry-chosen, hidden-proof, fenced, retry and restart scenarios. It retains the
actual authority directories, force frames, typed exchanges, callback publications,
source/JAR identities and Java test report binding. The independent Python oracle
checks force-before-receipt, two distinct voters, received proof ACK before publication,
unchanged carried values, fresh activation, acknowledged payloads and final authority.
Rechecksummed forged images and other causal/evidence mutations are rejected.

The application port in these scenarios is deliberately synthetic: it appends
opaque mutation payloads to the genesis image, while NO_OP leaves it unchanged.
This is a deterministic projection oracle, not V4 search/index/codec integration.
Each scenario runs in one JVM with three stores and simulated delivery; it is not
three networked public engines, a process-crash test, or a failover latency result.
The previously accepted Phase 2 JVM crash gates remain separate and mandatory.

CI runs this verifier after the storage/recovery gate and retains evidence even on
failure. PR #188 and its exact-master CI accepted this batch. Full Phase 3 closure
still requires the remaining obligations in the phase entry.

## Local validation (2026-09-20)

- Full reactor `package`: core 549 tests (four existing skips), replication 244,
  processor five; no failures. This run included the first 20 protocol regressions.
- After adding the shared campaign-deadline regression, targeted reactor `package`:
  all 21 protocol tests passed against the final production implementation.
- Protocol gate: six fresh-JVM scenarios passed independent retained-authority and
  causal checks; seven corrupted-evidence variants were rejected. Evidence receipt:
  `target/v51-protocol/run.t8y05t/evidence/receipt.json`.
- Phase 1 foundation: 41 Python tests and independent foundation gate passed;
  evidence: `target/v51-foundation/run.IKqPVQ/evidence`.
- Phase 2 ledger harness: all 36 process cuts passed at
  `target/v51-storage/run.NgEFSc/evidence/receipt.json`.
- The first recovery run reached its 20-second barrier wait limit during
  `halt-floor_write_chunk`, with no Java exception. Its partial directory and failure
  receipt remain at `target/v51-storage/run.NgEFSc/recovery`. A focused halt/SIGKILL
  retry passed in eight seconds, followed by all 72 recovery cuts passing at
  `target/v51-storage/recovery-retry.72id7jrb/recovery/receipt.json`. The full Phase 2
  script initially failed; the complete recovery harness was rerun separately.
  No timeout, cut or production recovery rule was relaxed.
- Final documentation contract: 17 documents/110 local links passed; shell syntax
  and `git diff --check` passed.

These local runs identify the worktree based on `eb2b8c0b51d9d3352b037d6435e3aad2839d788d`;
the protocol receipt binds its tested source inventory, JARs and Java test report.
It is not an accepted-master receipt. No cloud execution was performed.
