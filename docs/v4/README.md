# GeneralSearchEngine V4 documentation

Published `4.0.0` is the current stable release and begins the opt-in durable
single-node line. Published `3.4.0` remains the frozen in-memory reference; V4.0
changes the process-lifetime boundary without changing retrieval truth, scoring,
canonical order, snapshots, or the one-writer publication model.

This directory is the closed `4.0.0` contract and evidence record. Active post-4.0
development is governed separately by the [V4.x roadmap](../v4x/ROADMAP.md) and
[V4.1 Phase 0 contract](../v4x/v4.1/PHASE_0_CONTRACT.md); later minor work does not
rewrite the published V4.0 record.

## Current status

V4.0 Phase 0 is accepted on protected `master` through PR #77 at `d5a3253`. Phase 1
is accepted at `8758106d30223cc1ad6c2faf66a2f0d1131d507c`; exact-master CI run
`33578036261` passed. Phase 2 merged through protected PR #79 at `7056a5a` and supplies
the opt-in durable surface, storage ownership, immutable identity, framed WAL,
contiguous sequences, group force and writer crash barriers; its exact-master CI run
`33583721019` passed. Phase 3 merged through PR #80 at `2664638`; exact-master CI run
`33589193180` passed. It supplies authoritative
WAL-only reopen, deterministic replay and index rebuild, strict tail/corruption
classification, recovery barriers, differential oracles and fake-cloud failure-drill
evidence. Phase 4 is accepted through PR #81 at
`32e9c84c944ebd4f5c0b9f2d69efd690d25058cc`; exact-master CI run `33594843119`
passed. Phase 5 merged through protected PR #82 at
`c9a8b4725f3c44bced40764d1a9b3e9a4eb37b51`; exact-master CI run `33597658600`
passed. Phase 6 implementation and paid evidence are complete. The independently
reviewed three-member durable set is registered as `v4.0.0-durable-cloud`; its
protected evidence merge is PR #88 at
`adbe96d9bf73bf03d3082f2ceb58a66ca75dd325`, with exact-master CI run
`33694586398` passing. Phase 7's final candidate merged through protected PR #90 as
`0f2ea5e`; the local evidence-workspace boundary merged through PR #91 as final
protected-master commit `73479da344f24f69e15904660d46783459d80dcf`, and exact-master
CI run `33705710878` passed. Signed `v4.0.0`, release workflow run `33706352253`,
Maven Central publication, clean remote V3/V4 consumer and format-fixture verification,
production deployment `6235596306`, and GitHub Release `381684854` complete Phase 8
at that exact commit. Phase 6 and Phase 7 changed neither production behavior nor
format `1.0`.

## Contract map

- [Roadmap](ROADMAP.md)
- [Architecture and scope](ARCHITECTURE.md)
- [Durability and completion semantics](DURABILITY_AND_COMPLETION.md)
- [WAL and recovery](WAL_AND_RECOVERY.md)
- [Checkpoints and retention](CHECKPOINTS.md)
- [Codecs and storage identity](CODECS_AND_STORAGE_IDENTITY.md)
- [Storage-format compatibility](STORAGE_FORMAT_COMPATIBILITY.md)
- [API compatibility](API_COMPATIBILITY.md)
- [3.4-to-4.0 migration boundary](MIGRATION_GUIDE.md)
- [Validation](VALIDATION.md)
- [Crash harness and cloud durable lane](CRASH_HARNESS_AND_CLOUD_LANE.md)
- [Performance and evidence](PERFORMANCE_AND_EVIDENCE.md)
- [Phase 0 checklist](PHASE_0_CHECKLIST.md)
- [Phase 1 foundation baseline](PHASE_1_BASELINE.md)
- [Phase 1 checklist](PHASE_1_CHECKLIST.md)
- [Phase 2 storage and WAL format](PHASE_2_STORAGE_FORMAT.md)
- [Phase 2 storage and WAL baseline](PHASE_2_BASELINE.md)
- [Phase 2 checklist](PHASE_2_CHECKLIST.md)
- [Phase 3 WAL-only recovery](PHASE_3_RECOVERY.md)
- [Phase 3 local baseline](PHASE_3_BASELINE.md)
- [Phase 3 checklist](PHASE_3_CHECKLIST.md)
- [Phase 4 checkpoint format](PHASE_4_CHECKPOINT_FORMAT.md)
- [Phase 4 local baseline](PHASE_4_BASELINE.md)
- [Phase 4 checklist](PHASE_4_CHECKLIST.md)
- [Phase 5 lifecycle and crash hardening](PHASE_5_HARDENING.md)
- [Phase 5 local hardening baseline](PHASE_5_BASELINE.md)
- [Phase 5 checklist](PHASE_5_CHECKLIST.md)
- [Phase 6 performance and operational hardening](PHASE_6_PERFORMANCE.md)
- [Phase 6 local pre-cloud baseline](PHASE_6_BASELINE.md)
- [Phase 6 durable canonical review](PHASE_6_CANONICAL_REVIEW.md)
- [Phase 6 checklist](PHASE_6_CHECKLIST.md)
- [Phase 7 checklist](PHASE_7_CHECKLIST.md)
- [Release checklist](RELEASE_CHECKLIST.md)
- [Durable cloud baseline registry](cloud-benchmark-baselines.json)
- [V4.0.0 GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v4.0.0)

## Authority

These documents jointly govern V4.0. If a shorter overview conflicts with a
specialized contract, the specialized contract controls. A behavioral or storage
change after Phase 0 requires a reviewed contract amendment before implementation.
