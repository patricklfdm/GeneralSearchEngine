# V5.1 Phase 4I: public promise crash boundaries

**Status:** accepted through PR #200 at master
`6a781ac33945016645961ec1c6564d8975cd82fd`, exact-master CI `35693468905`.
All eleven full-CI lanes and the Required gate succeeded. Complete Phase 4
acceptance remains open; [Batch J](PHASE_4_PUBLIC_CANDIDATES.md) adds candidate-side
election crash qualification.

## Public schedule

`scripts/verify-v51-phase4-public-promises.sh --skip-build` compiles the external
consumer against packaged candidate JARs. Bootstrap, startup, mutations, strong
reads and close use public APIs. The internal observer only reads bytes and stops
at existing storage/transport boundaries; it cannot elect or repair a voter.

Each case creates three fresh public voters, acknowledges three tagged atomic
bulks and reads their ordered projection. Node 3's public bootstrap policy seals
a 600–601.2-second election interval; the other two retain the fixture's
3.6–6-second interval. This makes node 3 the interrupted peer-promise recipient
without choosing a ballot or disabling its voting/recovery behavior privately.
These are explicit test settings, not changed product defaults or latency claims.

After node 3 retains the proven seed prefix, the controller arms its crash and
SIGKILLs the current leader. The other voter campaigns naturally. At the requested
boundary, node 3 either calls `Runtime.halt(71)` or waits for controller SIGKILL.
The controller independently inspects and archives its exact stopped authority
before reopening that same directory in a new public JVM.

The original leader stays absent until the surviving voter and restarted node 3
serve a strong read, acknowledge another unique bulk and read the expanded
projection. Finally the original leader restarts and the group reads again.
Mutations are never replayed. Bounded recovery-read retries retain every typed
availability rejection in the client history; integrity/storage failures fail.

## Twelve cases

Each boundary runs once with halt and once with SIGKILL:

| Boundary | Independent required observation at crash |
| --- | --- |
| `PROMISE_BEFORE_WRITE` | Exact old promise journal; no new promise bytes or force. |
| `PROMISE_AFTER_WRITE` | One complete higher promise appended, matching a peer PREPARE; no force for that promise yet. |
| `PROMISE_AFTER_FORCE` | The exact appended promise has a preceding force observation in the same PID. |
| `PROMISE_BEFORE_ACK` | Forced promise retained before the storage operation returns. |
| `BASIS_BEFORE_ACK` | Forced promise plus the exact published frozen BASIS and matching IMAGE. |
| `WIRE_BEFORE_RESPONSE_WRITE_PREPARE` | Correlated positive PROMISE reply carries that same frozen BASIS after the promise force. |

The storage `BEFORE_ACK` boundary is distinct from the actual transport reply
boundary. Pre-force complete bytes surviving a JVM crash are not labelled forced.
This suite does not simulate power loss or filesystem cache loss.

## Independent evidence and rejection checks

The existing client-history and raw force/quorum/read oracles validate the complete
run. The additional [promise oracle](../../../scripts/v51/public_promise_evidence.py) independently
decodes checksummed root journals, rejects torn/reordered/duplicate epochs, and
requires exact prefix preservation across the crash archive and final authority.
It binds the previous durable promise, new peer request, force order, frozen
basis/image and reply correlation to actual bytes and process generations.
Node 3 must force an acceptance and proof for the post-restart public write.

Negative evidence removes the cut, exact boundary, pre-write bytes, prior/new
promise forces, retained restart or new acceptance; substitutes an archive hash;
or mislabels the crash stage. The checker must reject each mutation. Separate
unit fixtures test torn journals, invalid checksums, wrong voter identity, missing
genesis promises, reused/backwards epochs and forgotten/rewritten prefixes.

CI runs this gate in `v51-foundation-admission` and always uploads
`v51-public-promises-${{ github.sha }}` for fourteen days. Receipts include source
inventory, candidate JAR hashes, raw traces, client histories, pre-reopen archives,
exit codes, independent validation and failed negative variants.

## Scope and remaining qualification

This adds public E04 promise write/force/frozen-basis/reply interruption evidence
and supplements E08 retained-restart/history checks. It does not complete E04
or the entire Phase 4 matrix. Candidate-side crashes are extended in
[Batch J](PHASE_4_PUBLIC_CANDIDATES.md). Epoch/promise/ancestry exhaustion, snapshot-staging capacity, saturated
transport queues, slow-force accounting, ambiguous/conflicting frozen selections
and the remaining E01–E12 mapping still need explicit qualification.

No production Java, public API, wire/storage format, version, dependency, paid
cloud behavior or published V5.0 authority changes are included.

## Local validation

Base: local `55f2573430b6eaf74fe627db902bdda4204a4602`, whose file tree exactly
matches merged master `fdf9482781e04727e20326fa0e32bcd281242f04`, plus this batch.

- Full twelve-case gate: `target/v51-public-promises/run.itUhOH/evidence/receipt.json`
  passed with 96 application calls, 60 JVM identities and 168 rejected evidence
  variants. All twelve retained runs also passed the final oracle, including
  election policy decoded from the plan in the bootstrap seal; the extra review
  is recorded in `target/v51-public-promises/final-oracle-review.json`.
- Existing default public runtime: `target/v51-public-runtime/run.stfh8g/evidence/receipt.json`
  passed with four processes, nine chosen/publications, three acknowledged
  mutations and three strong reads, including published V4.4 backup comparison.
- Existing `basis-kill` protocol case passed in
  `target/v51-public-promises/shared-basis/receipt.json`.
- Final observer/policy-reader `before-reply-kill` recheck passed in
  `target/v51-public-promises/final-reply-check/receipt.json`.
- All 132 V5.1 Python tests passed; all 25 CI/toolchain fixture tests passed.
  CI YAML, 99 shell blocks, 28 unique artifact names, unchanged existing workflow
  steps/required lanes, the 31-document contract and whitespace checks passed.

Core candidate SHA-256:
`f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.
Replication candidate SHA-256:
`c43a9088e99929faf8a2b8a7266967c27887a325926be3e1a6916a108a770ed4`.
Production sources and packaged candidate bytes are unchanged. This batch compiles
and executes its external Java consumers; it does not claim a new full Maven
reactor run. CI performs each lane's existing full reactor build and tests.

Development receipts are retained, including a checker lookup failure while adding
the sealed-policy audit: policy is in the PLAN nested in the bootstrap SEAL, not
BOOTSTRAP_BINDING. This was a qualification-reader correction, not a runtime
protocol change. Source inventories describe execution-time worktrees; these
validation notes were written afterward.
