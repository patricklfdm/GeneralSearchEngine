# V5.1 Phase 6 — single-disk preparation and object probes

**Status:** implementation candidate; local/offline qualification only. No resource,
control object, canary or permission change has been made on Google Cloud by this
batch. Protected CI, current regional pricing, exact fixture approval and actual
manual runs remain required.

## Accepted basis

PR #275 accepted the [single-disk plan](PHASE_6_CLEANUP_FIXTURE.md) and USD 200
cumulative ceiling at master `35befc9adf41bf90520099721354632ff429bebf`.
[CI 36963053297](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36963053297)
passed all 29 jobs on attempt 2. This does not qualify the new driver or substitute
for real deletion/conditional object checks. The earlier manual empty-path evidence
remains historical; its freshness is not extended.

## Components and scope

| Component | Behavior |
| --- | --- |
| [Fixture driver](../../../scripts/v51/cloud_fixture_driver.py) `review` | Read-only control observation, exact request/price/operator/public-key binding, create-only local output |
| Fixture driver `prepare` | One operator-approved 100 GiB `n1-data` disk; native lease/context/ledger, two fixed canaries and a probe manifest |
| [Object probes](../../../scripts/v51/cloud_object_probes.py) `run` | Actual manual workflow identity; create/read one attempt canary and probe five forbidden actions with generation guards |
| Object probes `observe` / `review` | Independent GET-only collection and byte/generation comparison |
| [Manual workflow](../../../.github/workflows/v51-manual-cleanup.yml) | Optional `object_probe_request`; empty input runs the existing permission precheck and expired reconciliation |

The runner and scheduled identities stay disabled. No VM, boot disk, firewall,
grant or organization permission is added. The preparer uses a separately reviewed
operator account; it does not enable the runner or grant Compute creation to the
manual cleanup identity. Generic live HTTP remains read-only. The new network
writer is scoped to the exact preparation sequence and cannot enter the paid runner.

## Reviewed request and live entry

The local package binds source, exact configuration, operator account, native
request, public SSH-format descriptor, original lease/ledger observation, prices,
qualification manifest and USD 1 reservation. Its native request has a dedicated
sequence/attempt and `experiment` member, with no engine workload. The full package
has at most a 15-minute approval window. It is never synthesized from uploaded
offline fixture records.

`prepare` requires the complete package digest, clean tracked implementation and
exact master source, successful latest exact-source CI, matching configuration and
manual workflow bytes, fresh explicit manual configuration audit, unchanged empty
lease/ledger state and the approved active operator account. Tokens are requested
for that account; ambient impersonation, credential-file and access-token overrides
are rejected. Generation conditions are rechecked against live state; a stale
approval never overwrites another attempt. The script does not dispatch GitHub.

Two hashes serve different purposes:

| Hash | Usage |
| --- | --- |
| `fixtureSha256` | Operator confirmation of the entire reviewed package via `prepare --confirm` |
| `requestSha256` | Native request identity; optional Manual Cleanup input selecting the retained probe manifest |

## Mutation order and uncertain responses

The executor and its HTTP policy share this fixed sequence:

1. Verify absent lease, unchanged ledger, absent fixed objects, disk name and original operation.
2. Acquire the lease with generation-match 0; append the USD 1 reservation to the observed ledger generation.
3. Retain exact cleanup context and create/read back the fixed existing/outside canaries.
4. Persist and read back only `n1-data` as attempted within the unchanged 13-row inventory.
5. Submit one disk insert with the original deterministic requestId, inspect its operation and numeric ID.
6. Retain the numeric ID and create/read back the probe manifest, including the full reviewed package and prices.

Every object write is conditional and read back. Wrong order, altered body,
generation drift and additional resources are rejected. Any failed/uncertain write
stops this executor. There is no mutation retry, compensating delete or ledger reset.
The preparation HTTP deadline is five minutes; it does not extend the native
5400-second lease or 1080-second grace.

A lost insert response can leave a real disk with an attempted row and unknown
retained ID. Preserve the receipt and original operation. The existing manual
expired reconciler resolves that operation after expiry/grace; do not rerun
`prepare` or improvise a name-based deletion. If preparation stops before its first
create intent, the existing reconciler can finalize the empty inventory after
expiry/grace without a Compute context. Once an attempted row exists, missing or
invalid context/reservation prevents provider reconstruction and retains the lease
for investigation. Failed charges remain recorded.

## Object probe entry and evidence

Manual dispatch accepts only the optional native request SHA-256. Shell handling
uses an environment variable and quoted argument. The probe entry verifies actual
workflow/source/run/attempt/environment identity, reviewed workflow bytes and the
same-run successful permission precheck before using the bound renewable
credentials. Its request must identify a retained manifest and one active prepared
data disk with a pending reservation.

The canaries have deterministic, non-user-selectable keys:

- `control/attempts/<request>/canary-existing.json` and `canary-created.json` beneath the V5.1 suite prefix.
- `v5.1-cleanup-qualification-canaries/<attempt>/outside.json`, outside that control prefix in the same bucket.

Preparation creates the existing/outside objects. The manual identity creates the
third object once and reads it, reads the existing object, then probes overwrite
and deletion of the existing object and read/write/deletion of the outside object.
All negative mutations use `ifGenerationMatch=0`. Only HTTP 403 is the specified
denial result. HTTP 412, authentication errors, missing objects, throttling and
service failures are inconclusive; unexpected success stops the run. The tested
identity cannot choose another bucket, path, control record, resource or body.

`PROBES_RECORDED` still requires the independent reader to confirm unchanged
existing/outside bytes and generations, the expected new object, and the unchanged
manifest. `OBJECT_SCOPE_MATCH` describes that comparison; it leaves
`objectPermissionsQualified`, `cleanupReady` and `paidAdmission` false. Associate
the original GitHub artifact with its exact source/run/attempt and inspect provider
principal/operation audit evidence before accepting real-path qualification.

Probe results are single-use. If the created canary already exists, the entry fails
before another write; it does not turn a partial first execution into a fresh PASS.
Use an empty-input manual cleanup to reconcile the existing lease when eligible.
Retain canaries/context/receipts as evidence for at least thirty days. GitHub's
existing artifact retention is fourteen days, so archive the original artifact
before it expires. This driver does not delete these objects or change bucket
lifecycle rules.

## Prices and operator execution

The reservation is USD 1 under the USD 200 cumulative ceiling, with prior charges
preserved. `prices.json` must contain the following reviewed inputs. There are no
built-in current-price numbers or live-price claims:

| Field | Bound |
| --- | --- |
| `observedAt`, `expiresAt` | UTC seconds; valid now, at most 24 hours apart |
| `region`, `diskType` | `us-west4`, `pd-balanced` |
| `diskMicrousdPerGiBHour` | Positive integer regional rate, rounded conservatively if necessary |
| `pricedThroughSeconds` | At least 6480 and at most 86400 seconds; include the planned operator wait |
| `otherCostsMicrousd` | Positive allocations for `requests`, `retention30Days`, `actions`, `failureOverhang` |
| `sources` | Reviewed official Google Cloud / GitHub documentation URLs |

The ceiling-rounded disk allocation plus other costs must fit USD 1. The input is
an operator-reviewed estimate, not an authenticated price quote or hard spending
cap. Retain the regional SKU, request/object inventory and overhang basis alongside
the package. Inability to stay available through cleanup postpones allocation.

After protected merge, prepare only the review package first:

```bash
python3 -m scripts.v51.cloud_fixture_driver review \
  --operator "$APPROVED_OPERATOR" --public-key "$PUBLIC_KEY_FILE" \
  --prices "$REVIEWED_PRICES_FILE" --output target/v51-fixture-request
```

After separate approval of those exact bytes, the operator can execute:

```bash
python3 -m scripts.v51.cloud_fixture_driver prepare \
  --request target/v51-fixture-request/request.json \
  --confirm "$FIXTURE_SHA256" --output target/v51-fixture-preparation
```

The user triggers/approves Manual Cleanup with `object_probe_request` set to the
prepared native request SHA-256 while active. Download the original artifact,
independently observe/review its retained `manifest.json` and `receipt.json`, and
bracket subsequent empty-input grace/expired runs with the existing cleanup
observation tool. The preparation receipt records exact `expiresAt` and
`cleanupEligibleAt`; at least 108 real minutes must pass before expired cleanup.

```bash
python3 -m scripts.v51.cloud_object_probes observe \
  --manifest "$PROBE_ARTIFACT/manifest.json" --output target/v51-probe-after
python3 -m scripts.v51.cloud_object_probes review \
  --receipt "$PROBE_ARTIFACT/receipt.json" \
  --after target/v51-probe-after/receipt.json --output target/v51-probe-review
```

## Qualification boundary

The offline HTTP qualification retains three full chains: preparation/probes/
active/grace/expiry, lost insert response followed by original-operation cleanup,
and inconclusive 412 followed by safe expiry cleanup. It checks one insert, exact
scope, unchanged protected state and retained FAIL accounting. Unit negatives
cover malformed/stale packages, write order, conflicts, credential-entry guards,
probe outcome classification and independent state tampering.

Local validation passed the complete preflight gate (131 tests, 61 existing
preflight/identity/permission negatives, eight existing single-disk cases and the
three new chains). The final focused driver suite passed all 15 tests, including
independent rejection of altered identity/canary records. Receipts and source-file
hashes are indexed at `target/v51-cleanup-fixture-driver/validation-summary.json`.

Actual regional pricing/approval, operator allocation, workflow credential probes,
resource deletion, retained failure recovery and provider audit evidence are still
open. Instance/firewall and scheduled-identity qualification are separate remaining
work. A successful local receipt cannot authorize cloud execution or close Phase 6.
