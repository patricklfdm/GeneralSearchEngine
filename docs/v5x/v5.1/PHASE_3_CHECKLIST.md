# V5.1 Phase 3 checklist

**Status:** Phase 3 accepted through PR #191 at master
`263c488fa3d1b0f78ff8a4a4454d7b3b7ff0bfab`;
[exact-master CI 35542143840](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35542143840)
passed all six jobs, including the actual foundation/storage/protocol/runtime/rejoin gates and final soak.

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
- [x] Protected Batch B: PR #189, master `bc78f6587fee2c3c80ce3198230cfcfb13316f9f`, CI `35527143425`; all six jobs and the actual runtime gate passed; kind 24 accepted.
- [x] User entered `feat/v5.1-phase3-rejoin` and authorized Batch C.
- [x] Retained-disk third-voter rejoin/source-floor integration and transfer-lifetime pressure tests; see [Phase 3C](PHASE_3_REJOIN.md).
- [x] Batch C local runtime/lease/wire regressions, independent three-JVM evidence and five rejoin negatives.
- [x] Full reactor, 46 Python tests, foundation/protocol gates and all 108 ledger/recovery process cuts; initial local barrier failure retained alongside the passing retry.
- [x] Diagnose PR #190 master CI `35533377860`: active cuts 6/7/4 and full generation slots formed a recovery-floor cycle; add bounded exact-cut witness exchange and deterministic regression coverage.
- [x] Protected Batch C: [PR #191](https://github.com/patricklfdm/GeneralSearchEngine/pull/191), master and CI above; kinds 25–27 accepted.
- [x] Concurrent real-voter JVM/network/crash evidence and complete Phase 3 acceptance.

Next: [Phase 4 public lifecycle](PHASE_4_ENTRY_PLAN.md).
