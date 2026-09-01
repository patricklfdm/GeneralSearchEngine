# V3.4 Phase 5 final-candidate and cloud-evidence checklist

Status: final-coordinate preparation and local candidate validation are complete on
`release/v3.4.0`, based on the accepted Phase 4 protected-master merge. This phase
converts the exact candidate before any paid evidence is started. It does not publish,
tag, or claim the required heap, two-hour, canonical, or registered evidence
prematurely.

## Accepted entry boundary

- [x] Phase 4 merged through protected PR #71 as
  `0433de39a318a1885322ee22377e3b8a76738c62`.
- [x] Exact-commit protected-master CI succeeded in
  [run 33470856585](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33470856585)
  for that merge.
- [x] `release/v3.4.0` starts from that exact protected-master commit.
- [x] Phase 4 changed no production source or supported public API and ran no paid
  cloud job.

## Final version conversion

- [x] Core, processor, reactor, travel example, and all three independent consumer
  coordinates convert atomically from `3.4.0-SNAPSHOT` to final `3.4.0`.
- [x] Benchmark evidence metadata reports final `3.4.0` rather than the development
  coordinate.
- [x] `project.build.outputTimestamp` remains frozen at
  `2026-08-31T00:00:00Z` in both publishable projects.
- [x] The changelog receives the dated `3.4.0 — 2026-08-31` candidate entry without
  claiming publication.
- [x] Published `3.3.0` remains the current stable dependency until remote publication
  of `3.4.0` is independently verified.
- [x] No production implementation, supported descriptor, existing cloud preset, or
  published baseline changes during conversion.

## Final local candidate gates

- [x] Exact `3.4.0` version alignment passes across all seven active coordinates.
- [x] Core and reactor clean verification pass with 383 core and five processor tests,
  no failures or skips.
- [x] V1/V2/V3 independent consumers and the travel example pass against final
  coordinates.
- [x] V3.4 zero-addition fixtures and fresh-isolated Japicmp pass against all seven
  published baselines.
- [x] Strict core/processor Javadocs and exactly six publishable release JARs pass the
  service-entry boundary.
- [x] Two clean final builds produce byte-identical six-JAR output; retain their
  SHA-256 values.
- [x] Retained JMH, V3.4 reduced hardening, Cloud Benchmark unit/shell/fake lifecycle,
  Markdown, and diff-hygiene gates pass.

### Reproducible final artifacts

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-3.4.0.jar` | `bd678d2b50b5c59ae67a3b8869c0ad35a1ff810c2b7cb62b78882ae2f341e147` |
| `general-search-engine-3.4.0-sources.jar` | `9dcead48e29a932c18932b1343855917b369d7df2cb32842a397eecd91cc6e26` |
| `general-search-engine-3.4.0-javadoc.jar` | `f92638b3433e1dc244078739a1ab9144ee32e06ee61886d214b1b81c683786ba` |
| `general-search-engine-processor-3.4.0.jar` | `bf6935196e93b9ceaf8a7be0d09bfe54288f3cf5083d6c29e6a1f820f5459d65` |
| `general-search-engine-processor-3.4.0-sources.jar` | `a849b86579795047db224547a9d40d3e9df81e96d3cb450f0d6a6c97d3ff7eae` |
| `general-search-engine-processor-3.4.0-javadoc.jar` | `a002207e698ba0ddd3ceda7fbf7f83f4f5f39cffdaabc853b2b153e5cac8e3f7` |

Python `3.11.15` executed all 65 Cloud Benchmark unit tests. Shell analysis,
fake-gcloud, set, upload/registration, cleanup, failure, cancellation, timeout,
resume, replacement, and reduced final-suite gates also pass without GCP access.

## Eligible heap evidence

- [ ] Run the required `4g`, `8g`, and `16g` G1 cells on one suitable final-source
  host with sufficient physical memory and no active swap.
- [ ] Preserve identical corpus/workload identity, all individual cells, manifests,
  checksums, GC/heap/allocation fields, and explicit eligibility decisions.
- [ ] Do not treat the earlier swap-active local calibration or the fixed 16 GiB
  canonical JVM as a substitute for the complete heap matrix.

This matrix remains a separate diagnostic and does not create a new Cloud Benchmark
mode, suite, preset, or baseline identity. After the final-coordinate commit has
passed protected-master CI, build that exact checkout with `./mvnw clean -Pjmh
-DskipTests package`, record the source/JVM/host identity and zero-swap precondition,
then retain the complete output of:

```bash
java -cp target/benchmarks.jar \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V34HeapMatrixRunner \
  --heaps=4g,8g,16g \
  --documents=100000 \
  --tokens=16 \
  --operations=1000 \
  --seed=34 \
  --axis=sparse-vocabulary \
  --require-no-swap=true \
  --timeout-seconds=600
```

Run all three child JVMs on the same host and checkout. A missing cell, relaxed swap
guard, changed workload, timeout, resource exhaustion, or non-success matrix summary
keeps this gate open. This output is reviewed as diagnostic evidence beside, but is
never added to, the frozen `final-v34` canonical member file set.

## Required two-hour experiment

- [ ] Merge the final-coordinate candidate through protected review and require
  exact-merge master CI success before paid execution.
- [ ] Dry-run and review exactly one `final-v34` experiment using Standard
  `c3d-standard-30`, GCS retention, the `v3.4-final-in-memory-v1` preset, and `2h`.
- [ ] Run from the exact protected final-source commit and retain the immutable plan,
  raw/normalized evidence, durable upload receipt, and cleanup proof.
- [ ] Review all correctness, liveness, queue-drainage, window, drift, identity, and
  integrity fields; partial or interrupted evidence remains ineligible.

## Final canonical set and registration

- [ ] Dry-run and review a three- or five-member `final-v34` canonical set using
  Standard `c3d-standard-30`, GCS retention, and the fixed 30-minute window.
- [ ] Retain every member, median/variation, exact environment and source identity,
  aggregation report, durable upload receipt, and cleanup proof.
- [ ] Review the canonical set through a protected evidence PR before registration.
- [ ] Register only `v3.4.0-in-memory-cloud`; never append these results to
  `v3.0.0-cloud` or `v3.1.0-ranked-cloud`.

## Phase 6 entry

- [ ] Close the eligible heap, required two-hour, canonical, durable-retention,
  cleanup, review, and registration gates above.
- [ ] Preserve the accepted exact final source; any production change invalidates the
  affected evidence and returns to contract review.
- [ ] Prepare final consumers, compatibility, artifacts, release documentation, and
  signed `v3.4.0` publication on a separate Phase 6 release step.
- [ ] Begin no V4 durability implementation until signed publication, remote
  verification, deployment, GitHub Release, and post-publication evidence complete.
