# V5.3 Phase 3 entry and closure checklist

Status: **OPEN**. Entered on 2026-10-25 after local Phase 2 closure at
`f0d4dca`. The operator authorized continuous local work through this checklist,
with a local commit after each validated batch and no automatic push. Long
experiments may run later as whole-history GitHub Actions groups; paid cloud
execution requires separate authorization.

This page is the current navigation and closure checklist. The former 2,310-line
entry page is preserved byte-for-byte in
[development history](PHASE_3_DEVELOPMENT_HISTORY.md). Its dated component claims,
failed runs, first-batch boundaries and then-open tasks remain historical evidence.
Later implementations do not erase those failures; an older “unimplemented” note
does not override a newer implementation. Neither page grants qualification.

The [machine qualification plan](phase3-qualification-plan.json) owns the exact
source/test/reader dependencies and all five open gaps. The
[qualification audit](PHASE_3_QUALIFICATION_AUDIT.md) links the detailed component
evidence. The frozen obligations remain in the
[acceptance register](ACCEPTANCE_REGISTER.md), [acceptance plan](acceptance-plan.json),
[protocol](MEMBERSHIP_PROTOCOL.md) and [resource limits](RESOURCE_AND_LIFETIME_LIMITS.md).
No requirement, limit, retry rule, workload or acceptance threshold changes in
this reorganization.

## Implementation order

The implementation inventory is separate from acceptance. Existing controllers,
producers and readers are prerequisites; only the actual complete source-bound
originals and independent replay can close their obligations.

| Batch | Required deliverable | Frozen families | Complete qualification requires |
| --- | --- | --- | --- |
| 3A | Private durable activation | S02, S07, S09, S10 | Own grant, fixed eligible sources, exact installations, bounded retries, original deadline and fencing |
| 3B | TCP transfer and owned recovery | S02, S04, S10 | Root-bound STATUS/SOURCE, authenticated bounded transfers, receiving custody, historical proof, cross-view adoption, fresh ballot, source rotation and restart |
| 3C | Nonvoting learner and joint transition | S01, S03, S05, S09 | Original revisions/image/receipt, SEAL/INTENT eligibility, actual joining initialization, separate old/new majorities, FINAL and new-view barrier for all seven profiles |
| 3D | Generalized vote/publication and automatic continuation | S01, S02, S07, S10 | Carried entry first, ACCEPT then PROOF, certified application, fresh barrier before service, round reuse, competing owners, removal fencing and restart |
| 3E | Protocol closure audit | S01–S05, S07, S09, S10 and applicable N01–N24 | Deterministic faults, fresh-process halt/SIGKILL, network histories, real resource ownership/headroom, original-first physical/history replay and exact requirement mapping |

The machine plan expands these into twelve obligations: `3A-activation`,
`3B-transfer`, `3B-recovery`, `3C-learner`, `3C-initialization`, `3C-joint`,
`3D-rounds`, `3D-automatic`, `3D-removal`, `3E-resources`, `3E-coverage` and
`3E-cohort`. Their individual implementation/test/reader references remain there;
this page does not replace them with a pass count.

The frozen 3,310 S rows and 24 N families remain PLANNED until their owning
complete qualification passes. Phase 4 owns enabled public operations and reads;
Phase 5 owns combined hardening and the complete frozen S/N matrix. Phase 3 must
provide their real protocol dependencies; a component test does not close an S
family or enable public READY.

## Current acceptance work

[Membership control ownership](PHASE_3_MEMBERSHIP_CONTROL_RESOURCES.md) adds
original local PUBLISH capture and voting/slot/activation composition to the
required-four gate. Its v2 result requires **147** exact negatives. Focused native
validation is component evidence. The [complete corrected-source development result](PHASE_3_MEMBERSHIP_CONTROL_RESOURCES.md#complete-corrected-source-development-qualification)
now passes one unretried whole native original at `78403d87`, portable
original-first replay and all 147 exact negatives. Final-source cohort execution
remains pending. Earlier 89-case diagnostics below retain their historical scope.
The complete original at `2a8ed056` now passes execution and original resource
replay; its gate fails on a publication-witness omission after 127 passing
negatives. The [reader correction](PHASE_3_MEMBERSHIP_CONTROL_RESOURCES.md#complete-publication-coverage-without-fast-replies)
and retained failure remain distinct from the later corrected-source development
admission; the earlier original is never relabelled PASS.

[SOURCE queue byte pressure](PHASE_3_SOURCE_QUEUE_PRESSURE.md) now adds a real
six-session TCP cache/send overlap, aggregate-byte refusal and identical-request
recovery component. The [joint queue completion](PHASE_3_QUEUE_COMPLETION.md)
fixture now passes one full-pressure development original and all ten exact
negatives through native FINAL/BARRIER. Final-source execution remains pending. The [supplemental resource cohort](PHASE_3_RESOURCE_COHORT.md)
now makes all five resource originals mandatory in the v3 attested replay, with
[four source-bound workflows and nine seed/raw archives](PHASE_3_RESOURCE_ATTESTATION.md).
Combined byte maxima and final-source admission remain open.
The two queue originals have a [manual parallel execution entry](PHASE_3_QUEUE_RESOURCE_HOSTED.md),
outside Required CI. Hosted execution and supplemental workflow attestation are
pending; no long history is divided to obtain parallelism.
The [multi-chunk completion prerequisite](PHASE_3_QUEUE_COMPLETION.md#multi-chunk-development-prerequisite)
removes the queue fixture's fixed two-chunk image tail and independently checks
all remaining bytes. Its separate small rehearsal confers no maximum-image or
full-pressure qualification; the formal resource profile remains unchanged.
The [explicit segmented queue entry](PHASE_3_QUEUE_COMPLETION.md#explicit-segmented-queue-transport)
now has a separate source-bound producer and twelve-negative gate. It retains
the whole continuous history and rejects substitution into the JSON resource
slot. Its full-pressure execution and any maximum-image composition remain
pending; the existing hosted matrix and five closure gaps are unchanged.
The [maximum-image joint queue entry](PHASE_3_MAXIMUM_QUEUE_ENTRY.md) now connects
the calibrated source and default staging to one complete REMOVE history, with
an explicit capacity-admitted producer and 15-negative independent gate. Its
long positive execution, maximum-input memory and cohort admission remain
pending; it does not replace the earlier resource originals. The
[dedicated manual hosted transport](PHASE_3_MAXIMUM_QUEUE_HOSTED.md) now freezes
the same source/build/tools/dependencies, retains exact-attempt originals and
performs a fresh-process downloaded replay. External run attestation, execution
on an admitted large host and all five closure gaps remain pending.

| Gap | Existing prerequisite | Evidence still required |
| --- | --- | --- |
| component-cohorts | Twelve source-bound catalogues and their independent readers | Complete current-source original histories, exact negatives and undeleted failures |
| combined-resources | Native accounting/custody readers, simultaneous nonempty owner counts, source refusal/recovery, learner cold pressure, capacity continuation and supplementary entries | Feasible combined byte pressure and admitted completion, with actual same-owner lifetime/physical evidence and final-source executions |
| frozen-coverage | Twenty-two source-derived candidate witnesses and exact negative selectors | Actual original-derived applicability and outcomes; no inferred coverage from counts or labels |
| cohort-admission | Seed reconciliation, whole-history replay and exact-attempt workflow observation | One complete matching source/build/tool/reader set, all originals, resource prerequisites and failed-attempt review |
| final-source-execution | Whole-history workflow partitions and portable replay | Authorized execution of every required history on the final source, followed by independent downloaded replay and requirement-by-requirement audit |

The current twelve-subset catalogue contains **566 whole histories, 260 execution
groups, 500 raw archives and 544 selected workflow jobs**. These are planned
counts, not executed or accepted counts. A continuous operation, revision,
recovery or lease/source/history chain remains indivisible. Parallelism is
between independent complete groups only.

The following strengthened resource entries must not be lost behind that
catalogue total:

- [Required-four resource entry](PHASE_3_REQUIRED_FOUR_ENTRY.md): one full
  `5-REPLACE-required-four` original, including file handoff, five joining
  journal close intervals, network closes and complete session/direct/probe
  export bindings, plus original local PUBLISH calls and voting/slot/activation
  control ownership; the current v2 gate requires all **147** exact negatives.
  The 89-case results below describe the preceding gate. This is a supplementary
  three-job entry outside the twelve-subset count. An earlier complete local JVM run
  passed, but strict replay exposed observer-order and missing-request evidence
  gaps; the [integration corrections](PHASE_3_REQUIRED_FOUR_EXPORT_ENTRY.md#local-complete-integration-and-observer-order-correction)
  preserve those failures. Subsequent independent downstream replay passes all
  865 export allocations and the original file/handoff/close components; missing
  source observations still block that original's full gate. A second complete
  original at `feeb7241` includes the unsent observations; its pinned replay
  exposed a frozen-source request crossing a same-authority selector replacement.
  The [source-window correction](PHASE_3_REQUIRED_FOUR_EXPORT_ENTRY.md#frozen-source-across-a-same-authority-selector)
  retains this failure and a separate complete corrected-reader diagnostic with
  all 89 exact negatives. A later conservative cold-owner guard preserves the
  original's generation edges and all 42 frozen-source authorizations. Complete
  matching-source qualification is pending.
- [Maximum-image transition](PHASE_3_MAXIMUM_TRANSITION_EXECUTION.md): one exact
  67,108,832-byte image history, real same-pool receiver refusal, REMOVE/FINAL
  and stable continuation, followed by **16** exact negatives. Its manual-only
  three-job entry requires a separate large native-Linux runner. Only the small
  diagnostic and transport/orchestration have passed; full maximum execution
  remains pending.
- [Capacity completion](PHASE_3_CAPACITY_COMPLETION.md): a locally qualified
  operation-231 continuation with **34** negatives and **163** owner lifetimes.
  Its preceding prefix remains conditional; the final-source continuation and
  broader resource requirements are still necessary.
- [Learner byte pressure](PHASE_3_NATIVE_LEARNER_BYTE_PRESSURE.md): the strengthened
  retained-cancellation member requires three same-original cold lifetimes and
  **62** negatives; earlier weaker originals cannot fill its final-source slot.
- [SOURCE queue pressure](PHASE_3_SOURCE_QUEUE_PRESSURE.md) and
  [joint queue completion](PHASE_3_QUEUE_COMPLETION.md): two separate originals
  with eight and ten negatives respectively. The full joint component now passes
  local original-first qualification at `e532f2df`; this does not fill its
  final-source slot, and the earlier small rehearsal remains diagnostic. Both source-bound entries feed
  the [five-member supplemental set](PHASE_3_RESOURCE_COHORT.md).

The [native verified-backup seed entry](PHASE_3_NATIVE_BACKUP_SEED.md) now lets a
future combined-resource collector supply a real nonempty image to the same
native network/joining fixture. Its focused seed/BARRIER checks do not qualify
the full backup joining history or physical maximum. The complete reader chain
now has explicit backup-source binding and a separate resource receipt contract;
full positive backup replay and bounded large-image capture remain required.
Main/auxiliary wire, event and resource-boundary collectors now have bounded
spooled paths for that seed. Their short development replay is recorded there.
The same audit identifies a separate byte-capacity gap: one maximum image's
base64 representation already exceeds the old whole-wire bound. A dedicated
backup evidence layout and complete positive backup replay are required before
the long maximum native history can be admitted; the existing EMPTY limits are
unchanged.

The [segmented evidence component](PHASE_3_SEGMENTED_EVIDENCE.md) supplies bounded
large-history capture/readback and immutable prefix cuts. Its independent
collector probe is development evidence. The backup native fixture now selects
it explicitly and a short five-node BARRIER history passes independent
connection/resource replay. The complete reader chain now binds the explicit
wire layout and a separate result/negative contract. Deferred transport/content
views now avoid retaining all decoded payloads and pass an isolated memory probe.
Explicit segmented-backup admission now applies the shared 128 GiB whole-original
inventory, and a bounded scanner removes the codec's large-string regex peak.
Ordinary JSON limits remain unchanged. Whole-reader maximum-input memory and
full positive backup execution remain pending. Physical snapshot caches and
generation/source windows now use original-file views for explicit segmented
backup replay; isolated memory and retained-file comparisons are recorded in
the same component document.

The [complete backup execution profile](PHASE_3_BACKUP_EXECUTION.md) connects the
existing native history to immutable collection and independent segmented-backup
admission. Its [dedicated small-backup hosted transport](PHASE_3_BACKUP_HOSTED.md)
now binds the complete original and 149 negatives to one workflow attempt.
Actual positive execution remains pending; the frozen EMPTY supplemental
workflow is unchanged.

[Explicit native staging policy](PHASE_3_NATIVE_STAGING.md) now separates the
existing 512 MiB fixture from the frozen 16 GiB public default for future large
backup histories. The new caller-bound resource gate requires 150 negatives;
it does not reinterpret small-pool evidence or prove a simultaneous maximum.

[Streaming grant observations](PHASE_3_GRANT_STREAMING.md) now support that
explicit segmented-backup policy without caching the complete grant snapshot.
Ordinary JSON bounds remain unchanged. [Source-retirement/publication observation
pools](PHASE_3_CAPTURE_OBJECTS.md) also stream under explicit segmented policy.
Their [replica transport envelope](PHASE_3_REPLICA_CAPTURE_ENVELOPE.md) now covers
384 MiB metadata plus seven 64 MiB images consistently across all three readers.
Real maximum physical composition and whole-reader memory remain before maximum
native runs; synthetic envelope tests do not supply that qualification.
[Selected-member replay](PHASE_3_REPLAY_PAYLOAD_SELECTION.md) removes three
remaining value-first reads from current-generation and checkpoint checks.
Complete original validation stays in place; whole-reader maximum memory is
still distinct from these measured projection components.

The [maximum-image native execution entry](PHASE_3_MAXIMUM_NATIVE_ENTRY.md) now
connects the calibrated maximum backup to that complete history and the explicit
150-negative default-staging reader. Source/seed binding, workspace-local private
storage and capacity admission are implemented; full native execution and
whole-reader memory qualification remain pending. It is separate development
evidence, not a replacement for any frozen supplemental cohort slot.
Its [dedicated manual transport and fresh-process reader observation](PHASE_3_MAXIMUM_NATIVE_HOSTED.md)
now preserve exact-attempt originals and child memory diagnostics. Actual large
native execution and acceptance-environment setup remain pending.

The maximum-image component is a synchronous storage probe. It does not establish
an admitted learner, full metadata pressure or automatic-runtime peak. The
required-four entry qualifies observed ownership and completion, not all byte
maxima. Separate runs or callback peaks cannot be added together to invent a
single combined maximum. The failed
[external-copy pressure probe](PHASE_3_COMBINED_RESOURCE_PROBE.md) remains failed;
its imposed receiving lifetime is not evidence of permitted runtime overlap.

## Final evidence and admission order

1. Finish the remaining real-resource/coverage work without reducing the frozen
   requirements. Keep failures and original evidence; do not use planning rows,
   receipts alone, synthetic orchestration tests or related profiles as proof.
2. Freeze the final source, compiled classes, readers, toolchain and dependencies.
   Use the [qualification inventory](PHASE_3_QUALIFICATION_AUDIT.md) to select all
   required complete catalogues and supplementary entries.
3. Execute complete histories once, retaining all attempts and minute progress.
   An independent group may run in parallel. A failed original stays failed;
   a corrected-source run must remain distinguishable from a retry.
4. Reconcile the [seeds](PHASE_3_SEED_COHORT.md), replay the
   [whole original history set](PHASE_3_HISTORY_COHORT.md), and observe the
   [exact workflow attempts](PHASE_3_WORKFLOW_COHORT.md) before and after replay.
   Include the five supplemental resource originals in that same v3 invocation,
   with their four observed workflows and nine original seed/raw bundles. The
   entry is implemented; actual final-source observations remain pending.
   Inspect every prior failed/cancelled attempt. Do not mix source, toolchain,
   run/attempt, original fragments or independent ownership chains.
5. Audit all twelve obligations and five gaps against the actual original
   outcomes, resource evidence, exact witness applicability and negative reasons.
   Only that complete audit can close Phase 3. Current cohort readers correctly
   remain PARTIAL while broader resource/coverage obligations are missing.

## First batch boundary

The original internal activation-only first batch and its then-deferred socket,
learner, automatic FINAL and public READY scope are retained in
[the historical first-batch record](PHASE_3_DEVELOPMENT_HISTORY.md#first-batch-boundary).
They are not today's implementation boundary and cannot replace the complete
3A–3E obligations above.

## Exit and rollback

Each batch requires focused checks against its actual source/build, retained
logs, documented limits and a coherent local commit. Phase 3 closes only after
every obligation has concrete evidence; failed attempts cannot be replaced by
green retries. Rollbacks must follow the affected component's ownership and
format dependencies, retaining original failures and evidence. The historical
3A-only rollback describes that initial batch, not the whole current runtime.
