# GeneralSearchEngine 4.2 API and storage compatibility

## Published baseline

Published `4.1.0` is the immediate V4.2 binary, source, behavior and storage
baseline. Its core JAR remains checksum-pinned by the isolated artifact profile, and
Japicmp retains every published baseline from `1.0.0` through `4.1.0`. The independent
V1–V4 consumers remain required.

V4.2 is additive. It preserves the default in-memory path, V3.4 retrieval behavior,
V4.0 completion and recovery semantics, and every V4.1 backup, verification, restore
and cleanup guarantee. Opening an existing store never performs migration or silently
rewrites its bytes.

## Additive storage-evolution surface

The final source/reflection fixture freezes these public additions under
`io.github.patricklfdm.generalsearch.durability`:

- explicit `DurableStorageConfig.Builder.format(DurableStorageFormat)` selection,
  with exact `V1_0` and `V1_1` values;
- codec-free `DurableStorageOperations.inspectStoreFormat` and
  `inspectBackupFormat` reports;
- typed `SearchEngineBuilder.planDurableMigration` and `applyDurableMigration`;
- immutable request, transform descriptor/record, source-member, index-change, plan,
  result and stage values; and
- `DurableMigrationException` with bounded diagnostics and stable reason categories.

The exact declarations remain in
`src/test/resources/compatibility/V42StorageEvolutionPublicApi.java.fixture`, whose
frozen SHA-256 is
`19f71f0668c8f97ac3223c5da5a77d5e5555ab44ea3cb644461f18e71dc51cb1`.
Runtime reflection tests freeze methods, record components and enum ordering.

## Storage compatibility

V4.2 reads exact live formats `gse-durable (1,0)` and `(1,1)`. The builder default
remains `(1,0)`, so upgrading the library alone neither opts an application into
`(1,1)` nor changes existing bytes. A configured format must match an existing store.

Format `(1,1)` retains the V4.0 member inventory and logical authority model while
binding a canonical format-profile digest through metadata, WAL, checkpoints and
backup manifests. V4.2 backups preserve the source live format; restore recreates
that same format. Format conversion occurs only through the explicit migration API.

Published V4.1 can continue to open the untouched `(1,0)` migration source, but it
cannot open a `(1,1)` target. V4.2 supplies no reverse migration, online migration,
directory swap, history merge, automatic cutover or implicit downgrade.

## Migration compatibility

The supported edges are `(1,0)` to `(1,1)` and meaningful same-format migrations
when codec, schema, key or index configuration changes. Planning is read-only and
binds the complete source authority, source/target descriptors, transform identity,
projection, capacity bounds and a fresh target history. Apply accepts only that exact
plan and an unchanged source, writes into an absent target, verifies the result, and
publishes it atomically.

Successful migration preserves the source logical sequence and document projection
while publishing a distinct target history. The source directory remains byte-for-byte
unchanged. Source corruption, stale plans, transform collisions, target conflicts,
unsupported edges and ambiguous publication fail closed.

## Independent proof

The final candidate requires source/reflection fixtures, fresh-isolated Japicmp
through published `4.1.0`, all four independent consumers, immutable physical and
logical migration fixtures, strict Javadocs, six-JAR service-boundary inspection and
two byte-identical release builds. The V4 consumer performs a public-only `(1,0)` to
`(1,1)` migration, proves source preservation, opens and mutates the target, then
checkpoints and reopens it.

V4.2 publishes the same two Maven artifacts as V4.1. Migration scripts, crash
harnesses and cloud workflows are evidence infrastructure, not a third supported
artifact or command-line product.
