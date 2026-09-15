# V5.0 Phase 1 entry plan

- **Status:** Locally validated candidate; protected-master acceptance pending
- **Expected branch:** `feat/v5.0-phase1-foundation`
- **Expected coordinates after entry:** `5.0.0-SNAPSHOT`

## Entry preconditions

Phase 1 starts only from an exact protected-master commit for which:

- the V5.0 Phase 0 checklist is accepted;
- exact-master CI, including `verify-v50-phase0-contract.sh`, passes;
- the worktree is clean and root prompt files remain untracked;
- no `v5.0.0` tag or Central `5.0.0` coordinates exist; and
- the published V4.4 control artifacts and checksums remain resolvable.

## Planned work packages

1. Change every active reactor/example/consumer coordinate to `5.0.0-SNAPSHOT` and
   preserve exact published V4.4 comparison coordinates.
2. Add the optional replication Maven module with declaration-only API, package docs,
   source/reflection fixtures and an independent V5-style consumer.
3. Add an implementation-independent replicated-history model covering epoch promise,
   append, commit proof, apply, uncommitted truncation and recovery floor.
4. Freeze exact logical protocol fixtures and structured event/evidence schemas without
   enabling a production network path. Freeze the transport dependency, common binary
   frame envelope and golden bytes under [the framing decision](TRANSPORT_AND_FRAMING.md).
5. Add deterministic in-process delivery/fault scheduling with serialized replay.
6. Add three separate-JVM workers and safe process/storage crash orchestration over
   temporary directories; retain complete artifacts on failure.
7. Freeze finite API/storage/network defaults and absolute bounds through tests.
8. Add a no-GCP fake control plane for three concurrent voters and serial topology
   repetitions, including provisioning failures and cleanup receipts.
9. Add a manual cloud workflow in dry-run/fake mode only. Prepare WIF workflow identity,
   private firewall, GCS-prefix and quota preflight instructions; do not execute paid
   resources.
10. Record exact published V4.4 control, Java/Maven/toolchain identity and a Phase 1
    foundation baseline/checklist. Verify candidate machine and image catalog entries
    read-only; retain the [availability receipt](cloud-availability.json). Refresh
    capacity/quota/pricing and freeze the guest runtime before paid Phase 6 admission.

## Explicit non-goals

Phase 1 does not append a production replicated entry, open a production replicated
directory, listen on a production network endpoint, create a GCP VM/disk, publish an
artifact, register a baseline or claim quorum durability.

## Exit gate

Phase 1 exits only when independent model/property tests, declaration consumers,
logical fixtures, deterministic trace replay, separate-process crashes, fake cloud,
resource bounds and exact V4.4 controls all pass locally and in CI. Phase 2 may then
implement only replicated storage/inspection and follower durable append; leader
quorum publication remains Phase 3.
