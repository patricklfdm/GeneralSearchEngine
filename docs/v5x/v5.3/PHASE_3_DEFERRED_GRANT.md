# Reclaim same-cut sources before a fresh capture

Status: implementation and bounded component validation complete. The subsequent
[process qualification and required-four follow-up](PHASE_3_DEFERRED_GRANT_PROCESS.md)
adds fourteen fresh-process cases. Its complete native run passes the original
preparation failure, then exposes a distinct installed-generation/floor image
conflict. A successful required-four history and Phase 3 closure remain open.

## Ordering and authority

The failed run created a third immutable source before attempting to acquire a
four-copy governing floor. The six SOURCE slots cannot hold that final state.
Merely choosing another peer, extending the deadline or closing receiving files
early cannot supply missing headroom.

The journal now offers a narrow maintenance-aware grant path. It applies only
when at least two sources remain, the latest completed unselected BASIS is at
the exact current cut, neither its PROMISE nor BASIS belongs to the current
generation, and no accepted tail or pending vote/context owns it. Ordinary,
duplicate, selected and accepted-tail grants keep their existing path.

1. Check the actual voter, current generation, incoming full ballot, admission
   scope and journal capacity under the writer monitor. Reserve the existing
   two-frame journal headroom, then force a new PROMISE with a fresh BASIS UUID.
   No capture intent, source directory or BASIS has been created or advertised.
2. Release the writer monitor and acquire the ordinary original floor copies.
   Only the existing forced-floor, ancestry/tail, exact retirement inventory and
   forced journal replacement rules may retire old sources. The newly durable
   PROMISE supplies the higher fence; it is not deletion authority by itself.
3. Recheck the same generation, PROMISE and live invocation, completed maintenance,
   and original deadline under the writer. Capture the first original BASIS for
   that PROMISE using the existing capture transaction and return only after force.

The in-memory `DeferredGrant` has a private constructor and permits only this
invocation's continuation. Completion or any exception revokes it. It is not
serialized or reconstructed on reopen. No same-ballot replacement BASIS is
permitted after an unmarked incomplete PROMISE; the next attempt must use a
strictly newer ballot. If a capture intent was already forced, the existing
original-byte recovery completes that exact capture instead.

Both the outgoing activation driver and incoming authenticated PREPARE use this
ordering. The old-side joining preparation also uses it and keeps its original
cut and deadline while the promise changes. Network maintenance never runs under
the writer needed by reverse transfers. Incoming scope and view are checked again
under the writer before forcing a promise or capturing a basis. Outgoing lock
waits recheck the original deadline before reserving a counter. A higher ballot,
changed generation, closed scope or elapsed deadline prevents grant completion.

## Validation boundaries

`V53DeferredGrantTest` uses conditional original joint copies to cover:

- Four-copy establishment at SOURCE=6/APPLICATION=7 with two old sources;
  retirement and first capture then fit without increasing either limit.
- Exact duplicate return, unavailable/no-op maintenance, and higher observations.
- An interrupted forced PROMISE, six floor/source-retirement interruption points,
  and three post-maintenance capture/BASIS interruption points, followed by reopen.
- Incoming authentication before mutation, outgoing single-ballot allocation,
  entry fencing, waiting-for-writer deadline and no deadline renewal.
- Exclusion of an accepted FINAL tail from clean-source retirement.

These are real file operations with injected exceptions and owner reopen in the
same JVM. They are not fresh-process SIGKILL or power-loss evidence. The original
capacity-rejection regression remains unchanged: bypassing the new path still
correctly refuses three sources plus four floor copies.

The final-source targeted Java run passed **66 tests**, including all thirteen
new deferred-grant tests, the original capacity rejection, endpoint, joining,
capture/journal and one three-voter native activation. The earlier 62-test and
70-test runs predate the final entry/deadline guards and are retained separately.
The first test draft had a zero-count assertion error; its failed report remains
in the development index rather than being discarded.

Independent replay of that ordinary native history also exposed an older reader
assumption: selected materialization has derived its reachable original objects
since `6cb6844ce`, while this reader still expected the complete frozen packet.
`native_activation_evidence --current-prefix` now explicitly selects the existing
independent prefix derivation. The historical default remains unchanged. This
changes only the expected installed packet and its derived manifest/selector;
original grants, source files and network bytes must still match their complete
frozen originals. The reader never chooses its policy from output contents.
Twelve reader unit tests pass, and the same unmodified native original passes
the physical, force and network replay plus fourteen existing exact negatives
and two self-consistent output-policy mutations. These sixteen mutations are a
single-case development check, not the six-profile qualification entry. The
initial replay failure and a supplemental mutation-construction error are retained.

The new runtime must still pass the complete opt-in required-four native history,
its independent original-first replay and exact negative set. Full resource
composition across selected installation/publication and new process interruption
coverage also remain required. Earlier successful ordinary activation histories
and component counts do not replace these gates. Frozen formats, quorum rules,
resource limits, time budgets, twelve hosted subsets and 544 planned histories
remain unchanged; public runtime enablement remains outside Phase 3.

[Retained development validation](phase3-evidence/deferred-grant.json).

Rollback the maintenance-aware journal, activation/endpoint/driver and joining
campaign changes together. Keep the opt-in failing required-four regression and
its evidence, which describe the outstanding availability requirement.
