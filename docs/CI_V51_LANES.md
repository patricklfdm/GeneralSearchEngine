# V5.1 CI: three jobs split into nine

The three V5.1 regression jobs now each have three independently required children.
This refactor preserves every verification command and every evidence upload.
A later [Phase 6C2A rich-workload lane](v5x/v5.1/PHASE_6_REMOTE_RICH.md) is independently
required. The [6C2B fault lane](v5x/v5.1/PHASE_6_REMOTE_FAULTS.md) adds a separate
required twelve-cell qualification. The subsequent
[verification build domain](CI_V51_BUILD_DOMAIN.md) centralizes
V5.1 prerequisite compilation/tests. Full CI now has twenty required gates plus
Change scope and Required (twenty-two jobs total). Docs-only CI continues to skip Maven.

## Historical partition measurements

Timing source: [successful PR CI 35807126940](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35807126940).
The original foundation/admission, protocol/reclamation and public lifecycle jobs
took 19m52s, 23m27s and 27m04s respectively. The next master run shows comparable
protocol/lifecycle timings; its foundation reactor failed as described below.

| Previous job | New job | Existing verification/upload work | Repeated build/setup | Estimated total |
| --- | --- | ---: | ---: | ---: |
| `v51-foundation-admission` | `v51-foundation` | 327s | 320s | 10m47s |
| `v51-foundation-admission` | `v51-admission-resources` | 252s | 320s | 9m32s |
| `v51-foundation-admission` | `v51-promise-crashes` | 287s | 320s | 10m07s |
| `v51-public-lifecycle` | `v51-public-reads-faults` | 470s | 315s | 13m05s |
| `v51-public-lifecycle` | `v51-public-recovery-pressure` | 440s | 315s | 12m35s |
| `v51-public-lifecycle` | `v51-public-hardening` | 393s | 315s | 11m48s |
| `v51-protocol-reclamation` | `v51-protocol-selection` | 346s | 302s | 10m48s |
| `v51-protocol-reclamation` | `v51-candidate-crashes` | 349s | 302s | 10m51s |
| `v51-protocol-reclamation` | `v51-reclamation` | 407s | 302s | 11m49s |

These are step-sum estimates, not measurements of the new workflows. They exclude
new Java report upload/post-job overhead, queueing and cache/runner variation. Six
additional reactor builds add about 31 runner minutes at the observed build times;
wall-clock V5.1 completion is expected near 13 minutes when runners are available.
Each regression job retains the requested 60-minute timeout. Other CI jobs may
still determine the overall workflow duration.

## Gate and artifact ownership

Ordinary builds below now run through the [bounded Maven infrastructure helper](CI_MAVEN_INFRA_RETRY.md).
It preserves the underlying command and permits one retry only for classified remote
transfer failures before test execution. Phase gates and specialized builds keep their
original single-attempt behavior; all attempt logs are uploaded independently.

Each V5.1 behavioral child now waits for `changes` and `v51-verification-build`,
checks out the same source and uses the same pinned Temurin Java 21. It downloads
and validates the dedicated build bundle before its unchanged `--skip-build`
gates. Main JARs, replication test classes and executed Surefire reports come from
that one clean build; execution state/evidence remain private to each child.
The historical repeated-build estimates above describe the original split.
Phase 6A adds its rich-model/control qualification inside the existing foundation
command, retained under that command's `rich-workload` subdirectory. It compiles
against three isolated core JARs and runs only the published V4.4 semantic consumer;
the separate `phase6-performance.sh` gate now adds three measured runtime modes and
a bounded automatic SIGKILL/rejoin schedule. Its 900-second ceiling includes cleanup;
measured CI overhead must be reviewed on this implementation source.

Shared Python helpers do not share process/evidence state: every gate creates its
own workspace and compiles its own public consumer/observer when required.

The original split preserved 44 substantive steps: 22 verification commands and
22 evidence uploads. Phase 5B adds one gate/upload pair, for 23 of each. Phase 6A adds one local performance gate/upload pair, for 24 of each. The original
steps remain present exactly once with their original text/configuration. Within
each child their relative order is preserved. The V4 JMH chain, V5.0 cloud-preflight
job/step identifiers, paid workflows and release jobs keep their prior wiring.

| Gate (`scripts/verify-v51-…sh --skip-build`) | Job | Evidence directory |
| --- | --- | --- |
| `phase1-foundation.sh` | `v51-foundation` | `target/v51-foundation` |
| `phase2-storage.sh` | `v51-foundation` | `target/v51-storage` |
| `phase3-protocol.sh` | `v51-foundation` | `target/v51-protocol` |
| `phase3-runtime.sh` | `v51-foundation` | `target/v51-runtime` |
| `phase3-rejoin.sh` | `v51-foundation` | `target/v51-rejoin` |
| `phase6-performance.sh` | `v51-foundation` | `target/v51-performance` |
| `phase6-remote-rich.sh` | `v51-remote-rich` | `target/v51-remote-rich` |
| `phase6-remote-faults.sh` | `v51-remote-faults` | `target/v51-remote-faults` |
| `phase4-public-bounds.sh` | `v51-admission-resources` | `target/v51-public-bounds` |
| `phase4-public-promises.sh` | `v51-promise-crashes` | `target/v51-public-promises` |
| `phase4-bootstrap.sh` | `v51-admission-resources` | `target/v51-bootstrap` |
| `phase4-resources.sh` | `v51-admission-resources` | `target/v51-resources` |
| `phase5-combined-lifecycle.sh` | `v51-admission-resources` | `target/v51-combined-lifecycle` |
| `phase4-public-runtime.sh` | `v51-public-reads-faults` | `target/v51-public-runtime` |
| `phase4-public-qualification.sh` | `v51-public-reads-faults` | `target/v51-public-qualification` |
| `phase4-public-faults.sh` | `v51-public-reads-faults` | `target/v51-public-faults` |
| `phase4-public-recovery.sh` | `v51-public-recovery-pressure` | `target/v51-public-recovery` |
| `phase4-public-pressure.sh` | `v51-public-recovery-pressure` | `target/v51-public-pressure` |
| `phase4-backpressure.sh` | `v51-public-recovery-pressure` | `target/v51-backpressure` |
| `phase4-lifecycle-hardening.sh` | `v51-public-hardening` | `target/v51-lifecycle-hardening` |
| `phase4-final-coverage.sh` | `v51-public-recovery-pressure` | `target/v51-final-coverage` |
| `phase5-hardening.sh` | `v51-public-hardening` | `target/v51-hardening` |
| `phase4-public-protocol.sh` | `v51-protocol-selection` | `target/v51-public-protocol` |
| `phase4-public-selection.sh` | `v51-protocol-selection` | `target/v51-public-selection` |
| `phase4-public-candidates.sh` | `v51-candidate-crashes` | `target/v51-public-candidates` |
| `phase4-public-reclamation.sh` | `v51-reclamation` | `target/v51-public-reclamation` |

Each child additionally always uploads `**/target/surefire-reports/**` as
`<job-id>-java-tests-${{ github.sha }}`, for fourteen days. These nine unique artifacts
include XML reports, failure details and JVM dump files when available, even if the
initial package fails and no process gate runs. All 47 workflow artifact names are
unique. No failed or cancelled child can pass Required. The actual Required shell
is tested with failure/cancellation/unexpected-skip cases for all nineteen children,
and all nineteen intentional skips are required for a verified docs-only run.

## Build failure and fix

[Master CI 35809008207](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35809008207)
failed during the foundation job's reactor package, in
`V50ReadyTest.incrementalCatchupReplaysOnlyTheMissingTailOfAPublishedPrefix`, the
`published,APPEND` case. Its injected lost APPEND left node-2 behind while node-3
supplied quorum for the 300-update seed. Before isolating node-3, the test correctly
repaired node-2, but its helper gave the entire catch-up the same ten seconds used
for admission. The log showed node-2 already at 174/302 when the Java test's future
wait timed out. Later ordinary APPEND/PROOF rejections are expected after the seed
loss; they do not prove conflicting committed histories.

An admitted catch-up comprises activation, many serial bounded batch exchanges,
READY and authority/floor checks. The fixture permits only four entries per batch:
the CI deficit needs 75 batches, with a separate 1200 ms request deadline and one
retry per exchange. The test now retains ten seconds for admission backpressure,
and derives a finite overall completion budget from the actual missing entry
count, batch limit and configured request/retry bounds, with control-exchange
headroom. Only `CAPACITY_EXCEEDED` is retried; protocol, storage and integrity
failures still fail immediately. Successful batch responses are counted against
the observed deficit, and the existing exact final-index, READY, decode-count and
next-quorum-write assertions remain required. There is no production timeout or
replication protocol change.

## Validation

- Full reactor package after the budget correction: 862 tests, 858 passed and 4
  skipped, zero failures/errors. The final `V50ReadyTest` source then passed all
  thirteen cases independently, including the actual deficit/batch-count check.
- CI classifier/topology/Required, V4.4 toolchain and V5.0 cloud cleanup/runner
  fixtures: 68 tests passed. Required outcomes cover all seventeen full jobs;
  added coverage checks retain every V5.1 gate once with its local evidence and
  an executed local reactor build.
- YAML/113 shell blocks and all 45 unique artifact names checked. All 44 prior
  V5.1 steps are identical after relocation; non-V5.1 jobs and workflow-level
  triggers, permissions and concurrency are identical to the input workflow.
- V5.1 42-document contract, changed Markdown links and `git diff --check` passed.

Local logs and migration/validation JSON are under `target/v51-ci-split/`.
The next full PR/master runs must establish hosted scheduling and actual child-job
durations; the nine individual hosted jobs have not run locally.

## Phase 5B addition

`phase5-combined-lifecycle.sh` runs in `v51-admission-resources` and retains
`target/v51-combined-lifecycle` with `always()`. The fixed four-case gate extends
quarantine/admission into transport pressure, retained recovery and cancellation/close.
The independent reactor build already supplies every required JAR; no job dependency
is added. Exact-master CI `35818964327` measured this lane at 9m28s versus 12m18s
for public hardening, so the new gate uses the shorter lane. Actual added CI time
remains to be measured. Seventeen required full-CI jobs and docs-only behavior remain.
