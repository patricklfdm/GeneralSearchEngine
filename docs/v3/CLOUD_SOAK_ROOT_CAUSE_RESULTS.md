# V3 cloud soak root-cause investigation results

## Decision

The benchmark-only root-cause investigation is complete. Seven independent Standard
C3D-30 runs provide valid retained evidence: the three-cell screening and two further
rounds of the strongest `revision-update` versus `stable-update` contrast. Every run
completed without an engine error, checksum failure, preemption, artifact-recovery
failure, or VM-cleanup failure.

The evidence is suggestive but does not satisfy the frozen attribution rule.
`revision-update` produced negative aggregate and per-query read-rate drift in all three
runs. The first two `stable-update` runs were essentially flat, but its third run began
with an unusually low bucket-two rate and improved by 9.760% by bucket six. That valid
observation increased the stable group's sample standard deviation enough that neither
the aggregate contrast nor any query-specific contrast reached twice the larger group
standard deviation.

The formal outcome is therefore **inconclusive without product work**. This phase does
not authorize an engine change, a 1,800-second confirmation, or JFR collection. The
consistent revision signal remains a hypothesis for a separately contracted experiment,
not evidence of a product defect, memory leak, or content-dependent index regression.

## Evidence identity and controls

All seven runs used clean pushed commit
`2d0b8ed0cc50eb6dfb004a57a6ca94f440e78587` and reported:

- GCP project `gse-benchmark`, zone `us-west4-a`;
- Standard `c3d-standard-30` provisioning on one fresh VM per run;
- 30 logical CPUs reporting `AMD EPYC 9B14`;
- exact image `ubuntu-2404-noble-amd64-v20260826`, image ID
  `5563818848645508791`;
- OpenJDK `21.0.12+8-1~24.04`;
- `-Xms8g -Xmx16g`;
- 600 seconds, 100,000 documents, 16 readers, top K 10;
- `zipf-en-medium-4`, one-second sampling, and no dynamic index cycles;
- per-query instrumentation enabled and JFR disabled.

Each result reports `status=PASS`, `exit_code=0`, `errors=0`, unchanged final document
count, valid base and investigation analysis, and byte-valid `checksums.sha256`. Each
orchestration record reports `stage=FINISHED`, successful artifact recovery and
checksum verification, no preemption, and successful cleanup. Raw result directories
remain ignored generated evidence and are not committed to Git.

## Retained runs and execution order

The initial screening followed `revision-update`, `read-only`, `stable-update`. The
selected revision-versus-stable contrast then reversed order in round two and reversed
back in round three.

| Order | Cell | Round | Result directory |
|---:|---|---|---|
| 1 | `revision-update` | 1 | `20260828T051426Z-2d0b8ed0cc50-investigation` |
| 2 | `read-only` | Screening control | `20260828T053136Z-2d0b8ed0cc50-investigation` |
| 3 | `stable-update` | 1 | `20260828T054611Z-2d0b8ed0cc50-investigation` |
| 4 | `stable-update` | 2 | `20260828T060139Z-2d0b8ed0cc50-investigation` |
| 5 | `revision-update` | 2 | `20260828T061541Z-2d0b8ed0cc50-investigation` |
| 6 | `revision-update` | 3 | `20260828T062939Z-2d0b8ed0cc50-investigation` |
| 7 | `stable-update` | 3 | `20260828T064338Z-2d0b8ed0cc50-investigation` |

The state-identity controls held in every run:

| Cell and round | Writes | Snapshot | Corpus changed |
|---|---:|---:|---:|
| `revision-update` 1 | 52,168 | 100 to 52,268 | true |
| `read-only` | 0 | 100 to 100 | false |
| `stable-update` 1 | 52,337 | 100 to 52,437 | false |
| `stable-update` 2 | 52,826 | 100 to 52,926 | false |
| `revision-update` 2 | 51,925 | 100 to 52,025 | true |
| `revision-update` 3 | 50,567 | 100 to 50,667 | true |
| `stable-update` 3 | 50,891 | 100 to 50,991 | false |

For every mutation run, final snapshot version equals initial version plus completed
writes. The read-only snapshot and digest remained unchanged. Stable updates advanced
the snapshot while preserving the initial corpus digest; revision updates advanced the
snapshot and changed the digest.

## Per-run observations

Whole-run rates and deterministic bucket-two-to-bucket-six read drift were:

| Cell and round | Read ops/s | Write ops/s | Aggregate drift | TEXT | BOOL | PHRASE | FUZZY |
|---|---:|---:|---:|---:|---:|---:|---:|
| `revision-update` 1 | 581.819 | 86.889 | -5.828% | -5.843% | -5.765% | -5.816% | -5.849% |
| `read-only` | 615.825 | 0.000 | +0.074% | +0.087% | +0.074% | +0.048% | +0.087% |
| `stable-update` 1 | 607.466 | 87.167 | +0.291% | +0.337% | +0.344% | +0.238% | +0.238% |
| `stable-update` 2 | 602.728 | 87.982 | +0.148% | +0.130% | +0.163% | +0.210% | +0.090% |
| `revision-update` 2 | 587.121 | 86.483 | -5.906% | -5.861% | -5.893% | -5.919% | -5.952% |
| `revision-update` 3 | 584.599 | 84.217 | -6.488% | -6.507% | -6.431% | -6.480% | -6.533% |
| `stable-update` 3 | 585.027 | 84.755 | +9.760% | +9.817% | +9.807% | +9.672% | +9.747% |

The read-only control was flat in both operation rate and mean latency. The first two
stable runs were also flat despite publishing approximately 52,000 snapshots each.
All three revision runs declined across every query kind. Their query mean-latency
drifts were positive, ranging from 4.172% to 10.474%; the third run's TEXT mean latency
crossed the ten-percent review threshold. That review flag is diagnostic rather than a
failed run and cannot by itself establish attribution.

## Frozen contrast evaluation

The frozen rule requires all three of the following independently for the aggregate
and each query kind:

1. paired contrasts have the same direction in all three rounds;
2. the absolute difference between group mean drift is at least three percentage
   points;
3. the difference is at least twice the larger group sample standard deviation.

The values below are mean plus or minus sample standard deviation. Contrast is
`revision-update` mean minus `stable-update` mean.

| Metric | Revision drift | Stable drift | Contrast | 2 x larger SD | Same direction | Pass |
|---|---:|---:|---:|---:|---:|---:|
| Aggregate | -6.074% +/- 0.361 pp | +3.400% +/- 5.509 pp | -9.474 pp | 11.018 pp | true | false |
| TEXT | -6.070% +/- 0.378 pp | +3.428% +/- 5.534 pp | -9.498 pp | 11.068 pp | true | false |
| BOOL | -6.029% +/- 0.353 pp | +3.438% +/- 5.516 pp | -9.468 pp | 11.033 pp | true | false |
| PHRASE | -6.072% +/- 0.358 pp | +3.373% +/- 5.455 pp | -9.445 pp | 10.909 pp | true | false |
| FUZZY | -6.112% +/- 0.369 pp | +3.358% +/- 5.533 pp | -9.470 pp | 11.066 pp | true | false |

All paired contrasts have the same direction and all absolute mean differences exceed
three percentage points. None reaches twice the larger standard deviation. The frozen
rule therefore rejects the aggregate and every query-specific attribution.

## Third stable run and uncertainty

The third stable run is the source of the large stable-group variance. Its aggregate
bucket-two rate was 550.601 ops/s and its bucket-six rate was 604.342 ops/s, producing
the +9.760% drift. By comparison:

| Stable run | Bucket 2 | Bucket 6 | Drift |
|---|---:|---:|---:|
| 1 | 607.124 ops/s | 608.890 ops/s | +0.291% |
| 2 | 603.077 ops/s | 603.970 ops/s | +0.148% |
| 3 | 550.601 ops/s | 604.342 ops/s | +9.760% |

Every query kind in run three shows the same improvement, while mean latency declines
by 8.435% to 9.728%. Its late rate returns to the same approximately 604 ops/s band as
the first two stable runs; the difference is concentrated in the early steady bucket.

No frozen validity condition justifies excluding it. The run used the same commit,
image, JDK, CPU model, JVM, corpus, cell configuration, and duration; it has no error,
queue-pressure, checksum, preemption, collection, or cleanup failure. Treating it as an
outlier after seeing the result would violate the pre-registered rule. It therefore
remains part of the three-run statistics and prevents attribution.

## Why JFR was not triggered

All seven comparison runs used `GSE_SOAK_PROFILE=none`. The frozen contract permits a
separate JFR target/control pair only after an unprofiled contrast passes the three-run
rule and remains directionally consistent in a 1,800-second confirmation. No aggregate
or query-specific contrast passed, so the 1,800-second step was not authorized and the
JFR precondition was never reached.

The third revision run's TEXT mean-latency review flag does not override this sequence.
JFR could identify sampled execution or allocation candidates, but without a supported
control contrast it would invite post-hoc path selection. No profiled rates or JFR
artifacts are therefore part of this result set.

## Interpretation and boundary

The repeated revision runs are internally consistent, and the read-only plus first two
stable runs suggest that content-changing revisions deserve further study. However,
the valid third stable run demonstrates unresolved early-window variability in the
current experimental design. The evidence cannot distinguish an engine mechanism from
VM/runtime stabilization or another shared early-run effect with the confidence frozen
before execution.

This investigation closes with **inconclusive without product work**:

- no engine implementation or public API change is justified;
- no memory leak, snapshot accumulation defect, or content-dependent index regression
  is claimed;
- no retained run is discarded or rewritten;
- no additional paid run or profile belongs to this contract;
- any follow-up must begin with a new frozen contract, likely targeting early-window
  stabilization and absolute-rate controls before profiling a search path.

That follow-up is frozen separately in the
[cloud soak early-window stabilization contract](CLOUD_SOAK_EARLY_WINDOW_STABILIZATION.md).

The result is workload- and environment-specific diagnostic evidence, not a portable
SLA or a release regression threshold. The governing methodology remains the
[cloud soak root-cause investigation contract](CLOUD_SOAK_ROOT_CAUSE_INVESTIGATION.md),
and the preceding aggregate evidence remains in the
[cloud soak diagnostic results](CLOUD_SOAK_DIAGNOSTIC_RESULTS.md).
