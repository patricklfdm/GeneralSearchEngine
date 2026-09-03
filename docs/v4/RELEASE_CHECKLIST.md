# GeneralSearchEngine 4.0.0 release checklist

This state-aware record separates the accepted durable evidence, final local candidate,
protected-master acceptance, signed tagging, publication, and post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `4.0.0` |
| Release state | published and remotely verified |
| Phase 7 entry | `adbe96d9bf73bf03d3082f2ceb58a66ca75dd325` (PR #88) |
| Registered cloud baseline | `v4.0.0-durable-cloud` |
| Canonical source / run | `fe2060b9a872e66ff0067be6e8b7c900f0099708` / `33682157985` |
| Candidate branch | `release/v4.0.0` |
| Candidate merge | `0f2ea5e` (PR #90) |
| Final protected-master commit | `73479da344f24f69e15904660d46783459d80dcf` (PR #91) |
| Signed tag | verified `v4.0.0` at the exact final commit |
| Maven Central | core and processor `4.0.0` published and remotely verified |
| GitHub Release | ID `381684854`, published `2026-09-03T02:22:41Z` |

Publication and remote-verification items below were completed only after independent
observation. Published `4.0.0` and its format `(1,0)` compatibility promise are now
immutable; later fixes require a new version.

## Frozen release contents

- unchanged default in-memory and complete published V1–V3.4 behavior;
- additive, explicit single-node local durable mode with format family `gse-durable`
  and version `(1,0)`;
- deterministic codec and storage identities, exclusive ownership, framed WAL,
  contiguous logical sequences, force-before-publication, checkpoints, bounded
  retention, deterministic recovery, and fail-closed corruption;
- local process-crash, repeated-crash, fault-injection, lifecycle, capacity, JMH,
  operational, paid cloud, and replacement-VM evidence;
- immutable V4 format fixtures, independent byte inspection, and an independent
  public-API durable consumer; and
- no replication, multi-writer support, physical-disk-loss guarantee, persisted
  derived indexes, online upgrade, or repair tool.

## Final candidate evidence

| Gate | Evidence |
|---|---|
| Version alignment | PASS — final `4.0.0` across all eight active coordinates |
| Reactor and V4 phase gates | PASS — 424 core, 5 processor, Phases 1–6 complete |
| API and published compatibility | PASS — source/reflection and isolated Japicmp through 3.4.0 |
| Independent consumers | PASS — V1/V2/V3/V4 plus travel example |
| Format `1.0` fixtures | PASS — production reader and independent inspector |
| Strict release artifacts | PASS — strict Javadocs and six-JAR service isolation |
| Reproducible build | PASS — two clean final-version builds byte-identical |
| JMH and cloud-local tooling | PASS — full bounded smoke and 102 Python tests; no paid run |
| Durable cloud baseline | PASS — immutable `v4.0.0-durable-cloud` registration |
| Diff hygiene | PASS — no production or format-semantic change; local evidence excluded |

## Reproducible final artifact hashes

This table records the final two-clean-build validation. These local hashes are
evidence for reproducibility; the next table separately records downloaded Central
artifacts.

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-4.0.0.jar` | `77dd13c618caa36a411048a412e2ac88760186a479ed520b9e84a6ef8933e6a4` |
| `general-search-engine-4.0.0-sources.jar` | `3ebfa4b3ca810a52442e7b3997a6b42638356e88425be294819ca6d4b6533b4c` |
| `general-search-engine-4.0.0-javadoc.jar` | `9ffd48a3afdf546e02e12d7cd45a163dfcb8137c35860c280662d2f7805a365b` |
| `general-search-engine-processor-4.0.0.jar` | `1f61e404f4d783d943b73e7b5e108a98a41e5f8e51240d4b735fbcf99bbf3b1b` |
| `general-search-engine-processor-4.0.0-sources.jar` | `4cb2cfbeccb73e16a4c50b15ab14591984f9dcbe56faa8dcb53f5fb0c0c8321c` |
| `general-search-engine-processor-4.0.0-javadoc.jar` | `b5824f84aef6955f75ddd1bb7dad051cb06e45cde22ade3b003e4d18edca113f` |

Post-publication download records the immutable Central archives separately:

| Published Maven Central artifact | SHA-256 |
|---|---|
| `general-search-engine-4.0.0.jar` | `77dd13c618caa36a411048a412e2ac88760186a479ed520b9e84a6ef8933e6a4` |
| `general-search-engine-4.0.0-sources.jar` | `e9399be12de410f4574957532eb52f319569b293726c16d54a97b0a1fc10bdad` |
| `general-search-engine-4.0.0-javadoc.jar` | `fc16ad0b9319da860db84792113ff0b70f92772f156bde0197cb6d8a28dc284f` |
| `general-search-engine-processor-4.0.0.jar` | `1f61e404f4d783d943b73e7b5e108a98a41e5f8e51240d4b735fbcf99bbf3b1b` |
| `general-search-engine-processor-4.0.0-sources.jar` | `4cb2cfbeccb73e16a4c50b15ab14591984f9dcbe56faa8dcb53f5fb0c0c8321c` |
| `general-search-engine-processor-4.0.0-javadoc.jar` | `41fed66b506ebfdf54c665af178257635d17e4e5f1333ce7cb492462161be1ab` |

Both main JARs and the processor sources JAR match the local reproducibility record
byte for byte. The core sources difference is limited to six empty legacy package
directory entries omitted by the Central build. The two Javadoc differences are
limited to Central's additional `legal/ADDITIONAL_LICENSE_INFO` and `legal/LICENSE`
entries. Every entry common to each compared archive has identical content. All
Central archives independently pass detached-signature, checksum, manifest,
processor-service, immutable-format-fixture, and consumer verification.

## Protected candidate acceptance

- [x] Merge the Phase 7 candidate through protected PR #90 as `0f2ea5e`.
- [x] Merge the evidence-workspace boundary through protected PR #91 as final commit
  `73479da344f24f69e15904660d46783459d80dcf`.
- [x] Require exact-master CI run `33705710878` to pass for that commit before tagging.
- [x] Verify local and remote absence of `v4.0.0`.
- [x] Verify the production environment permits tag pattern `v*.*.*`.
- [x] Run Central immutability preflight for core and processor and observe HTTP `404`.

## Signed tag verification

- [x] Create annotated signed `v4.0.0` on the exact final protected-master commit.
- [x] `git cat-file -t v4.0.0` reports `tag`.
- [x] `git tag -v v4.0.0` verifies fingerprint
  `91AAB7A2B0FB55C3BBB334534B6103148D643AB3`.
- [x] `scripts/verify-release-tag.sh v4.0.0` passes.
- [x] `git rev-parse v4.0.0^{commit}` equals the recorded protected-master commit.
- [x] Push only the verified tag.

## Protected publication

- [x] Tag-triggered release validation checks out the exact tag and passes every gate.
- [x] The repository owner approves `production-release` only after validation.
- [x] Core and processor POM/main/sources/Javadoc artifacts and signatures publish.
- [x] `scripts/verify-published-release.sh 4.0.0` passes against Maven Central.
- [x] Clean V3 and V4 consumers pass without a reactor install.
- [x] The V4 consumer opens every immutable positive format fixture and rejects the
  corruption fixture using the downloaded artifact.
- [x] Production deployment `6235596306` reports success for the exact tag commit.
- [x] GitHub Release `GeneralSearchEngine 4.0.0` is created from the verified tag,
  marked latest, and is neither draft nor prerelease; its body was reconciled from
  candidate wording to observed publication facts.

## Post-publication evidence

| Evidence | Observed result |
|---|---|
| Release date | `2026-09-02` Pacific time; GitHub publication `2026-09-03T02:22:41Z` |
| Tag and protected-master SHA | signed `v4.0.0` -> `73479da344f24f69e15904660d46783459d80dcf` |
| Signing fingerprint | `91AAB7A2B0FB55C3BBB334534B6103148D643AB3` |
| Exact-master CI | run `33705710878`, `success`, before tagging |
| Release workflow | [run 33706352253](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33706352253), attempt 1, tag push, `success`, `2026-09-03T02:06:38Z` to `2026-09-03T02:22:45Z` |
| Production deployment | ID `6235596306`, ref `v4.0.0`, same SHA, independently verified `success`, updated `2026-09-03T02:22:45Z` |
| Maven Central core | [`io.github.patricklfdm:general-search-engine:4.0.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine/4.0.0), main JAR SHA-256 `77dd13c618caa36a411048a412e2ac88760186a479ed520b9e84a6ef8933e6a4` |
| Maven Central processor | [`io.github.patricklfdm:general-search-engine-processor:4.0.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-processor/4.0.0), main JAR SHA-256 `1f61e404f4d783d943b73e7b5e108a98a41e5f8e51240d4b735fbcf99bbf3b1b` |
| Clean remote verification | PASS — eight artifacts, detached signatures, SHA-1 files, manifests, service boundary, immutable format fixtures, and clean V3/V4 consumers |
| Durable cloud baseline | `v4.0.0-durable-cloud`, source `fe2060b9a872e66ff0067be6e8b7c900f0099708`, set digest `5e71ae200f94f5713278db7312057c4454fb73e18d159f78e71c31a92c44abbf`, run `33682157985` |
| GitHub Release | ID `381684854`, [`GeneralSearchEngine 4.0.0`](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v4.0.0), target `master`, published `2026-09-03T02:22:41Z`, not draft or prerelease; body verified free of candidate-state wording |

The tag, protected-master commit, workflow, deployment, Central artifacts, GitHub
Release, format fixtures, independent consumers, and registered durable baseline all
resolve to reviewed identities. The protected merge of this documentation-only record
closes Phase 8 and the V4.0 line. Published `4.0.0` and signed `v4.0.0` are immutable;
any later code or format fix must use a new version and retain the `(1,0)` compatibility
promise.
