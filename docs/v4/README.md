# GeneralSearchEngine V4 documentation

V4 begins the opt-in durable single-node line. Published `3.4.0` remains the
frozen in-memory reference; V4.0 changes the process-lifetime boundary without
changing retrieval truth, scoring, canonical order, snapshots, or the one-writer
publication model.

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
passed. Phase 5 is active and implements lifecycle/concurrency races, deterministic
I/O failure semantics, retained-footprint loops, same-history repeated hard crashes,
independent prefix inspection and a fake-cloud hardening drill.

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

## Authority

These documents jointly govern V4.0. If a shorter overview conflicts with a
specialized contract, the specialized contract controls. A behavioral or storage
change after Phase 0 requires a reviewed contract amendment before implementation.
