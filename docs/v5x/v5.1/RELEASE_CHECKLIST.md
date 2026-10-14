# V5.1 release checklist

**Status:** published; Phase 7 acceptance and Phase 8 publication independently
reconciled. Stable is **5.1.0**.

## Accepted publication

| Item | Verified identity |
| --- | --- |
| Candidate PR / exact-master CI | [#322](https://github.com/patricklfdm/GeneralSearchEngine/pull/322) / [38482900297](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38482900297), attempt 1, all 46 jobs passed |
| Published commit | `516fe1efb54ef0787f38209108f322f258f71696` |
| Signed tag | `v5.1.0`, tag object `a3ddf271aa01b8afe47c1bd55c998d209918fb25` |
| Pinned signing key | `91AAB7A2B0FB55C3BBB334534B6103148D643AB3` |
| Release workflow | [38488481320](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38488481320), attempt 1, all three jobs passed |
| Central deployment | `e6850421-91b0-43ce-b7b7-a99c6abb05f9`, successfully published at `2026-10-14T00:32:33Z` |
| GitHub deployment | `7053418761`, `production-release`, successful at `2026-10-14T00:33:16Z` |
| GitHub Release | [412224692 / v5.1.0](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v5.1.0), latest stable release at verification |
| Publication time | `2026-10-14T00:33:12Z`, October 13 in America/Los_Angeles |
| Release canonical receipt SHA-256 | `1fc05993e4edd73a6e58308e4b26258551b0faba451f48af12c4bd7eeb70ae1a` |
| Frozen artifact manifest SHA-256 | `5a6f6a4487066db95879637dd21c5a640a210afa93aa046e638660fadbf711c7` |

The release artifact `v51-release-reproducibility-38488481320` contains the
canonical receipt and packaged-API preparation receipt. The canonical receipt
identifies a clean `git-commit` source at the published commit and two independent
clean builds with identical nine JARs and three POMs. Local replay of that receipt
passes the exact-source and [twelve-artifact manifest](candidate-artifacts.sha256)
checks. The preparation receipt separately records 2240 preserved published V5.0
declarations, 154 additive declarations and successful execution of a consumer
compiled against published V5.0.

The release log records comparison of all twelve artifact hashes before signing,
after signing, before deployment and after deployment. Its remote verification passes
all twelve detached signatures and SHA-1 sidecars, all twelve canonical SHA-256
values, main-JAR manifest versions, processor service isolation, immutable storage
fixtures and clean V1–V5.1 consumers.

An independent post-publication execution of
`scripts/verify-published-release.sh 5.1.0` passes the same checks using a fresh
download directory and empty Maven repository: all six consumer modules compile,
22 tests pass, and V1 remains compile-only. It uses Temurin `21.0.12+8` and Maven
Wrapper `3.9.11`. Local `scripts/verify-release-tag.sh v5.1.0` also passes against
the repository's pinned public key. GitHub reports `unknown_key` for its
account-level tag badge; the cryptographic pinned-key checks pass independently.

Downloaded workflow/deployment records, release receipts and the independent
verification log are retained under ignored `target/v51-publication/`.
The reproducible archive timestamp `2026-09-19T00:00:00Z` is a build parameter,
not the publication date. The changelog's October 13 heading uses Pacific time.
The accepted [five-member cloud baseline](PHASE_6_NATIVE_SET_ACCEPTANCE.md)
keeps its original measured sources, continuation exception, failures and costs;
the final release commit is not relabelled as a measured cloud source.

## Before a tag

- [x] [Phase 6](PHASE_6_NATIVE_SET_ACCEPTANCE.md) accepted through PR #320 and
  exact-master CI `38457745089`, attempt 1, all 46 jobs.
- [x] [Phase 7A](PHASE_7_CHECKLIST.md) consumer/API/documentation changes accepted
  through PR #321 with the recorded one-time CI skip; no hosted PASS is claimed.
- [x] Phase 7B final `5.1.0` candidate accepted, with canonical toolchain, nine
  unsigned JAR/three POM identities and protected exact-source CI.
- [x] Core, processor and replication remain separately publishable; independent
  V1–V5.1 consumers pass at final coordinates in an isolated Maven repository.
- [x] Strict Javadoc, public API/format compatibility and source/fixture exclusion
  pass for all three artifacts. Final candidate source is explicit; measured
  cloud sources and their accepted continuation remain separately recorded.
- [x] Final release workflow and post-publication verifier have V5.1-specific
  candidate-byte checks and the V5.1 consumer. Generic V5 handling is insufficient.
- [x] Dated release notes, migration guide and release title/body reviewed; remote
  version absence checked. No tag may point to a snapshot or unqualified commit.

## Phase 8 — completed publication

- [x] Record exact-master candidate CI and canonical artifact acceptance.
- [x] Confirm remote tag/Release absence and Central HTTP 404 for all three POMs
  before publication; the release workflow repeats Central immutability checks.
- [x] Operator creates, verifies and pushes the signed `v5.1.0` tag at the exact
  accepted commit.
- [x] Release validation passes tag/signature/versions, compatibility, consumers,
  strict Javadocs, packaging and canonical builds.
- [x] Operator approves `production-release`; the workflow signs and publishes
  all three coordinates while preserving every frozen unsigned artifact.
- [x] Record successful Central and GitHub deployment identities and GitHub Release.
- [x] Independently verify all twelve remote signatures/checksums/canonical hashes
  and fresh V1–V5.1 consumers.
- [x] Prepare README, changelog, migration and roadmap updates marking 5.1.0 stable
  after reconciliation. This documentation follow-up does not change the signed tag.

Next is V5.2 Phase 0 contract and evidence design for replica reads, under the
[V5.x scope](../ROADMAP.md#next-entry-and-proposal-status). Its runtime work follows
contract acceptance; V5.1 publication does not qualify follower reads.

If publication partially succeeds, inspect immutable remote state and use the
existing exact-tag recovery path. Do not select a new commit under the same tag
or run the paid cloud measurements again to repair publication metadata.

## Explicit limits to retain in release notes

- Automatic mode is opt-in, one shard and exactly three fixed voters.
- Strong automatic reads belong to the ready leader; no public follower reads.
- No dynamic membership, mixed-version rolling upgrade or in-place configured
  authority conversion. Migration uses a quiesced verified backup and a new group.
- Indeterminate writes require application reconciliation, not unconditional retry.
- Registered latency/resource observations apply to the frozen test workload and
  do not establish a production throughput, p99 or general failover SLA.
- The five-member cloud baseline preserves its narrowly authorized two-source
  continuation. Future batches retain their ordinary common-source/sequence rule.
