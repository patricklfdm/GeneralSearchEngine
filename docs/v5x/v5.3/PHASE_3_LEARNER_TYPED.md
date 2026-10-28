# Phase 3 — typed learner image and forced receipt

The private `MembershipLearnerMaterialization` owner consumes an exact original
PREPARING revision from the [nonvoting learner store](PHASE_3_LEARNER_STORE.md).
It validates the captured schema, codec, startup indexes and local configuration,
then decodes the original image with the core's actual typed backup reader. Only
after successful decoding and image/history validation does it force the frozen
GSER LEARNER record and its directory. The returned receipt is bound to this live
owner; closing the parent closes the child and revokes receipt access.

This prepares a bounded backup and a decoded application state. It does not open
the live core directory, allocate a ballot, create a local voting journal or grant
joint eligibility. A historical PREPARING source may have been superseded remotely.
The next lifecycle work must validate current certified successors and a locally
forced matching INTENT before votes can be admitted.

## Original recovery and accounting

The [A16 contract](PHASE_3_CONTRACT_AMENDMENTS.md#a16--typed-learner-backup-and-forced-readiness-record)
places the private sidecar at a deterministic sibling of the operation directory,
bound to the original plan digest. Its locked, forced canonical plan records the
source packet, exact receipt, captured configuration, materialization path and
original sidecar directory identity. It holds only this plan/candidate, three
backup members, an empty lock and the LEARNER record.

A complete original candidate can be forced and sealed after interruption. A
missing or partial plan is preserved and refused, without reconstructing a new
decision from caller arguments. Under the original complete plan, partial backup
members and receipt may be completed only as exact prefixes of their original
bytes. Reopen repeats semantic decoding even when the original receipt is already
complete. Unknown members, hard links, changed bytes/configuration, a replaced
directory, or changes during a live ownership interval are refused.

The parent reserves one additional APPLICATION slot at the existing 64 MiB limit
before any sidecar writes. Child close or failure retains that reservation because
the backup remains on disk. Parent reopen also accounts for an existing sidecar
before completing writes. Closing the parent releases its process reservations;
it does not erase retained originals. No capacity or timing limit is increased.

The 2 MiB MISC reservation covers both 64 KiB admission-plan files, three 256 KiB
retention/admission copies, ROOT (16 KiB), NODE (4 KiB), two 256 KiB typed plans
and LEARNER (16 KiB): at most 1,444 KiB. Backup bytes use the separate APPLICATION
slot. Combined maximum headroom and eventual source/sidecar retirement remain
required lifecycle work, not an assertion of unbounded repeated preparations.

## Qualification and remaining work

Focused component coverage includes all five joining shapes, eleven write/force
interruption positions, changed originals, semantic identity mismatch, simultaneous
owners, parent-close revocation and retained image accounting. Historical voter
forces in these fixtures remain explicitly conditional.

The native smoke starts real voters over TCP, certifies RESERVE and PREPARE,
receives and admits the original source, performs actual core decoding, forces the
receipt, closes/reopens the learner, and explicitly proposes READY with those exact
receipt bytes. Its independent reader derives the original physical history and
checks network acquisition, retained bytes, force order and READY binding. This
does not exercise an autonomous READY sender or a new leader taking over.

The new five-slot smoke declares one 600-second test deadline before starting.
Its first run inherited the older two-slot helper's 180 seconds and expired during
READY after typed reopen; that failed history is retained. The production deadline
mechanism, individual RPC limits and retry counts are unchanged; the deadline is
never restarted within either history. This is not a latency/SLA qualification.

Long process-death matrices and final-source acceptance stay in the
[deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md). Current results and source/build
identities are recorded in [the retained receipt](phase3-evidence/learner-typed.json).
Next: prepared-generation ownership, bounded refreshed-source acquisition,
revision/cancellation handling, matching INTENT, all seven transitions and the
complete Phase 3 audit. Public factories remain disabled.

## Retained focused results

Fourteen Java component methods and one complete TCP history pass against
identical production inputs. The native history takes 277.9 seconds (291 seconds
including compilation), with 31 received exchanges and nine original source files.
Independent original replay rejects all nine exact mutations; portable optimized
replay is also retained. Seventeen related Python tests and the documentation
contract pass. The earlier store/preparation regression run passes nineteen
additional methods on the preceding snapshot; its only production difference is
removal of an unused local variable in the shared image reader. Those results
retain their separate source identity rather than being pooled as one run.

Both failed attempts remain in the archive: a component test expected a different
exception type even though the changed descriptor was correctly refused without
writes, and the first longer native history exhausted the inherited 180-second
budget. Neither was discarded or converted into a passing run. Full process-death,
all-transition and maximum-headroom acceptance remain outstanding.
