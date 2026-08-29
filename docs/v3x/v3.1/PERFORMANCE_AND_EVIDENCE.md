# V3.1 performance and evidence contract

## Evidence anchors

The immutable comparison anchor is registered as `v3.0.0-cloud`. Its three independent
Standard C3D-30 members report these 1,000,000-document median mean times for the
uniform English short corpus at top K 10:

| Query | Canonical median |
|---|---:|
| BOOL | 60.986 ms/op |
| TEXT | 52.915 ms/op |
| PHRASE | 88.197 ms/op |
| FUZZY | 59.877 ms/op |

The earlier stabilized production run remains the current focused allocation anchor:

| Query | Mean time | Allocation |
|---|---:|---:|
| TEXT | 56.584 ms/op | 28.1 MiB/op |
| BOOL | 47.384 ms/op | 17.0 MiB/op |
| PHRASE | 82.226 ms/op | 57.6 MiB/op |
| FUZZY | 62.231 ms/op | 35.8 MiB/op |

The two tables are different evidence sets and must not be presented as one run.
Canonical latency comparison uses the registered set; allocation claims identify the
stabilized source until equivalent canonical allocation metrics are reviewed.

## Two evidence lanes

### Frozen regression lane

The existing `v3-production-<mode>-v1` presets and complete metric-ID sets remain
unchanged. A V3.1 candidate uses this lane to compare existing TEXT, BOOL, exact
PHRASE, FUZZY, concurrency, and soak behavior directly with `v3.0.0-cloud` when mode,
preset, configuration, environment, and metric identities agree.

New feature metrics must not be inserted into a frozen preset. Cloud Benchmark V2
requires the same complete metric-ID set and benchmark configuration fingerprint for a
direct comparison.

### V3.1 feature lane

A separately versioned `v3.1-ranked-v1` preset covers new semantics and scalability:

- phrase slop `0`, `1`, `2`, and `4`;
- low- and high-frequency phrase slots;
- repeated terms, analyzer gaps, and same-position alternatives;
- BOOL widths `4`, `16`, and `64` with minimums `1`, half, and all;
- BOOL with and without MUST clauses;
- fuzzy vocabulary scale and retained full-scan oracle comparison;
- 100,000 and 1,000,000 documents;
- mean time, normalized allocation, GC, and result-consumption guards;
- 1M mixed TEXT/PHRASE/FUZZY reads with one writer.

This preset has a distinct benchmark configuration and metric identity. It establishes
its own canonical family and is never compared directly with `v3.0.0-cloud`. Adding it
to the protected cloud workflow requires a separately frozen Cloud Benchmark contract
extension; ad hoc workflow inputs or unverified retrieval are forbidden. The extension
is frozen in [the V3.1 cloud contract](CLOUD_BENCHMARK_EXTENSION.md).

## Optimization protocol

Each phrase or fuzzy optimization follows:

```text
pre-change focused baseline
-> allocation/JFR or equivalent profile
-> one narrow implementation change
-> focused correctness and differential tests
-> focused JMH rerun
-> unchanged regression preset
-> feature preset when applicable
```

Phrase and fuzzy representation changes do not land in one unreviewable patch. A
result is not accepted because it improves one query cell while materially regressing
text-index build, mutation publication, dynamic-index replay, retained heap, or mixed
writer progress.

## Required performance surfaces

Phrase evidence covers candidate construction, slot unions, intersection, positional
verification, slop width, document frequency, repeated terms, long positions, scoring,
and allocation. Fuzzy evidence covers vocabulary size, term length, hit density,
Unicode code points, exact and near misses, trie build/update, full-scan equivalence,
and expansion ordering.

Publication evidence covers initial text-index build, dynamic build, single mutation,
explicit bulk sizes, vocabulary insertion/removal, unchanged vocabulary with changed
postings, structural sharing, and retained memory. Concurrency evidence covers reader
latency/throughput, writer throughput, queue depth, GC, snapshot publication, dynamic
index lifecycle, errors, and final oracle agreement.

## Release evidence

V3.1 release requires a reviewed canonical candidate on the unchanged regression lane
and direct comparison with `v3.0.0-cloud`. It also requires a three-member Standard
reference run of the V3.1 feature lane after the protected workflow extension exists.
The feature set establishes a new anchor rather than a false before/after comparison.

Early V3.x policy remains measure, compare, and review. No fixed percentage becomes a
CI failure until multiple comparable canonical histories justify a separately frozen
threshold policy. Correctness, evidence validity, cleanup, and compatibility remain
hard gates.

## Long soak boundary

The current protected workflow supports canonical 30-minute soak and bounded one-run
two-hour experiments. Six-, twelve-, and twenty-four-hour runs require a new workflow
and evidence contract with paid-runtime caps, resumability, cleanup, retention, and
failure precedence. They are V3.x hardening investigations, not V3.1 blockers.
