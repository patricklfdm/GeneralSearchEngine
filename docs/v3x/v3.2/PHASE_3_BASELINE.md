# V3.2 Phase 3 TEXT-highlighting baseline

## Scope and comparison eligibility

This record captures the first integrated one-snapshot TEXT highlighting surface. The
Phase 3 branch starts from accepted Phase 2 merge commit `0729d77`. Ordinary ranked
search remains the same embedded-request control; highlighting explicitly re-analyzes
only requested fields of final top-K hits and stores no offsets in the index.

The short, single-fork WSL2 measurements below are local diagnostics. They are not
canonical evidence, do not replace either registered cloud family, and must not be
used as a cross-machine regression gate. Raw JMH output under `target/` is disposable.

## Environment and protocol

- captured: 2026-08-30, America/Los_Angeles;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- memory visible to WSL2: 15 GiB, with 4 GiB swap;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37;
- benchmark mode: average time, one thread, one fork, two 500 ms warmups, three
  500 ms measurements, GC profiler; and
- workload: 10,000 matching documents, top K 10, one requested field with 16 source
  tokens, context 40, and three fragments per field.

```bash
java -jar target/benchmarks.jar 'V32TextHighlightBenchmark.*TextSearch' \
  -p documentCount=10000 \
  -p topK=10 \
  -p sourceTokenCount=16 \
  -p contextCharacters=40 \
  -p maxFragmentsPerField=3 \
  -f 1 -wi 2 -w 500ms -i 3 -r 500ms -prof gc -foe true
```

## Local diagnostic result

| Operation | Mean time | Normalized allocation |
|---|---:|---:|
| ordinary TEXT top-10 | 1,205.713 us/op | 638,443.586 B/op |
| highlighted TEXT top-10 | 1,213.124 us/op | 1,192,514.879 B/op |
| workload-specific delta | +0.6% | +554,071.293 B/op (+86.8%) |

The short-run timing intervals overlap and do not establish a universal latency
claim. The allocation delta is real diagnostic evidence for explicit offset analysis,
range normalization, substrings, and immutable result construction after canonical
top-K execution. It is retained for Phase 5 profiling rather than hidden by averaging
with ordinary operations. Phase 0 intentionally freezes no numerical acceptance
threshold for this new surface.

The benchmark checksum consumes canonical document IDs and score bits together with
field names, fragment ranges/text lengths, and span counts. Trial setup also fails if
highlighted hits differ from the ordinary control. Full factorial 100k/1M, multi-field,
all-query-family, concurrency, and retained-memory evidence belongs to Phases 4 and 5;
this Phase 3 cell establishes only the first narrow TEXT implementation anchor.

## Correctness and evidence boundary

Focused fixtures cover the immutable model, validation order, exact Unicode source
ranges, every TEXT occurrence, duplicate and overlapping ranges, context coalescing,
caps, surrogate boundaries, extractor/analyzer failures, dynamic index lifecycle,
closed-engine rejection, and a writer publication while highlighting is blocked.

The integrated fixed-seed 300-trial differential suite compares highlighted hit lists
with ordinary canonical search and derives expected spans/fragments independently.
The lower-level fixed-seed 2,000-trial suite independently covers interval and fragment
construction. Replay information includes seed, trial, query, context, cap, and limit.

No paid cloud run is required for Phase 3. Neither `v3.0.0-cloud` nor
`v3.1.0-ranked-cloud` contains highlighting metrics, and Phase 3 changes no protected
workflow or stored index shape. A future canonical highlight lane still requires the
separately reviewed preset, mode, identity, cost, and retention contract frozen in the
performance document.

## Reproduction boundary

Build and execute the bounded discovery gate with:

```bash
scripts/verify-jmh-smoke.sh
```

The smoke cell proves benchmark discovery and execution only. It is not a latency or
allocation threshold.
