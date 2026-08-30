# V3.1 Phase 7 local calibration

## Purpose and eligibility

This is a bounded local feasibility check for the `v3.1-ranked-v1` workload plan. It
is not canonical evidence, a latency baseline, or a substitute for the required 1M
Standard C3D runs.

The calibration was captured on 2026-08-29 under WSL2 with OpenJDK 21.0.12, 20 logical
CPUs, approximately 15 GiB total memory, and approximately 8.5 GiB available at the
start. Each representative row used 100,000 documents or vocabulary terms, one
non-forked 100 ms measurement, and an outer `-Xms1g -Xmx6g` JVM. Wall time and maximum
RSS therefore describe setup feasibility only.

| Representative fixture | Wall time | Maximum RSS |
|---|---:|---:|
| phrase, high frequency, slop 4 | 1.32 s | 1,127,088 KiB |
| BOOL, width 64, all, with MUST | 1.45 s | 1,204,308 KiB |
| fuzzy, supplementary Unicode near hit | 0.93 s | 552,396 KiB |
| publication, 100 added memberships | 0.97 s | 651,888 KiB |
| mixed concurrency, 16 readers and one writer | 5.76 s | 2,021,928 KiB |

All setup guards passed. The mixed trial observed queue depth at most one and teardown
verified a final depth of zero. Its short operation rates are deliberately not used as
performance claims.

## Runtime budget

The frozen matrix has 84 entries. Two forks with three one-second warmups and five
one-second measurements consume exactly 1,344 seconds, or 22 minutes 24 seconds, of
scheduled JMH iteration time. The 3,600-second VM cap therefore leaves 37 minutes 36
seconds for checkout, bootstrap, Maven build, trial setup, GC, result checksums,
recovery, and cleanup.

The 100k setup observations support proceeding to one paid calibration member, but
they do not prove the 1M set fits the cap. The workflow must fail rather than silently
drop cells or increase the cap if the calibration member exceeds it.

## Heap decision

The 100k mixed fixture reached about 1.93 GiB RSS. A naive scale projection makes the
old 16 GiB production heap unsafe for the required 1M four-field fixture. The distinct
feature preset therefore freezes `-Xms32g -Xmx64g` on the reviewed 120 GiB C3D-30
machine. This changes the feature configuration and environment fingerprints by
design. It does not modify any existing regression preset or permit cross-family
comparison.

The local host does not have enough spare memory to run the frozen 1M mixed cell
without material OOM or host-swap risk, so no local 1M result is claimed. That cell is
intentionally deferred to the protected Standard-VM calibration after merge.
