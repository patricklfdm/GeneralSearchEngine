# V5.1 Phase 5A: combined faults and repeated retained recovery

**Status:** Batch A accepted at master `04d12316bd6971ac477cfcb08c5073b2252ecf2a`,
[exact-master CI 35818964327](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35818964327),
all 19 jobs passed. PR #209 supplied Batch A; PRs #210–#212 corrected the inherited
CI/test issues encountered before this exact-master pass. Full Phase 5 acceptance
is recorded in [Phase 5C](PHASE_5_ACCEPTANCE.md), accepted through PR #214.
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

## Post-PR-220 correction: a recovered read does not lease leadership

[Master CI 35927462738](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35927462738)
at `717bed8f578019c71ffe3d739deaf067ec0fa8d2` failed `partition-accept-kill`
in its first round. The other two Phase 5A cases passed. The downloaded original
failure remains under `target/v51-hardening-recovery-race/failed-master`, artifact
`v51-hardening-717bed8f578019c71ffe3d739deaf067ec0fa8d2`, ID `10779324202`.

The physical trace shows a valid leadership race, rather than an ordinary API
latency timeout: node 1 completed the recovered read at epoch 5, then nodes 1 and 3
forced the next bulk (keys 140/141) at index 13. The restarted node 2 returned a
rejection advertising its retained epoch-6 promise. Node 1 received that higher
promise before the proof acknowledgment was processed and conservatively completed
the write as `INDETERMINATE / STALE_EPOCH`. A successful read only qualifies its own
captured cut; it cannot guarantee leadership through a later write. The original
driver incorrectly required that first post-restart write to succeed immediately.

The correction is restricted to the Phase 5A client schedule. After each restart,
allow at most three **fresh** recovery writes, each preceded by a new strong read.
Attempt `a` in round `r` uses keys `100*r + 40 + 2*a` and the following key, with
`a` starting at zero. No uncertain mutation is replayed. Every response remains in
the client history; each receipt records the read/write operation IDs and the
recovery start boundary. The final attempt must actually succeed, followed by a
successful final read and the existing per-voter proof/resource drain checks.

Only the existing conservative availability outcomes permit another fresh attempt:
`NOT_SUBMITTED` with NOT_LEADER, NOT_READY, QUORUM_UNAVAILABLE, STALE_EPOCH or
DEADLINE_EXCEEDED, or `INDETERMINATE` with the last three reasons. Integrity,
storage, capacity, closed, unknown and disconnected results fail immediately.
The next successful read may contain exactly the prior acknowledged projection,
or that projection followed by the entire immediately preceding uncertain bulk.
Partial, changed, reordered or unrelated documents fail. The original independent
physical and history validators still decide whether that observed cut is legal;
the harness does not turn an uncertain response into a successful acknowledgment.

Each read retains the four-attempt limit. The complete history retains its
48-operation / 100000-state bounds, with the operation limit also checked before
dispatch. With first-try reads, the partition cases use at most 40 calls across
three rounds if each recovery needs all three fresh writes; read refusals consume
the remaining headroom. Exceeding any bound fails. Sealed policy, timeouts,
production code, fault cuts and three-round requirements remain unchanged. Shared
Phase 5B lifecycle drivers retain their previous behavior.

Independent recovery checks account for every call between the recorded recovery
boundary and the successful write, enforce distinct predetermined keys, require
only classified failures before that success, and reconstruct the exact expected
projection. Additional evidence negatives remove attempts, replay keys, shift the
boundary or forge the projection. The deterministic regression reproduces the
original STALE_EPOCH failure and covers both chosen and unchosen uncertainty,
exhausted attempts, forbidden errors, invalid projections and history preservation.
Corrected-source protected CI remains required; this does not establish a failover
SLA or eliminate every possible scheduling or storage delay.

### Correction validation

- Original deterministic chosen-write regression fails with the original single-write
  driver; all twelve new driver/evidence tests pass with the correction.
- All 349 V5.1 Python tests pass. Full reactor package: 877 tests, four existing
  skips, zero failures/errors. Packaging identical JAR bytes preserved an old file
  timestamp locally; removing only the generated replication JAR and repackaging
  with already tested classes satisfied the existing freshness check.
- Complete unchanged three-case/nine-round gate passes at
  `target/v51-hardening/run.K3Yo9X/evidence`: accept-cut 28 calls / 21 negatives,
  proof-cut 28 / 21, whole-group restart 22 / 19. All 61 negative variants reject.
  This live run used one recovery write per round; the classified-refusal branch
  is covered by the deterministic regression and the original failed CI trace.
- Documentation contract, changed local links, shell syntax and whitespace pass.
  Local evidence/source hashes and original-failure analysis are retained under
  `target/v51-hardening-recovery-race/validation-summary.json` and
  `failure-analysis.json`. No paid cloud work or production/workflow edit.
