# Phase 3 original export resource bindings

The [development evidence index](phase3-evidence/export-resources.json) retains
the exact runtime/test inputs, original collections and replay hashes. This adds
resource bindings for native frozen-source, record and current-prefix exports.
Phase 3 remains OPEN.

## Original content and local reservation identity

The three CONTROL owner names now include their original content digest plus a
fresh allocation UUID. The digest supplies correlation; the physical reader
supplies authority. Names remain within the existing 128-character bound. No
wire or disk record, quota, deadline, registry limit or public API changes.

| Export | Binding derived from original bytes | Existing reserved extent |
| --- | --- | --- |
| Frozen source | Forced BASIS digest | Original PROMISE length plus BASIS length |
| Record | Exact retained record digest | That record's byte length |
| Current prefix | Original generation manifest digest | 4096 bytes of control metadata |

The frozen source's existing physical packet/images remain owned by their
original storage reservations. The prefix reservation is metadata for a borrow,
not another application image or a full generation copy. A fresh UUID prevents
two exports of the same content from becoming one accounting lifetime.

## Native component execution

Three histories start with the public bootstrap API at stable sizes 3, 4 and 5.
Each opens a native journal and forces one real PROMISE/BASIS pair. On that same
owner, two modes overlap one source, record and prefix export and read their
original content: explicit close, then expiration using an injected clock.
There is no authority reset between modes. Clock rollback and duplicate close
must not revive a released export. File inventories remain unchanged after the
original grant, and every budget reaches zero after owner close.

These are 18 export allocations, not 18 distributed histories. The record tested
by the independent reader is the original PROMISE; other record kinds have
existing Java regressions but are not promoted to this new physical scope.
There is no network exchange or view transition in these three histories.

## Independent replay

```bash
python3 -m scripts.v53.export_resource_evidence RAW
python3 -m scripts.v53.export_resource_negatives RAW
```

The reader first reconstructs bootstrap storage, the actual native grant,
captured/after file inventories and exact exported bytes using the existing
source-export physical reader. It derives all three expected bindings and
extents from those admitted originals. The producer's usage totals are checked
against the complete resource transition stream.

Constructor/close observation points delimit the actual allocations and release
calls. All three exports must overlap the completed reads. Every allocation has
one unique identity, immutable extent and release within its corresponding call.
The original storage baseline must remain continuously owned; equal counters
before and after cannot excuse a release/reacquisition gap. Exactly six exports
must be accounted for in each original, including both modes. Legacy UUID-only
names cannot satisfy this new binding requirement.

Sixteen resource mutations per original require exact rejection reasons, after
the unchanged physical precondition passes. They cover failed/incomplete scope,
call order, boolean boundaries, stale totals, wrong content/size, legacy names,
missing/extra/reused allocations, an original-storage gap, premature release
return, reads after release and incomplete observation. Mutation works on copies
of accounting/history observations; the physical originals and derived content
expectations remain unchanged. These are resource-layer negatives, not 48 new
native fault executions.

The clock behavior and successful reads are exercised by Java. These accounting
records do not independently qualify a real-time deadline or all read-return
boundaries. The reader reports those limits explicitly. The [vote and ROOT follow-up](PHASE_3_SPECIAL_EXPORT_RESOURCES.md) adds those
direct families. Joining-specific exports, direct-versus-session ownership
composition, complete native network integration, physical peaks and final-source
qualification remain pending.
The 12 Phase 3 requirements and 544 planned hosted histories are unchanged.
