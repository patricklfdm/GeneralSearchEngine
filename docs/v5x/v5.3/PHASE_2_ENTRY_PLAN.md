# Phase 2 — configuration-aware storage

Status: **OPEN**, local development only. Phase 1 is locally closed; its conditional
context/capsule/selection helpers do not provide durable ownership observations.
The public membership factory remains disabled throughout this storage entry batch.

## Batches and dependencies

| Batch | Work and exit condition |
| --- | --- |
| 2A — locally complete | Private exclusive owner and separately forced ballot counter; exact pre-provisioned root/node binding; fresh-process lock, halt/SIGKILL and restart evidence |
| 2B1 — locally complete | [Root-wide promise and original basis frames](PHASE_2_GRANT_JOURNAL.md); exact duplicate response, incomplete-grant refusal and concurrent observation fencing; physical source retention still pending |
| 2B2a — locally complete | [Original source retention](PHASE_2_BASIS_SOURCES.md): packet/image force before BASIS, exact original replay/reopen and bounded reservations; no source reclamation |
| 2B2b — locally complete for capture | [Current local generation](PHASE_2_CURRENT_GENERATION.md): derive grant parent/tail/images from exact selected disk authority under the journal owner; immutable generation only, remote historical ownership remains conditional |
| 2C1 — locally complete for decision persistence | [Durable SELECTED](PHASE_2_DURABLE_SELECTION.md) under the journal owner, physical original local source and exact same-ballot replay; no installation ACK |
| 2C2 — locally complete for selected install | [Selected local generation installation](PHASE_2_GENERATION_INSTALL.md): exact original decision, carried tail, ancestry, shared reservation and forced selector with interrupted recovery; remote historical ownership remains conditional |
| 2C3a — locally complete for fence | [Certificate-derived adoption fence](PHASE_2_ADOPTION_FENCE.md): exact authenticated bound, forced null-BASIS promise and unchanged original sources; prefix installation still pending |
| 2C3b — locally complete for adoption install | [Local prefix adoption](PHASE_2_ADOPTION_INSTALL.md): force certificate bound before exact candidate, preserve current/original ancestry and removal metadata, recover interrupted install and require a fresh new-view grant; no public runtime |
| 2C4a — locally complete for one retained floor | [Governing floor copies](PHASE_2_GOVERNING_FLOOR.md): complete original copies and eligible exact local generation, old/joint/new majorities, shared reservation, force-before-publication and exact interrupted resumption; no deletion or rotation |
| 2C4b — locally complete for inactive retirement | [Governing-floor retirement](PHASE_2_RETIREMENT.md): forced exact inventory and complete saved original, preserve active/floor/source authority and above-floor owned bytes, resume partial deletion and interrupted recovery; [exact floor image borrowing](PHASE_2_RETIREMENT_IMAGES.md) additionally qualifies constrained four/five-voter retirement without another physical image; no source/floor/journal rotation |
| 2C4c1 — locally complete for journal compaction | [Bounded journal rotation](PHASE_2_JOURNAL_ROTATION.md): preserve exact original source groups/current/floor/highest promises; force compact candidate before atomic replacement; interrupted recovery and all six retained sources |
| 2C4c2 — locally complete for floor release | [Obsolete floor-copy release](PHASE_2_FLOOR_RELEASE.md): exact forced release inventory, relinquish authority before deletion, preserve current/source bytes, recover partial cleanup and permit another full floor within existing slots |
| 2C4c3 — locally complete for journal admission | [Automatic bounded journal backpressure](PHASE_2_JOURNAL_BACKPRESSURE.md): one safe exact compaction attempt at grant/selection/adoption admission, then bounded capacity refusal; retain original sources and fences |
| 2C4c4a — locally complete for decision | [Original-source retirement planning](PHASE_2_SOURCE_RETIREMENT_PLAN.md): newer promise, protected current/floor references, exact ancestry and tail preservation; read-only deletion inventory and exact journal candidate |
| 2C4c4b — locally complete for completed sources | [Original-source retirement](PHASE_2_SOURCE_RELEASE.md): bounded forced original decision, exact journal replacement before listed deletion, partial cleanup/recovery and returned reservations |
| 2C4c4c — locally complete for covered full captures | [Capture-only retirement](PHASE_2_CAPTURED_SOURCE_RELEASE.md): complete original packet/images without BASIS, strictly later full floor, exact journal/deletion recovery |
| 2C4c5a — locally complete for current-pinned captures | [Exact capture recovery](PHASE_2_CAPTURE_RECOVERY.md): forced selector/promise/BASIS intent, actual packet/image prefixes, repeated halt/SIGKILL, unchanged original tail and continuous reservations |
| 2C4c5b — locally complete for exact torn BASIS | [Capture journal recovery](PHASE_2_CAPTURE_JOURNAL_RECOVERY.md): full original intent/source, exact suffix continuation, repeated halt/SIGKILL and unchanged earlier evidence replay |
| 2C4c5c — PROMISE safety locally qualified, capacity/lifetime open | [Unmarked/torn PROMISE boundaries](PHASE_2_PROMISE_BOUNDARIES.md): retain complete fences and refuse unauthorised torn-prefix repair; maximal source/image headroom and complete coordinated lifetime progress remain pending |
| 2C5a — locally complete for selected first-slot ACCEPT | [Original pending ACCEPT](PHASE_2_PENDING_ACCEPT.md): actual forced vote, exact candidate recovery, shared journal/source admission and fresh PREPARE capture |
| 2C5b — locally complete for selected first-slot PROOF | [Original pending PROOF](PHASE_2_PENDING_PROOF.md): actual local ACCEPT-quorum validation, exact durable proof/recovery, duplicate preservation and fresh capture |
| 2C5c — locally complete for original first-slot certificate | [Pending certificate](PHASE_2_PENDING_CERTIFICATE.md): real ACCEPT/PROOF quorum checks, original forced certificate, repeated recovery and unchanged applied state |
| 2C5d — in progress | [Complete application image](PHASE_2_APPLICATION_IMAGE.md) [private replay](PHASE_2_APPLICATION_REPLAY.md) and [catalog projection](PHASE_2_CATALOG_PROJECTION.md) and [certified checkpoint construction](PHASE_2_CHECKPOINT_EXTENSION.md) locally qualified; [applied-end/ACK file component](PHASE_2_APPLIED_END.md) locally qualified; [actual journal application/ACK](PHASE_2_JOURNAL_APPLICATION.md) and bounded replay recovery now locally qualified; [complete generation/selected-parent component](PHASE_2_PUBLISHED_GENERATION.md) now qualified; [actual journal publication and covered cleanup](PHASE_2_JOURNAL_PUBLICATION.md) now integrate the original first slot; [actual parent checkpoints](PHASE_2_PARENT_CHECKPOINT.md) now endorse its hidden immediate parent; [ancestor renewal](PHASE_2_ANCESTOR_RENEWAL.md) extends earlier authenticated endpoints to the new end; [publication admission](PHASE_2_PUBLICATION_ADMISSION.md) checks next ancestry/coverage capacity before ACCEPT; [safe pruning](PHASE_2_ANCESTRY_PRUNING.md) and [repeated fresh-ballot maintenance](PHASE_2_PUBLICATION_LIFETIME.md) now have local evidence; [same-round storage](PHASE_2_ROUND_STORAGE.md) and [process recovery](PHASE_2_ROUND_PROCESS.md) now preserve original first-slot proof; [carried first-entry publication](PHASE_2_CARRIED_PUBLICATION.md) now transfers original votes and bounded maintenance into a new ballot; [carried process recovery](PHASE_2_CARRIED_PROCESS.md) adds repeated-crash qualification; [fenced staging handoff](PHASE_2_STAGED_HANDOFF.md) now retires exact derived work under one newer installed selection; [bounded pending-context reconstruction](PHASE_2_PENDING_CONTEXT.md) supplies a pure exact-byte component and [context persistence](PHASE_2_PENDING_CONTEXT_FILES.md) qualifies candidate/active crash recovery; [bounded capture/rebind](PHASE_2_PENDING_TRANSFER.md) now qualifies exact original preservation across six pure backing transfers; [actual owner retention/reopen and redundant withdrawal](PHASE_2_JOURNAL_CONTEXT.md) now have twelve twice-interrupted local cases; derived staging cleanup now completes under higher volatile observations while all acknowledgements stay fenced; exact context-backed first governing-floor retirement now reconstructs the original vote after its generation is gone, with 54 repeated-crash cases / 162 fresh JVMs; [exact source/context acceptance](PHASE_2_CONTEXT_ACCEPTANCE.md), [three-owner apply/publication](PHASE_2_CONTEXT_PUBLICATION.md) and [86 repeated-death context completion cases](PHASE_2_CONTEXT_COMPLETION_PROCESS.md) now qualify the installed-round completion path; later-campaign progress with retained context, maximal and complete cross-view lifetime remain pending |
| 2D — in progress | [Initial seed projection](PHASE_2_BOOTSTRAP_SEED.md) now verifies EMPTY/actual backup images and initial 3/4/5 layouts without synthetic observations; [private exact-plan persistence](PHASE_2_BOOTSTRAP_PLAN.md) now retains original history through interrupted recovery; [private all-voter prepare/commit/seal transaction](PHASE_2_BOOTSTRAP_TRANSACTION.md) now has local repeated-interruption qualification plus [48 halt/SIGKILL cases / 144 fresh JVMs](PHASE_2_BOOTSTRAP_PROCESS.md); complete public provisioning/open, legacy rejection and configuration-aware storage qualification; real ownership observations replace synthetic inputs; physical S/N coverage and closure audit |

The [2A storage foundation](PHASE_2_STORAGE_FOUNDATION.md) qualifies an isolated
component. Its exact six-name directory inventory must be incorporated into the
complete storage authority layout in later batches. It cannot open a legacy
replica directory or one containing future unrecognized records. The test producer
does not implement the public empty/backup bootstrap contract.

Before Phase 2 closure, all complete-store recovery rules must account for missing,
truncated, corrupt and stale authority, directory/selector replacement, capacity
headroom and interruption during recovery itself. Retaining ambiguous bytes and
rejecting an isolated allocator open is safe, but is not a substitute for the
complete generation/floor recovery and operational repair contract.

## Boundaries

- No 1.1/1.2 format, fixed-three runtime, API inventory, resource limit or workflow
  change is implied. Ballot identity includes proposer and durable storage UUID;
  the 2A component only allocates the counter from verified local identity.
- The later storage/protocol owner must supply every observed bound, establish
  voter eligibility and integrate current promise/selection. A high counter alone
  never authorizes voting, reads or service readiness.
- Fresh-process tests establish behavior under halt/SIGKILL on the tested local
  filesystem. They do not emulate power loss or prove all disk/network schedules.
- Keep all V5.3 work and intermediate commits local. V5.2 experiment, release and
  eventual predecessor integration remain separate, as specified in the
  [development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).

Phase 3 will connect storage to actual activation and transitions. Phase 4 public
operations and later unified acceptance remain required; no Phase 2 batch alone
turns the current physical S/N inventory from PLANNED into an accepted runtime.

2B2b separates immutable capture from the installation transaction originally
listed in that row. Installation serialization belongs with 2C's selector/adoption
recovery: the current entry exposes no installation API and refuses inactive or
selected-installation generations. This sequencing does not waive any storage
closure requirement or establish remote historical ownership.

The [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md) tracks the complete remaining
storage obligations while local batches continue. Component PASS results cannot
close the phase without the integrated recovery, resource and physical audit.

[Applied-but-unpublished covered recovery](PHASE_2_COVERED_STAGING.md) adds
explicit typed retirement of derived staging under an exact newer published
selection, preserving original votes and all voting fences.
[Hidden endpoint cleanup](PHASE_2_HIDDEN_STAGING.md) now has supplemental-proof
owner qualification. [Covered protected contexts](PHASE_2_COVERED_CONTEXT.md)
now have a local selection/install/cleanup and floor-maintenance implementation;
complete process/lifetime profiles and the closure audit remain pending.
