# GeneralSearchEngine V4.4 Phase 1 foundation baseline

- **Entry:** protected Phase 0 acceptance `c59b828` / CI `34583543174`
- **Coordinates:** `4.4.0-SNAPSHOT`
- **Published control:** Maven Central `4.3.0`
- **Production behavior change:** none
- **Paid cloud work:** none

## Boundary

Phase 1 establishes the executable evidence system required before V4.4 may classify
a product finding. It changes development coordinates, tests, fixtures, scripts,
documentation and bounded CI only. It does not change `src/main`, add public API,
introduce format `(1,3)`, create a paid workflow, mutate IAM, provision GCP, register a
baseline or claim Phase 2 matrix coverage.

The frozen machine-readable plan is [`phase1-plan.json`](phase1-plan.json). Logical
cases remain explicitly `PHASE2_PENDING`; the local process protocol operates on a
test-only model file and never presents it as production durable storage.

## Published 4.3 and closed API

The sole predecessor artifact is:

```text
io.github.patricklfdm:general-search-engine:4.3.0
SHA-256 c5ecf5cf311c734481e95f14bdcfffb466fa132dde424a2b6b4a58fe41778583
```

The `artifact-compat` profile resolves it from an isolated Maven repository, verifies
the digest and compares it with the current JAR. Unlike earlier compatibility gates,
the published-4.3 comparison uses Japicmp `breakBuildOnModifications`: additive public
API drift is rejected as well as source/binary incompatibility.

The independent inventory runs `javap -public -s -constants` over every public GSE
type. It canonicalizes member order to remove compiler-emission ordering differences,
but retains type declarations, signatures, descriptors and public constants. The
published artifact freezes:

| Field | Value |
|---|---:|
| Public types | 177 |
| Canonical declaration lines | 2,939 |
| Inventory SHA-256 | `d67f7f18795222d77c36d4e11ffdc913d1c9c8b6330ea9797b41f6f77d83650b` |

The current source JAR produces the same inventory. This inventory plus Japicmp makes
the V4.4 closed-surface rule executable without treating compiler member order as API.
Existing V1/V2/V3/V4 consumer projects now compile against `4.4.0-SNAPSHOT`; remote
published consumers remain a release-stage gate.

## Independent final matrix

The checksummed `v44-final-matrix-v1` fixture freezes ten complete-program families:
mutation/search, live authority, backup/restore, migration, derived reopen,
corruption, publication interruption, lifecycle/ownership, scale/resources and
replacement host. Twenty representative cases name their fault, expected result,
continuation requirement and one of the accepted independent oracle families.

The model distinguishes `PASS`, `FAIL_CLOSED`, `FALLBACK` and
`REJECT_BEFORE_MUTATION`. It also freezes the six finding classifications from Phase
0. It does not execute production transitions; Phase 2 must realize the complete
local matrix and classify its findings before any correction is proposed.

## Local process and evidence foundation

The new process-control scaffold begins with the stable test-only barrier
`v44-phase1-model-publication-v1`. The Python controller and Java child exercise seven
bounded paths:

1. graceful close;
2. `Runtime.halt(89)`;
3. external kill performed by a separate interrupter JVM;
4. startup failure before store creation;
5. injected I/O failure leaving staging but no canonical publication;
6. malformed canonical bytes; and
7. post-publication corrupt bytes.

Valid paths run writer, independent Python pre-open inspector, Java inspector, Java
recovery, Java continuation and a second Java inspection. They prove sequence `1`
continues to sequence `2`. The Java side validates CRC32C; the Python inspector has a
separate CRC32C implementation and validates exact member semantics before any
recovery role. Graceful and abrupt shutdown are distinguished by an external marker.
Every child has an external 15-second deadline.

Malformed/corrupt bytes fail closed. Startup and injected-I/O cases prove absence of a
canonical publication. The controller deletes its model workspace and writes a
strict, one-MiB-bounded, canonical-JSON evidence bundle using schema
`gse-v44-final-durable-evidence-v1`. Checksums, source identity, profile, bounded logs,
expected authority state and exact cleanup are independently validated.

This is process-control infrastructure, not a physical power-loss claim and not
production-format evidence. To prevent that scaffold from floating free of the real
engine, the Phase 1 verifier also executes the inherited production
`v4-wal-after-force-v1` barrier with an external kill, codec-free pre-open inspection,
separate recovery JVM, continued mutation and repeated reopen. That bridge retains
its original strict V4 evidence schema rather than being translated into a stronger
V4.4 claim. Phase 2 attaches the complete frozen matrix to the full set of real
inherited authority transitions.

## Paired pre-change calibration

One source file is compiled only against the checked published `4.3.0` API, then run
in isolated stores once with the published JAR and once with the current JAR. Both
use 20,000 deterministic documents, four built-in indexes, 1,000-document atomic
batches, an explicit checkpoint, three reopen samples and complete document plus
query/sequence checksums.

The pre-change local diagnostic on Linux WSL2, 20 logical CPUs, Intel i7-12700F,
Ubuntu OpenJDK `21.0.12+8` recorded:

| Runtime | Write | Reopen median | Semantic digest |
|---|---:|---:|---|
| Published 4.3 | 702,352,044 ns | 165,376,911 ns | `76588235…6848043` |
| Current source | 755,629,591 ns | 169,959,779 ns | `76588235…6848043` |

This single local sample is calibration only. Page cache was uncontrolled, the JDK is
not the canonical release distribution, and the timing is neither a regression
decision nor an SLA. It proves the published/current harness is genuinely isolated,
the semantic oracle is exact and the proposed 20,000-document frequent workload is
bounded. Canonical non-regression requires three paired members in Phase 6.

## Frozen workloads and thresholds

The dense workload uses seed `440001`, 20,000 documents, 16 tokens/document, four
indexes, 2,000 mutations, four readers, one writer, checkpoint cadence 500, backup
cadence two checkpoints, four migrations, one-GiB heap, G1 and a 180-second maximum.

The persistent workload uses seed `440002`, 100,000 documents, 16 tokens/document,
512-byte values, four indexes, 10,000 mutations, eight readers, one writer,
checkpoint cadence 1,000, backup cadence two checkpoints, six migrations, eight-GiB
heap, G1, 30-second progress and 3,600 measurement seconds. Warm and explicit cold
page-cache controls are reported separately.

Correctness/checksum/cleanup comparisons are exact. Lower-is-better ratios retain
median/member maxima `1.20/1.35`; higher-is-better ratios retain median/member minima
`0.80/0.65`. Phase 1 does not weaken the provisional Phase 0 gates.

## No-GCP cloud plan

| Control | Frozen value |
|---|---|
| Suite / preset | `v4.4-final-durable-suite-v1` / `v4.4-final-durable-v1` |
| Profiles | experiment 1 / canonical 3 / failure drill 1 |
| Scheduling | independent serial members; cleanup before next member |
| Machine | Standard `c3d-standard-30`, peak 30 vCPU |
| Image | `ubuntu-2404-noble-amd64-v20260906` |
| Disks | 100-GiB boot; 200-GiB source; at most one 200-GiB target |
| Peak provisioned disk | 400 GiB data / 500 GiB including boot |
| Filesystem | `ext4`, mount `defaults` |
| Persistent measurement / deadline | 3,600 / 10,800 seconds per member |
| Maximum complete-run cost | USD 40 |
| Retention | experiment/failure drill `actions`; canonical `gcs` |
| GCS prefix | `v4.4-final-durable/<source>/<run>-<attempt>/<profile>/member-<slot>/` |
| Future workflow | `v44-final-durable-evidence.yml@refs/heads/master` |

The fake lane models actual source-host deletion, independent pre-open inspection,
fresh replacement host, continued mutation/checkpoint/close/second reopen, per-resource
cleanup and zero leftovers. It does not create the future paid workflow or IAM grant;
those remain Phase 5 readiness and Phase 6 execution work.

## Canonical release toolchain

[`release-toolchain.json`](release-toolchain.json) chooses Phase 0 option 1: exact
canonical toolchain rather than archive normalization. Linux/amd64 is pinned to
official Eclipse Temurin `21.0.12_8-jdk-jammy`, OCI index digest
`sha256:887801…6f4605` and amd64 platform digest `sha256:4cfc63…6b29f7` over Ubuntu
22.04 base digest `sha256:281c57…79986`.

The manifest also binds Java `21.0.12+8`, Maven `3.9.11` distribution URL and SHA,
Wrapper `3.3.4`, all release-relevant plugin versions, `C.UTF-8`, UTC, umask `0022`,
output timestamp policy, two POMs and six unsigned JARs. Phase 1 validates identity
against repository POM/wrapper inputs. Phase 5 must execute independent-workspace
byte reproducibility under this container and bind the release workflow to it.

## Local commands

```bash
./mvnw -f reactor/pom.xml clean test
scripts/verify-v44-phase1-foundation.sh
scripts/verify-v44-published-v43-baseline.sh --skip-resolve
scripts/verify-v44-paired-baseline.sh
./mvnw -Dmaven.repo.local="$(mktemp -d)" clean -Partifact-compat verify
scripts/verify-consumer-projects.sh
./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh 4.4.0-SNAPSHOT
scripts/verify-reproducible-build.sh
scripts/verify-jmh-smoke.sh
```
