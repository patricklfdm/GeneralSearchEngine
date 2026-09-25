# V5.1 Phase 6C3A: owned cloud control and failure qualification

**Status:** implementation candidate on master
`57622552e02addfae991642786e1a87a0633fb43` after PR #229. Exact-master
[CI 36094121631](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36094121631)
passed all 27 executed jobs, accepting the corrected
[public 512-slot runtime](PHASE_6_FULL_SIZE_RUNTIME.md) and closing 6C2 alongside
its accepted rich, fault and component gates. This controller requires its own
protected CI. Full 6C and paid admission remain open.

## Implemented boundary

The controller executes prepare, cell dispatch, stop, binary collection, retention,
cleanup and completion through adapter interfaces. It currently accepts only
`fake-v51-cloud-control` adapters. The local provider and object store are in-memory
fakes; diagnostic guest commands use the actual fsynced
[command store](../../../scripts/v51/remote_command.py), and collection uses the
actual bounded binary pack/unpack implementation. No GSE calls, GCP SDK, credentials,
network requests or cloud resources are used by this gate.

The [authority module](../../../scripts/v51/cloud_authority.py) and
[runner](../../../scripts/v51/cloud_runner.py) are V5.1-specific. V5.0's suite,
leases, cost history and same-group disk replacement are outside these interfaces.
The existing planning-only `cloud_plan.py` remains a separate historical fixture.
The frozen [6B workload](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md), including its 15 cells,
limits and approved document-size exceptions, is unchanged.

## Request and admission

A closed request binds source, bundle and configuration digests, frozen workload
hash, sequence, globally unique attempt, member, order and creation time. Unknown
fields, V5.0 identifiers, paid execution and malformed identities are rejected.
The control approval binds the exact request and preflight digests, confirmation,
per-attempt conservative charge and previously observed suite-wide charge.

Preflight requires all seven observations (configuration, IAM, image, quota,
retention, exact-source CI and remote qualification), an expiry within 900 seconds,
and a completed cleanup for the exact source within two hours. Either schedule or
manual dispatch qualifies, with its exact workflow/ref and actually executed PASS
reconciliation; a skipped, WAITING, future or different-source receipt cannot qualify.
Freshness is checked at admission; expiry after an admitted start does not reset or
abort the separate runtime deadline.

The reserved identities are `.github/workflows/v51-replication-evidence.yml`,
`.github/workflows/v51-expired-cleanup.yml`, `.github/workflows/v51-manual-cleanup.yml`,
`refs/heads/master` and environment `v51-cloud-benchmark`. They are **not deployed**
by this batch. Observations, digests and charges in the gate are synthetic test
inputs, not actual CI attestations, image readiness, prices or paid approval.
A future trusted adapter must collect and verify them before enabling a different
execution scope; callers cannot turn this fixture into a paid runner with a flag.

## Single topology, sequence and append-only cost history

One generation-conditional lease covers the entire V5.1 suite, at
`v5.1-automatic-leadership/control/active.json`. An existing lease, even expired,
blocks new allocation until explicit reconciliation. The separate ledger at
`v5.1-automatic-leadership/control/ledger.json` contains only appended reservation
and terminal events. Before any create, the controller verifies the ledger and
reserves the attempt against its observed generation while owning the lease.
A raced write or lost acknowledgement cannot authorize any Compute call.

The budget is USD 100 in integer microunits across all attempts, sources and
sequences in this suite. Failed attempts remain fully charged; changing sequence
cannot reset the ledger. The fixture's USD 1 reservation is an arbitrary test input.
No pricing, refund or financial estimate is claimed.

Both accepted member orders are implemented. Every attempt within a sequence keeps
source/bundle/configuration/workload/order identities. Only the next unfinished
member can run. Failed experiment/failure-drill attempts may use a new attempt ID;
a failed canonical blocks that sequence and requires a fresh complete comparable
sequence. Pending reservations block another attempt even if a lease is missing.
Terminal records must reference a real reservation and can be appended only once.

## Resource ownership and failure cleanup

The fixed intent contains four firewall rules, three 50-GiB boot disks, three
100-GiB data disks and three voter instances. There are no replacement generations.
Each intent includes the attempt owner, request digest and deterministic operation
identity. The controller persists `attempted` before calling create, then retains
the returned exact resource ID. A lost create reply is resolved through that exact
operation; an unknown/pending operation remains unresolved even when describe
returns absence. No resource creation is blindly retried.

Finally cleanup and expired schedule/manual reconciliation call the same deletion
implementation. It requires a completed original operation and matching full
resource ownership/ID. It deletes instances before disks and firewall rules,
continues after individual errors, and reads back every attempted name. A foreign
owner, reused name/ID, denied operation read, unresolved creation, failed deletion
or missing absence proof keeps the lease. Store updates and lease deletion are
conditional on the observed generation; a stale controller cannot release a new
owner's lease.

Manual cleanup changes only when inspection starts. It waits until the original
5400-second lease plus 1080-second operation grace has expired, exactly like schedule.
There is no force mode. Operation grace does not extend workload time. The existing
[time accountant](../../../scripts/v51/remote_budget.py) retains each cell's own
ceiling and the independent 600-second cleanup reservation. Cleanup is attempted
after a control/cell overrun, cancellation or upload failure.

## Remote commands and retained evidence

Each diagnostic cell submits one identity-bound command. A dropped response causes
only receipt queries under the original deadline. A reconnect can replace a failed
query connection; NOT_FOUND/UNCERTAIN is never permission to submit again. The
qualification retains one handler execution per issued successful diagnostic cell.
This tests command ownership, not real token renewal or engine workload performance.

Stopped diagnostic evidence is packed, independently unpacked, then uploaded as
immutable binary parts plus metadata with exact read-back. Evidence and completion
retention precede the terminal ledger event and lease release. Failed retention
still triggers cleanup and preserves a lease. Expired reconciliation retains its
own failure/cleanup record, finishes an interrupted reservation conservatively,
and can release only after exact absence and retention. It preserves any earlier
immutable completion, never upgrades failed workload history to PASS. In particular,
reconciliation of a failed evidence upload is not recovery of missing GSE evidence.

The local qualification writes requests/ledger, provider operation/deletion records,
command receipts, raw parts, relocated copies and terminal outcomes. Store audit
JSON records binary objects by size/digest; the actual parts remain under each
case's guest directory. Every receipt states `engineWorkloadExecuted=false`,
`fullRemoteQualification=false`, `paidCloud=false`.

## Gate and next integration

```bash
scripts/verify-v51-phase6-cloud-control.sh
```

The required `Cloud runner (no GCP)` job runs this gate with a 120-second subprocess
backstop and always uploads `target/v51-cloud-control` for fourteen days. Existing
job dependencies, Required results, docs-only behavior and Maven builds are unchanged.
Foundation test discovery also includes the new authority/lifecycle regressions.

The 19 retained cases cover success, lost response, query reconnect, partial and
unresolved insertion, startup, unavailable SSH, cancellation, collection/upload/
read-back/completion failure, failed/falsely reported deletion, foreign ownership,
reused IDs, denied operation reads, preparation and cell overrun. Unit regressions
also cover both complete sequence orders, digest/freshness/scope changes, ledger
replay, stale generations, lost reservation/intent acknowledgements and expired
manual reconciliation. A FAIL that matches an injected fault is qualification PASS;
it never becomes a passing workload member.

**Remaining 6C3 integration:** a source-exact build/jlink bundle and guest launcher;
actual persistent JVM wiring over remote hosts; independently collected provider,
GitHub and pricing observations; real generation-conditional storage and operation
resolution (including exact-ID deletion races); renewable credentials; V5.1-owned
manual runner and both cleanup workflows, WIF/environment/IAM setup; real partial
provision/SSH/upload/cancellation/deletion adapter qualification; fresh configuration
review and exact-source full CI. In-memory adapter results do not qualify those
provider semantics. Paid runs remain separately confirmed and user-triggered.


## Local candidate validation

The complete gate passed all 19 cases and 34 focused tests. Complete V5.1 discovery
passed 502 tests under Python 3.11; 33 CI/topology/toolchain tests passed. YAML and
131 shell blocks were checked. The comparison to the accepted workflow preserves
all 24 other job definitions and every existing cloud step; only the new short
gate and its always-uploaded evidence were added. The documentation gate checks
55 required documents; an expanded walk checked all ten changed documents and
744 local links, including anchors. Whitespace checks passed.

Receipts and logs are indexed at `target/v51-cloud-control-review/validation-summary.json`.
The qualification records the dirty local candidate's source and Python input
hashes. No production Java, POM, frozen workload, published control or V5.0 cloud
implementation changed. A new Maven reactor/workload run was unnecessary for this
Python control-only change; corrected-source protected CI remains pending.
