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
the final price remain deployment prerequisites.

No application service account, WIF credential or production secret belongs on
this runner. It executes local multi-process qualification and uploads evidence
to GitHub. Use a dedicated runner user and data volume, with no unrelated builds.
The label is a routing selector, not an authorization boundary: review the public
repository's self-hosted workflow access before bringing it online, and remove
the runner registration when this campaign finishes. Do not give arbitrary PR
jobs this host.

The following is a **future paid deployment template, not an executed command**.
All three variables must be supplied from the reviewed deployment inventory;
`V53_IMAGE` is an exact Ubuntu image name, not a moving family. Resolve the
current family in `ubuntu-os-cloud` during deployment and retain its numeric ID.

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

A local review package is at `target/v53-large-runner-preparation-20261116/`:
`master-registration.patch`, `registration/` and `manifest.json`. Its four
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

Resolve the ordinary failed families first. Only after explicit permission to
spend and run, bring the dedicated runner online and use the final planner's
exact commands. The three large workflows retain their shared serialized queue;
continuous histories and reservations stay intact. The ordinary queue-resources
workflow does not need this VM, but its registration is still separate work.

Record VM/disk IDs, source/ref, run/attempt, start/stop times, input/output sizes
and egress estimates. Retain raw failures and replay results. Verify downloaded
archives and hashes before de-registering the runner and deleting the VM/disk.
`auto-delete=no` preserves the data disk on VM deletion; it continues to incur
charges until deliberately removed. Stopping compute alone is not final cleanup.
