# GeneralSearchEngine 4.4.0 release checklist

This record separates accepted final-durable evidence, local candidate validation,
protected-master acceptance, signed tagging, publication and post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `4.4.0` |
| Release state | final candidate; local validation in progress |
| Phase 7 entry | `c9f77d2b203bab48360b55d80d67e09463984f8e` (PR #142) |
| Entry exact-master CI | `34892824621` (`success`) |
| Registered cloud baseline | `v4.4.0-final-durable-cloud` |
| Canonical source / run | `6301d855a92a3b2de8d9c338232a520fb9dd2b36` / `34824651199` |
| Candidate branch | `release/v4.4.0` |
| Candidate merge / exact-master CI | pending / pending |
| Signed tag / release workflow | pending / pending |
| Central deployment | pending |
| GitHub deployment / Release | pending / pending |
| Publication time | pending |

## Frozen candidate contents

- zero production Java, public API, storage-format or authority change;
- exact inherited V3.4 retrieval and V4.0–V4.3 durable behavior;
- ten-family independent crash, corruption, lifecycle, migration, derived-state,
  resource and replacement-host validation;
- canonical digest-pinned release toolchain and two-workspace byte identity;
- paired published-4.3 control under the frozen one-hour persistent workload; and
- immutable three-member `v4.4.0-final-durable-cloud` registration.

V4.4 adds no `(1,3)`, repair, salvage, online/reverse migration, replication,
sharding, consensus, remote live storage, retrieval change or third Maven artifact.

## Final candidate evidence

| Gate | Evidence |
|---|---|
| Version alignment | PASS — all eight active coordinates resolve to final `4.4.0` |
| Final durable cloud | PASS — experiment `34813346549`, failure drill `34818721022`, canonical `34824651199` |
| Registered baseline | PASS — immutable `v4.4.0-final-durable-cloud` through PR #142 / CI `34892824621` |
| API and published compatibility | PASS locally — frozen source/reflection inventory and fresh-isolated Japicmp through `4.3.0` |
| Independent consumers | PASS locally — V1, V2, V3 and V4 projects against final `4.4.0` |
| Logical/physical fixtures | PASS locally — Phase 7 identities plus inherited reduced crash/operational matrices |
| Strict release artifacts | PASS locally — main, sources and strict Javadoc JARs for core and processor |
| Canonical reproducible build | pending final six-JAR hash capture |
| Diff and evidence hygiene | pending final review |

## Canonical same-toolchain candidate artifact hashes

The following table is filled only from two byte-identical clean builds under
`release-toolchain.json`. These are unsigned candidate JAR hashes and must match the
six unsigned pre-deploy and published Central JARs in Phase 8. The normative
machine-readable inventory is `candidate-artifacts.sha256`; the table below mirrors
that file for review. `scripts.v44.candidate_artifacts` rejects missing, extra,
duplicated, reordered, malformed or byte-different members.

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-4.4.0.jar` | pending |
| `general-search-engine-4.4.0-sources.jar` | pending |
| `general-search-engine-4.4.0-javadoc.jar` | pending |
| `general-search-engine-processor-4.4.0.jar` | pending |
| `general-search-engine-processor-4.4.0-sources.jar` | pending |
| `general-search-engine-processor-4.4.0-javadoc.jar` | pending |

## Protected acceptance

- [ ] Candidate PR passes required checks.
- [ ] Candidate merges to protected `master` without a direct push.
- [ ] Exact-master CI passes on the candidate merge commit.
- [ ] Local and remote absence of `v4.4.0` is confirmed before signing.
- [ ] Central immutability preflight returns HTTP `404` for core and processor.

## Phase 8 publication

- [ ] Create and locally verify signed annotated tag `v4.4.0` at the exact accepted
  protected-master commit.
- [ ] Push only that tag and approve the protected production deployment.
- [ ] Verify release-workflow unsigned hashes match the six candidate hashes before
  signing and deployment.
- [ ] Verify signed core/processor POM, main, sources and Javadoc artifacts remotely.
- [ ] Verify all six Central JAR SHA-256 values equal the candidate hashes.
- [ ] Verify clean remote V3/V4 consumers against published `4.4.0`.
- [ ] Verify the GitHub Release and successful production deployment.
- [ ] Replace candidate wording only after every publication fact exists.

No Phase 8 publication claim is made by this candidate record.
