# GeneralSearchEngine 4.4 API and storage compatibility

## Published baseline

Published `4.3.0` is the immediate binary, source, behavior and storage baseline.
Japicmp retains every published baseline from `1.0.0` through `4.3.0`, and the
independent V1–V4 consumers remain required. V4.4 preserves the in-memory default,
all V3.4 retrieval semantics, V4.0 durability, V4.1 operations, V4.2 migration and
V4.3 fast-reopen behavior. It publishes the same two Maven artifacts.

## Closed public surface

V4.4 adds no public Java declaration. The independently generated inventory remains
exactly 177 public types and 2,939 declaration lines with declaration digest
`d67f7f18795222d77c36d4e11ffdc913d1c9c8b6330ea9797b41f6f77d83650b`.
The frozen inventory file is
`src/test/resources/compatibility/v44-public-api-inventory-v1.json`, SHA-256
`67e8c3435a6ccdfb572a0a00d3aa8b3b969815462a6fdebba08e64b412eaf04f`.

No constructor, method, record component, enum order, exception reason, builder
default, serialized identity, Maven coordinate or artifact is added or changed.

## Storage compatibility

Live and backup formats remain exactly `(1,0)`, `(1,1)` and `(1,2)`. The default is
still `(1,0)`. Installing V4.4 never rewrites a store, publishes a derived image,
migrates a format or changes canonical authority merely because the dependency was
upgraded.

Canonical metadata, checkpoint, sequence, documents, WAL and logical index
configuration retain their published meanings. V4.3 derived catalogs and component
images remain optional reconstructible acceleration. Backup stays canonical-only.
All corruption, ambiguity, ownership, cleanup, recovery, restore and migration
boundaries remain fail-closed exactly as published.

## Compatibility proof

The published release freezes the API inventory, V4.4 ten-family independent logical
matrix, V4.1/V4.2/V4.3 physical fixtures, all four independent consumer projects,
fresh-isolated published Japicmp baselines and the immutable
`v4.4.0-final-durable-cloud` registration. The release contains no production Java
change relative to the accepted Phase 1 boundary.

V4.4 adds no `(1,3)`, repair or salvage mode, reverse/online migration, memory-mapped
contract, remote live storage, replication, sharding, consensus or new retrieval
semantics. Those remain outside V4.x.
