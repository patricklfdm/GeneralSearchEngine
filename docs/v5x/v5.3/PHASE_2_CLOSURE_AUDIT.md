# Phase 2 local storage closure

**Status: LOCALLY CLOSED**, 2026-10-25. Unified operator review is pending.

Scope is the configuration-aware **local storage layer**, including the public
offline EMPTY/verified-backup bootstrap. The membership engine, learners, automatic
network campaigns and public add/remove/replace remain disabled. Unified operator
acceptance, protected CI and integration with the eventual released V5.2 remain
separate. No push, tag, workflow dispatch, release or paid experiment was performed.

## Requirement and evidence map

| Storage requirement | Direct evidence | Scope boundary |
| --- | --- | --- |
| Exclusive root/node owner and monotonic allocation | [Foundation](PHASE_2_STORAGE_FOUNDATION.md), [admitted store](PHASE_2_BOOTSTRAP_STORE_ADMISSION.md), [public bootstrap](PHASE_2_PUBLIC_BOOTSTRAP.md) | Supported initial 3/4/5 sizes and EMPTY/backup sources; no implicit legacy conversion or genesis fallback |
| Original promise, BASIS/source and fixed selected set | [Grant journal](PHASE_2_GRANT_JOURNAL.md), [source retention](PHASE_2_BASIS_SOURCES.md), [selected decision](PHASE_2_DURABLE_SELECTION.md), capture/torn-journal recovery | A stored authenticated original is required; no synthetic remote receipt is inferred by an owner |
| Exact install, context-backed recovery and carried voting | [Selected installation](PHASE_2_GENERATION_INSTALL.md), [context completion](PHASE_2_CONTEXT_COMPLETION_PROCESS.md), [mixed originals](PHASE_2_COVERED_CONTEXT_MIXED.md), [successor process recovery](PHASE_2_SOURCE_SUCCESSOR_PROCESS.md) | Local original owners and bounded maintenance; network installation delivery remains Phase 3 |
| ACCEPT/PROOF/certificate, typed apply-once and publication | [Pending certificate](PHASE_2_PENDING_CERTIFICATE.md), [application](PHASE_2_JOURNAL_APPLICATION.md), [publication](PHASE_2_JOURNAL_PUBLICATION.md), [same-round](PHASE_2_ROUND_PROCESS.md), [carried process](PHASE_2_CARRIED_PROCESS.md) | Both applicable majorities and exact original first-slot proof; no service-ready inference |
| Configuration-aware recovery and removal | [Admitted cross-view](PHASE_2_ADMITTED_CROSS_VIEW.md), [admitted adoption process](PHASE_2_ADMITTED_ADOPTION_PROCESS.md) | Four initial size/source profiles; six actual REMOVE transitions, 60 slots, 232 owner publications; adoption has 152 twice-interrupted cases, 456 workers and 76 lock probes. ADD/REPLACE learner delivery remains later |
| Governing floor and bounded reclamation | [Floor](PHASE_2_GOVERNING_FLOOR.md), [retirement](PHASE_2_RETIREMENT.md), [source image ownership](PHASE_2_RETIREMENT_SOURCE_PROCESS.md), [hidden endpoints](PHASE_2_HIDDEN_STAGING_PROCESS.md), [full journal](PHASE_2_FULL_JOURNAL.md) | Complete original copies and inventories, forced decisions before deletion, repeated recovery, no deletion by timeout |
| Byte limits, completion headroom and continued stable DATA | [Publication capacity](PHASE_2_PUBLICATION_CAPACITY.md), [native maximum application](PHASE_2_MAXIMUM_APPLICATION.md) | Logical count and actual byte limits both apply. Native image is 64 MiB minus the original writer's 32-byte request ID; unchanged container ceiling is 64 MiB |
| Independent physical and source/build evidence | Retained original inventories, normal/optimized readers, original-first negative mutations, portable copies and [closure index](phase2-evidence/closure.json) | Historical source/build hashes stay historical; current regression results are recorded separately |

The conditional large-history fixture proves pre-vote capacity refusal and actual
subsequent owner operations. It does **not** prove 233 distributed reconfigurations.
Ordinary DATA still increments the application sequence and survives typed reopen
after new membership admission is refused. The size reservation also keeps valid
pre-SEAL cancellation available and preserves already-owned votes.

The admitted cross-view process fixture uses actual public bootstrap originals,
forced old/joint/new votes and the original remote FINAL packet. Its process cuts
qualify removed-owner adoption; component floor/source/generation crash histories
remain separately scoped. Finite halt/SIGKILL tests do not emulate power loss or
establish an availability/performance SLA.

## Final-source checks

Final runtime: **709 production classes** from an isolated fresh build. The
replication JAR and 693 class files match the publication-capacity build exactly.
The remaining 16 files are empty package declarations: independent decoding checks
identical class identity/version/flags, no fields, methods or interfaces, and only
the same SourceFile attribute; their constant-pool ordering differs. The core JAR
also omits six empty ZIP directory entries. All executable classes and other
resources are byte-identical. The final two JAR hashes are recorded separately. **61 final-source Java tests** pass,
including admitted old/joint/new continuation, legacy application recovery, frozen
API inventories and version boundaries. The current-source cross-view evidence
passes in normal and optimized Python, including 16 exact negative results and
portable replay. **530 V5.3 Python tests** pass separately in normal and optimized
mode; **29 coordinate/shared-build/release-fixture tests** also pass.

The first workspace invocation had 11 local-socket errors across the V5.0 recovery
and V5.2 read-cut suites. Those two suites passed outside the sandbox, but a later
artifact comparison found the shared core output had been rewritten outside that
Maven compilation. Its source was unchanged and the exact writer is unverified.
Those workspace results remain diagnostic, not final binary qualification. All 13
suites were therefore rerun on the isolated fresh build, with before/after source
and class hashes and fresh JUnit timestamps. Original failures, output differences
and both workspace reports remain retained.

The complete native-maximum Java run passes with two BARRIER publications and
three campaigns at 67,108,832 bytes, retaining seven full physical images. Its
original-first reader and 13 evidence negatives pass in normal, optimized and
archive-unpacked replay. All failed calibration/driver/heap/reader attempts remain
retained separately. The prior 8 publication-capacity and 46 related regressions
are bound to the same executable production classes; they are not counted again above.

The [machine-readable closure receipt](phase2-evidence/closure.json) records the
exact final inputs, JUnit reports, raw inventories, source/JAR/class hashes and
historical evidence references. Historical crash executions are not relabelled as
new runs of the final runtime. The final admission guard adds no write boundary;
its original red tests, exact refusal behavior and affected continuation paths
have their own current-runtime qualification.

The final capacity change modifies the journal's pre-vote admission and adds one
read-only packet-size accessor plus the private size estimator. There is no new
write boundary. Two additional nested-record class hashes change only because
debug line numbers moved; full disassembly is retained. Final source qualification binds all 709 production class files and separately
records the fresh-build differences in empty package metadata. Executable class
bytes remain identical; historical and final JAR hashes are not conflated.

All inherited core Java, V5.0/V5.1/V5.2 runtime scripts, predecessor documentation
and workflows match the development branch base. Two inherited V5.1 test fixtures
explicitly recognize the V5.3 coordinate/consumer count. The only pre-existing
replication production file changed across the local development sequence is
`ReplicaApplication`: package-private application-state and descriptor decoding
were extracted without changing the old backup/restore contract. Focused inherited
behavior, token/API and version-boundary checks are recorded on the final source.

The metadata audit distinguishes immutable evidence from historical observations
of shared `target` build paths. One old finalizer hashed its empty stdout before
printing a finalization message. The original index is preserved; that stdout is
excluded as a semantic oracle. The caveat does not waive missing authority or
allow failed evidence to count as a successful replay.

## What remains planned

Storage portions of S02 map to promises/selection/phased votes; S04 to capsules,
catalogs, selectors, floors and retirement; S07 to retained first proof and round
reuse; S09 to count/byte/resource admission; S10 to exact original recovery.
Their full distributed combinations, learner and service-readiness behavior still
belong to Phases 3–5. Relevant component mutations cover identity, both-side quorum,
force order, descriptors/catalog, owned tail, selector/floor and crash labels;
these counts are not substitutes for the frozen N01–N24 inventory.

The negative-family mapping is a scope map, not a claim that the final runtime
matrix negatives have executed:

| Frozen families | Local storage evidence and remaining boundary |
| --- | --- |
| N01 source SHA, N02 build hash | Exact input maps, JAR/class comparisons and the retained-index audit bind each batch. This provenance audit is not the future hosted source/build tampering gate. |
| N03 attempt ID, N21 crash relabeling | [Process adoption](PHASE_2_ADMITTED_ADOPTION_PROCESS.md), [same-round process](PHASE_2_ROUND_PROCESS.md) and [typed bootstrap process](PHASE_2_BOOTSTRAP_TYPED_PROCESS.md) validate exact case/worker/exit/cut inventories. Hosted workflow-attempt authority remains later. |
| N04 root/history, N05 configuration generation, N10 storage identity | [Grant originals](PHASE_2_GRANT_JOURNAL.md), [installation](PHASE_2_GENERATION_INSTALL.md), [admitted cross-view](PHASE_2_ADMITTED_CROSS_VIEW.md) and [maximum application](PHASE_2_MAXIMUM_APPLICATION.md) verify original root/view/node/typed history binding. |
| N06 ACCEPT force, N07 PROOF force | [Pending ACCEPT](PHASE_2_PENDING_ACCEPT.md), [pending PROOF](PHASE_2_PENDING_PROOF.md), same-round and admitted cross-view replay check actual force-before-return order. |
| N08 duplicate voter, N09 either-side majority | Context/certificate verification and the admitted old/joint/new chain require exact voter sets and both majorities; no union-majority shortcut. Full distributed witness combinations remain Phase 5. |
| N11 pre-admitted learner | This storage owner admits original voters and verifies context eligibility; learner enrollment, READY delivery and public admission are Phase 3/4 work, not closed here. |
| N12 prepared cut, N13 SEAL/CANCEL order, N14 hidden membership RANGE, N15 catalog, N16 sealed descriptor | [Catalog projection](PHASE_2_CATALOG_PROJECTION.md), [checkpoint extension](PHASE_2_CHECKPOINT_EXTENSION.md), [context verification](PHASE_1_CLOSURE_AUDIT.md) and admitted cross-view replay bind exact original transitions. Learner/runtime ordering combinations remain later. |
| N17 owned tail, N18 selector force, N19 retirement floor | [Selected installation](PHASE_2_GENERATION_INSTALL.md), [covered originals](PHASE_2_COVERED_PHASED_VOTES.md), [floor](PHASE_2_GOVERNING_FLOOR.md), [retirement](PHASE_2_RETIREMENT.md) and original-source recovery preserve forced authority before switching or deleting. |
| N20 replayed read cut | Public membership reads are disabled; later public-runtime qualification owns this negative. Predecessor read-cut regression is compatibility evidence only. |
| N22 missing failed attempt, N24 incomplete matrix | Local evidence indexes retain original failures and exact component case inventories. They do not qualify a future cloud cohort or turn omitted S rows into PASS. |
| N23 wrong control JAR | Published V5.2 control integration and workload control negatives remain later; no current local storage fixture is labelled a released control. |

All **3,310 S rows and 24 N families remain PLANNED** for their owning acceptance
phase. No public read/runtime, network liveness, whole-group service recovery,
performance measurement, paid cloud, signed release or published V5.2 control is
claimed. Phase 3 is not started automatically by local storage closure. The next
operator boundary is unified review of the locally committed Phase 2 work.
