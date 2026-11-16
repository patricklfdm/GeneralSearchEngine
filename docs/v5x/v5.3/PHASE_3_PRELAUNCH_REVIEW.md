# Phase 3 prelaunch preparation, 2026-11-16

Status: **preparation completed locally; deployment and large execution NOT
authorized or started**. Development baseline is
`571c3d69a995d6802a10e0af8528e0a4ea3945f2`. Preparation changes require a new
clean-source plan before execution. No production Java, workflow, POM, timing
limit, resource limit or evidence decision is changed by this preparation.
The compact [review receipt](phase3-evidence/prelaunch-20261116.json) retains
the observation identities and outstanding external prerequisites.

## Ordinary results and registration

Node renames run `43803439569` and learner histories run `43823342145` both
completed all their exact-attempt jobs successfully. Latest family progress is
14 successful and four unexecuted, across seven successful source commits.
These mixed sources cannot satisfy final same-source qualification.

The four unexecuted families are ordinary queue resources (six hosted jobs)
and three large workflows (three jobs each). The ordinary queue family remains
unexecuted because its manual entry is not registered, not because it needs
large hardware. Its existing hosted/unit/source-contract checks pass locally;
those checks do not substitute for original hosted execution.

Fresh read-only GitHub observation found master still at
`1216bc9e87fd6cc0ce96c44903864a882950035e`. Its complete recursive tree has
2,876 entries and none of the four manual workflow paths. The workflow registry
has 35 entries, 14 V5.3 entries; the only registered self-hosted runner is the
offline V5.2 WSL runner. No new runner was registered.

`target/v53-prelaunch-20261116/registration/` contains a reviewed four-file
patch, manifest, PR body and operator commands. These add **registration-only**
manual stubs on a separate branch based on master. Each stub exits 1 with an
instruction to select the frozen V5.3 ref. There is no checkout, secret, cloud
action or self-hosted job in those stubs. Dispatch on the V5.3 ref uses its full
existing implementation. The patch was checked and applied in a temporary
directory, with its output compared to all four manifests; it was not applied
to master. No PR was opened or merged by this preparation.

After registration is merged, verify all four API entries are active, verify
the remote source equals the clean-source plan, then execute **only** ordinary
queue resources. Large dispatch still awaits the operator's explicit start.
When eventually merging V5.3 into master, resolve the four add/add conflicts
using the full reviewed V5.3 workflows, not the registration stubs.

## Real GCP observations and corrected deployment prerequisites

All observations were read-only in `gse-benchmark`; no resources, quota, IAM,
network or repository settings were changed. Raw JSON, SHA-256 inventory,
read-only recollection commands and offline analysis are retained under
`target/v53-prelaunch-20261116/`. Current observations are not future guarantees.

| Proposed allocation | Available at observation | Result |
| --- | ---: | --- |
| `e2-standard-8`, `us-central1-a` | Catalogue: 8 vCPU, 32768 MiB | Correct shape |
| Regional E2 CPU, need 8 | 24 | Sufficient quota |
| Project all-region CPU, need 8 | 32 | Sufficient quota |
| SSD persistent disks, need 32 + 1024 = 1056 GiB | 500 GiB | **BLOCKED** |
| External address / VM instance, need one each | 8 / 24 | Sufficient quota |
| New VPC / firewall rule, need one each | 4 / 96 | Sufficient quota |

`pd-balanced` consumes **SSD_TOTAL_GB**, not the 4096 GiB standard-disk quota.
Both boot and work disk count. Request **2048 GiB** for Compute Engine API →
Persistent disk SSD (GB) → `us-central1` in the
[quota console](https://console.cloud.google.com/iam-admin/quotas?project=gse-benchmark).
The immediate deployment requires at least 1056 GiB unused. A quota increase
is a limit adjustment, not disk creation or a reservation; actual allocation
and billing begin separately. Do not shrink the work disk to pass this gate.
The [provider quota contract](https://docs.cloud.google.com/compute/resource-usage)
also makes clear that available quota does not guarantee zonal capacity.

The exact image observed READY/X86_64, without deprecation, is
`ubuntu-os-cloud/ubuntu-2404-noble-amd64-v20261105`, numeric ID
`1892012953239034119`. Recheck that name and ID immediately before creation;
never silently switch a prepared image to a moving family. This preparation
does not modify the separate V5.1/V5.2 image-deprecation admission policy.

Only the auto-mode `default` network currently exists. Its central subnet is
`10.128.0.0/20`; its active `default-allow-ssh` and `default-allow-rdp` rules allow
`0.0.0.0/0`. Therefore the deployment proposal uses a **new isolated custom VPC**,
`gse-v53-large-net`, subnet `gse-v53-large-us-central1` (`10.253.0.0/24`), and a
tagged IAP-only `tcp:22` rule. Existing default/V5.2 networking is untouched.
The [IAP source range](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding)
is `35.235.240.0/20`. An external IPv4 supplies outbound GitHub/artifact access;
it does not require public inbound SSH or replication ports. Effective IAM,
organization/network policy, IAP connectivity and actual outbound connectivity
remain launch-time checks; catalogue GET permission does not prove create access.

The new [offline checker](../../../scripts/v53/large_host_preflight.py) reads
the four retained catalogue/quota files and returns 2 on blockers. It accounts
for used quota, both disks, E2/global CPU and exact image location/identity.
Even a PASS has `deploymentReady=false`, `authorizationRequired=true` and
`phase3Complete=false`: it cannot create a VM or dispatch a workflow.

```bash
python3.11 -B -m scripts.v53.large_host_preflight \
  --inventory target/v53-prelaunch-20261116
```

## Prepared execution and evidence lifecycle

The [runbook](PHASE_3_GCP_RUNNER_RUNBOOK.md) covers creation, isolated networking,
runner installation, disk placement, capacity, source freeze and retirement.
It stays unapplied until explicit startup authorization. The current plan remains
8 vCPU / 32 GiB / 1024 GiB pd-balanced workspace / 32 GiB boot. Earlier prices
are dated estimates; refresh the estimate before paid creation, including egress.

Bring the runner online only after validating its real mounted workspace,
available memory, pinned tools and outbound artifact access. Keep service-user
home, Maven, tool cache, runner work/temp and originals on the data volume.
Each large workflow retains the shared serialized queue and whole-history
boundary. Submit one large family at a time initially and inspect its original
and downloaded replay before the next; do not consume disk with three pending
copies blindly. Existing 1380-minute job timeouts and native deadlines remain.

For every run retain source, run/attempt, original seed/raw artifacts, digests,
replay receipts, failure diagnostics and VM/disk IDs. Before reclaiming a local
copy, verify an off-host copy's complete inventory and hashes. Never delete the
only failed original. Capacity is checked again at each stage; final v4 replay
requires **448 GiB free after all selected inputs are present**. One TiB initial
capacity is not a promise that all originals plus replay outputs fit together.

The final cohort must still bind all 18 families to one source/build/toolchain/
dependency set, observe complete exact attempts, independently replay originals,
then reconcile coverage, combined-resource maxima and historical failures.
Fourteen historical green families are not that final acceptance.

## Actual validation

38 lightweight tests passed: offline cloud checks, large-host capacity probe,
all actual workflow contracts/execution planner and ordinary queue hosted
adapter tests. The frozen-source offline plan inspected 18 workflows / 565 jobs.
Its generation did not invoke Maven, dispatch Actions or execute a native history.
Real cloud inventory correctly produces BLOCKED on the SSD quota. Documentation
contract, registration patch/stubs and whitespace are checked separately.

Not performed: quota adjustment, master registration merge, ordinary queue
originals, VM/network/disk creation, runner installation, large originals,
downloaded large replay or final-source cohort acceptance. The first two are
external prerequisites; hardware checks wait for the authorized host. Nothing
in a preparation PASS removes the explicit operator-start boundary.
