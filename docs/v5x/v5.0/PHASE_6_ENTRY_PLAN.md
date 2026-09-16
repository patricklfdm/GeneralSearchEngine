# V5.0 Phase 6 performance and cloud entry plan

- **Status:** Accepted through PR #156 and exact-master documentation CI; 6A implementation candidate
- **Branch:** `docs/v5.0-phase6-entry-plan`
- **Starting master:** `836137aba672c010d0c7e3fc07bc194359543d9f`
- **Predecessor:** [Step C, PR #155](https://github.com/patricklfdm/GeneralSearchEngine/pull/155), [exact-master CI 35031124266](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35031124266)
- **Authority:** [Development charter](../DEVELOPMENT_CHARTER.md), [testing and evidence](TESTING_AND_EVIDENCE.md), [public runtime](PUBLIC_ADMISSION_RUNTIME.md)
- **Published control:** `io.github.patricklfdm:general-search-engine:4.4.0`
- **Control SHA-256:** `0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5`

## Accepted entry boundary

Step C merged through protected PR #155. Its PR CI
[35029395429](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35029395429)
and the exact-master run above passed all six jobs: Change scope, Reactor tests,
Compatibility, Release artifacts, Cloud runner (no GCP) and Required. Master logs
confirm Steps A/B/C and Phase 1–5 executed successfully, including all 21 public
runtime cases. The [public-admission acceptance checklist](PUBLIC_ADMISSION_ENTRY_PLAN.md#public-runtime-acceptance)
is complete.

Phase 6 now measures the accepted public 1.1 runtime and establishes independently
validated cloud evidence. The entry plan records the work and its gates. It supplies
no performance result, cloud-readiness receipt or registered baseline.

## Current implementation and remaining work

| Existing surface | What Phase 6 must add |
| --- | --- |
| [Public runtime gate](../../../scripts/verify-v50-public-runtime.sh) and [external consumer](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/PublicRuntimeConsumer.java) | Repeatable workload and measurement schedules over the same public bootstrap/start/activation/mutation/maintenance interfaces |
| [Independent 1.1 inspector](../../../scripts/v50/runtime_format.py) and [runtime harness](../../../scripts/v50/runtime_harness.py) | Offline inspection of retained cloud authority, success-boundary reconciliation and independent topology/set validation |
| [Phase 1 plan](phase1-plan.json) and [availability receipt](cloud-availability.json) | A separately reviewed Phase 6 plan with actual workload, artifact, guest-runtime, resource, evidence-size and cost inputs |
| [Foundation workflow](../../../.github/workflows/v50-replication-foundation.yml) | A separate protected-master workflow for preflight and explicitly selected real execution; the foundation workflow continues to allow only plan/fake |
| [Fake runner](../../../scripts/v50/fake_cloud_lane.py) and [evidence validator](../../../scripts/v50/evidence.py) | A runner that owns real VMs/JVMs, plus fake tests of that runner's provisioning, failure, cancellation and cleanup behavior |

The Phase 1 fake lifecycle and process fixtures are historical infrastructure evidence.
Their `gse-v50-replication-evidence-v1` envelope has bounded small members and does not
validate real performance samples or GCP receipts. Step 6A must freeze a distinct,
versioned runtime-evidence extension or schema with explicit execution provenance,
bounded members and negative fixtures before the real runner writes it. Keep the
old schema/fixtures and their classifications intact. A fake/model receipt cannot
satisfy a real-run gate. Historical internal 1.0 gates remain regression coverage;
the Phase 6 probe must use sealed `gse-replicated (1,1)` and `gse-replication/1.1`.

## Ordered delivery

Each implementation PR starts from its predecessor's merged master with passing
exact-master CI. A source or build-input change invalidates the downstream admission
receipts for that candidate; a failed stage retains evidence and stops progression.

| Step | Concrete deliverables | Exit evidence |
| --- | --- | --- |
| 6A — local performance and evidence | Public-API probe, independently compiled published V4.4 control, bounded local three-JVM smoke, machine-readable `phase6-plan.json`, runtime member/set schema and validators; integrate a bounded gate into Required CI | Exact-source smoke, semantic comparison, measurements and semantic negative fixtures pass; worker/instrumentation assets stay outside production JARs |
| 6B — real runner and preflight | Owned private three-VM lifecycle, exact artifact distribution, fresh admission receipts, watchdogs, GCS/Actions retention and verified cleanup; a proposed separate `v50-replication-evidence.yml` workflow | Fake tests exercise the same orchestration decisions, including partial provisioning, failed startup, unreachable member, interrupted upload, cancellation and failed deletion; local/public/regression and compatibility gates pass |
| 6C — staged cloud evidence | Refresh read-only preflights and present exact source, plan, resources and total cost estimate for the existing explicit paid-run confirmation; execute experiment, then failure-drill, then canonical | Every member and topology set validates independently; cleanup and budget receipts pass after each run; no later topology starts with leftovers |
| 6D — review and registration | Phase 6 baseline, checklist and canonical review; append-only registration of `v5.0.0-replicated-cloud` through a separate protected PR | Raw evidence remains retrievable, all three canonical repetitions pass, registered identities match the accepted source and artifacts |

The current implementation candidate is [6A local performance](PHASE_6_LOCAL_PERFORMANCE.md).
Its review freezes the exact local workload parameters and
evidence limits before timings become comparable. Optimization is evidence-driven:
any production change receives its own correctness/compatibility review and reruns
affected gates before a new exact-source performance set is admitted.
The documentation-only registration records the measured source SHA; it does not
relabel those measurements as having run on the later registration commit.

## Probe and comparison contract

The probe compiles against production core/replication JARs outside the implementation
package. Each topology owns three separate JVMs with captured PIDs, startup/exit
receipts and overlapping lifetimes. Bootstrap, activation, mutation, checkpoint,
backup, catch-up, replacement and close use public APIs. Fault coordination may use
the existing internal test barriers; it cannot substitute a private initializer or
private application operation. Followers expose public status/diagnostics only;
application equality comes from independent inspection of quiescent retained bytes.

The exact published V4.4 control runs separately, reports its loaded code source and
checksum, and uses the same seeded documents, codec, index definitions, query mix,
operation schedule and application configuration where shared. Run that control
sequentially on the leader-class host with the replica workload stopped. Account
for its runtime and storage in the topology budget. Preserve source backup bytes
and isolate every control/candidate authority directory.

| Cell | Required measurement and correctness evidence |
| --- | --- |
| Published V4.4 control | Single-node durable mutation/query results and latency; independently verifies exported V4 backups and ordered application state |
| Healthy three voters | Single and atomic bulk mutations, index drop/create and committed leader reads; successful Future follows entry quorum, proof quorum and publication |
| One follower unavailable or slow | Accepted/completed/rejected rates, client/peer queue occupancy, lag and retries; the remaining quorum continues only within configured bounds |
| No write quorum | Classified write rejection and committed leader-read behavior; failed or indeterminate Futures never count as durable successes |
| Catch-up and transfer | Time, bytes and lag for incremental recovery and verified snapshot installation, including interruption and capacity rejection |
| Restart and fencing | Activation/reconciliation duration, committed-prefix preservation and rejection of a stale incarnation |
| Disk replacement | Follower remains non-voting until admitted; configured-leader reconstruction rejects one survivor and requires both; no election or promotion |
| Maintenance and shutdown | Local checkpoint, writer-ordered backup, cancellation/close and restart; immutable source preservation and completed backup retention |
| Sustained bounds | Heap/RSS, GC, CPU, client/peer queues, force durations, log/proof/snapshot/staging/disk/network bytes; bounded rejection and unchanged valid recovery sources |

Before measurement, 6A freezes corpus size/seed and hash, encoded document/key sizes,
index/query distribution, bulk sizes, mutation mix, client concurrency and offered
rate, warmup, cell order, durations, sampling frequency and maximum operations/bytes.
Give local smoke a reduced named preset. A reduced run cannot stand in for a complete
experiment or canonical set. Every run records resolved replication/application
bounds, JVM flags, JDK/Maven identities, GC/heap, image ID, kernel, filesystem, mount
options, disk type/size and machine/zone identities.

Use monotonic process-local durations for entry force, proof force and end-to-end
Future latency; do not subtract timestamps from different VMs. Record attempted,
admitted, durable-success, rejected, timed-out and indeterminate counts separately,
with operation-specific p50/p95/p99, sample count and measurement window. Report bulk
requests and documents separately. Retain raw bounded samples/histograms and all
topology results; aggregated medians cannot hide a failed member. Quantify measurement
overhead, and keep fault schedules distinct from healthy throughput samples.

There is no pre-existing V5 throughput/p99 target to claim as passed. Correctness and
declared resource ceilings are mandatory; measured differences from the paired V4.4
control must be explained. A target or preset change is reviewed before rerunning a
complete comparable set, rather than adjusting a threshold after seeing results.

## Profiles and resource ceilings

These are inherited planning limits, not fresh quota or price observations.

| Profile | Independent topologies | Measurement budget per topology | Retention |
| --- | ---: | ---: | --- |
| Local smoke | 1, three JVMs on the local host | Fixed bounded reduced schedule frozen in 6A | Local/Actions artifacts |
| Experiment | 1 | Up to 300 seconds total across its declared cells | Actions |
| Failure-drill | 1 | Up to 900 seconds total across its declared cells | Actions |
| Canonical | 3 serial repetitions | 1800 seconds total across declared cells in each repetition | GCS plus Actions summary |

All three voters run concurrently during healthy replication cells; deliberate fault
windows record the lost member and surviving quorum. Canonical repetitions use fresh
isolated topologies. The control is sequential on the same leader VM; no fourth
measurement VM is budgeted. 6A records the allocation of each measurement budget
across cells and reserves time for warmup, control, failure handling and cleanup.

| Resource | Frozen planning ceiling |
| --- | --- |
| CPU | 8 vCPU per voter, 24 total |
| Data disks | 100 GiB `pd-balanced` per voter, 300 GiB total |
| Boot disks | 50 GiB per voter, 150 GiB total |
| Peak provisioned disk | 450 GiB, including retained disks during replacement |
| Topology wall-clock limit | 5400 seconds; stop workload early enough to execute cleanup |
| Complete-run cost | USD 40 across the admitted experiment, failure-drill and canonical sequence, including control and evidence costs |
| Replication network | Private endpoints and explicit three-member firewall scope |

The previous catalog selection was Standard `n2-standard-8` in `us-west4-a`, with
Ubuntu image `ubuntu-2404-noble-amd64-v20260906`, ID `6257327608773510097`.
Recheck the [historical receipt](cloud-availability.json) against current allocation,
image status and quota before use; a catalog listing does not reserve capacity.
The previously observed 32-vCPU/500-GiB project ceilings are not admission receipts.
Changed image/SKU/runtime inputs require a new exact plan; floating image families
cannot silently replace the pinned guest. Increasing the resource, runtime or cost
ceilings requires reviewed documentation first.

Memory and log growth need explicit admission calculations. The runtime retains
snapshot ancestry with a 1,000,000-anchor limit; local checkpoint does not advance
the recovery floor and repeated checkpoint can reject to preserve old sources.
Freeze workload entry counts (including initial load and control entries), payload/receipt
sizes, heap, log retention, snapshot/staging and evidence budgets with headroom.
Keep sustained cells within those limits; capacity-exhaustion cells prove bounded
rejection separately. Never silently reset authority or discard a failed tail to
finish a measurement window. Disk-loss replacement deletes the owned obsolete
resources before allocating replacements if overlap would breach the peak cap.

## Preflight and execution order

1. Bind the complete planned sequence to a clean protected-master SHA, successful
   CI, core/replication/control JAR hashes, plan/schema/preset hashes and exact build
   inputs. Verify local/public and relevant regression evidence for that source.
2. Pass the local production-probe smoke and real-runner fake matrix. Independently
   reject forged success, serial-voter stand-ins, mixed sources/versions, missing
   samples, conflicting commit history and false cleanup even with valid checksums.
3. Record fresh read-only receipts for the exact workflow/ref/environment WIF
   allowlist, service-account permissions, zone/SKU/image, current CPU/disk quota
   usage, private network/firewall and the precise GCS prefix. Preflight credentials
   are least-privilege; secrets and tokens are excluded from evidence.
4. Produce a cost estimate from current prices, planned durations, all five topology
   instances (1 experiment + 1 failure-drill + 3 canonical), control time, disks and
   evidence storage/transfer. Track failed attempts and remaining budget. Record
   expiry/revalidation rules for these receipts and present the existing explicit
   paid-run confirmation for this exact plan under the `cloud-benchmark` environment.
5. Run one experiment. Admission requires valid semantics, measurements, resource
   bounds, upload and cleanup. A failed experiment stops the sequence.
6. Run one failure-drill. Kill an owned leader after proof quorum and before client
   success, then independently prove the committed result survives. Separately
   exercise entry quorum before proof: the incomplete call is indeterminate, and
   recovery must follow valid proofs rather than inventing a committed result.
7. Run all three canonical repetitions serially, preserving three concurrent voter
   lifetimes per healthy cell. A failed repetition fails the set; retain it instead
   of replacing it with a selectively reported successful retry.
8. Validate every member, topology and aggregate set independently, then review and
   register the baseline through 6D. A changed candidate or workload starts a new
   comparable set with renewed preflights.

The intended evidence prefix is
`gs://<evidence-bucket>/v5.0-replicated-single-shard/<source>/<run-attempt>/`.
6B must capture exact resource IDs/ownership before mutation, retain raw evidence on
success and failure, and verify deletion by read-back after stopping owned JVMs.
Budget/deadline/watchdog and cancellation paths invoke the same idempotent cleanup.
Evidence upload failure cannot suppress cleanup; incomplete cleanup blocks subsequent
topologies and records the remaining resource inventory. Retention must separate
durable evidence from disposable staging, and deletion scope must exclude unrelated
resources and accepted evidence. Retrying after failure needs a new attempt ID and
remaining-budget admission, with the failed attempt still visible.

## Acceptance checklist

- [x] Step C protected PR and exact-master CI verified; public-admission gates complete.
- [x] Existing cloud scaffolding, measurement matrix, inherited caps and delivery order documented.
- [x] This entry plan accepted through protected PR #156 and exact-master documentation CI `35039318340`.
- [ ] 6A public probe, pinned control, exact plan and independent evidence validators accepted.
- [ ] 6B real-runner ownership, preflight, fake-failure, retention and cleanup gates accepted.
- [ ] Exact-source preflights and explicit paid-run confirmation recorded.
- [ ] Experiment, failure-drill and all three canonical repetitions pass with cleanup.
- [ ] Independent member/set review and append-only baseline registration accepted.

Phase 7 begins only after the final Phase 6 gate. Phase 6 introduces no election,
public follower reads, dynamic membership, storage-format change or release claim.

## Validation for this documentation PR

Validate the Phase 0 contract, local links/anchors, Markdown fences, whitespace and
the final changed-file list against the existing CI classifier. This Markdown-only
PR follows the lightweight documentation lane: Change scope validates the contract,
and Required verifies the expected skips. Java, process matrices and release builds
remain the accepted Step C results; 6A/6B code changes require their own full gates.

Local validation passed: Phase 0 contract, 14 existing CI-classifier/gate tests,
609 local links across 40 Markdown files (including six anchor references), code
fences and whitespace. All 12 changed paths classify as documentation; the expected
PR/push decision is `run_full_ci=false`. Protected acceptance completed through [PR #156](https://github.com/patricklfdm/GeneralSearchEngine/pull/156)
at `3eb0dc1067b3001c04768190a2844be69c137da3`. Its
[PR CI 35039229374](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35039229374)
and [exact-master CI 35039318340](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35039318340)
passed Change scope and Required; the four full-CI jobs were correctly skipped.
The Phase 0 documentation contract step ran successfully.
