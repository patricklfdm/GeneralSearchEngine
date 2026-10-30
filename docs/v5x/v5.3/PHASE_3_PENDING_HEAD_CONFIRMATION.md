# Retained pending-source confirmation

Phase 3 remains **OPEN**. This extends the existing
[learner confirmation](PHASE_3_LEARNER_CONFIRMATION.md) and
[pending-linked joining](PHASE_3_PENDING_JOINED_CUSTODY.md) paths.

The original native joining attempt reached JOINT at index 6, but both old
voters still held possible sources `[3,5]` with no confirmation. Offering source
6 correctly refused a third unresolved endpoint. The original failed execution,
source, original ledgers and diagnostics remain retained in the preceding
[component receipt](phase3-evidence/pending-joined-custody.json).

A private capability from the actual forced pending owner may now report its
complete retained SEALED source at 5 through the existing read-only head
QUERY/ACK protocol. This is a source-possession observation; the original typed
selector stays at 3. The pending INTENT and its ACK do not authorize reporting
unretained JOINT at 6. Only the original pending SOURCE reservation, forced ACK,
retained marker and unchanged complete source can supply the observation.
Decoded metadata, copied files and ordinary typed-head observation do not bypass
the pending disposition. Every response checks the actual owner and original
bytes/inodes, including after the external before-response hook. Closing the
owner or creating a linked full INTENT revokes new observations.

The pending owner tracks the new listener. Its checkpoint listener and head
listener cannot coexist; replacement requires the previous listener to drain.
Voter handoff drains either actual listener outside the owner's monitor, and
custody requires both to have released their reservations. Read-only queries
use the existing CONTROL allocation; no wire, public format, voting authority,
source/endpoint capacity or production timeout changes.

An old source owner may query after JOINT or COMPLETED only while its retained
ledger still binds that exact original prepared operation and permanent learner.
The requester must be both a current voter and an original voter in the prepared
stable view. A newly joined voter cannot query as an original source voter.
CANCELLED, changed operations/identities and unretained reservations still refuse;
ordinary discovery remains restricted to the active pre-JOINT reservation.
The original stable endpoint and request remain authenticated by current ancestry.

Each source owner must receive its own actual wire reply through its own live
probe and force its own confirmation. One owner's Received capability cannot
be installed by another owner. Confirming 5 narrows `[3,5]` to `[5]` but keeps 3
as checkpoint renewal debt; the plan can project `[5,6]` within the unchanged two-point bound. Actual
post-publication export remains blocked by the separate contract gap below. Selected-source reconciliation is still required
before another source's renewal debt can be discharged.

Four focused tests pass: original forced SOURCE binding, malformed query and
mutated original refusal, last-response-boundary mutation, owned listener drain,
and the existing ordinary typed-head interface. No skipped cases.

The additional native integration attempt uses real bootstrap, an old 2/3
majority with the third voter unreachable, READY/SEAL, original joining ACK and
JOINT publication. It completes both actual QUERY/ACK exchanges and forces both
old ledgers to `[5]` with renewal debt `[3]`. The original after-close checksummed
ledgers retain exactly those wire frames. This establishes the confirmation
milestone in that execution, not a passing full native history.

The later source acquisition **fails** at `learner intent original stable
reservation`. The prefix service has the correct JOINT context, but dispatch
still requests the nonvoting learner replicated-retention permit unconditionally;
that permit deliberately accepts only the pre-JOINT stable reservation. The
complete published-INTENT export needs an explicit source-obligation contract.
Do not remove the permit check or synthesize a governing quorum. Conditional
progress fixtures lack that opt-in native retention path, which is why they did
not expose this missing connection.

The failed research case, exact source, reports, wire, physical ledgers and
original thread diagnostic are preserved in the
[component receipt](phase3-evidence/pending-head-confirmation.json) and archive.
It does not count among the four passing tests. Existing committed native tests
remain unchanged; the full integration case must return as a gate after the
published-source contract is implemented. The research lifetime was declared
before execution; production RPC deadlines and the existing cases are unchanged.

Automatic coordinator continuation, joint FINAL/fresh barrier, independent
original-first physical/history replay, actual process death and all profiles
remain required. Expensive complete acceptance remains in the
[deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md); focused component results do not
close Phase 3.

Rollback may disable the new pending-source observation and post-publication
query entry points. Preserve the existing confirmation/renewal decoder and all
already forced ledger bytes; do not clear debt or rewrite the original source
as a workaround. Removing this connection restores the original safe capacity
refusal, rather than authorizing a third uncertain endpoint.
