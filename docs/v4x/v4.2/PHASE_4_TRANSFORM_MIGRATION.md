# GeneralSearchEngine V4.2 Phase 4 typed transform migration

Phase 4 completes the typed migration semantics frozen in Phase 0. A migration may
now change codec, schema, business-key, storage, transform, or target-index identity
while preserving one-to-one logical history and the source authority.

## Supported edges

The production planner admits only:

```text
gse-durable (1,0) -> gse-durable (1,1)
gse-durable (1,1) -> gse-durable (1,1) with a declared identity or index change
```

The first edge may use either `identity-format-v1@1` or a declared versioned typed
transform. The second edge requires at least one changed storage, schema, codec,
codec-version, transform, or ordered durable-index identity. An exact same-format,
same-identity copy is rejected as `MIGRATION_NOT_REQUIRED`. Downgrades, `(1,0)` to
`(1,0)`, unknown formats, and hidden multi-hop conversions remain unsupported.

## Typed projection

Planning decodes every canonical source record and invokes the transform exactly once
in source slot order. Every source record must produce one non-null target key and
document. The target schema must extract the returned target key, encoded key bytes
must be globally unique, and both key and document must round-trip through the target
codec canonically. Phase 4 permits target bytes to differ from source bytes only for
a declared non-identity transform.

The projection preserves document count, slot order and holes, durable sequence, and
`nextDocId`. It binds the target format profile, complete target storage descriptor,
transform descriptor, ordered target indexes, target history, and canonical encoded
records. Planning constructs the target indexes in memory so an extractor failure is
reported before filesystem publication.

## Index rebuild and plan binding

Target indexes are exactly those declared by the target builder. The plan reports
canonical sorted `added`, `removed`, and `retained` descriptor sets; apply rebuilds
those indexes from transformed canonical documents. Derived index contents remain
non-authoritative and are never copied from the source.

The target descriptor digest covers format, storage/schema/codec identities, codec
version, every configured bound, format-profile digest, and ordered index
descriptors. The plan digest additionally covers source and target paths and formats,
source-member hashes, histories, sequence, transform, projection, capacity estimate,
safety reserve, collision bound, finding bound, and diagnostic bound. Apply validates
that request and plan binding before invoking the transform, then repeats the full
projection and requires exact equality.

## Failure rules

Null output, thrown transforms, target-key/schema disagreement, exact encoded-key
collision, target encode/decode disagreement, and target-index extraction failure are
`TRANSFORM_FAILURE`. Projection disagreement between plan and apply is
`TRANSFORM_NONDETERMINISTIC`. Changed request bounds, target configuration, target
indexes, or plan fields are `PLAN_STALE`. These failures create no final target and
never mutate the source.

Diagnostics expose only bounded stable categories; application keys, documents, and
exception payloads do not enter the public message. Exact encoded bytes, rather than
hash-only equality, decide target-key collisions.

## Independent and crash evidence

The independent migration oracle now covers changed schema, key, codec, transform,
and index identities as well as same-format index evolution. A separate-JVM catalog
scenario materializes a true integer-key legacy source and migrates it to a string-key
catalog target with different binary bytes and rebuilt equality/prefix indexes.

The production harness abruptly halts before final rename and after parent force. A
fresh verifier requires the source to remain byte-identical in both cases; the final
target must be absent before publication and a typed, searchable, sequence-preserving
`(1,1)` store afterward. Evidence remains in the Phase 1-frozen
`gse-v42-migration-evidence-v1` family.

## Deliberate exclusions

Phase 4 does not add online or in-place migration, record filtering/fan-out, automatic
cutover, source deletion, remnant cleanup, rollback automation, broad repeated-fault
hardening, paid cloud execution, performance claims, or baseline registration. Those
lifecycle and evidence responsibilities remain assigned to Phases 5 and 6.
