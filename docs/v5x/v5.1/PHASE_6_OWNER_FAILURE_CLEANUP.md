# V5.1 native preparation failure cleanup

**Status:** accepted with the native owned lifecycle through PR #292, master
`20f977e8b5fed5bc5f54f53218c27d7971c2b3d4`,
[CI 37424341468](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37424341468)
attempt 1 (36 successful jobs). The subsequent
[manual entry candidate](PHASE_6_NATIVE_RUNNER_ENTRY.md) has a separate review.
The preceding [guest preparation](PHASE_6_NATIVE_GUEST_SETUP.md) was accepted
through PR #291, master `70b452348832d6c2803870ae1b3ec74409e43ece`,
[CI 37411762406](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37411762406)
attempt 2 (36 jobs). That result does not establish the cause of attempt 1.

## Immediate owner continuation

Native resource/IAP and volume/package preparation now enter bounded owner
recovery after failure, including preparation deadline and local diagnostic-write
failure. This continuation requires the original freshly admitted creation API,
an open mutation gate, a failed preparation and its last authorized lease CAS.
It consumes that in-memory authority once. A copied receipt, request, generic
HTTP API or earlier invocation cannot authorize it.

Before cleanup, it reads the retained lease at a pinned generation and requires
the exact bytes of the original authorized write. This also covers a CAS that
succeeded but lost its reply. It verifies the original ledger baseline or charged
reservation; attempted resources additionally require the retained charge and
exact cleanup context. Changed authority blocks mutations.

The existing shared cleanup algorithm resolves original insert operations,
checks ownership and numeric IDs, persists resolved IDs by CAS, and deletes
instances before disks/firewalls. It never deletes by name, resubmits an insert,
or treats an unknown/pending operation as final absence. An unresolved intent,
replaced resource, denied deletion or lost delete reply keeps the lease.

Manual and scheduled entries still require lease expiry plus the full operation
grace. Their public binding check is unchanged. Active manual reconciliation
remains WAITING even after immediate owner cleanup could not finish. This is not
a force-delete switch or another operator entry.

## Failure evidence and accounting

Cleanup runs before remote diagnostic retention so upload failure cannot prevent
a deletion attempt. A closed inventory collects the original preparation,
admission, resource, IAP and guest setup records, plus the cleanup result and HTTP
trace. It excludes private keys, credential files and arbitrary workspace files.
Each source file is bounded to 8 MiB and the source inventory to 32 MiB. Symlinks
are rejected. A manifest records each file's length and SHA-256.

Objects under the exact attempt's `preparation-failure/` prefix are immutable,
generation-zero uploads, followed by exact pinned read-back. Only verified
evidence permits a native FAIL completion; only that completion permits the
append-only terminal ledger event. No reservation is refunded. If the initial
lease CAS succeeded but no reservation was submitted, recovery does not invent
a charge or ledger event.

Lease release requires confirmed cleanup, retained evidence/completion and the
terminal ledger state. Uncertain uploads/terminal writes preserve the lease.
An independent expired reconciler can preserve an already retained completion
after a lost reply. The original preparation remains FAIL even when its separate
`owner-recovery/receipt.json` reports PASS. Offline qualification receipts stay
explicitly offline; their native-format records represent synthetic attempt intent.

## Time and activation boundaries

The preparation deadline is not extended. Cleanup and validation/retention each
use their existing 600-second allowance, capped by the original owner's fixed
5400-second lease deadline. The 1080-second operation grace and USD 200 cumulative
ceiling remain unchanged. Reconnection or another invocation cannot reset these
deadlines; native HTTP mutations are submitted once, including HTTP 401 replies.

Successful package preparation remains PARTIAL with an active charged lease.
The same PR also connects a separate [native owned experiment entry](PHASE_6_NATIVE_OWNED_EXPERIMENT.md)
for successful preparations. This failure continuation remains restricted to FAIL;
it cannot finish a successful workload. This accepted cleanup change added no
CLI/workflow, cloud execution, IAM change or paid authorization. The subsequent
manual entry is reviewed separately.
Full Phase 6 remains open.

## Qualification

Tests run actual admission, creation, cleanup, CAS, retention and ledger code
against synthetic credential/provider boundaries. They cover lost lease,
reservation, context, plan, intent, insert, identity, delete and completion replies;
IAP/guest failure; authority/resource replacement; missing charge/context; deadline
exhaustion; upload/local-write failure; original evidence hashes and closed scope.
Fresh-process manual/expired replay checks the WAITING boundary and preserved
completion after lost finalization. No GCP resources or engine workload are run.

The suite joins the existing Python storage and focused cloud-storage gates.
Local logs and the PR description are retained at `target/v51-owner-failure-cleanup/`.
Protected CI for this candidate remains required.

## Asynchronous delete wait correction — 2026-10-06

The [first native experiment](PHASE_6_NATIVE_RUNNER_ENTRY.md#first-native-run-and-bounded-readiness-correction--2026-10-06)
showed that a 30-second HTTP request cap cannot also serve as the full lifetime
of a Compute delete operation. The provider now captures one cleanup deadline
before resolving any resource: the existing 600-second allowance, capped by the
native owner's original stage/lease deadline. Reentering cleanup on that provider
does not renew it. A fresh expired reconciler gets its own bounded invocation.

Each DELETE is still submitted once, by exact numeric ID and deterministic request
ID. Only the returned, validated operation is polled. Successful instance deletion
requires operation completion and numeric absence before advancing in the shared
ordered cleanup. Failed deletes remain failures while other resources can still
be attempted. Each HTTP request remains capped at 30 seconds; operation polls,
later resource resolution and absence reads share the remaining cleanup budget.
Exhaustion, failed/lost responses and identity drift preserve failure and the lease.
No error is converted into successful cleanup merely because a later read is absent.

This shared correction covers owner failure, successful-owner final cleanup and
manual/scheduled expired reconciliation. It changes no workload, lease, grace,
IAM, spending limit, mutation replay or active-lease protection. Synthetic tests
keep disks attached while VM deletes take 85.5/56.5/50 seconds, verify once-only
deletes and final absence through owner/manual/scheduled paths, and reject both
whole-cleanup exhaustion and a shorter original owner deadline. Protected CI and
real-provider verification of this correction remain pending.
