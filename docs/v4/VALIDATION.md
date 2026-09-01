# V4.0 validation contract

The process-control and evidence-bundle details are normative in
[Crash harness and cloud durable lane](CRASH_HARNESS_AND_CLOUD_LANE.md). This document
defines the semantic case matrix that runs through that infrastructure.

## Oracle strategy

Durability tests use three independent views:

1. the published V3.4 engine as retrieval and mutation-semantic oracle;
2. a small history model that tracks keys, canonical slots, `nextDocId`, index
   configuration, logical units, and committed sequence; and
3. a byte-level storage inspector that does not invoke production recovery.

Production writer plus production reader is never accepted as its own sole oracle.

## Required functional matrix

The matrix covers fresh, WAL-only, checkpoint-only, checkpoint-plus-WAL, clean close,
and repeated reopen for add/update/remove, all bulk variants, successful no-ops, empty
bulk, supported startup indexes, dynamic create/install/drop/cancellation, and mixed
document/index histories.

Every recovered case compares documents, canonical slot/internal-ID order,
`nextDocId`, index existence, structured truth, ranked membership, score bits, order,
phrase/fuzzy/BOOL/BOOST, Explain, highlighting, exact totals, and applicable first
pages. Cursor reuse across restart must fail under the existing cursor contract.

## Process-crash matrix

Tests kill a separate JVM without close at deterministic barriers around:

- before sequence allocation and WAL append;
- after private candidate preparation but before sequence allocation;
- partial fixed header, payload, and trailer/checksum;
- complete write before and after force;
- after force before prepared-snapshot publication;
- after publication before Future completion;
- checkpoint data and manifest staging;
- sealed pre-cut generation and newly forced post-cut generation;
- checkpoint force before authoritative rename;
- authoritative rename before directory force;
- publication before WAL rollover/cleanup; and
- repeated recovery followed by new writes.

Assertions use the frozen incomplete-Future rule: every completed Future is present;
an incomplete Future may be present only if the inspected durable prefix contains its
valid committed unit. No batch prefix is accepted.

## Corruption matrix

Byte-level fixtures cover truncation at every structural region, bit flips, checksum
failure, invalid/overflowing lengths and counts, unknown types/versions, sequence gap/
duplicate/reorder, history mismatch, checkpoint/manifest truncation and checksum,
schema/codec mismatch, generation overlap, stale staging, and unrelated history files.

Only a physically incomplete newest terminal frame is recoverable. A complete invalid
terminal frame and any earlier invalid data must fail with the expected reason.

## Concurrency and lifecycle

Bounded multi-producer runs prove that producer concurrency never creates multiple
internal WAL writers or publishers. They validate sequence order, per-Future results,
group commit, queue drainage, reader snapshot consistency, close admission, terminal
I/O failure, capacity rejection, checkpoint coalescing, and recovery after abrupt kill.

## Platform and fault evidence

Local deterministic tests inject short writes, force failure, rename failure,
directory-force failure, deletion failure, decode failure, and capacity exhaustion.
Release evidence also includes abrupt JVM termination and at least one VM reset/kill
with the persistent local block device preserved and reattached. Graceful shutdown is
not crash evidence; physical disk loss is not claimed.

## Compatibility gates

- all published API baselines through exact Maven Central `3.4.0`;
- public descriptor/source fixture for the additive durable family;
- in-memory and durable independent consumers;
- strict Javadocs and artifact/service-boundary checks;
- immutable format `(1,0)` fixtures opened by every V4.0 release candidate; and
- negative consumers for unsupported custom indexes/filesystems and mismatched IDs.

## Phase acceptance

Each implementation phase records exact commit, Java/Maven/runtime environment,
commands, seeds, fixture hashes, passed/failed/excluded cases, and remaining gates.
No flaky rerun is silently substituted for evidence; infrastructure failure and product
failure remain distinct.
