# V5.1 Phase 6C3C25 — native authority formats and cleanup HTTP policy

**Status:** implementation candidate on PR #256 master
`2ea9dbbfbf2821afc859663c87925a0e1d93322c`. Its
[CI 36655860450](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36655860450)
passed all 29 jobs on attempt 1. This accepts the preceding
[retained reconstruction](PHASE_6_CLOUD_CLEANUP.md), not this candidate or native
activation. Corrected-source protected CI remains required.

## Separate record domains, shared invariants

The existing fake records cannot become native deletion authority merely by
changing an adapter's execution label. [cloud_native_authority.py](../../../scripts/v51/cloud_native_authority.py)
provides an explicit native facade over the same bounded request, lease, inventory
and ledger algorithms in [cloud_authority.py](../../../scripts/v51/cloud_authority.py).
Neither facade infers its domain from incoming JSON; the native facade cannot be
overridden with a domain keyword. Existing fake record bytes and default call
behavior remain compatible.

| Record | Native schema |
| --- | --- |
| Request | `gse-v51-native-request-v1` |
| Lease | `gse-v51-native-lease-v1` |
| Ledger | `gse-v51-native-ledger-v1` |
| Cleanup context | `gse-v51-native-cleanup-context-v1` |
| Completion | `gse-v51-native-completion-v1` |

Native records require `execution=gcp-v51-owned-control`. Requests and contexts
require `paidCloud=true` as the intended original attempt domain. Requests always
bind the attempt's SSH public descriptor hash. These fields are **not** an
execution receipt or payment approval: the current native-format fixtures retain
`execution=offline-native-provider-cleanup`, `paidCloud=false`, `cleanupReady=false`
and `fullRemoteQualification=false`. The reconstructed adapters and inner cleanup
receipts use `offline-v51-native-control`, never a live execution claim.

Request hashes are calculated over the native bytes; inventory descriptions,
operation IDs, context paths, reservations and completions bind those hashes.
Fake/native requests, leases, contexts and ledger entries reject one another,
including mixed nested records. No conversion, ledger reset or migration command
is supplied. The selected bucket and V5.1 object names remain fixed; unexpected
records at those names block rather than being relabelled or discarded.

The shared rules retain the 13-resource inventory, 5400-second lease,
1080-second operation grace, 100 USD cumulative reservation ceiling, sequence
ordering and failed-canonical blocking. The shared reconciler still handles
manual/scheduled triggers, generation-conditional persistence, immutable evidence,
terminal ledger updates and lease release. The paid runner's fake admission path
continues to reject native records and native-format adapters.

## Closed cleanup HTTP policy

[cloud_native_cleanup.py](../../../scripts/v51/cloud_native_cleanup.py) wraps the
existing HTTP adapter. Before binding it permits only reads of the selected
lease/ledger, with pinned generations for media. Binding requires the exact
observed native lease and generation, the selected configuration hash and an
expired lease including its grace. An active lease remains read-only WAITING.

After binding, requests are checked before reaching credentials or transport:

| Operation | Allowed scope |
| --- | --- |
| Object reads | Exact lease/ledger and this request's context, completion and current cleanup record |
| Lease replacement | Existing observed generation; same request, expiry, inventory and attempted flags; retained or original-operation-resolved IDs |
| Ledger replacement | Observed generation; exactly one matching terminal event appended to the observed history and retained completion |
| Completion creation | Create-only interrupted-owner FAIL record; no synthesized successful workload evidence |
| Cleanup record creation | Create-only current-request/current-generation result |
| Object deletion | Exact lease, after completion, terminal accounting and observed absence of every attempted resource |
| Compute reads | Attempted inventory names, original insert-operation filter, resolved numeric IDs, and exact returned delete-operation polling URLs |
| Compute deletion | Numeric ID resolved from the original completed insert operation, with its exact delete request ID |

Compute creation, metadata changes, guest commands, name-based deletes, unresolved
IDs, arbitrary operation queries, foreign projects/buckets/attempts, evidence or
ledger deletion, history resets, extra query parameters and duplicate query keys
are rejected. A missing original operation remains unresolved. A reused name
cannot substitute another ID. Each resource's complete existing provider shape
and ownership checks still run; the HTTP policy is an additional boundary.

A previous completion is read and preserved, including a previously successful
owner's completion. Cleanup can create only a failure completion for an interrupted
owner; it cannot manufacture a successful workload or erase failed charges. A lost
delete response retains the lease. A later reconciliation queries the original
operation/resource state and can finish without repeating an already completed
delete. A lease generation conflict prevents stale resource deletion.

## Validation

The existing provider gate includes both fake and native-format reconstruction:

```bash
scripts/verify-v51-phase6-cloud-provider.sh
```

Each domain runs the same fourteen fresh-process cases: no lease, active/grace,
expired manual/schedule, empty reservation, missing/changed context, missing
reservation, lost insert acknowledgement, pending/missing operation, reused name
and deletion denial. Native fixtures are constructed from their own request
bytes and operation IDs, not by relabelling retained fake fixtures. The native
inputs, HTTP traces, output states and receipts are retained in the existing
provider artifact under `native-cleanup/`.

Nineteen additional tests cover domain isolation, required SSH binding, existing
admission rejection, observation/generation/expiry binding, HTTP scope and body
negatives, completion/history preservation, exact delete-operation polling,
lost-delete reconciliation, lease CAS conflict, metadata-only refresh rejection and unchanged budget/order rules.
Python 3.10 and 3.11 have different strict empty-query parsing behavior; a missing
query is explicitly handled before strict parsing. Nonempty malformed or duplicate
queries remain rejected.

## Activation boundary and next work

This batch exercises **native-format data through an offline HTTP server double**.
`CleanupApi` rejects a live transport before credential acquisition. Native-format
live Store/Compute adapters retain the unqualified tag; the original HTTP live
mutation barrier remains closed. There is no activation flag or new workflow.
No identity grant, environment, credential transition, cloud deletion or paid
experiment is performed by this change.

Next: separately authorize/apply the already reviewable disabled identity proposal;
review exact workflow/identity and native admission observations; wire and qualify
the native transport and separate manual/scheduled cleanup entries before reviewing
activation. Native provider acceptance, operation-history availability, effective
IAM and actual cleanup readiness require fresh evidence. Source delivery, remaining
workload cells, pricing and exact-request approval still precede user-triggered
paid experiments. Full Phase 6C remains open.
