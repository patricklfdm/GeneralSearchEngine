# V5.1 Phase 3 checklist

**Status:** Batch A implemented and locally validated; protected acceptance pending.

- [x] Phase 2 accepted in PR #187, master `eb2b8c0b51d9d3352b037d6435e3aad2839d788d`, CI `35503107173`.
- [x] User entered `feat/v5.1-phase3-election` and authorized the next implementation batch.
- [x] Real-store transition kernel; ranked epochs, durable own prepare and frozen quorum selection.
- [x] Exact ACCEPT/PROOF receipts, carried origin preservation and separate fresh activation NO_OP.
- [x] External reconstruction/publication actions; higher PREPARE and retired-reply fencing.
- [x] Bounded retries/actions, progress heartbeat rules, deadline/cancellation and close ownership.
- [x] Deterministic transition regressions and independent causal/retained-directory oracle.
- [x] CI verifier and always-retained evidence.
- [x] [Local validation](PHASE_3_PROTOCOL.md): full reactor, final 21 protocol tests,
  six independent scenarios/seven rejected negatives, foundation, 36 ledger cuts
  and 72 recovery cuts. Initial local recovery barrier timeout retained; full retry passed.
- [ ] Protected Batch A merge and exact-master CI.
- [ ] Review and implement frozen 1.2 wire/selected-basis transfer mapping.
- [ ] Bounded real driver, V4 application staging and retained-disk rejoin/source-floor integration.
- [ ] Concurrent real-voter JVM/network/crash evidence and complete Phase 3 acceptance.

Public automatic bootstrap/façade/strong-read enablement remains Phase 4.
