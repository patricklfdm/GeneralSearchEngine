# V5.2 Phase 0 entry: explicit replica reads

**Status:** entry plan candidate, 2026-10-15. Source review and documentation only;
the complete read contract is not yet frozen or accepted.

**Reviewed checkout:** `0ada3ccbbcb9bcab3ef5ddbf25f28861e6cf7b7d`, after PR #333.
Exact-master CI `38699074927` passed all 46 jobs at accepted attempt 2; attempt 1's
automatic-healthy canonical tape and Required failures remain in the
[CI acceptance record](../../CI_TIERED_HOSTED_ACCEPTANCE.md).

**Immediate replication reference:** published `5.1.0`, source
`516fe1efb54ef0787f38209108f322f258f71696`, with the
[publication record](../v5.1/RELEASE_CHECKLIST.md). Published `4.4.0` remains the
inherited search/storage oracle. The reviewed production core/replication sources
and V5.1 consumer have no diff from the release tag at this entry; later CI and
documentation commits are not a new release or new cloud evidence.

## 1. Governing scope and intended outcome

Read the [accepted charter](../DEVELOPMENT_CHARTER.md#v52--replica-reads),
[proposed refinement](../NEXT_DEVELOPMENT_ADDENDUM.md#v52-explicit-read-policies),
[V5.1 migration limits](../v5.1/MIGRATION_GUIDE.md) and
[V5.1 read contract](../v5.1/PHASE_4_PUBLIC_RUNTIME.md) before designing additions.
Published guarantees and accepted version-specific contracts take precedence over
the proposed refinement.

Define three explicitly distinct policies: the existing strong leader read,
stale-allowed reads of locally published committed state, and a history-bound
minimum-progress read that waits for publication or rejects according to its
contract. No request may silently downgrade. A minimum-progress read is not a
promise to observe every concurrent client's latest write.

The acceptance example is a public three-JVM client: obtain a progress token tied
to confirmed committed work, address a lagging follower, observe the prescribed
wait/rejection, then observe a valid published prefix after catch-up. Partition,
leadership change, restore and restart must not turn an incompatible numeric index
or an uncommitted suffix into a successful stronger read.

This batch defines the work to produce that contract. It does not add APIs, choose
format versions, open `5.2.0-SNAPSHOT`, alter existing bounds or start workloads.
Keep the three fixed voters, existing mutation outcomes and configured-mode
semantics. Membership changes, sharding, transparent mutation retry, mixed-version
rolling upgrade and automatic paid-cloud execution remain outside this entry.

## 2. Findings from the current implementation

Paths below are relative to
`general-search-engine-replication/src/main/java/io/github/patricklfdm/generalsearch/replication/`.
Inspect their actual definitions again when implementation starts; this table
describes the reviewed checkout, not a proposed API already available to callers.

| Surface | Observed behavior | Phase 0 implication |
| --- | --- | --- |
| `AutomaticReplicatedSearchEngine.java` | Extends the durable engine with `start()` and `leadershipStatus()`; no explicit read-policy or progress-token API. | Specify additive source/binary compatibility before declaration fixtures. The interface's old Phase 1 Javadoc is historical, not evidence that runtime is disabled. |
| `PublicAutomaticEngine.java`, `strong` / `capture` | Public data reads require leader admission, submit operation 9 (`NO_OP`) as a barrier, then capture its published cut. `get`, query/ranking/paging/highlight/explain and `currentSequence` use this path. | Preserve existing no-policy strong semantics; follower reads need a separately defined admission path, not a relaxed role check. |
| `AutomaticRuntime.java`, `capture` | Rechecks closing/deadline, leader readiness, epoch and application index at capture; query work runs on the application worker outside the protocol monitor. | Specify the atomic publication/identity boundary for each new policy and every promise/install race. |
| `PublicAutomaticEngine.java`, mutation methods | Successful mutation Futures return `Void`; internal submit returns an index. | A public token needs a defined issuance operation and ordering. A later status sample is not automatically a receipt for a particular write. |
| `AutomaticReplicationStatus.java` and runtime `refresh` | Exposes local `provenIndex`, `appliedIndex` (fed from published index), application sequence and leader hints; these are diagnostic observations. | Do not treat a status record or timestamp as a transferable authority proof. Log position and application sequence are distinct. |
| `AutomaticApplication.java`, `publish` | Control-only publication can advance index while preserving application sequence and the live core cursor; changed application state replaces the materialization. | Define cursor/pin lifetime and exact snapshot identity before allowing replica switching or waiting. |
| `AutomaticBootstrap.java` | Genesis/manifest bind group and history; backup import preserves application sequence while assigning a new group history. | Restore/new-group identity must reject an old token even when sequence/index numbers coincide. |
| `PublicAutomaticEngine.java`, admission / close | Bounded permits/queues; admission/barrier/capture deadline; an already active user query completes cooperatively. | Freeze bounded waiters and cleanup separately from query execution. Do not promise forced termination of arbitrary user callbacks. |
| `AutomaticRuntime.inspectLocal` | Explicitly internal/test inspection without a public strong-read contract. | It cannot be exposed as follower-read correctness merely because it returns local data. |

The existing `ReplicatedSearchEngine` configured mode remains a distinct public
contract. [V5.1 migration](../v5.1/MIGRATION_GUIDE.md) permits automatic-mode disk
loss recovery only through a reviewed new-group transfer; V5.2 read tokens must
not accidentally introduce online voter replacement or change that boundary.

Useful existing verification entry points are `V51PublicRuntimeTest`
(`completeFacadeUsesOneEntryPerCallAndNoOpKeepsPageCursor`, concurrent reads and
active-view close), `scripts/v51/public_qualification_harness.py`,
`public_fault_harness.py`, `public_protocol_evidence.py`, `public_qualification_evidence.py`
and the external `compatibility/v51-style-consumer/`. Reuse relevant framework
boundaries; neither internal inspections nor synthetic evidence substitutes for
the new public follower-read contract.

## 3. Decisions that block Phase 1

All rows are **OPEN** in this entry. Recommendations identify the design direction;
they do not resolve exact signatures, formats or numeric limits by implication.

| ID | Required decision and completion criterion |
| --- | --- |
| D01 | Policy and operating-mode matrix: enumerate supported methods, roles and lifecycle states. Preserve existing automatic strong reads and configured legacy semantics; reject unsupported combinations explicitly. |
| D02 | Token identity/issuance: bind group and compatible history, committed position, schema/format where needed; define issuance after confirmed work, comparison, malformed/fabricated inputs, unknown versions and trust assumptions. Distinguish log index from application sequence and avoid sequence-to-index guessing. |
| D03 | Readable cut: derive committed, locally applied and published state from valid authority; define the capture/linearization point and races with concurrent writes, promise changes, rejoin and snapshot installation. Stale policy permits older committed data, never staged/unproven data. |
| D04 | Waiting and outcomes: exact wait/reject decisions for lag, deadline, unavailable state, wrong history, cancellation and close; no stale fallback on timeout. Decide synchronous/asynchronous surface and local monotonic deadline ownership. |
| D05 | Token lifetime: retained-disk restart, leadership change, compaction, snapshot install, backup import/new group and unsupported disk loss; decide expiry versus explicit non-expiry and any required metadata bound. |
| D06 | Paging and pins: query identity, snapshot lifetime, replica/process affinity, invalidation and resource release; decide which policy/cursor combinations are supported. Do not imply that minimum index proves cross-node cursor portability. |
| D07 | Resource isolation: exact finite waiter counts, queues, memory/retained bytes, pins/cursors, deadlines and fairness; prove lagging readers cannot block publication/catch-up needed to release those readers. Bound metrics/trace cardinality too. |
| D08 | Compatibility and formats: exact additive API/error declarations, wire/storage/token versions or evidence why unchanged formats suffice; old consumer behavior and homogeneous upgrade/new-group procedure. No fabricated format version or unsupported rolling-upgrade claim. |
| D09 | Independent evidence: map every success/rejection rule to decoded history and captured publication, not only local role/status. Define corruption negatives and real public consumers before implementation. |
| D10 | Phase/resource acceptance: split foundation/runtime/public/fault/measurement/release work; freeze local measurement goals before performance runs. Reuse cloud infrastructure with new source/admission evidence, not old accepted runs. |

Required counterexamples include: equal indices in different histories; a larger
accepted suffix with no commit authority; proof present but application unpublished;
leadership fencing between admission and capture; a timed-out waiter receiving a
late publication; close/install racing with a pinned view; and waiter saturation
starving catch-up. For each, specify the permitted public outcome and the exact
evidence needed to reject an invalid success.

## 4. Evidence matrix to freeze with the contract

These are planned evidence families, not executed scenarios or a frozen scenario
count. Expand each into concrete schedules, numeric bounds and negative mutations
before calling Phase 0 complete.

| Family | Required observation |
| --- | --- |
| E01 policy/API compatibility | Existing V5.1 strong/default callers and configured-mode consumers preserve behavior; every supported new policy is exercised through public APIs. |
| E02 published prefix safety | Stale success matches a valid committed published prefix; accepted-only tails and unpublished proofs cannot become results. |
| E03 lower-bound progress | Below/equal/above required position, zero-wait/deadline cases, successful catch-up and no silent downgrade; token/result provenance binds one compatible history. |
| E04 identity/lifecycle | Wrong group/history/version, retained restart, checkpoint/compaction, backup import/new group and stale tokens; equal numbers cannot cross identities. |
| E05 authority races | Partitions, old leader, higher promise before/after capture, concurrent writes and follower rejoin/install; preserve strong safety and explicit stale guarantees. |
| E06 wait/cancel/close | Bounded queue exhaustion, cancellation at each ownership transition, late completion, close and callback behavior; prove permit/pin cleanup and catch-up progress. |
| E07 pagination/snapshot | Page consistency, query mismatch, changed materialization, wrong replica/process, snapshot pin lifetime and all unsupported combinations. |
| E08 independent rejection | Mutate token binding, published cut, returned documents, invocation order, source/attempt and resource receipts; valid originals must pass before negatives count. |
| E09 operating envelope | Compare leader/stale/minimum-progress reads under declared offered load and lag. Report wait latency, errors, retained bytes and impact on writes/recovery; no linear-scaling claim from a single throughput number. |

Keep control-plane log positions and application operations separate in the oracle.
Use local monotonic clocks for intervals; do not subtract timestamps across hosts.
Public three-process tests must use supported APIs for token issuance and reads,
while internal hooks may only choose deterministic faults. Preserve all failed
attempts and exact source/artifact identity. A published control or a prior V5.1
cloud success does not qualify V5.2 behavior.

## 5. Concrete next batch and outputs

Prepare one coherent Phase 0 document set before production work:

| Planned file | Required contents |
| --- | --- |
| `PHASE_0_CONTRACT.md` | Resolve D01–D10; authority, non-goals and policy/state matrix; unresolved blockers stay explicit. |
| `READ_AUTHORITY_AND_LIFECYCLE.md` | Read/token transitions, capture ordering, restart/install/cancellation races and counterexample arguments. |
| `API_FORMAT_AND_COMPATIBILITY.md` | Exact proposed signatures/errors, token encoding/validation, version strategy and supported upgrade path. |
| `TESTING_AND_EVIDENCE.md` | Concrete E01–E09 schedules, independent oracle/negative rules, public consumers and resource/measurement criteria. |
| `PHASE_0_CHECKLIST.md` | Decision/evidence cross-reference, reviewed source, open issues and actual acceptance identity. |
| `PHASE_1_ENTRY_PLAN.md` | Declaration/byte fixtures, independent model and deterministic network/process tests; explicitly separate from production enablement. |

Resolve token/publication semantics first, then API/lifecycle/bounds, then evidence
and cross-document review. These are work groups within the next contract batch,
not a requirement to create one PR per table row. Keep the next PR documentation
only unless the user explicitly changes the phase scope.

Phase 0 exit requires all ten decisions resolved with rationale, every public
operation mapped to lifecycle/outcomes/resources, compatible old behavior, exact
format and numeric-bound decisions, independent evidence cases, local link/contract
checks and protected review. Record acceptance only after merge. A docs-only CI
pass checks documentation; it does not validate the design experimentally.

## 6. Current CI and execution boundary

Use [the existing tiered CI](../../CI_TIERED_DESIGN.md). This entry and other
permitted Markdown select docs. Future V5.2 source, tests, scripts, build inputs
and machine plans are unclassified non-doc inputs and select full; the sole
integration rule remains ordinary content changes to the travel example.

The [Tiered CI acceptance gaps](../../CI_TIERED_ACCEPTANCE.md) remain visible:
five retained local failures and unobserved Nightly/cross-event behavior. Preparing
this read contract does not close those checks or trigger extra CI/cloud runs.
Commit/push/PR operations remain operator-owned. Paid execution and publication
still require separate user authorization; no account/IAM setup is part of Phase 0.
