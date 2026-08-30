# V3.1 Phase 5 optimization 1: bitmap intersection allocation

Status: accepted local experiment. This change adds no supported API and changes no
query semantics or benchmark identity.

## Profiled cause and implementation boundary

The [Phase 5 pre-change profile](PHASE_5_BASELINE.md) traced the dominant exact and
sloppy phrase allocation sample to the candidate-slot intersection path:

```text
SearchPlanner.compilePhrase
-> ImmutableBitmap.and
-> ImmutableBitmapBuilder.set
-> ImmutableBitmapBuilder.mutableBlock
-> HashMap.computeIfAbsent capturing lambda
```

`set` invoked `mutableBlock` for each retained candidate. Although a mutable block is
created only once per block, the capturing mapping function was created before every
`computeIfAbsent` call. The implementation now performs an explicit dirty-block
lookup, creates or copies a block only on the first miss, installs it, and returns the
existing block on later calls.

The change is deliberately limited to `ImmutableBitmapBuilder.mutableBlock`. Bitmap
contents, cardinality, copy-on-write behavior, structural reuse, planner ordering,
phrase verification, scoring, Explain, and public descriptors are unchanged.

## Focused JMH result

Both runs use 100,000 documents, one fork, two 500 ms warmups, three 500 ms
measurements, and the GC profiler on the same machine and JVM. Before values are from
commit `aabaa0c`; after values include only this production change.

| Benchmark | Before allocation | After allocation | Reduction | Before mean | After mean |
|---|---:|---:|---:|---:|---:|
| common exact | 21,994,108 B/op | 20,497,973 B/op | 6.80% | 24.983 ms/op | 25.155 ms/op |
| focused exact | 13,523,891 B/op | 12,015,357 B/op | 11.15% | 13.427 ms/op | 13.517 ms/op |
| focused sloppy | 15,442,664 B/op | 13,934,111 B/op | 9.77% | 17.988 ms/op | 17.337 ms/op |
| composed | 12,468,068 B/op | 8,826,129 B/op | 29.21% | 12.958 ms/op | 11.778 ms/op |
| long | 21,445,717 B/op | 18,428,616 B/op | 14.07% | 21.752 ms/op | 21.250 ms/op |
| position gap | 28,449,889 B/op | 26,049,866 B/op | 8.44% | 32.143 ms/op | 31.731 ms/op |
| repeated | 2,951,398 B/op | 2,652,188 B/op | 10.14% | 2.726 ms/op | 2.586 ms/op |
| selective | 13,523,896 B/op | 12,015,351 B/op | 11.15% | 13.805 ms/op | 13.602 ms/op |

Every measured shape reduces normalized allocation, by about 0.30 to 3.64 MB per
operation. No cell regresses allocation. The short latency movements range from about
+0.7% to -9.1% and are not treated as latency improvements or regressions because this
diagnostic configuration has wide confidence intervals.

## Profile confirmation

After-change common exact and sloppy JFR recordings use the same one-warmup,
one-measurement diagnostic settings as the pre-change profile. The
`ImmutableBitmapBuilder$$Lambda` allocation source no longer appears. CPU samples
remain concentrated in `PostingList.positions`,
`TextIndexSnapshot.documentLength`, persistent-map lookup, and candidate evaluation.

The next experiment remains separate: remove successful-path diagnostic-string
allocation from `PhrasePositionAccess` validation while preserving all validation
behavior and messages. BitSet representation, positional storage, BM25 access, and
top-K object changes remain deferred.

## Correctness and repository gates

- focused bitmap, phrase, slop, lifecycle, randomized differential, and ranked
  hardening suites: 28 tests, zero failures/errors/skips;
- complete core suite: 274 tests, zero failures/errors/skips;
- JMH package and all eight setup-time result guards: pass;
- unchanged repository JMH smoke: pass;
- `git diff --check`: pass.

The allocation reduction, cross-shape consistency, JFR cause removal, and semantic
gates justify retaining this optimization.
