# Phase 3 — original nonvoting learner storage

Status: implementation and focused component checks complete. Complete Phase 3,
typed readiness and joint eligibility remain **OPEN**. Long final-source matrices
are tracked in the [deferred acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).

## Durable admission

The [original admission plan](PHASE_3_LEARNER_PLAN.md) now feeds a real private
nonvoting store. The received directory is completed from its original generation,
with metadata growth reserved before writes. All original metadata is forced,
including existing exact bytes after an interrupted write. The one LEARNER lease
and original image leases move with their exact inode handles; admission does not
reserve another physical copy.

The operation owner forces the [A15 retention decision](PHASE_3_CONTRACT_AMENDMENTS.md#a15--original-nonvoting-learner-source-retention)
before creating replica metadata. It exclusively owns the joining identity's
root/node files, moves the exact original directory atomically and forces both
parents before forcing the admission marker. Cross-filesystem copy fallback is
not supported. Closing the owner preserves retained originals and releases all
process-local locks/reservations. Original source-voter records remain historical
evidence, never local learner promises or votes.

Reopen requires exactly one original source location, complete original hashes
and inode bindings, the original operation/parent bindings and exclusive owners.
Partial local root/node/admission files can be completed only as exact prefixes
of the persisted original decision. Foreign files, replaced objects or incomplete
retention decisions are preserved and refused. Validation precedes any resealing
or removal of redundant decision files. A completed admission marker permits its
old staging parent to disappear; an incomplete move does not.

## Preparing the retained image

`MembershipLearnerPreparation` selects the exact image of an original PREPARING
revision under the live nonvoting store. It binds the full operation request,
joining identity, expected configuration, revision and original packet. RESERVED,
READY and SEALED records cannot create a new preparation through this entry. A
closed/replaced owner invalidates already obtained preparation objects.

The captured builder, root schema/codec/startup-index descriptor and local
root/identity/replica paths are checked before future typed writes. This input
binding does not semantically decode an application, force LEARNER or imply that
a remote peer has not advanced or cancelled the operation. The later typed owner
must decode the exact image, persist its readiness and obtain a matching current
certified suffix. In particular it must not replace the prepared image with a
later DATA application's image merely because that is the terminal catalog value.

## Qualification boundaries

Component tests cover the five joining shapes, pre-joint states, exact original
inodes, every local retention/install interruption, bounded accounting, unchanged
foreign refusals, closed ownership and preparation/configuration mismatches.
Their explicitly conditional historical forces do not establish network quorum
evidence. Native tests instead bootstrap actual voters, certify RESERVE, acquire
the complete original over TCP and use fresh JVMs for halt/SIGKILL and recovery.
Independent readers validate original source history before exact retained bytes,
force traces, exit results and negative mutations. Portable readers never open
absolute paths recorded inside a retained original plan.

The test's default process matrix remains twelve complete histories. Its optional
case selector enables later hosted parallel execution without shortening any
history. Single-case replay reports PARTIAL; final source/build-bound aggregation
and the remaining Phase 3 audit are still required.

## Retained results

The [receipt](phase3-evidence/learner-store.json) binds the complete archive and
24,910 checked files. The final runtime passes 19 Java methods (14 store and five
preparation-input tests). A preceding immutable review passes 59 Java methods and
756 Python tests; the twelve current reader unit tests pass separately. Counts
from different snapshots are not summed as final-source acceptance.

The already-running native matrix completed twelve independent histories and 24
fresh processes, including six live-lock refusals. Original and relocated optimized
replay each reject all twelve exact mutations. That build predates the guarded
preflight/re-force corrections and preparation-input additions. An additional
native installation/reopen smoke exercises the storage corrections, with eight
portable exact negative cases; it predates the read-only preparation accessor.
All production differences, source inventories and compiled-class hashes are
retained. The final-source complete process matrix remains deferred, not passed.

Earlier failures are retained: a component fixture omitted its cut callback, a
native snapshot used filenames as restricted JSON object keys, and the review
reader expected name rejection instead of the earlier five-member inventory
limit. The last correction keeps exact error matching; unrelated rejection cannot
count as valid evidence. No production retry hides these failures.

From the archive's `readers/` directory, replay with:

```bash
python3 -O -m scripts.v53.learner_store_evidence ../raw-nativesecond --qualify
python3 -O -m scripts.v53.learner_store_review_evidence ../raw-finalnative --qualify
```

## Remaining work

Transfer the retained nonvoting source into a bounded prepared-generation owner;
reacquire certified successor preparations without accumulating an extra learner
slot; perform typed materialization and force the original LEARNER receipt. Bind
READY delivery, metadata catch-up and locally forced matching INTENT before joint
votes. Complete all seven transitions, alternative-leader takeover, automatic
continuation and combined maximum headroom. Public factories remain disabled.
