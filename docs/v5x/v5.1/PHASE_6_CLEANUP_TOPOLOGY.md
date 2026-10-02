# V5.1 Phase 6 — complete-topology cleanup qualification

**Status:** implementation candidate on `f299b61a2e724ffb45c27a2c9150965d09626655`
(PR #277). The user authorized branch development while the second single-disk
fixture finishes. Keep this change unmerged until that review and protected CI
complete. No topology has been allocated by this development task.

## Purpose and inherited state

The [single-disk driver](PHASE_6_CLEANUP_FIXTURE_DRIVER.md) exercises conditional
object access and one data-disk deletion. This candidate supplies a bounded way to
exercise all three Compute resource kinds and their cleanup dependencies before
connecting the engine workload to real infrastructure.

The original disk's expired cleanup `36985944368` passed independent absence,
terminal ledger and provider deletion-audit review. The original failed object
probe remains FAIL. Its grace workflow returned WAITING, but no separate
post-grace state snapshot was retained before deletion; that coverage is not claimed.
PR #277 accepted the generation correction at master `f299b61`, exact-master CI
`36986377529` attempt 1 (29 successful jobs).

The separately approved second fixture has native request
`f1a49e0c223c4a0d99621cb1f861899a9af809100b6796049c022b5713ba3d81`.
Manual run `36989911551` passed all eight object cases; independent observations
returned `OBJECT_SCOPE_MATCH` and active `STATE_MATCH / ACTIVE_OR_GRACE`.
Its expiry is `2026-10-02T10:52:57Z` and deletion eligibility is
`2026-10-02T11:10:57Z`. Grace and expired-state/audit reviews remain pending.
The native ledger reserves USD 2 cumulatively for the two single-disk attempts;
the earlier USD 1 failed attempt remains charged. These records do not authorize
this candidate's larger allocation.

## Closed fixture profile

The [request/driver](../../../scripts/v51/cloud_topology_fixture.py) uses the
unchanged thirteen-row native inventory:

| Resource | Exact scope |
| --- | --- |
| VMs | Three private Standard `n2-standard-8` instances, no attached service account or public IP |
| Boot disks | Three 50 GiB `pd-balanced` disks from the frozen image name/numeric ID |
| Data disks | Three 100 GiB `pd-balanced` disks, `autoDelete=false` on attachments |
| Firewalls | Four existing attempt-tagged peer/IAP/deny rules, unchanged network/ports |
| Authority | One exclusive 5400-second lease plus 1080-second grace; existing append-only ledger |
| Preparation | One 600-second deadline for reads, conditional writes, inserts and original-operation polling |
| Reservation | Proposed USD 5 under the approved USD 200 suite ceiling, including prior failed charges |

No engine package, guest command, mount, workload, IAM grant, workflow dispatch or
identity enablement is performed. The exact reviewed public SSH descriptor appears
in the existing closed metadata shape. No private key is retained in evidence.
The runner and scheduled identities remain disabled.

### Keep VMs present for an actual cleanup deletion

The ordinary workload VM profile uses a 5400-second maximum runtime and `DELETE`.
Those VMs can disappear before the lease's 6480-second cleanup eligibility,
which cannot demonstrate a deletion by the cleanup identity.

This fixture alone uses **5400 seconds then `STOP`**, leaving stopped instances
and their disks for exact-ID cleanup after the unchanged grace period. Google's
[runtime-limit API](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime)
supports stop or delete as the termination action. The runtime cap is not extended;
disk/evidence charges and delayed-cleanup overhang remain budgeted.

The closed [profile contract](../../../scripts/v51/cloud_topology_contract.py)
binds that action, all resource counts, times, prices and configuration to the
native request's bundle hash. The distinct `gse-v51-topology-cleanup-context-v1`
retains the manifest. Preparation, independent observation and both cleanup
entries reconstruct the same checked profile. Missing/changed manifests and
unbound requests fail validation. Existing contexts retain their original schema
and ordinary workload VMs retain `DELETE`. This profile is not a canonical
workload amendment, paid-runner admission or permission qualification by itself.

## Review and once-only preparation

`review` writes a create-only local package. It requires a clean tracked checkout,
a fresh independent empty lease/settled ledger observation, reviewed operator and
public key, and fresh provider image/topology/quota/storage observations. Price
inputs cover all three VMs and 450 GiB of disks for the chosen duration, plus
requests, thirty-day evidence retention, Actions and failure overhang. The duration
must cover at least 6480 seconds; the ceiling-rounded estimate must fit USD 5.
There are no built-in current price numbers and USD 5 is not a provider spending cap.

`prepare` requires that package's exact digest, unchanged approved state, the
current master source with every required CI job successful, matching manual
workflow bytes and a fresh explicit configuration readback. Image, quota,
network and storage observations are collected again before writes. The reviewed
operator supplies credentials; ambient impersonation/token overrides are rejected.
Review/preflight evidence is not converted into an approval flag.

The shared real/offline driver then:

1. Checks all thirteen names and original operation IDs are absent, plus absent
   attempt context/manifest and unchanged native control objects.
2. Acquires the lease conditionally, appends the USD 5 reservation to the observed
   ledger generation, and retains the complete reconstruction context.
3. For each fixed resource, persists `attempted=true` before its one insert,
   waits only on that original operation, verifies the numeric ID/body and
   persists the returned identity before proceeding. Before each VM insert,
   rechecks its disks and firewall dependencies against retained IDs.
4. Retains the full prepared manifest and emits `PREPARED`, exact resource IDs,
   lease expiry and cleanup eligibility. Independent read-only observation plus
   `review-prepared` must match all thirteen live identities/original operations,
   the context, reservation and preparation receipt.

Every upload is generation-conditional and read back. A failed/uncertain mutation
stops preparation; neither the current process nor a fresh invocation repeats it.
No compensating deletion, new resource name, new lease or refunded reservation is
invented. An original insert whose response was lost is resolved by existing
expired cleanup. A missing/ambiguous/pending operation stays unresolved. In
particular, an image refusal after durable intent but before insertion does not
prove no insert could exist; that attempt retains its lease for investigation.

## Operator sequence after protected acceptance and separate approval

Prepare the review package first, using fresh prices and an empty settled lease:

```bash
python3 -m scripts.v51.cloud_topology_fixture review \
  --operator "$APPROVED_OPERATOR" --public-key "$PUBLIC_KEY_FILE" \
  --prices "$REVIEWED_TOPOLOGY_PRICES_FILE" --output target/v51-topology-request
```

Only after approval of the exact package, resource profile, USD 5 reservation and
operator availability through cleanup:

```bash
python3 -m scripts.v51.cloud_topology_fixture prepare \
  --request target/v51-topology-request/request.json \
  --confirm "$FIXTURE_SHA256" --output target/v51-topology-preparation
python3 -m scripts.v51.cloud_cleanup_observation capture \
  --output target/v51-topology-before
python3 -m scripts.v51.cloud_topology_fixture review-prepared \
  --request target/v51-topology-request/request.json \
  --preparation target/v51-topology-preparation/receipt.json \
  --observation target/v51-topology-before/observation.json \
  --output target/v51-topology-prepared-review
```

The user triggers Manual Cleanup with **empty** `object_probe_request`. This is
not a single-disk object-probe manifest. Retain active WAITING, grace WAITING and
expired cleanup evidence with independent snapshots bracketing each run. Record
the original source/collector; do not switch collector bytes between observations.
Inspect VM state before expired cleanup and provider audits for the actual manual
identity's numeric instance/disk/firewall deletions. An already absent instance or
an independently stopped VM is not evidence of a delete by that identity.

The existing read-only state reviewer establishes authority/absence consistency;
it does not authenticate artifacts or replace provider audits. Verify all thirteen
identities absent, lease released, completion retained and the full reservation
still charged. A cleanup-only attempt ends as FAIL in the native workload ledger
because no engine workload ran; cleanup itself may PASS.

## Offline qualification and remaining work

The existing cloud-preflight gate runs the added unit suite and
[retained qualification](../../../scripts/v51/cloud_topology_qualification.py).
Eleven cases each cover manual and schedule: complete topology, lost firewall/
boot/instance insert responses, pending instance operation, reused instance name,
delete denial, missing context, generation conflict, completion-retention failure
and image drift. The credential-bound fresh-process entries replay nine cases;
two injected storage-conflict cases use the same native policy in process.
All outcomes retain previous charges. Correctly blocked cleanup is qualification
PASS with an underlying FAIL and retained lease, not successful resource cleanup.

Unit regressions additionally lose the insert response at every one of the thirteen
inventory positions, check the exact grace boundary, original preparation deadline,
conditional authority failures, no mutation replay, dependency replacement,
forbidden raw calls, source/approval gates, complete cost arithmetic and independent
prepared-state tampering. Existing single-disk and ordinary provider/cleanup tests
remain required because the optional profile crosses those shared components.

Actual provider qualification, scheduled identity activation, runner permissions,
real SSH/mount integration and remaining failure-drill/canonical workload wiring
remain open. This batch adds no CI job or Maven build and makes no claim of paid
workload readiness. User-owned commit/push/PR can proceed on the branch; merge and
any new cloud allocation are separate steps after the pending reviews.

### Local validation of this candidate

- Complete cloud-preflight gate: 153 unit tests; 61 preflight/identity/permission
  negative cases, eight single-disk cases, five original driver/probe chains and
  all 22 topology/manual/schedule outcomes passed. Evidence is retained at
  `target/v51-cloud-preflight/run.ZteKHu/`.
- The additional provider/native-cleanup/entry/runner/CI suite exercised 126
  cases. Four loopback TLS cases initially could not create sockets in the sandbox;
  those four passed with loopback access enabled. The other 122 passed initially.
- A new real loopback TLS test reconstructs this profile through the network
  cleanup entry, deletes all thirteen numeric IDs in dependency order and retains
  prior charges. It passed separately; this does not establish real GCP behavior.
- Both documentation contracts, changed local links/anchors and whitespace passed.
  The local scripts used Python 3.10; protected CI still must validate the committed
  candidate on its configured toolchain. No Maven/runtime Java change was made.

Logs and final candidate file hashes are retained under
`target/v51-cleanup-topology-review/`. Initial development failures remain under
`target/v51-topology-dev/`; these include a tuple/list serialization mismatch in
the new manifest and test-fixture setup errors, corrected before the final gate.
Corrected-source protected CI remains pending.
