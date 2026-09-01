# V4.0 codecs and storage identity

## Explicit generic encoding

Durable mode cannot persist arbitrary `K` and `T` objects implicitly. It requires one
caller-supplied deterministic `DurableCodec<K,T>` with the Phase 1 public shape:

```java
public interface DurableCodec<K, T> {
    String codecId();
    int codecVersion();
    byte[] encodeKey(K key);
    K decodeKey(byte[] bytes);
    byte[] encodeDocument(T document);
    T decodeDocument(byte[] bytes);
}
```

Names and signatures above are frozen for Phase 1 fixtures. Methods must reject null;
codec IDs are 1–128 ASCII characters matching
`[a-z0-9][a-z0-9._-]*`, and versions are non-negative. Encoded bytes must be
deterministic for the same logical value and codec version. Every accepted stored value
has canonical round-trip bytes: encoding its decoded value produces identical bytes.
Decode must not depend on ambient time, locale, process identity, mutable global state,
or Java native serialization.

The engine copies returned byte arrays, checks configured length limits before decode,
and treats codec exceptions as explicit codec/storage failures. Independent consumer
fixtures must encode, reopen in a new process, decode, and round-trip representative
values.

## Key/document consistency

Each persisted mutation contains the encoded business key separately from document
bytes. After decode, `schema.idOf(document)` must equal the decoded key under normal
key equality. A mismatch fails the mutation before sequence allocation or fails open
during recovery. The engine never silently substitutes one identity for the other.

Codec equality is logical, not byte-reference identity. Object identity, transient
fields, class-loader state, and original object references are not durable promises.

## Storage identity

`DurableStorageConfig<K,T>` requires and exposes the exact builder/accessor surface
frozen in [API compatibility](API_COMPATIBILITY.md):

- local storage `Path`;
- non-empty stable `storageIdentity` chosen by the application;
- non-empty stable `schemaIdentity` chosen by the application;
- the durable codec and its ID/version;
- maximum encoded key and document byte lengths;
- maximum bulk element count and decoded document count;
- automatic checkpoint WAL-byte threshold; and
- maximum retained engine-owned bytes.

Storage and schema identities use the same 1–128 character pattern as codec IDs. They
are exact, case-sensitive persisted strings. They are not derived from lambda classes,
reflection order, `hashCode`, serialized Java metadata, or class names. The caller
increments an identity or codec version when a persisted meaning is not
backward-readable.

## Schema and index configuration

Field extractors and custom analyzers are executable behavior and cannot be reliably
fingerprinted. The application-supplied schema identity asserts that the current
schema/extractors interpret persisted documents compatibly. In addition, the engine
persists the ordered supported index descriptors and rejects disagreement.

Built-in descriptors have stable engine-owned kind IDs. Built-in analyzers have stable
engine-owned analyzer IDs and configuration bytes. A custom analyzer or custom
`IndexDefinition` is supported by in-memory mode but rejected by durable open/create;
V4.0 defines no caller extension SPI for persisted index behavior.

At fresh creation, the ordered builder index descriptors become the persisted
bootstrap configuration. On reopen, the caller supplies the same bootstrap descriptors
and schema identity; mismatch fails. Recovery then applies persisted dynamic create/
drop transitions to obtain the current index set, so callers do not manually rewrite
the builder after each dynamic change.

## Safe bounds

All lengths and counts are validated with checked arithmetic before allocation.
Configured limits must be positive and within implementation hard caps recorded in
the format appendix. Lowering a limit below existing data makes open incompatible;
raising a limit does not reinterpret existing bytes.
