# Python and cloud qualification CI partition

**Accepted:** PR #286, master `b0bc7b4b9e63a40a1d812138d86cb40e7e298e92`,
[exact-master CI 37280773489](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37280773489)
attempt 1, all 36 jobs passed. This establishes correctness of the migrated gates;
the pre-split measurements below are historical, not measured post-split durations.

## Observed bottlenecks

The four latest full successful runs reviewed for this change were
[PR #284](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37258477403),
[master #284](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37261105426),
[PR #285](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37266248728),
and [master #285](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37269773248).
Job durations below exclude time waiting for a runner.

| Job | PR #284 | Master #284 | PR #285 | Master #285 |
| --- | ---: | ---: | ---: | ---: |
| Cloud runner (no GCP) | 24m40s | 22m38s | 27m04s | 26m58s |
| V5.1 foundation and runtime | 22m23s | 24m07s | 26m33s | 14m26s |
| V5.1 owned experiment (no GCP) | 16m06s | 16m00s | 17m26s | 16m47s |
| V5.1 full-size runtime | 17m17s | 14m34s | 12m09s | 11m59s |

The Cloud runner preflight step took 13m51s–17m39s and its provider step
7m32s–8m14s. They do not exchange evidence or share a provider. Foundation's
Phase 1 step took 10m38s–20m26s, dominated by discovery of all V5.1 Python tests.
That suite creates its own temporary fixtures and requires no reactor output.
Other jobs stayed below fifteen minutes in these four runs.

## Required lanes and ownership

| Job ID | Work | Evidence |
| --- | --- | --- |
| `python-v51-core` | All V5.1 Python modules outside the cloud prefix, including guest and protocol tests | `python-v51-core-<sha>` |
| `python-v51-admission` | Cloud Python modules other than the eight storage modules below | `python-v51-admission-<sha>` |
| `python-v51-storage` | `test_cloud_fixture_driver`, `test_cloud_topology_fixture`, `test_cloud_runner_storage`, `test_cloud_runner_storage_entry`, `test_cloud_experiment_resources`, `test_cloud_runner_resources`, `test_cloud_runner_iap`, `test_cloud_runner_guest_setup` | `python-v51-storage-<sha>` |
| `v51-foundation` | Existing Phase 1 executable foundation, Phase 2/3 and local performance gates; restore the exact shared build | Original six evidence artifacts and build receipt |
| `cloud-runner-tests` | Remote command foundation, cloud control, shell checks and all historical V2/V4/V5 runner checks | Original remote foundation and cloud control artifacts |
| `cloud-preflight-tests` | Preflight, recent manual, identity, permission, cleanup deployment/observation and Runner precheck tests; preflight/identity/permission/request-inspection qualification and generated deployment/Runner review | Original `v51-cloud-preflight-<sha>` |
| `cloud-cleanup-fixture-tests` | Cleanup fixture, operator driver and topology tests; single-disk review, single-disk/driver/topology and ordinary experiment resource qualification | `v51-cloud-preflight-cleanup-<sha>` |
| `cloud-storage-tests` | Runner storage, entry, resources, IAP and native guest setup tests; both nine-case storage qualifications and ten-case resource/IAP interruption qualification | `v51-cloud-preflight-storage-<sha>` |
| `cloud-provider-tests` | Original OpenSSH setup, complete provider gate, safe archive packaging and upload | Original `v51-cloud-provider-<sha>` |

`ci_v51_python` partitions every `scripts/v51/test_*.py` module by name. New cloud
modules enter admission; all other new modules enter core. A regression compares
all discovered test IDs against the disjoint union of the three partitions,
rejecting missing or duplicate tests. A failing test, import error or empty suite
fails its job. Each lane retains executed/expected counts and per-test durations,
including timings completed before a failure. Existing focused unit tests inside
other gates remain present; the partition does not remove their checks.

The local `verify-v51-phase1-foundation.sh` still runs the complete Python suite
by default and with `--skip-build`. Only CI uses the explicit
`--skip-build --skip-python-tests` combination, with all three Python jobs
required. The runtime portion still consumes the verified build by artifact ID.
The new Python and cloud jobs start after Change scope, with Python 3.11, no Maven
build/download, no OIDC permission and no cloud Environment.

`verify-v51-phase6-cloud-preflight.sh` still runs everything by default.
`--lane admission|cleanup|storage` chooses an independent subset. Across the
three lanes all thirteen original test modules and every original qualification
command, argument, timeout and output subtree remain. Each generate/validate
pair stays in the same job. The jobs have separate workspaces; no qualification
receipt from one is treated as another's input. The later resource and two Runner
request-inspection modules bring the focused union to sixteen modules; request
inspection adds a bounded offline original-artifact/credential/resource/cleanup
qualification in admission, with no new job or Maven dependency. Failure evidence uploads always
run, with unique artifact names and the original fourteen-day retention. The
native resource/IAP candidate adds two focused storage modules (eighteen in the
complete focused union) and one ten-case offline matrix with a 600-second process
cap, retained in `runner-resource-entry`. Existing commands/timeouts and all
Required job IDs remain unchanged; there is no additional Maven build or live
cloud execution. The native guest-preparation candidate adds one storage module
(nineteen in the focused union), including volume/package failures and fresh-process
expiry cleanup. It adds no job or independent build.

Full CI now requires **32 job IDs**, expanding to **36 executed jobs** including
Change scope, Required and the existing three rich-workload matrix children.
Required rejects any failure, cancellation, missing result or unexpected skip.
For verified docs-only changes all 32 must be skipped. The native read-only
preflight derives its exact job inventory from the source-bound CI workflow and
therefore also requires the new jobs. V5.0 Reactor/Phase 6B identifiers and the
owned experiment job/step consumed by admission remain unchanged. No branch
protection adjustment is needed for the existing Required check.

## Work deliberately kept together

The owned experiment is one complete three-mode healthy/fault/maintenance history
under one lease, with shared guest services, ownership and independent backup
validation. Splitting its internal phases into jobs would require a new acceptance
contract and cannot preserve that continuous experiment by moving YAML steps.
It stays intact despite its sixteen-to-seventeen-minute duration.

The 512-slot runtime similarly executes a continuous public history and its
recovery/reclamation boundary. Its latest three runs were below fifteen minutes.
The older seventeen-minute observation does not justify splitting its history or
reducing slots. It stays independent of the existing component/reclamation lane.

The partition adds seven lightweight jobs, not seven reactor builds. Hosted
scheduling, VM speed and upload overhead still affect total workflow time;
fifteen minutes is an optimization target, not a new test timeout or SLA. Original
job and script limits, workload sizes and retry rules remain unchanged. The next
full CI measurements should be used to assess actual per-lane durations separately
from the accepted gate results above.

## Local validation

Retained review data, source comparison, test receipts and logs are in
`target/v51-storage-cli-ci-split/`. The migration is checked against its original
workflow and gate commands, in addition to Required/docs-only tests and exact
Python discovery coverage. The native storage CLI correction is tracked in the
[Runner entry record](v5x/v5.1/PHASE_6_RUNNER_STORAGE_ENTRY.md).

## Ordinary experiment resource addition (accepted PR #288)

The existing cleanup-fixture lane now also runs `test_cloud_experiment_resources`
and the forty-one-case `cloud_experiment_resource_qualification`, retaining its
`experiment-resources` subtree in the original artifact. Its 600-second process
cap bounds offline failure replay; the per-attempt preparation/lease/grace clocks
remain 600/5400/1080 seconds. The same new unit module belongs to Python storage.
At that addition, fourteen focused unit modules formed the exact default/three-lane union;
existing commands and timeouts are unchanged. No workflow job, Required check,
Maven build or paid workflow input is added.
