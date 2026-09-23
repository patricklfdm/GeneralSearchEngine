# V5.1 Phase 4B: public automatic runtime

**Status:** accepted through [PR #193](https://github.com/patricklfdm/GeneralSearchEngine/pull/193)
at `6ca9418ae14bb3434e3ee2aa8dcc6ba2cd7e45b6`, with exact-master
[CI 35554352587](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35554352587).
All six jobs succeeded; the reactor and V5.1 evidence steps actually executed.
Complete Phase 4 acceptance is tracked in the [checklist](PHASE_4_CHECKLIST.md).
Phase 4A was accepted through [PR #192](https://github.com/patricklfdm/GeneralSearchEngine/pull/192)
at `fce35d955e0b6b973014959e23fc38eb95dd2745`, with exact-master
[CI 35547603482](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35547603482).
This batch implements the [frozen API contract](API_FORMAT_AND_COMPATIBILITY.md)
without adding public methods, changing configured 1.1 behavior or authorizing cloud runs.

## Handle and local admission

`build()` captures configuration and returns STOPPED without filesystem access,
codec invocation, DNS, sockets or running threads. `start()` shares one opening
attempt while returning independently cancellable futures. Startup acquires the
local authority lock, validates the 1.2 seal and complete bootstrap-bound local and
application configuration, and reconstructs/publishes the local proven application
before enabling protocol traffic. Its first result is a locally started FOLLOWER;
it does not wait for a quorum. A coordinator/source backup need not remain mounted.

Missing, incompatible or already-owned authority fails startup. The same failed
handle does not bootstrap or retry; a new handle can open after resources have
been released. Imported application sequence and replication index stay distinct.
Election and activation remain internal, with a newly proven NO_OP before readiness.

## Ordered application calls and outcomes

The façade overrides every inherited operation, including atomic bulk and dynamic
index methods. A bounded admission semaphore covers queued calls, the active call
and completion callbacks. One ordered worker dispatches application operations.
Queued deadlines and cancellations remove work before argument/codec execution.
No application mutation is retried automatically.

Business validation occurs on the application worker before authority submission.
Pre-admission/encoding capacity rejection is NOT_SUBMITTED. The first attempted
acceptance IO crosses the uncertainty boundary, even if an injected IO error occurs
before a byte is written; that failure is INDETERMINATE. Public queue/barrier waits
use one call deadline. Arbitrary active codec/query/force work is cooperative, and
cancelling a caller future cannot undo an issued operation.

Protocol completion first publishes a consistent diagnostic snapshot, then hands
results to separate virtual-thread completion tasks, bounded by the same admission
permits. User future callbacks hold neither the
protocol monitor nor the ordered worker. A callback can submit a new call subject
to the same finite admission bound.

## Fresh reads and stable application views

Every `get`, query/ranking/search/page/highlight/explain, `currentSequence` and
`metrics` call submits its own NO_OP. It waits for acceptance quorum, proof quorum
and local publication, then checks current readiness/ballot and the exact cut under
the protocol monitor. User query evaluation runs after releasing that monitor.

The single application worker serializes evaluation with replacement/publication.
It therefore retains the captured engine for the entire callback. A later election
may overlap an already captured read, but cannot destroy its application view.
The deadline bounds queueing, the barrier and view acquisition; it does not forcibly
interrupt arbitrary query evaluation. A control-only publication preserves an
otherwise unchanged application snapshot and its current-snapshot page cursor.

Per-handle callback context rejects reentrant application/start/checkpoint/backup/
close calls before admission. Pure schema/field metadata and cached status remain
available. Core business/query/cursor exceptions keep their original types.

## Maintenance, diagnostics and close

`checkpoint()` is local to a started healthy voter and needs no quorum. It rebuilds
a private proven cut, rechecks the promise/proven boundary and absence of unresolved
acceptance, and verifies generation capacity before selecting local checkpoint
storage. It neither adds an application entry nor advances the recovery floor.
If the exact cut is already retained as the active snapshot (or sealed genesis),
checkpoint reuses it without rotating generations. A newer cut still requires an
available generation slot; capacity rejection must not quarantine the voter or
retire storage without the existing two-source durable floor.
The process gate allows up to 30 seconds for checkpoint capacity to become
available. It retries only `CAPACITY_EXCEEDED` / `NOT_APPLICABLE`, records every
attempt in `checkpoint-maintenance.json`, and still requires an actual success.
Other failures and missing responses are not retried; application mutations and
backup are issued once.

The Maven public-facade test uses the same bounded maintenance policy. A one-shot
checkpoint raced background generation retirement in
[CI run 35835260963](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35835260963/job/107097095512).
Its test-only wait shares one 30-second deadline across calls and pauses, and keeps
the attempt count and last capacity rejection if that deadline expires. Deterministic
tests cover permanent pressure, all other reason/outcome pairs, missing responses,
submission time, cancellation and interruption. Checkpoint sequence and exported
backup contents still require actual success; the storage regression still requires
a newer cut to reject without changing retained bytes until a durable floor exists.

`backup()` obtains a fresh read barrier and exports the captured application through
the existing bounded V4 backup path. It preserves core backup failures and rejects
an absent target beneath local authority. Cancellation never deletes created output.

`leadershipStatus()` and `durabilityMetrics()` return cached local observations;
they do not synchronously probe storage/peers or invoke codecs. Peer reachability
and retained acknowledgements are observations, not a readiness grant. The façade
reports its bounded pending call count and separates application sequence from
proven/published replication positions. Storage `currentSequence` describes the
local proven prefix; startup replay counts/durations retain their startup boundary.
Automatic 1.2 uses alternating named generation slots, so the inherited numeric
`walGeneration` is zero (not applicable); election epochs remain in leadership status.

Close stops admission and queued work, then waits for startup, ordered operations,
network and application work. Only after application users quiesce does the runtime
release authority ownership. An incomplete close throws and retains ownership;
a later close can finish after the callback returns. Metadata remains pure after close.

## Evidence gate

Run `scripts/verify-v51-phase4-public-runtime.sh --skip-build` after a current reactor
package. It requires the executed public Java regression report and compiles its
external consumer against the packaged core/replication JARs, outside implementation
packages. A separate observer bridge records forces and raw wire frames; it does
not initialize voters or call private activation/submission APIs.

Three independent JVMs use public bootstrap/start/election, mutate and perform fresh
reads, survive controller SIGKILL of the leader, restart its retained directory,
checkpoint and export a backup. The published V4.4 JAR verifies the export. An
independent oracle checks chosen entries, forced proof/remote ACK/publication order,
selected quorum transfer and each read's fresh NO_OP/result. Negative traces remove
forces/ACKs/chunks or forge a success/read result/barrier. CI always uploads the raw
traces, process logs, pre-reopen archive, source/JAR/control hashes and receipt.

The Java regressions additionally cover every successful read overload, atomic bulk
and index lifecycle, cursor continuity, imported local startup without quorum,
failed ownership/configuration admission, reentrancy, completion callbacks, queued
cancellation/deadlines, first-IO outcomes and close with an active view.

## Remaining Phase 4 qualification

This batch is a functional public-runtime milestone. It does not close every E01–E12
row in [TESTING_AND_EVIDENCE.md](TESTING_AND_EVIDENCE.md). [Batch C](PHASE_4_PUBLIC_QUALIFICATION.md)
adds the concurrent public-client history with bounded
linearizability checking, deterministic public read capture/release and response
crash cuts with both halt/SIGKILL, and the full separate V4.4 rich-query comparison.
The existing internal protocol/rejoin fault evidence remains necessary but is not
relabelled as that outstanding public-process matrix. No performance or cloud
acceptance is inferred from these local tests.

## Local validation

Base `fce35d955e0b6b973014959e23fc38eb95dd2745` plus this batch, 2026-09-20:

- Full reactor package passed: core 549 tests (four existing skips), replication
  282 tests, processor five tests. After the final callback/outcome checks were
  added, all 114 targeted automatic/configured-lifecycle tests passed, including
  11 public-runtime tests. The last diagnostics-only adjustment was rechecked by
  15 public/internal runtime tests before final packaging.
- Final public process gate:
  `target/v51-public-runtime/run.eEwIMn/evidence/receipt.json` — four JVM process
  instances, nine independently verified chosen entries/publications, three client
  write successes, three fresh public read barriers and seven rejected negatives.
  Published V4.4 restore/query of the exported backup passed.
- Final foundation gate:
  `target/v51-foundation/run.PRYcHO/evidence/receipt.json` — 47 Python tests,
  external stopped-handle/offline execution and published V5.0 binary compatibility.
- Before that diagnostics-only adjustment, storage/recovery, protocol, rejoin and
  public bootstrap gates also passed. Rejoin retained five JVM process instances
  at `target/v51-rejoin/run.ZnuXie/evidence/receipt.json`; bootstrap retained 16
  cases at `target/v51-bootstrap/run.4SvRXU/evidence/receipt.json`. These prior
  receipts retain their own JAR/source identities and are not relabelled as final.
- CI YAML, shell/Python syntax, 21 classifier/format tests, the V5 contract gate,
  changed Markdown links/fences and whitespace checks passed.

Final replication JAR SHA-256:
`cfc717934b216b2c5274d1aea10fc6c325f685ba0ea0633a04670dde24dbbfbb`.
The initial external-driver failures (JSON helper visibility, V4.4 API and batch
configuration) remain retained. The final gate uses V4.4's actual restore/open/query
path and an explicitly compatible batch size. Those failed driver attempts are not
counted as qualifying runs.

These are the original local results. The acceptance update above records the
subsequent protected Batch B merge; the complete public matrix remains separately tracked.
