# Complete transfer lifetime and process matrix admission

Phase 3 remains **OPEN**. The later [hosted adapter](PHASE_3_TRANSFER_HISTORY_HOSTED.md)
now implements the subsequent wiring described below; its final-source execution
is still pending. This document retains the local batch's original scope.

The [local entry](../../../scripts/v53/transfer_history.py)
reuses the existing [TCP lifetime producer/reader](PHASE_3_TRANSFER_FAULTS.md)
and [process recovery producer/reader](PHASE_3_TRANSFER_PROCESS.md). It adds
immutable capture and complete-pair admission; it does not add a second transfer
implementation or enable public runtime operations.

## Indivisible execution and provenance

`tcp-lifetimes` runs the complete `V53TransferFaultsTest` method: three original
bootstrap owners (stable sizes 3, 4 and 5), each with nine consecutive service
lifetimes. Reply loss, retry exhaustion, active/completed expiry, service close,
changed retry and owner close remain in the same owner history. The expiry clock
uses an explicit offset; it is not a measured wall-clock delay.

`process-recovery` runs the complete `V53TransferProcessTest` method: all eighteen
size/boundary/death combinations. Each history retains both JVM lives and the
original donor files across halt or SIGKILL. The optional producer case filter
is never supplied by this entry. A passing subset cannot fill a complete slot.

The first capture copies actual source bytes. The second copies that recorded
source with `--source-from`, even if the live checkout has changed. Both must
match one source manifest, actual compiled class inventory, portable toolchain
identity and the exact independent reader manifest. Capture requires one exact,
unretried JUnit method and successful original process/collection receipts. It
retains failure output and never overwrites an existing capture directory.

Collection checks only bounded inventories and completeness. Its receipt stays
`PARTIAL`, `nativeHistoryQualified=false` and `phase3Complete=false`. Neither a
producer PASS nor matching hashes substitute for independent validation.

## Admission

The aggregate requires exactly the two distinct producers and all 21 distinct
original bootstrap plans. Each original is independently replayed before its
complete existing negative vector. Exact case order, scope and rejection reasons
are required; a different failure cannot count as a successful negative. The
source, compiled classes, reader, process receipts and original inventory are
checked again after replay. One failed member is retained while the other is
still inspected; no native attempt or measurement is retried.

At most two independent matrix readers run concurrently. Neither a continuous
owner history nor the two lives of one recovery case are split. Capture and
replay report progress every minute; missing heartbeats are not success evidence.

A passing aggregate qualifies these declared transfer matrices only: 27 lifetime
cases plus 18 process cases. It does not establish complete Phase 3, automatic
competition, all membership profiles, simultaneous physical peak resources,
combined force/network faults or power-loss survival. The existing six hosted
subsets and their 428 planned histories are unchanged. A hosted adapter and
final-source admission are subsequent work; no workflow is dispatched by this
local entry.

## Local commands

Choose a new output root each time; Maven dependencies must already be available
for the offline build. The first command prints the exact native methods and
negative counts. These commands run the complete matrices, not the whole GSE CI.

```bash
python3 -B -m scripts.v53.transfer_history plan
OUT=target/v53-transfer-acceptance/manual-001
mkdir -p "$OUT/inputs"
python3 -B -m scripts.v53.transfer_history capture "$OUT/inputs/tcp-lifetimes" \
  --case tcp-lifetimes --maven /opt/maven/bin/mvn
python3 -B -m scripts.v53.transfer_history capture "$OUT/inputs/process-recovery" \
  --case process-recovery --maven /opt/maven/bin/mvn \
  --source-from "$OUT/inputs/tcp-lifetimes"
```

Freeze and review the expected pins from the first capture, then pass those same
values to the aggregate. `sourceSha256` and `buildSha256` refer to manifest bytes;
`readerSha256` is in the producer receipt. The toolchain pin is the portable
identity returned by `scripts.v53.process_toolchain.pin` on `toolchain.json`,
not that file's host-specific byte digest. Future hosted admission must obtain
these expectations from its immutable seed, not from each arriving member.

```bash
python3 -B -m scripts.v53.transfer_history aggregate "$OUT/aggregate" \
  --inputs "$OUT/inputs" --workers 2 \
  --source-sha256 "$SOURCE_SHA256" --build-sha256 "$BUILD_SHA256" \
  --toolchain-sha256 "$TOOLCHAIN_SHA256" --reader-sha256 "$READER_SHA256"
```

`receipt.json` retains the scoped result and each member's original/negative
replay. `progress.jsonl` records member completion. A failure returns nonzero and
retains its failed receipt; it cannot overwrite a previous result.

## Validation and remaining work

The [development receipt](phase3-evidence/transfer-history-cohort.json) records
actual local captures and original-first replay separately from synthetic
orchestration tests. The two native invocations completed without retries; the
complete pair replay covers 21 original histories, 45 native cases and 48 exact
negative results (25 lifetime and 23 process mutations). Packing/unpacking into
a new directory and replaying under Python `-O` produced the identical result
without modifying the originals. All 2,330 V5.3 Python tests pass, including
18 new orchestration guards; those guards also pass under `-O`. Captures bind a recorded working-byte snapshot based on
`f332b327`; they are not executions of the later documentation commit or a final
Phase 3 cohort. Existing historical component evidence is not replaced.

Regression tests exercise source/build/tool/reader drift, incomplete or aliased
matrices, changed process/JUnit evidence, retries, extra/linking paths, mixed
bootstrap plans, unrelated negatives, overclaimed scope and mutation during
replay. They also check that a failed original is retained without a native retry.

Rollback removes this optional entry, its tests and navigation. Java, frozen
resource/time limits, workflows, Required and ongoing V5.2 cloud experiments are
unchanged. Subsequent hosted wiring must preserve the same complete-matrix
boundary and bind its workflow, source, seed and exact run/attempt before it can
count towards phase-wide admission.
