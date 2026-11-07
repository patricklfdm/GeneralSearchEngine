# Joint queue pressure and native REMOVE completion

Status: **full-size development original qualified; final-source acceptance OPEN**.

The [source-bound producer and supplemental cohort](PHASE_3_RESOURCE_COHORT.md)
now bind the full experiment to its exact source, compiled classes, toolchain,
reader and unretried JUnit. Final-source full-pressure execution remains pending.

This explicit development qualification connects actual 64 MiB queue pressure
to the continuous native REMOVE history. It does not close `combined-resources`:
simultaneous maximum metadata/application occupancy and final-source cohort
admission remain separate requirements.

The four original voters import one verified backup containing 129 documents
with 32,768-byte values. The existing original-byte preparation publishes
RESERVE, PREPARE, READY and SEAL. Native TCP activation and slot drivers then
publish INTENT and install the joint configuration. Owners, listeners, journals
and resource pools remain live through the rest of the experiment.

Four additional reader-bound SOURCE traces retain original 4 MiB image chunks in the actual
activation endpoint. Seven exact duplicates pause at the real response-write
callback with send buffers charged. The next duplicate must fail at the
aggregate queue-byte bound; the server's CAPACITY and client's IO observations
must agree. Releasing the callbacks drains the sends. The same failed request
then succeeds with identical bytes, and each trace commits its image tail.

The same native owners subsequently publish FINAL, activate the new stable
configuration and publish BARRIER. The source sessions belong to the original
activation scope; the test does not manually release reservations, replace an
owner, manufacture a vote or enlarge any runtime resource bound. Remaining
export scope cleanup uses the normal endpoint lifetime. Test scheduling barriers
are deliberate faults, not a claim about normal traffic or recovery latency.

`scripts.v53.queue_completion_evidence` first reduces the complete original
bootstrap, preparation, three installations, publication acknowledgements and
terminal files through the existing continuous-history reader. Its additional
checks derive the actual queue transitions, four cache/seven send overlap,
original source bytes, exact request/reply attempts, classified refusal, retry,
joint/FINAL boundaries and zero terminal ownership. All declared negative
mutations require a passing original and their exact rejection reasons.

The old continuous reader retains its 512 MiB evidence bound and empty-bootstrap
default. This large-image adapter explicitly permits an 8 GiB **observation
archive**, including repeated physical snapshots. The new fixture permits a
256 MiB wire observation array; old fixtures retain 64 MiB. Neither setting
changes protocol frame sizes, queue capacity or source counts. The new explicit
large-image fixture uses a 900-second campaign/slot lifetime; the existing
continuous tests retain their original 180 seconds. Per-request timeout remains
30 seconds. These are qualification scheduling budgets, not changed runtime
defaults, an extension of an in-flight operation, or a failover SLA.

Run the explicit experiment separately from ordinary unit tests:

```bash
/opt/maven/bin/mvn -o -B -ntp -f reactor/pom.xml \
  -pl :general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  '-Dtest=V53QueueCompletionQualification#admittedRemoveFinishesAfterRealJointQueuePressure' test

# Use the original directory printed by the experiment.
python3 -m scripts.v53.queue_completion_evidence ORIGINAL_DIRECTORY --qualify
```

The explicit `Qualification` class is excluded from the ordinary `*Test`
discovery pattern. Large original-history execution may be scheduled with the
later hosted acceptance batch; this change does not add or dispatch a workflow.
Its observations do not establish public membership readiness, autonomous
completion, fresh-process recovery, a final-source admission or Phase 3 closure.

## Development observations and limits

### Explicit segmented queue transport

The retained continuous native fixture can now use the existing segmented wire
registry. Its constructor fixes the selected format before starting listeners.
The registry has one shared 8 GiB ceiling; collection and independent replay also
retain this component's existing 8 GiB whole-original ceiling. The ordinary JSON
queue profile keeps its 256 MiB wire ceiling. Runtime frame, queue, staging and
time limits are unchanged. This transport work does not admit a maximum-image
history or enlarge the formal resource cohort.

Both continuous physical replay and queue replay require the caller to choose
`SEGMENTED_BACKUP` explicitly. The bootstrap must still be the original verified
backup; the only registered logical history is `wire.json`. The reader validates
the complete registry, segment hashes, exact inventory and all rows before
exposing any prefix, and checks that the archive remains unchanged after replay.
It iterates the checked reader rather than rebuilding one large wire array.
Mixed JSON/segmented layouts, extra auxiliary histories and relabelled source or
layout metadata are rejected.

The new source-bound profile is `joint-queue-final-64mib-segmented`. It selects
only `V53QueueCompletionQualification#segmentedQueuePressureCompletesSameNativeHistory`:
the same 129 documents, four additional sessions, seven held sends, one real
aggregate-byte refusal, identical-request recovery and uninterrupted native
FINAL/BARRIER. Its separate execution schema binds source, classes, toolchain,
reader, exact unretried JUnit and the retained original. Capture is only PARTIAL;
verification requires the complete physical original, ten queue negatives, five
storage-capture negatives and two exact source/layout rejections. It cannot fill the original
JSON resource slot, and the existing two-member hosted workflow is unchanged.

The following commands are for later full execution; development of the entry
does not imply that this full pressure profile has passed:

```bash
python3 -m scripts.v53.queue_completion_run capture \
  target/v53-segmented-queue-acceptance/execution \
  --profile joint-queue-final-64mib-segmented --maven /opt/maven/bin/mvn
python3 -m scripts.v53.queue_completion_run verify \
  target/v53-segmented-queue-acceptance/verification \
  --profile joint-queue-final-64mib-segmented \
  --producer target/v53-segmented-queue-acceptance/execution \
  --pins target/v53-segmented-queue-acceptance/execution/pins.json
```

`segmentedImageRehearsesSameNativeCompletion` is the separate six-chunk small
rehearsal. Its original is read with `--multi-chunk-rehearsal --segmented`; its
`pressureRequired=false` receipt and different JUnit method cannot stand in for
the full profile. Long full-pressure and maximum-image acceptance remain pending.
The separate [maximum-image queue entry](PHASE_3_MAXIMUM_QUEUE_ENTRY.md) now
connects the calibrated seed, default staging and larger observation envelope
to this continuous path. Its original and twenty-negative gate remain distinct
from both small-image entries; full execution is still required.

The BASIS audit also confirms that `MembershipGrantJournal` emits a descriptor
containing cut/identity and capsule/inventory digests, not the capsule's complete
metadata payload. The queue probe now checks its existing single-record-chunk
precondition before starting pressure; actual capsule transfers remain the
native activation path's responsibility.

The [segmented development index](phase3-evidence/queue-segmented-development.json)
records the final 8 GiB collector's small native rehearsal (308.8 seconds),
11 passing Java tests, 128 Python tests in both normal and optimized modes, and
19 plan/contract tests. Independent replay and local pack/unpack replay returned
the same result, preserving all 4,216 original files: four sessions, 53 calls
and a 20,867-byte application delivered in six chunks. This original uses one
wire segment; multi-segment transport guards are covered separately. Neither
full-pressure nor maximum-image qualification follows from the small run.
Current-reader replay of the unchanged historical JSON full-pressure original
also preserves its exact result and ten negatives. The earlier collector
prototype and its observations remain separately identified in the index.

For explicitly segmented originals, the queue reader now retains frame
positions, hashes, kinds and sizes rather than all decoded request/response
payloads. It still validates every exchange before indexing and rechecks original
bytes and the frame binding on each lookup. Returned values are fresh; neither a
caller mutation nor a changed retained file can be hidden by a payload cache.
The JSON path, complete physical replay and original-first negatives are unchanged.

The [frame-view development index](phase3-evidence/queue-frame-views-development.json)
records 135 Python tests (also with assertions disabled), 19 plan/contract tests,
and identical replay of the existing segmented original, its portable copy and
the historical JSON full-pressure original with ten negatives. An isolated
synthetic index probe compares twelve distinct 256 KiB responses with the decoded
map; it measures retained Python allocations for this index only. It does not
qualify whole-reader RSS at maximum input or replace a native large-image run.

### Multi-chunk development prerequisite

The image tail now consumes all remaining bytes of the original SOURCE image
under the existing session, transfer identity and deadline, then commits at the
next sequence. The previous helper sent exactly two chunks and therefore cannot
be reused for a near-64 MiB image. The formal 129-document profile still produces
the same two chunks and the same 37 attempts; its limits, ten negative families,
source-bound entry and acceptance scope are unchanged.

The streamed native collector also now receives this fixture's existing
256 MiB wire envelope in its constructor, before opening the spool or listeners.
Previously the queue fixture assigned that value after construction; since the
backup path became streamed, the spool retained its admitted 64 MiB default and
normal close rejected the mismatch. The admitted field is now immutable. Other
JSON histories retain 64 MiB; 256 MiB is an explicit verified-backup option, and
unrecognized limits are rejected. This changes observation setup, not any
network frame, queue, resource or operation-time bound.

The independent reader derives the complete sequence set, every offset, tail
length and terminal COMMIT from the original image. It rejects omitted,
reordered, truncated or altered tail chunks and early completion. The record
basis in this component remains one chunk; a larger basis is rejected explicitly
and is a separate prerequisite for combining maximum metadata pressure. A future
maximum-image queue history also needs an explicitly admitted segmented evidence
envelope; this existing 256 MiB JSON component does not become that entry merely
because its image tail can now contain more chunks.

`multiChunkImageRehearsesSameNativeCompletion` imports two 10,000-byte values and
uses the existing 4 KiB rehearsal chunk size. Its six-chunk transfer and native
FINAL/BARRIER are development checks, with `pressureRequired=false`; it cannot
satisfy the formal resource slot or combined maximum. Select the explicit
rehearsal reader only for this method's original:

```bash
/opt/maven/bin/mvn -o -B -ntp -f reactor/pom.xml \
  -pl :general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  '-Dtest=V53QueueCompletionQualification#multiChunkImageRehearsesSameNativeCompletion' test
python3 -m scripts.v53.queue_completion_evidence ORIGINAL_DIRECTORY --multi-chunk-rehearsal
```

No maximum native qualification has been obtained from this rehearsal. The
operator has no qualifying native Linux machine for that long execution yet;
environment provisioning and final-source acceptance follow development.

The [multi-chunk development index](phase3-evidence/queue-multichunk-development.json)
retains the old two-chunk failure, the evidence-spool mismatch and the deliberately
stopped interim run. The corrected native rehearsal passed in 332.2 seconds;
its encoded image is 20,867 bytes, so four sessions deliver six chunks each,
commit at sequence 11 and complete 53 calls. Independent original-first replay
passed, preserved all 4,214 original files and rejected promotion to full queue
pressure. Current-reader replay of the unchanged historical full-pressure original
also preserved the original result and all ten negative outcomes exactly. These
are development and compatibility observations; final-source execution remains
required.

The first large-image original completed four preparation slots and its first
native activation, then failed local INTENT publication with
`original activation endpoint deadline/closed` under the inherited 180-second
fixture lifetime. Its 624-second execution, raw files and thread snapshot remain
retained; it never reached queue pressure. The subsequent 900-second fixture
must execute as a new history. The failed original is not relabelled as passing.

`smallImageRehearsesSameNativeCompletion` exercises the same endpoint and session
path with 4 KiB chunks. The eighth send is expected to succeed; its receipt sets
`pressureRequired=false`, so it cannot satisfy the full queue-pressure reader.
It checks integration and completion while the full-size experiment remains a
separate acceptance requirement. The whole original must pass before the ten
pressure-evidence negatives can count. No successful full-size negative replay
is claimed merely from their implementation or unit guard tests.

The first small-image rehearsal reproduced the native owner bound when opening
its fifth additional SOURCE trace: two exports from the actual joint activation
were still live. The corrected probe keeps those owners and uses four additional
large caches plus seven held sends. It does not close an activation scope early
or erase real reservations to reproduce the isolated six-cache experiment.
The original count-bound refusal remains distinct from aggregate-byte evidence.

The corrected small rehearsal passed its one native test in 302.625 seconds.
Independent current-maintenance replay of the original and a relocated copy
passed, including the exact small application, four sessions, 37 delivered
attempts, original retained exports, native FINAL/BARRIER and terminal cleanup.
It observed no capacity refusal and is rejected by the full-pressure gate.
Six existing continuous-transition tests and 38 Python guards also passed;
optimized Python produces the same guard results. The final fixture additionally
uses dedicated virtual threads for the seven blocked sends and prints pressure
milestones; those scheduling/observation edits are included in the subsequent full original
reported below. The earlier small receipt keeps its original source and scope.

The [development evidence index](phase3-evidence/queue-completion-development.json)
retains failed originals, exact executed fixture source, reports and raw hash
inventories. The twelve obligations and 566 planned whole histories are unchanged.

## Full-size development original

The clean `e532f2df3fb823b2b7faa9fb9f60b0d4cc80dbc4` source executed the exact
full-profile method once: one test, no failures/errors/skips, 979.2 seconds in
the original JUnit report (993.892 seconds for the recorded Maven execution).
Collection retained 4,214 original files / 1,768,608,365 bytes. Independent
original-first replay passed in 35.52 seconds, followed by all ten exact negative
rejections. Peak replay RSS was 1,218,664 KiB on this development machine.

The original derives four additional sessions, 62,142,358 maximum queued bytes,
one capacity refusal and identical-request recovery. The same native owners
complete FINAL/BARRIER and close with zero queued bytes. No history was retried,
no runtime bound changed, and no earlier failed evidence was replaced. The
[source/pins/hash index](phase3-evidence/joint-queue-original-development.json)
identifies the retained producer, immutable raw inventory and complete replay.

This is a local development component result. It is not the shared-seed hosted
queue pair, final-source supplemental cohort, maximum metadata/application
occupancy, automatic public runtime or Phase 3 closure. Those flags remain false.

## Same-owner storage during pressure

Current v2 originals require two physical snapshots at held-send and capacity-refusal
pressure. See [storage-pressure binding](PHASE_3_QUEUE_STORAGE_PRESSURE.md) for
independent byte/reservation derivation, the 15/17/20 negative sets and the limits
of this observation. Historical v1 evidence remains bound to its original reader and source; it cannot substitute for the new captures.
