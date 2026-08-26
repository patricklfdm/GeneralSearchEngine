# V3 Phase 5 exact phrase performance smoke

## Scope

This is a focused implementation smoke, not a portable performance promise or release
threshold. It checks that exact phrase retrieval first reduces work through posting
membership and then verifies stored primitive positions without document reanalysis,
full-collection positional scans, per-document index/posting/IDF resolution,
per-document candidate reconstruction, boxed position collections, or unbounded result
retention.

## Environment

Recorded on 2026-08-26:

```text
OS: Linux 6.6.87.2-microsoft-standard-WSL2 x86_64
CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs
JVM: OpenJDK 64-Bit Server VM 21.0.12
JMH: 1.37
```

The focused fixture contains 10,000 documents and two independent text indexes. One in
five documents contains the exact three-slot phrase; one in seven contains all phrase
terms with a wrong gap. Both cases retain only the ranked top 10. The composed case
adds a cross-field TEXT MUST and boosted PHRASE SHOULD.

## Commands

JMH source and generated-code compilation:

```bash
./mvnw -Pjmh -DskipTests package
```

Short functional smoke:

```bash
java -jar target/benchmarks.jar '.*PhraseSearchBenchmark.*' \
  -wi 1 -i 1 -f 1 -w 100ms -r 100ms
```

## Observations

| Benchmark | Documents | Smoke result |
|---|---:|---:|
| exact phrase top 10 | 10,000 | 1.378 ms/op |
| cross-field TEXT MUST + boosted PHRASE SHOULD top 10 | 10,000 | 1.703 ms/op |

Both cases produced ten deterministically ordered hits. Inspection of the implementation
and focused tests confirms that phrase slots, postings, union/intersection candidates,
anchor selection, IDF, and field statistics are prepared once per request leaf.
Candidate evaluation uses the stored Phase 2 primitive positions through the narrow
boolean positional bridge and retains only bounded top-K state.

The run used one short warmup and one short measurement iteration. These numbers are
diagnostic only, must not be compared across machines, and do not establish a frozen
Phase 5 performance budget or universal speedup claim.
