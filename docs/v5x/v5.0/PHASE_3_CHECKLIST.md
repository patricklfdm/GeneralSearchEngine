# V5.0 Phase 3 leader-path checklist

- **Status:** Locally validated candidate; protected-master acceptance pending
- **Public engine/bootstrap:** reserved pending recovery admission
- **Paid cloud:** disabled

## Entry and implementation

- [x] Phase 2 protected PR #147 merged at `1895598412b82da9de57655027d0ae76f75e327c`.
- [x] Exact-master CI `34934537274` passed, including the Phase 2 storage gate.
- [x] Canonical NIO wire codec matches all frozen Phase 1 envelope bytes.
- [x] Private bind admission, correlated responses, bounded FIFO peer queues and deadlines implemented.
- [x] Higher epoch/incarnation activation requires matching committed history and durable promise quorum.
- [x] Leadership establishment commits a NO_OP through entry and proof quorum.
- [x] Local force precedes remote quorum counting; socket writes never count as ACKs.
- [x] Entry quorum and proof quorum are distinct; only proof quorum enables leader publication/success.
- [x] Atomic bulk, updates/removals and built-in index lifecycle use the replicated order.
- [x] Private preparation cannot become visible through current or retired readers.
- [x] ApplicationSequence is distinct from LogIndex and unchanged by control entries.
- [x] One READY follower is sufficient; two unavailable followers cannot produce new successful writes.
- [x] Followers reject public application reads/mutations and leader activation.
- [x] Cancellation does not retract admitted history or release its resource slot prematurely.
- [x] Close resolves pending futures and releases transport/store ownership; callback close is tested.
- [x] Matching committed restart advances epoch and retains application state.
- [x] Uncommitted/divergent/missing histories require Phase 4 recovery and do not auto-truncate.
- [x] No core/processor behavior, public API inventory or replicated storage bytes changed.

## Evidence

- [x] 8 separate-JVM cases use three concurrent TCP voters per topology.
- [x] 7 real leader SIGKILL barriers retain exact PID/event/control evidence.
- [x] Independent inspection retains hashes and raw pre-reopen storage for all three voters.
- [x] Independent model compares parsed entry/proof histories and observed application progress.
- [x] Oracle negative cases reject missing proof quorum, wrong sequence and conflicting histories.
- [x] Required CI reactor job invokes the Phase 3 gate and uploads failed-case evidence with always().

## Exit

- [x] Final reactor, V5 Python suite and Phase 1/2/3 gates pass.
- [x] Consumers, published API comparison and nine-JAR artifact integrity pass.
- [x] Two clean release builds match byte-for-byte.
- [ ] Protected Phase 3 PR accepts the candidate.
- [ ] Exact-master CI passes before Phase 4 begins.
