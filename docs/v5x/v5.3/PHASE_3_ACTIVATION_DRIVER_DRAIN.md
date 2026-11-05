# Phase 3: outgoing activation drain preserves original ownership

Status: focused runtime correction; Phase 3 remains OPEN.

An outgoing activation can stop while a peer task still owns a file channel or
waits inside a source exchange. Previously `Task.stop()` interrupted that thread,
and `Round.close()` released the local source export and campaign exchanges in a
`finally` block even when peer drain timed out. Closing from the active runner
could also release its scratch before that same runner returned.

Cancellation now marks the round and tasks stopped and cancels pending protocol
futures without interrupting peer threads. Every peer must drain before ancestry,
receiving copies, the local export and campaign controls can be released. A
failed drain keeps the same bounded round reachable; a later external close
retries its cleanup. Scratch ownership is released only after that succeeds.
Closing from the active runner or a peer callback revokes further work and
returns an explicit error instead of declaring its own drain complete.

No deadline, retry count, campaign/source limit, wire format or durable voting
rule changes. An unresponsive worker can still cause the existing bounded close
to fail; retaining its owner is intentional. This does not turn cancellation into
permission to retire durable sources or delete unrelated files.

## Validation

The [development receipt](phase3-evidence/activation-driver-drain.json) retains
original and corrected source hashes, JUnit reports and original native replay.
All five final regressions fail on the exact original implementation. The final
corrected reactor passes 33 Java tests; 138 Python checks, stable-3/4/5 activation
replay with ten negatives and the new native two-slot replay with twenty exact
accounting negatives pass. Neither native history is retried to obtain a pass.
The new deterministic regressions use actual bootstrap/journal/scratch ownership
and pause existing callbacks. They check:

- Original export, campaign request and peer-task reservations survive repeated
  failed drains, then release after the actual worker exits.
- A held file channel can still write and force after cancellation; closing the
  driver does not interrupt its writer.
- An interrupted external closer preserves the same owners for another close.
- Runner and peer self-close refuse completion and leave scratch locked until
  an external closer drains the invocation.

The reservation check uses original lease identities and extents. Unused incoming
transfer-service cleanup is permitted to release its own separate charge; total
queued bytes alone cannot distinguish that legitimate release from lost source
custody. Intermediate broad-count assertions and sandbox socket restrictions are
retained as development failures, not positive evidence.

These regressions qualify outgoing cancellation and cleanup, not arbitrary
transport failures, simultaneous physical maxima, interrupted process histories
or the final-source 544-history cohort. Phase 3 closure remains OPEN.
