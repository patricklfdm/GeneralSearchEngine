# Phase 3 large-runner preparation and cost comparison

Prepared 2026-11-15 against `659377b3ea89245fb939d124a0783f5b840492b1`.
Status: **GCP option selected; no host provisioned, no large workflow dispatched**.
The concrete [deployment runbook](PHASE_3_GCP_RUNNER_RUNBOOK.md) retains the
reviewed profile, installation steps and unapplied registration package.
The [acceptance inventory](PHASE_3_ACCEPTANCE_STATUS.md) records the remaining
ordinary failures separately from the hardware-dependent work.

## Recommended arrangement

Use ordinary GitHub-hosted runners for the existing fifteen ordinary workflows.
For the three large workflows, use one dedicated native Linux x86-64 VM as a
self-hosted Actions runner with label `gse-v53-large-evidence`. A GCP VM is the
preferred starting option for this repository: the existing workflows already
select that self-hosted label, and the operator already uses GCP. AWS EC2 is
also technically suitable. Neither requires a protocol/runtime change.

A Linux VM qualifies as native Linux for the current checks; bare metal is not
required. WSL is rejected by kernel identity. Running these “no GCP” workloads
on a GCP-hosted runner does not turn them into paid multi-node cloud acceptance:
the provider supplies the CI machine; the history, ownership and evidence
contracts remain the existing local/process qualification.

Start with **8 vCPU, 32 GiB RAM, 1,024 GiB SSD workspace plus a separate 32 GiB
boot disk**. Four vCPU/16 GiB is a lower-cost candidate, not a measured
performance equivalent. Eight GiB installed memory is insufficient as a
selection rule: admission requires eight GiB *available*. One TiB is a proposed
initial capacity, not a guarantee after accumulating all large inputs and
failed attempts. Expand or archive verified copies before a stage if its free
space check fails; never discard failed originals to obtain a pass.

## Existing admission and scheduling contracts

| Stage | Required free disk at the actual stage |
| --- | ---: |
| Direct maximum capture | 272 GiB |
| Direct maximum replay | 144 GiB |
| Maximum-native / maximum-queue hosted execution | 280 GiB |
| Before downloading their replay inputs | 416 GiB |
| Their replay | 288 GiB |
| Complete attested replay, after inputs are present | 448 GiB |

All large checks require native Linux and at least 8 GiB available memory.
These are free-space gates, not disk sizes or measured peaks. They come from
[direct capacity](../../../scripts/v53/maximum_transition_capacity.py),
[hosted capacity](../../../scripts/v53/maximum_native_capacity.py) and
[attested capacity](../../../scripts/v53/maximum_resource_attested.py).

| Pending workflow | Runner work | Preparation needed |
| --- | --- | --- |
| `v53-queue-resources.yml` | Six ordinary hosted jobs; two whole originals | Manual registration; no large host |
| `v53-maximum-transition.yml` | Hosted prepare, large execute/replay | Registration and native host |
| `v53-maximum-native-resources.yml` | Hosted prepare, large execute/replay | Registration and native host |
| `v53-maximum-queue.yml` | Hosted prepare, large execute/replay | Registration and native host |

All four currently have only `workflow_dispatch`; the current remote registry
does not contain them. Their definitions must be registered on the default
branch before manual dispatch. Prepare a narrowly reviewed registration change
with the actual source-contract readers; do not assume publishing a branch
satisfies that prerequisite. This task does not make that change.

The large three share `v53-maximum-transition-large-runner`, `queue: max` and
`cancel-in-progress: false`. Execute/replay jobs currently have an explicit
**1,380-minute (23-hour) workflow timeout**. Nothing in this preparation changes
that timeout or the native operation deadlines. GitHub permits up to five days
per self-hosted job, but this workflow's shorter timeout still applies.
Continuous history, source, reservation/lease, process lifetime and negative
qualification cannot be split into independent jobs to evade a deadline.
See [Actions limits](https://docs.github.com/en/actions/reference/limits).

## Preparation checklist and commands

Before spending money:

1. Decide region, architecture and machine/disk size; verify quota, availability
   and the final provider estimate. Use on-demand capacity for the uninterrupted
   original. Spot/preemptible termination can invalidate a whole history.
2. Resolve the two ordinary failed families; freeze the intended source after
   corrections. Regenerate the execution plan from a clean checkout. The
   current local plan is a snapshot, not a future source authorization.
3. Register the four manual workflows separately. Do not broaden their triggers
   or remove Required checks to make them visible.
4. After provisioning is explicitly authorized, register a dedicated runner
   using the required labels and put its entire work/tool/temp directories on
   the large volume. Do not reuse the V5.2 runner or route unrelated PR jobs to
   it. These jobs require repository/artifact access, not production cloud
   credentials. Use the manual, reviewed source.
5. Confirm outbound access to GitHub/artifacts and pinned tool downloads, local
   socket support, filesystem permissions and disk health. Use a local Linux
   filesystem, not a Windows-mounted directory or a network share.
6. The existing setup action selects Temurin `21.0.12+8.0.LTS`, Python 3.11 and
   the checksum-pinned Maven wrapper. Preserve toolchain receipts; changing VM
   shape does not authorize changing these versions.

On the selected host, from the exact repository checkout, the following only
inspect an **existing** workspace. Set `V53_WORKSPACE` to the real mounted
runner workspace, not an unrelated large mount:

```bash
export V53_WORKSPACE=/path/to/the/actual/runner/workspace
uname -sr
findmnt -T "$V53_WORKSPACE"
df -h "$V53_WORKSPACE"
awk '/MemAvailable:/ { print }' /proc/meminfo
python3.11 -B -m scripts.v53.maximum_transition_capacity "$V53_WORKSPACE" --stage execute
python3.11 -B -m scripts.v53.maximum_native_capacity "$V53_WORKSPACE" --stage execute
python3.11 -B -m scripts.v53.maximum_native_capacity "$V53_WORKSPACE" --stage verify-download
python3.11 -B -m scripts.v53.maximum_native_capacity "$V53_WORKSPACE" --stage verify
```

After all actual final replay inputs are present, inspect its stronger gate:

```bash
python3.11 -B -c 'import json,sys; from scripts.v53.maximum_resource_attested import capacity; print(json.dumps(capacity(sys.argv[1]), indent=2))' "$V53_WORKSPACE"
```

The tracked read-only probe combines those checks and retains every blocker:

```bash
python3.11 -B -m scripts.v53.large_runner_readiness --workspace "$V53_WORKSPACE"
```

It returns 2 on a blocked host and performs no build, cleanup, download,
VM creation or dispatch. Passing on an empty volume proves only current hardware
availability; recheck at each stage after the actual inputs exist.

After source and registration are verified, regenerate the existing planner's
`EXECUTION.md` and use its exact dispatch commands only with execution approval.
Keep run ID, attempt and source with each original and downloaded replay.
Retain archives and SHA-256 inventories outside any disposable checkout before
deleting a VM. Disk retention continues to cost money after stopping the VM.

## GitHub-hosted feasibility

Ordinary public-repository runners are suitable for the already defined
ordinary families, but the documented Ubuntu disk allowance is only 14 GB.
They cannot satisfy the large gates. Larger runners offer 600 GB at 16 cores
and 1,200 GB at 32 cores; 600 GB is marginal once inputs and replay copies are
present. Larger runners require a Team/Enterprise Cloud organization, while
this repository currently belongs to a personal account. They also retain the
six-hour hosted-job limit and would require workflow/reader runner-contract
changes. Consequently they are not the recommended maximum-history route.
See [runner specifications](https://docs.github.com/en/actions/reference/runners/larger-runners),
[availability](https://docs.github.com/en/actions/concepts/runners/larger-runners)
and [standard runners](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job).

## Price comparison

USD public list-price examples checked 2026-11-15, Linux x86-64 on demand, no
commitment/Spot/credits/taxes. GCP uses Iowa `us-central1`; AWS uses
N. Virginia `us-east-1`. Region, hardware and disk performance differ: the table
compares a fixed rental duration, **not predicted completion time**.

VM estimates include 1,024 GiB workspace + 32 GiB boot disk, one in-use public
IPv4 and base SSD performance. Monthly disk prices are normalized over 730
hours for this rough comparison; actual proration follows the provider's bill.

| Option | vCPU / RAM | Disk assumption | Approx. USD/hour | 24 accumulated hours |
| --- | --- | --- | ---: | ---: |
| Standard public GitHub Ubuntu | 4 / 16 GB | Documented 14 GB | Free Actions execution | Unsuitable for large gates |
| GitHub larger Linux 16-core | 16 / 64 GB | Included 600 GB; marginal | 2.52 | 60.48 |
| GitHub larger Linux 32-core | 32 / 128 GB | Included 1,200 GB | 4.92 | 118.08 |
| GCP e2-standard-4 self-hosted | 4 / 16 GiB | 1,056 GiB pd-balanced | 0.284 | 6.81 |
| **GCP e2-standard-8 self-hosted** | **8 / 32 GiB** | **1,056 GiB pd-balanced** | **0.418** | **10.02** |
| AWS m6i.xlarge self-hosted | 4 / 16 GiB | 1,056 GiB gp3 | 0.313 | 7.51 |
| AWS m6i.2xlarge self-hosted | 8 / 32 GiB | 1,056 GiB gp3 | 0.505 | 12.11 |

The GitHub 24-hour column represents accumulated billable job time, **not one
24-hour hosted job**. Large-runner rates are $0.042/$0.082 per minute, billable
even for public repositories. Standard public and self-hosted Actions execution
is free; the cloud VM and its storage/network remain payable.
[GitHub rates](https://docs.github.com/en/billing/reference/actions-runner-pricing),
[billing rules](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

Price inputs:

* GCP e2-standard-4/8: $0.13402284/$0.26804568 per hour;
  pd-balanced: $0.10 per provisioned GiB-month. One VM IPv4: $0.005/hour.
  [Compute](https://cloud.google.com/products/compute/pricing/general-purpose),
  [disk](https://cloud.google.com/compute/disks-image-pricing),
  [network/IP](https://cloud.google.com/vpc/network-pricing).
* AWS Linux m6i.xlarge/2xlarge: $0.192/$0.384 per hour; gp3: $0.08 per
  provisioned GB-month, baseline 3,000 IOPS/125 MB/s; IPv4: $0.005/hour.
  [EC2](https://aws.amazon.com/ec2/pricing/on-demand/),
  [EBS](https://aws.amazon.com/ebs/pricing/),
  [IPv4](https://aws.amazon.com/vpc/pricing/).
  Exact regional Linux and gp3 entries were independently read from the official
  price JSON, published 2026-11-14, retained with the local audit. They are not
  inferred from a Windows licensing example.
  [Regional Linux price JSON](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/US%20East%20%28N.%20Virginia%29/Linux/index.json),
  [regional EBS price map](https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ebs.json).
* Calculation: `compute/hour + 1056 × disk/month ÷ 730 + 0.005`.
  At 48 hours, the recommended GCP estimate is $20.05; AWS 8-core is $24.23,
  before network or retained-storage charges.

**Evidence upload can cost more than compute.** Uploads from the VM to GitHub
are internet egress. A GCP Premium Tier North-America example is $0.12/GiB in
the first paid tier: 500 billable GiB is roughly $60, separate from the VM.
Actual destination, monthly free allowance and prior usage affect this.
Do not infer future large-archive sizes from today's 18.48 GiB ordinary archive
inventory. AWS has a shared monthly internet-egress allowance; confirm the
remaining allowance and regional price before deciding it is cheaper overall.
[Google network pricing](https://cloud.google.com/vpc/network-pricing),
[AWS transfer pricing](https://aws.amazon.com/ec2/pricing/on-demand/).

Stopping a VM does not remove attached disks or all allocated IP charges.
The proposed 1,056 GiB disks alone are about $105.60/month on GCP or
$84.48/month on AWS if retained all month. Archive upload, snapshots, larger
disk sizes, extra IOPS/throughput and additional failed attempts are outside
the compute estimates. Do not delete local evidence until retained copies
and their hashes have been verified.

## Validation performed for this preparation

The source planner and paginated metadata reconciliation completed. Checks for
complete/missing/duplicate pages and JSON consistency passed. The existing
lightweight documentation/frozen-byte contract passed, including 3,262 local
links; whitespace and diagnostic Python syntax checks passed. The local capacity
probe returned BLOCKED for WSL in all five stages, as expected. The wrapper is
only a diagnostic aid and has no qualification authority. Native large-host
capacity, VM performance, resource quotas, dispatchability and original/replay
success remain untested. Full CI, Maven and paid resources were not run.

