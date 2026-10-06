# V5.1 native owned experiment integration

**Status:** accepted through PR #292, master
`20f977e8b5fed5bc5f54f53218c27d7971c2b3d4`,
[CI 37424341468](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37424341468)
attempt 1 (36 successful jobs), together with
[immediate preparation failure cleanup](PHASE_6_OWNER_FAILURE_CLEANUP.md).
The subsequent [manual Runner entry](PHASE_6_NATIVE_RUNNER_ENTRY.md) is a separate
implementation candidate. No real GCP workload has yet been qualified, and full
Phase 6 remains open.

## Fixed entry and reused workload

`cloud_runner_owned.run_native` continues fresh request/credential admission,
once-only resource creation, pinned IAP identity, native volume setup and original
package transfer into the existing complete experiment. It accepts the original
reviewed inputs, with no backend, credential, clock, SSH command or target override.
The legacy fake Runner and public offline adapters remain closed to native inputs.

The workload is the existing [complete experiment](PHASE_6_OWNED_EXPERIMENT.md):
three healthy modes (published V4.4, published V5.0 configured, candidate V5.1
automatic), followed by automatic leader-loss, maintenance and no-quorum. The
same authenticated V4.4 backup feeds all three healthy modes. Three installed
packages are reused across six distinct service groups; the fault groups retain
their existing public empty bootstrap. No measurement or mutation is resubmitted
after a lost response. Existing bounded immutable source downloads can retry reads.

Physical/history replay, shared source validation, backup/restore checks, combined
evidence budgets, 270 healthy calls and frozen per-cell ceilings are unchanged.
Native request validation is passed explicitly to the aggregate evidence readers;
replay does not infer authority from a claimed result. Independent replay receipts
remain evidence-only; the outer native owner records actual execution scope.
A complete experiment is not the full canonical qualification set:
`fullRemoteQualification` remains false.

## Guest session and deadlines

A new trusted session receiver runs from the controller's closed source bundle,
before importing any installed Python. It rechecks the original native package,
account, metadata and mounted filesystem. The admitted session binds package
hash, original preparation clock/boot identity, three exact private peer IPs,
port and the original owner lease deadline. Roots, node identities, group IDs,
mode and fault-cell names are derived from that session and cannot be supplied
as arbitrary service destinations. Bootstrap accepts transferred source objects,
not a controller-provided guest filesystem path.

An exclusive durable session claim precedes service use. A torn claim stays
UNCERTAIN; a lost begin response permits queries only. Preparation, source creation,
source transfer and bootstrap retain their original deadline. Completed service
sessions remain usable after preparation expires, only until that same original
lease deadline. Both the parent launcher and new daemon check it; reconnecting,
changing the boot ID, or starting another daemon cannot renew it.

Every native connection uses pinned SSH with a short-lived bound token file and
isolated gcloud configuration. Ambient credentials and API redirects are not
inherited. Provider IDs, attached disks, exact retained lease/ledger and host pins
are rechecked. Binary partial source bytes may be retained for diagnostics; raw
credential-bearing transport diagnostics are not retained.

## Completion and cleanup

The original creation API is consumed once when the completed preparation hands
off to the owner. The new owner independently reads the retained lease, charge and
cleanup context. Creation authority cannot be reused after handoff. Runtime calls
cannot create resources or mutate control state; cleanup alone permits exact-ID
resource deletion and lease-ID adoption through the existing reconciliation code.
Manual/scheduled reconciliation still enforces expiry plus grace independently.

The controller stops and collects after any cell failure. It retains the closed
startup/preparation inventory, native sessions, original history archive, evidence
result and a hash inventory under the exact attempt prefix. Each immutable upload
must be read back exactly. Collection failures keep partial history where it can
be packaged. Cleanup is attempted even if validation, service shutdown or upload
fails. An uncertain authority read stops mutations; the retained lease remains
available to independent expiry cleanup.

A terminal PASS requires all four cells, independent physical/history and backup
validation, the original time budgets, verified evidence and confirmed cleanup.
Failures remain FAIL and their charge is never refunded. Completion retention
precedes the append-only ledger event. Lease release requires verified evidence,
completion, a terminal ledger state and resource absence; unresolved uploads or
cleanup keep the lease. Partial preparation uses its separate immediate failure
continuation and cannot produce a successful workload completion.

The [native experiment timing amendment](PHASE_6_PREPARATION_BUDGET.md) sets
preparation to 1800 seconds and binds the same allocation in the approved plan
and owner controller. The USD 200 cumulative ceiling, lease 5400 seconds, operation
grace 1080 seconds, validation/retention 600 seconds and cleanup 600 seconds
are unchanged. Final completion calls use the remaining existing control
allowance. The retained completion labels its timing as `budgetBeforeCompletion`;
the local final receipt also accounts for the completion calls in `budget`.

## Qualification and next step

Native session tests exercise actual claim/package/configuration validation with
synthetic provider and operating-system boundaries. Owner-policy tests use the
real CAS, immutable retention, terminal ledger and exact-ID cleanup algorithms
against synthetic HTTP. Deterministic lifecycle tests inject workload, collection,
shutdown and upload failures; they do not count as real JVM/cloud evidence.
Shared guest regressions and the existing complete loopback-SSH experiment cover
the reused workload implementation. New unit tests join the existing storage
lanes; no CI job or paid entry is added.

Local validation and the combined PR description are retained under
`target/v51-native-owned-workload/`. The [manual entry candidate](PHASE_6_NATIVE_RUNNER_ENTRY.md) supplies explicit
workflow selection, original artifact/approval handoff, summary and operational
prechecks; its own protected CI and exact-request approval precede cloud execution. Actual Compute/IAP,
guest privilege and end-to-end timing still need that separately approved run.
Manual cleanup remains sufficient admission evidence; delayed schedule does not
block this development step. Never resume a failed preparation or reset charges.
