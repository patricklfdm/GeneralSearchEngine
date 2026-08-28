# V3 cloud soak early-window stabilization results

## Decision

The early-window stabilization experiment is complete. Ten independent Standard
C3D-30 runs provide valid retained evidence: six 600-second screening measurements,
two 1,800-second confirmations, and one 600-second measurement-only JFR target/control
pair. Every run reached `READY`, started its selected measurement cell, completed
without an engine error, preserved the required state identity, passed its checksum
verification, and cleaned up its VM.

The frozen screening comparison passed both the drift and absolute-rate gates for the
aggregate and for TEXT, BOOL, PHRASE, and FUZZY independently. `revision-update`
averaged 27.162 fewer reads per second than `stable-update` (4.458% of the stable mean)
and its mean early-to-late drift was 6.445 percentage points worse. All three paired
rounds agreed in direction. The unprofiled 1,800-second confirmation preserved that
direction: revision-changing updates measured 73.187 fewer reads per second (11.882%
of the stable control) and 10.977 percentage points more negative drift.

The formal outcome is therefore **jointly supported factor requiring a separately
contracted engine investigation**. Under this workload, changing document content
during replacement is a supported differentiating factor relative to replacing the
same IDs with content-stable documents. This is not a claim that the public API is
incorrect, that a particular search method is defective, or that an optimization is
already justified. The governing contract expressly keeps product implementation out
of this phase.

## Evidence identity and controls

All ten runs used clean pushed commit
`cca124cc62838e23e1125246f2d415f6a94a2b05` and reported:

- GCP project `gse-benchmark`, zone `us-west4-a`;
- Standard `c3d-standard-30` on one fresh VM per run;
- exact image `ubuntu-2404-noble-amd64-v20260826`, image ID
  `5563818848645508791`;
- OpenJDK `21.0.12+8-1~24.04` and `-Xms8g -Xmx16g`;
- 300 seconds of read-only stabilization in five 60-second windows;
- 100,000 documents, 16 readers, one measurement writer, and top K 10;
- `zipf-en-medium-4`, one-second samples, and no dynamic index cycles;
- successful artifact recovery, checksum verification, and VM cleanup.

Stabilization and measurement use separate counters and reservoirs. The selected
measurement starts only after all frozen readiness predicates pass. The profile pair
starts the built-in JFR after readiness and immediately before measurement workers are
released, then stops it after those workers join. Profiled rates are diagnostic context
and do not enter the frozen comparison or confirmation decision.

Raw result directories remain ignored generated evidence rather than Git content. The
deterministic screening comparison is retained as
`benchmark-results/v3-production/cca124cc-stabilized-screening-comparison.properties`;
its SHA-256 is
`8a32cc5bbd91f07cbaa7dbfd65b05b76cf2bec0f219e9706e8849dbe46a48206`.

## Retained runs and readiness

The screening order followed the frozen three paired rounds: stable then revision,
revision then stable, and stable then revision. Confirmation reversed the last order,
then the profile target/control pair ran revision followed by stable.

| Order | Purpose | Cell | Result directory | Status | Handoff |
|---:|---|---|---|---|---:|
| 1 | screening | `stable-update` | `20260828T083543Z-cca124cc6283-stabilized-investigation` | READY | 0.135 s |
| 2 | screening | `revision-update` | `20260828T085632Z-cca124cc6283-stabilized-investigation` | READY | 0.136 s |
| 3 | screening | `revision-update` | `20260828T091500Z-cca124cc6283-stabilized-investigation` | READY | 0.159 s |
| 4 | screening | `stable-update` | `20260828T093624Z-cca124cc6283-stabilized-investigation` | READY | 0.154 s |
| 5 | screening | `stable-update` | `20260828T095458Z-cca124cc6283-stabilized-investigation` | READY | 0.159 s |
| 6 | screening | `revision-update` | `20260828T101306Z-cca124cc6283-stabilized-investigation` | READY | 0.156 s |
| 7 | confirmation | `revision-update` | `20260828T103403Z-cca124cc6283-stabilized-investigation` | READY | 0.154 s |
| 8 | confirmation | `stable-update` | `20260828T112501Z-cca124cc6283-stabilized-investigation` | READY | 0.159 s |
| 9 | profile | `revision-update` | `20260828T163751Z-cca124cc6283-stabilized-investigation` | READY | 0.352 s |
| 10 | profile | `stable-update` | `20260828T170647Z-cca124cc6283-stabilized-investigation` | READY | 0.323 s |

Each stabilization retained 301 samples, had zero mutations and errors, left snapshot
version 100 and the loaded corpus digest unchanged, and passed aggregate plus per-query
rate and latency stability checks. Every handoff was far below the frozen 30-second
limit. Screening and profile measurements retained 601 samples; confirmations retained
1,801.

## State-identity controls

All mutation cells advanced snapshot version by exactly the number of completed writes.
Stable updates preserved the initial corpus digest; revision updates changed it.

| Purpose and cell | Writes | Snapshot | Corpus changed |
|---|---:|---:|---:|
| screening stable 1 | 52,388 | 100 to 52,488 | false |
| screening revision 1 | 51,268 | 100 to 51,368 | true |
| screening revision 2 | 51,164 | 100 to 51,264 | true |
| screening stable 2 | 52,609 | 100 to 52,709 | false |
| screening stable 3 | 51,274 | 100 to 51,374 | false |
| screening revision 3 | 51,081 | 100 to 51,181 | true |
| confirmation revision | 151,391 | 100 to 151,491 | true |
| confirmation stable | 153,624 | 100 to 153,724 | false |
| profile revision | 50,356 | 100 to 50,456 | true |
| profile stable | 50,883 | 100 to 50,983 | false |

This isolates content identity as the intended difference while both comparison cells
continue to publish snapshots at a similar write rate. It does not isolate which
content-derived index property or query-execution behavior produces the rate change.

## Screening observations

Whole-run rates and deterministic bucket-two-to-bucket-six read drift were:

| Round and cell | Read ops/s | Write ops/s | Aggregate drift | TEXT | BOOL | PHRASE | FUZZY |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 stable | 608.343 | 87.270 | +0.276% | +0.294% | +0.340% | +0.241% | +0.228% |
| 1 revision | 582.433 | 85.400 | -6.951% | -6.931% | -6.877% | -7.020% | -6.976% |
| 2 revision | 582.761 | 85.234 | -5.769% | -5.754% | -5.773% | -5.742% | -5.806% |
| 2 stable | 613.651 | 87.640 | +0.146% | +0.125% | +0.118% | +0.190% | +0.151% |
| 3 stable | 605.865 | 85.411 | -0.297% | -0.317% | -0.357% | -0.218% | -0.277% |
| 3 revision | 581.180 | 85.096 | -6.491% | -6.475% | -6.500% | -6.515% | -6.475% |

The deterministic comparator evaluated drift and absolute throughput separately. Means
below are arithmetic means; variability is sample standard deviation across three
runs. Contrast magnitudes are the absolute revision-versus-stable group difference.

| Metric | Revision drift mean +/- SD | Stable drift mean +/- SD | Drift contrast / threshold | Revision rate mean +/- SD | Stable rate mean +/- SD | Rate contrast / threshold | Joint |
|---|---:|---:|---:|---:|---:|---:|---:|
| Aggregate | -6.404 +/- 0.596 pp | +0.042 +/- 0.301 pp | 6.445 / 1.192 pp | 582.125 +/- 0.834 | 609.286 +/- 3.978 | 27.162 / 7.956 | true |
| TEXT | -6.386 +/- 0.594 pp | +0.034 +/- 0.316 pp | 6.421 / 1.187 pp | 145.529 +/- 0.208 | 152.321 +/- 0.995 | 6.792 / 1.989 | true |
| BOOL | -6.383 +/- 0.561 pp | +0.034 +/- 0.356 pp | 6.417 / 1.122 pp | 145.534 +/- 0.206 | 152.321 +/- 0.989 | 6.787 / 1.978 | true |
| PHRASE | -6.426 +/- 0.644 pp | +0.071 +/- 0.251 pp | 6.497 / 1.287 pp | 145.537 +/- 0.211 | 152.326 +/- 0.992 | 6.789 / 1.984 | true |
| FUZZY | -6.419 +/- 0.587 pp | +0.034 +/- 0.272 pp | 6.453 / 1.174 pp | 145.525 +/- 0.210 | 152.318 +/- 1.001 | 6.793 / 2.002 | true |

The table shows the larger variability threshold for each gate. Every drift contrast
also exceeded the independent three-percentage-point minimum. Every absolute-rate
contrast exceeded the independent 3%-of-stable-mean minimum. Paired directions were
consistent in all three rounds, rate and drift directions agreed, and every query kind
agreed with the aggregate. The frozen differentiating-factor decision is therefore
`true` without selecting or discarding a run after observing its score.

## Unprofiled confirmation

The two 1,800-second measurements preserved the screening direction:

| Cell | Read ops/s | Write ops/s | Aggregate drift | TEXT | BOOL | PHRASE | FUZZY |
|---|---:|---:|---:|---:|---:|---:|---:|
| `revision-update` | 542.752 | 84.072 | -11.432% | -11.417% | -11.445% | -11.432% | -11.434% |
| `stable-update` | 615.939 | 85.312 | -0.455% | -0.453% | -0.455% | -0.462% | -0.451% |

Revision was 73.187 reads per second below stable and its drift was 10.977 percentage
points more negative. All four query kinds retained the same direction. The revision
run's rate decline and heap-band growth raised review flags; the run remained valid,
with zero errors, final queue depth zero, queue maximum one, and low GC time. The stable
control remained nearly flat. Confirmation is one target/control observation rather
than a new variance estimate, so it validates direction but does not replace the
three-round screening statistics.

## Measurement-only JFR evidence

The authorized target/control profiles each cover only the 600-second measurement
phase. Both use the same JDK `profile` configuration, are below the 512 MiB bound, are
parseable by JDK 21 `jfr`, and are included in their checksum manifests.

| Cell | JFR bytes | Execution samples | Allocation samples | Young GCs | GC wall time | Monitor enters |
|---|---:|---:|---:|---:|---:|---:|
| revision | 48,998,315 | 285,293 | 172,609 | 1,117 | 2.07 s | 0 |
| stable | 49,671,863 | 285,446 | 172,562 | 1,169 | 1.99 s | 0 |

No old collection occurred and the `contention-by-site` view contained no events.
Reader CPU load was evenly distributed across the 16 reader threads in both recordings;
writer CPU load was 1.86% for revision and 1.89% for stable. Writer allocation pressure
was similarly close at 8.65% and 8.26%.

The dominant execution samples are mostly shared:

| Method or family | Revision | Stable |
|---|---:|---:|
| `PersistentAvlMap.get` | 28.68% | 29.63% |
| `Bm25Scorer.evaluate` | 24.17% | 23.54% |
| phrase-plan/position family | 15.35% | 15.49% |
| `FuzzyPlan.evaluateFuzzy` leaf | 5.74% | 2.01% |

The phrase family combines `PhrasePlan.evaluate`, `matches`, `validate`, `matchesAt`,
and `contains`; grouping is necessary because JIT compilation and inlining changed
which frame received samples. The fuzzy leaf difference is a candidate for a future
engine investigation, not an attribution result. A stack-aware investigation must
first determine whether it reflects more fuzzy candidate work, a compilation-shape
difference, or sampling attribution elsewhere in the common execution path.

Allocation shape is nearly identical. The four largest sites account for 81.42% of
revision allocation pressure and 81.96% of stable allocation pressure:

| Allocation site | Revision | Stable |
|---|---:|---:|
| `Integer.valueOf` | 27.29% | 27.35% |
| `Unsafe.allocateUninitializedArray` | 26.35% | 26.30% |
| `SearchExecutor.lambda$execute$0` | 14.64% | 14.98% |
| `ScoreMatch.match` | 13.14% | 13.33% |

The profiles therefore identify the existing lookup, scoring, phrase, fuzzy, and result
construction paths as bounded candidates, but do not reveal a revision-only allocation
site, lock bottleneck, or GC mechanism. Their own rates were 583.785 reads/s with
-6.263% drift for revision and 613.629 reads/s with -0.184% drift for stable. Those
values are directionally consistent diagnostic context only and are deliberately
excluded from the statistical decision.

## Interpretation, limitations, and boundary

The completed experiment resolves the previous early-window uncertainty. A five-minute
read-only stabilization made all ten cells READY, the three stable screening runs then
remained flat, and the revision group retained a low sample standard deviation. The
supported factor is specifically content-changing replacement under sustained snapshot
publication. Snapshot publication alone is not sufficient under this workload because
the content-stable controls publish a comparable number of snapshots without the same
read-rate trajectory.

The evidence does not yet distinguish among changing term/posting distributions,
candidate-set growth, position-list work, fuzzy expansion work, accumulated immutable
index state, or another content-derived execution cost. JFR is sampled rather than an
exact accounting system; leaf percentages can move with compilation and inlining, and
the two profiles are one fresh VM each. The fixed corpus, query mix, concurrency,
hardware, image, and JVM make this workload-specific evidence, not a portable SLA or a
general regression threshold.

This phase closes with **jointly supported factor requiring a separately contracted
engine investigation**:

- no product or public API change is authorized here;
- no retained run is excluded or rewritten;
- no profiled throughput enters the frozen statistics;
- no memory leak, synchronization defect, or single hot method is claimed;
- no additional paid run belongs to this contract;
- a follow-up must freeze correctness oracles, candidate/posting cardinality evidence,
  stack-aware CPU/allocation comparisons, and explicit stop rules before engine work.

The governing methodology is the
[cloud soak early-window stabilization contract](CLOUD_SOAK_EARLY_WINDOW_STABILIZATION.md).
The earlier inconclusive experiment remains valid under its own frozen rules in the
[cloud soak root-cause results](CLOUD_SOAK_ROOT_CAUSE_RESULTS.md); this separately
contracted follow-up adds stabilization and absolute-rate controls rather than
retroactively changing that result.
