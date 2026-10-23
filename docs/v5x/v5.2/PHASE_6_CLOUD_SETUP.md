# V5.2 cloud setup review and pre-cloud boundary

Phase 6BK supplies the tracked provider configuration and an offline generator
for the two required identities, their permissions and GitHub environments.
The generated commands have **not** been applied. No live infrastructure fact,
permission, deployed environment or cloud acceptance is established by this file.

## Configuration and its provenance

[cloud-provider.json](cloud-provider.json) is the native entry's fixed source file.
Project `gse-benchmark` / `266952534277`, evidence bucket, `default` network/subnet,
`us-west4-a`, `n2-standard-8` and the exact Ubuntu image name/ID come from the
tracked [V5.1 preflight configuration](../v5.1/phase6-preflight-config.json).
Those are historical configuration facts, not fresh GCP observations. The image
is `ubuntu-2404-noble-amd64-v20260918`, ID `763874002631433611`; a fresh exact GET
must still prove its identity, READY state and X86_64 architecture. DEPRECATED
warns; OBSOLETE/DELETED or a changed ID rejects. Never silently follow a family or
replacement image.

| V5.2 choice | Value | Reason |
| --- | --- | --- |
| Disk type | `pd-ssd` | Matches the existing V5.2 preflight's reviewed SSD quota policy; V5.1's `pd-balanced` would reject |
| Boot / data disk per voter | 50 / 100 GiB | Keep the earlier cloud layout; three voters require 450 GiB total |
| Replication TCP port | 19752 | Separate V5.2 peer port, read by both native firewall and topology builders |
| Renewable lease | 3,600 s | Ownership expires if renewal stops; running work renews it at most every 30 s |
| Operation grace | 300 s | Cleanup waits after expiry; not a workload time limit |
| Cumulative cost budget | 200,000,000 micro-USD ($200) | Soft warning, including failed reservations; no ledger reset |

Private Google Access, RFC 1918 subnet space, actual quota, image readability,
bucket project/UBLA/lifecycle and current control state remain fresh preflight
checks. There are no external VM IPs or attached service accounts. Preparation
requires an explicit dated cost estimate; these settings do not claim current
pricing. The five-member source/configuration/sequence must stay fixed after its
first accepted member. Configuration changes require a new complete cohort.

## Generate and verify the local review bundle

Run from the repository root, using a new directory each time:

```bash
python3.11 -m scripts.v52.cloud_setup generate --output target/v52-cloud-setup/review
python3.11 -m scripts.v52.cloud_setup check --output target/v52-cloud-setup/review
```

The generator reads the actual configuration and native permission/identity
constants. Its 24 files contain a proposal, exact command arguments, role and
condition bodies, environments and `COMMANDS.md`; an additional manifest pins
every byte. `check` independently regenerates this closed inventory and rejects
missing, extra, edited or symlinked files. Neither command invokes `gcloud`, `gh`,
an API, authentication or a subprocess. `REVIEW_ONLY` is not deployment success.

`commands.json` separates inspection, disabled staging, per-role activation and
per-role disabling. No executable apply script is produced. Inspect and compare
live state before applying any stage. A 403 is an access error, not proof of
absence. Existing accounts, pools, providers, roles or environments need a diff
review; do not overwrite them or blindly rerun partially applied commands.
Generated commands use paths relative to the review bundle directory.

## Dedicated identities and authorization scope

Only `gse-v52-runner` and `gse-v52-manual-cleanup` are proposed. Each gets its own
service account and WIF pool/provider. New service accounts are disabled before
any grant; pools/providers are created disabled. The provider requires the exact
repository, numeric repository/owner IDs, `master`, workflow path, environment
and `workflow_dispatch` event. The Python entry additionally checks the exact job,
source, run and attempt; job ID is not invented as an OIDC claim.
This follows the [deployment-pipeline WIF guidance](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines).

| Grant | Runner | Manual cleanup |
| --- | --- | --- |
| Compute project operations | Actual `cloud_preflight.RUNNER` set | Actual `cloud_preflight.CLEANUP` set; no create, metadata or guest login |
| IAP | TCP port 22 only | None |
| Bucket metadata | `storage.buckets.get` | Same |
| Object reads | V5.2 `control/` prefix only | Same |
| Object creation | Exact lease/ledger plus V5.2 immutable `control/attempts/` | Same, for reconciliation/operation/completion receipts |
| Object deletion | Exact lease and ledger keys only | Same |
| Impersonation | Its own pool gets `roles/iam.workloadIdentityUser` on its own account | Same |

Replacing a mutable GCS object needs both create and delete permissions; those
grants do not extend to attempt evidence. There is no object-list/update grant,
bucket administration, IAM administration, service-account attachment/key creation
or project-wide SSH metadata grant. See the
[Storage permission reference](https://docs.cloud.google.com/storage/docs/access-control/iam-permissions)
and [conditional object scopes](https://docs.cloud.google.com/storage/docs/access-control/iam#conditions).

Compute permissions are project-scoped. Their ownership/exact-ID restrictions
are enforced by the native adapter, not by an IAM name-prefix claim. The IAP
condition limits destination port but is not an instance ownership check; actual
original guest identities and host keys are separately verified. The port
condition follows [IAP TCP forwarding](https://docs.cloud.google.com/iap/docs/using-tcp-forwarding).
External public-image permissions are not incorrectly granted on the experiment
project. Exact image GET and real boot-disk creation still have to succeed.

Organization/folder IAM reads are not required. Inherited grants/denies are not
exhaustively audited here; actual required/forbidden diagnostic probes and the
owned request paths remain necessary. The operator's administrative deployment
permissions are separate from the much smaller runtime identities.

Required service APIs are listed in the proposal, including Resource Manager
for the actual project permission probe. No API is enabled automatically. Shared
network, subnet, bucket lifecycle and older-version IAM settings are not edited.
Current native evidence is stored under `control/attempts/<request>/evidence/`;
the existing preflight protects the entire V5.2 control namespace from automatic
Delete lifecycle rules. Do not add a generic bucket expiry rule. Evidence storage
can therefore accumulate; deliberate archival is a separate operator task.

## Environments, activation and safe rollback

Both new environments require the repository owner's approval and allow only the
`master` branch. Self-review is permitted for this single-operator workflow.
Only `v52-cloud-benchmark` holds `V52_EXPERIMENT_SSH_KEY`, an unencrypted Ed25519
OpenSSH private key supplied privately by the operator; never put it in review
files. Manual cleanup has no SSH secret. Environment and branch-policy bodies use
the [GitHub environment API](https://docs.github.com/en/rest/deployments/environments).

After staging and comparing its actual state, activate manual cleanup first.
After exact-source master CI and configuration checks, the operator dispatches
manual cleanup and verifies the whole original job and its retained observation.
Only then activate Runner, set its private secret and use the
[operator guide](PHASE_6_OPERATOR_ENTRY.md). Schedule remains optional and is not
created or required by this package.

The `disable` commands are a stop-on-error rollback aid for identity access;
they do not delete VMs, objects, ledger history, roles or earlier-version settings.
Preserve manual cleanup while any lease/resources may need reconciliation.
Disabling a provider prevents new exchanges but does not revoke already issued
tokens, as described by the
[provider command reference](https://docs.cloud.google.com/sdk/gcloud/reference/iam/workload-identity-pools/providers/create-oidc).
Observe active operations and lease expiry/grace before changing access. Never
replace exact-ID cleanup with broad project deletion.

## Completion boundary

Local implementation now includes original input provenance, fixed provider
preflight, safe manual cleanup, whole native members, renewable ownership,
private guest/storage/Java preparation, immutable retention, original Runner
provenance and independent complete-set replay. Workflow/configuration/setup
artifacts are present. Existing hosted measurement acceptance remains attached
to its [historical exact source](PHASE_6_HOSTED_ACCEPTANCE.md).

Before the first paid member, the operator still must:

1. Merge reviewed changes and obtain the exact-master **V5.2 Cloud Build**
   or full protected CI. A prior source's green build cannot substitute.
2. Inspect live infrastructure and identity collisions, apply/compare disabled
   staging, set the private secret and activate the two identities in the order
   above. Preserve raw administrative observations separately from public artifacts.
3. Confirm a recent successful manual cleanup on the same source. WAITING is
   not empty-state readiness; investigate and let lease/grace rules reconcile it.
4. Prepare one selected member with an explicit priced estimate, approve its
   exact request hash, and manually trigger `run` after merge. All nine execution
   units may run in any order on one sequence/source with whole original histories.
   The [five drill shards](PHASE_6_HOSTED_DRILL.md) use hosted jobs; other runs
   and complete-set replay still select `execution_host=self-hosted`.
5. After all nine original successes, use `verify-set`. Preparation, cleanup or
   an individual successful job is not complete cloud acceptance.

Those external actions have not run. The local development goal stops before
push/deployment/dispatch; paid acceptance and publication remain open.

## Local validation

`target/v52-cloud-setup/validation-summary.json` retains file/log hashes and
the local review bundle. The entry/preflight/cleanup group passed 114 cases;
the final setup-only group passed ten cases, including a subsequent explicit
rejection of unreviewed disk/machine quota policies. The CI contract group passed
75 cases. Groups overlap and must not be summed as independent tests.
Discovery assigns all 1,149 cases once across the existing eight Python lanes;
the 62 expanded full-CI jobs remain required. Discovery is not a new full run.

Generated command quoting/file references, source workflow contracts, Python
syntax, local documentation links and whitespace were checked. Provider/identity
observations in tests are modeled. Only public documentation and local SDK help
were consulted for deployment syntax; no authenticated provider query or command
was executed. No new Maven build, workload measurement or long physical replay
was needed for these configuration/review changes.
