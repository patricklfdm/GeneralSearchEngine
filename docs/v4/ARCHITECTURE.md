# V4.0 architecture and scope

## North star

GeneralSearchEngine V4.0 adds opt-in durable single-node storage while preserving the
published V3.4 immutable-snapshot, lock-free-reader, asynchronous-mutation, and
single-writer model. It is a durability release, not a retrieval-feature release.

## Frozen modes

### In-memory mode

The existing builder and `build()` path remain storage-free. They require no codec or
directory and retain V3.4 behavior and performance intent. Upgrading the dependency
cannot silently enable disk I/O.

### Durable mode

Durable mode is opened explicitly with a durable configuration. One engine process
owns one local directory through an exclusive lock. Open blocks until storage
validation, recovery, and index rebuild succeed; an application never receives a
partially recovered engine.

## Authoritative flow

```text
concurrent producers
        |
        v
admission and per-unit validation
        |
        v
single authoritative writer
        |
        +--> prepare private candidate state in logical order
        +--> allocate contiguous sequence
        +--> encode and append complete WAL unit
        +--> force group to durable boundary
        +--> atomically publish the prepared immutable snapshot
        `--> complete successful Futures
```

One force and one publication may cover several independently atomic logical units.
Group commit does not merge their sequence identities or failure results.

## Durable truth

V4.0 persists enough information to reconstruct exactly:

- business key and deterministic document bytes;
- canonical live-document slot/order and internal document ID assignments;
- `nextDocId`, so later tie ordering remains deterministic;
- supported startup and dynamic index kind/configuration identities;
- storage, schema, codec, analyzer, and history identities;
- the contiguous committed sequence boundary; and
- authoritative checkpoint and required WAL generation metadata.

Equality, range, prefix, and text index structures are derived. They are rebuilt from
the durable canonical state and frozen configuration. Java object reference identity
is not preserved across restart.

## Supported durable indexes

Durable mode supports only engine-owned built-in equality, range, prefix, and text
index definitions whose kind and configuration have stable persisted identities.
Caller-supplied schema field extractors remain supported under the explicit
`schemaIdentity` assertion and must be supplied again on reopen. Arbitrary custom
`IndexDefinition`, comparator, or analyzer behavior cannot be reconstructed from a
lambda or class name and is rejected in durable mode.

A dynamic create becomes durable only when its background build is successfully
installed. A crash before install recovers the index as absent. A successful drop is
one sequenced durable transition and recovers as absent. Drop continues to cancel an
uninstalled create according to the V3.4 lifecycle contract.

## Preserved behavior

Recovery must reproduce canonical documents and all applicable V3.4 equality, range,
prefix, filter, text, ranked, phrase, fuzzy, BOOL, BOOST, Explain, highlighting,
pagination-first-page, and exact-total results, including score bits and ordering.
Existing cursors remain process/snapshot-bound and never survive reopen.

`SearchEngineMetrics` and `snapshotVersion` remain process-local observations. A
recovered ready snapshot begins at process-local version zero; subsequent successful
publications increment normally. Durable sequence is the cross-restart identity.

## Supported platform and failure boundary

V4.0 initially supports Java 21 on Linux local POSIX-like filesystems that provide
exclusive file locking, forced file data, same-filesystem atomic rename, and directory
durability needed by the implementation. Network filesystems, object-store mounts,
memory filesystems, and directories whose required semantics cannot be established
are unsupported and fail during open.

The machine-failure guarantee assumes the persistent block device and its acknowledged
forced writes survive or are reattached. Physical disk loss is outside single-node
durability and requires external backup or replication.

## Explicit exclusions

V4.0 does not add sharding, replication, consensus, multi-writer storage, remote live
storage, persisted production indexes, vector/hybrid search, facets, caches, new
ranking or analysis semantics, snapshot pinning, or transparent downgrade.
