# GeneralSearchEngine 4.3 API and storage compatibility

## Published baseline

Published `4.2.0` is the immediate binary, source, behavior and storage baseline.
Japicmp retains every published baseline from `1.0.0` through `4.2.0`, and the
independent V1–V4 consumers remain required. V4.3 preserves the in-memory default,
all V3.4 retrieval semantics, V4.0 completion/recovery, V4.1 operational APIs, and
V4.2 explicit migration. It publishes the same two Maven artifacts.

## Additive public surface

The final declaration and reflection fixture freezes these additions:

- exact `DurableStorageFormat.V1_2` and corresponding backup format `(1,2)`;
- `DurableStorageConfig.Builder.maxDerivedStateBytes(long)`;
- codec-free `DurableStorageOperations.inspectDerivedState(Path)`;
- `DurableSearchEngine.lastReopenReport()`; and
- immutable derived-state component/finding/status and reopen outcome/rejection/report
  values.

The exact declaration fixture is
`src/test/resources/compatibility/V43FastReopenPublicApi.java.fixture`, SHA-256
`4bf3503d77d01834915377002ceea92e5704274a2f131f15c71baaf7c2ed233a`.

## Storage compatibility

V4.3 reads exact live formats `(1,0)`, `(1,1)` and `(1,2)`. The builder default is
still `(1,0)`; installing V4.3 never rewrites an existing store. Fresh `(1,2)`
storage and explicit migration targets are opt-in and must be reopened with the exact
same format and logical index configuration.

Canonical metadata, checkpoint, sequence, documents, WAL and logical index
configuration remain the only authority. A `(1,2)` checkpoint may additionally bind
one non-authoritative catalog and one independently validated image for each built-in
equality, range, prefix or text index. Backup remains canonical-only; restore and
migration therefore open cold once, then may publish a new derived generation.

Missing, stale, incompatible, incomplete or corrupt derived bytes never repair or
reinterpret canonical state. Reopen deterministically performs component-local
fallback where possible, otherwise a full rebuild, and best-effort refresh. A refresh
failure cannot fail an otherwise valid canonical checkpoint or mutation.

## Compatibility proof

The published release freezes every API, logical-model and physical `(1,2)` fixture
hash; independently parses live, backup, catalog and component bytes; and expands the
V4 consumer to perform public-only `(1,1)` to `(1,2)` migration, cold fallback,
complete warm reopen, all four built-in query paths, continued mutation, checkpoint
and reopen while proving source bytes unchanged.

Published `4.2.0` can continue to open an untouched `(1,0)` or `(1,1)` source but
must reject a `(1,2)` target. V4.3 adds no reverse migration, online migration,
memory-mapped contract, remote storage, replication or new retrieval semantics.
