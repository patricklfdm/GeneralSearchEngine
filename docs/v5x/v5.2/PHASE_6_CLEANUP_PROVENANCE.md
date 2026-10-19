# V5.2 Phase 6AZ manual cleanup provenance

This stage follows [native reconciliation](PHASE_6_NATIVE_CLEANUP.md), closes its
acquisition-context crash gap, and connects cleanup results to original GitHub
workflow evidence. It does not open the native Runner or deploy cloud identities.

## Acquisition crash recovery

The shared owner validates reservation feasibility, retains the immutable original
provider context, then acquires ACQUIRING by create-only lease CAS, reserves the
ledger and advances to ACTIVE. The wire gate independently requires that retained
context before the initial lease write. No resource can be submitted before
ACTIVE and its reservation. A failure before context leaves no lease or charge;
one after context but before acquisition may leave only harmless immutable metadata.
Different contenders may retain distinct contexts; only one can win the lease CAS.

An abrupt process exit after lease acquisition, reservation or ACTIVE now leaves
enough original information for cold expiry reconciliation. Cleanup never invents
context, resets costs, extends an expired lease or substitutes current resource
names/configuration. The strict OfflineOwner still rejects native adapters and
records. Sharing the lifecycle implementation does not expose a native factory.
Three deterministic tests fail on the original ordering and pass on this ordering.
The existing context-denial regression now checks that no lease, charge, resource
or synthetic cleanup PASS exists when the initial context write is rejected.

## Manual workflow and identity

[v52-manual-cleanup.yml](../../../.github/workflows/v52-manual-cleanup.yml) is a
fixed `workflow_dispatch` entry, with master-only execution and the dedicated
`v52-cloud-manual-cleanup` protected environment. Its job is `V5.2 manual cleanup`.
It uses the existing pinned checkout, Python 3.11, Google auth and artifact actions.
It adds no schedule dependency and changes no Required or main-CI job.

The pre-authentication command validates the actual clean source, tracked provider
configuration, workflow bytes and exact run/attempt before publishing only the
selected provider and service account to Actions outputs. Native cleanup then
owns its credential exchange, original context and provider mutations as before.
Cleanup does not depend on Runner build/image/paid admission. Serial concurrency
does not cancel an active cleanup. There is no added stage deadline; existing
per-exchange, lease/grace, freshness and decoder limits remain hard. The hosting
platform's own job limit still applies.

This workflow is present only in local source. The fixed
`docs/v5x/v5.2/cloud-provider.json`, protected environment and dedicated identities
still need a separate reviewed deployment. This development stage performs no
configuration, IAM, GitHub dispatch, token exchange or actual provider operation.

## Sealed observation

The observation includes configuration, original preflight/observations and final
receipt; a reconciliation additionally includes original context, result and the
redacted exchange journal. Its closed inventory is at most 64 MiB. Each file is
size-bounded and hashed; native sealing checks the source again before writing the
seal. Original failed factories cannot publish an accepted bundle.

Validation checks original source/run/attempt, native domain, exact resource
absence inventory, original numeric IDs, unchanged ledger history/cost and lease
release. Every journal send has one matching response or uncertain terminal record;
counts must match the receipt. The journal contains no credential headers or raw
provider error bodies. WAITING uses the recorded decision instant, so slow final
observations crossing expiry do not retroactively invalidate a correct decision.

The artifact is `v52-cleanup-manual-<run-id>-<attempt>`, retained for 30 days.
Separate diagnostics and a concise summary are always attempted. WAITING may be a
successful workflow execution, but it is not an admissible recent cleanup PASS.
An empty PASS has zero writes and does not prove resource-delete permissions.
`deletionPathExercised` remains distinct from native execution and paid admission.

## Independent recent-cleanup collection

`python3 -m scripts.v52.cloud_recent_cleanup --source <exact-master-sha>
--output <new-directory>` owns a fixed read-only GitHub client. It does not accept
a caller-provided PASS, client, cloud token or configuration in its native entry.
The future Runner must call this collection itself, alongside its other fresh
admission checks; stored receipts alone grant no mutation capability.

The collector fully pages source-filtered manual runs, exact-attempt jobs and
artifacts, retaining failures/cancellations. It chooses the latest run for the
current source, never an older green run. A rerun must qualify its latest original
attempt. It checks the fixed job and five required steps, ordering, source workflow
Git blob, original upload interval, artifact origin and original ZIP digest/size.
Repeated master/run/job/artifact observations reject concurrent changes. Archive
validation rejects duplicates, extra/missing files, links and oversized contents;
it replays the original bundle instead of trusting its headline status.

The cleanup job must have completed within two hours, and collection is valid for
at most 15 minutes. These are observation freshness bounds, not execution time
budgets. The returned `RECENT_CLEANUP_VERIFIED_NOT_ADMITTED` is neither effective
IAM qualification nor paid admission. Schedule remains optional; this collector
deliberately relies on the manual entry. It cannot rerun, cancel, dispatch or access
arbitrary workflow/source paths.

## Validation and next connection

The measurement unit gate retains its existing checks and adds acquisition,
bundle/workflow and original-cleanup-provenance regressions. Native factory tests
mock external source/credential/provider/GitHub I/O. They cover all thirteen
resource IDs, crash boundaries, failed-cost preservation, malformed archives,
complete pagination, source/attempt drift, stale observations and rejection of
green WAITING. Original failures and final validation/source hashes remain in
`target/v52-native-admission/validation-summary.json`.

Final local validation passed all 893 V5.2 Python tests in 431.293 seconds and
171 related CI/V5.1 contracts in 87.949 seconds. All 137 focused control/provider/
wire/new-boundary tests also pass, including the 36 new cases. Static checks cover
200 local links, the exact workflow and four shell steps, syntax, preserved gate
commands and unchanged main CI/Java/POM/frozen plans. The initial full-suite failure
at the old context-denial expectation remains retained alongside its strengthened
regression and corrected-source result.

Next connect actual CI/build/package inspection, this recent cleanup, fresh
provider/control observations and exact prepared approval in one owned native
Runner. Then finish strict IAP/guest binding, immutable member retention and
independent complete five-member qualification, with protected operator workflows.
All five members may still start in any order; a whole history retains one
source/lease and cannot be assembled from retries. The frozen measurement calls,
rates, windows and resource bounds are unchanged. No new engine measurement or
paid execution is claimed by this stage.
