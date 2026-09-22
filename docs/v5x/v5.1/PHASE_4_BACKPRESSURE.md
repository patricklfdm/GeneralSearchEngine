# V5.1 Phase 4M: runtime backpressure and callback ownership

**Status:** local qualification passed; protected Batch M and complete
Phase 4 acceptance remain open. [Batch L](PHASE_4_RESOURCE_LIMITS.md) is accepted
through PR #203 at master `a5595f8efad34ec96a3f6e883e5c9c9491004279`, exact-master
CI `35712922357`; all eleven full-CI lanes and Required passed.

## Evidence boundaries

`scripts/verify-v51-phase4-backpressure.sh --skip-build` owns two internal mailbox
fixtures and four public runtime scenarios. Their receipts have separate execution
identities and source inventories. No production source, API, numeric constant,
format, dependency or version changes in this batch.

The internal runtime's 32-slot input and 16-slot completion queues are not the
public facade's configured admission limit or the transport's inbound/outbound
reservations. A public operation can be rejected by an earlier bound before it
could fill a deeper queue. This batch does not claim that the public workloads
naturally saturate both internal mailboxes, nor that finite executor/pipeline
counts prove a bound under every stalled-control/repeated-timeout schedule.

## Internal mailbox fixtures

`V51MailboxWorker` opens one real runtime over an explicitly internal sealed fixture.
It uses reflection to invoke the actual private `enqueue`/`complete` methods and
read occupancy. It never replaces the queues, changes their capacity, supplies a
ballot or invokes application mutation. A bounded latch task parks the control
thread while uniquely numbered no-op tasks fill the selected mailbox.

| Case | Required result |
| --- | --- |
| `inputs` | Observe empty capacity 32, enqueue 32 tasks, reject task 33 as `CAPACITY_EXCEEDED / NOT_SUBMITTED`, drain every admitted task exactly once in order, and accept new work after release. The overflow alone must not fail/close the runtime. |
| `completions` | Observe empty capacity 16, admit 16 completions, overflow completion 17 and mark runtime failure/closing with `CAPACITY_EXCEEDED / INDETERMINATE`. Further input is `CLOSED / NOT_SUBMITTED`. Release and drain the original 16 tasks; the refused task must not execute. |

The controller archives the closed authority directory and reopens it in a separate
JVM. An independent byte inspector checks the archive, unchanged inventories and
zero manufactured application progress. Counterexamples change capacities, lose or
execute extra tasks, misclassify failures or relabel internal evidence as public.
These are boundary witnesses, not public reachability or overflow recovery claims.

## Public scenarios

`PublicBackpressureConsumer` compiles against only the packaged core/replication
JARs. All three voters use public EMPTY bootstrap and public startup; the controller
never supplies an election result, modifies authority or accesses internal queues.
Bootstrap seals four public pending operations, the existing 9600-ms operation
budget and 4096-byte chunks. Node 3 retains the existing long-election fixture
policy while continuing normal voting/recovery. The other policies are unchanged.

| Case | Schedule and acceptance |
| --- | --- |
| `queued-deadline` | Hold an already captured query callback. Queue three uniquely tagged bulks with observable poison arguments; a fourth bulk must be rejected for capacity. All three queued bulks expire as `DEADLINE_EXCEEDED / NOT_SUBMITTED` without evaluating arguments or writing any local ACCEPT. Release the active cooperative query only after those deadlines; its original complete view still succeeds. |
| `query-reentrancy` | Inside a real query callback, attempt same-handle mutation, read, start, checkpoint, backup and close. Each must report `REENTRANT_CALL`, with `NOT_SUBMITTED` for mutation and `NOT_APPLICABLE` otherwise. Status/schema/durability diagnostics remain callable, and the outer read completes without a nested append. |
| `completion-chain` | A successful mutation's completion handler synchronously invokes a second mutation and strong read on the same handle. Both complete before the handler returns. A publication pause ensures registration precedes completion; trace thread identity and invocation order distinguish this from calling after a future was already completed. |
| `completion-capacity` | Hold the callbacks of four successful mutations after their responses. All four admission permits remain occupied until the callbacks return. Extra write/read calls must fail with typed capacity outcomes. Release all callbacks and require subsequent write/read service. |

Every scenario starts with three tagged atomic bulks and a strong read, releases
caller-owned holds, obtains later write/read service, then archives and restarts
the leader from retained state and requires another strong read. The independent
client-history and force/quorum/captured-byte oracles apply to all ordinary calls.
Nested chain calls are registered by the controller before dispatch; these are
conservative invocation envelopes. Worker-local events separately prove the actual
nested invocation and completion order within the original callback.

The new oracle binds sealed bounds/deadlines, process generations, callback entry
and exit, precise failure classes, all local ACCEPT payloads for refused writes,
and retained archives. Its negative variants remove required callbacks, substitute
outcomes, shorten deadlines, change thread identity, erase later service/restart or
alter retained bytes. Existing history/physical negatives remain enabled.

## CI and remaining work

The gate and always-retained `v51-backpressure-${{ github.sha }}` artifact run in
`v51-public-lifecycle`. All eleven required lanes, existing gates/uploads,
documentation-only routing and cloud behavior remain unchanged.

[The current evidence map](PHASE_4_EVIDENCE_STATUS.md) retains the remaining
selection/recovery and method/scenario reconciliation. Full Phase 4 acceptance,
Phase 5, cloud runs and publication are separate boundaries.

## Local validation

Base: `a5595f8efad34ec96a3f6e883e5c9c9491004279` plus this batch.

- Complete gate: `target/v51-backpressure/run.g6ar0X/internal/receipt.json` and
  `target/v51-backpressure/run.g6ar0X/public/receipt.json`; two internal fixtures and
  four public scenarios passed. The public histories contain 43 calls across
  sixteen runtime process identities. All 73 evidence-negative variants were rejected.
- Targeted reactor package passed all 16 `V51AutomaticRuntimeTest` and
  `V51PublicRuntimeTest` tests: `target/v51-backpressure/build.log`.
  This is a targeted local run; protected CI retains each lane's full reactor tests.
- Shared observer/compiler/configuration regression: existing `outbound-saturation`
  passed in `target/v51-backpressure/shared-pressure/receipt.json`.
- All 188 V5.1 Python tests, including eleven new backpressure-oracle tests, and
  25 CI/toolchain tests passed. The 36-document contract, V5.0 contract, Python
  compilation and whitespace checks passed.
- `target/v51-backpressure/static-review.json` checks YAML, 103 shell blocks,
  32 unique artifact names, unchanged existing steps/job configuration/triggers,
  the eleven required lanes, local links and the historical 87-step migration map.

Both candidate JAR SHA-256 values remain identical to accepted Batch L:

- Core: `f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.
- Replication: `a00af22cb868218816bdb4c6f2476445be2a0b90b0c42ed5b6d6772adaad6bd7`.

The first preflight correctly refused an older generated JAR timestamp after the
branch update. Repackaging regenerated the same bytes. An initial complete matrix
also passed; the final run above adds stricter response/process/restart binding and
counterexamples. Execution-time source inventories precede this final documentation
record. Protected Batch M and full Phase 4 acceptance remain pending.
