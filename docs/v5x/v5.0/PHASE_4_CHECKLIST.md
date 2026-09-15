# V5.0 Phase 4 recovery checklist

- **Status:** Accepted through protected PR #149 and exact-master CI 34950041552
- **Public engine/bootstrap:** reserved for complete bootstrap/lifecycle admission
- **Paid cloud:** disabled

## Entry and implementation

- [x] Phase 3 protected PR #148 merged at `911c9de0bd63149e5d48e7f4d5cb0ea7042a951e`.
- [x] Exact-master CI `34940262703` passed, including its real three-JVM gate.
- [x] Higher durable promise quorum fences prior incarnations before recovery selection.
- [x] All observed valid committed prefixes survive; longest unproven log is not authority.
- [x] Conflicting proofs fail closed during activation and catch-up and stop leader writes.
- [x] Lost responses do not erase a valid local proof or imply rollback.
- [x] Incomplete final ENTRY tails require fenced installation; public inspection stays strict.
- [x] Corrupt promises/proofs and missing committed bytes reject without generic automatic repair.
- [x] Bounded incremental catch-up and immutable chunked snapshot fallback use production TCP.
- [x] Replacement followers remain non-voting until verified active-epoch installation.
- [x] Explicit replacement-leader reconstruction requires both surviving voters.
- [x] Private application rebuild preserves document/query order and index lifecycle.
- [x] Atomic generation publication keeps root promise and exclusive lock authority intact.
- [x] Recovery floor requires two complete equivalent sources and an installed local snapshot.
- [x] Exact physical cleanup is restartable after partial deletion or legacy truncation.
- [x] Missing completed-generation selectors cannot silently select legacy history.
- [x] Canonical payload, staging, transfer count, ancestry and retained-byte limits are enforced.
- [x] Existing storage fixture bytes, wire IDs and public API inventories remain unchanged.
- [x] Core/processor source and POM dependency/version surfaces remain unchanged.

## Evidence

- [x] Independent Python producer and parser cover the versioned snapshot/generation extension.
- [x] Java reads the independently produced fixture and checks its committed golden inventory.
- [x] Recovery oracle checks proof preservation, counters, admission and recovery floor sources.
- [x] Negative oracle cases reject conflicting prefixes, sequence drift, lost success and V4.4 mismatch.
- [x] Real process evidence covers 17 three-JVM scenarios and six cross-parser corruption cases.
- [x] SIGKILL cuts cover snapshot staging/publication, floor publication, cleanup, uncertain mutation and transfer.
- [x] Published V4.4 comparison pins artifact SHA-256 and verifies the loaded SearchEngine code source.
- [x] Gate retains source status, exact PIDs, raw controls/events, pre-reopen copies, inventories and comparisons.
- [x] CI invokes the Phase 4 gate and uploads failed-case evidence with always().

## Exit

- [x] Final clean reactor, Python suite and Phase 1/2/3/4 gates pass.
- [x] Consumers, published API comparison and nine-JAR artifact integrity pass.
- [x] Two clean release builds match byte-for-byte.
- [x] Protected Phase 4 PR accepts the candidate.
- [x] Exact-master CI passes before the next phase begins.

Local checks do not establish protected-master acceptance. The public admission,
performance, paid-cloud and signed-release gates remain separate.
