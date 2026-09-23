# V5.1 Phase 5A: combined faults and repeated retained recovery

**Status:** Batch A accepted at master `04d12316bd6971ac477cfcb08c5073b2252ecf2a`,
[exact-master CI 35818964327](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35818964327),
all 19 jobs passed. PR #209 supplied Batch A; PRs #210–#212 corrected the inherited
CI/test issues encountered before this exact-master pass. Full Phase 5 acceptance
is reviewed in [Phase 5C](PHASE_5_ACCEPTANCE.md), pending that review's protected merge.
The local record below retains its original Phase 4 source. See the
[fixed entry plan](PHASE_5_ENTRY_PLAN.md) and [checklist](PHASE_5_CHECKLIST.md).

## Public execution and independent evidence

Run `scripts/verify-v51-phase5-hardening.sh --skip-build` after reactor package.
The gate checks fresh successful `V51ApplicationRebuildTest` reports, compiles the
existing external public consumer against candidate JARs, then executes all three
scenarios. Each scenario retains the same GroupId and voter directories through
three rounds, without replaying an uncertain mutation or retrying a failed case.
The observer supplies fault injection and raw facts; it does not drive activation.

`hardening_harness.py` records the complete bounded client history, distinct process
starts, exit codes, stop/archive/reopen intervals and per-round resource samples.
Each pre-reopen disk has its own immutable tar, SHA-256 and file inventory. Original
manifest, genesis, node identity and bootstrap authority must survive every round.

The shared physical oracle still independently decodes force records, chosen
quorums, publication bytes and each read barrier; the bounded history checker
includes every attempt, refusal and uncertain result. Explicit validated process
identities permit generations 1–4 in this gate; older gates retain their 1–2 bound.
Additional checks require higher-epoch preservation of each chosen held bulk, new
majority service before killing the isolated owner, sequential acknowledged-prefix
preservation and a new read/write after every restart. Before each round drains,
all three current processes must retain a raw proof or installed recovery prefix
through the final acknowledged bulk. Followers are checked for retained authority;
only ready leaders publish query views.

Read-only resource observations must match raw per-process trace rows. Each round
ends with zero pending work, queued deadlines and ordered work and all four public
admission permits available. Transport admission and release records are counted
per PID with the existing frame/inbound/per-peer limits. Only a recorded SIGKILL
can destroy bounded outstanding reservations; graceful owners must release all of
them. A later generation cannot release an old process's reservation.

Negative evidence removes/reorders rounds, changes process generations or owner
intervals, borrows an archive, removes a voter sample or its durable prefix proof,
leaks a timer, drops a prior
prefix, removes an original durable acceptance, fabricates delivery of the held ACK
or claims successful uncertain/minority service. Every variant must be rejected.
This is finite local combined-fault evidence, not a long-duration or cloud result.

## Defect found by continuous recovery

The original `partition-accept-kill` schedule failed in round 2 when the retained
application reached 18 documents. `ReplicaApplication.rebuildApplication` grouped
reconstruction only by `DurableStorageConfig.maxBulkElements` (100 in this fixture),
while the captured `SnapshotEngineConfig.maxBatchSize` was 16. Its internal
`addAll` therefore rejected an otherwise valid committed snapshot with
`BulkMutationException: atomic bulk mutation size 18 exceeds configured maximum 16`.

Private rebuild now batches at the minimum of those two configured limits. Both
private engines are populated before the original application cut is published;
document order, dynamic indexes, index/sequence identity and snapshot bytes remain
unchanged. This shared path serves configured and automatic replication. Client
atomic bulk operations retain their existing size checks and are never split.

`V51ApplicationRebuildTest` covers engine/storage limits 16/100, 100/2, 2/2 and
1/100, including incomplete final batches, changed indexes, exact snapshot roundtrip,
logical publication identity and later writes through both engines. A fifth case
checks that an oversized client bulk still fails without partial publication.
The unmodified implementation failed the 18/16 and 3/1 cases before the correction.

The failing live trace remains at
`target/v51-hardening/dev-accept/partition-accept-kill`, and the pre-fix regression
log is `target/v51-hardening/rebuild-before.log`. They are debugging evidence for
this change, not successful qualification.

## Local validation

The final complete gate passed at
`target/v51-hardening/run.AxhUSQ/evidence/receipt.json`. Runtime/test/workflow source
hashes in its inventory match the final implementation; subsequent documentation
updates only record these results. All failed development attempts remain separate.

| Scenario | Consecutive rounds | Runtime JVMs | Pre-reopen archives | Attempted public calls | Rejected evidence variants |
| --- | ---: | ---: | ---: | ---: | ---: |
| `partition-accept-kill` | 3 | 6 | 3 | 28 | 17 |
| `partition-proof-kill` | 3 | 6 | 3 | 28 | 17 |
| `whole-group-restart` | 3 | 12 | 9 | 22 | 15 |

- Full reactor package: 862 tests, 858 passed, 4 skipped, zero failures/errors;
  includes all five rebuild regressions and existing configured/automatic recovery tests.
- Final V5.1 Python discovery: 232 tests passed, including 12 new schedule/accounting tests.
- Foundation gate: independent model, format/negative checks, 42-document contract passed.
- CI classifier/topology/Required tests: 17 passed; 13 jobs, 107 shell blocks and
  36 unique artifact names checked. Existing lanes remain required.
- Whitespace, changed Python/shell syntax and Markdown local-target checks passed.

Summary: `target/v51-hardening/validation-summary.json`; logs: `reactor.log`,
`python-final.log`, `foundation.log`, `ci-tests.log`, `qualification.log` in that
same parent directory. CI uploads `target/v51-hardening` as
`v51-hardening-${{ github.sha }}` even on failure. The acceptance record above supersedes the original pending
Batch A status; [Phase 5B](PHASE_5_COMBINED_LIFECYCLE.md) now has its own protected
acceptance and [Phase 5C](PHASE_5_ACCEPTANCE.md) reconciles both on exact-master evidence.
