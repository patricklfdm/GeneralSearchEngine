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

4B builds the public process fault driver on the same external consumer and
independent published query replay: retained restart/lost response, isolation and
proof/publication cuts. Later 4C completes promise/install/cancel/close process
races and exact resource evidence; 4D closes the full schedule and negative matrix.
Each batch is locally verified and committed without a push. Phase 5 combined
hardening and Phase 6 frozen local/no-GCP measurements follow only after the matrix
is complete. Paid execution remains outside this authorization.
