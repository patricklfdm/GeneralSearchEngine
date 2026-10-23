# V5.2 hosted canonical shards — local standby

## Status and scope

Prepared locally on `feat/v52-canonical-shards-ready`, based on deployed source
`fd3f87581db451ca294c0cb0c74d0f98f791ec98`. This candidate has not been pushed or
used for paid execution. The operator will first inspect the existing five-part
failure-drill results before deciding whether to adopt it. The current v2 master,
prepared plans, sequence and running jobs are not changed by this local work.

Each canonical repetition becomes three fixed **2+2+1 whole-history** executions:

| Suffix (each of repetitions 1, 2, 3) | Complete histories | Reads incl. setup | Updates | Nominal M01 seconds |
| --- | --- | ---: | ---: | ---: |
| `legacy` | Published V5.1 legacy strong + candidate legacy strong | 3,602 | 360 | 360 |
| `explicit-stale` | Candidate explicit strong + candidate stale | 3,602 | 360 | 360 |
| `minimum` | Candidate minimum | 1,801 | 180 | 180 |
| One logical canonical repetition | Five modes | 9,005 | 900 | 900 |

For example, repetition 1 uses `canonical-1-legacy`,
`canonical-1-explicit-stale`, and `canonical-1-minimum`. Repetitions 2 and 3 use
the same suffixes. The suffix groups are fixed, not user-supplied history subsets.
The legacy pair keeps the published comparison together; minimum gets a separate
unit. This is a conservative grouping, not a measured optimal load balance.

Together with experiment and the existing five drill shards, the v3 suite needs
**15 original executions for five logical members**. It keeps exactly 33 histories
(28 formal), 27,428 reads, 2,760 updates, 2,700 nominal M01 seconds and all 439
formal negatives per replay location. The machine/local cohort plan is unchanged.

## Indivisible history and acceptance

Every M01 history retains its continuous 60-second warmup and 120-second measured
window, 1,980 offered calls, original initial strong read, 125-second response
observation allowance, session, lease and bootstrap. No window or live history is
split. Every shard owns a fresh three-host topology, request, original run/attempt,
resource identities, evidence retention, exact-ID cleanup and cost reservation.

`verify-set` restores and authenticates all fifteen originals. It independently
replays the original physical/history/query/resource evidence and negatives, and
still runs all fifteen M01 cross-repetition compiled-consumer/artifact/profile/
outcome checks. A missing shard, changed source/build/sequence, reused identity,
partial history or failed attempt cannot qualify. Individual shard success alone
is not a complete canonical or cloud-set PASS.

Execution remains serial: `v52-native-runner`, one active lease and one complete
history at a time. Any shard may start first. A failed shard can receive a new
approved attempt after cleanup; other complete successes can be retained only
within the same exact source/sequence/build. Business operations are never retried
or reconstructed from fragments. Existing finite transport retries are unchanged.

## Host choice, time and costs

`execution_host=github-hosted` accepts the five drill and nine canonical shards.
Prepare may use either host. Experiment and final `verify-set` still use the
existing self-hosted route; this change does not split or skip final independent
replay. Workflow path, `runner` job, environment, WIF identity, approvals and
artifact contracts are preserved. The workflow's only edits are input descriptions.

Splitting reduces the amount of work that must finish in one hosted job. It adds
six canonical topology/setup/retention/cleanup cycles across three repetitions, so
total time and GCP cost may increase. Reservations are estimates, not invoices.
There is no current-source GCP canonical end-to-end timing for these units, and no
claim that every unit is guaranteed to fit six hours. The first adopted shard must
measure setup, complete histories, retention, cleanup and peak disk separately.

Time and cost remain soft warning budgets. GitHub's hosted job ceiling remains
360 minutes, an external hard limit. The existing minute progress/free-disk report,
four-hour warning and 4 GiB admission floor remain; the floor is not a worst-case
capacity guarantee. An interrupted job must still be reconciled through the
original lease/expiry/grace and exact-resource-ID checks.

## Adoption and historical boundary

Do not dispatch this branch while evaluating the current failure-drill sequence.
If the operator elects to adopt it:

1. Review the retained drill timing/failure evidence and this local candidate.
   Incorporate any later master fixes before committing and validating the source.
2. Push/merge only on explicit instruction; then obtain the exact new master
   **V5.2 Cloud Build** and successful manual cleanup. Prepare from that source.
3. Create a new sequence for v3. Review each shard's estimate and prepare/approve/
   run it separately using [the operator entry](PHASE_6_OPERATOR_ENTRY.md).
4. Preserve successful original request hashes and run/attempt pairs; complete all
   fifteen units and invoke the unchanged independent `verify-set` entry.

The exact v1 and v2 plans are retained for old ledger accounting and lease cleanup.
Their prior charges stay in the append-only ledger; active leases still WAIT and
expired leases use original resource identities. New v1/v2 allocations reject.
This compatibility does **not** let a v2 success fill a v3 selection. In particular,
successful failure-drill units from today's source cannot automatically be joined
with canonical units from a later source. No cross-source exception is introduced.

## Local validation and rollback

The regression suite checks complete grouping, all-start orders, missing/altered
units, original totals, compiled-consumer and invocation checks, v1/v2 frozen bytes,
retained costs, active/expired leases, native exact-ID cleanup on a simulated
provider, hosted routing and workflow generation. It does not perform paid work,
rerun long JVM measurements, or establish hosted timing.

Before any v3 reservation exists, rollback is simply declining this local candidate
or reverting its source change before adoption. After v3 reservations exist, do
not restore a reader unable to parse those requests: retain v3 historical
validation/accounting/cleanup and migrate only after active leases are reconciled.
Never reset charges, rewrite old evidence, or relabel a successful history.
