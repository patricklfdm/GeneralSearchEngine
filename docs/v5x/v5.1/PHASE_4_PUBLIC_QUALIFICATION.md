# V5.1 Phase 4C: public history and search qualification

**Status:** accepted through [PR #194](https://github.com/patricklfdm/GeneralSearchEngine/pull/194)
at `6d3fbb7ae149222903eba4ccbce0cab5cafb1cf4`, with exact-master
[CI 35560692475](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35560692475).
All six jobs passed; the reactor and new public qualification step actually executed.
[Batch D](PHASE_4_PUBLIC_FAULTS.md) extends the public fault coverage; complete
Phase 4 acceptance remains open.

## Concurrent public history

`scripts/verify-v51-phase4-public-qualification.sh --skip-build` compiles the consumer
outside implementation packages against packaged core/replication JARs. Every voter
is created with public bootstrap and started through the public handle. Three JVMs
run simultaneously; the killed leader is later reopened in a fourth process using
its retained directory. The observer only records or interrupts boundaries.

Four callers overlap uniquely tagged, two-document atomic `addAll` operations and
ordered match-all strong reads. Histories span leader failure, an attempted write to
a follower, surviving-majority service and retained restart. Every attempted call
is retained, including NOT_SUBMITTED and calls whose responses were lost. There is
no uncertain-write retry. Controller invocation/response times use one monotonic
clock; per-worker clocks are never subtracted across processes.

Two independent checks must agree:

- The client-only exhaustive search models ordered atomic bulks and reads. A
  successful write is mandatory; pending/indeterminate writes can be omitted or
  completed once. A response reporting uncertainty is not proof of completion.
  Real-time precedence comes from successful response-before-invocation intervals.
  The gate allows at most 24 calls and 100,000 search states; exhaustion fails as
  inconclusive. This bounded result is not a proof for arbitrary histories.
- The physical oracle independently decodes retained 1.2 authority, force records,
  raw receipts, frozen selection transfers and publication snapshots. It binds
  each tagged bulk to at most one chosen entry, checks that NOT_SUBMITTED has no
  effect, and compares each successful read with its exact captured application.
  Its own NO_OP acceptance must follow that call's invocation in the same process.

Stale reads, partial bulks and changed document order must be rejected by both
checkers. Missing force and borrowed-barrier negatives target the physical oracle.
The client-only checker does not pretend to inspect durability or network receipts.

## Crash cuts and retention

Each of `READ_CAPTURED`, `READ_RELEASED`, and `BEFORE_CLIENT_RESPONSE` runs with
worker `Runtime.halt(71)` and controller SIGKILL: six cases. The read observer hooks
are package-private, disabled by default and execute outside the protocol monitor.
Release is observed after query evaluation returns and before delivery of its result.
The response cut loses a successfully applied mutation's client response, so the
controller keeps it pending even though physical evidence can establish inclusion.

Receipts retain requested/observed cut, PID, process generation, exit code, source
inventory, candidate JAR hashes, full client history and raw force/wire traces.
The dead voter's exact authority inventory and archive are checked before reopening;
the independent inspector records its pre-reopen state. Failure receipts and logs
are uploaded by CI with `always()`, alongside successful runs.

## Separate published V4.4 search oracle

A richer external program starts three public automatic handles with real TCP in
one JVM. This semantic lane is labelled separately from the multi-process crash lane.
It executes the same deterministic application program as an independently compiled
and launched, hash-pinned published V4.4 core control.

The reports compare ordered documents; add/update/remove and atomic bulks; index
drop/recreate; equality/prefix/range/text/Boolean queries; ranking with exact score
representations; phrase/fuzzy search; all pages; highlights and explain trees.
The candidate checkpoints and exports a backup; published V4.4 restores that backup
and repeats the rich report. NO_OP reads must leave the application sequence equal
to the control. Code source locations and the published control hash are retained.

The rich candidate uses the same bounded maintenance policy as the public runtime
gate: checkpoint may wait up to 30 seconds in total for generation retirement,
retrying only the classified `CAPACITY_EXCEEDED` / `NOT_APPLICABLE` result. Each
attempt, including failures and a pending response, is retained in
`rich/checkpoint-maintenance.json`; success still requires a completed checkpoint.
Other reasons, uncertain outcomes, timeouts and interruption fail immediately.
Application operations and backup are not replayed. The published V4.4 comparison
and restore remain mandatory after checkpoint succeeds.

This closes the one-shot checkpoint race seen in master CI `35816488469`: all six
public read/crash cases passed, then rich checkpoint failed while the retained
voters still held snapshots at cuts 37 and 71 with a durable recovery floor at 37.
The checkpoint was correctly refused before overwriting the occupied generation;
the semantic consumer must allow the normal background reclamation to finish.
The gate runs a deterministic Java probe against this same helper before the
process matrix. It covers capacity recovery, permanent pressure with a fixed
deadline, all other reason/outcome classifications, missing responses, interruption
and synchronous/unclassified failures, retaining per-case receipts in
`checkpoint-probe/`. Production capacity checks and retention rules are unchanged.

## Coverage boundary

The table records the gaps at Batch C's completion. [Batch D](PHASE_4_PUBLIC_FAULTS.md)
now adds public mutation crashes, old-leader isolation and higher-promise read fencing.

| Evidence family | This batch | Still required before full public-matrix acceptance |
| --- | --- | --- |
| E01/E08 | Public three-JVM failover, successful-prefix survival and retained restart | Imported-genesis runtime failover; missing/copied authority process cases |
| E05/E10 | Lost mutation response, pending outcome, atomic chosen inclusion, observed follower rejection | Public mutation cuts throughout ACCEPT/PROOF/publication; cancellation/close fault schedules |
| E09 | Concurrent strong reads, exact fresh barrier/capture, capture/release crashes, full rich query oracle | Deterministic higher-promise before/after capture, isolated old leader, cursor across rebuild |
| E02/E03/E04/E06/E07/E11/E12 | Existing model, Java, storage, internal protocol and compatibility evidence remains applicable | Complete mapping to public-process schedules, including partitions, exhaustion and mixed modes |

This batch does not relabel internal Phase 2/3 evidence as public API execution and
does not claim performance, cloud or complete Phase 4 acceptance. No public API,
disk/wire format, dependencies, version or paid-cloud configuration changes.

## Local validation

Base `6ca9418ae14bb3434e3ee2aa8dcc6ba2cd7e45b6` plus this batch, 2026-09-20:

- The targeted reactor package passed all 15 `V51PublicRuntimeTest` /
  `V51AutomaticRuntimeTest` tests. This was a targeted regression run, not a new
  full-reactor test claim. Initial sandbox socket-denial results were environmental;
  the same local TCP tests passed with the required execution permission.
- Final qualification receipt:
  `target/v51-public-qualification/run.ilRZyw/evidence/receipt.json` — all six crash
  cases, four voter process instances and 14 recorded client calls per case (84
  calls total), both independent oracles, five negative variants per case, and
  the published V4.4 rich-query/restore comparison passed.
- Existing public gate:
  `target/v51-public-runtime/run.vYWLpi/evidence/receipt.json` — four process
  instances, nine chosen/publications, three write successes and three read
  barriers passed, including its existing seven negative fixtures.
- Foundation:
  `target/v51-foundation/run.Z4uksu/evidence/receipt.json` — all 59 Python tests,
  external consumer and published V5.0 binary compatibility passed. The later
  documentation-only gate expansion also checks the Batch B/C records.
- Shell syntax, CI YAML, changed Markdown links/anchors/fences, the V5 contract
  gate and whitespace checks passed.

Replication JAR SHA-256:
`1a040bfcb1ce041d74ea73d06cb2141e2300fede6b9fec7f121066660c4dbd78`.
The first driver attempt omitted an explicit startup event for a reopened node
that had not yet written anything; that retained FAIL receipt is not counted as
qualification. The driver now records startup/close and binds every trace to its
node, process generation, group and manifest. A preliminary complete run passed;
the final receipt above additionally covers the tightened identity/order/negative
checks and atomic fault-arm consumption.

Receipts keep their own source inventories, including the documentation state at
execution time. This validation summary is written afterward. Protected acceptance
is recorded only after the user merges and the corresponding exact-master CI passes.
