# V3.4 Phase 2 local diagnostics

Status: retained local evidence complete on
`feat/v3.4-phase2-local-diagnostics`. The branch starts from protected-master Phase 1
merge `331284bd70b0234b97bb43cf693dd10af8e9b7e1`. These results validate local
diagnostic surfaces; they are not cloud members, release evidence, or an eligible
replacement for the required heap matrix.

## Environment

| Property | Value |
|---|---|
| Base source | `331284bd70b0234b97bb43cf693dd10af8e9b7e1` plus the Phase 2 working tree |
| OS | Linux `6.6.87.2-microsoft-standard-WSL2`, x86-64 |
| CPU | Intel Core i7-12700F, 10 cores / 20 logical CPUs |
| Physical memory visible to JVM | 16,681,971,712 bytes |
| Swap | 4,294,967,296 bytes total; 287,322,112 bytes used during capture |
| JVM | OpenJDK 21.0.12, Ubuntu `21.0.12+8-1-22.04-Ubuntu` |
| Collector for explicit heap cells | G1 |

Dependency resolution and compilation are outside every process timing.

## Cold construction

Both retained configurations use seed `34`, 16 tail tokens per text field, 1,000
documents per ingestion batch, sparse vocabulary, four final indexes, and five
independent JVMs. `process` values begin immediately before JVM launch; `probe` values
begin at the first line of the child `main`. `ready` ends after initial equality/text
indexes exist; `total` additionally includes the verified first query, dynamic
equality/text replay, and engine close.

Command shape:

```bash
java -cp target/benchmarks.jar \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V34ColdBuildProcessRunner \
  --documents=<100000|1000000> --tokens=16 --batch-size=1000 \
  --repeats=5 --seed=34 --timeout-seconds=600
```

| Documents | Run | Process ready | Probe ready | Process total | Probe total |
|---:|---:|---:|---:|---:|---:|
| 100,000 | 1 | 1,244,996,413 | 1,209,099,807 | 1,829,777,492 | 1,745,716,610 |
| 100,000 | 2 | 1,135,387,245 | 1,102,575,898 | 1,588,333,930 | 1,522,063,181 |
| 100,000 | 3 | 1,092,327,577 | 1,058,753,510 | 1,709,650,214 | 1,639,226,443 |
| 100,000 | 4 | 1,070,138,912 | 1,037,438,534 | 1,603,615,884 | 1,532,567,108 |
| 100,000 | 5 | 1,060,256,201 | 1,026,846,516 | 1,596,942,757 | 1,524,146,449 |
| 1,000,000 | 1 | 35,088,469,680 | 35,049,280,527 | 39,513,497,413 | 39,375,257,612 |
| 1,000,000 | 2 | 34,975,985,863 | 34,940,696,426 | 39,077,812,362 | 38,946,083,209 |
| 1,000,000 | 3 | 34,938,726,723 | 34,905,127,475 | 39,128,013,034 | 39,000,169,786 |
| 1,000,000 | 4 | 34,839,117,306 | 34,803,152,046 | 39,127,039,537 | 38,997,594,532 |
| 1,000,000 | 5 | 34,923,699,201 | 34,890,183,489 | 39,191,821,442 | 39,067,160,933 |

| Documents | Probe ready median/CV | Probe total median/CV | Process ready median/CV | Process total median/CV | Corpus digest |
|---:|---:|---:|---:|---:|---|
| 100,000 | 1,058,753,510 / 0.061059 | 1,532,567,108 / 0.055367 | 1,092,327,577 / 0.060101 | 1,603,615,884 / 0.055947 | `10ef91cdb4ec3249eadd6114443ff82a79d78957a600da24e58414e3faeefdf7` |
| 1,000,000 | 34,905,127,475 / 0.002287 | 39,000,169,786 / 0.003938 | 34,938,726,723 / 0.002321 | 39,128,013,034 / 0.004008 | `36965216d28567ce427cc131f33229bad97fab44cf1ad14675e67110fade5375` |

Every run produced checksum `5521978693839043314`. The digest and checksum were
identical within each repeated configuration; no timeout, partial checkpoint,
resource exhaustion, or invalid output entered the summaries.

## Extreme-corpus matrix

The retained command used 1,000 documents, 64 generated tail tokens per text field,
seed `34`, 500 expected eligible matches, and all nine independent axes.

```bash
java -cp target/benchmarks.jar \
  io.github.patricklfdm.generalsearch.benchmark.jmh.V34ExtremeCorpusProbe \
  --documents=1000 --tokens=64 --seed=34 --axis=all
```

| Axis | Corpus digest | Combined checksum | Status |
|---|---|---:|---|
| long-text | `25e1b410658ef05dce8324f6e683538ab61e084129014cee15fcd565f2c756a9` | 8472602110984147248 | success |
| high-frequency | `573cbc7e89b9001059f722846ff488b0acaed272bb5d525bcc5fd8324a743798` | -8996425654573055639 | success |
| large-vocabulary | `dd033cb0353407600a8297d043e0cfa4cd4eded834c4266f62bb452a6db4f41e` | -8744338620007287408 | success |
| sparse-vocabulary | `58ec7d02018a2ac162cd9c66d075ff322597b8e62fb665281c82c769177f8e1f` | 8026166715841367057 | success |
| zipf-heavy | `77d2e11c7d1332edad66a8d00b1f82aad4af4b5114db104011baaf82fb56dc0b` | 8148060064892311426 | success |
| multiple-fields | `44f17eaf5dcd2e84e1b138144c605acd2a0e04575eefe8a57f432a57facc9f2e` | 9153827781765358445 | success |
| unicode-heavy | `ae20e3336f326ed93cbbb97527357424ea3bd8a92defd2d2e107092c753b79b6` | 7050289548729518431 | success |
| repeated-terms | `cfd9b59d7df54a43027fe7783203d56ccdad265f7f5dadb01254fe8a228aca5e` | -6744379879978220388 | success |
| position-heavy | `7c3490f2adf3a04436b66596e6e3266753ed09cf3b07ba4084b177b99ec18968` | 7349707187054276562 | success |

The combined nine-axis checksum is `5552394216862102831`. Each component also emitted
and validated hit, Explain, highlight, page, fuzzy, and secondary-field checksums.

## Heap matrix and environment decision

The required `4g`/`8g`/`16g` command used equal `-Xms`/`-Xmx`, G1, 100,000 documents,
16 tail tokens, 1,000 search operations, and `require-no-swap=true`.

| Heap | Result | Exact reason |
|---:|---|---|
| 4g | invalid environment | 287,322,112 bytes of host swap already in use |
| 8g | invalid environment | 287,322,112 bytes of host swap already in use |
| 16g | invalid environment | max heap 17,179,869,184 bytes exceeds visible physical memory 16,681,971,712 bytes |

The runner returned `heapMatrix=NON_PASSING` and non-zero exit as designed. These cells
are controlled rejections, not successful measurements. A 32g cell was not attempted
because it is even further outside the physical-memory contract.

For harness calibration only, swap rejection was relaxed on 4g and 8g. Both cells used
the same corpus digest
`10ef91cdb4ec3249eadd6114443ff82a79d78957a600da24e58414e3faeefdf7`
and checksum `-5900766649474570239`:

| Heap | Loaded | Peak | Released | Live set | Allocated | Bytes/op | GC count/time | Pause p95/max | Process CPU |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4g | 105,746,512 | 2,761,030,376 | 2,386,200 | 104,033,800 | 6,904,825,648 | 6,904,825.648 | 2 / 4 ms | 2 / 2 ms | 22,800,000,000 ns |
| 8g | 105,511,816 | 3,286,104,968 | 2,386,160 | 103,799,104 | 6,900,784,304 | 6,900,784.304 | 3 / 5 ms | 2 / 2 ms | 24,010,000,000 ns |

Peak heap is diagnostic and includes allocation pressure between GCs; allocated bytes
are cumulative thread allocation, not retained heap. Empty/loaded/released controls
use three explicit GC requests separated by 25 ms. The no-swap-relaxed results prove
the sampler, workload, checksum, and release checkpoints only and are ineligible for a
V3.4 heap pass.
Both cells emitted 1,000 result sets and zero retained pagination cursors.

## Decision

- Cold 100k and 1M construction surfaces are accepted as local Phase 2 evidence.
- All nine extreme-corpus correctness cells are accepted.
- No production bug or optimization is justified by these results.
- Heap instrumentation and fail-closed classification are accepted, but the eligible
  `4g`/`8g`/`16g` heap matrix remains an open V3.4 exit gate for a machine with
  sufficient physical memory and no swapping.
- Phase 2 creates no cloud evidence and authorizes no paid run.
