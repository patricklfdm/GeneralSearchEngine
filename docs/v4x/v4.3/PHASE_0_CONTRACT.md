# GeneralSearchEngine V4.3 Phase 0 fast-reopen contract

- **Phase:** 0 — Fast-reopen contract freeze
- **Status:** Candidate for protected acceptance
- **Reference baseline:** Published GeneralSearchEngine `4.2.0`
- **Production V4.3 implementation:** Authorized only by the owning later phase

## Authority and interpretation

This document is the normative V4.3 contract. The
[development charter](DEVELOPMENT_CHARTER.md) defines the release boundary, and the
[Phase 0 checklist](PHASE_0_CHECKLIST.md) records whether every required decision is
explicit. A conflict with a published V4.0, V4.1, or V4.2 guarantee blocks Phase 0;
it is not an implicit amendment.

Normative terms `MUST`, `MUST NOT`, `SHOULD`, and `MAY` have their ordinary standards
meaning. Examples are explanatory unless they repeat an explicit requirement.

## Exact predecessor identity

The predecessor is signed tag `v4.2.0` at protected-master commit
`5742b01def2fa5b1dd84b57f00ba6026c661f634`. Exact-master CI run `34388796604`
passed before tagging. Maven Central contains:

```text
io.github.patricklfdm:general-search-engine:4.2.0
io.github.patricklfdm:general-search-engine-processor:4.2.0
```

GitHub Release `385924091` and production deployment `6361088014` resolve to that
commit. Append-only baseline `v4.2.0-migration-cloud` is bound to source
`d0afbb593ab5df468c0b7c4b2622ebc6daa69317`, canonical run `33906942139`, and set
digest `57abb5394a537faaf551b9182ae5a1669de4703689dfe91e6e08dcd4580f2d75`.
The deployment history retains release workflow `34415073641`'s post-upload Central
polling timeout and verified-success reconciliation `18088668544`; no artifact was
redeployed.

Phase 1 MUST resolve published `4.2.0` artifacts from a fresh isolated repository and
pin their API, live/backup formats, migration behavior and immutable fixtures. Reactor
output, the current working tree, or a mutable downloaded cloud workspace is not a
substitute.

## Inherited guarantees

V4.3 inherits without reinterpretation:

- immutable search snapshots, lock-free readers, one authoritative writer, atomic
  publication, and all V3.4 retrieval behavior;
- V4.0 force-before-completion, contiguous logical units, bulk atomicity, incomplete-
  Future crash indeterminacy, checkpoint authority, WAL recovery, corruption fail-
  closed behavior, and bounded retained storage;
- V4.1 structural and semantic verification, exact-cut backup, new-history restore,
  plan-bound cleanup, operational classification, and source-loss evidence;
- V4.2 exact `(1,0)`/`(1,1)` readability, explicit format selection, profile binding,
  source-preserving offline migration, absent-target publication, transform rules,
  operator-owned cutover, and rollback; and
- the in-memory default, two-artifact release boundary, public Java compatibility,
  storage identities, schema/codec identities, and built-in durable-index limits.

A derived image MUST NOT alter which logical units are committed, what canonical
documents exist, which index descriptors are configured, or how a query matches,
scores, orders, paginates, highlights, or explains a result.

## Terms

- **canonical authority:** metadata, the current authoritative checkpoint relation,
  canonical checkpoint documents/index descriptors, and contiguous post-checkpoint
  WAL required to recover the durable logical state.
- **C:** the sequence of the authoritative checkpoint to which an image generation is
  bound.
- **derived catalog:** one non-authoritative atomically published inventory of image
  components for checkpoint `C`.
- **component image:** one non-authoritative bounded logical encoding of one built-in
  index snapshot at `C`.
- **warm reopen:** an open that admits at least one validated component image.
- **complete warm reopen:** an open that admits every checkpoint index component and
  rebuilds none at checkpoint `C`.
- **partial fallback:** an open that admits at least one component and deterministically
  rebuilds at least one rejected or absent component.
- **full fallback:** an open that admits no component and rebuilds all configured
  indexes from canonical documents.
- **cold target:** a valid `(1,2)` restored or migrated store with no admissible
  derived catalog.
- **refresh:** generation and atomic publication of a new derived catalog/components
  from one already verified immutable checkpoint snapshot.
- **image generation:** the complete catalog plus its referenced components.
- **stale image:** intact derived bytes whose history, checkpoint, profile, schema,
  codec, descriptor set, generator, or canonical checkpoint binding differs.

## Non-goals

V4.3 MUST NOT introduce authoritative indexes, Java serialization, arbitrary custom-
index persistence, silent upgrade, online migration, downgrade, repair, salvage,
source deletion, automatic cutover, history merge, persisted cursors, query caches,
memory mapping, off-heap search, lazy readiness, partial-snapshot serving, replication,
multiple writers, remote live storage, new retrieval semantics, or a third artifact.

## Exact format policy

V4.3 recognizes:

```text
gse-durable (1,0)
gse-durable (1,1)
gse-durable (1,2)
```

and matching backup minors `(1,0)`, `(1,1)`, and `(1,2)`.

`(1,0)` and `(1,1)` bytes and member policies remain immutable. Default durable
configuration remains `(1,0)`. Fresh `(1,2)` creation requires explicit selection;
opening any existing store requires an exact configured format. Selecting `(1,2)`
against `(1,0)` or `(1,1)` MUST fail before recovery or write and MUST NOT migrate.

The `(1,2)` format profile is a new canonical profile. It retains the V4.2 canonical-
state, checkpoint, WAL, logical-index and profile-binding capabilities and adds one
required capability for reconstructible derived index images. The capability permits
the exact derived member families and fallback semantics; it does not make presence of
an image mandatory. Optional capabilities remain empty for V4.3.

Same-major higher minor and unknown required capabilities are incompatible. Malformed
known `(1,2)` canonical bindings are corrupt. Malformed, stale, or absent derived
bindings have a separate derived-state result and MUST NOT change a canonically valid
store's structural status to corrupt.

Phase 2 freezes exact magic, byte order, field order, bounds, capability spelling,
profile bytes/digest, minimum sizes and immutable fixture hashes. Phase 0 authorizes
no format implementation.

## Authority separation

The canonical authority set for `(1,2)` is the same logical set as `(1,1)`. The
following are always non-authoritative:

- the current derived catalog;
- every referenced component image;
- any catalog/component staging file;
- any unreferenced recognized prior image generation; and
- diagnostics about image load, rebuild, refresh, or cleanup.

Deleting every derived member from an otherwise valid closed `(1,2)` store MUST leave
a valid, fully recoverable store. Copying only derived members MUST never form a store,
backup, checkpoint, or recovery authority.

Canonical structural verification MUST validate canonical authority independently.
Derived inspection MUST be a separate report. A valid store may therefore report
canonical `VALID` together with derived `ABSENT`, `PARTIAL`, `STALE`, `CORRUPT`, or
`INCOMPATIBLE` and still reopen by rebuilding.

If canonical authority is invalid, open fails under inherited reasons before image
admission. A valid image MUST NOT mask a missing sequence, corrupt checkpoint, invalid
WAL, codec failure, schema mismatch, or canonical index-descriptor mismatch.

## Derived member model

One `(1,2)` store may contain:

```text
gse-derived-manifest
gse-derived-manifest.staging
gse-derived-index-<20-digit-checkpoint>-<5-digit-ordinal>-<32-hex-generation>.idx
gse-derived-index-<...>.idx.staging
```

Phase 2 freezes the exact generation-token source and placement but MUST retain
separate manifest and per-index components, deterministic descriptor ordinals,
unambiguous staging suffixes, bounded names, and no collision with canonical V4
families. A generation token distinguishes repeated refresh attempts; it is not a
canonical-state or semantic image-content identity.

The catalog binds at least:

- family/major/minor and exact format-profile digest;
- history identity and checkpoint sequence `C`;
- authoritative checkpoint filename, byte length, stored checksum and SHA-256;
- storage, schema and codec identity/version;
- image generator identity/version;
- complete canonical index-descriptor list and count;
- one ordered entry per persisted component containing descriptor ordinal/kind,
  filename, byte length, component checksum and SHA-256; and
- a domain-separated catalog checksum and SHA-256 identity.

Each component repeats enough header identity to prevent substitution across stores,
histories, checkpoints, descriptors, ordinals, profiles, schemas, codecs, or generator
versions. Catalog and component disagreement rejects the component or generation.

No timestamp, hostname, PID, absolute path, Java class name, object hash, randomized
map order, compression timestamp, or filesystem enumeration order participates in a
content identity.

## Supported index images

Durable mode already supports only these persisted logical descriptors:

1. equality;
2. range;
3. prefix over `String`; and
4. text using exact `SimpleAnalyzer` identity `gse-simple-v1`.

All four MUST have stable logical image encodings by V4.3 completion. No change to the
public `IndexDefinition`, `IndexSnapshot`, `IndexBuilder`, `Field`, or `TextField` SPI
is required from third-party implementations.

### Equality and range

V4.3 MUST NOT serialize arbitrary extracted Java values. Each non-null distinct value
group is represented by:

- the smallest live document ID in that group as its representative;
- a canonical strictly increasing bitmap of all document IDs in the group; and
- bounded statistics needed to reproduce the exact snapshot.

On load, the representative document is already present in canonical decoded slots.
The configured field extractor recovers the Java value. The representative MUST be
live, MUST belong to the bitmap, and MUST extract a non-null value. Equality groups
use strictly increasing representative document ID. Range groups additionally use
the runtime field ordering required by the published range semantics and reject
duplicate compare-to-equivalent groups.

### Prefix

Prefix image keys are strict UTF-8 strings in canonical byte order. Each key maps to
a canonical strictly increasing bitmap. Null values remain unindexed. The loaded
snapshot MUST reproduce published prefix candidates and statistics.

### Text

Text images bind exact SimpleAnalyzer identity and encode strict UTF-8 terms in
canonical order, document frequency, postings, positions, field lengths, document
count, total field length, and vocabulary structures required by published term,
phrase, BM25, prefix/fuzzy and estimation behavior. Posting document IDs and positions
are strictly increasing and bounded. No source text or highlight payload is added
solely for the image.

### Common invariants

Every document ID is within `[0,nextDocId)`, is live when required, and appears at most
once where uniqueness is required. Counts and statistics are overflow-safe and agree
with decoded content. Unknown kind/version, trailing bytes, non-canonical order,
duplicate entries, bound violations, checksum/digest mismatch, or descriptor mismatch
rejects that component.

Image validity is structural and identity-bound. Phase 3–5 differential tests MUST
also prove complete query results, score bits, order, estimates, statistics, mutation,
dynamic create/drop, checkpoint, close, and reopen equivalence against forced rebuild.

## Reopen algorithm

Every `(1,2)` open follows this order:

1. acquire inherited exclusive storage ownership;
2. validate metadata, format/profile, checkpoint manifest, checkpoint and WAL
   authority exactly as if no image existed;
3. decode canonical checkpoint keys/documents and reconstruct document-ID mappings;
4. inspect the optional derived catalog without repairing it;
5. admit only exact catalog/components bound to the authoritative checkpoint;
6. materialize admitted checkpoint index snapshots;
7. deterministically rebuild every absent/rejected checkpoint index from the decoded
   canonical checkpoint documents;
8. if the checkpoint image was absent or rejected, make one synchronous bounded
   best-effort refresh attempt from this exact checkpoint snapshot, never from later
   WAL-derived state;
9. replay all post-checkpoint WAL logical units in contiguous sequence over the same
   complete snapshot model, including dynamic index create/drop;
10. complete all invariants and publish one process-local immutable version-zero search
   snapshot; and
11. expose immutable reopen diagnostics.

Canonical checkpoint decode remains mandatory. The accelerator skips index extraction,
tokenization, postings/bitmap construction, and equivalent derived work only.

No reader or writer may observe state before step 10. If materializing an admitted
component fails, that component MUST be discarded and rebuilt once. If fallback
rebuild succeeds, open succeeds with a bounded diagnostic. If fallback rebuild fails,
open retains the inherited `INDEX_REBUILD_FAILURE`; the image failure is secondary
context and cannot replace the primary cause.

Post-checkpoint WAL replay MUST produce exactly the same snapshot as rebuilding from
the final canonical state. A valid image at `C` never authorizes skipping WAL units.
Refresh during reopen always remains bound to `C`; it never serializes the final
post-replay snapshot under the checkpoint's identity.

## Publication lifecycle

Image generation consumes one immutable checkpoint capture and one exact descriptor
set. It MUST NOT read a mutating live snapshot piecemeal.

The minimum publication sequence is:

1. canonical checkpoint authority is fully published and parent-forced;
2. compute each component under independent hard byte/count/work bounds;
3. create a unique component staging file with `CREATE_NEW`;
4. write, checksum, force, rename, and parent-force that component;
5. independently reopen/validate every proposed component;
6. write and force the catalog staging file;
7. atomically replace/publish the catalog and force the parent directory;
8. independently re-read the published catalog and components; and
9. only then classify components not named by the current catalog as cleanup
   candidates.

A catalog MUST never name an unforced component. Before catalog publication, new
components are unreferenced remnants. After successful fixed-catalog replacement,
components not named by the new catalog are remnants. At every crash point, canonical
authority remains independently recoverable.

The inherited `checkpoint()` Future completes according to canonical checkpoint
semantics. For exact `(1,2)`, it completes only after one bounded best-effort refresh
attempt downstream of canonical checkpoint publication. Derived generation may delay
neither force-before-completion nor durable mutation publication. A refresh failure
after canonical checkpoint success is recorded but MUST NOT fail or make that
checkpoint Future indeterminate.

After a cold restored/migrated target or fallback rebuild, V4.3 MUST make one
synchronous bounded best-effort refresh attempt for the decoded checkpoint snapshot
before open returns. Refresh failure is diagnostic and open still succeeds after a
successful rebuild. Open success proves the attempt completed, not that image
persistence succeeded. V4.3 adds no background refresh queue or post-ready cache
publication.

## Backup and restore

An exact `(1,2)` store produces exact `gse-backup (1,2)`. The bundle retains exactly
three canonical members and excludes derived catalog, components, staging files and
diagnostics. Its content identity uses a new domain-separated algorithm rather than
extending `gse-backup-content-v2`.

Backup sequence and Future semantics remain V4.1. Image generation cannot block or
fail backup after its canonical cut succeeds. Source derived bytes are neither copied
nor included in the bundle's maximum byte accounting.

Restore validates the canonical bundle and publishes an absent new-history `(1,2)`
target with no derived members. The restored target is cold. Its first open MUST prove
the complete canonical oracle through deterministic rebuild and only then make the
contracted refresh attempt.

Published V4.2 MUST reject exact `(1,2)` live and backup formats fail-closed according
to its immutable parser. V4.3 continues verifying/restoring exact `(1,0)` and `(1,1)`
without creating images for them.

## Migration continuity

V4.3 preserves every V4.2 migration rule and edge. It adds these direct edges:

```text
(1,0) -> (1,2)
(1,1) -> (1,2)
(1,2) -> (1,2)  only with a meaningful declared change
```

`(1,0) -> (1,2)` is an explicit registered direct encoder, not an internal
`(1,0) -> (1,1) -> (1,2)` chain. Planning and apply remain offline, typed,
source-preserving, absent-target, new-history, bounded, independently verified and
operator-cutover-owned. Downgrade and reverse migration remain unsupported.

The migration target contains canonical `(1,2)` authority only and is cold. Derived
bytes are excluded from the plan projection identity, target-authority identity,
source byte identity, and migration success. First target open rebuilds and then makes
the contracted refresh attempt. Source derived files remain untouched with every
other source byte.

## Public API ownership

All V4.3 product API remains in `general-search-engine`. No new Maven module, service
provider, reflection-loaded image codec, or supported general-purpose CLI is added.

`DurableStorageFormat` and `DurableBackupFormat` gain exact public `(1,2)` constants.
The existing format value constructors and validation remain unchanged.

`DurableStorageConfig.Builder<K,T>` gains one positive bounded derived-state byte
allowance with a safe default frozen in Phase 1. It is meaningful only when the exact
configured format is `(1,2)`. Explicitly setting the allowance while selecting
`(1,0)` or `(1,1)` MUST fail builder validation rather than being silently ignored.
Existing source that does not invoke the addition retains the same defaults and
behavior.

`DurableStorageOperations` gains one additive synchronous codec-free derived-state
inspection operation and immutable report family. It does not change components or
enum order in published verification/format/cleanup reports.

`DurableSearchEngine` gains one additive default diagnostic capability returning an
optional immutable last-reopen report. Independent implementations that do not adopt
V4.3 remain source/binary compatible and return absence by default. V4.3 MUST NOT add
constructor parameters or components to published `DurabilityMetrics`.

Phase 1 freezes exact public type/method/constant names, generic bounds, builder
default and hard maximum, record/class components, enum order, optionals, validation,
null behavior, equality/hash/toString expectations and Javadocs before production
format or image code exists.

## Inspection and classification

V4.3 adds a codec-free offline derived-state inspection family. It requires exclusive
ownership of a live store and never invokes production recovery, decodes documents,
repairs, deletes, or refreshes.

The immutable report exposes at least:

- normalized directory;
- derived status;
- optional declared live format/history/checkpoint sequence/catalog identity;
- catalog/component counts;
- referenced, admissible, rejected, staging and unreferenced byte totals;
- ordered per-component descriptor/status/size/digest information; and
- bounded, payload-free, canonically ordered findings.

The frozen status order is conceptually:

```text
NOT_APPLICABLE
ABSENT
VALID
PARTIAL
STALE
INCOMPATIBLE
INCOMPLETE
CORRUPT
```

Phase 1 freezes exact public names and enum order. `NOT_APPLICABLE` covers exact older
formats. `ABSENT` is a valid `(1,2)` store with no catalog. `VALID` means every
checkpoint descriptor has one admissible component. `PARTIAL` means at least one but
not all components are admissible. Catalog-level stale/incompatible/incomplete/corrupt
classification rejects the generation as a whole.

## Reopen diagnostics

V4.3 MUST NOT add components to published `DurabilityMetrics` or reorder a published
enum. A separate immutable report records at least:

- authoritative checkpoint and final recovered sequence;
- total checkpoint indexes, loaded components, rebuilt components, and replay-created
  indexes;
- derived classification and bounded rejection codes;
- canonical load, derived inspection/load, rebuild, WAL replay, refresh and total
  open durations;
- derived bytes read/written and whether refresh was attempted/succeeded; and
- complete-warm, partial-fallback, full-fallback, or not-applicable outcome.

`DurableSearchEngine` gains only an additive default diagnostic method returning an
optional report. Existing independent implementations may return absence. Diagnostics
are observations, not query or durability authority.

## Resource and failure policy

Phase 1 freezes positive hard bounds for:

- derived generation bytes and total retained bytes;
- catalog size, component count, per-component bytes and total derived bytes;
- term/value-group/posting/position/bitmap counts;
- string lengths, finding counts/text, and evidence output;
- synchronous refresh work/bytes and temporary amplification; and
- local/cloud process, VM, disk, workflow and cost duration.

All arithmetic is overflow-safe. Work is bounded by counts and bytes; as with
canonical checkpoint force, V4.3 makes no wall-clock guarantee when a filesystem call
itself stalls. Workflow/process maximum runtime remains an external operational bound.
Canonical WAL/checkpoint space has priority. If an
image cannot fit the configured derived allowance or observed usable space, it is
omitted and reopen rebuild remains available. ENOSPC, short write, force failure,
rename failure, directory-force failure, changed inventory, or cleanup failure in
derived state MUST NOT retroactively fail a canonical checkpoint or mutation.

Unchecked JVM-fatal conditions are not converted into success. Normal runtime/image
exceptions are bounded, recorded without document values or credentials, and either
fall back or leave canonical state ready for the next process.

## Cleanup and remnant policy

V4.1 dry-run-first plan binding governs cleanup. V4.3 extends the recognized live-store
inventory only for exact `(1,2)` derived families. Planning MUST bind canonical
authority, current valid catalog identity, every observed member size/SHA-256, real
paths, link relationships and the complete delete set.

Cleanup may remove only:

- component/catalog staging files proven unreferenced;
- recognized components not named by the current valid catalog.

It MUST NOT remove the current catalog, a referenced component, canonical authority,
an unknown member, an ambiguous alias, or anything after inventory changes. A corrupt
catalog grants no deletion permission for otherwise ambiguous components. Apply
recomputes the plan and forces the directory, while canonical verification before and
after must agree.

## Crash and fault matrix

Every production transition adds a stable barrier in the same change. Required barrier
families include:

- before/during/after component staging write;
- before/after component force, rename and parent force;
- during component independent validation;
- before/during/after catalog staging write and force;
- immediately before/after catalog publication and parent force;
- during published-generation reinspection;
- before/during/after fallback reconstruction and refresh;
- before/during/after superseded-image cleanup; and
- after a complete image generation but before any reporting/Future/close boundary.

Fault injection includes short write/read, truncation, bit corruption, swapped files,
stale checkpoint/history/profile/schema/codec/generator/descriptor binding, duplicate
ordinal, missing component, unknown kind, malformed UTF-8/order/count/bitmap/posting,
ENOSPC, force/rename/delete failure, permission denial, concurrent close/checkpoint,
WAL after image sequence, and retained-byte enumeration races.

For every crash/fault, an independent parser runs before production open and records
canonical status plus derived status. A replacement JVM then either performs the
contracted warm/partial/full path or fails only for an independently demonstrated
canonical/rebuild cause, verifies the complete retrieval oracle, continues mutation,
checkpoints, closes, and reopens again.

## Compatibility matrix

| Producer / operation | Published 4.2 | V4.3 |
|---|---|---|
| default fresh durable store | `(1,0)` | `(1,0)` |
| open/write exact `(1,0)` | supported unchanged | supported unchanged, no images |
| open/write exact `(1,1)` | supported | supported unchanged, no images |
| explicit create/open `(1,2)` | incompatible/unavailable | supported |
| verify/restore backup `(1,0)` and `(1,1)` | supported | supported unchanged |
| verify/restore backup `(1,2)` | incompatible | supported, cold restore |
| V4.2 migration edges | supported | supported unchanged |
| direct migration to `(1,2)` | unavailable | explicit offline edges only |
| derived inspection/reopen report | unavailable | additive |

Published `4.2.0` becomes the pinned Japicmp, source/binary consumer, live/backup
format, migration, operations and rollback baseline. Existing V1–V4.2 consumers and
the default in-memory/durable paths remain valid.

## Evidence architecture from Phase 1

### Required foundation

Before production `(1,2)` or image behavior, Phase 1 MUST add:

- declaration-only API fixtures and an independently compiled V4.3 consumer;
- fresh-repository published-4.2 compatibility and rollback probes;
- independent canonical document/index/image models for all four built-in kinds;
- exact logical or handcrafted physical fixtures for valid, absent, partial, stale,
  corrupt, incompatible and interrupted image states;
- a separate-JVM parent/child harness with stable modes, barriers, exit codes and
  checksummed artifacts;
- a Python or equivalently independent byte inspector that never calls production
  recovery;
- deterministic cold/warm/partial/full oracles and fault controls;
- no-GCP fake orchestration with serial-member cleanup and failure receipts; and
- a calibrated workload/cost plan based on measured published-4.2 cold rebuild.

### Evidence identities

```text
local artifact schema  gse-v43-fast-reopen-evidence-v1
cloud suite            v4.3-fast-reopen-suite-v1
cloud preset           v4.3-fast-reopen-v1
eventual registration  v4.3.0-fast-reopen-cloud
```

No V3, V4.0, V4.1, or V4.2 baseline is overwritten, relabeled, or treated as a V4.3
member.

### Frozen measurement cells

Each evidence member records separately:

1. published-4.2 forced canonical rebuild;
2. current-source `(1,2)` forced full rebuild;
3. complete warm reopen;
4. one structured-component rejection and partial fallback;
5. one text-component rejection and partial fallback;
6. catalog rejection and full fallback;
7. complete warm checkpoint-plus-WAL reopen;
8. cold restored-target first open followed by refreshed second open;
9. cold migrated-target first open followed by refreshed replacement-host open; and
10. continued mutation, dynamic index create/drop, checkpoint, close and reopen.

Every cell records corpus/index identity, live/slot counts, encoded canonical bytes,
image bytes, temporary peak, heap, GC, CPU, filesystem/device/cache state, checkpoint
and WAL sequences, bytes read/written, stage durations, result checksum and cleanup.
OS page-cache state is explicit; a warm-derived comparison MUST NOT be relabeled as a
cold-device result. Benchmark-only forced-rebuild controls MUST NOT become supported
product API, and evidence reports both recovery-ready time before refresh and complete
open-return time when a cold/fallback path performs refresh.

### Acceptance thresholds

Phase 1 freezes numeric thresholds after running the published-4.2 local diagnostic,
before production optimization. At minimum, final canonical acceptance requires:

- complete result/checksum equality for every cell;
- zero canonical failure caused solely by derived absence/corruption;
- bounded retained and temporary bytes with no canonical-space starvation;
- complete cleanup and three comparable members; and
- median complete-warm total open time at most 50% of the paired current-source forced
  full-rebuild median on the same member, with no member regressing that paired ratio
  above 0.65. Phase 1 may tighten but MUST NOT weaken this minimum without a reviewed
  Phase 0 amendment.

The threshold is a release evidence gate, not a portable user SLA. If Phase 1 data
shows the workload cannot measure the intended bottleneck reliably, the workload may
be amended only in a reviewed documentation change before production image code.

### Cloud topology

Experiment uses one member; canonical uses three independent serial members. Each
member uses one Standard VM and one persistent data disk, creates a canonical indexed
store, records cold and warm paths, detaches the disk, and verifies warm reopen plus
fallback on a replacement VM. Restore/migration targets use distinct bounded disks
only when their cell runs; resources are deleted before the next member.

Serial scheduling MUST respect the established project boundary of 32 global vCPUs
and 500 GiB regional SSD. Phase 1 freezes exact machine/image/zone, disk type/size,
filesystem/mount, corpus, indexes, durations, maximum runtime, maximum complete-run
cost, retention, GCS prefix, OIDC workflow allowlist, artifact schema, cleanup order,
and job summary.

GCS is immutable evidence transport only. It is never a live store, image authority,
checkpoint, WAL, or cache source. Paid runs occur only in Phase 6 after local smoke,
fake cloud, dry-run, exact-source CI, cost validation, explicit user confirmation and
verified resource cleanup behavior.

## Phase ownership

| Phase | Authorized work | Explicitly not yet authorized |
|---|---|---|
| 0 | these documents and indexes | version/code/tests/harness/workflow/IAM/paid changes |
| 1 | `4.3.0-SNAPSHOT`, published-4.2 gates, API fixtures, models, immutable fixtures, crash/fake-cloud scaffolding, pre-change calibration | production `(1,2)` or images, paid runs |
| 2 | public declarations, exact `(1,2)` and backup bytes, derived codecs/inspection and independent parsers | production image-assisted open |
| 3 | explicit `(1,2)`, structured images, fallback/refresh and direct migration edges | text images |
| 4 | text images and complete selective fallback | paid evidence or speculative tuning |
| 5 | lifecycle, crash/fault/capacity/concurrency/backup/restore/migration/cleanup and published-4.2 hardening | paid evidence |
| 6 | scale profiling, experiment/canonical cloud, review and append-only baseline registration | unmeasured semantic change |
| 7 | final coordinates, consumers, compatibility, Javadocs, artifacts, reproducibility and release docs | publication |
| 8 | signed tag, Central, deployment, GitHub Release and remote proof | later-version work |

## Phase 0 exit gate

Phase 0 exits only when the checklist confirms:

- predecessor identity and every inherited guarantee are pinned;
- explicit `(1,2)`, unchanged default/older formats, and backup/migration continuity
  are exact;
- canonical and disposable derived authority are unambiguously separated;
- all four built-in logical image models avoid arbitrary Java serialization;
- catalog/component binding, publication, selective fallback, refresh, retained bytes,
  cleanup and crash states are frozen;
- canonical open/replay/Future/failure semantics remain unchanged;
- additive inspection/diagnostic API ownership and compatibility are explicit;
- Phase 1-first independent fixtures, crash harness and fake-cloud lane are frozen;
- workload cells, provisional performance gate, cloud isolation, cost, retention and
  paid-run authorization are explicit; and
- phase ownership prevents implementation from preceding its evidence foundation.

After protected acceptance, Phase 1 may open `4.3.0-SNAPSHOT`, pin published `4.2.0`,
and implement only declarations, independent models/fixtures, harnesses, fake-cloud
planning and pre-change calibration. Production format/image code remains prohibited
until its owning phase.
