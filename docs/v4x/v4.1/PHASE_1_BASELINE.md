# GeneralSearchEngine V4.1 Phase 1 foundation baseline

## Boundary

Phase 1 begins from protected Phase 0 merge
`8d83f41f7fd3431b63ee550502ea97376d586108` (PR #93), whose exact-master CI run
`33714630130` passed. It opens all eight active coordinates as `4.1.0-SNAPSHOT` and
adds only compatibility, model, fixture, crash-harness, fake-cloud and evidence
infrastructure. No production verifier, backup, restore, cleanup method or operational
value type is present.

## Published 4.0 compatibility input

The immediate Maven Central baseline is
`io.github.patricklfdm:general-search-engine:4.0.0`, pinned to SHA-256:

```text
77dd13c618caa36a411048a412e2ac88760186a479ed520b9e84a6ef8933e6a4
```

The isolated artifact profile copies and checks that exact JAR, then runs the ninth
published Japicmp comparison. V1, V2, V3 and V4 independent consumers compile against
the reactor snapshot.

## Frozen API and logical models

`V41OperationalPublicApi.java.fixture` is the exact declaration-only API shape. The
[Phase 1 public API fixture contract](PHASE_1_API_FIXTURE.md) freezes operation
ownership, generic descriptors, immutable record constructors and accessors, null and
equality rules, structural and semantic status families, cleanup plan/result values,
Javadoc obligations, and the separate operational exception reasons. The fixture
compiles, while reflection tests prove these types and methods do not yet exist in
production.

`V41BackupRestoreOracle` independently freezes an exact backup cut at sequence `B`,
stable content identity, exclusion of later source mutation, semantic-identity
matching, new-history restore, preservation of canonical state/indexes/`nextDocId`,
and the `Long.MAX_VALUE` rejection. It never calls production checkpoint or recovery.

## Immutable backup fixture and inspector

The immutable fixture directory contains lowercase hex representations of exact
`gse-backup-metadata`, `gse-backup-checkpoint`, and `gse-backup-manifest` bytes. The
manifest uses `GSEBKP10`, version `(1,0)`, strict length-prefixed UTF-8, big-endian
integral fields, canonical payload descriptors, raw SHA-256 digests, and a final
CRC32C. Its fixed content identity is:

```text
gse-backup-v1-d1a8b2c947d21af5d3cf2d0b50e80006c0369b9f4e5a0f5e5a427c6e57e18514
```

`scripts/v41/backup_format.py` is an independent encoder and byte inspector. It shares
no production recovery parser and fails closed on an incorrect member set, non-regular
member, payload mutation, manifest mutation, checksum error or identity mismatch.

## Crash and evidence foundation

The stable Phase 1 barrier is `v41-phase1-operational-scaffold-v1`. A Python parent
launches a separate Java child, observes a machine-readable acknowledgement, and
exercises both `Runtime.halt(87)` and external-kill paths. A second JVM verifies the
scaffold, and a shutdown-hook marker proves graceful close did not run. Phase 1 creates
no production operation or storage member.

Local and fake-cloud output uses exact schema
`gse-v41-operational-evidence-v1`, canonical JSON, a SHA-256 inventory, a full source
commit and clean/dirty state, bounded logs, ordered lifecycle, explicit model-only
operation status, and independently verified cleanup. The validator rejects extra
members, checksum changes, malformed identity, unbounded logs and incomplete cleanup.

## Calibrated no-paid cloud plan

| Control | Frozen Phase 1 value |
|---|---|
| Suite / preset | `v4.1-operational-safety-suite-v1` / `v4.1-operational-safety-v1` |
| Profiles | experiment `1`, canonical `3`, source-loss failure drill `1` |
| Scheduling | serial independent members |
| Machine | Standard `c3d-standard-30` |
| Source / restore disk | separate `pd-balanced`, at most `200 GiB` each |
| Filesystem | `ext4`, mount options `defaults` |
| Corpus | `100,000` documents, `16` tokens/document |
| Operations | `10,000` pre-backup mutations, `1,000` continued mutations |
| Measurement / maximum runtime | `1,800` / `5,400` seconds per member |
| Budget ceiling | USD `25` for an explicitly authorized complete run |
| GCS layout | `v4.1-operational-safety/<source>/<run>-<attempt>/<profile>/member-<slot>/` |

The fake lane orders source creation, exact cut, verification, simulated transport,
source VM and source-disk deletion, replacement VM and new restore disk, independent
verification, new-history restore model, continued mutation, second reopen, upload,
and exact cleanup. It invokes no GCP API and spends nothing. Paid workflows remain a
Phase 6 concern.

## Inherited V4.0 pre-change evidence

Published V4.0 behavior is the pre-change control. Its accepted canonical run
`33682157985` at source `fe2060b9a872e66ff0067be6e8b7c900f0099708` records three
independent serial members, checkpoint/recovery latency, retained bytes, 30-minute
read/write progress, storage amplification and cleanup. The set digest is
`5e71ae200f94f5713278db7312057c4454fb73e18d159f78e71c31a92c44abbf` and its
append-only registration is `v4.0.0-durable-cloud`. V4.1 does not overwrite or relabel
that evidence.

## Local commands

```bash
./mvnw -Dtest=V41PublicApiFoundationTest,V41BackupRestoreOracleTest test
scripts/verify-v41-phase1-foundation.sh --skip-build
scripts/verify-version-alignment.sh 4.1.0-SNAPSHOT
```

Focused Java tests and the bounded Python, fixture, internal-halt, external-kill and
three-profile fake-cloud suite pass locally. The full reactor (430 core and 5 processor
tests), published compatibility through exact `4.0.0`, all four consumers, six release
JAR integrity checks and two-build byte reproducibility also pass locally. Protected
PR #94 merged as `e183face9cd2649f266cc54167f5419b86144e4e`; exact-master CI run
`33717370973` passed and closed Phase 1.
