# V3.3 Phase 1 pre-change baseline

## Scope and comparison eligibility

This record captures the V3.3 foundation before any production page, total-hit, or
cursor implementation. The production source is unchanged from accepted Phase 0 merge
`72f94c063d44fe5d758976e58ae30ab9f24b5439`; that merge itself changes only
documentation from signed V3.2 production behavior. Phase 1 changes coordinates,
compatibility gates, test-only oracles, benchmark coverage, and documentation, but no
file under `src/main/java`.

The short, single-fork WSL2 measurements below are local diagnostics for repeatable
same-machine comparison. They are not canonical evidence, do not replace either
registered cloud family, and are not cross-machine regression thresholds. Raw JMH JSON
belongs under `target/` and is disposable.

## Environment

- captured: 2026-08-30, America/Los_Angeles;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- memory visible to WSL2: 15 GiB, with 4 GiB swap;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37; and
- benchmark mode: average time, one thread, one fork, two 500 ms warmups, three
  500 ms measurements, GC profiler.

## Ordinary ranked page-harness baseline

`V33PaginationBaselineBenchmark` invokes only published ordinary
`search(SearchRequest)`. Sparse cells match 100 of 10,000 documents. Dense-tie cells
match all 10,000 documents with equal text and equal scores. Filtered cells admit the
`eligible` half before ranked retention.

```bash
java -jar target/benchmarks.jar \
  'V33PaginationBaselineBenchmark.*RankedSearch' \
  -p documentCount=10000 -p topK=10 \
  -p corpusShape=sparse,dense-ties \
  -f 1 -wi 2 -i 3 -w 500ms -r 500ms -prof gc \
  -rf json -rff target/v33-phase1-pagination.json -foe true
```

| Operation | Corpus | Mean time | Normalized allocation |
|---|---|---:|---:|
| ordinary ranked top 10 | sparse | 8.175 us/op | 10,992 B/op |
| filtered ranked top 10 | sparse | 10.403 us/op | 15,808 B/op |
| ordinary ranked top 10 | dense equal-score | 1,211.433 us/op | 878,435 B/op |
| filtered ranked top 10 | dense equal-score | 812.847 us/op | 445,471 B/op |

The dense-tie ordinary cell is the direct pre-change first-page anchor. Phase 2 must
compare its disabled-total first page with the same ordinary request and checksum;
Phase 3 later adds cursor depth. The table does not imply that filtering is universally
faster: this fixture deliberately halves the dense candidate set.

## Highlighted regression anchor

The retained V3.2 benchmark uses a 10,000-document dense TEXT corpus, 16 source tokens,
top 10, 40 context characters, and three fragments per requested field.

```bash
java -jar target/benchmarks.jar \
  'V32TextHighlightBenchmark.*TextSearch' \
  -p documentCount=10000 -p topK=10 -p sourceTokenCount=16 \
  -p contextCharacters=40 -p maxFragmentsPerField=3 \
  -f 1 -wi 2 -i 3 -w 500ms -r 500ms -prof gc \
  -rf json -rff target/v33-phase1-highlight-regression.json -foe true
```

| Operation | Mean time | Normalized allocation |
|---|---:|---:|
| ordinary TEXT top 10 | 1,232.387 us/op | 878,444 B/op |
| highlighted TEXT top 10 | 1,307.439 us/op | 1,194,758 B/op |

Pagination implementation may not move work onto the ordinary or highlighted overload.
Later same-machine comparisons must retain the exact host, JVM, parameters, JMH
options, and idle-system conditions and report distributions rather than only means.

## Compatibility and evidence boundaries

The fresh-isolated artifact gate downloads and compares `1.0.0`, `2.0.0`, `2.1.0`,
`3.0.0`, `3.1.0`, and `3.2.0`. It also checks the three pinned V3 artifact digests.
The default local repository failed closed because it contains a stale
same-coordinate V3.0 artifact; the isolated repository then passed all six comparisons.

No cloud run is required in Phase 1. `v3.0.0-cloud` remains the regression family and
`v3.1.0-ranked-cloud` remains the ranked-feature family. Pagination metrics cannot be
inserted into either immutable identity. A future paid page lane requires a separately
reviewed mode, preset, retention policy, and comparison contract.

## Reproduction boundary

Build and execute the complete retained smoke set with:

```bash
scripts/verify-jmh-smoke.sh
```

The smoke gate includes one bounded dense-tie V3.3 page-harness cell. It proves
benchmark discovery and execution only; it is not a latency or allocation threshold.
