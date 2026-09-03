# GeneralSearchEngine V4.1 development charter

- **Status:** Proposed governing charter for protected Phase 0 acceptance
- **Predecessor:** Published GeneralSearchEngine `4.0.0`
- **Theme:** Operational Safety

## Purpose

V4.0 proves that a live durable GSE history survives supported process and machine
failures when its persistent block device survives. V4.1 addresses the next boundary:

> How can an operator safely inspect, back up, restore, and maintain that history
> without weakening V4.0 fail-closed guarantees?

V4.1 is neither a retrieval-feature release nor a distributed-durability release.

## Governing principles

1. Published V4.0 durability and V3.4 retrieval semantics remain frozen.
2. Backup, verification, restore, and cleanup are explicit supported operations.
3. A backup identifies one exact durable sequence, not filesystem timing.
4. A complete backup is independently restorable; incremental and deduplicated
   backup are deferred.
5. Operational tooling never silently repairs authoritative corruption.
6. A source history remains authoritative until a restored target is independently
   verified.
7. Restore creates a new history in an absent target while preserving the backed-up
   logical sequence.
8. V4.1 does not change the live-store format `gse-durable (1,0)`.
9. Structural validation does not claim semantic decode or retrieval correctness.
10. Independent parsers, local process crashes, fake cloud, durable media, and
    replacement-host recovery are first-class architecture from Phase 0 onward.

## Scope

V4.1 adds:

- a typed live-engine full-backup API;
- a checkpoint-only backup consistency protocol;
- a versioned immutable `gse-backup (1,0)` bundle;
- deterministic content identity and SHA-256 member integrity;
- codec-free offline store and backup structural verification;
- codec-aware backup and restored-state semantic verification;
- typed offline restore into an absent target;
- new-history restore with source provenance returned and retained by the backup;
- offline dry-run-first cleanup of proven non-authoritative members;
- stable verification reports and operational failure categories;
- backup, restore, verification, and cleanup diagnostics;
- interruption testing at every authority boundary;
- replacement-host restore and source-loss cloud evidence;
- migration guidance from published `4.0.0` APIs.

## Explicit exclusions

- incremental, differential, deduplicated, or resumable backup;
- backup streaming to arbitrary remote transports as product semantics;
- in-place restore or overwrite of an existing target;
- replication, remote synchronous commit, or zero-RPO guarantees;
- consensus, sharding, cross-process writers, or history merge;
- live format `gse-durable (1,0)` field/member changes;
- automatic format, schema, or codec migration;
- heuristic repair, committed-WAL skipping, guessed checkpoint reconstruction, or
  salvage into the same history;
- persisted derived indexes;
- a separately published command-line/tool artifact;
- new matching, scoring, ordering, highlighting, pagination, or snapshot semantics.

## Product surface

V4.1 separates application-aware and codec-free responsibilities.

### Typed Java operations

The core artifact supplies immutable request/result types and:

- an asynchronous `DurableSearchEngine.backup(...)` operation over a running durable
  engine;
- typed semantic backup verification requiring the application schema and codec;
- typed offline restore requiring the target durable configuration and schema;
- immutable restore results exposing the new history, source history, source backup
  identity, and restored sequence.

The exact source-level family is frozen by the Phase 0 contract. These additions are
opt-in and cannot affect an in-memory engine or an application that does not invoke
them.

### Codec-free offline operations

The core artifact supplies read-only structural verification and plan-bound cleanup.
These operations can parse format identities, inventories, sizes, checksums,
authority, and sequence relationships without loading application classes. They do
not claim that application documents decode or that retrieval results are correct.

V4.1 does not add a third Maven artifact or promise a general CLI. Repository scripts
may exercise the public Java surface and provide independent evidence, but scripts are
not a substitute for the supported API.

## Backup model

A supported backup represents exactly one durable logical state at sequence `B`:

```text
accepted live backup request
    ↓ writer-ordered bounded cut at B
force and publish checkpoint state at B
    ↓ pin checkpoint against cleanup
resume later mutations
    ↓ copy immutable metadata/checkpoint into target staging
write canonical inventory and SHA-256 identity
    ↓ publish completion manifest last
atomically finalize target directory
    ↓ independent structural and typed semantic verification
complete backup future
```

The baseline is a full checkpoint-only bundle. No growing live WAL belongs to the
bundle. The dedicated backup operation must not infer success from an unrelated or
coalesced checkpoint request.

## Restore model

Restore consumes a complete structurally and semantically verified backup:

```text
verified gse-backup (1,0)
    ↓ absent target and sibling staging directory
decode logical checkpoint with supplied codec/schema
    ↓ allocate a new non-zero history identity
encode ordinary gse-durable (1,0) metadata/checkpoint/manifest/WAL
    ↓ validate the staged target
atomic staging-directory rename and parent-directory force
    ↓ normal buildDurable/open and semantic oracle
```

The restored target is a normal V4.0-readable live store. It does not gain provenance
fields or sidecar members. Source history and backup digest remain authoritative in
the immutable backup and are returned in a diagnostic restore result. Operators may
persist a receipt outside the live directory, but that receipt is not live-store
authority and its absence cannot invalidate the target.

## Verification model

Structural verification is codec-free and classifies supported stores and bundles as
valid, valid with proven safe remnants, incompatible, incomplete, corrupt, or
unsupported. It is independent from production recovery and never truncates,
rewrites, or deletes bytes.

Semantic verification is an additional typed step. It validates codec/schema
identities, decodes every canonical key/document, rebuilds required indexes, and
compares the restored state and retrieval behavior with an independent oracle.

An offline live-store verifier requires a closed store and exclusive ownership. A
completed immutable backup may be verified concurrently by multiple readers.

## Safe cleanup model

Cleanup is offline, explicit, and dry-run-first. A cleanup plan binds to the exact
directory, history/operation identity, authoritative manifest digest, and member
inventory observed during planning. Apply reacquires exclusive ownership and rejects
a stale plan before deleting anything.

Cleanup may remove only members proven non-authoritative by accepted format rules.
Unknown, ambiguous, corrupt authoritative, or identity-mismatched members cause
refusal rather than partial cleanup. Parent-directory scanning, deletion by age, and
glob-based deletion are unsupported.

## Failure and lifecycle model

- Backup failures leave source authority unchanged when its durability remains known.
- Only one backup may be active per engine; a second request fails rather than
  coalesces.
- Readers continue throughout backup. Later mutations resume after the bounded cut
  and do not enter the bundle at `B`.
- An accepted backup participates in engine close: close stops new admissions and
  waits for the accepted backup to finish before releasing storage ownership.
- Restore and live-store verification/cleanup require offline exclusive ownership.
- A crash before final directory publication leaves only a recognizable incomplete
  staging candidate.
- A crash after final publication but before future/method completion is
  indeterminate to the caller; independent verification resolves whether the
  operation completed.
- No failed operational command makes the live engine terminal unless source
  durability itself becomes ambiguous under the inherited V4.0 rules.

## Performance and capacity philosophy

V4.1 measures, separately:

- writer pause and consistency-cut duration;
- checkpoint and total backup duration;
- bytes read/written and backup amplification;
- source mutation/search impact during copy;
- structural and semantic verification time;
- restore materialization and first-open time;
- retained source bytes while a checkpoint is pinned;
- staging and final target disk demand;
- cleanup planning/application time;
- large-corpus heap and disk bounds.

Live `maxRetainedBytes` continues to govern engine-owned live bytes. It does not count
an external backup target, but backup/restore perform their own overflow-safe size and
usable-space preflight and fail closed when bounds cannot be established.

## Local crash and cloud evidence

The implementation program does not postpone infrastructure until backup and restore
are finished.

Phase 1 establishes independent bundle/state models, stable artifact schemas,
child-process crash modes, a fake cloud control plane, exact cleanup assertions, and
pre-change evidence. Every later authority transition adds a stable crash barrier and
expected-state fixture in the same change.

The cloud family is independent from the V4.0 durable benchmark:

- suite: `v4.1-operational-safety-suite-v1`;
- preset: `v4.1-operational-safety-v1`;
- eventual immutable registration: `v4.1.0-operational-cloud`.

Canonical execution uses serial independent members under the existing quota-safe
model. It creates a source store, exports a verified backup to durable transport,
destroys or detaches source authority, restores to a new empty persistent disk on a
replacement VM, verifies logical and retrieval equivalence, continues mutations, and
proves cleanup. GCS is transport/evidence retention only; it is not live WAL or live
store authority. Exact workload sizes and paid duration are calibrated and frozen in
Phase 1 before any paid run, within the Phase 0 resource and cost envelope.

## Phase order

| Phase | Scope | Exit boundary |
|---|---|---|
| 0 | freeze scope, backup/restore/verifier/cleanup/API/evidence contracts | documentation only; protected acceptance required |
| 1 | open `4.1.0-SNAPSHOT`; pin published 4.0; models, fixtures, crash/fake-cloud scaffolding, baseline | no production operational implementation |
| 2 | codec-free offline structural verification and reports | read-only fixtures and classification matrix pass |
| 3 | live checkpoint-only backup and immutable bundle | cut, pin, identity, interruption, and lifecycle gates pass |
| 4 | typed semantic verification and new-history restore | restored-state/retrieval and atomic-finalization gates pass |
| 5 | plan-bound safe cleanup and operational integration | no authoritative deletion across full failure matrix |
| 6 | scale, performance, source-loss, replacement-host, and canonical cloud evidence | reviewed eligible evidence and immutable registration |
| 7 | final candidate, consumers, compatibility, Javadocs, artifacts, reproducibility | exact-master release gates pass |
| 8 | signed publication and post-publication proof | Central, release, deployment, consumer, and evidence identities close |

## Release gates

V4.1 requires:

- no V4.0 durability or V3.4 retrieval regression;
- unchanged readable live format `gse-durable (1,0)`;
- deterministic independently verified backup identity;
- exact-sequence full backup and new-history restore;
- typed semantic and independent structural oracles;
- interruption-safe backup, restore, verification, and cleanup;
- no authoritative-data deletion by cleanup;
- bounded large-corpus behavior and measured source impact;
- replacement-machine recovery after source authority is unavailable;
- published-4.0 compatibility and clean external-consumer evidence;
- signed post-publication verification.

## North star

> GeneralSearchEngine V4.1 makes the V4 durable store operationally safe to verify,
> back up, restore, and maintain while preserving every inherited V4.0 fail-closed
> guarantee.
