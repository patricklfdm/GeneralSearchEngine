# GeneralSearchEngine V4.2 Phase 1 foundation baseline

## Boundary

Phase 1 begins from protected Phase 0 merge
`8391ea67e451da476f8dc8f7c25c3f78e3656173` (PR #106), whose exact-master CI run
`33830552115` passed. It opens all eight active coordinates as `4.2.0-SNAPSHOT` and
adds only compatibility, declaration fixture, independent logical model, immutable
fixture, separate-process crash scaffold, fake-cloud and evidence-plan infrastructure.

No production `gse-durable (1,1)` reader/writer, format selector, inspection report,
migration type, migration operation, physical migration member or paid workflow is
present in Phase 1.

## Published 4.1 compatibility input

The immediate Maven Central baseline is
`io.github.patricklfdm:general-search-engine:4.1.0`, pinned to SHA-256:

```text
36aa783cef653ead26d2500a847b70bb1f8222d224c8a83de55419de46814bcb
```

The isolated artifact profile copies and checks that exact JAR and adds a published
4.1 Japicmp comparison. Earlier published comparisons remain active. V1–V4
independent consumers compile against the reactor snapshot without changing their
source contracts.

## Frozen declarations and independent model

`V42StorageEvolutionPublicApi.java.fixture` and
[the API fixture contract](PHASE_1_API_FIXTURE.md) freeze format selection,
codec-free format reports, typed builder-owned migration, request/plan/result records,
transform cardinality, stage order and the distinct migration failure family. The
fixture compiles while reflection proves these types remain absent from production.

`V42MigrationOracle` models a source-preserving new-history projection independently
of production storage. It proves exact sequence and `nextDocId`, slot order, source
authority identity, target-history separation, plan/projection domain separation,
and independent apply re-execution. It refuses stale source state, unsupported/no-op
edges, sequence exhaustion, transform exceptions, key mismatch, collision and
invocation-dependent output.

## Immutable logical bytes and inspector

`src/test/resources/compatibility/v42-migration-v1/` contains checksummed canonical
JSON bytes for a `1.0` logical source, `1.1` logical target, `1.1` backup and migration
plan. The independent Python validator verifies exact inventory, hashes, formats,
profile capabilities, one-to-one ordered projection, distinct history, sequence,
`nextDocId`, transform descriptor, backup inventory and identity domains.

These are deliberately logical Phase 1 fixtures, not fabricated production `1.1`
member bytes. Every `1.1` model carries `PHASE2_PENDING`; Phase 2 owns exact metadata,
checkpoint, manifest, WAL and backup byte layouts plus immutable physical hashes.
This distinction satisfies Phase 1 model immutability without preempting Phase 2.

## Local crash and evidence foundation

The stable Phase 1 barrier is
`v42-phase1-migration-plan-no-output-v1`. A Python parent launches a separate Java
child and exercises both `Runtime.halt(88)` and external kill. A second JVM proves:

- the source model bytes are identical before and after interruption;
- the target remains absent;
- no graceful-close shutdown hook ran; and
- no production migration operation or `1.1` storage member exists.

Local and fake-cloud bundles use exact schema `gse-v42-migration-evidence-v1`,
canonical JSON, SHA-256 inventory, full source commit, bounded logs, explicit source
before/after identities and exact cleanup. Tampering fails closed.

## Calibrated no-paid cloud plan

| Control | Frozen Phase 1 value |
|---|---|
| Suite / preset | `v4.2-storage-evolution-suite-v1` / `v4.2-storage-evolution-v1` |
| Profiles | experiment `1`, canonical `3`, failure drill `1` |
| Scheduling | serial independent members; cleanup verified before the next member |
| Machine / peak CPU | Standard `c3d-standard-30` / `30` vCPU |
| Source / target disk | separate `pd-balanced`, `200 GiB` each; `400 GiB` regional peak |
| Filesystem | `ext4`, mount options `defaults` |
| Corpus | `100,000` documents, `16` tokens/document |
| Mutation workload | `10,000` before migration, `1,000` continued on target |
| Transforms | `identity-format-v1`, `catalog-schema-key-v1` |
| Measurement / maximum runtime | `1,800` / `5,400` seconds per member |
| Maximum complete-run cost | USD `25` |
| Retention | experiment/failure drill `actions`; canonical `gcs` |
| GCS prefix | `v4.2-storage-evolution/<source>/<run>-<attempt>/<profile>/member-<slot>/` |
| Environment | `cloud-benchmark` |
| Future workflow identity | `v42-storage-evolution-evidence.yml@refs/heads/master` |

The fake lifecycle closes the source writer before planning, keeps source and target
disks distinct, records source identity around migration, stops the first target host,
reattaches target authority to a replacement host, continues and reopens target,
stops target writing, then models published-4.1 rollback from the untouched source.
Source and target writers never overlap. GCS is transport/evidence only.

The future OIDC condition must retain exact repository, repository ID, owner ID,
protected `refs/heads/master`, the workflow identity above, and environment
`cloud-benchmark`. No IAM or workflow is changed in Phase 1. Paid execution and
baseline registration remain Phase 6-only after explicit confirmation.

## Pre-change evidence

Published V4.1 is the complete pre-change control:

- signed source `9db6efce275d25eb8da75d6532ea103982e591c6`;
- canonical operational source `88205cf28f1aa80f8ea7ccf1bada723b3205215c`;
- canonical run `33758217508`;
- set digest `bede37bfd7c37bd7da891461a5d91d8dc6bdc3a085d2b873c739cc723ca68f27`;
- registration `v4.1.0-operational-cloud`.

This evidence remains immutable and is not relabeled as V4.2 migration evidence.

## Local commands

```bash
./mvnw -Dtest=V42PublicApiFoundationTest,V42MigrationOracleTest test
scripts/verify-v42-phase1-foundation.sh --skip-build
scripts/verify-version-alignment.sh 4.2.0-SNAPSHOT
```

The focused Java tests, independent fixture/parser tests, internal-halt,
external-kill and all three fake-cloud profiles pass locally. The full reactor (478
core and 5 processor tests), published compatibility through exact `4.1.0`, all four
consumers, six release JAR integrity checks and two-build byte reproducibility also
pass locally. Protected pull-request checks, merge identity and exact-master CI remain
pending and are not claimed by this branch.
