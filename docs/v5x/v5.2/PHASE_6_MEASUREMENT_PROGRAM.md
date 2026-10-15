# V5.2 Phase 6A offered program and query foundation

**Status:** untimed program/query foundation locally verified. M01–M04 execution,
the complete execution freeze, hosted acceptance and cloud admission remain open.
Continue under the [local commit authorization](LOCAL_DEVELOPMENT_SEQUENCE.md).
The [measurement contract](TESTING_AND_EVIDENCE.md#measurement-contract-and-later-freeze)
and [machine program](phase6-program.json) govern the next work.

## Program fixed before measurements

The corpus has 64 integer-key/string-value documents, seed 52, one initial bulk
(application sequence 1), 128-byte document bound and an explicit measurement
codec. The core queue/bulk configuration is 64/64 with a 1 ms batch wait; the
durable limits are 64 documents and 100 bulk elements. Candidate and controls use
the same configuration. These are fixture limits, not new production defaults.

M01 has five modes, each with three fresh histories:

| Mode | Read target | Semantics |
| --- | --- | --- |
| Published V5.1 | Initial leader | Existing strong methods |
| Candidate default | Initial leader | Existing strong methods |
| Candidate explicit strong | Initial leader | `LEADER_STRONG` |
| Candidate stale | Highest ordinal initial follower | `STALE_ALLOWED` |
| Candidate minimum | Highest ordinal initial follower | `AT_LEAST_INDEX`, initial strong token, 5000 ms |

All writes target the initial leader. Each history preserves 60 seconds warmup and
120 seconds measurement, with ten offered reads and one update per second. Reads
are offered every 100 ms; updates are offset 50 ms into each second. One history
contains 1,800 reads and 180 updates. Each window has exactly 20% get, prefix
filter, ranked, highlight and explain queries. There are 138 distinct descriptors,
including every document key. The 15 healthy windows total 2,700 nominal seconds;
this is a schedule calculation, not an observed runtime or completion estimate.

M02 retains nine lower-bound/wait combinations and 30 reads each. M03 retains
P=4/P=65 saturation and reserved writer progress. M04 retains leader SIGKILL/restart
and follower snapshot catch-up with carried tokens. These cells still need their
complete execution schedules, numeric runtime/evidence limits and outcome rules
committed before the first measured run. No hidden retry, fallback, shortened
window or speedup/latency acceptance threshold is introduced.

## Independent untimed query check

`measurement_model.py` independently generates/decodes document bytes, the exact
offered program and whole-update projections. It checks the canonical program
hash, corpus/call hashes and existing published-control manifest. The program
hash is `da2c68dc014595e176e1842a85181ea2d6fbd8ef9d8fef5c712993a0aa9126be`.

`measurement_foundation.py` independently compiles the same closed public query
consumer against the pinned published V4.4 core and candidate core. It verifies
the actual loaded JAR, records source/tree/JAR/class identities and checks all 138
descriptors at application sequences 1, 2, 65, 66 and 181. Each core executes all
180 actual updates and 690 queries. Document/order/sequence projections must match
the independent Python model; every complete query result, ranking score,
highlight span and explanation must match the published core exactly.

This validates query semantics and fixture construction. It does not start three
replicas, measure latency, compare V5.1 replication performance or qualify token
consistency. Published V4.4 is query truth; published V5.1 remains the strong-read
replication control for the future measured runs.

Local evidence is retained under `target/v52-measurement-foundation/`. The first
development check rejected the inherited 16-item core bulk bound when seeding 64
documents; the dedicated measurement builder now uses the declared 64-item bound.
The second rejected an outdated program admission hash after that pre-measurement
configuration addition. Both failures remain retained. The final complete query
check is `query-4`; no performance result was used to tune these fixture fixes.

The existing foundation shell gate runs this untimed check after its API/default
consumer/model gate, within the same required job and retained foundation artifact.
Existing suite identities, jobs, matrices, cloud consumers and checks are unchanged.

## Next implementation boundary

Before M01, provide a bounded compact trace retaining all original authority
bytes, independently validate reconstruction and relocation, and avoid repeating
full snapshot data in memory during replay. Then implement the common offered-load
consumer, V5.1/candidate adapters, clock-local measurements and independent
physical/query/history checks. Freeze the complete source/build/environment and
execution contract before running the full windows. Preserve each continuous
history and its dependent operations together. Cloud admission follows local and
portable no-GCP qualification; paid execution remains manual after push/merge.
