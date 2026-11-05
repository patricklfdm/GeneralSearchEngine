# Phase 3 explicit probe export ownership

This follows [constructor rollback ownership](PHASE_3_EXPORT_CONSTRUCTOR_ROLLBACK.md).
The [development index](phase3-evidence/probe-export-ownership.json) retains the
focused checks. Phase 3 remains OPEN.

## Exact scope

Successful direct qualification probes now expose their actual original cleanup
handles through the opt-in resource observer. A prefix probe has one prefix lease;
an INTENT probe has its metadata lease and the exact nested prefix lease. These
are separate from source sessions, activation/maintenance borrows and failed
constructor rollback. No request, voting authority or resource identity is
invented to fill an unobserved allocation.

The fixture call sites have different coverage. The full joining/required-four
path includes the published learner prefix probe. INTENT expiry, capacity and
fencing guard probes run only in the `!publishJoint` branch. Instrumenting both
does not mean the full required-four history executes all guard probes.

Descriptor inspection and original cleanup execute outside the budget monitor.
Observation-disabled calls return the original object without inspecting it.
Every close invocation still reaches the original exporter, including repeated
calls. Only the first invocation records an interval; a failed close cannot be
turned into a normal return by a later retry. Original primary and suppressed
exceptions are preserved. Normal return requires every recorded handle released;
an already revoked prefix retains its original identity.

Invalid, foreign or truncated observations invalidate evidence while preserving
the original cleanup path. Limits, formats, deadlines and protocol decisions are
unchanged.

## Replay

The generic export inventory accounts for probe allocations separately and
rejects overlap with sessions, direct-operation borrows or constructor rollback.
Unmarked allocations remain PARTIAL. Final zero usage alone is insufficient.

The probe reader accepts explicit expectations derived by its caller from
originals. It checks exact immutable reservations, content bindings, extents,
successful body boundaries, uninterrupted body ownership, original child release
order and normal cleanup return. Its narrow PASS does not qualify served content,
all native probes or whole-runtime physical custody.

Two actual conditional prefix captures retain their original selector and
generation manifest: normal close and expiry followed by close. The independent
component reader derives the prefix binding from those bytes and verifies that
baseline ownership is restored. This baseline equality applies to these
synchronous components, not a concurrent native runtime. Both outer receipts
remain PARTIAL because they are not complete native membership histories.

## Validation and remaining work

- Ten new Java tests and adjacent regressions: 46 tests pass, no skips/errors.
  Both actual captures come from that exact hashed Java input.
- Eleven new Python tests and adjacent readers: 178 tests pass. Synthetic nested
  INTENT cases exercise the reader; they are not actual INTENT content evidence.
- The two original captures pass 24 exact negative checks. Each unmodified
  original must validate before any mutation; unrelated rejection is failure.
- The retained stable native history still passes physical/network/resource and
  export replay for 45 allocations. It has no probes and does not qualify the new
  Java source or joining history.

Logs, copied JUnit reports, source hashes and component inventories are retained
under `target/v53-probe-export-ownership/`. No long native execution or hosted
workflow was run in this batch.

Remaining work includes complete native joining/required-four composition,
independent joining metadata content/extent checks, additional failure paths,
physical custody and final-source hosted qualification. The plan remains twelve
review requirements and 544 planned hosted histories; the 3310 S cases belong to
Phase 5.
