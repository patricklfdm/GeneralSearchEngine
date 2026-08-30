# V3.1 Phase 6 local pre-change fuzzy baseline

## Scope and comparison eligibility

This profile was captured from Phase 5 merge commit `22aef03` before the Phase 6
persistent fuzzy dictionary changed production sources. The query rows use the same
100,000-term JMH configuration as the Phase 1 fuzzy profile. Build and publication
rows were reproduced from the same commit in a detached temporary worktree.

These short, single-fork WSL2 measurements are local diagnostics, not canonical
release evidence or fixed regression thresholds. Raw JMH JSON remains disposable
under `target/`.

## Environment and protocol

- captured: 2026-08-29, America/Los_Angeles;
- source: `22aef03`;
- OS: Linux 6.6.87.2-microsoft-standard-WSL2, x86_64;
- CPU: Intel Core i7-12700F, 10 cores / 20 logical CPUs;
- JVM: OpenJDK 21.0.12, 64-bit Server VM;
- JMH: 1.37;
- query profile: one fork, two 500 ms warmups, three 500 ms measurements, GC
  profiler;
- build profile: one fork, one 500 ms warmup, three 500 ms measurements, GC
  profiler;
- publication profile: one fork, two 500 ms warmups, three 500 ms measurements, GC
  profiler.

## Fuzzy query baseline

| Scenario | Mean time | Normalized allocation |
|---|---:|---:|
| exact | 44.557 ms/op | 10,505,505 B/op |
| high expansion | 4.598 ms/op | 5,166,914 B/op |
| no match | 34.447 ms/op | 2,763 B/op |

Exact and no-match continue to expose the complete vocabulary scan. The high-expansion
cell length-rejects most terms early and is dominated by 625 accepted expansions and
candidate construction.

## Build and publication baseline

| Workload | Mean time | Normalized allocation |
|---|---:|---:|
| raw build: 10k documents, 16 tokens, 10k vocabulary | 217.068 ms/op | 258,498,192 B/op |
| publish one replacement, 100k vocabulary | 1.764 us/op | 6,896 B/op |
| publish 100 replacements, 100k vocabulary | 432.644 us/op | 666,529 B/op |

The build and 100-replacement latency confidence intervals are wide. Their allocation
figures are stable enough to expose the cost of maintaining an additional persistent
dictionary, while latency remains review evidence rather than a claim.
