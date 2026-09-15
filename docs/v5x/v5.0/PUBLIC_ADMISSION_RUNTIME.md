# V5.0 public-admission Step C public runtime

- **Status:** Implementation candidate; protected PR and exact-master acceptance pending
- **Branch:** `feat/v5.0-public-runtime`
- **Starting master:** `915b79c4e197a262a3a8dbcc8d53b7b1a81f7c33`
- **Predecessor:** [Step B, PR #154](https://github.com/patricklfdm/GeneralSearchEngine/pull/154), [master CI 35020203126](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35020203126)
- **Contract:** [Public admission](PUBLIC_ADMISSION_CONTRACT.md), [accepted API](PUBLIC_ADMISSION_API.md), [frozen 1.1 bytes](PUBLIC_ADMISSION_FORMAT_1_1.md)

## Delivered behavior

`build()` captures the complete immutable application configuration and returns a
stopped handle without opening storage, starting threads, calling codecs or resolving
endpoints. `start()` shares one asynchronous attempt, exclusively owns and validates
the sealed 1.1 authority, reconstructs imported genesis even at LogIndex zero, and
starts the existing bounded private-network transport. Startup does not activate.
Each caller receives an independent future; cancelling it does not cancel startup.
Close racing startup prevents publication and keeps ownership until cleanup finishes.

Configured-leader activation shares its ordered recovery barrier. Repeating a READY
activation preserves the incarnation. Normal activation rejects a replacement leader;
explicit reconstruction requires both surviving voter identities. Catch-up explicitly
recovers a configured peer and returns its verified LogIndex. No election, promotion
or automatic catch-up is introduced.

All application methods, including inherited bulk/search/page/highlight/explain
overloads, enforce role and lifecycle before application codecs or queue admission.
Mutations occupy one application entry and retain bounded admission through actual
completion, including cancellation. The published view remains readable after quorum
loss; detected fencing, integrity failure or conflicting history revokes it. Schema
and field metadata remain available before startup and on followers.

Dynamic indexes require canonical schema field references. The frozen snapshot
format permits one active index per field; switching its kind requires dropping the
existing index first. Both checks reject before appending an entry or advancing the
application sequence.

Public checkpoint captures a resolved committed cut on the local writer. It works
on followers and isolated leaders, requires no remote ACK, adds no log entry and does
not advance the recovery floor. It retains old recovery sources; an unresolved suffix
or insufficient retained capacity rejects before deletion. The historical internal
quorum checkpoint remains available to the Phase 4/5 regression gate.

Backup exports a writer-ordered readable committed view through the core V4 transfer
API, preserving group application history, application sequence, live-document order
and active index definitions. Export preserves captured index field order for V4
metadata compatibility and canonically appends new fields. Core bundle exceptions
retain their original types. An absent backup target inside the owned replica authority
rejects as `TARGET_INVALID` before writing; existing targets retain `TARGET_EXISTS`. Cancellation never deletes an already published bundle.

Diagnostics expose a local snapshot, two peers in manifest order, observed and verified
progress, observation times, recovery floor and last quorum/failure information.
Probes are coalesced by request timeout, share bounded admission and transport limits,
and never synchronously block the getter or claim a fresh quorum. Durability metrics
report local entry-journal generation/records/bytes, actual recovery measurements and
application sequences. The numeric generation is the selected generation UUID's
nonnegative most-significant 63 bits; the original root journal is generation zero.

Public storage and wire records use 1.1 end to end, including receipt digest domains,
snapshot base sequence, generation selectors and top-level wire manifest identity.
Historical 1.0 internal tests and immutable fixtures remain version-specific. Public
startup cannot convert or open unsealed historical authority, and peers cannot mix
versions. Startup checks retained durable proofs against selected committed ancestry.
Absolute bootstrap paths remain provenance so a sealed volume can be attached at a
different safe local path; configured identity, application settings and numeric
bounds must still match the seal.

## Implementation and review map

| Area | Files |
| --- | --- |
| Deferred lifecycle and complete public delegation | `PublicReplicaEngine`, `ReplicatedSearchEngineBuilder` |
| Ordered activation, maintenance, observations and metrics | `ReplicaNode`, `ReplicaApplication` |
| Owned startup and retained proof validation | `ReplicaStore`, `AdmissionNode` |
| Explicit historical/public format selection | `ReplicaFormat`, `ReplicaManifest`, `ReplicaEntry`, `ReplicaProof`, `ReplicaSnapshot`, `ReplicaRecoveryImage`, `ReplicaGeneration`, `ReplicaTransfer`, `ReplicaWire` |
| Public behavior, races and frozen-byte agreement | `V50PublicRuntimeTest`, `V50PublicLifecycleTest`, `V50OfflineFixtureAgreementTest` |
| External consumer and separately compiled V4.4 oracle | `PublicRuntimeConsumer`, `PublicRuntimeWorkload`, `AdmissionSemanticModel`, `AdmissionV44Control` |
| Test-only process fault injection | `V50PublicRuntimeWorker`, package-private `ReplicaRuntimeHooks` |
| Independent inspection and executed gate | `scripts/v50/runtime_format.py`, `runtime_harness.py`, `test_runtime_format.py`, `scripts/verify-v50-public-runtime.sh` |

The public API inventory remains the accepted Step A inventory. Interface defaults
retain compatibility with third-party implementations. Step A/B evidence now labels
runtime as outside those gates' scope; the separate Step C gate proves enablement.

## Evidence and acceptance

The Step C gate compiles a consumer outside the implementation package against the
production core/replication JARs. Three concurrent owned JVMs use public APIs for all
bootstrap, lifecycle, application, maintenance and replacement work. The fault worker
only supplies internal event barriers and captures wire frames; it never initializes
authority or substitutes private runtime methods for public operations.

Pinned published V4.4 JAR SHA-256:
`0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5`.
The separately compiled control reports its loaded code source. Comparison covers
ordered documents, structured Boolean queries, ranking scores, phrase/fuzzy search,
pagination, explanation trees and highlight spans. All three V4 backup formats are
produced by the published control and exported by the public runtime for published
restore and semantic comparison.

Every process cut retains its PID, exit status, command receipts, raw wire frames,
pre-reopen archive and file hashes. Independent Python checks sealed identity, promise
order, entry ancestry, proof quorum and receipt domains, snapshot application sequence
offset, recovery floor and cross-node committed-prefix agreement. It never calls Java
decoders or repairs evidence. The gate refuses stale JARs or missing/skipped Java test
reports. CI runs it in `Reactor tests`, uploads evidence with `always()`, and preserves
the existing `Required` dependency and Phase 1–5 gates.

## Local validation (2026-09-15)

| Check | Result |
| --- | --- |
| Release reactor | 705 tests: 701 passed, four existing opt-in tests skipped; zero failures/errors |
| Step A | Five positive and 48 negative frozen fixture classifications passed |
| Step C public consumer | 21 cases passed: three V4 format round trips, four lost-response cases and 14 owned SIGKILL cuts; includes follower/leader replacement and local maintenance |
| Compatibility | `api-compat`, published `artifact-compat` and independent V1–V5 consumers passed; the final consumer used the same replication JAR hash below |
| Packaging | All nine release JAR checks passed; two clean release builds were byte-identical and the subsequent full reactor preserved those hashes |
| Step B and Phase 1–5 | All passed: 106 offline cases; historical storage, leader, recovery and hardening gates, including 16 Phase 5 cases |
| Static checks | Contract gate, workflow lint, shell syntax, 536 local links across 38 Markdown files and whitespace checks passed |

Final production JAR SHA-256 values:

- Core: `ac25695c3a446b2ea07e312164b6277f612610eeec2d33dc91f94a2316b0769f`
- Replication: `36691a127dc172ff3629f250941993b3245833204eb38f277a79dae876426352`

The Step C receipt is
`target/v50-public-runtime/run.kiPmDG/evidence/receipt.json`. It records the starting
master SHA, dirty-tree diff and source-inventory hashes, candidate/control JAR hashes,
Java report hashes and all case results. Final documentation records these completed
runs after their receipts were produced; implementation and tests remain unchanged.
The local handoff archive is
`/tmp/gse-v50-public-runtime-evidence/final-runtime-evidence.tar.gz`; it retains gate
logs, process evidence, Java reports, release JARs and the final changed-source inventory.
Protected PR/master acceptance remains pending; this candidate does not authorize
Phase 6 or paid cloud work.
