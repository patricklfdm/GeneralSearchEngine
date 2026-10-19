# V5.2 Phase 6B bounded measurement observation encoding

**Status:** encoding and real writer/crash foundation locally verified. This is
not a measured replica run or physical correctness acceptance. The
[offered program](PHASE_6_MEASUREMENT_PROGRAM.md) remains unchanged; the complete
M01–M04 execution freeze is still pending.

## Why a separate representation

Existing fault observers retain full JSON records, including growing snapshot
ancestry. Healthy strong reads introduce NO_OP publications; saving every growing
snapshot as another full string creates repeated data over a 1,980-call history.
The measurement representation preserves every original record byte and uses
content-addressed chunks for repeated large data. It does not sample observations,
omit proof/force/publication events, manufacture a cut or relax replica checks.

`V52MeasurementTrace` is a test-only subclass of the existing observer writer.
The shared writer gains one identity-by-default encoding hook; all existing
observers still append their original bytes. Measured observers will opt into the
new representation explicitly in a later execution harness.

## Closed representation and decoder budgets

Each reference line identifies `gse-v52-chunk-trace-v1`, original length/hash and
the original node/process/generation/order/clock/event/group/manifest metadata.
Rows of at most 8 KiB are inline base64. Larger rows reference fixed 4 KiB chunks
in a sidecar directory, named by SHA-256. Chunks are written by atomic rename
before the reference is published. The complete original line, including newline,
is recovered exactly. All original JSON and authority parsing follows decoding.

| Limit, per node across all process generations | Bound |
| --- | ---: |
| Original row | 4 MiB |
| Encoded reference row | 128 KiB |
| Total decoded observations | 8 GiB |
| Reference file | 128 MiB |
| Stored chunk bytes | 512 MiB |
| Chunk files | 131,072 |
| Observation rows | 262,144 |

These are evidence-decoder safety bounds, not workload performance targets or
runtime authority limits. Full execution admission must bind these limits and
combined evidence limits before measurement. Reaching one fails qualification;
the collector must not trim evidence or raise limits after seeing candidate data.

The independent Python reader validates all chunk names/hashes/types, exact row
hashes, strict JSON, metadata equality and consecutive process-local order. It
rejects missing/reordered chunks, duplicate keys, changed authority, skipped or
reused generations, symlinks, path traversal, pending appends and incomplete rows.
It bounds decoded size before reconstruction and streams one row at a time.
Re-iteration supports separate physical-checker passes without materializing all
decoded snapshots. Clock values are compared only within the same process.

Complete chunks created before an interrupted reference publication may be
unreferenced. They remain hash-checked, counted and reported; they never supply an
observation. Incomplete chunk staging rejects qualification. No partial bytes are
promoted to authority. The existing pending-record journal may finish only an
exited writer's already published exact reference, retaining its interrupted bytes
and completion receipt. Original source/authority locations still require the
existing relocation mapping in the future physical checker.

## Real writer qualification

`measurement_trace_foundation.py` separately compiles against candidate and pinned
published V5.1 artifacts, records their hashes and checks matching Java/Python
budgets. For each artifact it SIGKILLs the actual writer before, halfway through
and after a reference append, completes the exact published reference after exit,
then starts a new JVM generation. All 24 original rows per case must reconstruct
byte-for-byte, including after ZIP packaging and relocation. The expected stream
comes from the probe before encoding; it is not a fabricated replica history.

The foundation also checks sticky rejection before an oversized row is published,
restart accounting of cumulative decoded bytes, and all existing legacy trace
writer/segmentation probes against both artifacts. Ten independent Python tests
cover corruption, budgets, interrupted tails, identity and relocation. Existing
V5.1/V5.2 physical consumers retain their plain encoding.

Local outputs are `target/v52-measurement-trace/development-1` and `development-2`.
Both six-case writer matrices pass. The second adds explicit writer/decoder budget
comparison and cumulative restart admission. The foundation shell entry runs this
check in the existing required lane and always-retained foundation artifact;
there is no new workflow identity or omitted gate.

Next: stream the physical/checkpoint/publication analysis over these reconstructed
records, add a persistent independent published-query replay, implement the actual
offered-load consumers and freeze the complete execution contract. Neither storage
savings in this synthetic writer probe nor the preceding query comparison is a
throughput, latency or failover measurement.
