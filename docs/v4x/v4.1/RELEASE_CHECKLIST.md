# GeneralSearchEngine 4.1.0 release checklist

This state-aware record separates accepted operational evidence, local candidate
validation, protected-master acceptance, signed tagging, publication and
post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `4.1.0` |
| Release state | locally validated final candidate; protected PR acceptance pending |
| Phase 7 entry | `049b232b12e9819a243c9d7925a39bc7ec0fec53` (PR #103) |
| Entry exact-master CI | `33809198755` |
| Registered cloud baseline | `v4.1.0-operational-cloud` |
| Canonical source / run | `88205cf28f1aa80f8ea7ccf1bada723b3205215c` / `33758217508` |
| Candidate branch | `release/v4.1.0` |
| Candidate merge | pending |
| Final protected-master commit | pending |
| Signed tag | pending Phase 8 |
| Maven Central | pending Phase 8 |
| GitHub Release / deployment | pending Phase 8 |

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

Two clean local release builds produced byte-identical output. These candidate hashes
remain distinct from the hashes that Phase 8 will independently obtain from Maven
Central after publication.

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-4.1.0.jar` | `36aa783cef653ead26d2500a847b70bb1f8222d224c8a83de55419de46814bcb` |
| `general-search-engine-4.1.0-sources.jar` | `092009a36e56b2b6c3eecdd718b117fc68cd4439bfb8342b6fe6dfb876bb2d46` |
| `general-search-engine-4.1.0-javadoc.jar` | `9c0b803f73d82d4cea58038c729d5b8e1ac50ce37b16f8333cbee96ece1a389e` |
| `general-search-engine-processor-4.1.0.jar` | `68deb84bff4b93d870be394479f3a12d132c031fd6c335a0b004d280dd9b58b8` |
| `general-search-engine-processor-4.1.0-sources.jar` | `6e68b6345a3c2b1c8b41ff8134adaaf04b779f9035bd69e5e80262456617f825` |
| `general-search-engine-processor-4.1.0-javadoc.jar` | `f6bc4042bdac592291f7aa7e895fec924d15fd996bf271d4028c27723fdcc95a` |

## Protected acceptance

- [ ] Candidate PR CI passes.
- [ ] Candidate merges to protected `master`.
- [ ] Exact-master CI passes and commit/run are recorded.
- [ ] Local and remote absence of `v4.1.0` is confirmed.
- [ ] Central immutability preflight returns HTTP `404` for core and processor.

## Phase 8 publication — do not pre-claim

- [ ] Create and locally verify a signed annotated `v4.1.0` tag at the exact accepted
  commit.
- [ ] Push the tag and obtain a successful release workflow.
- [ ] Approve the protected `production-release` deployment.
- [ ] Verify signed core and processor POM/JAR/source/Javadoc artifacts from Central.
- [ ] Verify clean remote V3 and V4 consumers against published `4.1.0`.
- [ ] Verify the GitHub Release, deployment status and tag target.
- [ ] Replace candidate wording only after every remote fact is independently true.

Until every Phase 8 item succeeds, `4.0.0` remains the current stable release in the
root README.
