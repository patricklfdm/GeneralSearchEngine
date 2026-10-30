# Phase 3B — selector-coupled retention merge

Later [complete-copy confirmations](PHASE_3_PEER_CONFIRMATION.md) add a verified
original-source discharge path. Bare decoded unions remain conservative; a
revision or cut claim still cannot erase uncertainty. The evidence below records
the earlier union-only component, not the subsequent confirmation qualification.

Status: **LOCAL COMPONENT QUALIFICATION**. The
[source-bound receipt](phase3-evidence/selected-retention.json) records the build
snapshots, native process evidence and independent replay. This extends the
[original-source snapshot](PHASE_3_PEER_RETENTION_SOURCE.md) and
[native local ledger](PHASE_3_PEER_RETENTION_STORAGE.md). It is not a quorum
dispatch permit, automatic peer maintenance or complete Phase 3 acceptance.

## Recovery boundary

A receiver must preserve the union of every selected source's possible peer
endpoints, together with its own current local ledger. Installing the generation
and then independently updating the ledger would leave a crash interval in which
the new selection survives but the inherited obligations do not.

The selected source packet therefore contains one private `GSRS` recovery object
for the receiver. It binds the exact SELECTED bytes, permanent local identity,
pre-install local GSPR bytes, and the original BASIS/envelope/GSRP bytes for every
selected source. Each inventory proves inclusion of its exact frozen snapshot;
the selected references prove the fixed source order, ballot, root and quorum.
Those structural bindings do not manufacture new force observations. The native
selection and history checks still establish the original sources' authority.

The merge is conservative: each identity retains the union of possible endpoints.
A larger claimed revision or cut cannot erase an older source's uncertainty.
Conflicting equal-index endpoints, changed permanent identities or more than two
possible endpoints per peer refuse. Every resulting anchor must be authenticated
against the installed capsule and its original ancestry before installation.

After the selector is installed, the native owner completes any required ledger
update before returning installation success. Opening that owner after a crash
performs the same completion before exposing it. The original local revision and
digest determine the exact successor; identical plans need no new revision. An
exact completed revision is checked by digest. Later native revisions are already
past this completion boundary and must not be overwritten, because a real peer
observation may have narrowed the uncertainty since installation. This relies on
the existing exclusive native owner and monotonic ledger updates, not arbitrary
external file replacement.

## Bounds and lifetime

The GSRS object uses a 48-byte checksum header, bounded identity/selection/ledger
parts, and at most six original source rows. It retains source envelopes and the
one included GSRP object from each source, not six complete source packets. Its
maximum size remains below the existing 8 MiB per-object limit and counts toward
the existing 32 MiB packet/generation limits. Ledger completion shares the existing
JOURNAL reservation and is admitted before SELECTED and before installation.
No frozen resource ceiling, wire record kind or generation filename is added.

The selected generation remains sufficient after obsolete original sources are
retired. A subsequent certified publication can drop this recovery object because
ledger completion precedes publication. The active local ledger retains the union.
Existing pending-context envelopes still require their exact retained objects;
this change does not grant new permission to remove them. Repeated unresolved
campaigns may reach the existing bounded packet or ancestry ceilings; autonomous
maintenance must address that lifecycle rather than silently increasing limits.

## Qualification scope

Native Java tests cover missing selected snapshots, altered included bytes,
conservative union, exact installation retries, source retirement, later real-copy
narrowing, repeated reopen and subsequent publication. A one-byte-short completion
budget refuses before any SELECTED write and preserves every original file. An actual three-voter EMPTY
bootstrap, first activation and BARRIER publication form the shared prelude for
sixteen halt/SIGKILL cases: generation force, selector rename, parent force, ledger
partial write, ledger force, ledger rename, ledger parent force and completion.
Each process case uses a fresh child, retains the interrupted tree and reopens in
another child. Live SIGKILL cases also probe the actual native file lock.

The Python validator independently derives the bootstrap, first campaign,
publication, next frozen source packets, selected GSRS bytes, merged ledger and
every interrupted/recovered file map. Only fresh capture UUIDs are observed; ready
snapshots and Java PASS fields are checked against derived state. Original evidence
must pass before mutations are attempted. Normal, optimized and relocated replay
all agree: sixteen process cases and twelve exact evidence mutations. Thirteen
Python tests pass in both modes. The main isolated Java build passes sixteen tests;
a later snapshot runs the additional capacity regression. The preceding snapshot
passes seven tests, including five original-source regressions, against identical
production bytes. The receipt distinguishes overlapping tests and snapshots.
The real-copy narrowing/publication scenario has separate Java assertions; it is
not part of this new independent crash-prelude replay. This finite process matrix does not claim power-loss testing or
full distributed lifecycle qualification.

Quorum recording before dispatch, automatic observation/maintenance, a complete
offline-survivor continuation, native cross-view pending contexts and the remaining
3B–3E gates remain open. Public membership remains disabled.
