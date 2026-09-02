# GeneralSearchEngine V4 documentation

V4 begins the opt-in durable single-node line. Published `3.4.0` remains the
frozen in-memory reference; V4.0 changes the process-lifetime boundary without
changing retrieval truth, scoring, canonical order, snapshots, or the one-writer
publication model.

## Current status

V4.0 Phase 0 is accepted on protected `master` through PR #77 at `d5a3253`. Phase 1
is accepted at `8758106d30223cc1ad6c2faf66a2f0d1131d507c`; exact-master CI run
`33578036261` passed. Phase 2 now implements the opt-in public durable surface,
exclusive fresh-directory ownership, immutable storage identity, bounded framed WAL,
contiguous sequences, group force and the production crash-barrier matrix. Recovery
and authoritative reopen remain Phase 3 work; checkpoint execution remains Phase 4.

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

## Authority

These documents jointly govern V4.0. If a shorter overview conflicts with a
specialized contract, the specialized contract controls. A behavioral or storage
change after Phase 0 requires a reviewed contract amendment before implementation.
