# V4.0 Phase 6 local pre-cloud baseline

## Source boundary

Phase 6 starts from protected Phase 5 PR #82 merge
`c9a8b4725f3c44bced40764d1a9b3e9a4eb37b51`; exact-master CI run `33597658600`
passed. The working branch is `feat/v4.0-phase6-performance-hardening`.

## Diagnostic smoke

The first dirty-source local smoke used 1,000 documents, 40 single updates, ten
20-element bulk updates, four producers, 80 concurrent logical units and a one-second
mixed long run. It is diagnostic evidence, not canonical or baseline-eligible.

- in-memory and durable final checksums both equal `4104998396018527713`;
- durable single completion p50/p95/p99 was approximately
  `10.13/11.60/16.67 ms`;
- in-memory single completion p50/p95/p99 was approximately
  `5.69/6.06/8.43 ms`;
- durable 20-element bulk completion p50/p95/p99 was approximately
  `4.52/8.50/8.50 ms`;
- 80 concurrent units completed in 20 successful forces: average group size `4.0`,
  maximum group size `4`;
- explicit checkpoint completed in approximately `61.9 ms`, with retained
  amplification `1.178x` and observed temporary amplification `2.658x` over encoded
  keys/documents;
- WAL-only, checkpoint-only and checkpoint-plus-WAL total open completed in
  approximately `9.11/5.82/3.12 ms`; and
- the mixed cell made 99 durable writes, more than seven million reads and five
  checkpoints while remaining `OPEN` and bounded.

These numbers are sensitive to the developer filesystem, cache state, scheduler and
dirty source. They demonstrate completeness and expose the expected force cost; they
must not be compared with registered cloud evidence or used as a performance promise.

## Current decision

No production optimization is justified. Actual force grouping is working, durable
overhead is visible rather than hidden, all three recovery paths are small at the smoke
scale, and retained bytes contract after checkpoint. The next evidence order is:

1. complete all local/CI gates;
2. merge the Phase 6 infrastructure through protected `master`;
3. run one paid experiment on that exact merge;
4. run the preserved-disk replacement-VM drill;
5. run the three-member canonical set on one exact final source; and
6. register `v4.0.0-durable-cloud` only after set validation and review.

## Local acceptance gates

The completed local implementation passed on 2026-09-02:

- `./mvnw clean test` and `./mvnw -f reactor/pom.xml clean test`;
- `./mvnw clean -Papi-compat test`, a fresh-repository
  `./mvnw clean -Partifact-compat verify`, and all independent consumers;
- unsigned release packaging, artifact-content inspection and reproducible-build
  comparison;
- Shell, Python and workflow-YAML parsing plus all fifteen Phase 6 Python contract
  tests; and
- the complete `scripts/verify-jmh-smoke.sh` chain, including all earlier V4 crash
  matrices, four durable/in-memory mutation cells, operational evidence validation,
  fake canonical assembly, split preserved-disk writer/recovery and paid-run dry-run.

The smoke timings above remain diagnostic because the source was uncommitted and the
host is not the frozen cloud machine. Passing local gates establishes correctness and
evidence plumbing only; it does not make the run baseline-eligible.

After the production preload correction, the complete Phase 6 gate passed again with
seventeen Python contract tests and the JMH-only bounded-batch regression test. A
separate local production-shape diagnostic used all 100,000 documents and
`loadBatchSize=1000`, exercised every operational cell with the requested long-run
duration reduced to one second, and produced a valid `PASS` bundle. Its dirty source,
local host and reduced requested duration make it correctness evidence only.

## Paid-lane staged rollout findings

Three exact-master experiment attempts failed closed before producing performance
evidence:

- run `33605510928` was rejected by the WIF provider because its original condition
  allowed only `cloud-performance.yml`; no VM or disk was created;
- run `33605963272` created its data disk, then VM creation was rejected because the
  custom role lacked `compute.disks.use`; `compute.disks.use` and
  `compute.disks.delete` were added without granting a broad Compute role; and
- run `33606438261` reached the cold VM and exposed a missing `unzip` prerequisite:
  Maven Wrapper fell back to a tarball while retaining the pinned ZIP checksum.

The next exact-master experiment reached the production probe and failed closed before
measurement because its 100,000-document corpus was submitted as one atomic mutation,
above the in-memory engine's 1,000-item limit. The corrected probe keeps that product
limit unchanged, preloads every operational corpus through one bounded-batch helper,
records `loadBatchSize`, and exercises a corpus larger than the limit in the JMH-only
test gate. This attempt is not an experiment member or baseline candidate.

The corrected experiment then passed on exact protected-master source
`a74b2d27498232b0440ea1856c1cee54a80a1c08` as run `33611955012`; its member and
single-member experiment set both passed independent local validation, and its cleanup
receipt reported the writer VM and persistent disk absent. The first preserved-disk
drill on that source, run `33612817180`, failed closed when the replacement VM could
inspect the writer's bytes but its recovery verifier could not reopen them. The
replacement VM can receive a different numeric UID, so the remote recovery bootstrap
now normalizes ownership only on the dedicated drill workspace before the independent
content inspector and recovery JVM run. The same attempt also exposed that the existing
Environment variable is already a complete `gs://bucket` URI; the V4 workflows no
longer prepend a second scheme and now validate that exact contract. Its retained
receipt recorded `runStatus=FAIL` with writer VM, recovery VM and persistent disk
deletion all `PASS`, so it is not failure-drill acceptance evidence and left no paid
resource behind.

The WIF provider now has an exact three-workflow allowlist, the role has the two narrow
data-disk permissions, and both remote bootstraps install `unzip`. Independent
post-run describes returned not-found for the VM and disk names from runs
`33605963272` and `33606438261`. These are infrastructure findings with verified
cleanup, not experiment members or baseline candidates.
