# V5.3 Phase 1 entry

Entry requires the local [Phase 0 checklist](PHASE_0_CHECKLIST.md) to pass. The
operator authorized this branch's local commits while V5.2 cloud work continues;
push/PR/merge/release/cloud remain separate permissions. This Phase 0 goal stops
at its closure and does not automatically start Phase 1.

## Implementation batches

1. **Coordinates and disabled surface.** Align all reactor versions and API fixtures
   to `5.3.0-SNAPSHOT` in one isolated commit; leave frozen published V5.2 evidence
   and contracts unchanged. Add the exact additive declarations from the Phase 0
   API contract. Builder/config constructors stay pure. New runtime `start()` remains
   explicitly unavailable until the storage/protocol/public gates are implemented.
   Do not expose membership through the legacy fixed-three factory.
2. **Bytes and independent readers.** Implement the 24 storage / 21 wire kinds,
   bounded content-addressed transfer, original basis/cut binding, separate catalog
   snapshot and resource accounting. Java output must match retained independent
   fixtures exactly; malformed/contextual inputs reject before allocating/writing.
   Add independent physical decoding, no importing production decoder into oracle.
3. **Full deterministic composition.** Join existing global-grant/operation/learner
   logic with same-round DATA/CONTROL/barrier validation and compacted frozen sources.
   Carry original bytes/certificates across recovery. Materialize the full S/N case
   inventory, deterministic clocks/network/fault points and explicit parent-force
   guards. Test stale promises, selected source loss and majority intersection at
   all seven membership profiles. No physical behavior claim from model traces.
4. **External process scaffold.** Fresh JVM public worker/consumer using only public
   API; independent process control and raw force/wire/app history; exact source/JAR
   provenance, portable evidence and expected negative inventory. Leave runtime
   disabled until Phase 2 storage and Phase 3 transition gates pass.

## Acceptance for Phase 1

- All existing compatibility/API consumers still compile and execute their existing
  supported path. New consumer declarations compile against the aligned JARs.
- Exact protocol schema/fixture parity, parser/allocation/ownership negatives and
  rejected opening of 1.1/1.2 as 1.3, without modifying original bytes.
- Full model covers steady rounds + catalog/compacted sources + membership recovery
  together, not only the separate Phase 0 references. Every original passes before
  corruption negatives; full finite inventory is generated and complete.
- Versions/build manifest/source inventories agree; focused reactor/build/test and
  Java/Python gates run once relevant code exists. Phase 0 intentionally did not run
  Maven or add CI jobs. Future workflow registry/Required/cloud exact-source consumers
  must be changed together when the new suites are wired, preserving old checks.
- No live voter mutation, file deletion, cloud permission/config change or release
  activation is bundled into declaration scaffolding.

## Predecessor integration and deferred qualification

The recorded base is `73f3bd5c21c97eee564397ab11af7b66bc1b13a3`, not a published V5.2
control. After actual V5.2 publication, verify its signed source and artifact
inventory, review every intervening runtime fix, merge that history into this local
branch under authorization, and rerun affected models/storage/compatibility checks.
Keep the independent V5.2 Runner checkout and active experiment untouched meanwhile.

Protected acceptance may wait for the operator's unified acceptance stage, but
focused local tests cannot be skipped. Phase 2–5 must supply actual durable storage,
wire, public concurrency/fault, read and resource evidence. Phase 6 pins real machine,
published controls, images and costs before frozen measurements; Phase 7 handles
release under a separate reviewed contract. No earlier local receipt substitutes.
