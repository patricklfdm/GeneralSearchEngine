# V5.1 Phase 7 release preparation

**Status:** Phase 7B candidate at `5.1.0`; protected CI and merge pending.
**Starting master:** `9c03356ab343fc5aafcefbbfcc0e33382d19eef0` (PR #321).

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
| 7A, accepted | Independent V5.1 Maven consumer; published V5.0 API/binary audit against packaged JARs; migration guide and release checklist; snapshot packaging/Javadoc/reproducibility review | PR #321 merged with the one-time CI exception below, at `5.1.0-SNAPSHOT` |
| 7B, current | Final `5.1.0` coordinates throughout modules/consumers/harnesses; frozen canonical toolchain/output timestamp; two independent clean-workspace builds; nine JAR/three POM hashes; CI/release/remote verification routes | Exact candidate source passes all required CI; no signed tag or publication |
| Phase 8 | Operator-created signed tag, approved Central/GitHub publication, signature/checksum/canonical-byte and clean remote-consumer reconciliation | [Release checklist](RELEASE_CHECKLIST.md) |

Phase 7A implemented its entry and qualification together in PR #321. It changed
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
- [x] Operator merge of Phase 7A through PR #321 under the recorded one-time CI
  exception, at `9c03356ab343fc5aafcefbbfcc0e33382d19eef0` on 2026-10-13.

The independent consumer does not launch a networked election or replace the
accepted real-process/cloud runtime evidence. Its three tests cover application
linkage and offline API behavior. Configured-mode binary compatibility is checked
separately with the published V5.0 control; API compatibility does not imply that
mixed-version groups are qualified.

## Phase 7A local validation (historical)

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

- [x] Align core/processor/replication/reactor/example/all six consumers to `5.1.0`.
- [x] Update V5.1 artifact resolvers and foundation checks that previously required
  `5.1.0-SNAPSHOT`; retain published control/version pins and historical evidence.
- [x] Freeze a V5.1 canonical toolchain manifest and output timestamp; verify its
  image/platform digest and Maven acquisition independently of local cache.
- [x] Produce two clean-workspace byte-identical builds of nine unsigned JARs and
  three POMs; derive candidate hashes only from the retained canonical receipt.
- [x] Add exact V5.1 routing to candidate CI, release validate/deploy/download
  checks and `verify-published-release.sh`, including the new remote V5.1 consumer.
- [x] Run source/reflection/API compatibility, all independent consumers, strict
  Javadocs and package inspections at final coordinates.
- [x] Add dated release notes while keeping 5.0.0 marked stable until publication.
- [ ] Protected candidate CI and exact-master acceptance recorded; Phase 7 closed.

Signed tag, publication and cloud workflow dispatch remain operator-owned. Do not
invoke the generic release workflow with this snapshot or treat a green 7A audit
as a substitute for the final nine-JAR/three-POM freeze.

## Phase 7B artifact and source boundaries

The [toolchain manifest](release-toolchain.json) pins the existing Temurin
`21.0.12+8` image index and its `linux/amd64` platform image, Maven `3.9.11` ZIP
checksum, plugin versions and output timestamp. `2026-09-19T00:00:00Z` remains
an intentional reproducible ZIP timestamp inherited from the existing build;
it is not the V5.1 publication date. The canonical script verifies the selected
platform's membership in the pinned image index, pulls/runs that platform digest,
checks the Java runtime and verifies/extracts the Maven ZIP independently in each
container. Git file modes are normalized before working-tree packaging.

The [candidate manifest](candidate-artifacts.sha256) contains **all twelve**
unsigned artifacts, including the three POMs under normalized, unversioned names.
It was generated only from a successful two-workspace canonical receipt at
`target/v51-canonical-reproducibility/`. That local receipt explicitly identifies
an uncommitted working tree based on PR #321; it does not claim an accepted final
commit. CI regenerates the receipt from a clean checkout and must match both the
frozen bytes and the exact CI/tag commit. Hosted acceptance remains open until
those checks actually pass.

Candidate version checks distinguish current execution from historical replay:
new builds resolve the exact current POM coordinate and matching manifest version;
retained evidence accepts only a complete, digest-bound core/replication pair at
`5.1.0-SNAPSHOT` or `5.1.0`. Mixed versions and substituted artifact roles are
rejected. The measured Phase 6 sources/sequences, raw bundles, registered hashes,
workload parameters and runtime Java are unchanged.

The existing required `Release artifacts` job compares its pinned-JDK build to
all twelve frozen hashes, runs the two container builds and uploads the exact-source
receipt. Release validation repeats these checks. The publish job compares the
same twelve artifacts before signing, after signing, before deploy and after
deploy; remote verification checks the downloaded POMs and all nine JARs, their
signatures/checksums, then all six independent consumers. This wiring is checked
locally without invoking a signing key or publishing anything.

Phase 7B local receipts are retained under `target/v51-phase7-candidate/` and
summarized in its `validation-summary.json`. Full final-candidate CI and a
master merge are the next acceptance steps. The Phase 7A CI exception does not
apply to this candidate.

## Phase 7B local validation

| Check | Result |
| --- | --- |
| Two clean container workspaces | All nine JARs and three POMs byte-identical; manifest derived from that receipt |
| Independent host reactor on the same pinned JDK | 923 tests, four existing skips, zero failures/errors; release packaging/Javadoc pass; all twelve outputs match the container manifest |
| Compatibility | Three frozen source/reflection tests, published artifact compatibility and 2240 preserved V5.0 declarations pass; 154 additive declarations |
| Independent consumers at `5.1.0` | All six compile; 22 tests pass; isolated Maven repository excludes historical project artifacts before candidate install |
| V5.1 Python coverage | 1976 current unique tests pass: 1974 partitioned tests plus final targeted coverage of two tests added during validation; final targeted suite has 25 tests |
| Foundation | Real final-coordinate artifact/consumer/control/model gate passes |
| Local performance | Three healthy modes (270 calls), nine failover calls, 30 evidence negatives and owned-process cleanup pass |
| Targeted remote fault | Whole-group restart passes independent history/physical replay, seven calls; all three adapter modes and the final-coordinate restore classpath compile |
| Complete Phase 7 CLI | Version alignment, 18 release tests, toolchain/manifest and accepted baseline check pass |
| Workflow/docs | CI's 46 expanded jobs and dependency/skip rules preserved; 198 Bash blocks and changed-document links validate |
| Remote immutability precheck | All three Central `5.1.0` POM URLs return 404 at 2026-10-13T21:23:45Z; publication preflight repeats this check |

The first sandboxed Python attempt was interrupted after errors and is retained,
not counted as a pass. All three existing CI partitions subsequently completed
with their required local-process permissions. Actual execution of the new release
CLI also caught missing baseline-check arguments; they were corrected and covered
by a regression that executes the same read-only command before the full gate
passed. No signing key, tag, deployment or paid experiment was used.
