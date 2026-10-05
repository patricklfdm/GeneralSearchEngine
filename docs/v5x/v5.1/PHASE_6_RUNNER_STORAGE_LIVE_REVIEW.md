# V5.1 Runner storage live review — 2026-10-05

**Result:** both authorized Runner executions passed all eight object probes.
Original artifact provenance and independent object/control state passed review.
The second execution has seven of eight probe audits observed; one missing audit
remains explicitly unresolved. This is storage evidence, not engine admission.

## Accepted source and original executions

PR #286 merged at `b0bc7b4b9e63a40a1d812138d86cb40e7e298e92`.
[Exact-master CI 37280773489](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37280773489),
attempt 1, passed all 36 jobs, accepting the canonical CLI entry correction and
[Python/cloud CI partition](../../CI_PYTHON_LANES.md). Both runs below used that
source. Their fresh preparations and Runner dispatches were separately authorized.

| Evidence | First successful execution | Audited execution |
| --- | --- | --- |
| Runner, attempt 1 | [37285400939](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37285400939) | [37290067974](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37290067974) |
| Recent manual cleanup, PASS / NO_LEASE | `37283638208` | `37288979457` |
| Original execution interval (UTC) | 08:44:44–08:45:05 | 09:27:56–09:28:17 |
| Original plan expiry (UTC) | 08:46:25 | 09:36:40 |
| Runner result | PROBES_RECORDED, 8/8 PASS | PROBES_RECORDED, 8/8 PASS |
| Independent state | OBJECT_SCOPE_MATCH | OBJECT_SCOPE_MATCH |
| Cumulative reserved USD / ceiling | 15 / 200 | 17 / 200 |
| Terminal attempts / pending / active lease | 7 / 0 / absent | 9 / 0 / absent |

Each transaction retained 33 HTTP requests, including five original HTTP 403
denials. The five metadata HTTP 404s were expected absence checks. Both protected
canaries kept their original bytes and generations; report, completion, manifest
and append-only ledger matched independent observations. All eleven observer
files matched the copies in each Runner artifact. Original native FAIL completions
correctly state that no engine workload ran, despite the storage probes passing.

The earlier `37274475579` failure and its USD 13 cumulative baseline remain
historical evidence. Neither subsequent success resets a failed reservation.
USD 17 is reserved budget, not a measured invoice. All three old plans are expired.

## Retained identities and provenance

| Run | Plan SHA-256 | Native request SHA-256 |
| --- | --- | --- |
| `37285400939` | `a188e12ff46e33b00644211dfe45b45f7ee590a4265503490b679b9e546563b6` | `d37c8a4d12156845d7bbf5727edb036681173ca85dce84a92eef797281d54c8c` |
| `37290067974` | `2a672ab75626331a4cf1455093769712b27c9e883b72a62a2d28a0a1c3e88c88` | `b65b854621ef4450680861d2f9b4fe6f2a3f61c491ac1c66cd9ac26c28bf7f39` |

Original ZIP sizes/digests and run/attempt/source identities matched GitHub
metadata, reread unchanged after download:

| Run / artifact | Artifact ID | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `37285400939` preflight | `11333304942` | 50090 | `77ceee166832c3de09603bbb73f3f46eb12b838102f25a839a31025b40a28017` |
| `37285400939` runner-precheck | `11334248146` | 67599 | `e2ab2f0627cfcb124a500d7b18c972a6c84d82e0021c050214bdf0e9e42e39f0` |
| `37290067974` preflight | `11335689192` | 50839 | `7b81dd59012d22a8030a5d51d0816c316717838d3f22422016871856229609d0` |
| `37290067974` runner-precheck | `11335623078` | 69110 | `619d2c466f4ab87ff5c5a582ecdabf2d26f997aa3f721c2b5ae740f1b36e0d4f` |

Full artifact names are `v51-preflight-<run>-1` and
`v51-runner-precheck-<run>-1`. Original archives, raw observations, replay receipts,
approval hashes and evidence indexes are retained locally under
`target/v51-runner-storage-result/run-<run>/`. Preparation evidence is in
`target/v51-runner-storage-retry-review/` and
`target/v51-runner-storage-audited-review/`. Preserve these before GitHub's
fourteen-day artifact expiry. This tracked record supplies identities and results;
it does not replace the original bytes or turn local files into signed evidence.

## Provider audit coverage and its limit

No object audit was found for the first run. Token-exchange audit rows alone do
not establish object actions. For the second run, the operator separately approved
a temporary project audit configuration enabling Storage DATA_READ/DATA_WRITE.
Actual operator reads verified delivery before the new preparation/dispatch.

The retained second-run window contains 37 Storage records: three observer reads
and 34 Runner records, comprising two manifest reads and 32 of 33 transaction
requests. Matched records bind the Runner service account, exact object, method,
time, result and evaluated permission.

| Probe | Actual probe | Observed provider audit |
| --- | --- | --- |
| create | PASS | MATCH |
| read-created | PASS | MATCH |
| read-existing | PASS | MATCH |
| overwrite-denied | PASS | MATCH |
| delete-denied | PASS | MATCH |
| outside-read-denied | PASS | MATCH |
| outside-write-denied | PASS, original HTTP 403 | NOT_OBSERVED |
| outside-delete-denied | PASS | MATCH |

Repeated fixed-window queries and an all-service query for the denial interval
did not find the outside-write row. Its cause is unknown. The original HTTP 403
and independently unchanged outside canary are retained; a provider logging
limitation, delay or implementation defect has not been established.

Coverage and probe success are separate observations. This review introduces no
new requirement for one audit row per HTTP call and does not require a paid rerun
solely to fill the gap. It claims neither complete per-probe audit coverage nor
broad effective-IAM qualification. The independent aggregate retains
`providerAuditVerified=false`; original `objectPermissionsQualified`,
`paidAdmission`, `engineWorkloadExecuted` and `fullRemoteQualification` stay false.
Historical review does not renew source or observation freshness.

## Audit restoration and next work

The authorized restoration completed at **09:36:51 UTC**, independently returning
`ORIGINAL_AUDIT_CONFIG_RESTORED`. One compare-and-swap request used the current
etag and `updateMask=auditConfigs,etag`; all eleven bindings, including the existing
conditional binding, were preserved. Logs, grants, objects and ledger records
were not deleted. Evidence remains at `target/v51-storage-audit-review/restoration/`.
The temporary project audit addition is no longer enabled.

Next, follow the [Runner resource integration plan](PHASE_6_RUNNER_RESOURCE_ENTRY.md).
Actual Runner resource/image-use/IAP access, native owned workload execution,
provider failure paths and paid admission remain open. Manual cleanup suffices;
schedule remains optional. Future operations need their own current source,
observations, prices and exact-request approval.
