# V5.2 hosted M01–M04 acceptance — 2026-10-16

**Status:** the complete fresh hosted measurement cohort passed. The final
protected PR/master CI, cross-host remote qualification and paid cloud acceptance
remain open. See the [machine-readable record](hosted-measurement-acceptance.json).

## Exact source and complete result

[Run 38888573888, attempt 1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38888573888)
ran the dedicated experiment branch at
`bd16e3af8b0f2ccf1820a5df2746e45cd99f07b7`. All 14 jobs succeeded:
one shared build, six complete-history measurement shards, six independent replay
jobs and the final aggregate. This is an experiment workflow, not protected full CI.

| Coverage | Accepted result |
| --- | ---: |
| M01: five modes × three repetitions | 15 histories |
| M02 minimum-progress waits | 9 histories |
| M03 capacity | 2 histories |
| M04 recovery | 2 histories |
| Complete original ledger | 27,373 reads / 2,745 updates |
| M01 nominal warmup + measurement windows | 2,700 seconds |
| Exact negative rejections | 439 per location; 878 total |
| Workflow elapsed time | 8,574 seconds (2 h 22 m 54 s) |
| Sum of job execution durations | 21,565 seconds (359.42 runner-minutes) |

The cumulative duration is execution accounting, not a billing amount. All offered
outcomes remain in the evidence. PASS is not a claim that every call succeeded,
a failover SLA or a speedup guarantee. Complete histories are never assembled
from successful fragments of failed attempts.

The aggregate sets `qualifiedMeasurement=true` and `hostedAcceptance=true`.
`localMachineAcceptance`, `protectedFullCI` and `cloudAcceptance` remain false.
The earlier local freezes and first hosted run `38875654052` remain failed. Its
last M01-r2 replay eventually passed, but the final aggregate correctly rejected
its incomplete/failed shard set. The [four repaired causes](PHASE_6_MEASUREMENT_REPAIRS.md)
were qualified by the new complete run, not by relabelling the old evidence.

## Independent review and retention

The local review fetched all 14 jobs, all 21 artifact records, six verified
receipts, the aggregate and its build/plan inputs. It reconstructed the exact
committed checkout identity and compared 65 imported checker modules with the
immutable source before recomputing the aggregate. The result exactly matches
the downloaded aggregate. This receipt review did not rerun the workload or the
physical replay already performed by the six hosted verification jobs.

The checked hashes are recorded in the JSON alongside the exact run and attempt.
The aggregate file SHA-256 is
`8a0939a02e6b8cb726beebc3468d2e13df0242e0e01a216ca6c6c4eb24aa383e`.
The shared build manifest SHA-256 is
`8f1b6d3c0442203d9a6a4272b30fc4a969996e192e2e46f000a959425a4e0928`.

All 21 original artifact ZIPs (667,539,197 bytes) were archived to the operator's
D-drive repository archive before their 14-day GitHub expiry. Every ZIP matches
GitHub's artifact SHA-256 and passes CRC validation. The archive manifest SHA-256
is `45283988078730b67f947b8b23a084a06c3716dcbc7a9670a6eaa169618f0e8f`.
Small API/receipt/review files remain under
`target/v52-hosted-review/run-38888573888/`; the D-drive location is recorded in
its `D_ARCHIVE.json`. Failed original runs are retained separately.

## Integration and next boundary

The measurement corrections are now collected with the previously developed
[cloud suite](PHASE_6_CLOUD_SUITE.md), [receiver bootstrap](PHASE_6_REMOTE_BOOTSTRAP.md),
[public pipe bridge](PHASE_6_REMOTE_RUNTIME.md), [durable commands](PHASE_6_REMOTE_COMMANDS.md)
and [owned-history probe](PHASE_6_REMOTE_OWNED_HISTORY.md).
These additions do not inherit the measured source identity above. New local
receipts bind the actual integrated checkout and freshly compiled helpers.

The temporary worktrees were absent. Recovery used immutable commit `4056aa4`,
its retained uncommitted source ZIP/patch and the previous reviewed hash inventory.
2,345 of 2,346 recovered source files match that inventory. The common Python
runtime was reconstructed from its two parents and the current shutdown fix;
it requires fresh integration validation, not a claim of byte-identical recovery.
Existing main-worktree changes and the original source review were preserved.

Next complete whole-history M01–M04 remote execution, cross-host identities,
owned process/fault/collection cleanup and their no-GCP qualification. Then obtain
exact-source protected full CI and fresh provider admission before the operator
starts the five-member paid suite. The five members may start in any order, while
one accepted cloud set must still share its source, sequence, build and package.
No V5.1 cross-source exception carries into this stage.
