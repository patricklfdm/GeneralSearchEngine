# GeneralSearchEngine V4.3 Phase 1 foundation baseline

## Boundary

Phase 1 begins from protected Phase 0 merge
`d3b34010a26888dee18f3e01d2e8215e952f5ea7` (PR #119), whose exact-master CI run
`34435766321` passed. All eight active coordinates are `4.3.0-SNAPSHOT`.

This phase contains declaration fixtures, independent models, logical fixtures, a
separate-process crash scaffold, a no-GCP control plane, a published-4.2 diagnostic
and CI gates. It contains no production `(1,2)` constant, parser, writer, catalog,
component, inspection operation, reopen optimization, migration edge, paid workflow,
IAM change, cloud execution or registry entry.

## Published compatibility input

The exact Maven Central baseline is
`io.github.patricklfdm:general-search-engine:4.2.0`, main-JAR SHA-256:

```text
8dba2f09b861e3ed5fe7edde8226632c2248fe49582e0f3cb2c3fcb1cd958191
```

The artifact-compat profile resolves and checks this JAR in addition to all earlier
baselines and runs a published-4.2 Japicmp comparison. The standalone diagnostic uses
a fresh isolated Maven repository and never links against current production classes.
An independent-JVM rollback probe also reopens current Phase 1 default-format bytes
with only the published JAR and proves that inspection does not change their tree
digest.

## Independent model and immutable fixtures

`V43DerivedStateOracle` independently models equality, range, prefix and exact
`gse-simple-v1` text state. Equality/range groups select a live representative slot
that belongs to the canonical bitmap. Prefix keys and text terms use strict UTF-8
ordering. Text postings retain ordered document IDs, ordered positions and field
lengths. Input order cannot alter component identity.

`v43-derived-model-v1/` contains a checksummed, exact-inventory logical matrix for
older-format, absent, complete, partial, stale, incompatible, incomplete, corrupt and
interrupted publication states. It says `PHASE2_PENDING`: these are not fabricated
production bytes. The independent Python classifier validates canonical authority
separately and refuses any fixture that attempts to mask canonical corruption.

## API and numeric bounds

The declaration fixture freezes a 2 GiB default and 8 TiB absolute hard maximum for
derived-state allowance. The remaining internal Phase 2 bounds are frozen as:

| Bound | Value |
|---|---:|
| Catalog bytes | 16 MiB |
| Components/index descriptors | 100,000 |
| One component | 2 GiB |
| Total derived bytes | configured allowance, at most retained bytes |
| Value groups, terms, postings or positions per component | 100,000,000 each |
| UTF-8 identifier/term | 1 MiB |
| Findings | 100,000 |
| One finding / total diagnostic text | 4 KiB / 1 MiB |
| Refresh input | exact checkpoint snapshot, configured allowance |
| Temporary derived amplification | current generation plus one candidate generation |

All counters and additions are overflow-safe. Canonical checkpoint/WAL capacity has
priority. External process/VM/workflow timeouts bound operations operationally without
claiming that an individual filesystem call has a wall-clock limit.

## Crash and evidence scaffold

The stable initial barrier is `v43-phase1-derived-plan-no-output-v1`. A Python parent
launches a separate Java child and exercises both `Runtime.halt(89)` and external kill.
A second JVM independently proves canonical model bytes unchanged, derived state
absent, no graceful shutdown and no production `(1,2)` bytes. Evidence uses exact
schema `gse-v43-fast-reopen-evidence-v1`, canonical JSON, SHA-256 inventory and bounded
logs. Every production transition added later must add its stable barrier and expected
independent pre-open classification in the same change.

## Published-4.2 diagnostic

The local diagnostic used the exact checked published JAR with 20,000 documents, four
built-in indexes and five reopen samples:

| Measurement | Nanoseconds | Approximate |
|---|---:|---:|
| Minimum | 235,718,519 | 235.72 ms |
| Median | 343,941,594 | 343.94 ms |
| Maximum | 543,005,711 | 543.01 ms |

Published 4.2 necessarily rebuilds all four indexes on every reopen. These samples ran
serially in one JVM with operating-system page-cache state uncontrolled and likely
warm; they are not cold-device evidence or a user SLA. They prove that reopen work is
measurable and establish the control implementation. Phase 6 must use per-member,
same-machine, same-corpus paired forced-rebuild/warm measurements and report page-cache
state explicitly.

## Frozen no-paid cloud plan

| Control | Phase 1 value |
|---|---|
| Suite / preset | `v4.3-fast-reopen-suite-v1` / `v4.3-fast-reopen-v1` |
| Profiles | experiment `1`, canonical `3`, failure drill `1` |
| Scheduling | independent serial members; cleanup before the next member |
| Machine / peak CPU | Standard `c3d-standard-30` / `30` vCPU |
| Persistent disks | `pd-balanced`, 200 GiB primary; one sequential 200 GiB target |
| Peak regional SSD | 400 GiB |
| Filesystem | `ext4`, mount options `defaults` |
| Corpus / indexes | 100,000 documents, 16 tokens/document, four built-in kinds |
| Mutations | 10,000 |
| Measurement / maximum runtime | 1,800 / 5,400 seconds per member |
| Maximum complete-run cost | USD 25 |
| Retention | experiment/failure drill `actions`; canonical `gcs` |
| GCS prefix | `v4.3-fast-reopen/<source>/<run>-<attempt>/<profile>/member-<slot>/` |
| Future workflow | `v43-fast-reopen-evidence.yml@refs/heads/master` |
| Environment | `cloud-benchmark` |

The ten frozen cells are published-4.2 forced rebuild, current-source forced rebuild,
complete warm, structured partial fallback, text partial fallback, catalog/full
fallback, checkpoint-plus-WAL warm reopen, restored cold then warm, migrated cold then
replacement-host warm, and continued mutation/index lifecycle/reopen.

Final canonical acceptance retains the Phase 0 minimum: complete-warm median no more
than `0.50` of paired current-source forced rebuild and no member above `0.65`, plus
complete semantic equality, bounded space and full cleanup. No paid workflow or IAM
mutation is authorized before Phase 6 and explicit user confirmation.

## Local commands

```bash
./mvnw -q -Dtest=V43PublicApiFoundationTest,V43DerivedStateOracleTest test
scripts/verify-v43-phase1-foundation.sh --skip-build
scripts/verify-v43-published-v42-baseline.sh
scripts/verify-version-alignment.sh 4.3.0-SNAPSHOT
scripts/verify-consumer-projects.sh
./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh 4.3.0-SNAPSHOT
scripts/verify-reproducible-build.sh
scripts/verify-jmh-smoke.sh
```
