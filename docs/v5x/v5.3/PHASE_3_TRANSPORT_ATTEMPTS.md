# Phase 3 — original failed transport attempts

The retained `3-REPLACE` history has unanswered control attempts. Its original
trace cannot establish their terminal state, so complete network replay still
rejects it. This batch adds the missing observation to future executions and
qualifies the mechanism with short real TCP cases. It does not repair old
evidence or close the full joining-profile gates.

## Collection boundary

`MembershipTransport.Events.failed` is a default method on the existing internal
functional interface. It reports the already-classified reason after an observed
attempted-write or admitted-request-read boundary. Preflight, queue admission or
connection failures before the attempted-write boundary produce no such row.
Existing functional callbacks remain compatible.

The joining trace records `NETWORK_ATTEMPT_FAILED`, its direction, permanent
node, optional owner scope, exact request digest, kind and failure reason. No
response or remote vote is manufactured. In particular, a terminal I/O error
does not prove that the recipient performed no durable work.

The receiver reports handler failure before closing the socket can unblock an
identical caller retry. The caller releases socket/resource/permit ownership and
reports failure before completing its future. An observation callback failure
is suppressed on the original transport error; it cannot replace that error or
strand the future. The optional diagnostic log remains outside evidence authority.

Protocol frames, durable formats, timeout/capacity settings and retry policies
are unchanged. The transport does not automatically resubmit an operation.

## Independent replay

`joining_attempts.py` binds every terminal row to the preceding original send
bytes, root, permanent endpoints and owner scope. An observed server read needs
its own original server terminal; a caller timeout cannot supply it. Both
terminals must finish before an identical retry starts. Duplicate, foreign,
malformed and late terminal records are rejected.

`joining_transcript.py` consumes qualified response-less controls separately
from response rows. They contribute attempted-send/read counts, never ACKs.
The existing declared initial source-reply loss may also bind both terminals;
its unchanged loss policy still requires exact recovered bytes and complete
transfer sequencing. Response-less CHUNK/TRANSFER_COMMIT, unqualified response
loss, post-delivery failures and ambiguous overlapping retries remain rejected.
Transfer-only replay still leaves control completeness to the full network gate.

The new component oracle derives identities and status from the original public
bootstrap, checks exact request-byte reuse and the successful reply, and compares
all original storage before/after. It checks input inventories and runs the
unmodified evidence before any mutation. Each negative must fail for its exact
designated reason; an unrelated original or mutated failure is not a pass.

## Local qualification

```bash
mvn -o -B -ntp -f reactor/pom.xml \
  -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53TransportAttemptTest,V53MembershipTransportTest,V53JoiningTraceTest test
python3 -B -m scripts.v53.transport_attempt_evidence /path/to/raw --qualify
python3 -B -m unittest scripts.v53.test_joining_attempts
```

Loopback sockets are required. The test prints its original evidence directory.
Six cases cover old/scoped observations and handler I/O, handler protocol and
pre-write guard failures, each followed by one identical explicit retry using
the same deadline. Additional Java checks cover observer failure, preflight
rejection, deadline expiry and close, including released capacity.

The [batch receipt](phase3-evidence/transport-attempts.json) records executed
tests, thirteen original-first negatives, source/build inventories, portable
optimized replay and unchanged historical peer replay. The initial sandbox
socket denial is retained separately from the successful loopback execution.
This uses an incremental local test build, not a clean reactor or protected CI.

The old complete `3-ADD` peer result remains unchanged. The old incomplete
`3-REPLACE` control transcript still fails at its ambiguous retry; no missing
terminal was synthesized. Full profiles on the new producer, same-view joining
installation, complete export/maintenance/peer composition, whole-history
process cuts, REMOVE profiles and frozen acceptance mapping remain open.
Phase 3 remains **OPEN**. No workflow, cloud experiment or push is performed.
