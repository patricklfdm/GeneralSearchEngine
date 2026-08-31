# V3.2 Phase 4 query-evidence highlighting baseline

## Scope and comparison eligibility

This record extends the Phase 3 one-snapshot highlighting surface from TEXT leaves to
deterministic PHRASE witnesses, the scoring-selected FUZZY expansion, and recursive
BOOL/BOOST evidence. The Phase 4 branch starts from accepted Phase 3 merge commit
`5425299`. Ordinary ranked search remains the embedded-request control, and highlighted
results preserve its canonical hits exactly.

The short, single-fork WSL2 measurements below are local diagnostics. They are not
canonical evidence, do not replace either registered cloud family, and must not be
used as a cross-machine regression gate. Raw JMH JSON under `target/` is disposable.

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
java -jar target/benchmarks.jar 'V32QueryEvidenceHighlightBenchmark.*Search' \
  -p documentCount=10000 \
  -p topK=10 \
  -p sourceTokenCount=16 \
  -p queryKind=phrase-exact,phrase-sloppy,fuzzy,bool-boost \
  -f 1 -wi 2 -w 500ms -i 3 -r 500ms -prof gc -foe true \
  -rf json -rff target/v32-phase4-query-evidence.json
```

## Local diagnostic result

| Workload | Ordinary time | Highlighted time | Ordinary allocation | Highlighted allocation | Allocation delta |
|---|---:|---:|---:|---:|---:|
| exact phrase | 3,262.362 us/op | 3,104.291 us/op | 1,358,709.748 B/op | 1,678,373.924 B/op | +319,664.176 B/op |
| sloppy phrase | 4,136.799 us/op | 4,055.245 us/op | 1,516,571.999 B/op | 1,832,538.838 B/op | +315,966.839 B/op |
| fuzzy | 1,357.033 us/op | 1,380.755 us/op | 1,120,212.999 B/op | 1,415,729.854 B/op | +295,516.855 B/op |
| BOOL/BOOST | 6,149.914 us/op | 5,861.293 us/op | 2,962,414.989 B/op | 3,291,997.393 B/op | +329,582.404 B/op |

The short-run timing intervals overlap. Lower highlighted point estimates in three
cells are measurement noise and do not establish a performance improvement. The
roughly 296–330 KiB/op workload-specific allocation deltas are Phase 5 profiling
anchors for requested-field offset analysis, recursive evidence selection, range
normalization, substrings, and immutable result construction. Phase 0 intentionally
freezes no numerical acceptance threshold for this new opt-in surface.

Trial setup fails if highlighted hits differ from the ordinary control. Checksums then
consume canonical document IDs and score bits together with field names, fragment
ranges/text lengths, and span counts. The benchmark distinguishes query families so
their different canonical planning and scoring costs are not averaged into one number.

## Correctness and evidence boundary

Focused tests cover phrase least-slop/offset-tuple selection, repeated terms,
same-position alternatives, intervening source text, fuzzy exact priority, typo
expansion and weighted lexical ties, recursive MUST/SHOULD/BOOST composition, matched
zero-score children, requested-field order, cross-field evidence, and overlap
normalization.

Fixed-seed differential suites add 240 simple phrase trials, 180 synthetic offset
phrase trials, 180 full-scan fuzzy OSA/BM25 trials, and 220 nested query-tree trials.
The references independently enumerate witnesses, compute weighted fuzzy selection,
and evaluate evidence trees; every highlighted hit is also compared with ordinary
canonical search. Replay diagnostics include the fixed seed and trial context.

No paid cloud run is required for Phase 4. Neither `v3.0.0-cloud` nor
`v3.1.0-ranked-cloud` contains highlighting metrics, and this phase changes no cloud
preset, protected workflow, or stored index shape. A future canonical highlighting
lane still requires the separately reviewed mode, preset, identity, cost, retention,
and comparison contract frozen in the performance document.

## Reproduction boundary

Build and execute the bounded discovery gate with:

```bash
scripts/verify-jmh-smoke.sh
```

The smoke cell proves benchmark discovery and execution only. It is not a latency or
allocation threshold. The full local diagnostic command above is intentionally
manual, and its JSON remains disposable under `target/`.
