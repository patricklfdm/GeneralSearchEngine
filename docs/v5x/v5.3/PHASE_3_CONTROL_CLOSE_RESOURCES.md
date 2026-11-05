# Phase 3 source-component cleanup intervals

The [native source buffer reader](PHASE_3_NATIVE_SOURCE_RESOURCES.md) already
binds original source requests, sessions and cached replies to transport and
resource lifetimes. This batch adds a separate observation of the cleanup call
that actually releases a source session, transfer trace or transfer service.
Exact inputs and retained reports are in the
[development index](phase3-evidence/control-close-resources.json).
Phase 3 remains OPEN.

## Recording and semantics

`MembershipControlCloseObservations` is disabled by default. Enabling it requires
the existing complete resource journal. BEGIN and RETURNED carry the original
CONTROL owner, one call identifier and the budget's resource sequence. BEGIN
also records the actual child reservations held by that cleanup scope. The
resource monitor serializes the observations without I/O or external callbacks;
the close work itself executes outside that monitor under its existing locks.

The recorder allows at most 65536 rows and 262144 child references. Missing,
failed or truncated recording rejects qualification. Observation failures cannot
enter resource cleanup's exception path. These are observation bounds, not new
runtime admission, time or storage limits. The existing resource delta schema,
wire formats, deadlines, retry policy and lease limits are unchanged.

RETURNED is recorded only after normal cleanup, including the exporter close.
An exporter exception therefore leaves BEGIN even if all session CONTROL bytes
were already released. Repeated close calls that do no cleanup add no new pair.
The annotation describes the **cleanup-performing invocation**; it does not
assert that every concurrent no-op caller waits for another closer's drain.
No process-crash experiment is inferred from an exception test.

## Original evidence and independent checks

The opt-in test collector writes `control-close-captures` beside the unchanged
resource collection. Its exact inventory binds each original owner identity,
resource-file hash and original events hash. Each owner file is limited to
64 MiB and the collection to 256 MiB; incomplete captures cannot qualify.

`scripts.v53.control_close_evidence` first runs the original public-bootstrap,
physical source, record-byte, TCP loss/retry and source-buffer readers. It then
requires every selected cleanup scope to have a unique complete pair, its
original reservation live at BEGIN, its release before RETURNED, and the actual
children released in the correct nested order. An already completed session
must have closed before its trace cleanup starts. The source-component check
also requires the complete response inventory at session close and containment
within the fixture's independent service call/return events.

Final zero accounting alone does not satisfy any of these checks. Historical
source collections still replay under their old source scope. Asking the new
close reader to qualify one without the original sidecar fails explicitly;
old collections are never assigned reconstructed close markers.

## Development validation

Four new loopback TCP histories cover lost offer, lost data, lost final commit
and exhausted offer replies. They pass 12 cleanup intervals and 64 exact close
mutations. The same unchanged originals also pass all 76 prior source-resource
mutations. Every negative suite first validates its unmodified input.

32 targeted Java tests pass, including nine new recorder/close tests and five
existing transfer-service deadline, concurrent-close and completed-cache tests.
The new tests distinguish exporter failure from normal return, check bounded
and damaged recording, and confirm that a slow exporter does not hold the
budget monitor. Original input hashes, test counts and Python checks are in the
development index. Initial test-compilation and conditional-fixture failures
remain retained alongside corrected results.

Reproduce independent replay of a retained source collection with:

```bash
python3 -m scripts.v53.control_close_evidence RAW
python3 -m scripts.v53.control_close_negatives RAW
```

## Remaining work

This is component qualification, not whole-runtime resource acceptance. The
joining checkpoint endpoint has its own concurrent listener-close/drain behavior
and is not claimed by these markers. Its close scope, multi-session native close
integration, export/task/control ownership, post-handoff physical custody,
combined maxima/headroom and final-source hosted qualification remain open.
The existing native `serviceCloseIntervalsQualified` flag stays false until that
integration has its own original evidence. No frozen histories or hosted jobs
change in this batch.
