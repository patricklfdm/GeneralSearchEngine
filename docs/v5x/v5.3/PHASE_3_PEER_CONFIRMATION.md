# Durable complete-copy peer confirmation

Phase 3 remains **OPEN**. This repairs the selected-retention capacity mechanism
observed in the [maintenance drain qualification](PHASE_3_MAINTENANCE_DRAIN.md).
It does not enlarge the two-endpoint, journal, source or time limits, choose a
preferred election winner or retry client DATA.

The retained failed competition froze node 3 at `[0,1]` in node 2's source, while
another owner had actually acquired node 3's complete generation at cut 2 and
recorded `[2]`. The conservative selected union became `[0,1,2]` and refused.
A larger local revision or a newer BASIS cut cannot resolve that uncertainty:
they do not establish which original peer copy was acquired.

## Native observation and durable metadata

The private peer plan may now retain `confirmation`, the canonical base64 of the
exact original GENERATION record from `MembershipFloor.Copy`. Only an actual
verified complete copy enters the native observation method. Its original root,
permanent owner, cut, catalog, application and ancestry checks remain required.
The record binds the endpoint and its original manifest; decoding or hashing it
alone proves neither receipt nor force. There is no public method that treats a
decoded confirmation as a new observation. Permanent storage identity remains
bound by the plan/catalog and the original native Copy capability.

Confirmation removes older possible endpoints but never a later unresolved
installation. An old observation cannot regress progress. Repeating an equivalent
observation retains the first original confirmation bytes and returns the existing
ledger revision without another write. Genesis creates no confirmation because
there is no older endpoint to discharge. Changed observations still complete the
existing candidate write, force, atomic replacement and parent force transaction.

Local narrowing preserves the older points in optional `renewals` until a
verified source reconciliation. These checkpoint obligations remain part of
`required`, so a peer with an older ledger can still obtain the original bridge
ACKs. At most two strictly ordered lower renewals are retained; a third refuses
before a new ledger is installed. This follows the existing
[learner confirmation](PHASE_3_LEARNER_CONFIRMATION.md) obligation model.

[Continuous maintenance](PHASE_3_MAINTENANCE_OBSERVATIONS.md) now defers optional
observation when it would require a third renewal, retaining the entire previous
ledger. The explicit observation API still refuses; only verified source
reconciliation discharges the retained debt.

The peer plan remains bounded by 32 KiB and its owner file by 64 KiB. The manifest
encoding is individually bounded and the complete plan must also fit its existing
limit; a large union of manifests can be refused. No claim is made that every
maximum-sized GENERATION record fits this smaller metadata budget. Legacy plans
without the optional fields retain their encoding.

## Selection and joining boundaries

The selected verifier first validates the exact SELECTED source references,
PROMISE/BASIS envelopes, included GSRP wrappers, original owner-bound ledgers and
local predecessor. Its private provenance token then permits the merge to use
recorded confirmations. All same-index conflicts, including renewal debt and
conflicts across peers, are checked before dropping anything. Only points strictly
below the confirmed endpoint are discharged. Equal endpoints select the original
manifest by deterministic digest order; confirmation cannot exceed the selected
cut. Remaining points and future-retention parents still pass the existing
installation ancestry checks.

Bare `mergeRecorded` stays conservative, including renewal debt. It cannot use
an arbitrary decoded manifest to discard an older point. The old-majority joining
seed has a separate private token created only after every source binding and
all original endpoint ancestry checks. It uses the same merge calculation; the
seed remains metadata, not voting, installation or deletion authority.

This is the existing non-Byzantine, exclusive native storage-owner model. A
private token prevents accidental use of an unverified decoded plan; it is not a
signature against a malicious voter. Cold recovery completes the exact retained
selection intent and does not overwrite later local revisions.

## Evidence scope

`V53PeerConfirmationTest` starts from actual public bootstrap, retains an
ambiguous dispatch, publishes cut 2, observes the original complete peer copy,
then performs a third election, publication and cold reopens. The original
implementation fails at the third election's three-point union. The component
suite also checks conservative decoding, renewal bounds, exact manifest bindings,
permanent identity drift, conflicts and repeated-observation idempotence.

The independent Python reader derives bootstrap, three elections, three original
publications and every retained snapshot. The only confirmation is reconstructed
from node 3's independently derived generation. It compares the local confirmation,
frozen sources, selected completion and post-publication ledgers, and checks force
ordering. Original validation precedes every negative mutation. Older generic
replay refuses confirmation/renewal fields rather than silently ignoring them.

The final focused Java group passes **25** tests, including all 13 joining-seed
cases and actual native confirmation, selected completion, reopening and delayed
message paths. The complete independent confirmation replay passes **12** exact
negative mutations, including removal of pre-merge installation ancestry. Native
installation preserves those old obligations through selector replacement even
when the eventual merged ledger no longer needs them; the reader derives those
bytes before verifying later publication. All **924** V5.3 Python tests pass on
the final reader, with an unchanged input hash inventory across the execution;
27 targeted checks and the complete native replay also pass separately.

Intermediate failures are retained. The old implementation fails the new native
regression at its three-point union. A later test draft exposed repeated identical
observation writes and two negative-fixture attempts to mutate immutable maps.
The journal now avoids the redundant update, and mutation fixtures use explicit
copies. Initial replay drafts omitted installed old ancestry or addressed the
generation through the wrong member map; they remain failed reader executions,
not accepted negative evidence. No native workload was repeated to repair them.

The final unchanged competing-owner producer still **fails** (137.245 seconds
including its isolated build). This run does not report the earlier three-point
merge error. Instead node 1 terminates with the typed `higher activation promise`
campaign loss, after bounded recovery; node 2 and node 3 are restarting. Nodes 3
and 2 each completed an earlier startup, but no client DATA completed. The observed
terminal branch and empty suppressed-error list are consistent with exhaustion of
the existing three-round recovery ceiling; the trace does not directly record its
in-memory round counter. All three owners close with zero leases and no cleanup
failure. This is a remaining convergence gate, not grounds to raise retry limits
or treat the producer as passed. Original source, wire and physical diagnostics
remain in the qualification archive.

Execution results, source hashes, original failures and archive identity are in
the [qualification receipt](phase3-evidence/peer-confirmation.json). A focused
history pass is separate from complete automatic competing-owner qualification.
Joining confirmation process cuts, the complete automatic network/history oracle,
remaining profiles and the incoming-maintenance scratch recovery boundary remain
in the [deferred acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).

Rollback must retain decoding of already written confirmations and renewal debt.
Disable new production of these fields rather than erase evidence or start an
older decoder against the changed private files. This is unpublished 1.3 metadata;
no released-format compatibility claim is made.
