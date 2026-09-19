# V5.0 Phase 7 release candidate

**Status:** complete — protected candidate accepted; Phase 8 publication is reconciled.
**Starting master:** `3e5da79c0fae47d4d1e8e50022c928fb3d0b1d60`.

## Accepted entry

- [x] Phase 6 registration PR #179 and telemetry correction PR #180 merged.
- [x] [Exact-master CI `35421934224`](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35421934224) passed all six jobs and actually executed the V5 gates.
- [x] Baseline `v5.0.0-replicated-cloud` retains measured source `340df06148bc7d5a25a29a55c3ee928c9472dd09`, all five members and the disclosed IAP retry exception.

## Candidate scope

- [x] Core, processor, replication, reactor, example and V1–V5 consumers use final `5.0.0` coordinates.
- [x] All three publishable POMs freeze `2026-09-19T00:00:00Z`; replication includes the Central publishing extension.
- [x] Existing process harnesses resolve final artifact filenames.
- [x] Candidate documentation retained `4.4.0` as stable until Phase 8 publication; the post-publication update now identifies `5.0.0` as stable.
- [x] [Migration guide](MIGRATION_GUIDE.md) covers opt-in activation, sealed bootstrap, compatibility and backup/recovery boundaries.
- [x] CI checks the candidate inventory and digest-pinned two-workspace build; Phase 8 checks unsigned bytes before/after signing/deploy and after download.
- [x] Three artifacts, three POMs and nine JARs are included in Central preflight and remote signature/checksum verification; remote consumers cover V1–V5.
- [x] Production Java, accepted public descriptors, format fixtures, workload plans and registered cloud review remain unchanged.
- [x] The test-only public-runtime worker publishes its crash barrier atomically; a reader can no longer mistake a newly created but incomplete file for a valid owned barrier.

## Local validation

- [x] Two independent clean temporary workspaces under the pinned canonical image produced identical nine-JAR/three-POM bytes.
- [x] [Candidate hashes](candidate-artifacts.sha256) derived from the canonical receipt.
- [x] [Source-permission correction](RELEASE_CHECKLIST.md#source-permission-correction) makes working-tree captures match Git checkout modes; candidate byte checks remain strict.
- [x] Full reactor tests (728 discovered, four existing published-baseline-dependent skips), strict Javadocs and nine-JAR artifact inspection pass at final coordinates.
- [x] V1–V5 independent consumers pass in an isolated Maven repository; frozen source/reflection API and published API compatibility pass. Published comparisons use a fresh repository, excluding locally installed historical versions.
- [x] V5 Python evidence/release discovery passed 288 tests. After the barrier fix, all four bound Java suites and all 21 public-runtime process cases passed; Phase 6A passed 80 measured calls, 64 durable successes and 21 semantic negatives.
- [x] Whitespace, shell/workflow syntax, 548 local Markdown link targets and 23 inherited release/change-scope tests pass.

Local preparation uses an explicitly labelled `working-tree` archive with its base
commit and archive SHA-256. It does not claim that the parent commit contains the
final coordinates. CI rebuilds the committed candidate using `git archive HEAD` and
matches the same nine hashes. Each build starts without generated outputs; local
cloud downloads remain outside the source archive.

## Protected acceptance and Phase 8 handoff

- [x] PR #181 passed all checks in CI `35425979189` and merged as `e6afb5349c018fe163d4938d7637a4de8854d4ea`.
- [x] Exact-master CI `35427118768` passed all six jobs, including nine-JAR byte matching and the two-workspace canonical build.
- [x] The user created/pushed signed tag `v5.0.0` at that commit and approved `production-release`; workflow `35428718030` and post-publication reconciliation passed.

Phase 7 creates no signed tag, publication or new cloud measurement. The
[release checklist](RELEASE_CHECKLIST.md) owns the remaining publication steps.
