# Bounded local learner-source retention

This is the local storage/publication part of the
[native cancellation correction](PHASE_3_LEARNER_CANCELLATION_NATIVE.md).
Phase 3 remains **OPEN**. It does not yet enable a replicated learner export,
alternative-leader recovery or successful complete cancellation qualification.

## Local obligation

`MembershipLearnerRetentionPlan` binds one exact root, complete original ADD or
REPLACE request and joining storage identity to at most two unresolved source
endpoints. Each endpoint includes the complete cut, catalog and application
hashes. Enrollment derives the request from the verified active reservation;
the endpoint is the exported terminal, not the catalog's pre-PREPARE cut.

Repeated offers of the same endpoint do not advance the durable revision.
Conservative merge retains both old/new possibilities even when another source
claims only the newer point or no obligation. Conflicting requests/identities,
same-index different bytes and a third unresolved point are refused. Decoding
or merging metadata is not authority: the actual capsule must independently
prove every endpoint. There is deliberately no narrowing/clearing API yet;
only a future exact forced learner-head confirmation may authorize that step.

## Storage and publication

The private `learner-retention.gslr` and `learner-retention.next.gslr` files use
bounded canonical state, root/owner binding, a revision and predecessor digest.
The 16 KiB plan and each 32 KiB container stay inside the existing shared
32 MiB journal reservation; active and candidate bytes both count. No public
record, wire kind, image count, bridge limit or frozen resource limit changes.

Initialization is explicit at unused native genesis. The required
`openRetainingLearners` entry refuses a missing ledger after authority advances.
Legacy component opens remain available and are not substitutes for this entry.
The existing exclusive owner checks the original file identity and bytes.
Updates force a candidate, replace the active file and force its parent before
returning. Recovery discards only unexposed candidates and re-forces the selected
active record. Corrupt/foreign/replaced originals fail closed; a failed owner
cannot continue using a pre-failure handle.

`MembershipGrantJournal` includes these obligations in publication admission,
ancestor renewal, reopen checks and incoming-adoption ancestry validation.
Pending-slot/staged-application boundaries prevent a new obligation from changing
an already planned publication. RETIRE cannot erase the operation while its
learner obligation is unresolved; refusal precedes ACCEPT and reports
`CAPACITY_EXCEEDED / NOT_SUBMITTED` for a fresh request.

## Deliberate integration boundary

A local force is not an old-view quorum. Unguarded learner prefix export still
refuses in this mode. The subsequent [frozen-source/selected merge component](PHASE_3_LEARNER_RETENTION_SELECTION.md)
now permits PREPARE and selected installation with exact captured obligations;
missing snapshots and mixed legacy/new owners are refused before selection.
Existing legacy learner fixtures do not opt into this mode, and the original
failed native cancellation entry remains unmodified. No test-only local ledger
is presented as a repaired end-to-end run.

The subsequent [native quorum recording](PHASE_3_LEARNER_RETENTION_QUORUM.md)
provides dedicated forced ACKs. [Protected source serving](PHASE_3_LEARNER_RETENTION_SERVING.md)
now consumes that exact live recording before source exposure. Remaining work must
bind narrowing to an actual forced learner head, retain both possibilities after
lost ACKs, and preserve the obligation through PREPARE replacement, READY,
CANCEL and matching locally forced INTENT. These steps precede automatic/public
runtime activation.

## Validation scope

Focused tests cover all five joining profiles as conditional pure projections,
metadata rejection/union, actual native local publication and restart, shared
journal refusal, seven initialization I/O cuts, and update interruption before
and after active replacement. The native sequence is BARRIER, RESERVE, PREPARE,
BARRIER, CANCEL with the original endpoints 3 and 4 retained at terminal 5. It
uses actual admitted voters and native journal history; it is a local storage
component test, without a network learner or independent Python acceptance.

The [source-bound receipt](phase3-evidence/learner-retention-local.json) accepts
32 distinct tests: 12 new local-plan/storage cases and 20 existing peer/source
regressions. The accepted class reports span two snapshots whose 881 production
class files are byte-identical; 1,272 code/build inputs match the final snapshot.
Only two test sources changed between those reports. One new fixture incorrectly
used the forbidden RETIRE through=0 value; it now checks that rejection explicitly.
The existing peer storage test incorrectly expected missing caller-supplied
ancestry to fail even with authentic local inheritance. Its identical failure
was reproduced on unchanged `41066966`; the corrected case requires failure
when both proof sources are absent and successful idempotent installation when
the original local proof exists. Runtime ancestry checks were not relaxed.

Original failed runs, successful class reports, source fingerprints and local
physical snapshots remain in the 4,465,337-byte archive named by the receipt.
Fresh-process halt/SIGKILL, original-first physical
and wire replay, complete READY/CANCEL learner recovery, maximum combined
resources and all profiles remain in the
[deferred hosted queue](PHASE_3_DEFERRED_ACCEPTANCE.md). A continuous history must
remain on one runner; independent histories may run in parallel.
