# V5.1 Phase 6A: rich model and published control foundation

**Status:** implementation candidate, awaiting protected full CI and review.
The [Phase 6 entry](PHASE_6_ENTRY_PLAN.md) was accepted through PR #215 at
`243434f6e1dc94422b57997b33eabb3cc1e8f64d`; its master CI `35831892351` was
correctly documentation-only. Full unchanged-runtime evidence remains Phase 5's
`fc1feca4dee6ee346e45d3afb22c4df9b9e0d945` / CI `35826641489`.

## Review boundary

This is the first implementation part of 6A. The existing public physical/history
checker supports two-field documents and unique bulk additions. The rich performance
program changes documents and indexes and needs a separate decoded state model.
Review that model against an independently compiled published implementation before
using it to accept automatic measurements. Existing physical/history validators and
their supported-operation restrictions remain unchanged.

The new receipt is `gse-v51-performance-foundation-v1`, with execution
`rich-model-and-control-only`. It explicitly reports `performanceMeasured=false`,
`automaticRuntimeExecuted=false`, `paidCloud=false`. It does not issue the reserved
`gse-v51-performance-evidence-v1` receipt or complete 6A.

## Executable plan and semantics

- [phase6-plan.json](phase6-plan.json) materializes the accepted
  [local measurement contract](PHASE_6_LOCAL_MEASUREMENT_PLAN.md), including all three
  future runtime modes, symmetric automatic policy, JVM flags, failover schedule,
  stage/slot/byte limits and the unchanged published-control pins.
- [performance_plan.py](../../../scripts/v51/performance_plan.py) admits only the
  reviewed canonical plan hash, then independently recomputes corpus, call, sequence,
  peak-document, payload, stage and logical-slot arithmetic. Duplicate JSON keys,
  nonfinite values, type/value drift, unknown fields and changed limits fail closed.
  This closed preset validator is the executable plan schema; no caller-supplied
  digest can authorize a different preset.
- [performance_model.py](../../../scripts/v51/performance_model.py) independently
  decodes rich documents, all eight mutation payloads and canonical application
  snapshots. GET and query answers preserve document order. The decoder accepts
  the frozen seed/revision document grammar; it does not approximate arbitrary
  rich text queries or extend the exhaustive two-field history checker.
- [performance_projection.py](../../../scripts/v51/performance_projection.py)
  uses the existing independent automatic 1.2 frame inspector to reconstruct a
  contiguous chosen prefix from exact-ballot acceptance quorums. Repeated observations
  do not add voters; re-proposals do not add logical slots. NO_OP does not advance
  application sequence. Snapshot anchors, exact observed proof voters, predecessor,
  application bytes and sequence must agree.

The projection helper requires its caller to establish each vote's owning process
and actual force boundary. It checks prefix/application facts only; it does not
establish basis selection, publication-before-response, a fresh read barrier or a
real three-JVM execution. Those observations remain required for the subsequent
runtime integration. Synthetic frames cannot become performance evidence by changing
an execution label.

Canonical plan SHA-256:
`1dff2117631534ead866cfbd2ea7da3ec29ab57e510a6a5e8e5bf17a32092c33`.
The source JSON file hash is recorded separately for each executing consumer.

## Published V4.4 execution

[V51RichWorkload.java](../../../scripts/v51/java/V51RichWorkload.java) uses common
public core APIs and issues exactly one workload API call per operation. It reads
`durabilityMetrics()` for labelled sequence diagnostics, never inserts before/after
`currentSequence()` strong barriers. Mode-specific runtime adapters remain pending.

The foundation independently compiles this workload and its semantic consumer against:

1. The checksum-pinned published V4.4 core.
2. The checksum-pinned published V5.0 core, as a common-API compilation check.
3. The candidate V5.1 core, also as a common-API compilation check.

Each compilation has its own output directory and exactly one core JAR on its
classpath. No replication implementation or workspace engine class shadows a
published control. Only V4.4 executes in this foundation. Exact JDK vendor/runtime,
flags, PID, loaded core location/hash, plan hash, compiler/process commands and
source inventory are retained. All probe sources live outside production JARs.

The V4.4 consumer loads 64 documents in four public bulk calls and exports the
immutable sequence-4 source backup. It then executes all 90 operations in the fixed
warmup/ABBA order, with no retry or reset. Full state scans after every operation
are extra **semantic probe reads**, not measured traffic. The independent Python
model compares every response, sequence, document order and index count.

After the program, a public checkpoint and same-store reopen must preserve final
sequence 76 and all 64 documents. The independent parser follows the real checkpoint
manifest, verifies CRC/profile/history/sequence/file binding, and decodes actual
ordered documents and index descriptors. A separate public restore of the unchanged
initial backup verifies the source at sequence 4. Source inventories before and
after the workload must match exactly. The independent backup parser also verifies
payload hashes and content identity; it supports this corpus's actual index order,
which differs from the old V4.3 fixed fixture's order.

### Published-control limitation found during implementation

An additional exploratory final backup from the V4.4 control failed with
`BACKUP_INVALID` after the 90-call program. Initial index order is
`title, category, price, body`; dropping and recreating `category` leaves final
checkpoint order `title, price, body, category`. The published structural backup
verifier requires checkpoint indexes to equal the initial metadata list, including
order. The workload itself, final checkpoint and public same-store reopen succeed.

This final **control-side** backup is not a call in the accepted 90-call program.
The foundation therefore validates its original source backup and actual final
checkpoint/reopen. It neither reorders indexes with extra calls nor repairs a
published JAR. Candidate replicated backup export and published-V4.4 restore remain
mandatory in the next 6A runtime part; this finding does not waive them. Retain the
failed exploratory receipt when reviewing local results. Any production fix for the
legacy structural-verifier behavior needs its own scope and regression review.

## Checked arithmetic and synthetic coverage

| Quantity | Recomputed value |
| --- | ---: |
| Encoded corpus documents / length-prefixed digest input | 3149 / 3405 bytes |
| Healthy calls / mutations / reads | 90 / 72 / 18 |
| Calls in measured-labelled windows | 80, without measured timings in this foundation |
| Final application sequence / documents / peak documents | 76 / 64 / 68 |
| Generated document / mutation payload maximum | 58 / 285 bytes |
| Automatic healthy / failover logical-slot admission bound | 162 / 90, each below 192 |
| Small-history maximum calls / checker limit | 18 / 24 |
| Whole future local performance gate | 900 seconds including 60-second cleanup reserve |

The synthetic projection includes one activation and eighteen read NO_OPs: 91
logical slots, 72 application mutations. Its peak encoded ENTRY/ACCEPT/PROOF sizes
are 482/632/274 bytes. The final snapshot is 29324 bytes, 39100 after base64 encoding.
These are exact **fixture** sizes, not runtime retained/staging/pinned byte peaks.
Runtime recovery bases, both generations, actual re-proposals, full envelopes,
resource samples and collection ceilings still need admission and observation.

Adversarial tests cover type/plan drift, malformed/truncated encodings, duplicate
keys, atomic bulk preconditions, index definitions/order, changed NO_OP semantics,
missing voters, mixed ballots, duplicate observations, re-proposals, prefix holes,
conflicting chosen values, changed snapshot/proof fields and wrong source/mode.
Resealed fixtures recompute storage frame checksums. Every actual control run also
rejects eight altered operation tapes and two changed source backups with recomputed
CRC, payload SHA and backup content identity; outer checksums cannot rescue wrong
application truth.

## Commands and CI integration

```bash
python3 -m scripts.v51.performance_plan
python3 -m unittest scripts.v51.test_performance_foundation
python3 -m scripts.v51.performance_foundation target/v51-performance-foundation/review
scripts/verify-v51-phase1-foundation.sh --skip-build
```

Use a fresh output directory for each standalone run. The standalone command needs
the current candidate core JAR and Java 21, and resolves pinned controls through the
existing cache. The full foundation gate also checks current reactor artifacts and
all existing declarations/models/consumers.

The existing `v51-foundation` job executes the new semantic check as part of its
foundation command. Its existing always-upload artifact retains
`target/v51-foundation/run.*/evidence/rich-workload`, including failed receipts,
process logs, loaded identities, raw backup/checkpoint data, 90-call tape, synthetic
frames, rejected mutations and member hashes. No new workflow/job/upload is needed.
Commands have a 60-second per-child cap and share a 300-second deadline from
harness startup. The existing resolver retains its own download bounds; independent
file/model checks are bounded by their input sizes. These are preparation checks,
not the future 900-second runtime gate. The observed local standalone pass took about
five seconds; actual CI scheduling and JDK timings are separate observations.

## Local candidate validation

- `verify-v51-phase1-foundation.sh --skip-build`: PASS, including all 292 V5.1
  Python tests (25 new model/encoding/observation tests), prior independent foundation
  checks and the new published-control flow. Receipt:
  `target/v51-foundation/run.967HxA/evidence/rich-workload/receipt.json`.
- Final standalone check after the explicit resolved-control/preset binding: PASS
  in 4.873 seconds, 90 real control operations, ten rejected evidence mutations,
  all 91 synthetic snapshots and three isolated core compilations. Receipt:
  `target/v51-performance-foundation/final-review/receipt.json`.
- Actual local JDK: Ubuntu `21.0.12+8-1-22.04-Ubuntu`. The CI Temurin execution will
  carry its own exact toolchain identity and timing.
- All 19 CI classification/Required tests passed. Text, local links, fences and
  whitespace checked across all changed/new files; 62 protected charter/V5.0/pin/
  workflow files matched HEAD.
- The exploratory legacy backup failure remains at
  `target/v51-performance-foundation/dev-1/receipt.json` and `control.stderr`.
  It is not a passing measurement or a discarded failed performance schedule.

Production/runtime code and old protocol/history validators are unchanged. Local
checks used existing packaged candidate artifacts; exact-source protected full CI
for this implementation candidate is still required.

## Next 6A implementation

Integrate the admitted plan and rich model with three concurrently alive V5.0
configured and V5.1 automatic voters, isolated published V4.4 timing, essential
force/quorum/publication/read-cut observations in every ABBA window, B-only timing,
periodic resources and the bounded two-field leader-kill/rejoin schedule. Add
independent measurement/resource/archive negatives and retain failed schedules.
Only after the complete preset passes should `verify-v51-phase6-performance.sh`
issue full performance receipts and enter CI at a measured lane location.

Full 6A acceptance, all later cloud stages and Phase 6 acceptance remain unchecked
in the [checklist](PHASE_6_CHECKLIST.md).
