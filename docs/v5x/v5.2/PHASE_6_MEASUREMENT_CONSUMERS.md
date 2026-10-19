# V5.2 Phase 6D untimed public measurement consumers

**Status:** five fresh three-JVM consumer histories locally verified, including
portable independent physical/query replay. This is a short integration gate;
none of the 60/120-second M01 windows or M02–M04 schedules has run. The complete
execution freeze, measured evidence and final hosted acceptance remain open.

## Actual consumers and independent controls

The common external consumer is compiled separately against published V5.1 and
candidate JARs. Legacy get/filter/ranked/highlight/explain calls use the ordinary
public methods. A separately compiled candidate-only adapter calls the explicit
read API. No candidate read types enter the published V5.1 classpath, and no
failed call falls back to another policy. All bootstrap, updates and reads use
public APIs. The observer records force, wire, capture and ownership boundaries;
it does not create authority or provide query results.

Each mode imports a real published V4.4 backup containing the declared 64-document
corpus at sequence 1. It starts three public runtimes, observes a ready leader,
performs one labelled setup query, confirms three declared updates and executes
ten query calls (five sequential and five overlapping). The legacy and explicit
strong modes read the initial leader; stale/minimum use the highest ordinal
initial follower. Minimum calls carry the actual initial strong token, unchanged.
The setup query is outside the future offered M01 windows and cannot be counted
as one of their requests.

The fixture currently uses P=64 (candidate R=63), eight client read threads and a
64-item client queue, 4,096 command identities per process, 1 MiB frames, eight
in-flight exchanges per peer, two protocol retries, 1,200 ms request/heartbeat,
3,600–6,000 ms election, 9,600 ms operation timeout, 25 ms retry backoff, 64 KiB
snapshot chunks and 64 MiB retained/staging limits. These are explicit **untimed
fixture** settings. The full measurement plan still must freeze its runtime and
client configuration before the first M01–M04 execution. There are no business
retries; status observations do not replace failed calls.

## Independent evidence checks

The compact trace is decoded without modifying its original bytes. The existing
physical checker still verifies actual forces, transferred bases, selected pairs,
chosen values, proofs, publications and retained authority. It additionally counts
the new consumer's single-document update response only after that exact document
occurs in a proven publication; all existing checks remain. The smoke-specific
checker requires:

- Exact source/tree/JAR/class/process/mode identity and the complete public ledger.
- The declared update and query stream, selected read node and unchanged minimum.
- An actual invocation, validated cut, entered view, release and response for every
  read. Candidate application generations must be present; the published V5.1
  observer predates that field, so its absence remains explicit rather than being
  assigned a fabricated generation.
- A fresh confirmed NO_OP for each strong call, the exact published token and
  sequence for explicit calls, and a satisfied minimum with the requested wait.
- Clock-local API, client queue and capture/release intervals. No subtraction
  between JVM clocks is performed. These short-run observations are not M01
  latency measurements or a latency SLA.
- Returned permits, no remaining explicit read ownership at idle, and balanced
  transport reservations after shutdown.
- Whole-prefix application reconstruction and actual V4.4 queries through the
  [advancing replay](PHASE_6_MEASUREMENT_REPLAY.md).

Packaging uses the existing bounded, hash-complete bundle and original-authority
path mapping. Fresh V4.4 query execution, physical replay and precise negative
rejections run again after relocation. The short gate additionally caps each
decoded node trace at 64 MiB/65,536 rows before in-memory negative mutation. It
does not materialize the larger future measured traces under these smoke rules.

## Bounded public close after measurement

Operator freeze `752968c` passed all preceding local/adapter gates and two M01
members. The third published V5.1 member completed its 1,980 offered requests,
then node 1 returned `DEADLINE_EXCEEDED: runtime close pending` during shutdown.
The original consumer called close explicitly inside try-with-resources: even
if implicit cleanup subsequently completed, the first exception still failed the
process and prevented its `CLOSED` observation. The failed history remains at
`target/v52-local-acceptance/runs/prepare-20261016T045013Z-3560646/cohort/histories/published-v51-legacy-strong-r3`.

The [public V5.1 contract](../v5.1/API_FORMAT_AND_COMPATIBILITY.md) permits retrying
close while ownership is retained after a timeout. The common external consumer
now owns that sequence explicitly for both published and candidate engines:

- At most eight public close calls, with a 20-second window for starting retries
  and 100 ms between them. The existing Python 35-second process exit bound stays
  in force; the retry window does not abort an in-progress public call.
- Retry only `AutomaticReplicationException(DEADLINE_EXCEEDED, NOT_APPLICABLE)`
  with no cause or a direct `TimeoutException`, and never when interrupted.
  Storage/integrity failures, wrapped execution errors, other outcomes and unknown
  exceptions propagate immediately. Backoff interruption preserves the interrupt.
- Retain attempt/failure events and earlier exceptions on exhaustion. Emit
  `CLOSED` only after public close returns successfully. Implicit cleanup cannot
  add another attempt after the explicit allowance is exhausted. An original
  workload exception remains primary if cleanup also fails.
- Normal close begins after executor/future drain and `CLIENT_IDLE`. There is no
  business retry, replacement workload or erasure of rejected/uncertain results.

`measurement_close.py` compiles eleven deterministic shutdown cases against both
public API artifacts. The existing foundation gate runs these checks, including
attempt/window exhaustion, interruption, original-failure preservation and
nonretryable nested causes. The machine freeze records the same policy and its
compiled consumer hashes. Short consumer execution still requires clean process
exit, released ownership, physical/query replay and exact evidence negatives.

The failed published history contains 660 successful offered reads, 1,028 client
executor rejections and 112 classified read rejections, plus 167 successful updates
and 13 not-submitted updates. Its setup read also succeeds. These remain real
performance outcomes; the close correction does not improve or relabel them.
No close stack establishes why the host experienced that load, and the failed
history cannot qualify without the required clean shutdown and independent replay.

## Local results and retained failures

The complete gate passes at `target/v52-measurement-runtime/run.O9v1LP/evidence`:

| Mode | JVMs | Successful reads | Confirmed updates | Final negatives per location |
| --- | ---: | ---: | ---: | ---: |
| Published V5.1 legacy strong | 3 | 11 | 3 | 6 |
| Candidate legacy strong | 3 | 11 | 3 | 6 |
| Candidate explicit strong | 3 | 11 | 3 | 10 |
| Candidate stale | 3 | 11 | 3 | 10 |
| Candidate minimum | 3 | 11 | 3 | 11 |

All fifteen JVMs shut down cleanly. The original complete execution passes 38
negatives per location. A stricter final replay adds the entered-view rejection
to every mode: ten unchanged raw/relocated inputs pass 43 negatives per location,
86 in total. Its receipt is under `target/v52-measurement-runtime/final-replay-1`.
That is checker replay, not another workload execution or a relabelled source.

Original execution binds base `add02e38c7eb97c4fa7224091014c914938b8b03` and checkout
`5f8ccc2d3236ad61d7b3168c2b9102ed23cc8e203781886b5f10cbc76309013a`.
Earlier failed observations remain retained: the first published-control replay
incorrectly required the new application-generation field, and the first complete
shell invocation hit a Python local name shadowing its reader function. Both were
fixed and checked against the unchanged captured evidence before fresh execution.
They were harness/checker defects, not evidence of a production timing failure.

All 73 V5.2 Python tests and 141 CI tests pass. Separate predecessor trace,
runtime-format, artifact and public-history checks pass. Production Java, POMs,
frozen authority formats and workload parameters are unchanged. The local JARs
come from the already verified reactor; observer/consumer Java is freshly compiled
for each control/candidate. This batch does not claim another Maven reactor run.

## CI and next boundary

`verify-v52-phase6-measurement-runtime.sh` runs the whole five-mode short matrix in
the existing required hardening lane after Phase 5. Its evidence is always retained
for fourteen days. Job identities and expanded counts remain unchanged: full 51,
integration 48, docs two meta jobs with 41 skipped suite placeholders. The registry
and generated inventory include one additional evidence upload (117 total); all
old checks, fixed cloud matrices and exact-master/attempt contracts remain intact.

Next freeze the complete M01–M04 execution plan, add the offered-load driver,
resource/allocation sampling and fault-specific schedules, and qualify their
streaming physical/history/query validators before running full measured windows.
This smoke gate cannot substitute for those windows or for paid cloud evidence.
Continue locally under the [existing authorization](LOCAL_DEVELOPMENT_SEQUENCE.md),
then stop before paid execution for the operator's combined push/PR/master review.
