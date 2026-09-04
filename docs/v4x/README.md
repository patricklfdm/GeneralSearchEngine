# GeneralSearchEngine V4.x development line

Published `4.0.0` is the immutable durability foundation. V4.x matures that
single-node durable engine through operational safety, explicit storage evolution,
faster reopen, and final evidence without redefining V4.0 durability or V3.4
retrieval semantics.

## Current status

V4.1 Phases 0–8 are complete. The operational registration merged through protected
PR #103 as `049b232`; the final candidate merged through protected PR #104 as
`9db6efc`, and exact-master CI run `33815734269` passed. Signed tag `v4.1.0`, Maven
Central publication, release workflow `33820284974`, production deployment
`6255241071`, clean remote V3/V4 consumers, and GitHub Release `382405193` all resolve
to that exact commit. V4.1 is the current stable release; V4.2 Phase 6 canonical
evidence is accepted and append-only registration is pending.

V4.2 Phase 0 was accepted through protected PR #106 as
`8391ea67e451da476f8dc8f7c25c3f78e3656173`; exact-master CI run `33830552115`
passed. Phase 1 opened `4.2.0-SNAPSHOT` and established declaration-only APIs,
independent migration models, immutable logical fixtures, a separate-process crash
scaffold and a quota-safe no-GCP evidence plan. Phase 2 froze exact `1.1` bytes and
added codec-free dual-minor inspection; it merged through protected PR #108 as
`85fc9a4`, and exact-master CI run `33839044114` passed. Phase 3 activated explicit
V1.1 operation, same-format backup/restore, and the format-only V1.0-to-V1.1 edge; it
merged through protected PR #109 as `43bf2bd`, and exact-master CI run `33842969788`
passed. Phase 4 merged through protected PR #110 as
`043b95b735dbc7dc1f319e2bd64fccba3063597a`; exact-master CI run `33846632898`
passed. Phase 5 merged through protected PR #111 as
`5687a05aa2f495f58d8acc904ab1e663361cf6e3`; exact-master CI run `33880571096`
passed. Phase 6 implementation and corrections merged through protected PRs
#112–#114; exact-master CI `33905418527` passed on `d0afbb5`. Experiment run
`33900943921` and canonical run `33906942139` passed independent validation and
cleanup. Canonical review is accepted; append-only registration remains pending.

The accepted V4.1 Phase 0 contract freezes a checkpoint-only full-backup protocol, a
distinct `gse-backup (1,0)` bundle, new-history restore into an absent target,
codec-free structural verification, typed semantic verification, offline plan-bound
cleanup, and local-crash plus durable-cloud evidence as first-class architecture.

## Authority map

- [V4.x roadmap](ROADMAP.md)
- [V4.2 development charter](v4.2/DEVELOPMENT_CHARTER.md)
- [V4.2 Phase 0 storage-evolution contract](v4.2/PHASE_0_CONTRACT.md)
- [V4.2 Phase 0 checklist](v4.2/PHASE_0_CHECKLIST.md)
- [V4.2 Phase 1 public API fixture](v4.2/PHASE_1_API_FIXTURE.md)
- [V4.2 Phase 1 foundation baseline](v4.2/PHASE_1_BASELINE.md)
- [V4.2 Phase 1 checklist](v4.2/PHASE_1_CHECKLIST.md)
- [V4.2 Phase 2 format and inspection](v4.2/PHASE_2_FORMAT_AND_INSPECTION.md)
- [V4.2 Phase 2 local baseline](v4.2/PHASE_2_BASELINE.md)
- [V4.2 Phase 2 checklist](v4.2/PHASE_2_CHECKLIST.md)
- [V4.2 Phase 3 format-only migration](v4.2/PHASE_3_FORMAT_MIGRATION.md)
- [V4.2 Phase 3 local baseline](v4.2/PHASE_3_BASELINE.md)
- [V4.2 Phase 3 checklist](v4.2/PHASE_3_CHECKLIST.md)
- [V4.2 Phase 4 typed transform migration](v4.2/PHASE_4_TRANSFORM_MIGRATION.md)
- [V4.2 Phase 4 local baseline](v4.2/PHASE_4_BASELINE.md)
- [V4.2 Phase 4 checklist](v4.2/PHASE_4_CHECKLIST.md)
- [V4.2 Phase 5 lifecycle hardening](v4.2/PHASE_5_LIFECYCLE_HARDENING.md)
- [V4.2 Phase 5 local baseline](v4.2/PHASE_5_BASELINE.md)
- [V4.2 Phase 5 checklist](v4.2/PHASE_5_CHECKLIST.md)
- [V4.2 Phase 6 performance and evidence](v4.2/PHASE_6_PERFORMANCE_AND_EVIDENCE.md)
- [V4.2 Phase 6 evidence baseline](v4.2/PHASE_6_BASELINE.md)
- [V4.2 Phase 6 canonical review](v4.2/PHASE_6_CANONICAL_REVIEW.md)
- [V4.2 Phase 6 checklist](v4.2/PHASE_6_CHECKLIST.md)
- [V4.2 migration cloud baseline registry](v4.2/cloud-benchmark-baselines.json)
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
- [V4.1 Phase 5 plan-bound safe cleanup](v4.1/PHASE_5_SAFE_CLEANUP.md)
- [V4.1 Phase 5 local baseline](v4.1/PHASE_5_BASELINE.md)
- [V4.1 Phase 5 checklist](v4.1/PHASE_5_CHECKLIST.md)
- [V4.1 Phase 6 source-loss and replacement-host evidence](v4.1/PHASE_6_OPERATIONAL_EVIDENCE.md)
- [V4.1 Phase 6 operational evidence baseline](v4.1/PHASE_6_BASELINE.md)
- [V4.1 Phase 6 canonical review](v4.1/PHASE_6_CANONICAL_REVIEW.md)
- [V4.1 Phase 6 checklist](v4.1/PHASE_6_CHECKLIST.md)
- [V4.1 operational cloud baseline registry](v4.1/cloud-benchmark-baselines.json)
- [V4.1 API and storage compatibility](v4.1/API_COMPATIBILITY.md)
- [V4.0-to-V4.1 migration guide](v4.1/MIGRATION_GUIDE.md)
- [V4.1 Phase 7 release-candidate checklist](v4.1/PHASE_7_CHECKLIST.md)
- [V4.1 release checklist](v4.1/RELEASE_CHECKLIST.md)
- [V4.1 GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v4.1.0)
- [Published V4.0 contract and evidence](../v4/README.md)

## Authority order

The published V4.0 contracts continue to govern durability, completion, storage
format `gse-durable (1,0)`, checkpoints, WAL recovery, and retrieval behavior. The
published V4.1 contracts govern backup, restore, verification, cleanup, and evidence
semantics. The V4.x roadmap governs release ordering and scope. The accepted V4.2
charter and Phase 0 contract govern storage evolution; each implementation phase may
add only the work explicitly assigned to it.

If documents conflict, the most specialized accepted contract controls, but it may
not weaken an inherited published guarantee. Any conflict with V4.0 or V4.1 is a
Phase 0 blocker, not an implicit amendment.

## Documentation policy

`docs/v4/` remains the closed historical record for published `4.0.0`, and
`docs/v4x/v4.1/` retains the completed `4.1.0` record. Version-specific V4.x work
belongs below `docs/v4x/v4.N/`; future minor releases do not rewrite prior evidence.
Raw benchmark output and downloaded cloud artifacts remain outside tracked
documentation.
