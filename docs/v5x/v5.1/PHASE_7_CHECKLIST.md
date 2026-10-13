# V5.1 Phase 7 release preparation

**Status:** Phase 7A implementation candidate; Phase 6 accepted through PR #320.
**Starting master:** `5c88a2b908347fa3e411e2018876657a21fa0912`.

## Accepted entry

- [x] PR [#320](https://github.com/patricklfdm/GeneralSearchEngine/pull/320) merged
  the independent five-member review and first baseline registry.
- [x] Exact-master [CI 38457745089](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38457745089),
  attempt 1, passed all 46 jobs. Phase 6 is closed.
- [x] [Original cloud evidence](PHASE_6_NATIVE_SET_ACCEPTANCE.md) retains both
  measured sources/sequences, the one-batch continuation, 61 cell instances and
  historical failures/costs. This release-preparation source is not a measured source.

## Delivery plan

| Batch | Concrete result | Acceptance boundary |
| --- | --- | --- |
| 7A, current | Independent V5.1 Maven consumer; published V5.0 API/binary audit against packaged JARs; migration guide and release checklist; snapshot packaging/Javadoc/reproducibility review | Operator merge with the one-time CI exception below; remain `5.1.0-SNAPSHOT` |
| 7B | Final `5.1.0` coordinates throughout modules/consumers/harnesses; frozen canonical toolchain/output timestamp; two independent clean-workspace builds; nine JAR/three POM hashes; CI/release/remote verification routes | Exact candidate source passes all required CI; no signed tag or publication |
| Phase 8 | Operator-created signed tag, approved Central/GitHub publication, signature/checksum/canonical-byte and clean remote-consumer reconciliation | [Release checklist](RELEASE_CHECKLIST.md) |

Phase 7A implements its entry and qualification together in this PR. It changes
consumer/test/release tooling and documentation, not runtime Java, formats,
measurement windows or cloud controls. No additional paid experiment is required
for this scope. If a later candidate changes production behavior, explicitly review
its effect on accepted evidence before accepting the release.

On 2026-10-13 the operator authorized skipping PR and master-push CI for this
Phase 7A merge only, using commit-message skip markers and the configured admin
bypass. Local validation below remains the evidence for this batch; skipped CI
must not be recorded as a successful hosted run. Phase 7B final-candidate CI
requirements remain in force.

## Phase 7A implementation

- [x] Add `compatibility/v51-style-consumer` to the independent Maven aggregator
  and version alignment checks, alongside unchanged V1–V5 consumers.
- [x] Exercise STOPPED/read-only planning, empty bootstrap/resume, V4 backup import
  with a new application history and preserved sequence/source bytes, configured
  reader rejection and refusal to clean committed automatic authority.
- [x] Add an artifact-bound release preparation audit to the existing required
  `Release artifacts` job; retain its receipt before subsequent clean builds.
  It validates the accepted baseline, nine JAR identities, the exact published
  V5.0 declarations and a consumer compiled with published V5.0 then run on V5.1.
- [x] Add negative tests for missing classifiers, mixed versions, test-asset leaks
  and failed/overwritten audit receipts. Preparation never claims candidate freeze.
- [x] Document opt-in use, migration, indeterminate outcomes, strong reads and
  unsupported rolling upgrade/follower-read/member-change behavior.
- [ ] Operator merge of this Phase 7A PR under the recorded one-time CI exception.

The independent consumer does not launch a networked election or replace the
accepted real-process/cloud runtime evidence. Its three tests cover application
linkage and offline API behavior. Configured-mode binary compatibility is checked
separately with the published V5.0 control; API compatibility does not imply that
mixed-version groups are qualified.

## Local validation

Local receipts and working-tree source inventory live at
`target/v51-phase7-preparation/`. Builds use an isolated source copy so Maven
`clean` cannot remove retained cloud archives from the main checkout. The local
build is explicitly a working-tree preparation, not a frozen release commit.

The current snapshot's two-build check is diagnostic reproducibility on its local
toolchain. Final coordinates, canonical image/toolchain identity and final artifact
hashes remain 7B requirements even if the snapshot bytes match.

| Check | Result |
| --- | --- |
| Complete reactor `clean -Prelease -Dgpg.skip=true verify` | 923 tests, four existing skips, no failures/errors; release packaging and Javadoc pass |
| Independent V1–V5.1 consumers | Six modules compile; 22 tests pass (V1 remains compile-only); isolated Maven repository seeded only with third-party cache, with project artifacts excluded before candidate install |
| Frozen source/reflection fixture | All three V1 API tests pass |
| Published V5.0 API/binary check | 2240 published declarations preserved, 154 additive declarations; published-5.0-compiled consumer runs on current JARs |
| Artifact content/version check | Nine JARs pass; sources/Javadocs contain no excluded test fixtures |
| Snapshot reproducibility | Nine JARs and three POMs identical across two independent source workspaces, Ubuntu OpenJDK 21.0.12.1 and Maven Wrapper 3.9.11 |
| Python release/baseline/foundation/CI regressions | 66 tests pass |

Javadoc uses the existing `all,-missing` doclint policy with warnings fatal. This
checks markup/references, not complete prose coverage of every public method.
The first new consumer import attempt correctly rejected its omitted startup
index with `IDENTITY_MISMATCH`. The fixture now supplies the complete application
configuration and asserts that the omitted-index variant still fails before
target creation. Original failure output is retained; production code was unchanged.

The required `Release artifacts` job runs the packaged-JAR audit and uploads its
receipt before the existing reproducibility step cleans `target`. The existing
`Compatibility` job picks up the sixth consumer through its aggregator. All 46
required jobs and their dependency/skip rules remain in place.

## Phase 7B release-candidate requirements

- [ ] Align core/processor/replication/reactor/example/all six consumers to `5.1.0`.
- [ ] Update V5.1 artifact resolvers and foundation checks that currently require
  `5.1.0-SNAPSHOT`; retain published control/version pins and historical evidence.
- [ ] Freeze a V5.1 canonical toolchain manifest and output timestamp; verify its
  image/platform digest and Maven acquisition independently of local cache.
- [ ] Produce two clean-workspace byte-identical builds of nine unsigned JARs and
  three POMs; derive candidate hashes only from the retained canonical receipt.
- [ ] Add exact V5.1 routing to candidate CI, release validate/deploy/download
  checks and `verify-published-release.sh`, including the new remote V5.1 consumer.
- [ ] Run source/reflection/API compatibility, all independent consumers, strict
  Javadocs and package inspections at final coordinates.
- [ ] Add dated release notes while keeping 5.0.0 marked stable until publication.
- [ ] Protected candidate CI and exact-master acceptance recorded; Phase 7 closed.

Signed tag, publication and cloud workflow dispatch remain operator-owned. Do not
invoke the generic release workflow with this snapshot or treat a green 7A audit
as a substitute for the final nine-JAR/three-POM freeze.
