# GeneralSearchEngine V4.1 Phase 1 checklist

- **Status:** Implementation complete; protected acceptance pending
- **Scope:** Non-production foundation and calibrated evidence plan

## Entry and coordinates

- [x] Work begins from Phase 0 merge `8d83f41` and exact-master CI run
  `33714630130`.
- [x] Core, processor, reactor, example and four independent consumers use
  `4.1.0-SNAPSHOT` atomically.
- [x] No production operational API or implementation is added.

## Published compatibility and API fixture

- [x] Published `4.0.0` core is pinned to SHA-256 `77dd13…e6a4`.
- [x] Artifact copy/checksum and ninth Japicmp comparison include exact `4.0.0`.
- [x] The declaration fixture freezes constructors, accessors, generic signatures,
  operation ownership, status families and failure reasons.
- [x] Construction bounds, null handling, normalization, defensive copying, equality
  semantics and production Javadoc obligations are frozen in the API fixture contract.
- [x] The fixture compiles while production V4.1 operation types remain absent.
- [x] Existing V4.0 durable methods and formats are unchanged.

## Independent models and format

- [x] The backup model freezes exact `B`, later-mutation exclusion and stable content
  identity without production recovery.
- [x] The restore oracle requires matching identities, creates a distinct non-zero
  history and preserves canonical logical state.
- [x] Sequence exhaustion fails without a modeled bundle.
- [x] Exact `gse-backup (1,0)` metadata/checkpoint/manifest byte representations are
  immutable fixtures.
- [x] Manifest magic, every field encoding, payload order, SHA-256 preimage and CRC32C
  are documented and tested.
- [x] The independent Python inspector rejects mutation, extra members and unsafe
  member types.

## Crash harness and evidence

- [x] Parent and child run as separate processes with stable barrier
  `v41-phase1-operational-scaffold-v1`.
- [x] Internal halt and external kill paths both run.
- [x] A shutdown-hook marker proves graceful close did not run.
- [x] A second JVM verifies the post-crash scaffold.
- [x] Stable evidence schema is `gse-v41-operational-evidence-v1`.
- [x] Canonical checksummed evidence is bounded and fails closed on tampering.
- [x] Phase 1 evidence explicitly identifies model-only operations and contains no
  production storage member.

## Fake cloud and calibration

- [x] Suite/preset identities are distinct from V4.0.
- [x] Experiment, canonical and failure-drill profiles use `1/3/1` members.
- [x] Canonical members are serial to respect the 32-vCPU and 500-GiB quota envelope.
- [x] Source VM/disk become unavailable before replacement-host restore.
- [x] Source and restore disks, staging object, VMs and local artifacts have explicit
  cleanup results.
- [x] Corpus, operations, duration, maximum runtime, disk, GCS layout and USD `25`
  ceiling are frozen before paid work.
- [x] Fake-cloud validation invokes no GCP API and performs no paid execution.

## Pre-change evidence

- [x] Published V4.0 canonical evidence `33682157985` remains the checkpoint,
  recovery, latency, heap/retention and long-run control.
- [x] Its source, set digest and `v4.0.0-durable-cloud` registration are recorded.

## Acceptance

- [x] Focused Java fixture/model tests pass locally.
- [x] Independent fixture/parser Python tests pass locally.
- [x] Internal-halt, external-kill and every fake profile pass locally.
- [x] Version alignment passes for `4.1.0-SNAPSHOT`.
- [x] Full reactor tests pass locally (430 core and 5 processor tests, zero failures).
- [x] Published compatibility through exact `4.0.0` and all consumers pass locally.
- [x] Six release JARs pass integrity and two-build byte reproducibility locally.
- [ ] Phase 1 pull request CI passes and merges to protected `master`.
- [ ] Exact-master CI passes and its commit/run are recorded.

Production codec-free verification remains blocked until every acceptance item passes.
