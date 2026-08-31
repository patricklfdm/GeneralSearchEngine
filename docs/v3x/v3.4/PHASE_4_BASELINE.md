# V3.4 Phase 4 final-v34 local evidence

Status: local/fake/synthetic calibration complete on
`feat/v3.4-phase4-final-v34`, based on protected-master Phase 3 merge
`34760b326fda6da31a0463d7b4765d6c6da5921c`. This record proves the implementation
and evidence lifecycle before paid execution. It is not cloud performance evidence,
the required two-hour run, a canonical set, or a registered baseline.

## Frozen identity and workload

| Control | Frozen production value |
|---|---|
| Mode / suite / preset | `final-v34` / `v3.4-final-in-memory-suite-v1` / `v3.4-final-in-memory-v1` |
| JVM | `-Xms16g -Xmx16g -XX:+UseG1GC` |
| Cold process | 100,000 documents; 16 tokens; batch 1,000; 5 processes; seed 34; 600 s timeout |
| Extreme corpus | 1,000 documents; 64 tokens; seed 34; all 9 frozen axes |
| Burst matrix | producers `1,4,16` × batches `1,100,1000`; 4 submissions/producer; 64,000 documents; 4 readers; queue 32; 180 s timeout |
| Long-run common | 10,000 documents; 6 readers; 30 s warmup; 60 s windows; 1 s samples; top-K 10; 25 ms steady writes |
| Long-run burst/lifecycle | every 60 s: 4 producers × 100 documents; range/text lifecycle every 120 s; queue 1,000 |
| Canonical duration | 1,800 s; 3 or 5 Standard/GCS members |
| Supplemental duration | 7,200 s; exactly 1 Standard/GCS experiment |
| Per-slot / family cap | 10,800 s / 5 slots |
| Accepted future registration | `v3.4.0-in-memory-cloud` |

The suite combines the already reviewed Phase 2 cold/extreme probes and Phase 3
burst/long-run probes without altering production code. Production evidence must use
the exact values above. A separate `reduced-test` profile exists only for local/CI
harness validation and is rejected by canonical analysis.

## Evidence schema

Each raw member contains `metadata.txt`, immutable lifecycle status, environment facts,
outer checksums, and exactly one `v34-final/` suite directory. That directory contains:

- frozen `suite-config.properties` and matching PASS summary;
- structured cold, extreme, burst, and long-run logs;
- five successful cold process records and one identity summary;
- one complete record for every extreme axis and burst matrix cell; and
- long-run config, raw samples, ordered windows, summary, and an inner SHA-256
  manifest.

The analyzer rejects missing or additional suite files, configuration drift, legacy
JMH/soak content under the preset, failed or incomplete cells, unordered/missing
windows, invalid source/tree identity, and checksum mismatch. Normalized metrics bind
the full suite configuration and duration into the benchmark configuration
fingerprint, so 30-minute and two-hour evidence cannot aggregate.

## Plan and cost calibration

The protected manual workflow now resolves the V3.4 preset for both experiment and
canonical requests and passes it explicitly into the immutable set plan. The dry-run
path proves:

- a three-member canonical set has a 9 VM-hour / 270 vCPU-hour maximum on
  `c3d-standard-30`;
- five members have a 15 VM-hour / 450 vCPU-hour maximum;
- one two-hour experiment still has a three-hour VM cap;
- no more than five slots are accepted; and
- invalid duration, heap, suite, mode, preset, provisioning, or retention controls
  fail before any gcloud mutation.

These are upper bounds, not a request to consume them. No paid resource was created in
Phase 4.

## Retained local verification

`verify-v34-phase4-final-suite.sh` runs one deliberately reduced suite after the JMH
artifact is built. The retained gate completed:

| Surface | Reduced verification |
|---|---|
| Cold process | 2/2 successful processes; stable checksum and corpus digest |
| Extreme corpus | 9/9 axes successful |
| Burst/recovery | 4/4 cells; zero unexpected failures and unresolved futures |
| Long run | 6 seconds, 3 ordered windows, all reader/writer/lifecycle/failure oracles successful |
| Integrity | inner long-run and outer raw SHA-256 manifests verified |

Synthetic analyzer fixtures additionally produce a complete three-member canonical
set, reject one changed frozen parameter, and prove that the only accepted future
baseline name is `v3.4.0-in-memory-cloud`. A correct name still cannot register without
the future verified GCS upload receipt.

All existing cloud workflow, fake-gcloud, set checkpoint, failure, cancellation,
timeout, resume/replace, partial-evidence, upload, cleanup, comparison, and registration
tests remain active. Existing mode plan shapes and preset definitions are asserted
unchanged.

## Decision

- The `final-v34` implementation is ready for protected review and later Phase 5 paid
  execution from an exact final source identity.
- There is no local evidence authorizing a production optimization or API change.
- The required final-source two-hour experiment, canonical cloud set, durable upload,
  registration, final conversion, release, and V4 work remain open.
- The eligible 4/8/16 GiB heap matrix remains an independent V3.4 exit gate.
