# V5.3 — controlled cluster operations

**Status:** local development branch, started 2026-10-21. Phases 0 and 1 are locally closed;
no V5.3 runtime, release, protected CI or cloud acceptance is claimed.

The operator authorized development on `feat/v53-cluster-operations` while V5.2
cloud qualification continues, with local commits and no push. The branch starts
at `73f3bd5c21c97eee564397ab11af7b66bc1b13a3`. V5.2 is still an unpublished
development predecessor; its eventual published artifacts are not yet pinned.

## Frozen local contract

- [Phase 0 contract](PHASE_0_CONTRACT.md) and [protocol](MEMBERSHIP_PROTOCOL.md)
- [API/bytes/compatibility](API_FORMAT_AND_COMPATIBILITY.md) and [resource limits](RESOURCE_AND_LIFETIME_LIMITS.md)
- [Acceptance register](ACCEPTANCE_REGISTER.md), [checklist](PHASE_0_CHECKLIST.md), [Phase 1 entry](PHASE_1_ENTRY_PLAN.md)

[Closure audit and evidence](PHASE_0_CLOSURE_AUDIT.md) record 198 tests and all nine
research matrices on the final script bytes. The [Phase 1 closure audit](PHASE_1_CLOSURE_AUDIT.md)
records current compatibility, byte, source-selection and complete causal-model
qualification. The new membership runtime remains disabled. [Phase 2 storage](PHASE_2_ENTRY_PLAN.md)
is open, with [private durable allocation and exclusive ownership](PHASE_2_STORAGE_FOUNDATION.md)
and the [promise/original-basis metadata journal](PHASE_2_GRANT_JOURNAL.md), now with
[physical original-source retention](PHASE_2_BASIS_SOURCES.md) and
[current local generation capture](PHASE_2_CURRENT_GENERATION.md), followed by
[durable original selection](PHASE_2_DURABLE_SELECTION.md).
[Selected local installation](PHASE_2_GENERATION_INSTALL.md) now preserves the original
source decision across generation/selector writes and interrupted recovery. Its
174-case local process gate passes. The [adoption fence](PHASE_2_ADOPTION_FENCE.md)
now passes 66 cases. [Integrated local adoption](PHASE_2_ADOPTION_INSTALL.md) passes
234 cases with forced prefix/selector recovery and obsolete-view refusal.
[One retained governing floor](PHASE_2_GOVERNING_FLOOR.md) now passes 315 cases,
with complete original copies and old/joint/new majorities. [Inactive-generation
retirement](PHASE_2_RETIREMENT.md) passes 549 cases, including interrupted deletion
and recovery. [Exact journal compaction](PHASE_2_JOURNAL_ROTATION.md) passes
135 cases while preserving all retained sources. [Old floor-copy release](PHASE_2_FLOOR_RELEASE.md)
passes 261 cases and returns its reservations before another complete floor. Actual
application publication and complete original-source lifetime progress remain open.
[Automatic journal backpressure](PHASE_2_JOURNAL_BACKPRESSURE.md) now attempts one
safe compaction before refusing an exhausted admission.
[Original-source retirement planning](PHASE_2_SOURCE_RETIREMENT_PLAN.md) now checks
exact floor/selector/ancestry and retained tail ownership.
[Completed original-source retirement](PHASE_2_SOURCE_RELEASE.md) now passes 297
crash/recovery cases. [Covered capture-only retirement](PHASE_2_CAPTURED_SOURCE_RELEASE.md)
and [current-pinned partial capture recovery](PHASE_2_CAPTURE_RECOVERY.md) now pass;
[Exact torn BASIS recovery](PHASE_2_CAPTURE_JOURNAL_RECOVERY.md) also passes;
[unmarked/torn PROMISE boundaries](PHASE_2_PROMISE_BOUNDARIES.md) now have process
qualification for retained fences and unchanged-byte refusal;
maximal image headroom and complete offline recovery remain open. The [pre-cloud checklist](PRE_CLOUD_CLOSURE_CHECKLIST.md) tracks the
expanded continuous local development scope.

[Original pending ACCEPT](PHASE_2_PENDING_ACCEPT.md) now passes 42 process cases,
including exact reaccept/recovery and fresh-grant capture. [Original pending PROOF](PHASE_2_PENDING_PROOF.md)
now passes 45 process scenarios with actual local voter ACCEPTs, repeated recovery
and source capture. [Pending certificate](PHASE_2_PENDING_CERTIFICATE.md) now passes
45 scenarios over actual ACCEPT/PROOF quorums. [Complete application images](PHASE_2_APPLICATION_IMAGE.md) now preserve
actual core backup state with deterministic administrative metadata. [Private application replay](PHASE_2_APPLICATION_REPLAY.md)
now preserves exact results across intermediate recovery cuts. [Exact catalog projection](PHASE_2_CATALOG_PROJECTION.md)
now covers every control transition and binds READY to the prepared image.
[Certified checkpoint construction](PHASE_2_CHECKPOINT_EXTENSION.md) now preserves explicit membership edges
and requires new exact range endorsements. [Applied-end/ACK storage](PHASE_2_APPLIED_END.md)
now forces the exact image/catalog before its local ACK. [Actual journal application](PHASE_2_JOURNAL_APPLICATION.md)
connects original local certificates, typed replay, bounded scratch recovery and guarded ACKs.
[Complete generation materialization](PHASE_2_PUBLISHED_GENERATION.md) now preserves the original selected
parent and certified first slot through component installation/reopen.
[Actual journal publication](PHASE_2_JOURNAL_PUBLICATION.md) connects the forced selector to exact covered
vote/end cleanup and interrupted recovery. [Actual parent checkpoint ACKs](PHASE_2_PARENT_CHECKPOINT.md)
now preserve the immediate original parent hidden by a compacted RANGE.
[Bounded ancestor renewal](PHASE_2_ANCESTOR_RENEWAL.md) also preserves earlier
authenticated BASIS/floor endpoints through the new forced end.
[Publication admission](PHASE_2_PUBLICATION_ADMISSION.md) checks ancestry groups and
coverage bytes before accepting new work. [Original selected-source retention](PHASE_2_SELECTED_SOURCES.md)
now enables omission of unreferenced ancestry from the next generation while preserving
the old bytes. Staged applications pin their references, and new votes reserve
the publication image as well as replay/end space. [Dedicated six-to-one pruning](PHASE_2_ANCESTRY_PRUNING.md)
now passes ten repeated-crash cases with independent portable replay.
[Repeated publication and source/floor maintenance](PHASE_2_PUBLICATION_LIFETIME.md)
now preserves supplemental installation ancestry through twelve fresh ballots and
reclaims obsolete copies. [Coordinated maintenance process recovery](PHASE_2_MAINTENANCE_LIFETIME.md)
adds original-request replay across installation, floor, generation/source retirement
and floor release. Complete lifetime crash/cross-view qualification and maximal
resource lifetime remain pending. [Bounded same-round proof continuity](PHASE_2_ROUND_COVERAGE.md)
now connects to [actual next-slot storage voting/publication](PHASE_2_ROUND_STORAGE.md),
retaining original decisions, first/current proofs and exact covered-cleanup recovery.
[Same-round process qualification](PHASE_2_ROUND_PROCESS.md) now covers actual
phased votes, application/ancestor ACKs, selector switching and covered cleanup
across 22 repeated-crash cases. Public runtime and complete cross-view/maximal
lifetime qualification remain pending. [Carried first-entry publication](PHASE_2_CARRIED_PUBLICATION.md)
now preserves the earlier vote's original round through new-ballot installation,
reacceptance, bounded maintenance and same-round continuation.
[Carried maintenance process recovery](PHASE_2_CARRIED_PROCESS.md) now exercises
22 repeated-crash cases with original-first physical replay.
[Fenced application staging handoff](PHASE_2_STAGED_HANDOFF.md) adds explicit
derived-work retirement under a newer installed selection; its local qualification
is tracked separately from the remaining repeated-campaign and maximal-lifetime work.

The [Phase 2 closure checklist](PHASE_2_CLOSURE_CHECKLIST.md) tracks integrated
storage work and the final requirement-by-requirement audit.

## Historical research in order

1. [Local development and integration rules](LOCAL_DEVELOPMENT_SEQUENCE.md)
2. [Phase 0 entry and actual source audit](PHASE_0_ENTRY_PLAN.md)
3. [Membership design decisions and open protocol obligations](MEMBERSHIP_DESIGN.md)
4. [Durable ballot research and handoff boundary](BALLOT_AND_HANDOFF_RESEARCH.md)
5. [Predecessor-certified transition research](TRANSITION_CHAIN_RESEARCH.md)
6. [Checkpoint, floor and retention research](RECOVERY_AND_RETENTION_RESEARCH.md)
7. [Global promise, recovery selection and activation](GLOBAL_PROMISE_AND_ACTIVATION_RESEARCH.md)
8. [Authority retention and learner identity](AUTHORITY_AND_LEARNER_RESEARCH.md)
9. [Queryable operations and maintenance](OPERATION_AND_MAINTENANCE.md)
10. [Certified operations and learner admission](INTEGRATED_PROTOCOL_RESEARCH.md)
11. [Stable rounds and complete catalog capsules](STEADY_ROUNDS_AND_CATALOG.md)
12. [Phase 0 closure worklist](PHASE_0_CLOSURE_PLAN.md)
13. [Independent model and later evidence requirements](TESTING_AND_EVIDENCE.md)
14. [Development status](DEVELOPMENT_STATUS.md)

The accepted [V5 charter](../DEVELOPMENT_CHARTER.md) and the V5.3 section of the
[development addendum](../NEXT_DEVELOPMENT_ADDENDUM.md#v53-controlled-operations)
define the direction: non-voting catch-up, controlled membership, restartable
operations and same-version maintenance. Search semantics remain inherited from
published V4.4; automatic leadership and explicit read guarantees remain inherited
from their version-specific contracts. This directory does not amend V5.2 evidence.

## Run the lightweight local research checks

```bash
python3 -m unittest discover -s scripts/v53 -t . -p 'test_*.py'
python3 -m scripts.v53.membership_model \
  --output "target/v53-membership-model/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.ballot_research \
  --output "target/v53-ballot-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.transition_research \
  --output "target/v53-transition-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.recovery_research \
  --output "target/v53-recovery-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.activation_research \
  --output "target/v53-activation-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.admission_research \
  --output "target/v53-admission-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.operation_research \
  --output "target/v53-operation-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.integrated_research \
  --output "target/v53-integrated-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

The additional composition driver is `python3 -m scripts.v53.continuity_research --output <new-directory>`.

Run from the repository root. The output directory must be new. These commands
need no Maven build, sudo, network, cloud credentials or running GSE processes.
They check the declared finite model only. See the retained
[research receipt](membership-research.json) and [coverage limits](TESTING_AND_EVIDENCE.md).

[Capture-only source retirement](PHASE_2_CAPTURED_SOURCE_RELEASE.md) adds recovery
for complete packet/image captures without BASIS under a strictly later full floor;
same-cut/partial capture and maximal coordinated resource progress remain open.

The [bounded pending-context component](PHASE_2_PENDING_CONTEXT.md) reconstructs
exact old generation/vote bytes from a retained source. Owner persistence, repeated
higher-ballot recovery and all-voter-count lifetime integration remain open.

[Pending-context persistence](PHASE_2_PENDING_CONTEXT_FILES.md) adds bounded
candidate/active files and 32 repeated-crash component cases. Complete journal
owner integration and repeated 3/4/5-voter lifetime recovery remain open.

[Inactive retirement using retained floor images](PHASE_2_RETIREMENT_IMAGES.md)
reuses exact pinned floor bytes when a full backup would need an eighth image.
It retains the existing seven-image/six-source bounds and qualifies 53 fresh-process
cases; arbitrary pending-context/source turnover remains open.

[Typed bootstrap revalidation](PHASE_2_BOOTSTRAP_REVALIDATION.md) now connects actual
source/configuration reads and all-target image exports to both private transaction
boundaries. Public admission, bounded scratch recovery and complete-store opening
remain Phase 2 obligations.

[Bounded read-only bootstrap rechecks](PHASE_2_BOOTSTRAP_RECHECK.md) reuse the original
planning exports through repeated checks and PREPARED recovery, preserving actual
typed validation without accumulating new scratch directories.

The [private bootstrap coordinator](PHASE_2_BOOTSTRAP_COORDINATOR.md) connects one
retained random history, a fixed bounded projection and exact typed plan/apply/resume.
Public admission and result reading after mutable runtime progress remain open.

[Bootstrap metadata inspection](PHASE_2_BOOTSTRAP_METADATA.md) now shares the initial
- [Original bootstrap commit metadata](PHASE_2_BOOTSTRAP_COMMIT_METADATA.md): exact receipt/decision/seal derivation and completion accounting without application bytes.
- [Compact original admission data](PHASE_2_BOOTSTRAP_ADMISSION_DATA.md): bounded receipt/decision decoding against original local preparation and seal.
- [Admission-file publication](PHASE_2_BOOTSTRAP_ADMISSION_FILES.md): force all compact admission files before seals; exact interrupted recovery and refusal of lost admitted authority.
- [Admission process recovery](PHASE_2_BOOTSTRAP_ADMISSION_PROCESS.md): 42 repeated halt/SIGKILL cases and 126 fresh workers for the private admission-file profile.
layout encoder with actual seed creation and verifies original plan metadata without
requiring application bytes. It remains separate from typed/committed admission.

- [Admitted initial-voter store](PHASE_2_BOOTSTRAP_STORE_ADMISSION.md): exact immutable admission before allocator recovery, actual grant/reopen across all six size/source profiles, and unchanged original records.

- [Typed admitted coordinator](PHASE_2_BOOTSTRAP_ADMITTED_COORDINATOR.md): real typed rechecks reserve compact admissions and retained projection together, then open all 24 initial voters.

- [Immutable bootstrap result](PHASE_2_BOOTSTRAP_RESULT_READER.md): read original commit after real local progress while preserving live node locks; current runtime integrity remains a separate owner check.

- [Progressed partial-group resume](PHASE_2_BOOTSTRAP_PROGRESS_RESUME.md): finish unsealed nodes while preserving completed live voters, exact original authority and exclusive unsealed ownership.

- [Typed bootstrap process recovery](PHASE_2_BOOTSTRAP_TYPED_PROCESS.md): 72 twice-interrupted halt/SIGKILL cases across all six profiles, including live completed voters and 264 child processes.

- [Public offline bootstrap](PHASE_2_PUBLIC_BOOTSTRAP.md): typed plan/apply/resume and immutable result inspection; online membership and learner admission remain disabled.

- [Context-backed source retirement](PHASE_2_CONTEXT_SOURCE_RELEASE.md): exact predecessor reclamation with the original vote and separate backing preserved; full transferred lifetime remains open.

- [Context-backed acceptance](PHASE_2_CONTEXT_ACCEPTANCE.md): force the exact successor, retire redundant context/floor, and reserve completion space before ACK.

- [Three-owner context publication](PHASE_2_CONTEXT_PUBLICATION.md): actual new proof, typed apply-once, two publications per owner and a fresh grant after context/source reclamation.

- [Context completion process recovery](PHASE_2_CONTEXT_COMPLETION_PROCESS.md): source/context/floor handoff across 86 repeated-death cases, with independent physical replay.

- [Retained context under a later durable promise](PHASE_2_CONTEXT_DURABLE_FENCE.md): distinguish exact backing, installed selection and latest promise during recovery; protected capture is covered by the later gate below.

- [Deferred capture inventory](PHASE_2_CAPTURE_INVENTORY.md): reserve complete backing sources before resolving an exact pending capture; the following protected-capture gate integrates context PREPARE/rebind.

- [Protected context capture](PHASE_2_CONTEXT_CAPTURE.md): actual source/BASIS/context force before a fresh local grant, exact repeated-interruption recovery and bounded capture refusal; later selected installation remains open.

- [Intermediate context backing retirement](PHASE_2_CONTEXT_BACKING_RETIREMENT.md): repeated protected capture and exact obsolete-source deletion within seven peak/six steady image reservations.

- [Protected capture/reclamation process recovery](PHASE_2_CONTEXT_CAPTURE_PROCESS.md): 100 twice-interrupted halt/SIGKILL cases and a subsequent exact fresh capture with fixed original authority.

- [Protected immutable selection](PHASE_2_CONTEXT_SELECTION.md): actual three-owner selected sets, unchanged original voting context and exact intermediate grant reclamation; later installation remains open.

- [Context-backed selected installation](PHASE_2_CONTEXT_INSTALLATION.md): reuse generation slots under exact original context/floor protection, retire the intermediate generation and force the original entry under the new ballot.

- [Repeated context installation and reclamation](PHASE_2_CONTEXT_INSTALLATION_LIFETIME.md): six actual three-owner installations preserve the old vote/floor while reclaiming obsolete sources within the frozen image limit.

- [Publication after repeated protected installation](PHASE_2_CONTEXT_INSTALLED_PUBLICATION.md): actual ballot-27 proof, typed apply-once, publication, obsolete-source cleanup, BARRIER continuation and an empty-tail ballot-28 grant.

- [Installed source process recovery](PHASE_2_CONTEXT_INSTALLED_SOURCE_PROCESS.md): 30 repeated-death cases across obsolete source reclamation and exact successor acceptance; Phase 2 remains open.

- [Context generation process recovery](PHASE_2_CONTEXT_GENERATION_PROCESS.md): selected slot reuse and intermediate retirement through repeated halt/SIGKILL, with original authority and force-order replay.

- [Mixed retained ACCEPT ballots](PHASE_2_CONTEXT_MIXED_ACCEPTANCE.md): preserve exact original votes while installing a higher acceptance of the same ENTRY, reclaim obsolete sources and publish once.

- [Mixed ACCEPT process recovery](PHASE_2_CONTEXT_MIXED_PROCESS.md): 84 repeated-death cases preserve exact original votes through successor acceptance and obsolete source reclamation.

- [Admitted bootstrap through publication](PHASE_2_BOOTSTRAP_PUBLICATION.md): six actual public bootstrap profiles, 24 voters and 72 node publications with exact original authority and independent physical replay.

- [Distinct minority ENTRY under a newer selection](PHASE_2_DISTINCT_MINORITY.md): actual admitted same-parent replacement, publication and source reclamation; covered-prefix and crash recovery remain open.

- [Covered bare minority vote recovery](PHASE_2_COVERED_MINORITY.md): exact advanced selector/source authority and bounded vote clearing; process/cross-view qualification remains open.

[Covered-minority physical/process recovery](PHASE_2_COVERED_MINORITY_RECOVERY.md)
adds independent replay and 24 admitted repeated-process cases. Phase 2 remains OPEN.
