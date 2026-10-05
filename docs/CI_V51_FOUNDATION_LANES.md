# V5.1 foundation and owned guest CI partition

**Current topology:** the [Python/cloud partition](CI_PYTHON_LANES.md) supersedes
Python test and cloud-gate ownership below: 32 required job IDs, 36 executed jobs.
Earlier counts and timings in this document describe their historical migrations.


The accepted master [job 109353691714](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36551903980/job/109353691714)
took **25m47s** on 2026-09-29. Its steps are independent after the existing V5.1
verification-build handoff, except for guest package and local SSH setup.

| Required job | Owned steps and retained evidence | Prior step timing |
| --- | --- | ---: |
| `v51-foundation` | Phase 1 foundation, Phase 2 storage, Phase 3 protocol/runtime/rejoin, Phase 6 local performance; six original evidence uploads | About 8 minutes |
| `v51-guest-services` | Package build/relocation, persistent service, OpenSSH, SSH delivery, owned idle, two-fault qualification, isolated bootstrap; original guest/package/fault uploads | About 10 minutes |
| `v51-owned-experiment` | Own package build/relocation and OpenSSH; complete owned experiment, including the original three-mode healthy coordinator | Healthy predecessor: 9m24s; full assembly timing pending |

The complete experiment supersedes the standalone three-mode healthy invocation
in this workflow. Its retained `healthy` subtree contains those same three modes,
270 original calls, physical/history replay and both replicated backup restores.
Leader-loss, maintenance and no-quorum join them under one lease. The prior
`v51-owned-three-mode` artifact is replaced by `v51-owned-experiment`; the local
`--three-mode` entry remains available. The quick two-fault gate remains in the
service lane. See [the C21 contract](v5x/v5.1/PHASE_6_OWNED_EXPERIMENT.md).

Every lane restores by the producer's artifact ID and validates the exact
source/build manifest before execution. None adds a Maven reactor build. The two
guest lanes construct independent guest packages (~15s each in the reference
run); they have separate runner workspaces and no sibling dependency. Original
package evidence stays `v51-guest-package`; the experiment's package evidence is
`v51-experiment-package`. Restore receipts and all artifacts have unique names.

All three lanes retain 60-minute job limits. Script deadlines and frozen workload
budgets remain independent. All uploads use `always()`, retaining partial failure
evidence. Required checks cover all three outcomes, including docs-only skips.
There are now **25 full-CI job IDs**, plus Change scope and Required; the rich
matrix expands this to **29 executed jobs**. Other lanes are unchanged.

These estimates exclude queue delays and cache/runner variation. Full experiment
work increases scope, so the next protected CI must measure the actual critical
path. No throughput threshold, retry, production runtime or paid-cloud change is
part of this CI partition.

## Accepted timing

PR #252 / [master CI 36566870122](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36566870122)
attempt 1 passed all 29 jobs. Foundation/runtime took 8m11s, guest services/faults
9m37s and complete owned experiment 17m02s. The full experiment step took 16m04s.
These are one hosted run's durations, including new maintenance/fault coverage;
queue delay and other lanes still determine overall workflow completion.
