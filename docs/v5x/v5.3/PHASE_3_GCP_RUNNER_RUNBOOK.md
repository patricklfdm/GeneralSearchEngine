# Dedicated GCP runner: prepared, not provisioned

The operator selected the GCP self-hosted option on 2026-11-15. No VM, disk,
firewall, registration token, runner service or large original was created by
this preparation. Pricing and capacity rationale are in the
[comparison](PHASE_3_LARGE_RUNNER_PREPARATION.md). GCP is cheaper in that fixed
compute/disk comparison; transfer charges and runtime can change the total.

## Review before creation

Use one on-demand `e2-standard-8` VM (8 vCPU / 32 GiB), Ubuntu 24.04 x86-64,
32 GiB boot disk and 1,024 GiB `pd-balanced` workspace. Proposed region is
`us-central1`, consistent with the estimate. The existing experimental project's
`us-west4` subnet cannot be attached in this region. Before authorization, select
an existing approved regional subnet or review a new dedicated subnet; do not
silently alter the V5.2 network. Zone/quota, image identity, network access and
the final price remain deployment prerequisites. The
[November 16 prelaunch review](PHASE_3_PRELAUNCH_REVIEW.md) now resolves the
catalogue and identifies two corrections: SSD quota is only 500 GiB (1056 GiB
needed), and default networking has unrestricted inbound SSH/RDP. Request 2048
GiB SSD quota and use the dedicated network below; neither change was applied.

No application service account, WIF credential or production secret belongs on
this runner. It executes local multi-process qualification and uploads evidence
to GitHub. Use a dedicated runner user and data volume, with no unrelated builds.
The label is a routing selector, not an authorization boundary: review the public
repository's self-hosted workflow access before bringing it online, and remove
the runner registration when this campaign finishes. Do not give arbitrary PR
jobs this host.

The following are **future deployment templates, not executed commands**. Do
not execute before the operator says to start, the SSD quota is sufficient and
fresh read-only checks confirm all proposed names are unused. If any name is
already present, inspect its ID/ownership rather than reusing or deleting it.
Existing networks and firewall rules are not edited.

```bash
export V53_PROJECT=gse-benchmark
export V53_SUBNET=gse-v53-large-us-central1
export V53_IMAGE=ubuntu-2404-noble-amd64-v20261105

# Recheck image numeric ID 1892012953239034119 and READY/X86_64 before creation.
gcloud compute images describe "$V53_IMAGE" --project=ubuntu-os-cloud \
  --format='json(name,id,status,architecture,deprecated)'

# Future isolated network: no shared application ports or public SSH/RDP.
gcloud compute networks create gse-v53-large-net \
  --project="$V53_PROJECT" --subnet-mode=custom
gcloud compute networks subnets create "$V53_SUBNET" \
  --project="$V53_PROJECT" --network=gse-v53-large-net \
  --region=us-central1 --range=10.253.0.0/24
gcloud compute firewall-rules create gse-v53-large-iap \
  --project="$V53_PROJECT" --network=gse-v53-large-net \
  --direction=INGRESS --action=ALLOW --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 --target-tags=gse-v53-large-evidence
```

Keep the exact image name/ID in the deployment receipt. If its observation
changes, refresh and review the plan; do not silently select a moving family.

```bash
: "${V53_PROJECT:?review project}"
: "${V53_SUBNET:?review us-central1 subnet}"
: "${V53_IMAGE:?pin exact Ubuntu 24.04 amd64 image}"
gcloud compute instances create gse-v53-large-runner \
  --project="$V53_PROJECT" --zone=us-central1-a \
  --machine-type=e2-standard-8 --provisioning-model=STANDARD \
  --subnet="$V53_SUBNET" --network-tier=PREMIUM \
  --image-project=ubuntu-os-cloud --image="$V53_IMAGE" \
  --boot-disk-size=32GB --boot-disk-type=pd-balanced \
  --create-disk=name=gse-v53-large-work,type=pd-balanced,size=1024GB,device-name=v53-work,auto-delete=no \
  --no-service-account --no-scopes \
  --tags=gse-v53-large-evidence \
  --metadata=block-project-ssh-keys=TRUE \
  --labels=purpose=v53-large-evidence
```

The template uses an ephemeral external IPv4 for outbound Actions traffic;
ingress must use the reviewed SSH/IAP route, with no public replication ports.
No firewall change is implicit here. See the official
[create flags](https://docs.cloud.google.com/sdk/gcloud/reference/compute/instances/create)
and [disk procedure](https://docs.cloud.google.com/compute/docs/disks/add-persistent-disk).

## Configure the actual workspace

Inspect the attached disk by device ID and cloud disk ID before formatting.
Format only the newly created empty workspace disk as ext4, mount it at
`/srv/gse-v53`, and persist its filesystem UUID in `fstab`. Existing partitions,
filesystems or evidence require investigation; never blindly run `mkfs` on a
reused device. Put the runner installation, `_work` (including `_temp` and
`_tool`), Maven cache and retained archives on this volume. The boot disk is not
the evidence workspace.

Install the runner using GitHub's current repository **Settings → Actions →
Runners → New self-hosted runner → Linux x64** instructions, checking the supplied
download hash. Use a short-lived registration token on the VM; do not commit it
or place it in this plan. Configure `--name gse-v53-large-runner`,
`--labels gse-v53-large-evidence`, and an absolute work directory under
`/srv/gse-v53`. Keep the runner offline until registration/source review is
complete. [Runner installation](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners).

The repository setup action supplies pinned Temurin and Python; use its exact
tool versions and checksum-pinned Maven wrapper. Validate that the service user
can write the workspace/tool cache and establish local TCP sockets. No changes
to the existing local WSL/V5.2 runner are required.

The dedicated user's home must also be on `/srv/gse-v53`, so default Maven and
other caches cannot fill the 32 GiB boot disk. Set
`AGENT_TOOLSDIRECTORY=/srv/gse-v53/runner/_work/_tool` in the runner's own `.env`
before starting its service, and make that path owned by the service user.
This is supported by [setup-python on Ubuntu self-hosted runners](https://github.com/actions/setup-python/blob/main/docs/advanced-usage.md#ubuntu).
Keep `_work/_temp` on the same filesystem, and confirm the service user's
effective environment rather than only an interactive shell. Install native
runner prerequisites (`git`, `curl`, `tar`, `gzip`, `unzip`, CA certificates and
the runner's published Linux dependencies) before starting the service.
Registration and runner tokens belong only on that dedicated host, never in
retained evidence. Do not install GCP application credentials on the runner.

From the reviewed checkout on that machine:

```bash
export V53_WORKSPACE=/srv/gse-v53/runner/_work/GeneralSearchEngine/GeneralSearchEngine
findmnt -T "$V53_WORKSPACE"
df -h "$V53_WORKSPACE"
python3.11 -B -m scripts.v53.large_runner_readiness --workspace "$V53_WORKSPACE"
```

The probe checks all five existing gates, reports every blocker and exits 2 if
any is blocked. It neither builds nor starts a workload. An empty-host PASS is
only preparation: each workflow checks capacity again after its actual inputs
arrive. Final replay needs 448 GiB free **after** inputs, so retain failed runs
off-host or expand storage if needed; never delete originals just to pass.

## Manual workflow registration, separately reviewed

Remote master was read again on 2026-11-16 UTC:
`1216bc9e87fd6cc0ce96c44903864a882950035e`. Four manual workflows still require
default-branch registration: queue-resources, maximum-transition,
maximum-native-resources and maximum-queue.

A refreshed local review package is at `target/v53-prelaunch-20261116/registration/`:
`master-registration.patch`, `stubs/`, `manifest.json`, `PR.md` and `COMMANDS.md`.
The previous package is retained unchanged. Its four
default-branch stubs deliberately fail with an explanation if run from master.
They contain no checkout, cloud action or self-hosted job. Their purpose is
registration only; dispatch against the reviewed V5.3 branch uses that branch's
complete workflow, source guards and independent readers. The manifest hashes
both the stubs and actual development workflow bytes. No patch was applied to
master and no registration PR was created.

Before applying in a separately reviewed default-branch checkout, confirm that
these paths are still absent, check the patch with `git apply --check`, and
inspect the resulting diff. After merging registration, verify dispatchability
through the API without dispatching. Do not merge all unfinished V5.3 code merely
to register the four entries. Regenerate the execution plan from the final clean
development source; never treat this preparation's baseline SHA as new evidence.

## Execution and retirement, still pending

The two ordinary failed families now pass their targeted reruns. Register and
execute the ordinary queue family before the large originals. Only after
explicit permission to spend and run, bring the dedicated runner online and use the final planner's
exact commands. The three large workflows retain their shared serialized queue;
continuous histories and reservations stay intact. The ordinary queue-resources
workflow does not need this VM, but its registration is still separate work.

Record VM/disk IDs, source/ref, run/attempt, start/stop times, input/output sizes
and egress estimates. Retain raw failures and replay results. Verify downloaded
archives and hashes before de-registering the runner and deleting the VM/disk.
`auto-delete=no` preserves the data disk on VM deletion; it continues to incur
charges until deliberately removed. Stopping compute alone is not final cleanup.

Retirement order: stop accepting runner jobs after the active workflow finishes;
download and verify original/replay inventories off-host; remove runner registration;
verify the recorded VM/disk IDs still match; delete only that VM, its retained
work disk and this campaign's isolated firewall/subnet/network. Check the resource
API again for absence. Keep cleanup observations and cost/egress notes with the
run record. If evidence transfer is incomplete, preserve the disk and record its
ongoing cost rather than deleting the only copy. Never use broad project cleanup
or alter the existing V5.2 runner/network during this process.
