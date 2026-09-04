# GeneralSearchEngine V4.2 Phase 1 checklist

- **Status:** Implementation candidate; protected acceptance pending
- **Scope:** Non-production storage-evolution foundation and calibrated evidence plan

## Entry and coordinates

- [x] Work begins from Phase 0 merge `8391ea67e451da476f8dc8f7c25c3f78e3656173`
  and exact-master CI run `33830552115`.
- [x] Core, processor, reactor, example and four independent consumers use
  `4.2.0-SNAPSHOT` atomically.
- [x] No production format selector, `1.1` parser/writer, migration API or migration
  implementation is added.

## Published compatibility and public fixture

- [x] Published `4.1.0` core is pinned to SHA-256 `36aa783c…14bcb`.
- [x] Artifact copy/checksum and a published-4.1 Japicmp comparison are present.
- [x] The declaration-only consumer freezes exact generic operation descriptors.
- [x] Format/report, transform, request, plan, result, stage and failure component
  order is frozen.
- [x] Null, normalization, defensive-copy, equality, bounds and Javadoc obligations
  are explicit.
- [x] The declaration fixture compiles while V4.2 production types remain absent.
- [x] Published V4.1 operational reason order and existing behavior are unchanged.

## Independent migration model and fixtures

- [x] The Java oracle preserves source bytes, slot order, sequence and `nextDocId`.
- [x] The model allocates a distinct non-zero target history and domain-separated
  source, projection and plan identities.
- [x] Plan/apply independent projection catches stale source and non-determinism.
- [x] Unsupported/no-op edges, exhaustion, transform failure, key mismatch and
  collision fail closed.
- [x] Checksummed logical `1.0` source, `1.1` target, `1.1` backup and plan bytes are
  immutable.
- [x] The independent Python validator rejects inventory, hash, profile, projection,
  sequence, history, backup and transform inconsistencies.
- [x] Logical fixtures explicitly retain `PHASE2_PENDING`; they do not claim the exact
  physical `1.1` format owned by Phase 2.

## Crash harness and evidence

- [x] Parent and child use separate JVM processes and stable barrier
  `v42-phase1-migration-plan-no-output-v1`.
- [x] Internal halt and external kill both run.
- [x] A second JVM proves source identity unchanged, target absent and graceful close
  not run.
- [x] Stable evidence schema is `gse-v42-migration-evidence-v1`.
- [x] Canonical checksummed evidence is bounded and fails closed on tampering.
- [x] Phase 1 evidence identifies model-only work and contains no production `1.1`
  member or migration output.

## Fake cloud and calibration

- [x] Suite/preset are `v4.2-storage-evolution-suite-v1` and
  `v4.2-storage-evolution-v1`.
- [x] Experiment, canonical and failure-drill profiles use `1/3/1` members.
- [x] Members are serial and cleanup completes before the next member.
- [x] Peak `30` vCPU and `400 GiB` regional SSD stay inside established quotas.
- [x] Source and target use separate `200 GiB` `pd-balanced` disks.
- [x] Source writer stops before migration; target writer stops before 4.1 rollback.
- [x] Replacement-host target continuation and untouched-source rollback are modeled.
- [x] Corpus, mutations, transforms, duration, maximum runtime, GCS prefix, retention,
  OIDC identity and USD `25` ceiling are frozen.
- [x] Fake-cloud validation calls no GCP API and performs no paid execution.
- [x] Paid workflow creation, IAM mutation, execution and registration remain Phase 6.

## Pre-change evidence

- [x] Signed published `4.1.0`, canonical run `33758217508`, source, set digest and
  `v4.1.0-operational-cloud` registration are recorded.
- [x] Pre-change evidence is referenced immutably rather than copied or relabeled.

## Local acceptance

- [x] Focused Java declaration/oracle tests pass locally.
- [x] Independent fixture/parser Python tests pass locally.
- [x] Internal-halt, external-kill and every fake profile pass locally.
- [x] Version alignment passes for `4.2.0-SNAPSHOT`.
- [x] Full reactor tests pass locally (478 core and 5 processor tests, zero failures).
- [x] Published compatibility through exact `4.1.0` and all consumers pass locally.
- [x] Six release JARs pass integrity and two-build byte reproducibility locally.

## Protected acceptance

- [ ] Phase 1 pull request passes required checks.
- [ ] Phase 1 merges to protected `master`.
- [ ] Exact protected-master commit and CI run are recorded.

Production format readers/writers and migration remain prohibited until their owning
phases. Phase 2 may begin only after every local and protected acceptance item passes.
