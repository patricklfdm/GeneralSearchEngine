# V3.4 Phase 5 final-source evidence

Status: accepted through protected evidence PR #73 at master commit
`fea1547accf896c3a8111ac9cfbb4080a25c5ed5`; exact-merge CI passed in
[run 33529997974](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33529997974).
The reviewed canonical set is registered on the current branch as
`v3.4.0-in-memory-cloud`, pending protected registry review. Every retained result uses
final source commit `52be441f70e7f23195b8b4a0024444d315ee8eaa`, the protected-master merge of PR #72;
its exact-merge CI passed in
[run 33472758082](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33472758082).
No production source changed after this identity was frozen.

## Eligible heap matrix

The independent matrix ran on one Standard GCP `c3d-standard-30` host in
`us-west4-a`, using exact image `ubuntu-2404-noble-amd64-v20260826` with image ID
`5563818848645508791`. The host exposed 30 logical CPUs, 126,603,763,712 physical
bytes, and zero total or active swap. OpenJDK `21.0.12+8-1-24.04-Ubuntu`, equal
`-Xms`/`-Xmx`, and G1 were used for every child JVM.

The exact workload used sparse-vocabulary axis, seed `34`, 100,000 documents, 16 tail
tokens, 1,000 operations, a ten-minute per-cell timeout, and the strict no-swap guard.
The built `target/benchmarks.jar` SHA-256 was
`904ce63c6f4cb88b7cd66a4c9b20aa007c5f23fa30938bb42ec40fa21f5da4cb`.

| Heap | Loaded / peak / live-set bytes | Allocation bytes / bytes per op | GC count / time / pause p95/max | CPU ns | Status |
|---:|---|---|---|---:|---|
| 4 GiB | 105,877,552 / 2,772,867,080 / 104,163,064 | 6,901,996,776 / 6,901,996.776 | 3 / 4 ms / 2/2 ms | 23,080,000,000 | success |
| 8 GiB | 105,309,592 / 3,307,529,624 / 103,595,104 | 6,901,724,208 / 6,901,724.208 | 3 / 3 ms / 1/1 ms | 24,300,000,000 | success |
| 16 GiB | 105,035,464 / 3,402,479,304 / 103,320,976 | 6,901,422,880 / 6,901,422.880 | 4 / 4 ms / 2/2 ms | 23,440,000,000 | success |

All three cells produced snapshot version `100`, two indexes, 3,600,000 generated
tokens, 1,000 result sets, zero retained cursors, checksum
`-5900766649474570239`, and corpus digest
`10ef91cdb4ec3249eadd6114443ff82a79d78957a600da24e58414e3faeefdf7`.
The runner emitted `heapMatrix=SUCCESS cells=3 documents=100000 tokens=16
operations=1000`.

The retained text evidence SHA-256 is
`2481e9c7943215f11c14bacc07f3a1c13c9aab8b67033b87f243a3c70b0eff58`; its
downloaded checksum matched. The instance was explicitly deleted and a subsequent
describe returned no instance. This diagnostic does not enter the frozen canonical
member file set and creates no cloud baseline identity.

## Required two-hour experiment

[Cloud run 33474186962](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33474186962)
completed as a one-member Standard `c3d-standard-30`, GCS-retained `final-v34`
experiment with preset `v3.4-final-in-memory-v1` and an exact 7,200-second window.

| Identity | Value |
|---|---|
| Raw run | `20260901T053806Z-52be441f70e7-final-v34` |
| Set | `gse-set-v1-d8091283262ff11a1287132c3ebd6cd2fbe331ac9b5cfd43156651732305cde5` |
| Status | `VALID_EXPERIMENT` / `VALID_EXPERIMENT_SET` |
| Configuration fingerprint | `sha256:baa554e6eefa10aa205befb6dca775ba29e7feb8c7eebcf0fbc65251ac42e73d` |
| Environment fingerprint | `sha256:f201758392398c491e1a63daa42fa27b56221ebbb64c7fbf22db5fb4c35559d0` |
| Manifest / metrics | `sha256:a7b5d2e4595a7a1d54cf9d25cde66143d7bab1f8125fabdf7e321db61e8393dc` / `sha256:66f5d35ca9ee4cd05839a272b330b07a7862fe24cdf3169d5e159c56bbe12e9d` |
| Upload receipt | `gse-upload-receipt-v1-9e0d5cd4dd4aa6bd3c4a0cbf0f73808b495cd7d11011d4696929454bf8e2f9c3` |
| GCS objects | 25 unique objects |

The run completed all five cold processes, nine extreme axes, nine burst/recovery
cells, and 120 ordered long-run windows. It recorded 111,165,927 reads, 283,421 write
batches, 330,941 write mutations, 120 bursts, 60 lifecycle cycles, queue maximum `1`,
2,432 GCs taking 4,308 ms, one expected failure, zero unexpected failures, zero
unresolved futures, and the frozen final corpus digest. Artifact recovery, raw and
derived checksums, immutable upload, and VM cleanup all passed without interruption or
warning.

## Three-member canonical set

[Cloud run 33483714195](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33483714195)
completed three independent Standard `c3d-standard-30` members with GCS retention and
the fixed 1,800-second canonical window.

| Identity | Value |
|---|---|
| Set | `gse-set-v1-10aefc2272347b087adccc8dbc91fc87368a92560037a8e1d9751210e2c533e6` |
| Status | `VALID_CANONICAL_SET`; 3/3 `VALID_CANONICAL_MEMBER` |
| Configuration fingerprint | `sha256:222ca397e3473a5afcc03bb64b152a1d9abb4523ddcd61339bcec6c1bc7409c5` |
| Environment fingerprint | `sha256:f201758392398c491e1a63daa42fa27b56221ebbb64c7fbf22db5fb4c35559d0` |
| Aggregate metrics | 219 metrics; `sha256:f2dc1a401b3a98dbad6e49896a24c0d12b560a00da42bb07a9d2c45c89b88c47` |
| Upload receipt | `gse-upload-receipt-v1-b6d7c89163b2a5cfba4c2d51205c084bb0b402b5d333e9aa9556940cbb33db2d` |
| GCS objects | 67 unique objects: 48 raw, 9 derived, 6 orchestration, 4 set |

| Slot / raw run | Manifest SHA-256 | Metrics SHA-256 | Reads / writes | Review p99 median | GC count/time |
|---|---|---|---|---:|---|
| 1 / `20260901T074822Z-52be441f70e7-final-v34` | `adaaf43729fe09e0112ccdc37fe5daf293e63cb638f22c23ae62e65ee1d3f1b5` | `302b8e8982b6599dc5d7ba8e6bacd6f5d545f1cfc7c13fa735c8580c90389d9b` | 28,364,410 / 82,771 | 0.618210 ms | 624 / 1,081 ms |
| 2 / `20260901T082148Z-52be441f70e7-final-v34` | `0656fd9a111a9fb859c49ce6e6c93703ae77c735e781329f3249afe921733180` | `a9cd2909f6839475a6a2dcd2d4ba5d69f1fa53cdc8483ea3f197de445cafcc60` | 28,191,694 / 82,733 | 0.630990 ms | 620 / 1,072 ms |
| 3 / `20260901T085517Z-52be441f70e7-final-v34` | `2687ba3e638cb43dc7342ce6349952ca6757e819dad298833c9549cbfad17ca5` | `d6c05afb7bfd9d3463e08e63bffc3f27952b48297e8111968e6434d15bd1dace` | 27,834,087 / 82,790 | 0.631420 ms | 618 / 1,032 ms |

Every member completed 30 ordered windows, five cold processes, nine extreme axes,
nine burst cells, 30 bursts, 15 lifecycle cycles, one expected failure, zero
unexpected failures, zero unresolved futures, and queue maximum `1`. All three used
the same source, image, Java/JVM, suite, preset, environment fingerprint, configuration
fingerprint, metric schema, and corpus identities. Each slot selected attempt 1 with
no replacement or exclusion; artifact recovery, nested checksums, GCS upload, and VM
cleanup passed.

The reviewed long-window p99 medians span about 2.1%, read totals span about 1.9%, and
write totals differ by fewer than 0.1%. Some near-zero short-burst values have large
relative ranges, but their absolute values remain small and all frozen correctness,
completion, rejection, drainage, and liveness oracles pass. V3.4 freezes no universal
numeric threshold, and the retained windows show no unexplained sustained drift.

## Baseline registration

The append-only registry now records the reviewed set under the independent identity
`v3.4.0-in-memory-cloud`. Existing `v3.0.0-cloud` and
`v3.1.0-ranked-cloud` entries remain exactly unchanged from their protected-master
values.

| Registry field | Value |
|---|---|
| Release label | `v3.4.0 final in-memory reviewed cloud baseline` |
| Source commit | `52be441f70e7f23195b8b4a0024444d315ee8eaa` |
| Evidence profile | `canonical` |
| Set ID | `gse-set-v1-10aefc2272347b087adccc8dbc91fc87368a92560037a8e1d9751210e2c533e6` |
| Configuration fingerprint | `sha256:222ca397e3473a5afcc03bb64b152a1d9abb4523ddcd61339bcec6c1bc7409c5` |
| Environment fingerprint | `sha256:f201758392398c491e1a63daa42fa27b56221ebbb64c7fbf22db5fb4c35559d0` |
| Manifest generation | `1788255068286343` |
| Set-manifest SHA-256 | `sha256:55a19b274c3b7225d630d977bb396357dc5b80f560068a747b19ac7138dfcc70` |
| Upload receipt | `gse-upload-receipt-v1-b6d7c89163b2a5cfba4c2d51205c084bb0b402b5d333e9aa9556940cbb33db2d` |
| Upload-receipt SHA-256 | `sha256:3f54a3977931daa7b38893d7069c6dd1ca79d21e17e7caaee0712dd850dfa4f8` |

Registry schema validation and explicit append-only comparison both pass locally with
Python 3.11. The registration becomes the protected project record only after this
branch merges and its exact-master CI succeeds.

## Decision

- The eligible heap matrix and required two-hour experiment are accepted.
- The three-member set is accepted through protected evidence review and registered
  on this branch as `v3.4.0-in-memory-cloud`.
- Protected review of the append-only registry change remains required before Phase 6.
- No result justifies a production change, public API change, SLA, or V4 implementation.
- Phase 6 remains blocked until the registration commit merges and exact-master CI passes.
