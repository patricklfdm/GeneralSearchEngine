# V5.0 public-admission Step A foundation

- **Status:** Accepted through [PR #153](https://github.com/patricklfdm/GeneralSearchEngine/pull/153), master `855cfde29f3538121fa711e840f8701ded68c6a9`, [CI 35006998165](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35006998165)
- **Branch:** `feat/v5.0-public-admission-foundation`
- **Starting master:** `716f06f6bb04dcbf86e775eb93b4f7f31799739a`
- **Contract:** [Accepted amendment](PUBLIC_ADMISSION_CONTRACT.md), [ordered A/B/C plan](PUBLIC_ADMISSION_ENTRY_PLAN.md)
- **Bytes:** [Exact 1.1 specification](PUBLIC_ADMISSION_FORMAT_1_1.md)

## Accepted starting boundary

| Change | Protected merge | Exact-master CI |
| --- | --- | --- |
| Phase 5 internal runtime hardening | [PR #150](https://github.com/patricklfdm/GeneralSearchEngine/pull/150), `4a8fd3dfd9e398d712e896c9af511cf55f4cb16e` | [34956076066](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34956076066) |
| Public-admission contract/API amendment | [PR #151](https://github.com/patricklfdm/GeneralSearchEngine/pull/151), `72ea9a6b176a7371d708cea1d84ad8d603adef61` | [34960589647](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34960589647) |
| Documentation CI classification and pressure-harness catch-up admission | [PR #152](https://github.com/patricklfdm/GeneralSearchEngine/pull/152), `716f06f6bb04dcbf86e775eb93b4f7f31799739a` | [34965248513](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34965248513) |

PR #152's master run completed Change scope, Reactor tests, Compatibility, Release
artifacts, Cloud runner (no GCP) and Required successfully. Its Phase 1–5 steps
actually executed, including deterministic pressure/recovery hardening. These are
predecessor receipts, not acceptance of the current uncommitted implementation.

## Delivered boundary

Step A adds the exact API declarations from PR #151 and freezes the independent 1.1
byte projections that Steps B/C must implement. Constructors validate pure arguments
and copy lists. Existing V4 engine construction, durable restore/backup and processor
behavior is unchanged. Published baselines, historical 1.0 goldens and existing
API descriptors are retained. The POM changes only compatibility verification: the
old V4.3/V4.4 zero-addition gate now permits exactly the approved core handoff delta.

`configuration()`, `newBuilder()`, the core transfer methods and typed offline
operations at the Step A boundary throw `UnsupportedOperationException` before codec execution,
files, engine startup or threads. The three new interface defaults do the same,
preserving third-party implementations. The existing replicated builder and legacy
under-specified bootstrap overloads remain reserved. Step B implements configuration
capture and offline authority in its [separate report](PUBLIC_ADMISSION_OFFLINE_AUTHORITY.md); Step C admits the complete public engine.

## Exact API review

The inventory tests compare the full current replication surface against new v2
fixtures and separately compare the v1→v2 difference against checked-in signed-line
deltas. They require every old declaration except the explicitly amended constant
to survive. Nothing silently broadens the old fixture or ignores new declarations.

| Surface | Old → new |
| --- | --- |
| Core values | Add `SearchEngineConfiguration<K,T>` and `DurableApplicationState<T>` with the exact accepted components |
| Core operations | Add `SearchEngineBuilder.configuration/readDurableBackup/writeDurableBackup` and `SearchEngineConfiguration.newBuilder` |
| Replication values | Add `ReplicationBootstrapRequest`, `ReplicationBootstrapResult`, `ReplicationCleanupPlan`, `ReplicationReplacementPlan`, `ReplicationPeerStatus`, `ReplicationDiagnostics` |
| Offline operations | Add the three typed bootstrap overloads, `readBootstrapResult`, `planCleanup/applyCleanup`, `planReplacement/applyReplacement/resumeReplacement` |
| Interface | Add default `catchUp`, `reconstructConfiguredLeader`, `replicationDiagnostics` |
| Unpublished V5 constant | `ReplicatedSearchEngines.PROTOCOL`: `gse-replication/1.0` → `gse-replication/1.1` |
| Existing constructors/components/method descriptors | All retained |
| Published core/processor API fixtures | Unchanged |

Machine-reviewable exact declarations:

- [Historical replication signatures v1](../../../general-search-engine-replication/src/test/resources/compatibility/v50-replication-public-signatures-v1.txt)
- [Current replication signatures v2](../../../general-search-engine-replication/src/test/resources/compatibility/v50-replication-public-signatures-v2.txt)
- [Exact replication delta](../../../general-search-engine-replication/src/test/resources/compatibility/v50-public-admission-signature-delta.txt): 131 added lines, one removed line (the old constant value)
- [Pre-amendment core builder signatures](../../../general-search-engine-replication/src/test/resources/compatibility/v50-core-handoff-signatures-v1.txt)
- [Current core handoff signatures](../../../general-search-engine-replication/src/test/resources/compatibility/v50-core-handoff-signatures-v2.txt)
- [Exact core delta](../../../general-search-engine-replication/src/test/resources/compatibility/v50-core-handoff-signature-delta.txt): 32 added lines, no removed lines

The artifact-compat profile additionally compares the **entire** public core JAR
against both checksum-pinned V4.3/V4.4 baselines using the existing javap inventory
reader and a new [exact approved delta](../../../src/test/resources/compatibility/v50-core-approved-javap-delta.txt).
Its verify-phase Ant execution must pass before japicmp. Japicmp retains all binary
and source incompatibility failures; only its blanket `breakBuildOnModifications`
flags for V4.3/V4.4 become false because the stricter exact-delta gate covers allowed
additions. Extra additions, removals or changed signatures fail the new guard; unit
negatives exercise these cases. No artifact coordinate, dependency or published
baseline changes. This resolves the initial expected failure of the old zero-change
policy when it encountered the two newly authorized core records.

The new core historical handoff fixture was captured by compiling the unchanged
SearchEngineBuilder source from starting master `716f06f` in an isolated temporary
class directory and reflecting that class. It is an additional local comparison,
not regeneration of a published V4 core/processor baseline.

An outside-package test compiles a consumer against **only core classes**, covering
all handoff signatures without replication on the classpath. The separate v5-style
Maven consumer compiles the typed offline/admin API against installed production JARs.
Another test compiles a consumer against the historical constant, loads it beside the
new library and verifies that its stale inlined 1.0 value rejects in a 1.1 wire frame.

## Format fixtures and independent checks

The checked-in catalog has **5 positive and 48 negative cases**. Both Java and Python
read its exact bytes and compare the same expected history/base/snapshot sequence
and manifest/genesis digests. Neither test invokes a production decoder or rewrites
expected bytes. A SHA-256 inventory freezes the catalog itself.

Positive cases are EMPTY, backup provenance from 1.0/1.1/1.2, and imported base
Long.MAX_VALUE−1. Each includes the three initial payload inventories, manifest,
genesis, plan, preparations, complete global receipt, local seals, chained operation
rows, zero and nonzero snapshots/proofs, and every wire registry ID. Administrative projections also freeze cleanup/ABORTING,
replacement plans/journals, origin-1 NODE and rebuilding records; negatives reject
protected-source deletion, post-commit aborts, changed replacement inventories and
premature voter/group-commit claims. These `admin-*` catalog labels are independent
pre-commit/replacement examples, not permitted physical node filenames. Ordered source
keys are intentionally 3 then 1, so key sorting cannot masquerade as source order.
Snapshots demonstrate S, S+1, S+1, S+1 for genesis, ADD, NO_OP, SNAPSHOT_MARKER.

Negative cases include source hash/history collisions, changed genesis and manifest,
legacy header/inlined protocol/embedded ENTRY, duplicate preparations, inventory
mismatch, absent/wrong local seals, seal-before-decision and ambiguous COMMITTING,
torn/broken journals, wrong base/application/control sequence, arithmetic overflow,
conflicting terminal proof, changed index-zero data, unsafe/stale plan inputs and
malformed wire identity/payload. Some negatives recompute the outer checksum, so
rejection must come from field or cross-record validation rather than SHA alone.

The synthetic source members freeze provenance bytes and bindings only. They are
not runnable V4 backups or proof of V4 search semantics. Actual published V4.4 source
reading/export, full 1.1 production codecs, replacement/cleanup execution, filesystem
forcing/crash guarantees and standalone sealed startup still require B/C evidence.

## CI and local validation

`scripts/verify-v50-public-admission-foundation.sh` runs the reactor unless passed
`--skip-build`, checks the frozen catalog in Python, requires successful executed
Java declaration/format/inventory reports, and writes a result receipt under
`target/v50-admission-foundation`. Stale reports older than changed replication
sources/fixtures reject. CI runs it immediately after the reactor and always uploads
the foundation receipt and Java reports. Required depends on the reactor job as before.
Existing Phase 1–5 steps stay enabled for full CI; documentation-only behavior from
PR #152 remains unchanged.

Local checks on this candidate:

| Check | Result |
| --- | --- |
| Full reactor, plus final focused declaration/format/core-only compile checks | PASS; core, replication and processor tests passed |
| Step A Java/Python agreement | PASS; 5 positive + 48 negative byte cases, stale compiled constant rejection, immutable/reserved declarations and exact inventories |
| V5 Python suite | PASS; 78 tests |
| Phase 1–5 process gates | PASS; Phase 4 has 17 process cases + 6 corruption cases, Phase 5 has 16 hardening cases |
| Published API compatibility | PASS; frozen api-compat consumer, artifact-compat against V1–V4.4, and exact approved whole-core delta |
| Independent V1–V5 consumers | PASS, including typed admission signatures against installed JARs |
| Release packaging/Javadocs | PASS; nine JARs, explicit exclusion of test oracles/fixtures/workers |
| Reproducibility | PASS; nine JARs byte-identical across two clean release builds |
| CI classifier + published V4.4 fixture tests | PASS; 20 tests |
| Workflow/shell/docs | actionlint, shell syntax, local link checks and `git diff --check` pass |

Local raw phase evidence was archived before clean compatibility/release builds at
`/tmp/gse-v50-public-admission-evidence/phase-evidence.tar.gz`; it includes this run's
five phase workspaces and Step A receipt/Java reports. Final focused Java reports and
an updated Step A receipt are regenerated under `target/v50-admission-foundation`.
Local evidence is explicitly marked as an uncommitted working tree. Protected PR and
exact-master acceptance were subsequently supplied by PR #153 and CI `35006998165`.

## Scope and next gate

Changed production files are the two new core records, SearchEngineBuilder, six new
replication records, ReplicatedSearchEngine(s), ReplicationStorageOperations and the
internal ReplicaWire protocol literal. The latter pins historical 1.0 execution while
the public constant advertises the accepted future 1.1 protocol. Remaining changes
are tests, consumers, independent fixtures/readers, the CI step, exact-delta
compatibility verification, nine-JAR fixture-exclusion checks and documentation.
No public bootstrap/runtime is enabled and no paid cloud work is started.

- [x] Contract/CI-fix predecessor merges and exact-master receipts verified.
- [x] Exact approved API declarations and visible v1→v2 inventory delta supplied.
- [x] Complete 1.1 byte specification and independent frozen positive/negative cases supplied.
- [x] Protected Step A PR #153 merged.
- [x] Step A exact-master CI `35006998165` executed successfully.
- [x] Step B offline-authority implementation started after those two receipts.
