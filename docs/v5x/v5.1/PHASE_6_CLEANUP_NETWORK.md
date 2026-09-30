# V5.1 Phase 6C3C28 — scoped cleanup network transport and entry

**Status:** implementation candidate on top of PR #262, master
`569582e7a3df9847d7525f566ba9e4f5088cddbd`. Corrected-source protected CI is
pending. The [disabled identity staging](PHASE_6_CLEANUP_ACTIVATION_REVIEW.md)
remains complete; no account, pool or provider is enabled by this change.
No workflow is deployed or dispatched, and no GCP resource is touched.

## One cleanup policy, separate network execution

[NetworkCleanupApi](../../../scripts/v51/cloud_native_cleanup.py) connects the
existing native cleanup policy to the bounded HTTP/token implementation. The
policy checks every method, URL, body and generation **before acquiring a token**.
It retains the same expiry plus grace boundary, original insert-operation lookup,
exact numeric resource ID, ownership/configuration checks, conditional lease
updates and immutable terminal records as offline replay.

The generic [HTTP API](../../../scripts/v51/cloud_http.py) still rejects network
POST/DELETE. There is no `live`, `force`, endpoint or token-supplier argument that
opens its mutation path. The specialized class uses only `NetworkCredentials`
and the normal HTTPS transport. Its execution tag is `gcp-v51-native-cleanup`;
shared cleanup accepts that tag only on the concrete scoped API and native
GCS/Compute adapters sharing that API. Assigning a tag to a generic adapter does
not authorize it. The paid runner continues to reject this cleanup adapter.
These are API invariants, not a sandbox against an actor able to edit Python code
or use the service-account credential outside this entry.

The [shared reconciler](../../../scripts/v51/cloud_runner.py) remains the only
resource-cleanup implementation. It reads the retained lease, ledger and attempt
context, resolves original operations and deletes by ID. A lease that has not
passed expiry plus grace returns `WAITING`. Failed or ambiguous deletion retains
the lease; later reconciliation observes provider state before deciding what is
still needed. Failed-attempt charges are preserved. A cleanup may record an
interrupted attempt as `FAIL`; it cannot manufacture a passing engine workload.

## Formal command

The future reviewed cleanup workflow can invoke:

```bash
python3 -m scripts.v51.cloud_cleanup_entry reconcile \
  --trigger manual --source "$GITHUB_SHA" --output target/v51-cleanup/run
```

The scheduled entry uses `--trigger schedule`. This is documentation of the
implemented command, **not an instruction to activate or run it now**. Current
inactive workflow proposals still stop at `activation-check`.

The command independently checks the current Git checkout, repository and owner
IDs, exact master workflow/event/environment, source SHA and run attempt. It
re-observes the GitHub run before any credential or provider request; a previously
saved observation or binding file cannot substitute for that check. It does not
require a passing paid run or green CI to clean up an expired lease.

The only credential file is the pinned auth action's `GOOGLE_GHA_CREDS_PATH`.
The file must be absolute, regular, non-symlink and at most 128 KiB. Its parsed
contents must match the [existing exact descriptor contract](PHASE_6_CLEANUP_CREDENTIALS.md).
Ambient ADC, a gcloud account, executable credentials and caller-selected
accounts/providers remain unavailable. The network exchange shares the existing
OIDC claim checks, STS exchange, exact-account impersonation, expiry refresh and
original request deadline with offline qualification. Redirects remain forbidden.
GET can refresh once after 401; each mutation is submitted once, including 401
and a lost response. Tokens and provider response text are not copied into errors.

`PASS` and `WAITING` return exit 0. Entry, credential or reconciliation failure
returns exit 2 with a sanitized receipt/summary when the output can be created.
An existing output directory is rejected; its receipt is not overwritten. The
command accepts no resource list, force switch, clock override, configuration
file or credential endpoint override.

`credentialExchangeCompleted` records only completion of the exchange. It does
not establish effective inherited IAM or approve activation. `identityAuthenticated`,
`effectiveIamQualified`, `activationAllowed`, `cleanupReady`, `paidCloud` and
`fullRemoteQualification` remain false in this implementation candidate's entry
receipts. Provider execution tags identify the code path, not qualified cloud
evidence. A local fixture receipt must never be promoted into paid readiness.

## Network and failure qualification

The [loopback TLS qualification](../../../scripts/v51/cloud_cleanup_network_qualification.py)
runs the production command in fresh child processes. A test-only connection
adapter maps the fixed GitHub/Google hosts to a local HTTPS server with a throwaway
certificate. The production urllib request/framing, TLS verification, redirect
handler, credential exchange, policy, GCS/Compute adapters and reconciliation all
execute. Credential descriptors and TLS private keys remain temporary and are
removed when the fixture exits. No production flag or environment variable can
select this test connection adapter.

The server implements the existing offline issuer/provider model. Consequently
this validates network mechanics against controlled responses, **not Google's
signature authentication, real operation semantics, effective IAM or availability**.
Every aggregate receipt is labeled `loopback-tls-native-cleanup`,
`network=loopback-only`, with readiness/activation/paid flags false.

The 64 executions cover both manual and scheduled entries:

- All fourteen retained-state cases: no lease, active/grace, expired cleanup,
  empty reservation, missing/changed context, missing reservation, lost insert
  acknowledgement, pending/missing operation, reused name and denied deletion.
- Denial at all four credential/provider stages; redirects at each stage;
  oversized credential/provider bodies; malformed provider JSON/resource fields; untrusted TLS
  certificate and hostname mismatch.
- GET 401 refresh, mutation 401 without replay, lease generation conflict, and
  a lost successful delete response followed by fresh reconciliation.

The parent independently checks final state, preserved charges, exact-ID deletes,
read-only blocked paths, matching manual/scheduled Compute requests, exit codes
and absence of secrets. Forbidden redirect connection attempts are separately
counted so fixture routing rejection cannot mask a missing redirect guard.
The eleven additional unit regressions cover generic API/runner barriers, scope before
credentials, descriptor files, fresh entry validation, original deadline/expiry,
non-overwrite behavior, cancellation diagnostics and provider-field redaction.
Network cleanup errors retain phase/type only, including errors caught inside the
shared reconciler and uploaded to GCS; invalid provider fields cannot be echoed
through conversion exceptions. Offline diagnostic messages remain unchanged.

```bash
scripts/verify-v51-phase6-cloud-provider.sh
```

The existing provider CI lane runs these checks and retains the full evidence
alongside the original fake/native/offline-entry matrices and local guest checks.
The new TLS matrix has its own 300-second process ceiling; existing workload,
lease, budget and request timing parameters are unchanged.

## Next boundary

After corrected-source CI, prepare the exact cleanup workflow/identity activation
review, including the unresolved inherited IAM observations and real-provider
qualification/failure evidence. Keep the runner disabled while transitioning the
observer workflow path. Live cleanup activation remains separately authorized.
Fresh manual **or** scheduled cleanup evidence then contributes to admission;
remaining native workload integration, pricing and exact-request confirmation
still precede user-triggered paid experiments. Full Phase 6 remains open.
