# GeneralSearchEngine V4.x development line

Published `4.0.0` is the immutable durability foundation. V4.x matures that
single-node durable engine through operational safety, explicit storage evolution,
faster reopen, and final evidence without redefining V4.0 durability or V3.4
retrieval semantics.

## Current status

V4.1 Phases 1–3 are accepted. Phase 3 merged through protected PR #96 at `f5516df`;
exact-master CI run `33723841861` passed. Phase 4 is the active typed semantic
verification and new-history restore phase while all coordinates remain
`4.1.0-SNAPSHOT`. Cleanup and paid cloud work remain unauthorized.

The Phase 0 candidate freezes a checkpoint-only full-backup protocol, a distinct
`gse-backup (1,0)` bundle, new-history restore into an absent target, codec-free
structural verification, typed semantic verification, offline plan-bound cleanup,
and local-crash plus durable-cloud evidence as first-class architecture.

## Authority map

- [V4.x roadmap](ROADMAP.md)
- [V4.1 development charter](v4.1/DEVELOPMENT_CHARTER.md)
- [V4.1 Phase 0 operational-safety contract](v4.1/PHASE_0_CONTRACT.md)
- [V4.1 Phase 0 checklist](v4.1/PHASE_0_CHECKLIST.md)
- [V4.1 Phase 1 public API fixture contract](v4.1/PHASE_1_API_FIXTURE.md)
- [V4.1 Phase 1 foundation baseline](v4.1/PHASE_1_BASELINE.md)
- [V4.1 Phase 1 checklist](v4.1/PHASE_1_CHECKLIST.md)
- [V4.1 Phase 2 structural verification](v4.1/PHASE_2_STRUCTURAL_VERIFICATION.md)
- [V4.1 Phase 2 local baseline](v4.1/PHASE_2_BASELINE.md)
- [V4.1 Phase 2 checklist](v4.1/PHASE_2_CHECKLIST.md)
- [V4.1 Phase 3 live backup](v4.1/PHASE_3_LIVE_BACKUP.md)
- [V4.1 Phase 3 local baseline](v4.1/PHASE_3_BASELINE.md)
- [V4.1 Phase 3 checklist](v4.1/PHASE_3_CHECKLIST.md)
- [V4.1 Phase 4 semantic verification and restore](v4.1/PHASE_4_SEMANTIC_RESTORE.md)
- [V4.1 Phase 4 local baseline](v4.1/PHASE_4_BASELINE.md)
- [V4.1 Phase 4 checklist](v4.1/PHASE_4_CHECKLIST.md)
- [Published V4.0 contract and evidence](../v4/README.md)

## Authority order

The published V4.0 contracts continue to govern durability, completion, storage
format `gse-durable (1,0)`, checkpoints, WAL recovery, and retrieval behavior. The
V4.x roadmap governs release ordering and scope. The V4.1 charter governs the minor
release boundary. The V4.1 Phase 0 contract governs backup, restore, verification,
cleanup, and evidence semantics.

If documents conflict, the most specialized accepted contract controls, but it may
not weaken an inherited published guarantee. Any conflict with V4.0 is a Phase 0
blocker, not an implicit amendment.

## Documentation policy

`docs/v4/` remains the closed historical record for published `4.0.0`.
Version-specific V4.x work belongs below `docs/v4x/v4.N/`; future minor releases do
not rewrite V4.0 evidence. Raw benchmark output and downloaded cloud artifacts remain
outside tracked documentation.
