# V5.1 native Runner storage transaction

**Status:** implementation candidate after accepted PR #283 and actual Runner
permission precheck. This batch executes only offline HTTP fixtures. Protected
acceptance and an independently reviewed live storage entry remain pending.

## Scope and authority

The [accepted Runner precheck](PHASE_6_RUNNER_PREFLIGHT.md) establishes credential
exchange and diagnostic project/bucket permission results. It cannot establish
object-name conditions or generation-bound writes. `cloud_runner_storage.py`
implements that next storage protocol against an offline provider with native
request, lease, ledger and completion formats. It uses the existing GCS Store and
the shared expired-owner cleanup, without converting fake records or opening the
fake engine runner to native adapters.

The constructor accepts offline transports only; the same restriction and closed
method/path/body checks apply when calling the base HTTP API. There is no network
adapter, workflow input, cloud configuration change or paid admission in this
batch. No VM, disk, firewall, SSH command or image lookup occurs. Runner roles,
trust and the USD 200 cumulative ceiling are unchanged.

## Transaction and evidence

The offline fixture supplies an independently captured ledger generation/value
and two request-bound canaries: one under the exact attempt prefix and one outside
Runner's allowed control prefix. An absent ledger uses create-if-absent. A present
ledger must match both generation and bytes before lease acquisition.

1. Read absence of the shared lease and the exact ledger baseline. Require absence
   of this attempt's output/completion objects, including a cleanup completion
   left by an interrupted owner that never reached ledger reservation.
2. Acquire the unchanged 5400-second native lease with `ifGenerationMatch=0`.
   All thirteen resource entries stay unattempted. No cleanup context is needed
   because there are no resources to inspect or delete.
3. Append the reservation using the observed ledger generation; do not reset or
   discount prior charges. The fixture uses a synthetic USD 1 reservation after
   an earlier USD 2 failed attempt. This is not a current cloud price estimate or
   authorization for a real USD 1 write session.
4. Create and read back an immutable attempt canary; read the existing canary.
   Probe denied overwrite/delete of the existing object and denied outside
   read/write/delete. Existing-object mutations use their **actual generations**.
   Only 403 counts as a permission denial. 412, 404, authentication/transport
   errors and unexpected success all fail the session.
5. Retain the storage report and a native **FAIL** completion stating that no
   engine workload executed. A passing storage test cannot advance an experiment
   or canonical sequence as a successful engine run.
6. Append the terminal ledger record bound to that completion, then release only
   the original lease generation and verify absence.

Every original mutation and denied probe is consumed before submission. A lost
response cannot authorize replay. Control replacement, evidence overwrite,
foreign paths/buckets, unpinned reads, duplicate query fields, ledger deletion,
resource-intent changes and premature release are rejected. The original owner
deadline is not renewed between operations.

Successful outer reports remain `offline-v51-runner-storage`, `paidCloud=false`,
`objectPermissionsQualified=false`, `engineWorkloadExecuted=false` and
`fullRemoteQualification=false`. Nested native records retain their native paid
intent fields so the actual native cleanup format can be exercised; those fields
are data, not cloud authorization. Synthetic observations cannot be uploaded as
live qualification evidence.

## Interruption qualification

`cloud_runner_storage_qualification.py` retains initial and interrupted provider
state, original outcome, HTTP calls and source/input digests. It covers healthy
completion, lost responses after lease acquisition, reservation, canary/report/
completion writes, terminal ledger update and lease deletion, plus canary
readback interruption. A failed original submission stays recorded as FAIL even
when subsequent cleanup succeeds.

For each interruption, new Python processes reconstruct the retained state and
run the existing native reconciler at active, grace and exact expiry-plus-grace
boundaries, through both manual and schedule triggers (48 fresh-process checks).
Active/grace owners remain untouched; expired leases are finalized and released.
A lost lease-delete response is independently observed as NO_LEASE. Cleanup
preserves existing attempt evidence and previous ledger entries. A committed
reservation stays charged; a lease acquired before any reservation adds no cost.
No cloud wait is simulated as real elapsed-time qualification. Schedule testing
here is offline coverage, **not a new live schedule prerequisite**.

The existing `scripts/verify-v51-phase6-cloud-preflight.sh` gate runs the tests and
nine-case qualification and retains evidence under its existing upload directory.
No CI lane or additional Maven build is added. For a focused local run:

```bash
python3 -m unittest scripts.v51.test_cloud_runner_storage
python3 -m scripts.v51.cloud_runner_storage_qualification target/v51-runner-storage-check
```

Use a fresh output directory. The unit suite covers policy bypass attempts,
stale/contended control generations, rejected/ambiguous probes, immutable evidence,
readback generation drift, lost-response replay, duplicate requests, budget and
deadline boundaries. Protected CI remains required for this source.

Local validation passed the existing gate components (208 unit tests, 61
source/identity/permission negatives, eight single-disk, five driver and 24
topology cases). Its new readback-loss fixture initially fired on the preparation
absence check; that failed evidence remains retained. The corrected injection
requires the created object to exist. Final focused qualification passed all nine
storage cases and 48 fresh-process checks; all 20 final regressions passed under
Python 3.10 and 3.11. Results and hashes are indexed in
`target/v51-runner-storage/validation-summary.json`. The full wrapper was not
repeated after that fixture-only correction; corrected-source CI remains pending.

## Next live integration

The next entry must bind actual Runner identity/credentials, exact source and
fresh observer/manual evidence to a reviewed request and price/retention plan.
An operator must capture real canary/control generations; a closed network
policy must submit original operations once and retain failures. Independent
post-run reads must verify protected object bytes/generations, append-only
charges, retained evidence and lease absence. Only actual Runner results may
qualify object permissions. Existing manual-identity disk/topology qualification
cannot substitute for that result.

Actual resource/image/IAP access, native owned-workload integration and provider
failure qualification still follow. Paid engine experiments require exact-request
authorization and user dispatch. Manual cleanup remains the primary prerequisite;
waiting for schedule does not block development.
