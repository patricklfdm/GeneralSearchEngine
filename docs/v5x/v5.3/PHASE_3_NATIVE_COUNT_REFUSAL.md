# Native SOURCE-count refusal with admitted recovery continuation

Phase 3 remains **OPEN**. The optional resource-refusal fixture extends the
complete application-ACK process history: original carried INTENT or FINAL,
whole-group halt/SIGKILL, reopening of the same disks, completion of the carried
operation and a fresh stable BARRIER. It keeps all nine existing capture families
and both actual node-resource lifetimes. Existing fixtures use the unchanged
path unless the new test explicitly selects refusal capture.

## Real owning pool and bounded additional request

At `RETIREMENT_BORROW_PREFIX_WRITTEN`, the test observes the node's actual pool.
Only a callback with GENERATION/SOURCE/APPLICATION counts 2/6/7 is eligible.
The collector reads the existing private pool through test-only reflection;
it changes no pool field, limit, lease or production API. It reads one complete
original `sources/<id>/source.gscp` with descriptor custody preserved, then calls
the real private SOURCE receiver constructor for that packet and cut.

The constructor may temporarily reserve its ordinary 4 KiB CONTROL record, but
must reject the additional SOURCE with exactly `resource ownership/count`.
The test requires the scratch directory to be removed, all original authority
files to retain their hashes, and the before/after resource charges to match.
It holds the existing pool monitor around this short test operation, so unrelated
queue activity cannot be mistaken for its temporary reservation. The existing
journal writer already owns the captured storage boundary. There is no added
long-lived receiving copy or simulated learner authority.

The first qualifying callback for each node can record one probe per lifetime.
Each lifetime must contain at least one actual probe. The probe adds no protocol
request/response, retry or quorum member. It checks a private receiver admission
path; **wire admission, full byte saturation and admitted learner pressure are
not qualified** by this test.

## Independent original-first validation

`scripts.v53.native_application_refusal` requires the full unmodified nine-family
physical/protocol/owner history before inspecting the refusal sidecars. It binds
all sidecars to the original process PID, lifetime and terminal state, requires
complete sidecar inventories, and rejoins the recorded callback to its actual
resource checkpoint. The resource trace must show exactly one temporary CONTROL
reservation and its matching release, with the same original charges afterward.

The verifier derives the nonempty physical counts from that callback's original
file inventory. Reservation totals, zero-length files and empty directories
cannot substitute for the physical count. The supplied packet must match a
complete original source file byte for byte. The callback must precede the
recovered process's READY output, and the complete prerequisite must prove the
admitted recovery and fresh BARRIER. Close/drain and crash-prefix semantics remain
those of the original resource verifier.

Twelve exact negative variants change the probe record's scope, error reason,
cleanup, owner, callback/checkpoint, usage, file inventory or source binding.
These are in-memory sidecar-record mutations after a valid original; they do not
replace the existing captured-file negative catalogues. The producer records
physical paths as list values, not restricted protocol JSON object keys.

## Execution and acceptance scope

The two native entries are:

- `V53NativeApplicationRefusalTest#haltIntentWithSourceCountRefusal`
- `V53NativeApplicationRefusalTest#killFinalWithSourceCountRefusal`

A fresh source copy and matching tools/classes must accompany each execution.
The independent reader takes the emitted `v53NativeApplicationRefusalEvidence`
root, the corresponding `intent-application-halt` or `final-application-kill` case,
and a fresh output directory:

```bash
python3 -u -m scripts.v53.native_application_refusal /path/to/original \
  --case final-application-kill --output target/v53-count-refusal/replay
```

The command prints progress every minute and preserves failure receipts. The
result is `PARTIAL`. The subsequent [v5 cohort adapter](PHASE_3_NATIVE_REFUSAL_COHORT.md)
adds these two complete originals to carried-transition admission, including all
268 existing file/owner negatives. The twelve-subset boundary and frozen Phase 5
scenarios are unchanged; complete final-source execution remains pending.

## Development execution

The FINAL/SIGKILL entry passed on a fresh copy of `0df4de28` plus the recorded
test changes. The Maven command took 702.517 seconds, including compilation and
thirteen supporting tests; the native history itself took 669.4 seconds. All
fourteen selected Java tests passed. Independent replay took 116.755 seconds:
3,301 original callbacks, six actual refusals (nodes 1–3 in each process lifetime)
and all twelve exact negative checks passed. The 10,613 original files,
80,637,985 bytes, remained unchanged; the bounded result is 57,124 bytes.

All 79 related Python tests passed. The 25 overlap/refusal tests also passed with
assertions disabled. All 528 earlier evidence indexes remain unchanged. The
recorded source, build, tools, original inventory, failures, replay and test logs
are indexed in `phase3-evidence/native-count-refusal-development.json`.

Two earlier failed attempts remain retained. The sandbox denied local TCP during
the first attempt, before the native scenario. The next attempt reached the
refusal but failed when its new collector encoded a physical path as a restricted
JSON object key. The collector now uses path/value rows; a dedicated Java
regression covers that correction. Neither failure receives acceptance credit.

Only FINAL/SIGKILL was executed in this batch. INTENT/halt remains pending, and
neither history has final-source cohort admission. The complete physical
prerequisite was rerun before the twelve probe-record negatives; the existing
268 captured-file/owner mutations were not rerun in this supplemental check.

Full feasible byte pressure, remaining resource categories, actual learner
lifetime, the operation-231 continuation and final-source independent replay stay
open. This adds the concrete SOURCE-count refusal and continuation boundary to
the earlier [same-callback overlap measurement](PHASE_3_NATIVE_APPLICATION_OVERLAP.md).
It does not infer the full resource envelope from this one history.

Rollback removes the optional test producer/reader and its explicit capture flag;
keep all older native producers, nine-family readers, runtime fixes and retained
failed originals.
