# Phase 2C5d — complete application image component

Status: **local component PASS; publication integration OPEN**.

The private image adapter retains the existing core durable backup metadata and
checkpoint bytes, including history, application sequence, document order, active
index order, codec/schema identities and storage configuration. It calls the real
core backup writer and structural/typed backup readers. It introduces no competing
document, index or search-operation codec and changes no legacy backup writer.

## Deterministic complete bytes

The existing manifest includes a wall-clock creation time and random request ID;
these administrative fields are excluded from its content identity. Independent
exports therefore differ byte-for-byte even for identical state. Only a **new image
byte array** normalizes time to zero and request ID to empty, recomputing the existing
CRC32C. The core reader accepts these existing-format values. External source files
and their metadata/checkpoint/manifest remain untouched. The original semantic
reader still checks profile, payload hashes, history, sequence and all typed data.

The private `GSAI` container has a 12-byte big-endian header (magic, major 1, minor 3,
body length), followed by three length-prefixed members in fixed order: checkpoint,
manifest, metadata. The **complete container**, including overhead, fits the frozen
64 MiB APPLICATION limit. Its hash covers every retained byte, including sequence.
This is not a new GSER/GSRP kind or a public durable-backup version.

Active index descriptors are extracted from original bounded metadata and resolved
through the unchanged replica descriptor semantics. They only configure the core
typed verifier; extraction by itself never validates an application. Different
formats, index orders or persisted configuration are different images. Later
bootstrap must compare actual bytes across targets, and the application owner must
preserve original images at unchanged cuts and choose deterministic new-state order.

## Filesystem and authority boundary

Read into an absent caller-supplied scratch directory; refuse overlapping/aliased
paths, occupied targets, unexpected members, links, changed inventories, hostile
lengths and noncanonical administrative fields. Reads use original inventoried
lengths before allocation. Failures preserve source/scratch evidence and never
recursively remove files or open a live WAL. The owner still must reserve scratch
and image capacity and bind the returned history/sequence/full hash to its verified
catalog. A decoded image is not a selector, certificate, checkpoint ACK or public
publication. Full publication/recovery and offline bootstrap remain pending.

## Retained validation

**293 Java tests passed**, including eight new image tests, the earlier V5.3 gates,
existing core transfer tests and V5.1/V5.2 application/rebuild/read-boundary checks.
Tests cover all three existing backup formats, independently generated exports,
exact source payload preservation, dynamic prefix/range/text indexes, history,
sequence including the core terminal value, document order, hostile framing,
corruption, identity/bound mismatches, occupied paths, links and source mutation
during codec decode. V5.3 owner-level counter admission remains separate.

The first focused run passed the new tests but its three socket-using compatibility
tests were blocked by the sandbox. The complete run used local-socket permission;
an intervening test-only lambda compilation error was corrected. All original logs
remain retained; neither failure is relabelled as a pass.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53*Test,V50ApplicationTransferTest,V51ApplicationRebuildTest,V52ApplicationWorkerTest,V52ApplicationReadCutTest,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
```

[Implementation/JAR/test index](phase2-evidence/application-image.json).
Raw validation: `target/v53-certified-publication/`. No physical crash, protected
CI, public runtime or cloud acceptance is claimed by this encoding component.
