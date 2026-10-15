# V5.2 Phase 4 qualification

**Status:** in progress. Phase 4A adds deterministic and in-JVM public lifecycle
coverage; it is not complete acceptance of S01–S30. Hosted exact-source validation
and separate-process fault schedules remain pending. Follow the
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
| S01–S03 | Seven consumer modules, old implementation binary/default, stopped/closed checks, seven-query public three-JVM gate for all policies | Rerun complete compatibility on the final artifact |
| S04–S06 | Actual store/protocol accepted-only, proof-only and staged-publication tests | Public isolated/delayed-publication physical schedules |
| S07 | Three-JVM imported sequence four at index zero, fresh strong NO_OP; independent prefix replay | Included in later aggregate |
| S08–S12 | P=4 satisfying write, bounds/deadline/registration tests, queued strong ordering, update/delete carried bound | Public delayed follower and overlap physical evidence |
| S13 | All three identity mismatches before admission/allocation | Public new-group/import and retained restart variants |
| S14–S16 | Existing publication/recovery kernel and token compatibility rules | Carried-token halt/SIGKILL, below-floor catch-up and new-group backup |
| S17–S20 | Actual higher-PREPARE before capture, protocol publication/install state gates, captured-state deterministic variants | Public partition/promise/install cases with required process deaths |
| S21 | Real public paused callback with queued update and index create/drop; same generation | Physical process trace of the combined lifecycle |
| S22 | Compile-negative page API and inherited automatic cursor tests; nested page rejection | Final artifact cursor/restart matrix |
| S23–S24 | P=4 real public saturation, P=1 old maintenance, P=65/default deterministic cap | Separate-process counters in final resource evidence |
| S25–S28 | Queued/waiting/captured/completion cancellation, close, throw/null, blocked callback/handler, FIFO and alternating worker tests | Required halt/SIGKILL variants and physical allocation/release accounting |
| S29–S30 | Seven-method cross-thread/escaped rejection, reentry, token-byte vectors, Long.MAX_VALUE and maximum wait | Public corrupt-authority/fatal capture physical evidence |
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

4B implements the public process fault driver described below. Later 4C completes promise/install/cancel/close process
races and exact resource evidence; 4D closes the full schedule and negative matrix.
Each batch is locally verified and committed without a push. Phase 5 combined
hardening and Phase 6 frozen local/no-GCP measurements follow only after the matrix
is complete. Paid execution remains outside this authorization.

## 4B: owned process faults and carried tokens

The required foundation lane adds `verify-v52-phase4-public-faults.sh`. It creates
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
cover the declared 4B subset; S18/S20/S25/S26 still need their full separate-process
variants, and the complete N01–N16 physical matrix remains later work.
