# V3.4 Phase 3 burst and long-run calibration

Status: retained local evidence complete on
`feat/v3.4-phase3-burst-calibration`. The branch starts from protected-master Phase 2
merge `07b885790acbc8455db7bbc9a284173a05a19f56`. These results are local diagnostics;
they are not the required two-hour run, a `final-v34` cloud member, canonical evidence,
or a replacement for the still-open eligible heap matrix.

## Environment and identity

| Property | Value |
|---|---|
| Base source | `07b885790acbc8455db7bbc9a284173a05a19f56` plus the Phase 3 working tree |
| OS | Linux `6.6.87.2-microsoft-standard-WSL2`, x86-64 |
| CPU | Intel Core i7-12700F, 10 cores / 20 logical CPUs |
| JVM | OpenJDK 21.0.12, Ubuntu `21.0.12+8-1-22.04-Ubuntu` |
| Long-run heap / collector | equal `-Xms2g` / `-Xmx2g`, G1 |
| Phase 3 schema | `v34-local-long-run-v1` |

Dependency resolution and compilation are outside the recorded cells. The retained
long-run identity records the base commit and `dirty` tree state because the
diagnostic implementation and this evidence are committed together. This is permitted
for local calibration and is not eligible final-source evidence.

## Multi-producer burst matrix

The complete matrix uses 64,000 deterministic documents, four submitted batches per
producer, four concurrent readers, queue capacity 32, maximum bulk size 1,000, and a
180-second hard timeout per cell. A structured marker query may observe only zero or
the complete submitted batch. Every cell concurrently builds one range and one text
index, then verifies replay, final documents, marker counts, range/text truth, writer
metrics, and a drained queue/journal.

```bash
java -cp target/benchmarks.jar \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V34BurstRecoveryProbe
```

| Producers | Batch | Successful / submitted batches | Queue rejections | Successful mutations | Queue max | Completion p99 | Reader p99 | Drain from last submission | Snapshot delta | Checksum |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 4 / 4 | 0 | 4 | 5 | 21,122,204 ns | 19,403 ns | 155,257,369 ns | 6 | 1190479556868022490 |
| 1 | 100 | 4 / 4 | 0 | 400 | 3 | 39,144,328 ns | 27,155 ns | 59,454,453 ns | 6 | -6178851785341372201 |
| 1 | 1,000 | 4 / 4 | 0 | 4,000 | 4 | 108,983,093 ns | 32,567 ns | 128,967,236 ns | 6 | -5768644471529800598 |
| 4 | 1 | 16 / 16 | 0 | 16 | 15 | 71,977,249 ns | 2,150 ns | 72,675,624 ns | 18 | 2023923777793368000 |
| 4 | 100 | 16 / 16 | 0 | 1,600 | 15 | 94,798,462 ns | 3,950 ns | 101,726,660 ns | 18 | -93648620416366730 |
| 4 | 1,000 | 16 / 16 | 0 | 16,000 | 16 | 234,429,835 ns | 26,999 ns | 326,180,569 ns | 18 | 2104938903497984454 |
| 16 | 1 | 33 / 64 | 31 | 33 | 32 | 132,715,015 ns | 584 ns | 132,994,346 ns | 35 | 2012958889786759938 |
| 16 | 100 | 33 / 64 | 31 | 3,300 | 32 | 129,214,244 ns | 2,215 ns | 141,489,341 ns | 35 | 2655802007272981114 |
| 16 | 1,000 | 33 / 64 | 31 | 33,000 | 32 | 510,939,907 ns | 27,226 ns | 617,617,060 ns | 35 | -2184676675369275074 |

The combined nine-cell checksum is `-3957051389557579294`. The `16`-producer cells
deliberately reach the `32/32` queue saturation edge. Their 31 rejected batches are
completed `QUEUE_FULL` futures and do not publish; they are not timeouts or unresolved
work. Low and medium edges admit every batch. Every cell additionally injects and
verifies missing-document, duplicate-ID, and oversized-bulk failures; all three fail
atomically without a snapshot publication.

The matrix does not infer a multi-writer implementation. All producers submit through
the unchanged bounded queue to the existing single writer.

## Thirty-minute local calibration

The retained cell uses 10,000 documents, six rotating readers, 30 one-minute windows,
one-second sampling, a 30-second warmup excluded from all windows, 25 ms steady writes,
four-producer/100-document bursts every 60 seconds, and range/text dynamic-index
lifecycle every 120 seconds.

```bash
java -Xms2g -Xmx2g -XX:+UseG1GC \
  -cp target/benchmarks.jar \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V34LongRunCalibration \
  --output=/tmp/gse-v34-phase3-local-30m \
  --documents=10000 --readers=6 \
  --seconds=1800 --warmup-seconds=30 \
  --window-seconds=60 --sample-millis=1000 \
  --top-k=10 --steady-millis=25 \
  --burst-every-seconds=60 --burst-producers=4 --burst-batch-size=100 \
  --lifecycle-every-seconds=120 --queue-capacity=1000 \
  --source-commit=07b885790acbc8455db7bbc9a284173a05a19f56 \
  --tree-state=dirty
```

Readers rotate structured, ranked TEXT, ranked PHRASE, highlighted, exact-total first
page, and Explain paths. Stable document replacements allow every read to retain a
fixed truth/score/order oracle while still requiring atomic publications. The single
planned missing-document update occurs at the measurement midpoint; subsequent
windows prove recovery.

| Metric | Retained value |
|---|---:|
| Required windows / samples per window | 30 / 60 |
| Read operations | 34,510,438 |
| Write batches / mutations | 70,731 / 82,611 |
| Bursts / lifecycle cycles | 30 / 15 |
| Planned / unexpected failures | 1 / 0 |
| Unresolved futures | 0 |
| Final writer queue / maximum observed | 0 / 1 |
| Snapshot delta | 70,791 |
| GC count / collection time | 6,037 / 10,817 ms |
| Final checksum | -5676207448641903186 |
| Corpus digest | `da2f107e692333038a5472ae498a193f125a980d15896c835eb5ba8b9a98012d` |

| Window measure | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Read operations | 1,141,811 | 1,148,792 | 1,159,805 |
| Read p99 | 686,804 ns | 692,480 ns | 701,566 ns |
| Write batches | 2,353 | — | 2,360 |
| Per-window peak used heap | 1,234,461,264 bytes | — | 1,339,374,592 bytes |
| Queue maximum | 0 | — | 1 |

Every workload kind has positive coverage in every window. Snapshot evidence is
monotonic, every active writer window makes progress, the planned failure remains
isolated, and queue/build/journal state is zero at completion. The final digest equals
the initial digest, and the final structured/ranked/highlight/page/Explain/index
oracles all pass.

The run emits `config.properties`, `samples.csv`, `windows.csv`,
`summary.properties`, and `manifest.sha256`. The manifest validates all four evidence
payloads:

| File | SHA-256 |
|---|---|
| `config.properties` | `5accf6333818ab1de56aec4b0be64b025ac52c60ddea228d6b9abcecc5dda7fb` |
| `samples.csv` | `353db160cb29f114bb3f7097b94180f2dbb7238538eca563e8f5cd4e676c568f` |
| `windows.csv` | `7aaa4f6f12ff895e5957f1102e1e67bf92e214cdfa85b1fb7519cf24b8e20e39` |
| `summary.properties` | `6c95533958f5a130fa161df8beba123d0c8260486344cfdc4f9404eb57193f4a` |

The workload-specific provisional review band is at least 861,594 reads per minute
window and at most 1,384,960 ns read p99. These values are twice-labeled as review
calibration, not universal release gates. All retained windows are inside them; there
is no unexplained sustained throughput or p99 drift in this history.

## Decision

- The complete producer/batch matrix passes the Phase 3 local correctness, liveness,
  completion, replay, saturation, and drainage gates.
- The reduced and 30-minute local calibrations pass sampler, warmup, window, mixed
  reader, mutation schedule, failure injection, dynamic-index, artifact, and cleanup
  gates.
- No production defect or optimization is justified; production source remains
  unchanged.
- The eligible `4g`/`8g`/`16g` heap matrix remains open on a suitable no-swap host.
- The required two-hour final-source experiment, `final-v34` cloud implementation,
  paid execution, canonical set, baseline registration, final conversion, and release
  remain later-phase work.
