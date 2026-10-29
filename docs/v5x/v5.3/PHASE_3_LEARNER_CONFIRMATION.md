# Durable learner confirmation and selected-source discharge

Phase 3 remains **OPEN**. This connects the existing
[read-only head query](PHASE_3_LEARNER_HEAD_PROTOCOL.md) to a durable obligation
update and the existing selected-source installation transaction. It does not
enable joining-voter eligibility, matching INTENT or a public automatic runtime.

The optional `confirmation` field in the private learner plan retains the exact
original QUERY and ACK frames as canonical base64. Both frames bind the complete
original request, root/view, permanent identities, learner correlation ballot,
trace/sequence and the observed cut/catalog/application endpoint. The endpoint
must be the first retained possibility. The requester's identity must be an
original voter at that stable endpoint; both identities must still match the
permanent catalog. An endpoint with the same index but different bytes is refused.
The original source ancestry must authenticate it before local installation and
after recovery/selected installation.

The complete transcript remains bounded by 8 KiB; the plan stays at 16 KiB and
its owner-bound file at 32 KiB. Maximum-length identity fields, counter widths,
five-voter view, two uncertain endpoints and two pending renewals fit these
existing limits (7,765-byte transcript, 14,519-byte plan, 15,146-byte owner file
in the maximum-width fixture). Plans without the new optional fields retain
their exact previous encoding. No public frame or resource
ceiling changes in this batch. A transcript checksum is not a signature or
evidence that a receiver actually observed it.

`retainLearnerConfirmation` therefore accepts only a live `Received` capability
from that exact native owner and resource pool. Its original deadline, operation
and ancestry checks still apply. A decoded transcript has no such entry point.
The existing candidate write, file force, atomic replacement and parent force
complete before returning. The received capability is checked again after the
transaction; failure poisons the old owner and requires ordinary cold recovery.
Pending slots, uninstalled selection and incomplete grants retain their existing
refusal rules. A new trace confirming the same endpoint is idempotent; it does
not rewrite the ledger or advance the revision.

Confirmation removes only older possibilities. Any later unresolved offer stays.
A late older confirmation cannot regress a later point. Existing local-only
observations remain local: advancing beyond a recorded wire confirmation drops
that old transcript rather than inventing a new remote acknowledgment. That new
head must be queried before its progress can discharge another source's frozen
uncertainty.

Local narrowing does **not** immediately stop checkpoint renewal. The first
continuous native execution reproduced a publication failure: node 1 narrowed
`[2,3]` to `[3]` and forced only `1→4` and `3→4` supplemental checkpoints, while
node 2 still needed `2→4`. Its reverse pull could not find node 1's original ACK;
the next publication therefore could not form its checkpoint quorum. Retained
`applied-4` originals establish the differing statement sets; this was a logic
gap, not a deadline or scheduler diagnosis.

The optional private `renewals` array now keeps locally discharged endpoints
as physical checkpoint obligations until selected-source reconciliation. It
holds at most two strictly ordered endpoints below the first remaining
possibility, and is omitted when empty. Both local-only observation and remote
confirmation preserve this debt. `required` authenticates and renews it along
with uncertain points; narrowing never fabricates a missing ACK. A third pending
renewal is refused before installing a new ledger. Existing six-bridge, five
renewed-ancestor and shared-byte admission checks remain in force. Further
narrowing may need a fresh selected-source reconciliation first.

The selected verifier first checks the exact SELECTED sources, each included
PROMISE/BASIS inventory wrapper and the owner-bound original ledger, plus the
actual local predecessor. Only then does its private provenance token permit a
discharge-aware merge. Bare `mergeRecorded` remains conservative. All same-index
conflicts, including pending renewals, are checked before dropping older points.
The highest authenticated
confirmation is retained; equivalent-endpoint transcripts use a deterministic
digest tie-break. A stale `[2,3]` source plus confirmed `[3,4]` can thus become
`[3,4]`, while the same three-point union without verified confirmation remains
refused. Neither the selected pair nor the two-point bound changes.
Without verified confirmation, decoded merge conservatively retains pending
renewals as possibilities. A verified selected merge removes only obligations
strictly below the confirmed endpoint and writes the same reconciled plan to
participating owners; it does not leave one owner requesting an ACK another has
already stopped producing.

The exact transcript travels in frozen source bytes and the selected completion
intent. Installation forces the resulting local ledger before returning an ACK;
cold recovery repeats completion from that same immutable intent. Subsequent
publication may prune obsolete selection metadata but keeps the live confirmed
ledger and its required ancestry. The trust model is still non-Byzantine,
exclusive storage owners on the existing trusted private network. The private
provenance token prevents accidental use of an arbitrary decoded plan; it is not
a cryptographic defense against a malicious voter.

The Python reader understands the new bounded bytes and their bindings. Its
older conservative-history entry explicitly refuses confirmed discharge unless
a dedicated selected-provenance replay is supplied; decoding these files alone
must not turn the old history validator into a new acceptance claim. Complete
independent original-first replay of the new path, actual process-death cuts,
all profiles, repeated refresh and matching locally forced INTENT remain in the
[deferred acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).

The continuous native regression fixes reachability before the first campaign,
then uses actual RESERVE/PREPARE, a typed learner, TCP QUERY/ACK, durable local
narrowing, a later publication, a fresh campaign with the stale source, CANCEL
and two cold reopens. It preserves the initial failed execution rather than
swapping selected voters or weakening the publication requirement. The repaired
history completes in approximately 480 seconds. Its recorded bytes and wire
correlation are component diagnostics; the complete independent original-first
learner/publication replay and real process-death matrix are still pending.

The final conditional checks additionally cover renewal capacity/refusal,
conservative decoded merge, malformed transcripts, idempotence and late replies.
The native/observation group passes 13 cases; the final conditional/format group
passes 15 (19 distinct Java cases across those overlapping groups). Production
classes are byte-identical between both snapshots. All 831 Python tests pass,
including maximum-width private-plan and malformed renewal cases. The [source-bound component receipt](phase3-evidence/learner-confirmation.json)
retains the original failure, successful native history, exact code/test inputs,
JUnit results and archive hash; it is not full Phase 3 acceptance.

Rollback must preserve the new decoder for already written confirmation and
pending-renewal files.
Disable new confirmation production rather than run an older rejecting decoder
or erase the field from retained evidence. The format is still unpublished 1.3;
no released-version compatibility claim is made.
