# V4.0 Phase 1 checklist

**Status:** implementation complete; full validation and protected merge pending

## Entry and version

- [x] Work begins from Phase 0 protected merge `d5a3253` (PR #77).
- [x] Exact Phase 0 master CI run `33563515761` passed for protected-master commit
  `d5a32538f5eea5f419fe77d024171b4fbaabea20`.
- [x] Core, processor, reactor, example, and all three consumers use
  `4.0.0-SNAPSHOT` atomically.
- [x] No production source or supported public API is added.

## Compatibility and pre-change oracle

- [x] Published `3.4.0` core is pinned to SHA-256
  `e4dee61efacbff8d042b1ffda50f8b4ec1117b90689b55e621464f0c3a1c525f`.
- [x] Artifact-copy/checksum and eighth Japicmp comparison include exact `3.4.0`.
- [x] V1/V2/V3 independent consumers target the reactor snapshot.
- [x] V3.4 in-memory mutation/ranking/canonical-order behavior has a V4 pre-change
  fixture.
- [x] The independent history oracle models slots, `nextDocId`, indexes, atomic units,
  contiguous sequence, rejection, and replay without calling production recovery.
- [x] The declaration-only durable API fixture is present and production durable types
  remain absent.

## Crash harness and evidence

- [x] Parent and child are separate processes with a machine-readable stable barrier.
- [x] Internal `Runtime.halt` and external kill paths are both executable.
- [x] A shutdown-hook marker proves graceful close did not run.
- [x] Recovery verification occurs in a second JVM.
- [x] The independent storage inspector rejects unauthorized Phase 1 production files.
- [x] Evidence is canonical, schema-versioned, checksummed, bounded, and independently
  validated.
- [x] Case/configuration/history/Future/process/inspection/recovery/log/cleanup sections
  are mandatory before production storage exists.
- [x] Every evidence bundle records a full lowercase source SHA and an explicit
  `clean` or `dirty` source state.
- [x] Tampering and unexpected evidence structure fail closed.

## Fake cloud lane

- [x] V4 suite/preset/profile identities are independent from every V3 family.
- [x] Fake orchestration separates writer VM, persistent disk, abrupt termination,
  recovery VM, upload, and cleanup.
- [x] The failure drill proves the data disk survives writer termination in the model.
- [x] Experiment and failure-drill fake profiles validate without GCP or paid work.
- [x] CI runs the bounded local scaffold and no-GCP validators.

## Acceptance

- [x] Focused Java fixtures pass.
- [x] Internal-halt and external-kill scaffold cases pass.
- [x] Python unit, checksum, inspector, and fake-cloud tests pass.
- [x] Version alignment passes for `4.0.0-SNAPSHOT`.
- [x] Full reactor tests pass (394 core/processor tests, zero failures).
- [x] Published-artifact compatibility through exact `3.4.0` and all independent
  consumers pass.
- [x] Local release packaging integrity and two-build byte reproducibility pass for all
  six JARs.
- [ ] All required PR and exact-master CI jobs pass.
- [ ] This phase merges through protected review and exact-master CI succeeds.

Phase 2 production storage ownership and WAL work is not authorized until every open
acceptance item is resolved. Phase 2 must add stable crash barriers with each storage
transition rather than postponing harness integration.
