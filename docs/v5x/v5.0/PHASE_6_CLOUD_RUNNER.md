# V5.0 Phase 6B cloud runner and preflight

- **Status:** Runner accepted through PR #158 and exact-master CI; full cloud presets and paid execution pending
- **Branch:** `feat/v5.0-phase6b-cloud-runner`
- **Starting master:** `7754b696fea7e6fb18c79dd632ab055f5f1da546`
- **Predecessor:** [PR #157](https://github.com/patricklfdm/GeneralSearchEngine/pull/157), [exact-master CI 35043760510](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35043760510)
- **Plan:** [phase6-runner-plan.json](phase6-runner-plan.json)
- **Gate:** [verify-v50-phase6-runner.sh](../../../scripts/verify-v50-phase6-runner.sh)
- **Workflow:** [v50-replication-evidence.yml](../../../.github/workflows/v50-replication-evidence.yml)
- **Authority:** [Phase 6 entry plan](PHASE_6_ENTRY_PLAN.md), [6A workload](PHASE_6_LOCAL_PERFORMANCE.md)

## Scope and remaining preset work

This accepted implementation supplies the owned three-VM runner and its admission/cleanup
boundaries. Its only runtime profile is `admission-probe`: the exact reduced 6A
64-document public workload, carried to three private VMs. It cannot select
`experiment`, `failure-drill` or `canonical`, and its evidence cannot register a
baseline. The Phase 1 plan/fake workflow and historical evidence schema remain intact.

The complete cloud workload matrix still needs a reviewed extension before 6C:
slow/unavailable followers, interrupted transfer, restart/fencing, disk replacement,
proof-boundary failure drills and sustained sampling, with explicit cell budgets.
Those operations remain covered by the accepted local public/runtime correctness
gates; this PR does not represent that coverage as cloud performance measurements.
Any optional paid admission probe counts against the same USD 40 sequence budget.
Accepting this runner alone does not close the cloud preset review gate. The
[full cloud workload plan](PHASE_6_CLOUD_WORKLOAD_PLAN.md) was accepted in PR #159.
[Workload/evidence implementation](PHASE_6_CLOUD_WORKLOAD.md) was accepted in PR #160
with exact-master CI `35058372449`. The current candidate is
[runner preset qualification](PHASE_6_RUNNER_PRESETS.md), followed by the remote
workload and cloud evidence adapter.

## Runtime and artifact path

The controller builds both production JARs from the clean source, compiles the
public consumer against those JARs, and compiles the V4.4 control independently
against the pinned published artifact. A Java 21.0.12+8 `jlink` runtime, classes,
JARs, workload and source/build inputs form one checksummed bounded offline bundle.
Private guests need no package download, external IP or service account. The
controller transfers the bundle over IAP/SSH and verifies the same manifest on
every guest. SSH private keys live in a temporary directory outside evidence.

All three fresh 100-GiB data disks first attach to the leader VM. The public
bootstrap writes three sealed `(1,1)` authorities to separate ext4 mounts. After
bootstrap, follower volumes unmount, detach and attach to their respective VMs.
This follows the accepted offline-volume provisioning contract; seals are neither
forged nor rewritten. Each worker uses the public startup/activation/mutation/
maintenance APIs and the three private endpoints. Test instrumentation remains
outside production JARs.

The published control runs on the leader host before the three candidate JVMs
start, and restores the exported backup after they stop. Controller monotonic
timestamps establish overlap and command order. Latency, force and success-boundary
durations stay within each JVM's own clock; cross-host timestamps are never subtracted.
Quiescent retained bytes supply independent application and committed-history checks.

`gse-v50-cloud-probe-v1` adds exact VM IDs, boot IDs, private endpoints, ownership,
guest artifact manifests, remote PID/start ticks and mount receipts. It invokes the
full 6A semantic, sample, force, ancestry and V4-control verifier after checking
cloud provenance. The default local verifier still rejects cloud/fake labels.
`cloud_entry validate` additionally requires the completed real lifecycle, retention
receipt and absent-resource read-backs. A fake lifecycle cannot satisfy these checks.

## Ownership, failure and cleanup

The shared `Runner` drives both the GCP adapter and its fault-injection adapter.
Before creating anything, it obtains a generation-conditional GCS lease containing
the exact immutable resource names, nonce, source and create request IDs. Intent is
saved before each insert and returned IDs are saved before the next step. A name
prefix alone never authorizes deletion.

The inventory contains three `n2-standard-8` instances, three 50-GiB boot disks,
three 100-GiB data disks and four run-scoped firewall rules. Peer traffic on port
9700 is limited to the run's VM tag; SSH is limited to IAP. Higher-priority owned
deny rules prevent the default network's broader rules from opening those ports.
Preflight rejects unreviewed overriding or hierarchical/network firewall policies.

Cleanup stops every started worker, attempts collection from every guest, then
deletes instances, disks and firewalls in reverse dependency order. It continues
after individual errors and reads every attempted resource back. A 403, pending
insert, changed ID or foreign owner is never treated as absence. Deleting a VM also
checks the identities of disks subject to automatic deletion. Unresolved create
results remain blocking until the operation/resource can be reconciled.

Success and failure retain bounded evidence in Actions and an immutable GCS prefix:
`v5.0-replicated-single-shard/<source>/<prepare-run>-<attempt>-<nonce>/`.
Object writes use generation conditions and content read-back. Upload failure does
not prevent deletion. Incomplete retention or deletion holds the lease, so the next
topology cannot start. The expired-lease cleanup command retains its own receipt;
it never deletes accepted evidence or the budget ledger.

The controller stops workload before the 5400-second topology ceiling, reserving
300 seconds for cleanup. Each VM also has a provider-side 5400-second DELETE
watchdog and attached disks use automatic deletion. A controller crash can still
leave a disk between attachment steps or a firewall. A scheduled reconciler checks
expired leases every 15 minutes, after an additional operation grace period. GCP
outages and GitHub scheduling delays can extend cleanup; a failed read-back remains
an explicit failure and blocks new topology admission. This is not a guarantee of
instant deletion during a provider outage.

The scheduled job is **disabled by default**. Before paid admission, the repository
variable `GSE_V50_EXPIRED_CLEANUP_ENABLED` must be `true`, and the new workflow must
be admitted by the protected WIF condition. Enabling this variable is a later cloud
setup action; this implementation does not change it or IAM.

## Read-only preflight and paid review

Preflight checks exact-master full CI (including the 6B gate), workflow service
account, WIF repository/ID/ref/environment/workflow conditions, pinned image ID,
machine/zone, current quota headroom, effective firewall policies, permissions,
uniform-access evidence bucket, remaining budget and an actually executed successful
scheduled cleanup for the exact source within the last two hours. Reading Actions
run/step receipts uses the workflow's existing read permission; it does not require
a token with Variables API access. Its closed
CEL parser rejects unsupported expressions and tests all literal alternatives to
detect an `OR` branch that bypasses repository/ref/environment guards.

Receipts expire after 900 seconds. Quota observations do not reserve allocation.
The runner refreshes read-only checks immediately before mutation and rechecks the
original admission expiry. A blocked or stale receipt cannot be relabelled READY.

Preparation emits a request digest, bundle digest and preflight digest. A separate
manual `run` dispatch requires the reviewed request SHA-256 and a
`gse-v50-paid-admission-v1` document containing:

- `confirmed: true`, exact `requestSha256`, `preflightSha256`, `planSha256` and `expiresAt`;
- integer `maximumCostMicrousd` and `previousAttemptsCostMicrousd`, whose sum is at most 40,000,000;
- current `priceSources` and `estimateIncludes` exactly
  `three-vms, boot-disks, data-disks, control, evidence, cleanup, failed-attempts`;
- `pricedThroughTopologySeconds` at least 5400 and `cleanupOverhangSeconds` at least 1080.

Before resource creation, a generation-conditional, append-only budget ledger
reserves the approved maximum. Failed attempts keep their reservation. A stale
balance, duplicate request or exhausted balance blocks execution. These are
conservative reservations, not a claim about actual billed cost; measured billing
and any reservation adjustment require separate review. A prepared artifact or
successful fake run does not itself authorize paid execution.

### Observed local preflight

The read-only observation on 2026-09-15 found the pinned image and machine available
in the catalog, 32 global vCPU quota and 500-GiB regional SSD quota with no observed
usage, plus the existing private subnet and default network. No allocation was
attempted. The current WIF allowlist lacks `v50-replication-evidence.yml`; the local
observer is not the workflow service account. The predecessor's CI also predates
this new 6B gate, and cleanup enablement remains pending. These are blockers, not a
paid-readiness receipt. The retained local observation is outside the repository;
fresh workflow receipts are required after merge and cloud setup.

## Usage

Unpaid local validation:

```bash
python3.11 -m unittest scripts.v50.test_cloud_runner
scripts/verify-v50-phase6-runner.sh --skip-build
```

The new protected workflow accepts `plan`, `fake`, `preflight`, `prepare`, `run`
and explicit `reconcile`. `plan` and `fake` obtain no cloud credentials.
`preflight` performs read-only cloud/GitHub queries. `prepare` builds and tests an
exact offline bundle and retains `v50-prepared`; it provisions no resources.
`run` downloads that reviewed artifact from `prepared_run`, validates the exact
confirmation/cost receipt and executes one admission probe. `reconcile` requires
the retained request digest and an expired lease. Scheduled cleanup cannot create
resources. Paid execution commands belong to the later exact-cost review.

## Validation and acceptance

- [x] 6A PR #157 and exact-master CI verified; clean source reported sequence 76,
  committed index 73, 80 measured calls, 64 durable writes and 20 rejected semantic negatives.
- [x] Shared runner fault matrix covers partial/lost-ack creation, failed startup,
  unreachable member, interrupted upload, cancellation, deletion failure, forbidden
  reads, unresolved insertion and changed ownership/IDs.
- [x] Final local build, volume-layout runtime, regression and compatibility receipts recorded below.
- [x] Protected runner PR #158 and exact-master CI `35051728286` accepted.
- [x] Full cloud workload plan accepted through PR #159.
- [ ] Workload/evidence and full runner preset implementations accepted before 6C.
- [ ] Fresh service-account preflight, enabled cleanup, exact current-price review and explicit paid confirmation.
- [ ] Real cloud admission/runtime evidence, staged performance cells and baseline registration.

### Final local receipts

| Check | Result |
| --- | --- |
| Reactor release + API/artifact compatibility | PASS with the isolated published-baseline Maven repository; three source/reflection fixture tests, all published API comparisons, 151 replication tests and five processor tests |
| Default core tests | PASS; 549 tests, run separately because `api-compat` selects only its compatibility fixture |
| Release contents | PASS; all nine JARs; production core and replication SHA-256 unchanged from accepted 6A |
| V5 Python suite and final runner tests | PASS; existing 98 tests plus 18 cloud-runner/admission tests, including the final scheduled-cleanup check |
| Public admission A/B/C and Phase 1–5 | PASS; offline crash/replacement/published-V4 round trips, 21 public runtime cases and hardening matrix |
| Final 6A gate | PASS in 13.05 seconds; 20 resealed semantic negatives rejected |
| Final 6B gate | PASS in 27.28 seconds; 11 fake lifecycle scenarios, offline bundle, three real local JVMs using separate volume paths and the bundled JRE |
| Documentation/workflow checks | PASS; Phase 0 contract, 14 classifier tests, YAML/shell syntax, local links/fences and whitespace |

Both final runtime probes report sequence 76, committed index 73, 80 measured
requests, 64 durable measured writes and one no-quorum indeterminate result. The
6B receipt is explicitly `local-volume-layout-and-fake-runner-only`; it is not a
three-VM cloud result. Local source is starting HEAD with `sourceDirty=true` and
the retained final input inventory. The subsequent clean exact-source CI acceptance
is recorded below; it does not relabel the earlier dirty-source local receipts.

The first compatibility invocation correctly rejected a non-published 3.0.0 JAR
in the default Maven cache. The successful comparison used
`-Dmaven.repo.local=/tmp/gse-v50-artifact-compat-repo`. The first offline gate then
identified the missing default-core test report caused by combining `api-compat`
with the reactor build; running the default core tests supplied that report and
the complete offline gate passed. Neither issue required a production change.

## Protected acceptance

[PR #158](https://github.com/patricklfdm/GeneralSearchEngine/pull/158) merged at
`72137865f39535e8f41052b455bbfdd0e01be163`.
[PR CI 35050257631](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35050257631)
and [exact-master CI 35051728286](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35051728286)
passed all six jobs: Change scope, Reactor tests, Compatibility, Release artifacts,
Cloud runner (no GCP) and Required. Master logs confirm public A/B/C, Phase 1–5,
6A and 6B actually executed successfully.

The clean-source runtime receipts report `sourceDirty=false`, application sequence
76, committed index 73, 80 measured requests, 64 durable writes and one no-quorum
indeterminate call. All 20 semantic negatives were rejected. The 6B result is
`v50Phase6B=PASS execution=local-volume-layout-and-fake-runner-only`. This accepts
the runner infrastructure and its local/fake gate; it supplies no real three-VM
cloud performance or paid-readiness receipt. Fresh preflight and cloud setup remain
pending, as do the complete cloud presets described above.

## Provider contracts

The adapter uses documented [VM runtime limits](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime),
[effective network firewalls](https://docs.cloud.google.com/compute/docs/reference/rest/v1/networks/getEffectiveFirewalls),
[deployment-pipeline WIF conditions](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
and [GCS generation preconditions](https://docs.cloud.google.com/storage/docs/request-preconditions).
