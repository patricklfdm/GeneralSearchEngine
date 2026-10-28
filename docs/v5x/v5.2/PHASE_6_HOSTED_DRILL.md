# V5.2 hosted failure-drill shards

## Scope and status

This change replaces the single thirteen-history failure-drill execution with
five fixed whole-history units. They run serially on GitHub-hosted Ubuntu jobs;
the global `v52-native-runner` concurrency group and single active lease remain.
No cloud experiment is dispatched by this implementation or its local tests.
Hosted execution and end-to-end retention timing remain to be measured after
merge and the exact-source **V5.2 Cloud Build**.

| Execution name | Histories | Reads | Updates |
| --- | ---: | ---: | ---: |
| `failure-drill-m02-below` | 3 | 93 | 9 |
| `failure-drill-m02-equal` | 3 | 93 | 9 |
| `failure-drill-m02-above` | 3 | 93 | 11 |
| `failure-drill-m03` | 2 | 71 | 8 |
| `failure-drill-m04` | 2 | 8 | 8 |
| Logical failure-drill total | 13 | 358 | 45 |

Every history still owns its original session, roots, group, bootstrap, fault
schedule, read/update outcomes, physical/history/query/resource replay and exact
negative cases. There is no history slicing, workload resubmission or borrowing
successful fragments from failed attempts. Each unit has its own request,
original run/attempt, three VMs, lease, resource identities, immutable evidence,
cleanup and append-only charge. Five shard seals are inputs, not a qualified
logical drill result by themselves.

The v2 deployment has nine original executions and five logical results. The
[local v3 canonical standby](PHASE_6_HOSTED_CANONICAL.md) extends that to fifteen.
With v3, `verify-set` must independently replay all fifteen originals on one source/sequence,
including all five drill shards. Missing/duplicate/foreign units, altered
profiles, reused run/resource/history identities and failed ledger entries reject.
The existing full-set replay remains on self-hosted infrastructure; it is not
silently reduced to trusting uploaded PASS summaries.

## Measured basis and limits

Historical run [39678504498/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/39678504498)
on source `73f3bd5c21c97eee564397ab11af7b66bc1b13a3` executed all thirteen histories
but failed at retention-originals. Its job lasted 6h08m51s. Its complete-history
group times were 72, 73, 78, 49 and 56 minutes, excluding shared setup and final
retention/cleanup. Recent run [39905260525/1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/39905260525)
on `25d1ea8798687f3bc4766f332938fb7194e5761f` observed 86/82 minutes for the first
two groups and failed on OIDC during history eight. The suite/history definitions
are identical across these two sources; transport implementations differ.

The provisional 2–3.5 hour per-shard estimate includes repeated setup and
contingency, but is not measured hosted end-to-end acceptance. Complete final
retention duration is not established by those failed runs. Repeated setup adds
VM time/cost, while successful units can be retained if another unit fails on
the same source. GCP costs still apply; reserved estimates are not invoices.

[GitHub enforces six hours per hosted job](https://docs.github.com/en/actions/reference/limits).
This external ceiling cannot be made soft. The controller does not add a stage
timeout: time/cost overruns warn, finite exchange retries and authority checks
still fail closed. It emits free-disk/progress every minute, warns after four
hours, and requires 4 GiB free before any hosted operation. That floor does not
guarantee worst-case evidence capacity. Watch disk usage and retention on the
first hosted shard. An interrupted platform job may leave a lease for expired
cleanup; never assume an `always()` step alone guarantees cloud reclamation.

## Operator sequence

1. Merge this source, then complete **V5.2 Cloud Build** and manual cleanup on
   that exact master. Normal full CI remains optional under the existing V5.2
   cloud-stage policy. Do not reuse an expired or earlier-source prepared plan.
2. Create one new sequence for the new suite/source. Preserve the old ledger
   and its costs. Existing v1/v2 requests remain readable and cleanable, but cannot
   be newly reserved, allocated or substituted into the v3 acceptance set.
3. Select any shard above. Review a separate estimate covering its three VMs,
   disks, setup, retention, cleanup and prior charges. `prepare-request` accepts
   the same explicit estimate parameters; no automatic pricing claim is made.

```bash
V52_SEQUENCE=$(python3 -c 'import uuid; print(uuid.uuid4().hex)')
python3 -m scripts.v52.cloud_operator prepare-request \
  --source "$(git rev-parse HEAD)" \
  --member failure-drill-m02-below --sequence "$V52_SEQUENCE" \
  --cost-microusd "$V52_ESTIMATE_MICROUSD" \
  --coverage-seconds "$V52_COVERAGE_SECONDS" \
  --output target/v52-drill-request-1

python3 - <<'PY' | gh workflow run v52-replication-evidence.yml --ref master --json
import json
from pathlib import Path
print(json.dumps({"operation":"prepare","execution_host":"github-hosted",
                 "request":Path("target/v52-drill-request-1/request.json").read_text()}))
PY
```

4. Approve the existing `v52-cloud-benchmark` environment. After prepare passes,
   review its summary and submit `operation=run`, `execution_host=github-hosted`
   and its exact `runRequest`. The summary includes the shard name, logical
   member, full history list and recommended execution host.
5. Finish cleanup before preparing another unit. Retain each successful unit's
   request SHA and original run/attempt. A failed unit needs a fresh prepare and
   attempt; never rerun a paid original as an evidence substitute. The other
   completed units may be selected only if source/sequence/build remain exact.
6. Repeat for the remaining shards on the same sequence. Do not dispatch them
   concurrently or pre-create stale approvals/ledger snapshots for all five.
7. With v3, [canonical shards](PHASE_6_HOSTED_CANONICAL.md) can also use hosted
   execution. `experiment` and `verify-set` still require `execution_host=self-hosted`.
   Prepare itself may use either host.
8. The v3 verify-set JSON contains `experiment`, the five exact drill shard names,
   and nine canonical shard names. Old monolithic `failure-drill` or canonical
   names are not executable units. The currently deployed v2 retains its original
   nine-unit selection until the operator explicitly adopts v3.

Workflow path, `runner` job identity, environment, WIF audience and service
account remain unchanged. No new IAM privileges or repository settings are
required by the host choice. Host selection cannot bypass exact-source build,
cleanup, prepared confirmation, private guest ownership or evidence validation.

## Rollback boundary

Revert the orchestration change only after no new-suite lease remains active.
Do not roll old code back onto a ledger containing newer requests: the previous release cannot
parse new shard requests. Retain the v1/v2/v3 reader/cleanup path if new requests have
already been reserved. A new source/suite needs a new sequence and new build;
never move tags, rewrite old receipts, reset costs or relabel failed histories.
