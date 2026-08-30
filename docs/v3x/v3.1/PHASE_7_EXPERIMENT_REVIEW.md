# V3.1 Phase 7 experiment review

## Decision

Run `33292769552`, attempt 1, was a successful bounded calibration but is not the
accepted pre-canonical experiment. It proved that the frozen workload fits the
60-minute slot cap and that the workflow recovers, verifies, derives, stages, and
cleans up its evidence. Review also found that `writerQueueMaximum` was normalized
from JMH's summed AuxCounters score rather than from the maximum raw iteration value.

The correction was merged to protected `master` and run `33295811488`, attempt 1,
successfully exercised it. The corrected run is the accepted pre-canonical experiment:
it preserves the complete matrix, derives queue maximum one from the raw iterations,
records positive snapshot progress, finishes below the slot cap, and cleans up its VM.
Neither experiment is canonical evidence or eligible for baseline registration.

## Frozen identity

| Control | Observed value |
|---|---|
| Source commit | `672fc7707302b7f9911ba30b62ea39743b9b7796` |
| Evidence profile | `experiment` |
| Mode / repeats | `ranked-v31 / 1` |
| Provisioning / machine | `standard / c3d-standard-30` |
| Image | `ubuntu-2404-noble-amd64-v20260826` |
| JVM | OpenJDK `21.0.12`, `-Xms32g -Xmx64g` |
| Suite | `v3.1-ranked-suite-v1` |
| Set | `gse-set-v1-f2c50cb231898ce71a437494e4da333c4fefc801d9d3b73e0536b57efcda2e1f` |
| Configuration fingerprint | `sha256:b52dec379b78d1fc0d760d3cf18c64f2b0c0b56d97c8fa8ec2ec378f5cc57422` |
| Environment fingerprint | `sha256:51080e358d847728b6aaedb238f4d873158a1fde09b06c43b95a2b13ce2595f9` |

The workflow result was `success`; the member and set statuses were
`VALID_EXPERIMENT` and `VALID_EXPERIMENT_SET`. Artifact checksums, raw recovery,
source identity, and the single selected attempt all verified without warnings or
replacement.

## Matrix and runtime

The manifest contains exactly 84 JMH configurations and 460 normalized metrics:

| Workload | Configurations | JMH elapsed |
|---|---:|---:|
| Phrase | 22 | 9m 05s |
| BOOL minimum-should-match | 36 | 21m 40s |
| Fuzzy dictionary | 10 | 3m 53s |
| Text initial build | 2 | 1m 38s |
| Text publication | 12 | 4m 52s |
| Mixed-concurrency sample | 1 | 3m 19s |
| Mixed-concurrency throughput | 1 | 3m 17s |

The JMH phases consumed 47m 44s. End-to-end orchestration ran from
`20260830T043442Z` to `20260830T052457Z`, or 50m 15s, leaving 9m 45s below the
3,600-second slot cap. Cleanup was attempted and succeeded; the artifact was recovered
and checksum-verified without preemption or restart.

## Concurrency observations

The one-member observations are diagnostics, not claims or comparison thresholds:

- combined throughput was `56.736 ops/s`, with `43.416 read ops/s` and
  `13.320 write ops/s`;
- sample mean was `301.474 ms/op`; read and write sample means were `365.137 ms/op`
  and `81.597 ms/op`;
- the sample and throughput cells recorded 198 and 218 successful snapshot
  publications;
- normalized allocation was approximately 127.0 MB/op and 126.5 MB/op, with about
  6.1-6.2 GB/s allocation rate; and
- every logged iteration reported writer queue maximum one, and successful trial
  teardown proves the final queue depth was zero.

The high allocation rate is retained for canonical range review; this experiment does
not define whether it is acceptable.

## Queue-maximum defect and correction gate

`WriterEvidence` uses JMH `AuxCounters.Type.EVENTS`. JMH therefore reports the sum of
the ten per-iteration `writerQueueMaximum` values across two forks and five measured
iterations. The original derivation stored that reported sum, `10`, under an identity
named `writerQueueMaximum`, although the log showed `(min, avg, max) = (1, 1, 1)`.

The correction derives this metric from the maximum value in the exact `2 x 5` JMH
`rawData` matrix, validates that the raw event-count sum agrees with JMH's reported
score, changes the statistic to `maximum`, and omits the confidence/error fields that
describe the summed score. A local forked JMH control reproduced raw sum 10 and raw
maximum one; malformed dimensions fail closed in the Python evidence tests.

The corrected experiment must preserve the 84 configurations, complete below the
slot cap, report queue maximum one from `rawData`, retain positive snapshot progress,
and clean up successfully before canonical evidence is authorized.

## Corrected experiment acceptance

| Control | Observed value |
|---|---|
| Workflow run / attempt | `33295811488 / 1` |
| Source commit | `1daa4489630b9077b0e6decd533f4e4414e6d75d` |
| Request | `experiment / ranked-v31 / 1 / standard / c3d-standard-30 / 30m / actions` |
| Set | `gse-set-v1-8f68a9b98055d33188e5624ca55eec28add3b9f0e829a36430c1983ef567e902` |
| Set status | `VALID_EXPERIMENT_SET` |
| Orchestration lifetime | 50m 49s |
| Queue maximum | `1` in both mixed cells |

The orchestrator ran from `20260830T055851Z` to `20260830T064940Z`, leaving 9m 11s
below the 3,600-second cap. The member contains exactly 84 configurations and 460
normalized metrics. Artifact recovery, checksums, source identity, result derivation,
and cleanup all passed without preemption, restart, replacement, or warning. This
satisfies the correction gate and authorized the separately reviewed three-member
canonical feature run.
