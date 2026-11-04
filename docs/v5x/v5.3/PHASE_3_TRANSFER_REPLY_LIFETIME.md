# Phase 3 native transfer reply revocation

This component qualifies a PROMISE record response that has been materialized
inside `MembershipTransferService` but has not returned from its handler. It
complements the existing between-request expiry/close/lost-response matrix.
Phase 3 remains **OPEN**.

## Native scope

[`V53TransferReplyLifetimeTest`](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53TransferReplyLifetimeTest.java)
uses public offline bootstrap and real loopback TCP at stable sizes 3, 4 and 5.
Each of the 48 cases has its own original bootstrap, native owner, forced
PROMISE/BASIS and original source inventory. No authority is reset between
revocations on a shared owner.

| Reply boundary | Revocations at each boundary and size |
| --- | --- |
| SOURCE_OFFER | Original deadline expiry; service close; owner close; higher ballot |
| First DATA chunk | Same four revocations |
| Final TRANSFER_COMMIT | Same four revocations |
| Exact completed-commit retry | Same four revocations |

The existing `TRANSFER_BEFORE_REPLY` callback records the materialized bytes and
then performs the fault. Expiry adds exactly the original 60-second budget to
an injected clock offset. Higher ballot uses the actual owner's
`observeCurrent` and requires its typed `HigherBallot` refusal; it does not
pretend to be a received remote vote or a new durable promise. Service/owner
close invoke their real lifecycle methods. No production hook or timing bound
was added or changed.

The source and receiver record actual request-write, request-read, response-write
and response-read boundaries. The faulted call must produce IO without a
response-write. The service must already be closed and drained. An exact retry
and a new trace must both fail without rematerializing a response. For expiry,
the clock offset is reset before those probes: rollback cannot revive the scope.
Completed-commit cases observe the bounded replay marker with no live export.

This does **not** qualify revocation between handler return and a later socket
write, all source/learner/vote export kinds, process death, competing elections,
or a simultaneous physical resource maximum. Those obligations remain separate.

## Independent replay

[`transfer_reply_lifetime.py`](../../../scripts/v53/transfer_reply_lifetime.py)
first reconstructs every original source from admitted bootstrap bytes using the
existing source reader. It checks native force order and compares the final
owner files against the original captured bytes. The volatile higher-ballot
injection and read-only exports must not create a durable grant or publication.

It then derives each request and response from the original PROMISE bytes,
including sequence, trace, sender/recipient, ballot, content digest and offset.
It requires the exact event order, the unchanged original request deadline,
materialization before revocation, absence of any faulted response-write, and
both failed probes. Resource counters are explicitly source-bound observations;
they are not independently measured physical peak usage. All resources must
return to the live-owner baseline or zero after owner close, then zero at the
final close.

Thirty mutations cover physical authority, force order, materialized and delivered
bytes, late response, expiry, higher ballot, exact/new-trace retry and resource
release. Qualification validates the complete original before mutating copies,
requires each exact rejection reason, and rechecks original preservation. It
never reruns a workload to repair a reader failure.

## Development validation

The retained native execution passed all 48 cases once, with zero retries, in
278.860 seconds including compilation. Independent replay derived 216 calls,
120 materialized replies, 72 delivered replies and 144 refused calls (the fault
plus two non-revival probes in each case). All 30 exact negatives passed.
The complete V5.3 Python suite passed 2,559 tests; the 34 focused reader tests
also passed with Python assertions disabled.

A separate deliberate mutation removed only the final post-materialization
`live()` call in an isolated source/build copy. The first expiry case then
received a response and the native test failed with the expected missing
`ExecutionException`. Its failed original/log remains retained; this is a test
sensitivity check, not a retried or repaired successful experiment.

## Reproduction and admission boundary

Run the focused native matrix from a source/build recorded for the intended
cohort, retaining the printed `v53TransferReplyLifetimeEvidence` directory:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  '-Dtest=V53TransferReplyLifetimeTest#materializedRepliesCannotOutliveOriginalScope' test
python3 -B -m scripts.v53.transfer_reply_lifetime ORIGINAL_DIRECTORY --qualify
python3 -B -m unittest scripts.v53.test_transfer_reply_lifetime \
  scripts.v53.test_transfer_fault_evidence
```

Use a new evidence directory for every native execution and preserve failed
originals. A standalone reader PASS is a component replay, not source/build or
hosted cohort admission. This batch adds no hosted subset and does not increase
the current 462 planned whole histories. The remaining competition/transfer
cohort integration and final-source execution still need their own admission.

The [development receipt](phase3-evidence/transfer-reply-lifetime.json) records
actual checks, original location, source/build/toolchain and reader hashes.
Native capture and final reader source are retained separately; later Python
reader edits are not represented as bytes built by the earlier Java execution.

Rollback removes the optional test, reader/tests and these navigation entries.
Runtime Java, wire/storage formats, deadlines, workflows, Required and V5.2 cloud
experiments are unchanged.
