# GeneralSearchEngine 4.2.0 release checklist

This state-aware record separates accepted migration evidence, local candidate
validation, protected-master acceptance, signed tagging, publication and
post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `4.2.0` |
| Release state | locally validated final candidate; protected acceptance pending |
| Phase 7 entry | `94d320f4213e229e206f6ae5202df66a1d9a5ae1` (PR #116) |
| Entry exact-master CI | `33930894450 / attempt 2` |
| Registered cloud baseline | `v4.2.0-migration-cloud` |
| Canonical source / run | `d0afbb593ab5df468c0b7c4b2622ebc6daa69317` / `33906942139` |
| Candidate branch | `release/v4.2.0` |
| Candidate merge | pending |
| Final protected-master commit | pending |
| Signed tag | pending Phase 8 |
| Maven Central | pending Phase 8 |
| GitHub Release / deployment | pending Phase 8 |

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
the locally validated candidate; Phase 8 will independently hash Maven Central
downloads.

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-4.2.0.jar` | `8dba2f09b861e3ed5fe7edde8226632c2248fe49582e0f3cb2c3fcb1cd958191` |
| `general-search-engine-4.2.0-sources.jar` | `44c07ac47b1aab2c053b41c9f920e37299c8bc17e1f60f29ae4cf67d0be4468d` |
| `general-search-engine-4.2.0-javadoc.jar` | `8468a44322d17f9d9a13bb119633218d6d9ffe804a2a119fb3d458993c8d8a91` |
| `general-search-engine-processor-4.2.0.jar` | `a7e3e92518626920817fab7013008d23d98b27cb2b71dffd390eb392bcfc155e` |
| `general-search-engine-processor-4.2.0-sources.jar` | `8dc39f20d25e7fe6b06e0e89ce0d6f03f61c8d49c47fae3f465736e75ba1d35a` |
| `general-search-engine-processor-4.2.0-javadoc.jar` | `0ae23b5c0d6a9da04a580793a8e83d31c49a56ecb3b934f823f795abce8f79f6` |

## Protected acceptance

- [ ] Candidate PR CI passes.
- [ ] Candidate merges to protected `master`.
- [ ] Exact-master CI passes and commit/run are recorded.
- [ ] Local and remote absence of `v4.2.0` is confirmed.
- [ ] Central immutability preflight returns HTTP `404` for core and processor.

## Phase 8 publication — do not pre-claim

- [ ] Create and locally verify a signed annotated `v4.2.0` tag at the exact accepted
  commit.
- [ ] Push the tag and obtain a successful release workflow.
- [ ] Approve the protected `production-release` deployment.
- [ ] Verify signed core and processor POM/JAR/source/Javadoc artifacts from Central.
- [ ] Verify clean remote V3/V4 consumers against published `4.2.0`.
- [ ] Verify the GitHub Release, deployment status and tag target.
- [ ] Replace candidate wording only after every remote fact is independently true.

Until every Phase 8 item succeeds, `4.1.0` remains the current stable release in the
root README.
