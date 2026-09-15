# V5.0 Phase 5 hardening checklist

- **Status:** Accepted through protected PR #150 and exact-master CI
- **Public runtime/bootstrap:** reserved for complete authority and lifecycle admission
- **Paid cloud:** disabled

## Entry and implementation

- [x] Phase 4 protected PR #149 merged at `a67e654eff5e5aeb1571c1497f194c9c5de9c2b0`.
- [x] Exact-master CI `34950041552` passed, including the executed Phase 4 recovery gate.
- [x] Interrupted/timed-out close can retry without releasing a still-active writer's store owner.
- [x] Close completes a current forced record before interrupting the writer; later authority writes reject.
- [x] Concurrent close and completion callbacks avoid shutdown self-waits.
- [x] Writer rejection/close releases queued admission exactly once; cancellation alone retains admission.
- [x] Full writer queues reject with classified capacity/closed outcomes.
- [x] Sender shutdown drains bounded work and acceptor failure stops the transport.
- [x] Invalid derived chunk bounds reject before staging creation.
- [x] No core/processor, public API signature, POM or storage/wire fixture change.
- [x] Bootstrap/public-lifecycle gap remains explicit and public construction stays disabled.

## Evidence

- [x] Production socket-boundary drop/hold hooks use exact request/response evidence.
- [x] Lost ACK, bounded retry, duplicate/reorder/stale/conflict and malformed-frame tests.
- [x] Slow follower, client/writer/outbound/disk pressure and snapshot-staging rejection tests.
- [x] Close interruption, timeout, callback, concurrency and checkpoint reader-lease tests.
- [x] Independent trace validation and negative evidence tests.
- [x] Final 16-case three-JVM matrix, including eight SIGKILLs, passes with complete retained evidence.
- [x] Identical deterministic replay and repeated named fault plan pass.
- [x] Independent proof/application replay and published V4.4 comparison pass for every case.
- [x] Required CI invokes Phase 5 and uploads evidence with always().

## Exit

- [x] Final clean reactor, V5 Python and Phase 1–5 gates pass.
- [x] Consumers, published API comparison, nine-JAR integrity and fixture exclusion pass.
- [x] Two clean release builds match byte-for-byte.
- [x] [Protected PR #150](https://github.com/patricklfdm/GeneralSearchEngine/pull/150) accepted the candidate at `4a8fd3dfd9e398d712e896c9af511cf55f4cb16e`.
- [x] [Exact-master CI 34956076066](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34956076066) accepted the merged source, including executed Phase 1–5 gates.

Protected acceptance does not enable the reserved public bootstrap/lifecycle flows.
Their admission precedes any end-user production/cloud claim or completed-V5 claim.
The next review is the [public-admission contract](PUBLIC_ADMISSION_CONTRACT.md).
