# V5.1 Phase 3 checklist

**Status:** Batch A accepted; Batch B runtime implemented locally; protected review pending.

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
- [x] Protected Batch A: PR #188, master `cf13a87e84a25ed1470f8e6de307e53b0d67424c`, CI `35507802486`; six jobs passed and protocol gate executed.
- [x] User entered `feat/v5.1-phase3-runtime` and authorized the runtime batch.
- [x] Original 1.2 production wire codecs and explicit selected-quorum extension with independent fixtures.
- [x] Bounded real TCP driver and V4 application staging/reconstruction/publication.
- [x] Real three-JVM execution, leader SIGKILL, retained restart and independent wire/application evidence.
- [x] [Batch B local validation](PHASE_3_RUNTIME.md): full reactor, four runtime/three wire regressions, foundation/protocol gates and final three-JVM evidence with five rejected negatives.
- [ ] Protected Batch B merge and exact-master CI; accept the explicit wire extension.
- [ ] Retained-disk third-voter rejoin/source-floor integration and transfer-lifetime pressure qualification.
- [ ] Concurrent real-voter JVM/network/crash evidence and complete Phase 3 acceptance.

Public automatic bootstrap/façade/strong-read enablement remains Phase 4.
