# GeneralSearchEngine 4.1 API and storage compatibility

## Published baseline

Published `4.0.0` is the immediate V4.1 binary, source, behavior and live-storage
baseline. Its core JAR is pinned by the isolated artifact profile to SHA-256
`77dd13c618caa36a411048a412e2ac88760186a479ed520b9e84a6ef8933e6a4`.
Japicmp also retains every earlier published baseline from `1.0.0` through `3.4.0`,
and the independent V1–V4 consumers remain required.

V4.1 is additive. It does not change the default in-memory path, V3.4 retrieval
semantics, V4.0 mutation completion, crash indeterminacy, checkpoint authority,
recovery, corruption handling, single-writer ownership or live format
`gse-durable (1,0)`.

## Additive operational surface

The final source/reflection fixture freezes these public families under
`io.github.patricklfdm.generalsearch.durability`:

- `DurableSearchEngine.backup(DurableBackupRequest)` and immutable backup request,
  format and result values;
- codec-free `DurableStorageOperations.verifyStore` and `verifyBackup` with immutable
  structural reports, findings and status;
- typed `SearchEngineBuilder.verifyDurableBackup` with explicit codec/schema bounds
  and semantic status/report values;
- typed `SearchEngineBuilder.restoreDurableBackup` and immutable new-history
  provenance result;
- codec-free `planCleanup` and `applyCleanup` with exact scope, inventory, digest and
  result values; and
- the separate `DurableOperationException` operational reason family.

The exact declarations remain in
`src/test/resources/compatibility/V41OperationalPublicApi.java.fixture`, whose frozen
SHA-256 is
`1f50af65a5894d08d25d70d490c86a9cb958119576750b507ac049e8b0a5432b`.
Runtime reflection tests freeze methods, record components and enum ordering.

## Storage compatibility

V4.1 reads an existing V4.0 `gse-durable (1,0)` store without rewriting it merely
because a newer library opened it. A V4.1 restored target is an ordinary new-history
`gse-durable (1,0)` store and remains readable by V4.0 when the same codec, schema,
storage identities and index configuration are supplied.

The new immutable `gse-backup (1,0)` bundle is intentionally not a V4.0 capability.
It contains exactly metadata, checkpoint and completion manifest members and never a
live WAL. Its source bytes and identity are frozen by independent hex fixtures and a
Python parser that does not invoke production recovery.

No online migration, silent rewrite, in-place restore, repair, format conversion or
history merge is implied. Future live-format evolution remains owned by V4.2.

## Independent proof

The published release is protected by all of the following:

1. source and reflection fixtures for every inherited and V4.1 operation;
2. fresh-isolated Japicmp comparisons through published `4.0.0`;
3. V1, V2, V3 and V4 consumer builds against the candidate artifact;
4. a V4 consumer operational round trip using public API only;
5. immutable live-format `1.0` and backup-format `1.0` fixtures validated by both
   production and independent readers; and
6. release Javadoc, six-JAR service-boundary and reproducibility gates.

The V4 consumer creates and backs up a live store, verifies the bundle structurally
and semantically, restores a distinct history, checks documents, continues mutation,
checkpoints, reopens, verifies the restored store and applies an empty safe-cleanup
plan. The release workflow repeats the consumer against remotely downloaded artifacts
after publication.

## Artifact boundary

V4.1 publishes the same two Maven artifacts as V4.0. Operational APIs stay in the
core artifact; the annotation processor remains isolated. Repository scripts and
cloud workflows are evidence infrastructure, not a third supported CLI artifact.
