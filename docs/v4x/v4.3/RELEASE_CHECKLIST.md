# GeneralSearchEngine 4.3.0 release checklist

This record separates accepted fast-reopen evidence, local candidate validation,
protected-master acceptance, signed tagging, publication and post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `4.3.0` |
| Release state | published, independently verified and fully reconciled |
| Phase 7 entry | `cc603a6c946169b48390960091b6157c54e9ca0b` (PR #129) |
| Entry exact-master CI | `34568701485` |
| Registered cloud baseline | `v4.3.0-fast-reopen-cloud` |
| Canonical source / run | `1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6` / `34557940276` |
| Candidate branch | `release/v4.3.0` |
| Candidate merge / exact-master CI | `b6b4660ac6bf2cadc6b94be5f2db29e41ab0fe6d` (PR #130) / `34572477812` |
| Signed tag / release workflow | `v4.3.0` / `34573738901` (`success`) |
| Central deployment | `2526d3b2-7ec9-4ad6-ad97-31621ee2de99` |
| GitHub deployment / Release | `6388475724` (`success`) / `386867175` |
| Publication time | `2026-09-11T07:56:35Z` |

## Frozen candidate contents

- optional reconstructible per-index images for equality, range, prefix and text;
- exact `(1,2)` metadata/checkpoint/WAL/backup profile binding and derived catalog;
- codec-free bounded derived inspection and structured reopen diagnostics;
- complete warm load, component-local partial fallback and deterministic full fallback;
- canonical-only backup plus cold-first restore and `(1,0)`/`(1,1)` migration targets;
- bounded best-effort refresh, generation cleanup and crash/lifecycle hardening; and
- registered three-member replacement-host fast-reopen evidence.

Canonical documents, logical index configuration, checkpoint and WAL remain
authoritative. V4.3 adds no memory-mapping guarantee, online/reverse migration,
remote live storage, replication, retrieval change or third Maven artifact.

## Final candidate evidence

| Gate | Evidence |
|---|---|
| Version alignment | PASS — all active coordinates resolve to final `4.3.0` |
| Reactor and inherited phases | PASS — reactor, travel, JMH smoke and V4.3 Phase 1–6 gates |
| API and published compatibility | PASS — source/reflection plus fresh-isolated Japicmp through `4.2.0` |
| Independent consumers | PASS — clean V1, V2, V3 and V4 consumers |
| Logical/physical fixtures | PASS — frozen hashes and independent exact-byte parsers |
| Strict release artifacts | PASS — strict Javadocs and exactly six inspected JARs |
| Reproducible build | PASS — two clean release builds are byte-identical |
| Fast-reopen cloud baseline | PASS — immutable `v4.3.0-fast-reopen-cloud` registration |
| Diff and evidence hygiene | PASS — clean diff, source inventory and ignored evidence boundaries |

## Same-toolchain candidate artifact hashes

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-4.3.0.jar` | `c5ecf5cf311c734481e95f14bdcfffb466fa132dde424a2b6b4a58fe41778583` |
| `general-search-engine-4.3.0-sources.jar` | `43526518f91bc1ab4e606b9466616e1a763816999f193141a42895386c81a81c` |
| `general-search-engine-4.3.0-javadoc.jar` | `e9988885640a85307dcef9456113a5f1480d6c74020dec1ff75d1e20e767b68a` |
| `general-search-engine-processor-4.3.0.jar` | `a7ffd30a70f2eb873ef3672ceb2a103e11934582b5000484b1944ad19839cff0` |
| `general-search-engine-processor-4.3.0-sources.jar` | `ec9fd93f5050ce810b7df68eecba8b01cb8539369a46d22fa2c7492946685ad6` |
| `general-search-engine-processor-4.3.0-javadoc.jar` | `bd2ecb2b4ca5663013d48450b653fd56e20d47df6df38a75e50adcf1cc3ba6d8` |

These hashes came from the second of two byte-identical clean `4.3.0` release builds
under one local JDK/Maven toolchain. They describe the unsigned candidate JARs and
prove repeatability within that toolchain; they do not by themselves claim identical
archives across different JDK distributions.

## Published artifact reconciliation

All eight published POM/main/sources/Javadoc artifacts passed remote SHA-1 and
detached-signature verification with signing key
`91AAB7A2B0FB55C3BBB334534B6103148D643AB3`. Clean V3 and V4 consumers passed
against Maven Central `4.3.0`.

| Published artifact | SHA-256 |
|---|---|
| `general-search-engine-4.3.0.jar` | `c5ecf5cf311c734481e95f14bdcfffb466fa132dde424a2b6b4a58fe41778583` |
| `general-search-engine-4.3.0-sources.jar` | `21a27b50dbabd6c86f40742f417181a75afda916a399869f41b0583be7f9c5e8` |
| `general-search-engine-4.3.0-javadoc.jar` | `db6b31f19b9d75c321a7c65527b790f562772a4f56935cd149abadef61f5e1e6` |
| `general-search-engine-processor-4.3.0.jar` | `a7ffd30a70f2eb873ef3672ceb2a103e11934582b5000484b1944ad19839cff0` |
| `general-search-engine-processor-4.3.0-sources.jar` | `ec9fd93f5050ce810b7df68eecba8b01cb8539369a46d22fa2c7492946685ad6` |
| `general-search-engine-processor-4.3.0-javadoc.jar` | `2053ea23a014d5a8b64c76bd81139caa96fffabd9cb7f4019fd2aa2bd956efa9` |

The two main JARs and processor sources JAR match their local candidate hashes
exactly. Extracted core sources contain identical files; the local archive has only
six additional empty `org/example/...` directory entries. Extracted Javadocs share
identical files; the GitHub runner JDK additionally contributes `legal/LICENSE` and
`legal/ADDITIONAL_LICENSE_INFO`. This is a transparent cross-JDK-distribution
packaging boundary, not a runtime, source, API or storage-format difference. V4.4
must either pin an identical release toolchain or normalize these ancillary entries
before claiming cross-toolchain byte identity.

## Protected acceptance

- [x] Candidate PR #130 passed required checks.
- [x] Candidate merged to protected `master` without a direct push.
- [x] Exact-master CI run `34572477812` passed for `b6b4660`.
- [x] Local and remote absence of `v4.3.0` was confirmed before signing.
- [x] Central immutability preflight returned HTTP `404` for core and processor.

## Phase 8 publication

- [x] Create and locally verify signed annotated tag `v4.3.0` at the exact accepted
  protected-master commit.
- [x] Push only that verified tag and approve the protected production deployment.
- [x] Verify signed core/processor POM, main, sources and Javadoc artifacts remotely.
- [x] Verify clean remote V3/V4 consumers against published `4.3.0`.
- [x] Verify GitHub Release `386867175` and successful production deployment
  `6388475724`.
- [x] Replace candidate wording only after all publication facts exist; GitHub
  Release `386867175` was reconciled after independent verification.

Phase 8 is complete. The release-body reconciliation did not change the signed tag
or immutable Central artifacts.
