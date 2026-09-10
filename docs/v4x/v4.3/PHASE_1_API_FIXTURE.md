# GeneralSearchEngine V4.3 Phase 1 public API fixture

- **Status:** Frozen declaration baseline; realized by Phase 2
- **Fixture:** `src/test/resources/compatibility/V43FastReopenPublicApi.java.fixture`
- **Compatibility baseline:** Published `4.2.0`

## Exact additions realized in Phase 2

The fixture froze the following additive names before implementation, and Phase 2
implemented them without changing the fixture bytes or public declaration shape:

- `DurableStorageFormat.V1_2` and `DurableBackupFormat.V1_2`;
- `DurableStorageConfig.DEFAULT_MAX_DERIVED_STATE_BYTES`, the internal hard maximum,
  `maxDerivedStateBytes()` and `Builder.maxDerivedStateBytes(long)`;
- `DurableStorageOperations.inspectDerivedState(Path)`;
- `DurableDerivedStateStatus`, `DurableDerivedComponentStatus`,
  `DurableDerivedFinding`, `DurableDerivedComponentReport`, and
  `DurableDerivedStateReport`;
- `DurableReopenOutcome`, `DurableReopenRejection`, and `DurableReopenReport`; and
- default `DurableSearchEngine.lastReopenReport()` returning an empty `Optional` for
  independent implementations.

The derived-state status order is exactly `NOT_APPLICABLE`, `ABSENT`, `VALID`,
`PARTIAL`, `STALE`, `INCOMPATIBLE`, `INCOMPLETE`, `CORRUPT`. Reopen outcomes are
exactly `NOT_APPLICABLE`, `COMPLETE_WARM`, `PARTIAL_FALLBACK`, `FULL_FALLBACK`.

The configuration default is 2 GiB and the absolute hard maximum is 8 TiB. Phase 2
must additionally enforce that the effective allowance fits the configured retained-
byte bound and that explicitly setting it with exact format `(1,0)` or `(1,1)` fails.

## Value contracts

Phase 2 constructors must reject nulls, negative durations/counts/bytes, malformed
identifiers and unsorted or duplicate ordinals. Paths are absolute and normalized;
collections are immutable defensive copies; optionals are non-null. Finding details
are bounded and payload-free. Records retain ordinary value equality, hash and string
behavior without embedding document values, extracted keys, credentials or paths in
content identities.

`DurabilityMetrics` remains unchanged. Published enum order and constructors remain
frozen. No Java serialization, reflection-loaded codec, service provider, memory map,
custom-index persistence, background API, or third artifact is introduced.

## Phase boundary

In Phase 1 the fixture was compiled as an independent source file while tests proved
the proposed production report classes were absent. Phase 2 preserves its exact
SHA-256 and verifies the realized API separately; compiling the declaration-only
fixture against the realized API would intentionally introduce duplicate fixture
types. Phase 2 owns `(1,2)` readability plus codec-free derived-state inspection.
Warm reopen, fallback and refresh remain unclaimed until Phases 3 and 4, and migration
remains outside this Phase 2 boundary.
