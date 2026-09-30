# V5.1 Phase 6C3C24 — retained cleanup reconstruction

**Status:** accepted through PR #256, master
`2ea9dbbfbf2821afc859663c87925a0e1d93322c`, with all 29 jobs passing
[CI 36655860450](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36655860450)
on attempt 1. This acceptance covers offline retained reconstruction. The
preceding [disabled identity proposals](PHASE_6_CLOUD_IDENTITIES.md) remain
unapplied; native activation is separately pending.

## Problem and change

The provider could inspect an instance only with the configuration and attempt
SSH public-key descriptor held by its original runner. A new cleanup process had
the retained lease and resource IDs, but no durable way to reconstruct that
provider. In particular, request v2 retained the SSH descriptor's hash rather
than the descriptor bytes. Final startup diagnostics were too late for a runner
that disappeared during allocation.

The runner now retains an immutable `cleanup-context.json` under
`v5.1-automatic-leadership/control/attempts/<requestSha256>/` after its lease and
budget reservation, and **before its first resource create intent**. It verifies
an exact read-back. The closed record contains only:

- Schema, control-only execution marker, `paidCloud=false`, and request hash.
- The exact provider configuration, checked against the request's configuration hash.
- The attempt/user/Ed25519 public key for request v2, checked against its SSH hash;
  request v1 requires null access.

It contains no SSH private key, token, local path, shell command or authority to
choose additional resources. Extra fields, changed descriptors and conflicting
existing objects are rejected. A lost upload acknowledgement prevents all creates;
cleanup still attempts the original lifecycle's finalization. Existing request,
lease, ledger and resource schemas remain unchanged.

## One shared reconciler

[cloud_cleanup.py](../../../scripts/v51/cloud_cleanup.py) takes a selected provider
configuration and storage/API connection. It reads the lease from the configured
bucket; the caller does not supply a replacement lease or request. It delegates
to [cloud_runner.reconcile](../../../scripts/v51/cloud_runner.py), with a provider
factory invoked only after the existing expiry and operation-grace check.

| Retained state | Result |
| --- | --- |
| No lease | PASS with no resource operations |
| Active lease or operation grace | WAITING; reads only; no reconstruction |
| Expired lease with no create intent | Finalize/release through the shared path; no provider or SSH context needed |
| Expired lease with attempted creates | Require matching charged request, configuration and immutable context; reconstruct Compute adapter |
| Missing/changed context or reservation | FAIL before any provider/resource mutation; retain lease |
| Original insert pending, missing or ambiguous | FAIL/retain lease for that unresolved resource; never infer final absence or repeat create |

After reconstruction, the existing algorithm resolves original create operation
IDs, validates ownership and complete resource shape, persists discovered IDs with
a lease generation condition, deletes by numeric resource ID and verifies absence.
It retains cleanup/completion evidence, appends a terminal ledger event and releases
the lease only when cleanup succeeds. A reused resource name cannot authorize a
delete of another ID. A completed interrupted attempt remains FAIL and keeps its
charge; successful cleanup does not retroactively qualify the workload. An
already retained completion and terminal ledger event are preserved.

Manual and scheduled triggers execute this same code. Neither bypasses expiry,
graces, identity checks, ledger accounting or generation conditions. A lease CAS
conflict prevents subsequent resource deletion under that stale lease generation.
The reconstruction seam also rejects a live/unqualified adapter.

## Qualification and scope

The existing provider gate runs the new tests and fresh-process qualification:

```bash
scripts/verify-v51-phase6-cloud-provider.sh
```

Fourteen offline cases cover no lease, active/grace, expired schedule/manual,
empty reservation, missing/changed context, missing reservation, lost insert ACK,
pending/missing operation, reused name and delete denial. Each child starts with
serialized provider/storage bytes and a new adapter. It receives no original
runner, provider instance or private key. Input state, HTTP method/path/query/body
hashes, output state and receipts are retained under the existing provider CI
artifact's `cleanup/` directory. The explicit `offline-replay` command is a fixture
replayer, not a native cleanup entry point.

Additional regressions cover configuration/SSH drift, extra private-key fields,
context generation races, lease CAS conflicts, operation resolution on a later
reconciliation, existing completion preservation, public-only retention, and
context publication/acknowledgement ordering. Separate manual and schedule runs
must issue the same Compute operations.

Receipts remain `offline-provider-cleanup`, `paidCloud=false`,
`cleanupReady=false`, `fullRemoteQualification=false`. The real HTTP mutation
barrier, adapter execution guards and disabled identity proposals remain in place.
The checks qualify reconstruction through HTTP request adapters against a local
server double. They do not establish native GCP permissions, operation retention,
IAP/mount behavior or unattended cleanup availability. Missing provider operation
history remains unresolved; no name-only fallback is introduced.

## Next integration

Apply disabled identities only after separate authorization; review native
request/admission schemas and the workflow/credential transition; qualify native
provider reconciliation and SSH/mount delivery; then implement and review the
separate scheduled/manual cleanup workflows and activation. Fresh exact-source
cleanup evidence and all remaining admission checks precede user-triggered paid
experiments. This batch does not close Phase 6C or authorize cloud allocation.

The next [native authority and HTTP policy candidate](PHASE_6_NATIVE_CLEANUP.md)
shares these reconciliation invariants while requiring distinct native records.
It remains offline-only and does not activate provider mutations.
