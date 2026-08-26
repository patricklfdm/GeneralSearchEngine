# V3.0 performance and memory baseline

## Scope and method

This is release evidence for named workloads, not a portable SLA or universal speedup
claim. Measurements were recorded on 2026-08-26 under WSL2 Linux 6.6.87.2, an Intel
Core i7-12700F (20 logical CPUs), 15 GiB RAM, OpenJDK 21.0.12, and JMH 1.37. No swap was
used during the environment check.

The main matrix used one fork, two 500 ms warmups, three 500 ms measurements, one
thread, default JVM flags, average-time mode, and the GC profiler. The bounded 1M fuzzy
capacity row used `-Xmx6g`, one 500 ms warmup, and two 500 ms measurements. These short
one-fork runs are suitable for release diagnosis but have wide confidence intervals;
small differences are not treated as wins or regressions.

Build the executable harness from a clean tree:

```bash
./mvnw clean -Pjmh -DskipTests package
scripts/verify-jmh-smoke.sh
```

Reviewed raw JSON is generated under ignored `target/` paths named
`v3-phase8-*-baseline.json`; it is deliberately not committed.

## Ranked text, composition, phrase, and Explain

All rows below use 10,000 documents. Allocation values are retained in the raw GC
profiler output; latency is summarized here in ms/op unless noted.

| Workload | Result |
|---|---:|
| V2 legacy-equivalent text top 10 | 0.3538 |
| V3 equivalent TEXT top 10 | 0.3604 |
| V3 TEXT plus structured filter | 0.2238 |
| SHOULD-only cross-field | 1.1995 |
| multiple MUST | 0.2221 |
| MUST + SHOULD + structured filter | 0.1372 |
| nested BOOL + BOOST | 1.8334 |
| selective phrase | 1.1565 |
| common phrase | 2.2016 |
| repeated-term phrase | 0.2054 |
| long phrase | 1.8034 |
| position-gap phrase | 2.9117 |
| normal search top 10 | 0.4602 |
| matching Explain | 1.9801 us/op |
| non-matching Explain | 1.8963 us/op |

The V2/V3 equivalent rows returned identical hits and are effectively equal at this
measurement resolution. The filtered row is a different eligibility workload and is
not a claimed V3 speedup. Explain evaluates one requested document and is therefore not
directly comparable to ranking every eligible candidate for top 10.

## Fuzzy vocabulary scaling

The fixture has one canonical body term per document. The direct rows include analysis,
complete vocabulary expansion, candidate construction, scoring, and top-10 retention.

| Edit shape | 10k terms | 100k terms |
|---|---:|---:|
| exact-present | 5.152 | 43.773 |
| substitution | 3.640 | 40.370 |
| insertion | 3.704 | 42.123 |
| deletion | 3.528 | 39.974 |
| transposition | 3.498 | 41.398 |
| two edits | 3.382 | 40.660 |
| no match | 2.971 | 35.492 |
| 625-expansion stress | 2.424 | 4.698 |

The high-expansion fixture places 625 two-edit terms near the query and length-rejects
the remaining long terms early. Its roughly 5.18 MB/op allocation is expansion and
candidate work, not evidence that a 100k general vocabulary is constant-time.

Initial measurement found an avoidable per-vocabulary-term allocation pathology:
100k exact used about 56.1 MB/op and 1M exact used about 487.3 MB/op. A package-internal
reusable code-point buffer and three-row OSA workspace preserve the complete expansion
set while reducing those rows to about 10.5 MB/op and 24.1 MB/op respectively. The 1M
row measured 434.5 ms/op after the change (483.8 ms/op before it). Focused Unicode OSA,
randomized differential, fuzzy lifecycle, and full release-profile tests all pass.

The decision for 3.0.0 is to retain bounded complete vocabulary scan. Latency remains
approximately linear in vocabulary size, but the scan now avoids allocation per
rejected term. No hidden expansion cap, public tuning knob, trie, or automaton is added.

## Positional build and mutation

The positional fixture uses 10,000 documents, 16 tokens per document, and token-order-
only updates. Both the legacy default adapter and a native positioned analyzer were
measured.

| Workload | Default adapter | Native positioned |
|---|---:|---:|
| build 10k × 16 positions | 161–169 ms/op | 160–162 ms/op |
| publish one reordered document | 0.0108 ms/op | 0.0108 ms/op |
| publish 100 reordered documents | 2.438 ms/op | 2.398 ms/op |

Build allocation was about 265 MB/op and the 100-document publication rows allocated
about 2.95–2.97 MB/op. These are transient construction allocations, not retained heap.
The decision for 3.0.0 is to retain raw immutable primitive positions; there is no
position opt-out or compression mode.

## Transparent retained-memory estimate

For the same 10k × 16 fixture there are 160,000 term occurrences and 160,000
term-document associations because every document-local term is distinct. The
representation therefore has these reproducible payload facts:

- raw position integers: `160,000 × 4 = 640,000` bytes;
- document-length integers: `10,000 × 4 = 40,000` bytes before map/boxing overhead;
- theoretical bitmap membership floor: `160,000 / 8 = 20,000` bytes;
- actual trimmed `BitSet` long-array payload from the fixture's term/block layout:
  8,535,808 bytes across 99,457 term/block pairs.

Under the common 64-bit HotSpot compressed-reference layout, the 160,000 one-value
`IntPositions` wrappers plus padded `int[1]` arrays are approximately 6.4 MB, and the
corresponding persistent AVL nodes are approximately 9.0 MB before boxed keys,
posting objects, vocabulary strings/nodes, bitmap tree nodes, document-length nodes,
and snapshot/document storage. These figures are a structure-aware estimate, not a
heap ratio: object headers, alignment, compressed-oops settings, string sharing,
document shape, term repetition, sparsity, and retained older snapshots all change the
real total.

The committed design remains transparent: positions use four payload bytes per
occurrence, while per-association maps and sparse bitmap blocks can dominate on
high-cardinality, low-frequency vocabularies. Applications should benchmark their own
corpus and snapshot-retention pattern.

## Release decision

No V2-equivalent material regression was demonstrated. The measured new-feature costs
are understood and bounded by documented corpus shapes. The two release blockers found
during measurement—per-term fuzzy temporary arrays and a JMH uber-JAR overwrite
failure—received narrow internal fixes and focused/full validation. The performance
gate accepts complete vocabulary scan and raw primitive positions for 3.0.0 with the
limitations above.
