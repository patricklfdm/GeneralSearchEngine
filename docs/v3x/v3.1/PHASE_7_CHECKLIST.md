# V3.1 Phase 7 checklist

Status: implementation and synthetic validation complete; protected-master cloud
evidence remains pending. No paid run is valid from this feature branch.

## Evidence-lane isolation

- [x] Preserve every existing `v3-production-<mode>-v1` preset, workload filename,
  benchmark class, parameter set, and suite identity.
- [x] Add only the frozen `ranked-v31` mode, `v3.1-ranked-v1` preset, and
  `v3.1-ranked-suite-v1` suite.
- [x] Keep the V3.1 feature suite explicitly incomparable with the registered
  `v3.0.0-cloud` regression family.
- [x] Keep registration separate and human-reviewed; no workflow path registers or
  replaces a baseline.

## Frozen feature matrix

- [x] Phrase: 100k and 1M documents; low/high-frequency slop 0, 1, 2, and 4;
  repeated terms, analyzer gaps, and same-position alternatives.
- [x] BOOL: 100k and 1M documents; widths 4, 16, and 64; minimum 1, half, and all;
  with and without MUST.
- [x] Fuzzy: 100k and 1M vocabulary; short/long terms, supplementary Unicode,
  exact/near/miss cases, and dense expansion.
- [x] Text dictionary: 100k and 1M initial build plus one- and 100-document
  unchanged/added/removed membership publication.
- [x] Mixed concurrency: 1M documents, 16 readers, one synchronous writer, and a
  deterministic TEXT/ordered-slop-PHRASE/FUZZY read cycle.
- [x] Record mixed read and writer throughput/latency, normalized allocation, GC,
  writer queue maximum/non-zero samples, and successful snapshot publications.

The matrix contains exactly 84 JMH entries: 22 phrase, 36 BOOL, 10 fuzzy, two build,
12 publication, and two mixed-concurrency entries. Canonical derivation rejects a
missing, duplicate, renamed, differently parameterized, or differently threaded
entry.

## Correctness and publication guards

- [x] Validate non-empty controls, descending scores, and slop-zero legacy
  equivalence before phrase timing.
- [x] Validate the BOOL all-minimum control and ordered hit results before timing.
- [x] Compare every fuzzy trial with the retained independent full-scan OSA oracle
  before timing.
- [x] Validate the exact distinct-term delta for unchanged, added, and removed
  dictionary membership before publication timing.
- [x] Reject a mixed-concurrency trial whose writer queue does not drain at teardown.
- [x] Consume deterministic hit, distance, dictionary, and snapshot values so timed
  work cannot be eliminated.

## Runner and protected workflow

- [x] Add `ranked-v31` to the existing local, one-VM, set, and protected-workflow
  control planes without creating a second orchestrator.
- [x] Freeze two forks, three one-second warmups, five one-second measurements, GC
  profiling, 1M mixed documents, and the `16,1` thread group.
- [x] Freeze a 3,600-second per-slot VM cap. The required `30m` soak selector is
  ignored; `2h` is rejected and no production soak executes.
- [x] Use `-Xms32g -Xmx64g` only for `ranked-v31`, record it in the workflow plan,
  set controls, raw metadata, environment fingerprint, and benchmark fingerprint.
  Regression presets remain `-Xms8g -Xmx16g`.
- [x] Preserve sequential slots, non-cancelling repository concurrency, WIF,
  no-service-account benchmark VMs, bounded artifacts, checksum recovery, cleanup,
  and failure precedence.

## Synthetic and local validation

- [x] JMH compilation and the repository forked smoke pass for all five new benchmark
  classes.
- [x] The complete synthetic 84-entry canonical member derives successfully.
- [x] Removing one matrix entry fails closed; queue/publication auxiliary metrics are
  normalized and retained.
- [x] Existing and new workflow request matrices, V1 dry-run propagation, set
  checkpointing, comparison, upload, artifact, and cleanup tests pass without GCP.
- [x] Static workflow tests prove manual-only dispatch, pinned actions, bounded
  permissions, and absence of automatic registration.
- [x] The 100k local calibration and runtime-budget calculation are recorded in
  [the Phase 7 local calibration](PHASE_7_LOCAL_CALIBRATION.md).

## Protected evidence still required

- [ ] Merge this implementation to protected `master`; verify CI and exact source
  ancestry before any paid execution.
- [ ] Run one Standard, Actions-retained `ranked-v31` experiment to confirm that all
  84 cells, derivation, cleanup, and upload staging finish below the 60-minute slot
  cap.
- [ ] Run a three-member Standard/GCS `ranked-v31` canonical set; review ranges,
  allocation, GC, writer throughput, queue evidence, and snapshot progress.
- [ ] Run a directly comparable three-member Standard/GCS regression-lane candidate
  with the frozen preset used by `v3.0.0-cloud` and review the comparison report.
- [ ] Register the reviewed feature family under a new immutable name such as
  `v3.1.0-ranked-cloud`; never replace or compare it directly with `v3.0.0-cloud`.

Phase 7 remains open until the protected evidence is reviewed. Phase 8 release
hardening does not start merely because the infrastructure patch is merged.
