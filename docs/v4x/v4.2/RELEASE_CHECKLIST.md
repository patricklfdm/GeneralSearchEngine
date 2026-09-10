# GeneralSearchEngine 4.2.0 release checklist

This state-aware record separates accepted migration evidence, local candidate
validation, protected-master acceptance, signed tagging, publication and
post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `4.2.0` |
| Release state | published, remotely verified and fully reconciled |
| Phase 7 entry | `94d320f4213e229e206f6ae5202df66a1d9a5ae1` (PR #116) |
| Entry exact-master CI | `33930894450 / attempt 2` |
| Registered cloud baseline | `v4.2.0-migration-cloud` |
| Canonical source / run | `d0afbb593ab5df468c0b7c4b2622ebc6daa69317` / `33906942139` |
| Candidate branch | `release/v4.2.0` |
| Candidate merge | `5742b01` (PR #117) |
| Final protected-master commit | `5742b01def2fa5b1dd84b57f00ba6026c661f634` |
| Exact-master CI | `34388796604`, `success` |
| Signed tag | verified `v4.2.0` at the exact final commit |
| Maven Central | core and processor `4.2.0` published and remotely verified |
| Release workflow | `34415073641`; upload succeeded, post-upload 1800-second polling timed out |
| GitHub Release | ID `385924091`, published `2026-09-10T00:17:47Z` |
| Production deployment | ID `6361088014`; timeout failure retained, verified `success` reconciliation appended |

## Frozen candidate contents

- exact dual-minor `(1,0)` and `(1,1)` read/inspection policy with `(1,0)` default;
- canonical `(1,1)` profile binding across metadata, WAL, checkpoint and backup;
- explicit fresh/reopen/write and same-format backup/restore for `(1,1)`;
- typed dry-run/apply offline migration into an absent new-history target;
- deterministic format-only and codec/schema/key/index transforms with collision and
  stale-plan refusal;
- source preservation, target continued-operation/reopen and published-4.1 rollback;
- crash/lifecycle/remnant-cleanup matrices and immutable physical/logical fixtures;
  and
- accepted three-member replacement-host cloud evidence and complete cleanup.

V4.2 adds no retrieval change, silent upgrade, online migration, reverse migration,
history merge, in-place cutover, replication or third Maven artifact.

## Final candidate evidence

| Gate | Evidence |
|---|---|
| Version alignment | PASS — all eight active coordinates resolve to final `4.2.0` |
| Reactor and phase gates | PASS — 500 core and 5 processor tests plus inherited V4/V4.1/V4.2 local gates |
| API and published compatibility | PASS — source/reflection fixtures and fresh-isolated Japicmp through `4.1.0` |
| Independent consumers | PASS — V1, V2, V3 and expanded V4 migration/continued-operation coverage |
| Physical/logical fixtures | PASS — frozen hashes, independent V1.1 byte parsers and exact migration projection |
| Strict release artifacts | PASS — strict Javadocs and exactly six service-boundary-checked JARs |
| Reproducible build | PASS — two clean release builds are byte-identical |
| Migration cloud baseline | PASS — immutable `v4.2.0-migration-cloud` registration |
| Diff hygiene | PASS — whitespace, source inventory and ignored evidence boundary |

## Reproducible final artifact hashes

Two clean local release builds produced byte-identical output. These hashes describe
the locally validated candidate; the next table records independently downloaded
Maven Central archives.

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-4.2.0.jar` | `8dba2f09b861e3ed5fe7edde8226632c2248fe49582e0f3cb2c3fcb1cd958191` |
| `general-search-engine-4.2.0-sources.jar` | `44c07ac47b1aab2c053b41c9f920e37299c8bc17e1f60f29ae4cf67d0be4468d` |
| `general-search-engine-4.2.0-javadoc.jar` | `8468a44322d17f9d9a13bb119633218d6d9ffe804a2a119fb3d458993c8d8a91` |
| `general-search-engine-processor-4.2.0.jar` | `a7e3e92518626920817fab7013008d23d98b27cb2b71dffd390eb392bcfc155e` |
| `general-search-engine-processor-4.2.0-sources.jar` | `8dc39f20d25e7fe6b06e0e89ce0d6f03f61c8d49c47fae3f465736e75ba1d35a` |
| `general-search-engine-processor-4.2.0-javadoc.jar` | `0ae23b5c0d6a9da04a580793a8e83d31c49a56ecb3b934f823f795abce8f79f6` |

## Published Maven Central artifact hashes

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-4.2.0.jar` | `8dba2f09b861e3ed5fe7edde8226632c2248fe49582e0f3cb2c3fcb1cd958191` |
| `general-search-engine-4.2.0-sources.jar` | `68f559ab3cd7f62b883dc7abf79fd01792ee076a01550d8571cdb15de381e715` |
| `general-search-engine-4.2.0-javadoc.jar` | `80ee57e1d732dd1a3ce63df76178d57f771787632acd39d1c6ced8584b95670d` |
| `general-search-engine-processor-4.2.0.jar` | `a7e3e92518626920817fab7013008d23d98b27cb2b71dffd390eb392bcfc155e` |
| `general-search-engine-processor-4.2.0-sources.jar` | `8dc39f20d25e7fe6b06e0e89ce0d6f03f61c8d49c47fae3f465736e75ba1d35a` |
| `general-search-engine-processor-4.2.0-javadoc.jar` | `c7ab878b522cdfbc411b49fb977a4a281c14f385120763027b8bfbcb2196fe57` |

Both main JARs and the processor sources JAR match the local reproducibility record
byte for byte. The core sources difference is limited to six empty legacy package
directory entries omitted by the Central build. Each Javadoc difference is limited
to Central's additional `legal/ADDITIONAL_LICENSE_INFO` and `legal/LICENSE` entries.
Every file common to each compared archive has identical content.

## Protected acceptance

- [x] Candidate PR #117 passed required checks.
- [x] Candidate merged to protected `master` as
  `5742b01def2fa5b1dd84b57f00ba6026c661f634`.
- [x] Exact-master CI run `34388796604` passed for that commit.
- [x] Local and remote absence of `v4.2.0` was confirmed before signing.
- [x] Central immutability preflight returned HTTP `404` for core and processor.

## Phase 8 publication

- [x] Created and locally verified a signed annotated `v4.2.0` tag at the exact accepted
  commit.
- [x] Verified signing fingerprint
  `91AAB7A2B0FB55C3BBB334534B6103148D643AB3` and the exact tag target.
- [x] Pushed only the verified tag. Release workflow run `34415073641` completed all
  validation and uploaded Central deployment
  `a2341028-71df-42a6-a900-ad544676b08d`; its client exhausted the default
  1800-second status wait after the server-side publication continued successfully.
- [x] Approved the protected `production-release` deployment.
- [x] Verified signed core and processor POM/JAR/source/Javadoc artifacts from Central.
- [x] Verified clean remote V3/V4 consumers against published `4.2.0` (9 and 7 tests,
  zero failures or errors).
- [x] Created and verified GitHub Release `385924091` from the unchanged signed tag.
- [x] Preserved the original deployment failure and appended status `18088668544` as
  `success` only after independent Central, signature, consumer, tag and Release
  verification.
- [x] Replaced the GitHub Release body's candidate wording with verified publication
  facts, including the exact protected-master commit, Central deployment and
  reconciled production deployment identities.

## Post-publication evidence

| Evidence | Observed result |
|---|---|
| Release date | `2026-09-09` Pacific time; GitHub publication `2026-09-10T00:17:47Z` |
| Tag and protected-master SHA | signed `v4.2.0` -> `5742b01def2fa5b1dd84b57f00ba6026c661f634` |
| Signing fingerprint | `91AAB7A2B0FB55C3BBB334534B6103148D643AB3` |
| Exact-master CI | run `34388796604`, `success`, before tagging |
| Release workflow | [run 34415073641](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34415073641), tag push, terminal `failure` caused only by post-upload Central polling timeout |
| Central deployment | `a2341028-71df-42a6-a900-ad544676b08d`; server-side publication completed and all artifacts were independently resolved |
| Production deployment | ID `6361088014`, ref `v4.2.0`, exact release SHA; original timeout failure retained and explicit verified-success status `18088668544` appended `2026-09-10T00:28:56Z` |
| Maven Central core | [`io.github.patricklfdm:general-search-engine:4.2.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine/4.2.0), main JAR SHA-256 `8dba2f09b861e3ed5fe7edde8226632c2248fe49582e0f3cb2c3fcb1cd958191` |
| Maven Central processor | [`io.github.patricklfdm:general-search-engine-processor:4.2.0`](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-processor/4.2.0), main JAR SHA-256 `a7e3e92518626920817fab7013008d23d98b27cb2b71dffd390eb392bcfc155e` |
| Clean remote verification | PASS — eight artifacts, detached signatures, SHA-1 files, manifests, service boundary, immutable format fixtures, and clean V3/V4 consumers |
| Migration cloud baseline | `v4.2.0-migration-cloud`, source `d0afbb593ab5df468c0b7c4b2622ebc6daa69317`, set digest `57abb5394a537faaf551b9182ae5a1669de4703689dfe91e6e08dcd4580f2d75`, run `33906942139` |
| GitHub Release | ID `385924091`, [`GeneralSearchEngine 4.2.0`](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v4.2.0), target exact release SHA, published `2026-09-10T00:17:47Z`, body reconciled `2026-09-10T00:45:34Z`, not draft or prerelease |

The signed tag, protected-master commit, Central artifacts, GitHub Release, reconciled
deployment, immutable fixtures, independent consumers and registered migration
baseline all resolve to reviewed identities. The workflow timeout remains visible and
is not represented as a successful workflow run; the immutable version was never
redeployed.
