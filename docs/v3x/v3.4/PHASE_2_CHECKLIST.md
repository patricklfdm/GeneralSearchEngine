# V3.4 Phase 2 checklist

Status: locally complete on `feat/v3.4-phase2-local-diagnostics` and pending
protected review. Phase 2 adds benchmark-only cold construction, extreme-corpus, and
bounded-heap diagnostics. It changes no production source, public API, cloud identity,
workflow, preset, paid resource, baseline registry, burst/long-run surface, or release
coordinate.

## Entry boundary

- [x] Phase 1 merged through PR #68 as protected-master commit
  `331284bd70b0234b97bb43cf693dd10af8e9b7e1`.
- [x] Exact-commit protected-master CI succeeded in run `33378644523`.
- [x] The independent Phase 2 branch starts from that exact merge.
- [x] Published artifacts, tags, releases, deployments, and existing cloud families
  remain immutable.

## Cold construction surface

- [x] Each retained repeat launches an independent JVM with one fixed seed, corpus
  digest, document count, token shape, batch size, and classpath.
- [x] Ordered checkpoints distinguish process start, engine construction, corpus
  generation, initial load, structured index, text index, ready state, first verified
  query, dynamic structured index, dynamic text index, and closure.
- [x] The runner rejects timeout, non-zero exit, resource exhaustion, malformed or
  missing checkpoints, non-monotonic time, zero checksum, invalid digest, and
  cross-process identity drift.
- [x] Five-process 100k and 1M document cells complete under the declared local cap;
  all per-process values, medians, variation, checksum, and corpus digest are retained
  in `PHASE_2_BASELINE.md`.

## Extreme-corpus surface

- [x] Nine independent bounded axes cover long text, high frequency, large vocabulary,
  sparse vocabulary, Zipf-heavy frequency, multiple fields, Unicode, repeated terms,
  and large logical position gaps/position-heavy phrase behavior.
- [x] Every cell validates IDs, canonical score/order, raw score bits, Explain parity,
  highlight source ranges, complete exact-total page walks, fuzzy truth, secondary
  text-field truth, and the applicable sloppy-phrase oracle.
- [x] Deterministic seed/schema digests and non-zero component checksums are emitted;
  invalid document/token/axis parameters fail before unbounded allocation.
- [x] The retained 1,000-document, 64-token matrix passes all nine axes.

## Heap diagnostic surface

- [x] Every cell is a separate JVM with exact equal `-Xms`/`-Xmx`, G1 collector,
  corpus/workload identity, operation count, physical memory, swap, and JVM arguments.
- [x] The probe records empty/loaded/peak/released heap, live-set estimate, thread
  allocation and bytes/op, GC count/time, engine counts, generated-token count,
  cursor/result count, checksum, and digest.
- [x] Full-GC controls use three explicit `System.gc()` requests with 25 ms settling;
  the method is diagnostic and freezes no universal byte threshold.
- [x] The runner classifies success, invalid environment, resource exhaustion,
  timeout, non-zero exit, missing result, and malformed result; no non-success cell is
  aggregated as passing.
- [x] Required `4g`/`8g`/`16g` cells were attempted fail-closed: active host swap made
  `4g`/`8g` ineligible, and `16g` exceeded visible physical memory. These are retained
  controlled rejections, not passing heap members.
- [x] Reduced 256m/512m forked smoke passes. Separate 4g/8g no-swap-relaxed calibration
  proves measurement and release controls but is explicitly ineligible for the final
  heap gate. The required eligible heap matrix remains open for a suitable host.

## Validation and scope audit

- [x] `V34LocalDiagnosticsTest` covers deterministic generation, every reduced extreme
  axis, checkpoint order/completeness, strict parsers, timeout/failure/exhaustion,
  invalid environment, and incomplete-output rejection.
- [x] `verify-v34-local-diagnostics.sh` launches reduced cold/extreme/heap processes;
  the existing retained JMH smoke invokes it after packaging.
- [x] Core, reactor, JMH-profile, consumer, compatibility, artifact, Markdown, and
  diff-hygiene gates pass.
- [x] `src/main/java`, processor production source, `.github`, cloud scripts/presets,
  examples, compatibility consumers, and release/baseline registries are unchanged.

## Phase 3 entry

- [ ] Merge this branch through protected review.
- [ ] Require exact-merge protected-master CI success.
- [ ] Create a new Phase 3 branch from that exact merge.
- [ ] Implement only bounded multi-producer burst/recovery and local long-run
  calibration surfaces.
- [ ] Do not implement `final-v34`, paid cloud execution, final conversion, release,
  or baseline registration in Phase 3.

The local heap environment exclusion is not a V3.4 heap pass. An eligible
`4g`/`8g`/`16g` result remains required before the V3.4/V4 exit gate can close.
