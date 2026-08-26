# V3 Phase 6 fuzzy-search performance smoke

## Scope

This is a focused implementation smoke, not a portable performance promise or release
threshold. It records the initial Phase 6 tradeoff: every non-empty fuzzy occurrence
performs one bounded scan of its field-local vocabulary during planning, while top-K
execution uses only prepared postings, candidates, edit distances, similarities, IDF,
and field statistics.

The benchmark measures the complete request path, including query analysis, bounded
vocabulary-scan planning, candidate construction, scoring, and bounded top-10
retention. It does not isolate execution from planning through a new public or hidden
benchmark-only API.

## Environment

Recorded on 2026-08-26:

```text
OS: Linux 6.6.87.2-microsoft-standard-WSL2 x86_64
CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs
JVM: OpenJDK 64-Bit Server VM 21.0.12
JMH: 1.37
```

The fixture uses independent title and body text indexes. The body field contains one
unique normalized `destinationNNNNN` term per document, so the parameter is also the
exact body vocabulary size. The analyzed fuzzy query is `destinaton00000`, which is
within the frozen AUTO bound of controlled vocabulary terms. Every invocation retains
only the top 10 hits.

The composed case adds a cross-field `TEXT(title, "featured")` SHOULD clause with a
boost below a required FUZZY body clause. Both cases therefore include fuzzy planning
and execution; the composed case additionally exercises recursive candidate and score
composition.

## Commands

JMH source and generated-code compilation:

```bash
./mvnw -Pjmh -DskipTests package
```

Short functional smoke:

```bash
java -jar target/benchmarks.jar '.*FuzzySearchBenchmark.*' \
  -wi 1 -i 1 -f 1 -w 100ms -r 100ms
```

## Observations

| Benchmark | Vocabulary terms | Smoke result |
|---|---:|---:|
| fuzzy plan + top 10 | 100 | 0.074 ms/op |
| fuzzy plan + top 10 | 1,000 | 0.592 ms/op |
| fuzzy plan + top 10 | 10,000 | 4.547 ms/op |
| FUZZY MUST + boosted cross-field TEXT SHOULD + top 10 | 100 | 0.076 ms/op |
| FUZZY MUST + boosted cross-field TEXT SHOULD + top 10 | 1,000 | 0.619 ms/op |
| FUZZY MUST + boosted cross-field TEXT SHOULD + top 10 | 10,000 | 5.022 ms/op |

All cases produced ten deterministically ordered hits. The observed increase with
vocabulary size is consistent with the intentionally linear initial vocabulary-scan
strategy. These measurements do not establish a crossover, optimization requirement,
or claim about other corpora, analyzers, term lengths, expansion densities, hardware,
or JVM configurations.

Implementation inspection and focused tests confirm that vocabulary traversal,
code-point conversion, bounded OSA distance, similarity, posting lookup, candidate
union, expansion IDF, document count, and average field length are prepared once per
request-level fuzzy occurrence. Candidate evaluation performs no Analyzer call,
vocabulary traversal, edit-distance computation, or document-term scan, and result
retention remains bounded by the requested top K.

The run used one short warmup and one short measurement iteration per case. The values
are diagnostic only, freeze no numeric release budget, and make no universal speedup
claim. A future trie or automaton requires separate evidence and must preserve the
Phase 6 expansion set, ordering, and scoring semantics.
