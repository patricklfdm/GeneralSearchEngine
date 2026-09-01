# V4.0 durability and completion semantics

## Logical mutation unit

A logical unit is either one accepted single operation, one accepted atomic bulk, or
one accepted durable dynamic-index transition. A bulk has one external Future, one
sequence, one WAL unit, and all-or-nothing recovery regardless of element count.

An empty bulk retains the V3.4 immediate no-op behavior and consumes no sequence.
Every other successfully accepted operation, including a remove/drop whose target is
already absent, consumes one sequence. This makes retry histories deterministic.

## Validation and sequence allocation

The writer applies each unit to a private candidate state and validates the candidate
before sequence allocation. This preparation is not visible to readers. A unit that
fails schema, codec, index-kind, capacity, or mutation validation receives no sequence,
no WAL representation, and no publication. In an automatic writer batch, one rejected
unit does not invalidate otherwise independent valid units.

Accepted committed sequences start at `1` and are contiguous. `0` means no committed
unit. Duplicates, gaps, non-increasing replay, wraparound, and allocation past
`Long.MAX_VALUE` fail closed. Sequence values identify durable history and are exposed
only by the durable capability, not by existing mutation return values.

## Required success order

For every durable logical unit, the following order is normative:

```text
prepare, apply, and validate private candidate
  -> allocate next contiguous sequence
  -> encode and append the complete framed WAL unit
  -> force the containing commit group
  -> atomically publish the prepared immutable snapshot
  -> complete each successful Future
```

No successful Future may precede durable force or snapshot publication. Recovery must
include every successfully completed unit.

## Group commit

The writer may prepare multiple logical units in order, append them, perform one force,
and publish one snapshot. Each unit retains its own sequence, frame, validation result,
and Future. The force makes a contiguous prefix durable. Publication exposes exactly
that prepared prefix. A crash may recover a valid forced unit whose Future had not yet completed;
therefore a pre-crash incomplete Future is indeterminate, not promised absent.

## Atomicity and visibility

- A successful single unit is wholly present in its published snapshot.
- A successful bulk is wholly present; no element prefix may recover or publish.
- Readers see the previous or next immutable snapshot, never an intermediate apply.
- WAL order, committed sequence order, application order, and recovery order are the
  same authoritative order.
- Checkpoint completion is never required for ordinary mutation success.

## Runtime failure states

Failure before sequence allocation is an ordinary per-operation failure. Failure
during encode/append/force, or uncertainty about the forced boundary, moves durable
mutation service into terminal `FAILED` state for that engine instance:

- the affected and queued mutation/index-transition Futures fail;
- new mutations are rejected;
- the last successfully published snapshot remains readable;
- no in-process retry, truncation, or return to writable state is allowed; and
- close releases resources, after which a new open performs authoritative recovery.

A capacity-limit rejection detected before append does not by itself make the writer
terminal. Searches remain available and an explicit checkpoint may release eligible
history. A checkpoint-specific failure leaves the old checkpoint authoritative and
the writer usable only when the WAL/storage health is still known; a storage-wide or
ambiguous I/O failure uses terminal `FAILED` behavior.

## Close

Close rejects new admission, drains already accepted work using the same success
contract, closes WAL and directory ownership, and then completes. Close does not
require or imply a checkpoint. A clean close may record diagnostic metadata but
correct recovery never depends on it.
