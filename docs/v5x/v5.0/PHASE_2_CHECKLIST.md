# V5.0 Phase 2 replicated storage checklist

- **Status:** Local validation complete; protected-master acceptance pending
- **Production boundary:** Local storage and inspection only
- **Group runtime / paid cloud:** disabled

## Entry

- [x] Phase 1 accepted through protected PR #146.
- [x] Starting master is `2e78bddd37fff6638c621da4e4f7f27c3f85a8aa`.
- [x] Exact-master CI `34930568130` passed before Phase 2 began.
- [x] Work follows [the Phase 2 entry plan](PHASE_2_ENTRY_PLAN.md).

## Local storage authority

- [x] Exact `gse-replicated (1,0)` envelope, record fields and directory inventory documented.
- [x] Manifest binds immutable group, configuration, leader, voters, endpoints and application identities.
- [x] Local identity, journal headers and initialization marker bind the exact manifest.
- [x] Writer ownership is exclusive; Java/Python inspection rejects another live process owner.
- [x] Initialization requires an absent target, forces files/directories and retains partial failures.
- [x] Epoch/incarnation promises are monotonic, durable and fence stale writes after reopen.
- [x] Append requires the configured leader, current promise and exact contiguous predecessor chain.
- [x] Exact append/promise/proof retries force before ACK and do not grow journals.
- [x] Conflicting retries and same-epoch different-incarnation requests reject without writes.
- [x] Proof requires local entry bytes and exact receipts from distinct manifest voters.
- [x] Proof persistence commits the local prefix; it cannot apply, publish or complete an application Future.
- [x] All writes/forces complete before ACK; I/O failure poisons subsequent writes until reopen.
- [x] Frame, retained-byte, record-count and no-progress bounds prevent unbounded admission.
- [x] Unknown versions, reserved operations, corrupt/torn data and unsafe inventory fail closed.
- [x] Reopen and inspection never truncate or repair authority.
- [x] V4 production code and V5 public declaration inventory remain unchanged.

## Independent and crash validation

- [x] Independent Python-generated golden files open in Java and have pinned whole-file hashes.
- [x] Java-generated files parse independently and exactly match Python bytes.
- [x] Independent inspector never imports Java/model implementation and requires no application codec.
- [x] 19 real separate-JVM SIGKILL cases cover initialization and promise/entry/proof write/force/ACK boundaries.
- [x] Exact PID/barrier/exit evidence and raw pre-reopen bytes are retained.
- [x] Complete unacknowledged records can survive; partial records reject without byte changes.
- [x] 9 malformed directories reject in both readers, including recomputed-checksum semantic corruption.
- [x] JVM tests cover short writes, injected I/O failures, ownership, capacity, fencing and retry behavior.
- [x] Phase 2 CI gate and `always()` evidence upload are wired into Required's reactor dependency.

## Exit

- [x] Full final reactor, Phase 1 and Phase 2 local gates pass.
- [x] V1–V5 consumers, published artifact compatibility and nine-JAR release checks pass.
- [x] Two clean release builds are byte-reproducible.
- [ ] Protected Phase 2 PR accepts the candidate.
- [ ] Exact-master CI passes before Phase 3 starts.

Public bootstrap, transport/coordinator, application apply/publication, snapshot
installation, suffix repair, compaction and paid cloud are later-phase work.
