# Cloud Benchmark V2 Phase 5 durable retention and baseline registration

Status: frozen before implementation

## Purpose

This document freezes the Cloud Benchmark V2 Phase 5 contract before any upload or
registry mutation code is implemented. It is subordinate to the Phase 0 evidence
model and preserves the completed Phase 2 set, Phase 3 comparison/registry, and Phase
4 evidence-profile contracts.

Phase 5 closes one dependency boundary: a locally verified run or set can be retained
under immutable Google Cloud Storage object names, represented by a separately verified
upload receipt, and—only for reviewed canonical sets—registered under a new immutable
baseline name.

Phase 5 must:

- preserve every raw and derived source byte;
- upload only locally validated evidence;
- use per-object create-only generation preconditions;
- prove an identical collision before treating it as success;
- verify generation, size, CRC32C, and recorded SHA-256 metadata after upload;
- create a deterministic receipt outside the source evidence;
- require a verified receipt before canonical baseline registration;
- keep all local-only V1 and V2 analysis workflows independent of GCS; and
- make all normal CI validation synthetic and cloud-cost-free.

Phase 5 must not:

- create or configure a bucket, IAM binding, service account, key, or WIF provider;
- upload during an ordinary V1 run, set, comparison, pull request, or push workflow;
- overwrite, delete, rewrite, move, or lifecycle-manage any remote object;
- mutate a raw run, orchestration record, derived manifest, set, or comparison;
- register experiment evidence or automatically select a latest baseline;
- replace an existing baseline name, even through a force flag;
- download missing registered evidence;
- upload comparison artifacts;
- add the Phase 6 manual GitHub workflow; or
- add a real baseline entry or contact a real bucket during implementation tests.

Historical index generation remains deferred to Cloud Benchmark V2.1.

## Public commands and compatibility

Phase 5 adds exactly two root wrappers:

```bash
./upload-cloud-benchmark.sh [--dry-run] [--confirm-upload] RUN_OR_SET

./register-cloud-baseline.sh [--dry-run] [--receipt RECEIPT] \
  [--release-label LABEL] NAME SET
```

The wrappers execute focused Python subcommands in `scripts/cloud/benchmark_v2.py`.
They do not duplicate schema parsing, hashing, receipt generation, or registry mutation
in shell.

The following existing commands and their CLIs remain unchanged:

```bash
./run-cloud-benchmark.sh MODE
./run-cloud-benchmark-set.sh ... MODE
./compare-cloud-benchmark.sh BASELINE CANDIDATE
scripts/cloud/list-baselines.sh
```

Phase 5 adds no implicit upload environment switch to a V1 command. Calling a local
run, set, comparison, or registry-list command without GCS configuration continues to
work exactly as before.

## Configuration and explicit mutation

The only bucket input is:

```bash
GSE_BENCHMARK_GCS_BUCKET=gs://example-bucket
```

It identifies one bucket, not an arbitrary prefix. It contains no object path, query,
fragment, control character, whitespace, shell fragment, or trailing slash. Phase 5
always appends the fixed `general-search-engine/` prefix.

The wrapper may honor ordinary `gcloud` authentication/configuration selected by the
operator, but it does not read credentials from repository files and adds no credential
environment alias. Maven Central and GPG release secrets are unrelated and must never
be reused.

`--dry-run` requires valid local evidence and bucket syntax, prints the deterministic
source classification and destination plan, and performs no GCS command, local receipt
write, or registry write. It therefore remains suitable for normal CI.

An actual upload requires `--confirm-upload`. Omitting it fails with exit `2` before
contacting GCS or writing a receipt. Upload is an explicit, bounded storage mutation;
the confirmation is not inferred from a TTY, environment variable, or prior benchmark
confirmation.

Registration is already an explicit local command. Its `--dry-run` validates the local
set, receipt selection, candidate entry, and current registry without contacting GCS or
writing the registry. Actual registration re-verifies remote evidence before one atomic
local registry update.

## Accepted evidence

`RUN_OR_SET` resolves only to one of:

1. a valid derived run directory at
   `benchmark-results/v3-production/derived/runs/<run-id>/v1`; or
2. a complete valid set directory at
   `benchmark-results/v3-production/sets/<set-id>/v1`.

Filesystem existence takes precedence over ID-like interpretation. Canonicalized input
must remain below the configured results root. Symlinks, device files, sockets, FIFOs,
unexpected directory escapes, partial evidence, quarantined evidence, unfinished set
workspaces, checksum failures, unsupported schemas, and contradictory provenance fail
before any GCS command.

A derived-run upload includes:

- every checksum-bound raw-run file plus `checksums.sha256`;
- its unique finalized orchestration `.properties` record and retained `.log` when the
  log exists; and
- every regular schema-1 derived-run file under its `v1` directory.

A set upload includes:

- every member's complete derived-run upload inventory; and
- every regular file in the completed set `v1` directory.

The inventory is deduplicated by final GCS URI, sorted by Unicode code-point order, and
must map one source byte sequence to each URI. A set member that cannot reconstruct its
raw, orchestration, and derived binding makes the upload invalid.

Valid experiment runs and sets may be retained, but their receipt remains experiment
evidence. Only a `VALID_CANONICAL_SET` with `evidenceProfile=canonical` can be registered.
Standard provisioning, repeat count, preset, environment equality, and set membership
are revalidated from frozen evidence rather than trusted from CLI claims.

Phase 5 does not accept a single raw directory, an in-progress workspace, a comparison,
a registry name, or a `gs://` URI as an upload source.

## Immutable GCS layout

The Phase 0 layout is made concrete as follows:

```text
gs://<bucket>/general-search-engine/
  raw/<commit>/<run-id>/<raw-relative-path>
  orchestration/<commit>/<run-id>/<record-name>
  derived/runs/<run-id>/v1/<derived-relative-path>
  sets/<set-id>/v1/<set-relative-path>
  receipts/<receipt-id>/v1/upload-receipt.json
  receipts/<receipt-id>/v1/upload-receipt.sha256
```

`commit`, `run-id`, and `set-id` are validated identities from the source manifests;
they are never taken from an untrusted destination argument. Relative paths use `/`,
contain no empty, `.`, `..`, `#`, or `?` segment/content, and are derived only from
validated regular files. The local source path, username, project ID, branch name, VM
IP, and invocation time do not enter an object name.

Large raw objects are uploaded once at run-owned paths. A set refers to its member run
identities and does not duplicate member bytes under the set prefix. Phase 5 reserves
the Phase 0 `comparisons/` namespace but writes nothing there.

The registered manifest URI is exactly:

```text
gs://<bucket>/general-search-engine/sets/<set-id>/v1/benchmark-set-manifest.json
```

## Create-only upload algorithm

Files are uploaded individually; recursive or wildcard copy is forbidden because every
object needs an independent precondition and verification record.

For a destination that does not exist, the implementation invokes the stable
`gcloud storage cp` surface with:

```text
--if-generation-match=0
```

and attaches the lowercase local SHA-256 as immutable custom metadata owned by this
tool. Generation zero means create only when no live object with that name exists. The
implementation must not substitute `--no-clobber`, because a silent skip does not prove
the existing object's identity.

After the copy, and whenever the create precondition reports a collision, the tool uses
`gcloud storage objects describe` with machine-readable JSON. Verification requires:

- exact bucket and object name;
- a nonzero numeric generation;
- exact decimal size;
- exact server-reported CRC32C matching the locally calculated CRC32C;
- exact tool-owned SHA-256 metadata matching the local SHA-256; and
- exact MD5 when both local and remote MD5 are available.

Missing or malformed required metadata is not identical evidence. A collision is a
successful idempotent retry only when every required comparison succeeds. Otherwise it
fails with exit `86`; Phase 5 never overwrites or deletes the conflicting object.

The local CRC32C used for comparison must be calculated through a deterministic,
tested path compatible with the value emitted by `gcloud storage hash`. Phase 5 does
not confuse CRC32 with CRC32C. SHA-256 remains the repository evidence identity;
CRC32C is the server-verifiable transport/integrity field.

If an upload stops after some objects succeed, those immutable objects remain. No local
receipt is finalized. Re-running the same command verifies identical collisions and
continues; a changed source or conflicting object fails. There is no remote rollback.

## Upload receipt schema and identity

The receipt is not embedded in, or referenced from, any source manifest. Its local
location is:

```text
benchmark-results/v3-production/upload-receipts/<receipt-id>/v1/
  upload-receipt.json
  upload-receipt.sha256
```

`upload-receipt.json` is canonical UTF-8 JSON with one trailing newline, sorted object
keys, sorted object entries, no duplicate keys, and exactly schema version 1. Its
top-level semantic fields are:

```text
kind = cloud-benchmark-upload-receipt
schemaVersion = 1
receiptId
bucket
source
objects
```

`source` contains only:

```text
kind = derived-run | benchmark-set
id
manifestSha256
evidenceProfile
sourceCommit
environmentFingerprint
benchmarkConfigFingerprint
```

For both source kinds, the fingerprints come from the validated source manifest. The
receipt contains no
local path, generated-at time, user, branch, IP, credential, access token, project ID,
or mutable latest alias.

Every source-object entry contains exactly:

```text
role
relativePath
uri
generation
size
sha256
crc32c
md5 (optional)
```

`role` is one of `raw`, `orchestration`, `derived-run`, or `benchmark-set`.
`relativePath` is relative to that role's fixed owner directory and cannot be used to
change the destination namespace. The tuple `(role, relativePath, uri)` must be unique.

`generation` and `size` are nonnegative decimal strings; object generations are
nonzero. SHA-256 uses the existing `sha256:<64 lowercase hex>` representation. CRC32C
and optional MD5 use the exact base64 metadata representation returned by GCS.

To avoid a circular hash, receipt identity is defined in two steps:

1. canonicalize the complete receipt identity projection with `receiptId` omitted;
2. set `receiptId` to `gse-upload-receipt-v1-` plus the SHA-256 hex of that projection.

The finalized document includes `receiptId`. Its independent full-document SHA-256 is
written to `upload-receipt.sha256` and is the `uploadReceiptSha256` stored by the
baseline registry. The checksum file contains one lowercase line in the existing
`<hex>  upload-receipt.json` format. The receipt ID and full-document checksum
deliberately serve different purposes.

The finalized receipt and checksum are themselves uploaded create-only under the
receipt path and verified using the same metadata rules. They are not included in the
receipt's `objects` array, preventing self-reference. The local receipt directory is
created atomically only after both remote receipt objects verify. An existing local
receipt directory succeeds only when its complete bytes and file set are identical.

## Baseline registration

Registration accepts a local completed set, never a run. The selected receipt may be:

- supplied explicitly with `--receipt`; or
- inferred only when exactly one locally valid receipt binds the exact set ID and set
  manifest digest.

Zero matching receipts fails. Multiple matching receipts are ambiguous and require
`--receipt`. Receipt selection never uses newest mtime or lexicographic accident.

Before registry mutation, registration validates:

- the current registry is canonical schema 1;
- `NAME` matches `[a-z0-9][a-z0-9._-]{0,63}` and is absent;
- the set is a complete canonical set and locally checksum-valid;
- the set ID, manifest digest, profile, commit, and both fingerprints match the receipt;
- every receipt object still has the recorded URI, generation, size, CRC32C, SHA-256
  metadata, and optional MD5;
- the remote receipt JSON bytes are represented by the local receipt checksum and the
  remote receipt object metadata;
- the exact set-manifest object is present in the receipt with the canonical URI; and
- optional `LABEL` is nonempty single-line UTF-8 of at most 100 characters.

The candidate registry entry uses only the schema frozen in Phase 3:

```text
setId
setManifestSha256
evidenceProfile = canonical
sourceCommit
releaseLabel (optional)
environmentFingerprint
benchmarkConfigFingerprint
manifestUri
manifestGeneration
uploadReceiptId
uploadReceiptSha256
```

Registration does not upload a `baselines/<name>/` copy. The registry is the reviewed
name-to-immutable-set reference; large evidence remains at run/set paths.

Any existing name fails with exit `85`, including an identical proposed entry. There is
no `--force`, replace, delete, or rename path. A superseding baseline uses a new name and
normal code review.

After all local and remote checks pass, the tool constructs the entire sorted canonical
registry in memory, validates it again, writes a same-directory temporary file, fsyncs
as supported, and atomically replaces the tracked registry. Failure before replacement
leaves the original bytes unchanged. The command does not commit, push, or open a pull
request.

Phase 5 implementation tests mutate only temporary registry fixtures. The tracked
`docs/v3/cloud-benchmark-baselines.json` remains empty until the user performs a real,
reviewed upload and submits the resulting registry change separately.

## Exit model

Phase 5 preserves all V1 and existing V2 exits:

| Exit | Meaning in Phase 5 |
|---:|---|
| `0` | dry-run, verified upload, or registration completed |
| `2` | CLI, local configuration, confirmation, or unsafe input error |
| `80` | raw/checksum/orchestration evidence invalid |
| `81` | unsupported evidence or schema |
| `82` | contradictory manifest, receipt, or duplicate object identity |
| `83` | set incomplete or members incompatible |
| `85` | registry schema, receipt binding, name, or immutable-name conflict |
| `86` | bucket config, storage command, collision, transfer, or remote verification failure |

Upload errors never become registry errors merely because the upload is intended for a
baseline. Registration maps local/remote receipt binding failure to `85`; an underlying
live storage command or object-verification failure remains `86` so operators can
distinguish registry content from durable-storage availability.

No performance classification changes an exit code.

## Security boundary

All subprocesses use argument arrays. Phase 5 introduces no `eval`, generated shell,
untrusted command environment variable, user-supplied destination prefix, or raw
`--format` expression. Machine-readable storage output is strict JSON parsed with
duplicate-key rejection and exact field validation.

Logs and receipts must not print or persist access tokens, authorization headers,
credential file contents, environment dumps, or signed URLs. Error messages may name
the fixed `gs://` object URI but must not include secret-bearing command output.

Input file enumeration rejects symlinks and path escapes before hashing. Upload code
does not follow files that change identity between inventory and transfer: size,
regular-file identity, and SHA-256 are rechecked immediately before copy, and the
post-copy metadata must match the frozen plan.

The required runtime permissions are limited to reading bucket/object metadata and
creating objects under `general-search-engine/`. Phase 5 does not grant them and does
not require delete, overwrite, bucket-admin, IAM-admin, or service-account-key access.

## Test-first implementation plan

Implementation proceeds in this order:

1. add strict source inventory, URI mapping, receipt schema, and identity unit tests;
2. add fake-storage describe/hash/copy behavior and collision tests;
3. implement upload planning and receipt primitives in the existing Python utility;
4. add the thin root upload wrapper and fake-storage end-to-end runner;
5. add receipt-to-canonical-set and registry-entry unit tests;
6. implement atomic registration and its thin root wrapper;
7. update CI and operator documentation; and
8. run all existing no-cost gates.

Production code is added only to satisfy a frozen failing invariant. Phase 5 may extend
the existing Python utility but does not split identity logic across a second parser or
introduce a second registry implementation.

## Required synthetic test matrix

Local source and planning tests cover:

- valid derived run and experiment/canonical set inventories;
- raw, orchestration, derived, and set URI mapping;
- deterministic ordering and deduplication;
- checksum corruption, missing member source, unfinished evidence, symlink, path escape,
  special file, unsupported schema, and contradictory identity;
- missing/malformed bucket, absent confirmation, and mutation-free dry-run; and
- byte-stable receipt identity, full checksum, and local collision behavior.

Fake-storage tests cover:

- every copy carrying `--if-generation-match=0`;
- newly created object verification;
- identical collision as idempotent success;
- conflicting size, SHA-256 metadata, CRC32C, MD5, generation, URI, or malformed JSON;
- missing required metadata and absent object after apparent success;
- copy, describe, hash, authentication, and partial-upload failure;
- retry after a partial upload without overwrite or duplicate receipt;
- create-only receipt JSON/checksum publication; and
- no delete, move, rewrite, recursive copy, bucket creation, or IAM command.

Registration tests cover:

- a valid canonical set and uniquely matching verified receipt;
- explicit receipt selection and ambiguous implicit selection;
- experiment/run/incomplete set rejection;
- set/receipt ID, digest, commit, profile, fingerprint, URI, and generation mismatch;
- remote re-verification before mutation;
- invalid release label, invalid name, existing-name rejection, sorted insertion, and
  byte-stable canonical registry output;
- failure leaving the original registry byte-identical; and
- no real tracked-registry entry created by tests.

Compatibility and no-cost gates cover:

- Python 3.11+ unit tests;
- shell syntax and fake-storage runner tests;
- existing manifest, set, profile, comparison, registry, fake-gcloud, soak,
  stabilization, compatibility, release, reproducibility, and reactor tests;
- absence of GCP credentials in normal CI; and
- no real VM, bucket, GCS object, receipt, or paid workflow execution.

## Deferred manual validation

After implementation is merged and only when the user explicitly chooses a test bucket,
the operator may perform one bounded manual validation:

1. dry-run a small verified experiment upload;
2. inspect the exact object plan;
3. execute with `--confirm-upload`;
4. verify the local receipt and remote metadata;
5. retry to prove identical-collision idempotence; and
6. confirm no unexpected VM, bucket, IAM, delete, or overwrite action occurred.

A canonical upload and real baseline registry entry are separate human-reviewed actions.
They are not acceptance requirements for the implementation PR.

## Phase 5 completion checklist

- [x] V1 run, set, comparison, and registry-list CLIs remain unchanged.
- [x] Local analysis and comparison remain fully usable without GCS.
- [x] Only validated derived runs and completed sets are accepted.
- [x] Object inventory and GCS layout are deterministic and path-safe.
- [x] Every copy uses generation-zero create-only semantics.
- [x] Identical collisions are verified; conflicting collisions never overwrite.
- [x] Remote URI, generation, size, CRC32C, SHA-256 metadata, and optional MD5 are verified.
- [x] Source evidence remains byte-identical after upload.
- [x] Receipt identity, full checksum, local path, and remote path are deterministic.
- [x] Partial uploads are safely resumable and cannot finalize a false receipt.
- [x] Only verified canonical sets can produce baseline registry entries.
- [x] Existing baseline names are immutable and registry writes are atomic.
- [x] The tracked registry remains empty during synthetic implementation tests.
- [x] No bucket, IAM, workflow, download, comparison upload, or real-cloud work is included.
- [x] Phase-specific tests and all existing no-cost gates pass.
