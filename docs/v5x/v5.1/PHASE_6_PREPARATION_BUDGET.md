# V5.1 native experiment preparation budget

**Status:** timing allocation accepted through PR #296, master
`5254455d04bc832c5fb4ae4f2b8735a724a089e7`,
[CI 37540790465](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37540790465)
attempt 2 (36 successful jobs). The guest deadline propagation correction passed
PR #297 at master `cdfb5af108c16c7bc01df98b74182a00db6396ee`,
[CI 37552754929](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37552754929)
attempt 1 (36 successful jobs). Its admitted run reached all three installed
packages and sessions, then exposed a separate
[source-producer configuration failure](PHASE_6_SOURCE_PRODUCER.md#native-source-preparation-correction).
That correction passed PR #298 / CI `37565010319`. Run `37569971625` then
generated/downloaded the source but failed at a
[controller path boundary](PHASE_6_NATIVE_OWNED_EXPERIMENT.md#controller-path-correction-and-chain-review)
after 529.357 seconds; it did not exhaust this budget. The path correction needs
protected CI and a fresh approved native experiment.
This amendment applies only to the
four-cell native Runner experiment. It does not change the frozen canonical
machine plan or reinterpret earlier receipts.

## Observed failure and sizing

PR #295's connection reuse passed exact-master
[CI 37524630590](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37524630590)
on `46e2d15cf2e5bf6fe468571101f4e8f753ddfe29` (36 jobs). Its approved
[run 37531128228](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37531128228)
failed at the original 600-second preparation limit before any workload cell.
The original provider operation timestamps show 252.163 seconds for the first
firewall insertion. Admission, provisioning and IAP consumed 494.186 seconds,
leaving only 105.814 seconds for all three guests and service bootstrap.

The first guest reused one pinned SSH connection for thirteen commands, with no
connection failure. The 21-part package stopped before part index 8 was sent.
This establishes an insufficient preparation allowance in this execution; it
does not establish a network throughput guarantee. A 1800-second allowance gives
1305 seconds after the observed provisioning cost, with room for the three
packages and source/service bootstrap. Actual completion must still be measured.

Owner recovery passed in 323.917 seconds, retained original evidence and released
the lease. Independent original-operation/name/numeric-ID readback found all
thirteen resources absent. The ledger retained USD 47 / 200, including this
attempt's USD 10 reservation. No failed charge is refunded.

Original artifact: `v51-experiment-37531128228-1`, ID `11444084706`, SHA-256
`58dc34c0f71610ea36436d60028531fc502e8134f61a1b02f2ac924060f05f3d`.
Local diagnosis and original files:
`target/v51-native-experiment-pr295/run-37531128228/`.
The preceding run `37528957092` failed during unpaid admission; its generic
failure did not retain enough detail to establish a cause. This timing correction
does not claim to diagnose that separate failure.

## Approved scope and clocks

The exact Runner plan now includes `timing`, profile `owned-experiment-v1`.
The plan SHA-256 binds this allocation together with the source, artifacts,
prices, sequence, SSH identity and reservation. Missing or changed timing is
rejected; an old preparation cannot be used with this source.

- **Approval:** still 900 seconds from plan creation, shortened by quote expiry.
  Original preflight, plan, CI and artifact checks run again immediately before
  the first lease CAS. Credential refresh cannot carry that first mutation past
  the admission deadline. Expired plans cannot start execution.
- **Preparation:** one 1800-second monotonic deadline from the original native
  preparation entry, including admission, provisioning, all three guests and
  initial source/service preparation. Once admitted, plan expiry does not shorten
  this execution clock. Connections, polls and queries do not renew it.
- **Lease:** still 5400 seconds; operation grace remains 1080 seconds. The owner
  cannot renew the lease. Cleanup and retained failure handling remain bounded.

| Four-cell experiment allocation | Seconds |
| --- | ---: |
| Admission, provisioning, guests and initial service/source preparation | 1800 |
| Healthy, all three modes | 900 |
| Leader loss | 120 |
| Maintenance | 240 |
| No quorum | 120 |
| Validation and evidence retention | 600 |
| Cleanup and exact-ID absence | 600 |
| Control and transitions | 540 |
| **Allocated** | **4920** |
| Unallocated within the 5400-second lease | 480 |

The 480 seconds are not automatically borrowed by any category. The normal
experiment controller selects this same reviewed allocation; otherwise it would
reject a preparation that the native resource path had just accepted. Default
`Budget()` and the full canonical/failure-drill paths keep their original frozen
limits, including 600-second preparation. Canonical cloud execution will need
its own evidence-based timing review before any proposed amendment.

Workload calls, rates, cell ceilings, exact ownership/IDs, once-only mutations,
USD 200 cumulative ceiling and price coverage through 6480 seconds are unchanged.
No wider IAM, lease or VM-lifetime allowance is needed for this amendment.

## Diagnostics and qualification

Preparation retains admission/resources/IAP/guest-setup elapsed intervals and the
selected preparation ceiling. GitHub Summary displays these phases, approval,
preparation, lease/grace and allocated/unallocated totals. Immediate owner
recovery remains reported separately from failed preparation.

The same change also retains [safe admission failure codes](PHASE_6_RUNNER_ADMISSION.md#safe-admission-failure-diagnostics),
including failures before a native API is returned and the final pre-mutation
recheck. Unknown raw errors stay undisclosed; this does not diagnose the earlier
unpaid admission failure retrospectively.

Regressions cover a delayed firewall and three guest preparations past the
approval window, a complete controller after 1500 seconds of preparation,
1800-second expiry without renewal, unchanged default/cell/lease budgets,
expired approval before the first mutation (including credential refresh),
changed timing rejection, and cleanup/retention with failed charges preserved.
The existing offline storage and admission gates also exercise provider identity,
CAS, package integrity, pinned SSH and cleanup boundaries. Local results are
retained under `target/v51-preparation-budget/`; no paid run is part of this change.

## Guest deadline propagation correction

The admitted [run 37546477964](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37546477964)
used PR #296's 1800-second allocation, but stopped at node 1's volume clock
exchange after 249.500 seconds, before any engine workload. The retained failure
is `PREPARATION_REJECTED`; the original guest clock reply and detailed exception
were not retained. There were no recorded IAP transport failures.

The retained volume request with a valid modeled clock response reproduces a
deterministic blocker: about 1550.507 seconds remained, but the controller's
shared guest-budget validator still rejected anything over 600 seconds. The
package controller also had an independent 600-second check; installed-package,
source/bootstrap and native-session validation reused the same old ceiling.
This reproduction explains the incompatible limits without claiming a retained
raw guest exception or a transport failure.

The correction selects the existing `owned-experiment-v1` profile in the trusted
native volume, package and session paths. Controller allocation and guest
validation share the 1800-second constant from the standalone trusted receiver.
The full native descriptor is bound into the clock sample and consumed claim;
neither the wire budget nor a public duration argument can select a larger limit.
Ordinary helpers and package transfers retain 600 seconds, and their existing
entry points continue to reject native package descriptors. Package inventory,
boot identity, original deadline equality and expired-clock rejection remain
mandatory through source transfer and bootstrap. A lost reply permits queries
of the original operation, never a new clock, deadline or repeated write.

Regression evidence uses real controller endpoints, consumed file claims,
multipart package installation, installed-byte verification and session/source
receivers with a 1550-second budget. OS/provider/network boundaries and backup
payloads are explicitly modeled; no engine or cloud execution is claimed.
Four native controller/boundary regressions and ten existing session cases all
failed against the original implementation's 600-second limit. Boundary cases
cover exactly 1800 seconds, rejection at 1800 seconds plus one nanosecond,
unchanged ordinary limits, unknown profiles, wire overrides, expiry, reboot,
consumed deadline drift, and lost replies without replay. Local logs are retained
under `target/v51-guest-preparation-deadlines/`.

Run `37546477964` owner recovery passed in 302.156 seconds, verified retention
and released the lease. Independent original-name/numeric-ID reads confirmed
all thirteen resources absent. The ledger retained USD 57 / 200, including the
failed attempt. Original artifact ID `11451715815`, SHA-256
`202ab28e40ca6220241a82bcaa94a090aa7bda6e37d12e86b57ab16db08a4cc7`,
and diagnosis are retained at
`target/v51-native-experiment-pr296/run-37546477964/`.
No new cloud mutation or budget increase is part of this correction.

After protected merge, use a recent same-source manual cleanup and a fresh
prepare/review/run sequence with separate exact-request approval. A prior failed
run or expired plan is not resumable.
