# V3.1 Phase 5 optimization 2: validation diagnostics allocation

Status: accepted local experiment. This change adds no supported API and preserves
all phrase-position validation types, messages, and failure precedence.

## Profiled cause and implementation boundary

After [optimization 1](PHASE_5_OPTIMIZATION_1.md) removed the bitmap-builder lambda,
JFR exposed successful calls to `PhrasePositionAccess.validate` allocating `byte[]`
through eager string concatenation. The previous null checks passed dynamically built
messages to `Objects.requireNonNull` for every slot and alternative even when the
value was non-null:

```text
"alternativesBySlot[" + slot + "]"
"alternativesBySlot[" + slot + "][" + index + "]"
```

Phrase verification invokes this unsupported bridge for every candidate document.
The implementation now reads the slot or alternative first and constructs the same
indexed message only inside the null failure branch. It does not skip document-ID,
array, shape, ordering, anchor, empty-slot, slot-null, or alternative-null validation.

Focused tests now freeze the two indexed `NullPointerException` messages. No search
plan, position algorithm, scoring path, candidate bitmap, or public descriptor
changes.

## Focused JMH result

Both measurements use 100,000 documents, one fork, two 500 ms warmups, three 500 ms
measurements, and the GC profiler on the same machine and JVM. The intermediate
column is optimization 1; the final column adds only this validation change.

| Benchmark | After optimization 1 | After optimization 2 | Step reduction | Cumulative reduction from baseline |
|---|---:|---:|---:|---:|
| common exact | 20,497,973 B/op | 10,523,738 B/op | 48.66% | 52.15% |
| focused exact | 12,015,357 B/op | 4,472,643 B/op | 62.78% | 66.93% |
| focused sloppy | 13,934,111 B/op | 6,391,400 B/op | 54.13% | 58.61% |
| composed | 8,826,129 B/op | 5,511,886 B/op | 37.55% | 55.79% |
| long | 18,428,616 B/op | 5,857,420 B/op | 68.21% | 72.69% |
| position gap | 26,049,866 B/op | 10,049,870 B/op | 61.42% | 64.68% |
| repeated | 2,652,188 B/op | 1,156,293 B/op | 56.40% | 60.82% |
| selective | 12,015,351 B/op | 4,472,640 B/op | 62.78% | 66.93% |

Every phrase shape reduces normalized allocation again. The second step removes
about 1.50 to 16.00 MB per operation, and the two Phase 5 changes together reduce
the original baseline by 52.15% to 72.69% across the matrix.

The after-change mean times are 25.802, 14.129, 17.829, 12.565, 21.492, 30.748,
2.656, and 14.472 ms/op in the table's row order. Relative to the original baseline,
the short-run changes range from about -4.3% to +5.2%. The confidence intervals are
wide, so this experiment establishes an allocation reduction and no latency claim.

## Profile confirmation and stopping boundary

After-change common exact and sloppy JFR recordings no longer attribute allocation to
validation-message `byte[]`. The earlier bitmap-builder lambda also remains absent.
The residual samples vary between immutable-list iterators, boxed document keys,
`ScoreMatch`, top-K candidates, and BitSet storage; CPU remains concentrated in
position, document-length, persistent-map, and candidate evaluation.

Those residuals cross BM25, posting storage, top-K, and general query execution. This
profile does not justify broad representation changes in Phase 5. Further production
optimization stops here pending the Phase 5 final gates; Phase 6 retains its separate
fuzzy dictionary boundary.

## Correctness and repository gates

- focused position, phrase, slop, lifecycle, failure-precedence, randomized
  differential, and ranked hardening suites: 32 tests, zero failures/errors/skips;
- complete core suite: 274 tests, zero failures/errors/skips;
- explicit null-slot and null-alternative exception-message equivalence: pass;
- JMH package and all eight setup-time result guards: pass;
- unchanged repository JMH smoke: pass;
- `git diff --check`: pass.

The cross-shape allocation reduction, removal of the profiled source, exact failure
preservation, and semantic gates justify retaining this optimization.
