# V5.2 Phase 4 qualification

**Status:** in progress. Phase 4A supplies deterministic and in-JVM public lifecycle
coverage; 4B adds six physical process faults, and 4C1 adds eleven cancellation/close
process schedules. These do not complete S01–S30. Hosted exact-source validation,
the remaining matrix and final hosted acceptance are pending. 4C2 adds the seven
promise/install process cases described below. Follow the
[local commit sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).

## 4A: lifecycle and resource boundaries

`V52ReadLifecycleTest` adds seven controlled-scheduler tests with enumerated variants:

- Zero and positive waits at lower bounds below/equal/above publication; deadline
  expiry with zero callbacks and no replication/application work added by waiting.
- Wrong group/history/manifest before allocation, including P=1 with no read slots.
- P=1/4/65/10000, R=min(64,P-1), Long.MAX_VALUE lower bounds and full release.
- Cancellation and close for ready and behind requests; later progress cannot revive them.
- State/fatal changes after valid capture preserve that captured strong read, while
  rejecting subsequent reads with the actual reason.
- Publication at the exact deadline, including a delayed timer delivery.
- Cancellation while an already-completed Future's handler is still running;
  original ownership remains until the handler actually returns.

`V52PublicReadLifecycleTest` adds four real-TCP public-handle tests:

- P=4: three waiting reads, excess read rejection, and the fourth public slot used
  by the actual write that satisfies all three; final pending count returns to zero.
- Pause one callback while a real update and index create/drop queue behind it.
  Repeated rich query/get/sequence observations remain at one cut. Foreign-thread
  and escaped-wrapper use reject; subsequent publication includes all three changes.
- Carry a strong token across an update and delete. Minimum means history coverage,
  not a promise to return a previous document value.
- Same-handle legacy paging and backup reject during a callback; pure schema,
  leadership and cached durability diagnostics remain available.

These add to the existing queue, worker, application-cut, public-read and protocol
cases. They do not turn the Phase 1 synthetic model into physical evidence.

## Coverage accounting

The normative variants remain in [TESTING_AND_EVIDENCE](TESTING_AND_EVIDENCE.md).
This table records implemented evidence without declaring unfinished variants done.

| Schedules | Evidence available | Remaining qualification |
| --- | --- | --- |
| S01–S03 | Seven consumer modules, old implementation binary/default, stopped/closed checks, seven-query public three-JVM gate for all policies | 4D7 local consumer/API rerun; final exact-source hosted acceptance pending |
| S04–S06 | Actual store/protocol accepted-only tests; 4B public isolation/held-publication physical cases | Include full accepted-only read variants in final matrix |
| S07 | Three-JVM imported sequence four at index zero, fresh strong NO_OP; independent prefix replay | Included in later aggregate |
| S08–S12 | P=4 satisfying write, bounds/deadline/registration tests, 4B delayed follower and 4D1 physical update/delete carried-bound overlap | Final variant mapping |
| S13 | 4D2 public checks for all three identity mismatches before allocation; 4D3 new-group import; deterministic exhausted-capacity precedence | Final aggregate |
| S14–S16 | 4B carried-token halt/SIGKILL; 4C2 verified installed newer prefix; 4D3 actual backup/new-group import; 4D4 actual two-source retirement below carried token | Final aggregate |
| S17–S20 | Higher-PREPARE kernel, state gates and seven 4C2 public promise/install cases including halt/SIGKILL | Remaining isolated-old-leader and candidate/local state variants in final matrix |
| S21 | 4D1 three-policy process traces: pause complete query report, queue seven application mutations, repeat same-cut report, then verify every publication and later V4.4 query result | Final aggregate |
| S22 | 4D7 public cursor continuity, changed materialization, successor/reopened handles; negative page compilation and nested-page rejection | Final aggregate |
| S23–S24 | 4D5 separate-process saturation/counters at P=4/65/10000; 4D6 public P=1 rejection with old-API progress | Final aggregate |
| S25–S28 | Deterministic lifecycle/fairness tests and eleven 4C1 public cancellation/close cases, both crash modes and independent allocation/release accounting | Complete callback/null/reentry and fairness evidence mapping |
| S29–S30 | Seven-method cross-thread/escaped rejection, reentry, token-byte vectors, Long.MAX_VALUE and maximum wait | 4D8 controlled public startup/fatal-I/O tests; final aggregate |
| N01–N16 | Phase 1 synthetic sixteen plus Phase 3B eleven physical/query rejection mutations | Complete sixteen targeted physical mutations, before/after relocation |

## Local verification

The targeted run covers 33 tests: the 11 new tests plus the existing 15 queue,
three application-worker and four application-cut tests. Logs and hashes are at
`target/v52-lifecycle/`. Initial new public assertions incorrectly compared the
SearchResult wrapper by object identity and treated cached durability diagnostics
as a reentrant operation. The tests now compare immutable hit values and preserve
the existing pure-diagnostics contract. The failing run remains retained. No
production logic, workload timing, admission limit or CI check was changed for 4A.

## Next batches

4B implements the public process fault driver described below. 4C1 completes the
cancellation/close process schedules below; 4C2 covers promise/install races. 4D
closes the remaining resource, schedule and negative matrix.
Each batch is locally verified and committed without a push. Phase 5 combined
hardening and Phase 6 frozen local/no-GCP measurements follow only after the matrix
is complete. Paid execution remains outside this authorization.

## 4B: owned process faults and carried tokens

The required carried-read fault lane runs `verify-v52-phase4-public-faults.sh`. It creates
six independent histories, using only public bootstrap/start/mutation/read calls:

1. Halt at REPLICA_READ_CAPTURED, before the callback starts.
2. SIGKILL at the same capture boundary.
3. Halt after actual view release but before client response.
4. SIGKILL after that release.
5. Isolate the follower outside the actual selected pair, commit a later bulk on
   that intact majority, prove the isolated stale cut remains old, reject a zero
   wait for the later token, then heal and issue a new minimum read.
6. Pause a real follower publication. A behind minimum cannot expose its future
   index; an ordinary queued read remains behind the application worker. If actual
   snapshot install intervenes, both calls instead reject NOT_READY. After verified
   publication, new calls expose the correct complete prefix.

Each crash case retains the exact pre-reopen voter files before starting the next
process generation. The independent store inspector checks those copied files
against their recorded original seal path and proves that the restored application
matches the retained proven prefix. The prior strong token is then used on both
the new leader and the restarted follower. A missing response stays PENDING with a
recorded disconnect; the later successful read never changes that earlier outcome.

### Selected and installed prefix evidence

Follower publication can follow three real authority paths: a local forced proof,
a verified rejoin snapshot, or adoption of a new campaign's independently selected
proven prefix. The last path installs generation/selector files and need not append
another standalone PROOF row for the installed prefix. The read observer now copies
current selector, generation seal, snapshot and journal bytes at the existing
SELECTOR_BEFORE_ACK hook. This is read-only telemetry, not a new persistent record.
The checker parses the seal/file inventory, transfers and validates both selected
bases, replays selection, and binds the local publication to that proof/index.
Reconstructed application bytes are still independently replayed against V4.4.

All cases retain complete source/tree, JAR/control/class hashes, Java identity,
codec/seed, run/attempt, raw inventory, process exits and public histories. The
matrix rejects changes in those shared bindings between cases. Eleven common
physical/query mutations plus two fault-specific mutations must reject with the
expected category. Original evidence must pass before mutations are attempted.
The published V4.4 query program runs again after packaging and relocation, and
all thirteen negative results must match. New read traces use the existing bounded
fault writer; no truncation or silently repaired authority is permitted.

### Failures retained during development

- Initial replay assumed only an individually forced proof or an identical rejoin
  snapshot could authorize local publication. Selected-prefix adoption and fresh
  application encoding exposed that incomplete checker. Raw failures remain at
  `target/v52-public-faults/run.bN3FYB`.
- The first installation observer used file names as JSON object keys. The existing
  canonical encoder rejects dots in keys; this observer error failed the runtime
  rather than hiding the missing evidence. The representation is now a fixed list
  of name/bytes records. Its failed matrix remains at `run.ug9WyY`.
- Genesis has no terminal proof. The common evidence identity now treats index-zero
  authority explicitly. The unchanged halted workload at `run.NF1na0` passes replay
  and all thirteen negatives after correcting this parser edge.
- The first complete matrix with the repaired observer passed all four crashes and
  held publication, but its fixed node-3 isolation sometimes removed the current
  quorum partner. The following write correctly became indeterminate. The schedule
  now observes the selected pair and isolates its other follower; it does not retry
  that failed write. `run.67eNO1` preserves the failure; targeted `run.I5CgY6` passes
  the corrected isolation and all thirteen negatives.

### Final 4B local verification

The complete gate passes at `target/v52-public-faults/run.uSNQeu/evidence`:
six cases, 54 successful read responses, four deliberately lost responses, one
PROGRESS_NOT_REACHED rejection and one DEADLINE_EXCEEDED rejection. All 78
negative checks pass both before and after archive relocation, with fresh published
V4.4 query execution each time. The shared binding records base commit `6e5c8aa`
and actual checkout digest
`77e69f83db519628d41cb979d7bf7cce8066fc8e80e3c3c352d2690d79fb6b51`.
Final result documentation is added after that bound execution; protected CI of the
committed source is still pending.

The unchanged healthy gate also passes at `target/v52-public-reads/run.rn1Cv4/evidence`
with six reads, eleven negatives and portable query replay. All 63 affected
Python/CI tests and all 21 V5.2 Python tests pass. Shell syntax, generated CI
inventory, documentation contract, changed local links and whitespace checks pass.
No runtime Java, public API, POM, authority format or frozen measurement was changed
by 4B. The suite/Required/profile topology is unchanged; an additional always-upload
retains fault evidence for fourteen days. Receipt/log hashes and the final file
list are retained in `target/v52-fault-qualification/validation-summary.json`.

The original failure receipts are not overwritten or reclassified. These cases
cover the declared 4B subset. At that boundary S18/S20/S25/S26 remained for 4C;
the complete N01–N16 physical matrix remains later work.


## 4C1: cancellation, cooperative close and actual ownership release

`verify-v52-phase4-public-lifecycle.sh` creates eleven fresh three-voter histories:
waiting, queued, before-capture, captured and completion-handler cancellation;
waiting and captured close; then both halt and SIGKILL after a cancelled callback
or incompletely closed callback releases its view. Each crash preserves exact
pre-reopen files and starts a second process generation on the retained directory.
The previously returned token is used through the public minimum policy after
independently verified restoration. No controller reconstructs product authority.

The external consumer retains the **original public Future**. Cancelling a dependent
handler would not cancel its source and cannot qualify this schedule. The ordinary
callback waits until its completion observer is attached, so an extremely fast
completion cannot turn this test into a late, independently executed handler.
Cancellation after capture retains the callback's permit. Cancellation during an
already-completed Future's paused handler returns false, while ownership remains
until that handler returns. Waiting reads fail CLOSED; a paused callback keeps its
view after an incomplete close and a subsequent close completes after release.
A process death leaves a missing response PENDING instead of inventing completion.

### Observation and independent accounting

A before-dispatch pause runs outside the protocol monitor and rechecks the full
capture conditions afterward. An observer failure cannot orphan queued work.
SETTLING and OWNERSHIP_RELEASED observations run only at their serialized state
transitions; they are never pausable. The latter follows actual permit return and
requires completion handlers, cancellation handlers and any strong barrier to
have settled. Recording the same exception twice cannot abort settlement through
self-suppression. The new observation fields do not change authority files or API.

The external observer samples the real semaphore and queue counters without
changing state. Its V5.2 reflection branch remains compilable against the published
V5.1 JAR. The independent replay reconstructs admissions, captures, settlements and
releases, checks exact conservation and integer types, verifies the single active
view, bounded marker/timers and final zero ownership, and retains outstanding
ownership explicitly for an abruptly terminated process. A cancelled/completed
Future alone never counts as a release.

Each case includes all three policies and the seven-query published V4.4 oracle.
The original source/build/run/attempt, physical authority, query and process checks
remain mandatory. Eleven common negatives plus missing/duplicate/early release and
forged counter negatives reject, both before and after archive relocation. The
new required verification step retains evidence for fourteen days in the existing
foundation lane; no existing job, profile, check or artifact is removed.

### Local verification and boundary

The complete eleven-case execution passes at
`target/v52-public-lifecycle/development-2`, with fifteen negative checks per case
before and after relocation, including a fresh V4.4 query replay after relocation.
Its runtime/consumer binding records base commit `c133e2c` and actual checkout digest
`0faa9076ae2121b1fae2bc4d6307c424b19fd0924d1d82e2ca24b487fe86835a`.
The stricter counter-type checker replays that unchanged evidence separately; it
does not rerun workloads or overwrite the original receipts. The earlier targeted
captured-cancellation run is also retained at `development-1`.

The initial affected Java run passes forty tests. The subsequent queue-only run
passes all eighteen tests including the added identical-observer-exception regression.
Its first compilation exposed a missing test import; that failed log is retained.
All 28 V5.2 Python tests and 70 affected CI/evidence tests pass; the unchanged healthy
entry point passes six reads, eleven negatives and portable replay at
`target/v52-public-reads/run.zLEvyv/evidence`. Logs are retained at
`target/v52-read-lifecycle-process/`. The published V5.1 observer compilation,
Python/CI contract checks and final receipt/hash summary are retained there too.
CI wiring, additional checker-type tests and result documentation are added after
the bound process run; protected acceptance of the committed source is pending.
S18/S20 process variants, the remaining S01–S30/N01–N16 matrix, combined Phase 5
hardening and frozen Phase 6 measurements are still required before cloud entry.


## 4C2: higher promises and installed-but-unpublished snapshots

`verify-v52-phase4-read-protocol.sh` executes seven independent public histories:
strong read before/after a higher promise, halt/SIGKILL after the overlapping
captured callback releases its view, and paused snapshot installation with normal
resume or halt/SIGKILL before the minimum rejection response. Every abrupt case
retains the physical pre-reopen directory and verifies the restarted application
against its actual retained proven prefix before checking a carried-token read.

The promise schedule establishes a new majority through real partition/election,
commits a new bulk there, then permits its higher promise to reach the paused old
leader. An uncaptured request rejects STALE_EPOCH. A valid captured request keeps
its own original strong result; it does not change policy or recapture new state.
A lost response stays PENDING. The independent checker requires a forced higher
promise within the exact local pause interval, in addition to the existing full
wire, selection, proof, publication and query oracle.

The install schedule starts from the full three-voter baseline and isolates the
follower outside the actual selected pair. After a new majority write and retained
recovery floor, healing performs a real snapshot install. The observer pauses
before local publication. Both stale and minimum reads reject NOT_READY without
admission or callback; a new minimum read succeeds after actual publication or
verified retained restart. The checker requires the matching REJOIN_INSTALLED
snapshot/proof and prevents an already-published prefix from posing as a held one.

### Retained fixture failures and corrected observation budget

The original matrix at `target/v52-public-read-protocol/development-1` is retained.
Its two normal promise cases observed correct fencing/overlap outcomes but stopped
waiting for follower recovery at forty seconds. This fault fixture freezes a
sixty-second operation timeout to isolate promise ordering from read deadline
expiry; existing rejoin transfers inherit that lease. An installation initially
rejected for generation capacity can occupy that exact transfer identity until
expiry, so fresh transfer offers remain rejected during the live lease. Forty
seconds cannot cover that declared lifecycle. The corrected controller allows the
sixty-second lease plus twenty seconds of margin and polls status every 200 ms to
stay within the existing 1000-command fixture bound. Public minimum reads still
use five seconds; no client mutation/read is silently retried and no production
lease, capacity or recovery logic is changed.

The first install fixture began with two voters and later started the third.
Although its installation/read state outcomes were correct, that produced fewer
basis-transfer frames than the unchanged physical oracle requires. The corrected
schedule uses the full three-voter baseline and actual isolated-follower catch-up.
The physical oracle's minimum traffic and every authority check remain unchanged.

### Local result and remaining integration

The complete matrix passes at `target/v52-public-read-protocol/development-2`.
Its binding records base `008296c` and checkout digest
`ff3a004611a5f362457a66126479fa41a94a21dcdb52b4d9ab24bc22c6f2de20`.
All 32 V5.2 Python tests and 50 affected CI/evidence tests pass.
All seven cases pass twelve negative checks before and after relocation, with a
fresh published V4.4 query replay after each relocation. The two normal promise
recoveries took approximately 60.6 seconds, consistent with the declared transfer
lease; this finite observation does not establish a failover SLA. The later
no-admission check replays the same original evidence separately rather than
rerunning the workload. Logs, receipt hashes and the verification summary are at
`target/v52-read-protocol-process/`.

This stage changes test drivers and independent evidence only. Phase 4D0 below
wires the protocol gate into its own shared-build CI lane. No current check is removed.
The remaining S01–S30/N01–N16 coverage still blocks complete Phase 4 acceptance.


## 4D0: required shared-build CI lanes

Four independent jobs consume the same exact-source verification build by artifact
ID. A history remains inside one gate; no continuous process history is split.

| Job | Complete qualification | Job ceiling |
| --- | --- | ---: |
| `v52-foundation` | Foundation/model, healthy and three-policy application replay | 15 min |
| `v52-read-faults` | Six faults, token admission and two linked backup/import histories | 15 min |
| `v52-read-lifecycle` | Eleven cancellation/cooperative-close cases | 15 min |
| `v52-read-protocol` | Seven higher-promise/snapshot-install cases | 20 min |

Each job validates restored source/build/attempt provenance and retains it even on
failure. Existing evidence artifact names, paths and fourteen-day retention are
preserved; the protocol gate adds `v52-public-read-protocol`. The protocol job's
20-minute ceiling leaves setup/upload time around the existing 900-second script.
Full and integration require all four jobs; docs expects all four skipped. The
registry, Required dependency set and generated inventory change together. Existing
V5.1, release, cloud consumer names and fixed matrices are unchanged. This is a
configuration split, not a measured speedup or a hosted acceptance claim.


Local validation passes all 125 affected CI/Required/tiered/observation/health and
cloud-consumer tests. The first run exposed a new test's scalar-only inspection
of unrelated multiline shell steps; its corrected 21-test suite passes, while the
other 104 tests passed unchanged. All 164 shell blocks, the YAML job count, exact
unchanged-job/step comparison, generated inventory and documentation links pass.
Receipts and the original failed test log remain in `target/v52-ci-lanes/`.
No GSE runtime workload was rerun for this workflow-only split. Protected hosted
validation and measured lane durations remain pending.


## 4D1: physical application lifecycle and published-query replay

The required foundation job now also runs `verify-v52-phase4-read-application.sh`.
Three fresh histories exercise LEADER_STRONG, STALE_ALLOWED and AT_LEAST_INDEX.
Each pauses inside the callback after a complete seven-method query report,
submits update, updateAll, remove, removeAll, index create/drop and add through the
public API, then repeats the report before releasing the view. All mutations are
still pending while that callback owns the application worker. After release,
each successful mutation must have its own exact chosen-and-published command.
A fresh strong read and the carried older minimum then return the updated prefix,
including deleted documents staying absent. The old token conveys history coverage,
not a promise to retain old document values.

The independent fixture decoder now handles operations 1–9, including exact key
counts/lengths, canonical index descriptors, analyzer identity, trailing bytes and
empty NO_OP payloads. Snapshot descriptors follow the actual replica TreeMap's
field ordering. This differs from public backup index ordering; the decoder does
not substitute a backup's ordering for the snapshot format. Fixture deletes target
existing documents and bulk commands are nonempty; these checks describe this
fixture rather than narrowing the product API's general remove/bulk semantics.
The pinned published V4.4 core executes all decoded operations and all seven query
methods at every observed publication. No product command decoder is used as its
oracle, and no runtime Java or persistent format changed.

Local `target/v52-public-read-application/development-1` passes all three histories:
27 successful reads, nine baseline bulks and 21 overlapping application mutations.
Each case passes thirteen evidence negatives before packing and after relocation;
each relocated oracle executes the published control again. The run binds base
`3746149a1f1e05ca59018cbba3bf0efaf040bca7` and checkout digest
`0edf5cae45509925a59bde553b973df30b61ec1ec4e47fb91171f7b506ded631`.
The subsequent CI wiring and documentation edits are checked separately.

Five decoder tests (including three new strict operation/projection cases), all
32 V5.2 Python tests and 79 affected CI/decoder/cloud tests pass. Replaying unchanged
healthy evidence both locally and relocated, the cancelled-capture SIGKILL history
and the paused verified-install history also passes their original negatives.
Logs, bindings and hash summaries remain at `target/v52-read-application-process/`.
This closes the physical S21 overlap case; the remaining identity, resource,
compatibility and complete N01–N16 accounting still prevent Phase 4 closure.


## 4D2: token identity, format and maximum bound admission

`verify-v52-phase4-read-identity.sh` runs in the carried-read fault lane. One fresh
three-voter history rejects eight separately recorded requests: wrong group,
wrong history, changed manifest digest, unsupported version, nonzero reserved bits,
trailing bytes, corrupt checksum and an uncovered maximum signed-long index with
zero wait. The first three preserve the captured index and have valid recomputed
checksums. Version/reserved mutations also recompute their checksum, so checksum
failure cannot conceal the intended format rejection.

Foreign and malformed tokens acquire no waiter/timer/capture ownership. Malformed
bytes are rejected before the runtime invocation; foreign but well-formed tokens
return INCOMPATIBLE_HISTORY. The uncovered zero-wait token returns
PROGRESS_NOT_REACHED. A separate request using the maximum index and 60000 ms wait
owns exactly one waiter and timer, remains pending, and is cancelled through its
original public Future. Observation counts and actual shared admission return to
baseline; a subsequent valid carried-token read succeeds. No memory allocation is
scaled to the lower-bound index. This does not replace the still-pending physical
authority corruption and new-group import schedules.

Local `target/v52-public-read-identity/development-1` passes: seven successful
reads, eight explicit rejections and one cancellation, plus three baseline bulks.
Twelve negative evidence checks reject before and after archive relocation; the
relocated query oracle executes V4.4 again. The bound base is
`ffb0c9be5ed6a793d129c4f0eaf9085a9210f02f`, checkout digest
`b36820017fa4b92942e9924a2895a0bad60b41639146cd5d6cbdbaa0582dad98`.
All 35 V5.2 Python tests and 32 CI topology/composite tests pass. New fixture tests
verify one-field identity changes and format-error precedence. Subsequent CI/docs
edits are separate from that bound process run. Evidence and hash summaries are in
`target/v52-read-identity-process/`; protected hosted qualification remains pending.


## 4D3: actual public backup and new-group import

`verify-v52-phase4-read-import.sh` qualifies two distinct whole histories. The first
runs three public voters and exports through `backup()`. Its exact fresh NO_OP,
validated capture, release and public response are independently bound to the
published prefix. A byte decoder verifies backup metadata, checkpoint documents,
sequence, member hashes, CRC32C, content identity and the reported result fields.
The second imports those exact bytes through the public verified-backup bootstrap
into a different group, then starts three new voters. The pair validator binds
source/build/classes/run/attempt and compares the copied backup inventory.

The imported genesis preserves application sequence 7 and all ten documents while
resetting the replication index to 0 and changing group, history and manifest
identities. The old token rejects before read ownership allocation; a fresh token
succeeds. A separate public startup/read probe supplies only that old token to an
empty authority directory and returns STORAGE_FAILURE. Startup reads the missing
manifest before constructing the transport; no replica manifest/genesis is created.
The probe is a separate JVM, not a voter or a replacement history fragment. Its
retained stdout is checked against the recorded result.

Local `target/v52-public-read-import/development-1` passes both histories: thirteen
successful reads, one foreign-token rejection, six baseline bulks and one backup.
Each history replays its queries with V4.4 before and after relocation; the combined
23 negative cases reject at both locations, including a forged successful backup
content identity. The relocated pair retains identical sequence/identity results.
The process run binds base `c40d851e2a29767ec3a5ff5ea714e6aadc7f87a8` and checkout
`4e8e5a3cd29dd472b1d9919583d72e14a9ff28942c7195d5b1c88eaa5d3d3ac7`.

Four new byte-parser tests use small recorded output from the actual pinned V4.4
control. Repaired-CRC mutations still reject foreign codec, document identity and
live-count changes. The first mutation test used CRC32 instead of the format's
CRC32C; that test failure remains in `target/v52-read-import-process/parser-tests.log`.
The corrected four tests, all 39 V5.2 Python tests and 32 CI topology/composite tests
pass. The strengthened stdout/pair check replays unchanged original and relocated
artifacts successfully. Final CI/docs/test-only edits do not relabel the process
run's source binding. This completes the public backup/import S16 schedule locally;
full Phase 4 and protected hosted qualification remain pending.

## 4D4: minimum token below the retired log floor

The public three-voter `token-below-floor` case carries a token at index 5, waits
for the real two-source floor, isolates the voter outside the actual selected
pair, and publishes one additional mutation. The leader establishes floor 6 and
deletes its previous generation. After healing, the isolated voter installs the
new snapshot and establishes its own floor 6. Both read successfully using the
original minimum token; their application sequence advances from 7 to 8.

The independent checker decodes the durable floor and both complete source
packets, verifies the matching downloaded peer source before floor establishment,
and requires the observed directory deletion. The active accepted/proof journals
contain headers only. Query results still match fresh published V4.4 replay; the
read does not depend on the token's old log generation or a token registry.

`target/v52-public-read-compaction/development-1` passes eight reads, four public
bulks, six publications and portable query replay. Its thirteen original evidence
negatives pass before/after relocation. The final checker adds a missing-deletion
negative; all fourteen pass when replaying both unchanged retained copies.
The process run binds base `d25e531b10ae38ceff7d8d8764d66f174abd094b` and checkout `dfb8c2d4947bc81ccb6a000ddb39aba4b9632238634e0d2e3d8e21e36b34e4d2`.
CI wiring and the additional negative were added after that run and do not relabel
its binding. All 39 V5.2 Python tests and 32 CI topology/composite tests pass;
contract, inventory, shell and whitespace checks pass. This completes S15 locally.
Full Phase 4 and exact-source hosted acceptance remain pending.

## 4D5: bounded public waiters and reserved writer progress

Three independent public three-voter histories configure P=4, P=65 and the default
pending-operation capacity P=10000. Other small qualification bounds remain
unchanged; this is not a throughput run with all production default limits. The
independent checker decodes the actual bootstrap PLAN and verifies every bound.

After all three voters establish their verified baseline recovery floor, register
R=min(64,P-1) minimum reads for the next unpublished index. Probe the real queue,
timer and semaphore counts; reject one excess read before allocation. Submit one
public write using the reserved capacity, then require every waiting read to return
its exact new application cut. Actual V4.4 replay checks all seven query results.
Original Future completion is not counted as release: atomic ownership transitions
and a final quiescent probe must return all slots and timers.

The first full run passed P=4/65 but failed the default-capacity write because its
selected peer returned NOT_READY for ACCEPT during background source installation.
Evidence remains at `target/v52-public-read-resource/development-1`; its 64 waiters
were admitted and then closed during failed-run cleanup. A published baseline alone
was insufficient to isolate this healthy-capacity schedule from initialization.
The harness now waits for each real two-source RECOVERY_FLOOR before saturation.
It does not change runtime logic, retry a business call, increase a deadline or
claim to remove recovery-time unavailability.

`target/v52-public-read-resource/development-2` passes all three whole histories:
131 waiting reads, three excess rejections, 149 successful reads including baseline
queries, twelve successful bulks and 39 evidence negatives at each location.
Both original and relocated histories run published V4.4 query replay. Base
`c2e4c94fe6a4763f263aba044573a4d6528a294d`, checkout `fff513528f95151ea3adf28b78c3fb45d4c579fb1dcd5960d4ab4a42f6f51e10` identify this process run; later CI/docs edits are
separate. All 41 V5.2 Python tests and 32 CI topology/composite tests pass. The old
cancel-waiting evidence also replays unchanged at both locations with the default
ownership limit. Full protected qualification and public P=1 remain pending.

## 4D6: zero explicit-read slots with live old APIs

The `single-slot` three-voter case bootstraps public P=1, completes initialization,
and submits each explicit policy to the leader. Each returns NOT_APPLICABLE /
CAPACITY_EXCEEDED without admission, timers, live views or callbacks. The minimum
request uses a valid independently encoded same-history token at the actual
published index; it does not claim that a P=1 handle returned an explicit token.

Three unchanged public `get` calls and four writes succeed across the rejection
window. Each legacy query has its own newly accepted/proven NO_OP, publication,
epoch validation, captured lifetime and released view before its response. Query
documents match independent prefix reconstruction and actual V4.4 replay. Final
queue/semaphore probes preserve the one public slot and zero explicit high-water.
Only this exact scenario requires zero successful explicit reads; every existing
positive-policy scenario still requires all three policies and its full matrix.

`target/v52-public-read-single-slot/development-1` passes three capacity rejections,
three legacy queries, four bulks and eight publications. Both locations replay
actual V4.4 query controls and four original negatives. A final forged-success
negative also rejects against both unchanged retained copies (five negatives per
location). Source base `a112c6f57b6598c6ef6c42f8a191c5cf4d7757a7`, checkout `88aa7207c57f7d9a884d58382307ea6c10c12971cc39c1734cabd07112de4cdc` remain the original run's
binding; later checker/CI/docs changes are separate.

All 41 V5.2 Python tests pass. Retained P=4/65/10000 evidence revalidates unchanged
with the exact zero-capacity branch present. The resource verification entry now
runs this additional whole history and retains it in the same always-uploaded
resource artifact. No production change, workload retry or paid run. S23/S24 are
locally covered; final compatibility, state/failure variants, physical negative
matrix and protected acceptance remain pending.

## 4D7: legacy cursor and consumer compatibility

Two new public real-TCP tests exercise old paging beside all three explicit read
policies. A cursor remains usable across a fresh strong NO_OP and local/minimum
reads. Actual application changes replace the automatic runtime's materialization,
so the old cursor rejects with DIFFERENT_ENGINE. A successor leader and newly
opened handles also reject the old opaque cursor while the same-history minimum
token continues to work. This test retains actual cursor objects across handles;
it introduces no cursor serialization or cross-process cursor transport format.
Existing nested-page rejection and compile-negative view paging remain enforced.

The first two local test attempts incorrectly expected STALE_SNAPSHOT after an
application update. Inspecting AutomaticApplication.publish establishes why that
was the wrong layer: automatic publication replaces the whole materialization,
whereas the underlying core engine also has same-instance snapshot invalidation.
Both failure logs/XML reports remain in `target/v52-cursor-compatibility`. The
corrected tests require the precise public DIFFERENT_ENGINE outcome; they do not
accept arbitrary exceptions. No runtime correction was needed.

The corrected twelve targeted Java tests pass, including public lifecycle,
V5.1/V5.2 API inventories and token bytes. All seven isolated consumer modules
compile; six run 24 tests (V1 is compile-only), with zero failures/errors/skips.
The current-artifact foundation rerun at `target/v52-foundation/run.IbIne3/evidence`
passes published-V5.1 binary/default loading, public API comparison, negative
paging/mutation compilation, 41 V5.2 Python tests and three coordinate tests.
The final installed core/replication JAR hashes match that receipt. These checks
use local Ubuntu Java 21, not the hosted pinned Temurin qualification.

Foundation's synthetic/model evidence still does not count as physical matrix
completion. Source-bound local receipts and copied JUnit XML files are retained
in `target/v52-cursor-compatibility`. Remaining state/authority-failure variants,
full physical N01–N16 mapping, Phase 5 and Phase 6 are still pending.

## 4D8: corrupt startup and fatal I/O around capture

Three new public real-TCP tests cover the storage-failure side of S30. Two variants
flip an actual required manifest/genesis byte before startup. Startup rejects
INTEGRITY_FAILURE, stays FAILED and never repairs the bytes. Explicit calls on that
unsuccessfully started handle reject NOT_READY before a callback or identity wait.
This differs from a previously started runtime observing a fatal storage failure.

For a started leader, an injected IOException at ACCEPT_BEFORE_WRITE follows the
normal authority failure path. The failed write is INDETERMINATE / STORAGE_FAILURE;
a waiting minimum read and all new explicit policies reject STORAGE_FAILURE without
callbacks, and outstanding permits settle. The second running case observes the
actual selected pair, captures a verified follower view, then injects that peer's
acceptance I/O failure. Its pending/new reads fail while the captured callback can
still read the same document and finish. The wrapper becomes inactive after its
actual release. The tests do not manufacture read results or change authority via
an internal activation command.

`target/v52-read-storage-failures/tests-1.log` and the copied JUnit XML record all
three tests passing on the first execution (including both corrupt-file variants).
These are controlled in-JVM public runtime tests, not independent portable process
receipts, and they do not claim a live filesystem-tampering detector on every read.
No production change, retry or timing-limit change. The remaining accepted-only,
isolated-old-leader and local state-transition mapping and full physical negative
matrix still block Phase 4 completion.
