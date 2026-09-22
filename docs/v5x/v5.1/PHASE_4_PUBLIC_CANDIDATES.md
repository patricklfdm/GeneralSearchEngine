# V5.1 Phase 4J: public candidate election crashes

**Status:** accepted through PR #201 at master `04106a0c2e88010c2c14c43ad485bc3113ed1d05`,
exact-master CI `35698045261`; all eleven full-CI lanes and the Required gate
succeeded. Complete Phase 4 acceptance remains open. The local record below
retains the Batch J execution-time evidence and prior Batch I base.

## Public execution

`scripts/verify-v51-phase4-public-candidates.sh --skip-build` compiles the external
public consumer and observer against packaged candidate JARs. All bootstrap,
startup, mutation, strong-read and close operations use public APIs. Existing
storage/transport hooks only observe bytes or stop a JVM at a real boundary.
The controller cannot assign an epoch, inject a vote or rewrite retained authority.

Each fresh three-voter group acknowledges three tagged atomic bulks and reads
their ordered contents. Node 3 uses the same bootstrap-sealed 600–601.2-second
election interval as Batch I; nodes 1 and 2 retain the fixture's 3.6–6-second
interval. The inspector reads these policies from the actual PLAN nested in the
bootstrap SEAL. This public test configuration makes the survivor of nodes 1/2
the candidate while node 3 continues voting normally; product defaults do not change.

Both surviving voters must retain the proven seed prefix. The controller arms
the candidate and SIGKILLs the old leader. The survivor campaigns naturally and
either halts with exit 71 or waits at the selected boundary for controller SIGKILL.
The controller independently inspects and archives the stopped authority before
reopening the same directory in a new public JVM.

The restarted candidate must regain leadership with node 3, serve a strong read,
acknowledge another unique bulk, and read the expanded projection. Only then may
the original leader restart. Controller-clock launch and call intervals plus
PID/generation trace bindings establish that the original leader could not rescue
the claimed two-voter recovery. Another strong read follows its retained restart.
All mutations are single attempts; bounded recovery reads retain every typed
availability rejection and do not swallow integrity/storage failures.

## Fourteen cases

Each of these seven boundaries runs with both halt and SIGKILL:

| Boundary | Required evidence |
| --- | --- |
| Own `PROMISE_BEFORE_WRITE` | Original journal unchanged; no higher PREPARE dispatch observation. |
| Own `PROMISE_AFTER_WRITE` | One complete self-proposed promise appended; no force or higher PREPARE yet. |
| Own `PROMISE_AFTER_FORCE` | Exact self promise force in the crashing PID, still before PREPARE. |
| Own `PROMISE_BEFORE_ACK` | Same forced grant before the storage call returns. |
| Own `BASIS_BEFORE_ACK` | Matching published self BASIS/IMAGE after the self promise force, before PREPARE. |
| `WIRE_BEFORE_REQUEST_WRITE_PREPARE` | Exact self ballot and frozen basis forced before the outgoing request observation; no peer grant. |
| `WIRE_AFTER_RESPONSE_READ_PREPARE:PROMISE` | Positive correlated peer response read before delivery to the election kernel, backed by that peer's earlier force and exact reply observation. |

The before-request hook is a dispatch boundary, not proof that request bytes were
sent. The after-response case separately requires the real peer grant and reply.
No acceptance or activation may use the interrupted candidate's written ballot.
Incomplete frames and negative responses cannot stand in for a positive PROMISE.

The pre-write case observes an unchanged durable journal; it does not recover the
unwritten in-memory ballot identity. Every retained/exposed self ballot must survive
the crash without reuse. Every restarted self campaign must advance the highest
retained epoch and use an incarnation absent from retained history. Identical
same-ballot re-forces are valid; a changed same-epoch identity, backwards epoch or
incarnation reused across distinct campaigns is rejected. JVM crashes do not
simulate power loss, and complete pre-force bytes are never labelled forced.

## Independent qualification

The [candidate oracle](../../../scripts/v51/public_candidate_evidence.py) combines
the existing independent client-history and decoded quorum/read checks with:

- Checksummed, strictly ordered root promise journals and exact prefix preservation
  across pre-write observation, pre-reopen archive and final retained authority.
- Candidate identity, own force before dispatch, frozen self basis/image, absence
  or presence of the exact peer grant at the declared boundary, and correlated
  received PROMISE backed by a force in the replying process.
- Fresh retained self-campaign identities after restart, a successful public write
  from that exact new process, and a read before the original leader returns.
- Negative variants removing boundaries, pre-write journals, self/peer forces,
  replies, restart or post-restart acceptance, substituting archive identity,
  mislabelling a scenario, or moving the old leader's restart before recovery.
- Unit witnesses for retained/new incarnation reuse, same-epoch conflicts,
  backwards campaigns, and falsely attributed recovered service/process starts.

The candidate and peer-promise suites share compilation/source-inventory and
read-only archive/journal helpers. They retain separate case matrices, scenario
oracles, fresh directories/processes and execution identities. CI adds this gate
to `v51-protocol-reclamation` and always retains `v51-public-candidates-${{ github.sha }}`
for fourteen days. No existing verification command, required lane or evidence
upload is removed.

## Remaining work

This adds candidate-side E04 interruption and E08 retained-restart evidence;
it does not close the full E04 exhaustion requirement or complete Phase 4.
Epoch/promise-count/ancestry exhaustion, snapshot-staging capacity, saturated
transport queues, slow-force accounting, ambiguous/conflicting frozen selections
and the remaining E01–E12 mapping still require explicit qualification.

Production Java, public APIs, wire/storage formats, versions, dependencies,
published V5.0 authority and paid-cloud behavior remain unchanged.

## Local validation

Base: `6a781ac33945016645961ec1c6564d8975cd82fd` plus this batch.

- Complete fourteen-case gate passed:
  `target/v51-public-candidates/run.iCBM2H/evidence/receipt.json`, with 112
  application calls and 70 runtime process identities.
- Final independent oracle review passed all fourteen retained runs, including
  force → frozen-basis publication → PREPARE/reply ordering. All 220 negative
  variants were rejected; `target/v51-public-candidates/final-oracle-review.json`
  binds the original matrix receipt and final oracle source hashes. This extends
  the initial gate's negative checks without replacing its execution-time receipt.
- Shared helper/observer regression: Phase 4I `before-reply-kill` passed in
  `target/v51-public-candidates/shared-peer-promise/receipt.json` with unchanged
  peer-promise execution identity and independent qualification.
- All 149 V5.1 Python tests passed, including seventeen new candidate-oracle tests.
  All 25 CI/toolchain fixture tests passed. YAML, 100 shell blocks, 29 unique
  artifact names, unchanged existing steps/required lanes, the 32-document
  contract, local links and whitespace checks passed.

Candidate JAR SHA-256 values remain:

- Core: `f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.
- Replication: `c43a9088e99929faf8a2b8a7266967c27887a325926be3e1a6916a108a770ed4`.

This batch compiles and executes external Java consumers against unchanged
production JARs. It does not claim a new local full Maven reactor run; each CI
lane retains its existing reactor build and tests. All exploratory directories
remain retained. Source inventories describe execution-time worktrees; final
validation notes and stricter oracle review were written afterward.
