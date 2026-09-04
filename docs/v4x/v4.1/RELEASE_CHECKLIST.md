# GeneralSearchEngine 4.1.0 release checklist

This state-aware record separates accepted operational evidence, local candidate
validation, protected-master acceptance, signed tagging, publication and
post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `4.1.0` |
| Release state | published and remotely verified |
| Phase 7 entry | `049b232b12e9819a243c9d7925a39bc7ec0fec53` (PR #103) |
| Entry exact-master CI | `33809198755` |
| Registered cloud baseline | `v4.1.0-operational-cloud` |
| Canonical source / run | `88205cf28f1aa80f8ea7ccf1bada723b3205215c` / `33758217508` |
| Candidate branch | `release/v4.1.0` |
| Candidate merge | `9db6efc` (PR #104) |
| Final protected-master commit | `9db6efce275d25eb8da75d6532ea103982e591c6` |
| Exact-master CI | `33815734269`, `success` |
| Signed tag | verified `v4.1.0` at the exact final commit |
| Maven Central | core and processor `4.1.0` published and remotely verified |
| GitHub Release | ID `382405193`, published `2026-09-04T00:25:52Z` |
| Production deployment | ID `6255241071`, `success` |

## Frozen candidate contents

- published V4.0 durability and V3.4 retrieval behavior unchanged;
- codec-free structural verification of offline live stores and immutable bundles;
- checkpoint-only live backup with exact cut, pinning and canonical content identity;
- typed semantic verification and restore into an absent target as a new V4 history;
- offline dry-run-first cleanup bound to exact authority and inventory;
- stable operational values, failure categories and bounded diagnostics;
- separate-JVM interruption matrices, independent byte parsers and immutable live/
  backup format fixtures; and
- accepted true source-loss, replacement-host and three-member canonical cloud
  evidence with complete cleanup.

V4.1 adds no retrieval behavior, live-format change, online migration, repair,
incremental backup, in-place restore, replication or third Maven artifact.

## Final candidate evidence

| Gate | Evidence |
|---|---|
| Version alignment | PASS — all eight active coordinates resolve to final `4.1.0` |
| Reactor and V4/V4.1 phase gates | PASS — 476 reactor tests plus all local crash, lifecycle, cleanup and evidence gates |
| API and published compatibility | PASS — source/reflection fixtures and fresh-isolated Japicmp through `4.0.0` |
| Independent consumers | PASS — V1, V2, V3 and expanded V4 operational round trip |
| Live/backup format fixtures | PASS — frozen hashes and independent byte parsers |
| Strict release artifacts | PASS — release Javadocs and exactly six service-boundary-checked JARs |
| Reproducible build | PASS — two clean release builds are byte-identical |
| Operational cloud baseline | PASS — immutable `v4.1.0-operational-cloud` registration |
| Diff hygiene | PASS — whitespace, source inventory and ignored evidence boundary |

## Reproducible final artifact hashes

Two clean local release builds produced byte-identical output. These local hashes are
reproducibility evidence; the next table separately records the downloaded Maven
Central archives.

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-4.1.0.jar` | `36aa783cef653ead26d2500a847b70bb1f8222d224c8a83de55419de46814bcb` |
| `general-search-engine-4.1.0-sources.jar` | `092009a36e56b2b6c3eecdd718b117fc68cd4439bfb8342b6fe6dfb876bb2d46` |
| `general-search-engine-4.1.0-javadoc.jar` | `9c0b803f73d82d4cea58038c729d5b8e1ac50ce37b16f8333cbee96ece1a389e` |
| `general-search-engine-processor-4.1.0.jar` | `68deb84bff4b93d870be394479f3a12d132c031fd6c335a0b004d280dd9b58b8` |
| `general-search-engine-processor-4.1.0-sources.jar` | `6e68b6345a3c2b1c8b41ff8134adaaf04b779f9035bd69e5e80262456617f825` |
| `general-search-engine-processor-4.1.0-javadoc.jar` | `f6bc4042bdac592291f7aa7e895fec924d15fd996bf271d4028c27723fdcc95a` |

Post-publication download records the immutable Central archives separately:

| Published Maven Central artifact | SHA-256 |
|---|---|
| `general-search-engine-4.1.0.jar` | `36aa783cef653ead26d2500a847b70bb1f8222d224c8a83de55419de46814bcb` |
| `general-search-engine-4.1.0-sources.jar` | `f97a62158b86639a59e0b71600f6d0857d3f025905724c6cabf6c32fcd960ace` |
| `general-search-engine-4.1.0-javadoc.jar` | `46139e2dcc51cec71686ff08ed4a52d53cd63e1d9772342b42ed2b3dead23fc5` |
| `general-search-engine-processor-4.1.0.jar` | `68deb84bff4b93d870be394479f3a12d132c031fd6c335a0b004d280dd9b58b8` |
| `general-search-engine-processor-4.1.0-sources.jar` | `6e68b6345a3c2b1c8b41ff8134adaaf04b779f9035bd69e5e80262456617f825` |
| `general-search-engine-processor-4.1.0-javadoc.jar` | `9277c646f16fe3b67e0bdb4c536471771311104440eed0edfbb8ae66143a3157` |

Both main JARs and the processor sources JAR match the local reproducibility record
byte for byte. The core sources difference is limited to six empty legacy package
directory entries omitted by the Central build. The two Javadoc differences are
limited to Central's additional `legal/ADDITIONAL_LICENSE_INFO` and `legal/LICENSE`
entries. Every file common to each compared archive has identical content. All
Central artifacts independently passed detached-signature, SHA-1, manifest,
processor-service, immutable-format-fixture and consumer verification.

## Protected acceptance

- [x] Candidate PR #104 passed required checks.
- [x] Candidate merged to protected `master` as
  `9db6efce275d25eb8da75d6532ea103982e591c6`.
- [x] Exact-master CI run `33815734269` passed for that commit.
- [x] Local and remote absence of `v4.1.0` was confirmed before signing.
- [x] Central immutability preflight returned HTTP `404` for core and processor.

## Phase 8 publication

- [x] Created and locally verified a signed annotated `v4.1.0` tag at the exact accepted
  commit.
- [x] `git tag -v` and `scripts/verify-release-tag.sh` verified signing fingerprint
  `91AAB7A2B0FB55C3BBB334534B6103148D643AB3` and the exact tag target.
- [x] Pushed only the verified tag; release workflow run `33820284974`, attempt 1,
  completed successfully.
- [x] Approved the protected `production-release` deployment.
- [x] Verified signed core and processor POM/JAR/source/Javadoc artifacts from Central.
- [x] Verified clean remote V3 and V4 consumers against published `4.1.0` (9 and 6
  tests respectively, zero failures or errors).
- [x] Verified GitHub Release `382405193`, deployment `6255241071`, and tag target.
- [x] Reconciled the public GitHub Release body from candidate wording to independently
  observed publication facts.

## Post-publication evidence

| Evidence | Observed result |
|---|---|
| Release date | `2026-09-03` Pacific time; GitHub publication `2026-09-04T00:25:52Z` |
| Tag and protected-master SHA | signed `v4.1.0` -> `9db6efce275d25eb8da75d6532ea103982e591c6` |
| Signing fingerprint | `91AAB7A2B0FB55C3BBB334534B6103148D643AB3` |
| Exact-master CI | run `33815734269`, `success`, before tagging |
| Release workflow | [run 33820284974](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33820284974), attempt 1, tag push, `success`, `2026-09-04T00:04:48Z` to `2026-09-04T00:25:55Z` |
| Production deployment | ID `6255241071`, ref `v4.1.0`, same SHA, independently verified `success`, updated `2026-09-04T00:25:55Z` |
| Maven Central core | [`io.github.patricklfdm:general-search-engine:4.1.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine/4.1.0), main JAR SHA-256 `36aa783cef653ead26d2500a847b70bb1f8222d224c8a83de55419de46814bcb` |
| Maven Central processor | [`io.github.patricklfdm:general-search-engine-processor:4.1.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-processor/4.1.0), main JAR SHA-256 `68deb84bff4b93d870be394479f3a12d132c031fd6c335a0b004d280dd9b58b8` |
| Clean remote verification | PASS — eight artifacts, detached signatures, SHA-1 files, manifests, service boundary, immutable format fixtures, and clean V3/V4 consumers |
| Operational cloud baseline | `v4.1.0-operational-cloud`, source `88205cf28f1aa80f8ea7ccf1bada723b3205215c`, set digest `bede37bfd7c37bd7da891461a5d91d8dc6bdc3a085d2b873c739cc723ca68f27`, run `33758217508` |
| GitHub Release | ID `382405193`, [`GeneralSearchEngine 4.1.0`](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v4.1.0), target `master`, published `2026-09-04T00:25:52Z`, not draft or prerelease; body verified free of candidate-state wording |

The signed tag, protected-master commit, workflow, deployment, Central artifacts,
GitHub Release, immutable format fixtures, independent consumers, and registered
operational baseline all resolve to reviewed identities. The protected merge of this
documentation-only record closes Phase 8 and V4.1. Published `4.1.0`, signed
`v4.1.0`, live format `gse-durable (1,0)` and backup format `gse-backup (1,0)` are
immutable; later code or format changes require a new version and an explicit
compatibility contract.
