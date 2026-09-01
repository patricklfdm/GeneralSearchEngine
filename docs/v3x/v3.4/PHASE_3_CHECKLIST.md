# V3.4 Phase 3 checklist

Status: accepted through PR #70 as protected-master commit
`34760b326fda6da31a0463d7b4765d6c6da5921c`. Phase 3 adds benchmark-only bounded
burst/recovery and local long-run calibration surfaces. It changes no production
source, public API, cloud workflow, preset, paid resource, baseline registry, release
coordinate, or published artifact.

## Entry boundary

- [x] Phase 2 merged through PR #69 as protected-master commit
  `07b885790acbc8455db7bbc9a284173a05a19f56`.
- [x] The independent Phase 3 branch starts from that exact merge.
- [x] Published artifacts, tags, releases, deployments, and existing cloud families
  remain immutable.
- [x] Exact-commit protected-master
  [CI run 33384778745](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33384778745)
  succeeded for the Phase 2 merge at
  `07b885790acbc8455db7bbc9a284173a05a19f56` before Phase 3 evidence was committed.

## Multi-producer burst and recovery

- [x] The full `1/4/16` producer by `1/100/1000` submitted-batch matrix runs with an
  explicit document, producer, operation, queue, batch, reader, and timeout cap.
- [x] Controlled barriers separate worker readiness, dynamic-index admission, burst
  submission, reader observation, future completion, and final drainage.
- [x] Readers accept only zero or complete marker batches; no partial successful bulk
  publication is observed.
- [x] Every submitted future terminates as success or explicit `QUEUE_FULL`; no timeout
  or unresolved future enters a successful cell.
- [x] Missing-document, duplicate-ID, and oversized-bulk failures terminate explicitly,
  do not publish, and preserve the pre-failure document.
- [x] Dynamic range/text index builds complete during pressure and final range/text,
  document, marker, query, index-count, and corpus oracles match successful history.
- [x] Submission/admission/completion/reader latency, submitted batch size, publication
  rate, queue maximum/capacity, rejection, GC, checksum, and last-submit-to-drain time
  are emitted for every cell.
- [x] The `16`-producer cells reach queue saturation and recover to zero while the
  engine remains one-writer.

## Local long-run calibration

- [x] A forked six-second cell proves warmup exclusion, three-window rotation, all six
  reader kinds, steady and burst schedules, lifecycle, planned failure, artifacts,
  manifest validation, final oracles, and cleanup.
- [x] The retained 30-minute cell completes 30/30 one-minute windows with exactly 60
  samples per window.
- [x] Structured, ranked TEXT/PHRASE, highlighted, exact-total page, and Explain paths
  all have positive coverage and stable truth in every window.
- [x] Every writer window makes progress; 30 bounded bursts and 15 dynamic range/text
  lifecycle cycles complete.
- [x] One planned missing-document failure remains isolated; unexpected failures and
  unresolved futures remain zero.
- [x] Final queue, pending-build, and mutation-journal counts are zero; corpus digest
  and all final query/index oracles pass.
- [x] Raw samples, window summaries, configuration, summary, and their SHA-256 manifest
  are complete and verified.
- [x] Provisional workload-specific throughput/p99 review bands are emitted and marked
  non-release; every retained window is within them without sustained monotonic drift.
- [x] Local calibration is not represented as the required two-hour run or cloud
  evidence.

## Deterministic validation

- [x] Strict parsers reject unknown, duplicate, unbounded, oversized, and invalid
  matrix/window inputs, including an attempted 7,200-second local run.
- [x] Focused tests execute a reduced burst cell and fork-equivalent two-second long
  run, assert final evidence, and exercise passing/failing window decisions.
- [x] `verify-v34-phase3-diagnostics.sh` launches the reduced burst and six-second
  artifact-producing long-run cells; retained JMH smoke invokes it after packaging.
- [x] Core, reactor, JMH-profile, consumer, compatibility, artifact, Markdown, and
  diff-hygiene gates pass on the final Phase 3 tree.
- [x] Confirm `src/main/java`, processor production source, `.github`, cloud
  scripts/presets, examples, compatibility consumers, and baseline registries remain
  unchanged.

## Phase 4 entry

- [x] Merge Phase 3 through protected review as PR #70 at
  `34760b326fda6da31a0463d7b4765d6c6da5921c`.
- [x] Exact-merge protected-master CI succeeded in
  [run 33436691459](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33436691459)
  for `34760b326fda6da31a0463d7b4765d6c6da5921c`.
- [x] Create an independent Phase 4 branch from that exact merge.
- [x] Implement only the separately frozen `final-v34` mode/suite/preset and its local
  fake/synthetic lifecycle gates.
- [x] Do not start a paid job, final conversion, two-hour run, canonical set,
  registration, release, or V4 implementation in Phase 4.

The eligible heap matrix and required final-source two-hour run remain open V3.4/V4
exit gates.
