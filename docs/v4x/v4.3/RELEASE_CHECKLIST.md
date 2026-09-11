# GeneralSearchEngine 4.3.0 release checklist

This record separates accepted fast-reopen evidence, local candidate validation,
protected-master acceptance, signed tagging, publication and post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `4.3.0` |
| Release state | locally validated final candidate; protected acceptance pending; not published |
| Phase 7 entry | `cc603a6c946169b48390960091b6157c54e9ca0b` (PR #129) |
| Entry exact-master CI | `34568701485` |
| Registered cloud baseline | `v4.3.0-fast-reopen-cloud` |
| Canonical source / run | `1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6` / `34557940276` |
| Candidate branch | `release/v4.3.0` |
| Candidate merge / exact-master CI | pending Phase 7 protected acceptance |
| Signed tag / Central / GitHub Release | pending Phase 8 |

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

## Reproducible final artifact hashes

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-4.3.0.jar` | `c5ecf5cf311c734481e95f14bdcfffb466fa132dde424a2b6b4a58fe41778583` |
| `general-search-engine-4.3.0-sources.jar` | `43526518f91bc1ab4e606b9466616e1a763816999f193141a42895386c81a81c` |
| `general-search-engine-4.3.0-javadoc.jar` | `e9988885640a85307dcef9456113a5f1480d6c74020dec1ff75d1e20e767b68a` |
| `general-search-engine-processor-4.3.0.jar` | `a7ffd30a70f2eb873ef3672ceb2a103e11934582b5000484b1944ad19839cff0` |
| `general-search-engine-processor-4.3.0-sources.jar` | `ec9fd93f5050ce810b7df68eecba8b01cb8539369a46d22fa2c7492946685ad6` |
| `general-search-engine-processor-4.3.0-javadoc.jar` | `bd2ecb2b4ca5663013d48450b653fd56e20d47df6df38a75e50adcf1cc3ba6d8` |

These hashes came from the second of two byte-identical clean `4.3.0` release
builds. They describe the unsigned candidate JARs; Phase 8 owns signing and remote
publication verification.

## Protected acceptance

- [ ] Candidate PR passes required checks.
- [ ] Candidate merges to protected `master` without a direct push.
- [ ] Exact-master CI passes for the merge commit.
- [ ] Local and remote absence of `v4.3.0` is confirmed before signing.
- [ ] Central immutability preflight returns HTTP `404` for core and processor.

## Phase 8 publication

- [ ] Create and locally verify signed annotated tag `v4.3.0` at the exact accepted
  protected-master commit.
- [ ] Push only that verified tag and approve the protected production deployment.
- [ ] Verify signed core/processor POM, main, sources and Javadoc artifacts remotely.
- [ ] Verify clean remote V3/V4 consumers against published `4.3.0`.
- [ ] Verify the GitHub Release and successful production deployment.
- [ ] Replace any candidate wording only after all publication facts exist.

No unchecked Phase 8 item is implied by candidate validation.
