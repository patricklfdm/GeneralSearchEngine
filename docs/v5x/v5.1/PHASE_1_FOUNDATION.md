# V5.1 Phase 1 independent foundation

**Status:** implemented locally; protected Phase 1 acceptance pending.
**Implementation base:** `31b70d08b509ac75037a8eb6386780affc353ed9` (Phase 0, PR #184).
**Authorization:** user instructed “继续下一批” after merge and branch synchronization.

## Delivered boundary

All ten active reactor/example/consumer coordinates are `5.1.0-SNAPSHOT`. The ten
[accepted public types](API_FORMAT_AND_COMPATIBILITY.md#additive-public-surface) are
present as declarations with finite constructor validation. Configured-mode types,
constants and fixtures retain their published meanings. Automatic `build` and all
six storage operations throw NOT_READY / NOT_APPLICABLE before codec callbacks,
filesystem access or any runtime construction. There is no automatic handle whose
inherited default method could accidentally bypass this gate.

The exception and pure configuration/status records are usable; actual automatic
bootstrap, start, election, replication, read barriers, backup and cleanup are not
implemented. The external consumer compiles all these lifecycle/read overloads,
and executes only the seven disabled entry checks. No proxy or private worker
stands in for an enabled automatic engine.

## Foundation and acceptance map

| Area | Implementation / evidence |
| --- | --- |
| Additive API | [Public inventory](../../../general-search-engine-replication/src/test/resources/compatibility/v51-automatic-public-api-v1.txt), [154 declaration signatures](../../../general-search-engine-replication/src/test/resources/compatibility/v51-automatic-public-signatures-v1.txt); V50 fixtures retained, full old+new public surface checked separately |
| Published controls | [Pinned hashes](published-controls.json); independent Central downloads of V4.4 core and V5.0 core/replication, isolated class-loader comparison and published-to-current binary consumer |
| Storage/wire | [Complete catalog](PHASE_1_FORMAT_CATALOG.md); 25 storage/19 wire positive projections, recomputed-checksum semantic negatives, nested manifest/proposer/voter checks |
| Logical protocol | [Model](../../../scripts/v51/model.py), separate [event oracle](../../../scripts/v51/history.py), [bounded scheduler](../../../scripts/v51/explore.py), explicit traces and corrupt-history negatives |
| Read/atomicity oracle | [Small-history search](../../../scripts/v51/linearizability.py): atomic map writes/reads, real-time ordering, unknown inclusion/omission and proven-not-submitted exclusion |
| Process scaffold | [Worker](../../../scripts/v51/process_worker.py), [controller](../../../scripts/v51/process_harness.py): three simultaneous PIDs; 30 cut/method cases; fsync ordering, halt/SIGKILL, pre-reopen bytes and actual exits |
| External consumer | [Automatic consumer](../../../scripts/v51/java/AutomaticConsumer.java), [published API comparison](../../../scripts/v51/java/PublishedApiCheck.java), published-5.0-compiled legacy binary runner |
| No-GCP plan | [Fake plan/reconciliation](../../../scripts/v51/cloud_plan.py): three concurrent voters, 24 vCPU/450 GiB projection, bounded lease/grace and supplied cost envelope, active-lease WAITING and exact-ID negatives |
| CI | [Foundation verifier](../../../scripts/verify-v51-phase1-foundation.sh) runs after reactor package; always retains failed and successful evidence. Existing configured-mode, compatibility, packaging and Required gates remain enabled. |

## Exact qualification scope

The deterministic model uses three fixed voters, proposer-ranked epochs, one unresolved
slot per voter and separate promise, accepted value, chosen proof and published cut.
Durable actions are atomic logical transitions; physical write/force/ACK splits belong
to the separate fixture-process scaffold. A campaign is retired on proposer restart;
old replies cannot resume it. Accepted entry identity remains unchanged on re-proposal.

Two exhaustive explorations start from (a) competing candidates on empty genesis
and (b) a three-slot proven prefix with competing later campaigns. Each explores all
message delivery/drop choices through **six transitions**, including reordering:
8,107 distinct bounded states and 16,192 edges per starting state. This horizon is
explicitly limited; it does not exhaust the protocol's arbitrary histories. There
are also 32 reproducible longer seeds (0-31), plus targeted duplicate, quorum-loss,
restart, disk-loss quarantine, read-overlap, accepted-tail and exhaustion schedules.
Failed model traces are retained, never converted to successful summaries.

The event oracle independently checks I01-I08, including force-backed quorum receipts,
selection-to-acceptance binding, preserved chosen values, proof-quorum success,
read invocation/barrier/pin order and finite accounting. The bounded map search is a
separate oracle for histories of at most ten operations; larger inputs reject. Its
query domain is intentionally small. Published V4.4 query/backup comparison and real
automatic workload histories remain obligations of later production/public phases.

The process scaffold covers PROMISE, ACCEPT and PROOF at before-write, after-write,
after-force, before-ACK and after-ACK, using both worker halt and controller SIGKILL.
The other two fixture workers stay alive during the selected cut. This establishes
real process/force/retention plumbing; it is not an automatic three-voter runtime test.
Snapshots/selection/bootstrap cut names and ordering are frozen by the catalog and
Phase 0 evidence matrix; product crash qualification follows their implementing phases.

The no-GCP plan creates only local Python values. Its cost number is an input ceiling,
not current pricing or paid admission; its topology is a projection, not a fresh quota
observation. It cannot trigger workflows, obtain credentials, alter the V5.0 ledger or
delete cloud resources. Real authority stays with the existing reviewed preflight and
safe scheduled/manual cleanup. Future paid V5.1 work requires a separate accepted plan.

## E01-E12 foundation mapping

| Evidence | Current foundation coverage | Later implementation obligation |
| --- | --- | --- |
| E01 | Automatic model activation and external lifecycle compilation | Real three-JVM failover with public bootstrap |
| E02 | Competing campaigns, delivery/drop exploration, duplicate schedules | Real timer/transport liveness under declared stable conditions |
| E03 | Old-leader read/write fencing, overlapping pin history | Asymmetric partitions and delayed real replies |
| E04 | Ranked epoch/restart/promise exhaustion; five promise process cuts | Actual store torn-write/force and incarnation recovery |
| E05 | Lost entry/proof replies, quorum-before-success oracle; accept/proof process cuts | Product apply/publication/response crash boundaries |
| E06 | Highest-acceptance recovery including origin/acceptance difference; chosen-tail negative | Lagging public candidate and independently inspected authority |
| E07 | Complete catalog for image/basis/selection/floor, checkpoint accepted-tail rejection | Actual snapshot install/generation deletion and pinned rebuild cuts |
| E08 | Retained-disk restart and lost-disk quarantine model | Repeated public failover, operator new-group backup transition |
| E09 | New read barrier/pin ordering and bounded map history search | All real query/rank/page/explain/highlight methods and cursor truth |
| E10 | Conservative declared outcomes, retired campaigns, bounded queues, disabled public guards | Callback/cancellation/deadline/close races in the actual façade |
| E11 | Queue/promise/epoch rejection, finite catalog and fake topology | Product memory/IO pressure, metadata capacity and pin reclamation |
| E12 | Mode/version/manifest negatives, frozen API delta, published controls and consumers | Public automatic bootstrap/cleanup with real current artifacts |

A foundation mapping is not a claim that each E scenario has passed against product
code. No production path may use these model workers as a shortcut to public readiness.

## Local validation record

- Reactor: core 549 tests (4 existing skips), replication 179, processor 5; zero failures
  or errors in the run with local loopback networking enabled. The earlier sandbox
  attempt could not open ServerSocket; it is not counted as passing evidence.
- V5.1 Python suite: 24 tests passed. Complete foundation verifier passed; exact counts,
  current artifacts, source diff/untracked hashes and worker traces are retained in
  the local `target/v51-foundation/run.*/evidence/receipt.json` for each invocation.
- Published V5.0 comparison preserved 2,240 declaration lines; additive inventory 154.
  Seven disabled automatic entries passed the external no-file/no-codec check.
- Existing V1-V5 independent consumer verification and V5.0 foundation gate passed,
  including 290 inherited Python tests and the existing crash/fake-cloud qualifications.
- Unsigned release packaging and integrity checks passed for nine JARs. Final local
  documentation/source checks passed; details are in the [checklist](PHASE_1_CHECKLIST.md).
  No paid run or publication was performed.

The root `target` evidence directories are preserved. Local results do not identify
an accepted Phase 1 master commit; record that only after the user merges this batch
and the exact-source CI succeeds.

## Next boundary

Phase 1 acceptance requires review of the new catalog/fixtures and model limits plus
protected CI. Phase 2 will implement automatic durable authority and independently
inspect actual bytes and crash cuts. Automatic network/runtime/public service remains
closed until its owning phases. The user continues to perform commit, push and PR.
