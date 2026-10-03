# V5.1 Phase 6 — complete-topology cleanup qualification

**Status:** topology implementation accepted through PR #278 at master
`3e7e564972be01eb5894977cdc3c05e362bda0c0`, exact-master CI `37000588745`
attempt 1 (29 successful jobs). PR #279 accepted the duration-readback correction
at `9542f4910da439f31356da30b121ee8ced1af6ba`, exact-master CI `37059101337`
attempt 1 (29 successful jobs). PR #280 accepted the deletion-operation correction
at `e9c85c4631ce75b82fdeec3777361ddbbfe846c0`, exact-master CI `37075056038`
attempt 1 (29 successful jobs). The failed eleven-resource allocation is fully
cleaned up. The separately approved second allocation prepared all thirteen
resources and passed independent active/grace WAITING and expired PASS review.
All thirteen original identities are absent, the lease is released, and USD 12
remains reserved cumulatively. Completion remains FAIL because no engine workload ran.

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
`2026-10-02T11:10:57Z`. Grace run `36998281162` returned WAITING; expired run
`36999734150` passed independent absence/terminal-ledger and manual-SA deletion
audit review. No separate post-grace snapshot was captured before deletion, so
that coverage remains open. Both single-disk reservations remain charged (USD 2).

## First live topology and duration readback correction — 2026-10-02

The user approved the reviewed thirteen-resource profile, same operator and
USD 5 reservation. The review freshness window expired before execution; fresh
read-only observations retained the same source, configuration, resource names,
attempt/sequence, public key, prices and amount. Both packages and the exact scope
comparison are retained; the old request was never executed. The executed fixture
digest is `fff43e62d351b88f61b97f60516c0f9f4f574cd997fc14471d70e76a86af3a43`,
native request `57c6be206a9528c326114b39fc00de759792412b0e9577a64cc15f7077611b6b`,
attempt `de6b9671ac2c4a99ae562e04296c417f`.

Preparation retained all four firewalls and six disks. The first VM's original
insert completed with numeric ID `1865582398806300060`, but readback rejected
`maxRunDuration={"seconds":"5400","nanos":0}` because the request only contained
`{"seconds":"5400"}`. The [Compute REST contract](https://docs.cloud.google.com/compute/docs/reference/rest/v1/instances)
defines integer `nanos` as the fractional-second component. Zero does not extend
the requested lifetime. This is a provider-response compatibility bug, not a
timeout or an uncertain workload result. The observer and cleanup use the same
inspection path and would reject that VM too.

The correction accepts either an omitted fraction or integer zero, keeps exactly
5400 seconds, and rejects nonzero, malformed or unknown duration fields. STOP for
the fixture and DELETE for ordinary workloads remain distinct. The outgoing
request bytes, metadata, ownership, numeric IDs, disk attachments, deadlines and
budget do not change. The offline HTTP double now returns the explicit zero so
ordinary creation, interrupted-insert recovery and cleanup exercise real response
shape rather than echoing the request.

The failed attempt must not resume or recreate resources. Preparation retained
ten IDs; cleanup subsequently recovered the eleventh from its bound insert operation.
The last two VMs were never attempted. Lease start is `2026-10-02T13:00:52Z`,
expiry `14:30:52Z`, cleanup eligibility **`14:48:52Z`** (Beijing **22:48:52**).
The ledger remains USD **7 / 200**, including the full failed reservation. After
PR #279, the manual runs below reconciled this partial inventory, with independent
observations on that accepted source and provider deletion audits. This
eleven-resource cleanup cannot qualify the complete thirteen-resource topology.

Original receipts, HTTP call identities, raw provider response and the original
blocked observation remain at `target/v51-topology-live-review/`. Local response
replay/tests and the PR description are at `target/v51-gcp-duration-readback/`.
No engine workload, second preparation attempt, direct operator deletion or
schedule/runner identity activation was performed. A future complete topology
requires a new reviewed allocation after this attempt is reconciled.

Local validation of the correction: the explicit-zero regression and full
topology lifecycle both fail on the original decoder; 32 provider/topology and
85 related cleanup/native-entry/network/runner tests pass after correction.
The unchanged retained GCP response passes local replay. The complete preflight
gate passes 153 unit tests, 61 preflight/identity/permission negatives, eight
single-disk cases, five fixture/probe chains and 22 topology manual/schedule
outcomes at `target/v51-cloud-preflight/run.kbXOLH/`. The original preparation
remains FAIL. These local checks were subsequently accepted by PR #279 and
CI `37059101337`; the actual expired cleanup is recorded below.

## Delete operation target compatibility and cleanup closure — 2026-10-02

Manual cleanup [37062489423](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37062489423)
passed permission prechecks but failed during reconciliation. GCP accepted VM and
firewall deletes addressed by exact numeric ID, returning that numeric path in
`targetLink`. Disk delete operations instead returned the resource-name path.
The decoder required the name path for every resource, so it rejected the accepted
VM/firewall operations before polling them. The boot disk delete was then refused
while its VM was still being deleted: VM delete accepted at `20:46:22Z`, boot
delete refused at `20:46:24Z`, VM deletion completed at `20:46:26Z`.

Independent observation subsequently found ten resources absent and only the
50 GiB `n1-boot` disk (ID `3724585123737376166`) present, detached and READY.
The user started a new manual cleanup
[37063862494](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37063862494),
which passed. Before/after review returned `STATE_MATCH / EXPIRED_ABSENCE_CONFIRMED`:
all eleven attempted identities absent by name and numeric ID, lease released,
unchanged FAIL completion and append-only ledger. Provider audit binds the final
disk deletion to the manual cleanup service account. All USD 7 reservations remain;
the original preparation and first cleanup remain failed historical evidence.

The correction accepts a delete operation's exact name URL or its exact expected
numeric-ID URL. Request ID, action, project, zone, resource collection and final
numeric target checks remain mandatory. A supplied `targetId` is also checked
during PENDING/RUNNING; insertion binding remains unchanged. Waiting continues on
the original operation with the original 30-second deadline and no mutation replay.

The HTTP double now models the observed per-resource URL forms, rejects deletion
of an attached disk, and supports asynchronous deletion that keeps resources until
the operation is polled to DONE. Manual and scheduled offline topology cases
exercise that path. Unit checks prove VM completion precedes disk deletion, reject
foreign targets and mismatched in-progress IDs, and retain the original timeout
when a delete never completes. This changes response handling, not cleanup authority,
allocation profiles, IAM, workflow triggers, timing limits or budgets.

Original and follow-up evidence is retained under
`target/v51-topology-live-review/cleanup-37062489423/` and
`target/v51-topology-live-review/cleanup-37063862494/`. New regression logs and
unchanged-provider-response replay are under `target/v51-delete-operation-target/`.
PR #280 subsequently passed corrected-source protected CI `37075056038` at
`e9c85c4631ce75b82fdeec3777361ddbbfe846c0`. Both identities were disabled then;
the later scheduled enablement is recorded in the deployment review.

Local correction validation: 38 provider/topology tests passed; four regressions
first failed against the original decoder. All eleven unchanged retained complete
provider responses now decode successfully; the original decoder rejects five VM/
firewall responses. The 106-case cleanup/entry/credential/runner regression run
exposed one old fixture deleting disks before VMs. That fixture now follows the
production dependency order; all nineteen native-cleanup tests passed on recheck,
and the other 87 cases, including loopback TLS, passed the initial run.
The complete preflight gate passed 155 unit tests, the existing 61 preflight/
identity/permission negatives, eight single-disk cases, five fixture/probe chains
and all 24 topology/manual/schedule outcomes at
`target/v51-cloud-preflight/run.we1sv3/`. No live allocation or cleanup was run
during this correction.

## Second live topology — 2026-10-02

After PR #280 acceptance, the user approved a fresh source/price/configuration
review and one USD 5 reservation. The fixture digest is
`7a2370252776e245dbde0a6b2f78910b6f32038ab183b25d17134e64dee08ce7`, native request
`39479dcbee806f17ee40b483de4a8b5ad5452fd9d78e07f6f5737bbe36ef7711`, attempt
`b1c42040da52468dbdc6e9c14965df0b`. Preparation ran once on the accepted
`e9c85c4` source and returned PREPARED for all thirteen original resource IDs.
Independent GET-only review returned PREPARATION_STATE_MATCH; all three VMs
were RUNNING at that observation. The ledger preserves the previous USD 7 and
adds USD 5, for USD 12 total; the new attempt remains PENDING.

Manual run [37078761266](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37078761266)
attempt 1 passed its actual permission precheck and returned WAITING. Independent
before/after review returned `STATE_MATCH / ACTIVE_OR_GRACE`: all thirteen exact
identities, lease and ledger remained unchanged. Evidence is retained under
`target/v51-topology-v2-review/`, including original approval/preparation, original
before-state and `active-37078761266/` downloaded evidence, after-state and review.

| Boundary | UTC | America/Los_Angeles |
| --- | --- | --- |
| Lease start | 2026-10-02 23:34:06 | 2026-10-02 16:34:06 PDT |
| Lease expires; grace begins | 2026-10-03 01:04:06 | 2026-10-02 18:04:06 PDT |
| Expired cleanup eligible | 2026-10-03 01:22:06 | 2026-10-02 18:22:06 PDT |

Grace run `37084997701` returned WAITING and independently matched unchanged state;
the after-state was captured at 18:18:08 PDT, before eligibility at 18:22:06.
Expired run `37086891033` attempt 1 returned PASS and independently matched
`STATE_MATCH / EXPIRED_ABSENCE_CONFIRMED`. All thirteen original numeric identities
were checked absent by name and ID; the lease was released and USD 12 retained.
The original-source collector and evidence are retained in
`target/v51-topology-v2-review/grace-37084997701/` and
`target/v51-topology-v2-review/expired-37086891033/`.

Provider audit review matched 26 rows (13 start/end pairs) to the manual cleanup
service account and original resource IDs. All three VM deletions completed before
the first disk deletion. The pre-cleanup VMs were already TERMINATED by the timed
stop but still existed; audits and absence observations establish subsequent
deletion. The ledger retains four terminal FAIL attempts totaling USD 12; no
engine workload ran. This closes the full-topology successful manual cleanup
path, without claiming remaining provider failure paths or full workload readiness.

The user lifted the merge hold; PR #281 merged the scheduled entry at
`471ffd25787bcd872b1b4d71aed2ea620193eecf`, CI `37087985200` attempt 1 (29 jobs).
Schedule enablement and the manual-first policy are recorded in the
[deployment review](PHASE_6_CLEANUP_DEPLOYMENT_REVIEW.md#scheduled-enablement-and-manual-first-policy--2026-10-02).

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
The runner remains disabled. The scheduled identity was subsequently enabled by
separate authorization; its actual scheduled qualification is optional and does
not block development when manual cleanup evidence qualifies.

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
Twelve cases each cover manual and schedule: complete topology, asynchronous deletion, lost firewall/
boot/instance insert responses, pending instance operation, reused instance name,
delete denial, missing context, generation conflict, completion-retention failure
and image drift. The credential-bound fresh-process entries replay ten cases;
two injected storage-conflict cases use the same native policy in process.
All outcomes retain previous charges. Correctly blocked cleanup is qualification
PASS with an underlying FAIL and retained lease, not successful resource cleanup.

Unit regressions additionally lose the insert response at every one of the thirteen
inventory positions, check the exact grace boundary, original preparation deadline,
conditional authority failures, no mutation replay, dependency replacement,
forbidden raw calls, source/approval gates, complete cost arithmetic and independent
prepared-state tampering. Existing single-disk and ordinary provider/cleanup tests
remain required because the optional profile crosses those shared components.

Remaining actual provider failure-path qualification, runner permissions,
real SSH/mount integration and remaining failure-drill/canonical workload wiring
remain open. This batch adds no CI job or Maven build and makes no claim of paid
workload readiness. User-owned commit/push/PR can proceed on the branch; merge and
any new cloud allocation are separate steps. Actual scheduled qualification can
be recorded later and is not a prerequisite for manual-based progression.

### Original topology implementation validation (PR #278)

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
Those original candidate checks were subsequently accepted by PR #278 and
CI `37000588745`. The duration-readback correction passed CI `37059101337`;
the deletion-operation correction passed CI `37075056038` through PR #280.
