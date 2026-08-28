# Cloud Benchmark V2 Phase 3 baseline comparison and reports

## Status and authority

This document freezes the Phase 3 implementation contract before comparison code is
written. It specializes the normative
[Phase 0 evidence model](CLOUD_BENCHMARK_V2_PHASE_0.md) and consumes the Phase 1 run
artifacts and [Phase 2 set artifacts](CLOUD_BENCHMARK_V2_PHASE_2.md). Phase 0 wins if
these documents conflict. Implementation must amend this contract in focused review
instead of silently changing compatibility, classification, or registry semantics.

Phase 3 adds deterministic local comparison and reporting. It creates no VM, bucket,
GCS object, IAM binding, upload receipt, workflow dispatch, performance gate, or search
engine behavior. A reported regression is evidence for review, not a failed command.

## Goals and boundaries

Phase 3 must provide:

- a thin public `compare-cloud-benchmark.sh` wrapper;
- strict validation of local Phase 1 derived runs and Phase 2 completed sets;
- canonical set-to-set direct comparison;
- explicitly requested exploratory run/set comparison;
- deterministic compatibility decisions and policy-versioned metric classifications;
- canonical `comparison.json`, human-readable `comparison.md`, and checksums;
- the tracked baseline-registry schema plus read-only validation, listing, and local
  resolution.

Phase 3 must not:

- select, rerun, trim, or modify any benchmark member;
- compare console text instead of normalized metrics;
- treat a run, Spot evidence, or experiment set as a canonical baseline;
- weaken an environment or configuration mismatch to obtain a performance result;
- register a local path or a placeholder upload as a durable baseline;
- fail solely because a metric is classified `WARNING` or `POSSIBLE_REGRESSION`;
- implement upload, automatic baseline selection, threshold configuration, or a hard
  performance gate.

## User-facing commands

Compare two local completed sets with direct canonical semantics:

```bash
./compare-cloud-benchmark.sh \
  benchmark-results/v3-production/sets/BASELINE_SET_ID/v1 \
  benchmark-results/v3-production/sets/CANDIDATE_SET_ID/v1
```

Permit only the frozen exploratory exceptions with an explicit flag:

```bash
./compare-cloud-benchmark.sh --allow-exploratory BASELINE CANDIDATE
```

List and validate the tracked baseline registry without contacting GCS:

```bash
scripts/cloud/list-baselines.sh
python3 scripts/cloud/benchmark_v2.py registry-validate \
  docs/v3/cloud-benchmark-baselines.json
```

`BASELINE` and `CANDIDATE` may identify either:

- a Phase 2 `v1` set directory;
- its `benchmark-set-manifest.json`;
- a Phase 1 `v1` derived-run directory;
- its `benchmark-manifest.json`.

Only the baseline operand may be a registry name. A named registry entry resolves to
the canonical local set directory
`benchmark-results/v3-production/sets/<setId>/v1`. Phase 3 never downloads from the
entry's GCS URI. If the exact local set is unavailable or its digest contradicts the
entry, resolution fails precisely rather than falling back to another set.

An existing filesystem operand takes precedence over registry-name interpretation. A
nonexistent baseline operand is treated as a registry name only when it matches the
frozen name grammar; otherwise it is a missing-path configuration error.

Operands are ordered. Reversing them creates a different scientific question and a
different comparison ID. Options after the first positional operand are rejected so
that a path beginning with a hyphen cannot be interpreted ambiguously.

## Input validation and immutable evidence

Phase 3 reads only finalized evidence. It never writes below a run or set input.

A set operand requires exactly:

```text
benchmark-set-manifest.json
aggregate-metrics.json
set-attempt-audit.json
set-checksums.sha256
```

Validation reuses the Phase 2 file-set and checksum rules, then additionally requires:

- manifest `kind=benchmark-set`, `schemaVersion=1`, and a supported final status;
- directory name and manifest `setId` agreement;
- manifest aggregate path, digest, count, suite, and set ID agreement;
- aggregate `kind=aggregate-benchmark-metrics` and `schemaVersion=1`;
- unique sorted metric IDs and exact declared member count;
- finite numeric fields and complete aggregation fields;
- categorical consensus fields with internally consistent distinct/unanimous values.

A run operand requires exactly the Phase 1 `benchmark-manifest.json`,
`normalized-metrics.json`, and `derived-checksums.sha256`. Validation requires supported
schema 1, verifies both derived digests, manifest/metrics run ID and suite agreement,
unique sorted metric IDs, and finite canonical values. Historical raw schema 0 may be
represented only through a valid Phase 1 `VALID_EXPERIMENT` manifest and remains
exploratory.

Portable member references are evidence, not permission to search arbitrary paths.
Phase 3 resolves them only below the configured local results root, rejects traversal
and symlinks that escape that root, and never infers a missing file from timestamps or
console output.

Malformed JSON, missing/checksum-invalid files, or unreadable evidence exits `80`.
Unsupported kind/schema exits `81`. Duplicate metric identity, digest contradiction,
or an internally impossible manifest exits `82`. No final comparison directory is
created for invalid evidence.

## Common comparison view

The Python utility converts a validated run or set into an internal comparison view.
This view is not an additional stored artifact.

For a set, every numeric metric contributes its recorded median and
`relativeRangePct`; categorical metrics contribute their consensus. For a run, every
numeric metric contributes its canonical run-level value and an unavailable variation
reason of `single_run_has_no_independent_variation`; categorical metrics become a
one-value consensus.

Every view retains:

```text
evidence kind and immutable identity
manifest and metrics digests
source repository and exact commit
evidence profile and final status
mode and preset
suite name/schema
environment fingerprint
benchmark configuration fingerprint
metric identity/statistic/unit/direction/aggregation semantics
```

Branch, timestamps, project ID, instance name, IP address, local path, workspace ID,
and registry display name remain provenance only. They do not change metric arithmetic
or the comparison ID.

## Compatibility decision version 1

Compatibility is decided before performance classification and has exactly these
states:

```text
DIRECTLY_COMPARABLE
COMPARABLE_WITH_WARNINGS
INCOMPARABLE
INVALID
```

`INVALID` is reserved for evidence that failed validation. It is not a softer spelling
of `INCOMPARABLE`.

### Direct comparison

`DIRECTLY_COMPARABLE` requires:

- two `VALID_CANONICAL_SET` inputs;
- supported equal manifest, aggregate, suite, and policy schema versions;
- the same source repository, mode, preset, suite, benchmark configuration
  fingerprint, and environment fingerprint;
- the same complete metric ID set;
- exact equality for every metric's identity, statistic, unit, direction, percentile,
  and aggregation kind.

Source commits are expected to differ and never block comparison. Member counts may
differ when both sets independently satisfy the canonical minimum. Set IDs, member run
IDs, attempt history, timestamps, branches, and GCP project IDs are not compatibility
requirements.

### Explicit exploratory comparison

Without `--allow-exploratory`, any non-direct pair is `INCOMPARABLE`. The flag does not
turn arbitrary differences into comparable evidence. It permits
`COMPARABLE_WITH_WARNINGS` only for:

- a derived run on one or both sides;
- a `VALID_EXPERIMENT_SET` on one or both sides;
- canonical versus experiment evidence when the remaining scientific identity agrees;
- Spot versus Standard provisioning when every other environment field agrees.

Run views always add `single-run evidence has no independent-run variation`. Spot
evidence adds `provisioning models differ; comparison is exploratory`. Results in this
state cannot support registry registration or a future performance gate.

Even with the flag, these differences remain `INCOMPARABLE`:

- repository, mode, preset, suite, or supported schema;
- benchmark configuration fingerprint;
- provider, zone, machine type, CPU identity/topology, memory, resolved image identity,
  kernel, exact JDK/VM build, or ordered JVM options;
- metric ID set, identity, statistic, unit, direction, percentile, or aggregation kind.

To distinguish the provisioning-only exception from another environment mismatch,
Phase 3 validates and compares the environment object from a representative member
manifest. All members are already fingerprint-equal within a valid Phase 2 set. A
missing representative manifest prevents this exception; it is never guessed from a
set ID or machine name.

Reasons and warnings use stable machine-readable codes, are deduplicated, and are
lexicographically sorted in JSON. Markdown may render friendlier text from the codes.

## Comparison policy version 1

The policy identity is `gse-comparison-policy-v1`. Policy is repository-owned and has
no CLI threshold override in Phase 3.

The fixed classification vocabulary is:

```text
MATERIAL_IMPROVEMENT
IMPROVEMENT
NEUTRAL
WARNING
POSSIBLE_REGRESSION
INCOMPARABLE
INVALID
```

A metric may have `classification=null` with an explicit reason when no honest ordered
policy applies. Null is not an eighth classification.

### Continuous performance metrics

Policy `continuous-relative-v1` applies only to known latency, throughput, and
allocation-per-operation metrics whose normalized direction is `lower` or `higher`.
Known statistics are:

```text
mean_time
sample_mean
sample_percentile_*
throughput
allocation_per_operation
```

For finite nonzero baseline median and available relative variation on both sides:

```text
absoluteDelta = candidateMedian - baselineMedian
deltaPct = absoluteDelta / abs(baselineMedian) * 100
variationPct = max(baselineRelativeRangePct, candidateRelativeRangePct)
neutralLimitPct = max(5, variationPct)
materialLimitPct = max(10, 2 * variationPct)
benefitPct = deltaPct                 when direction = higher
benefitPct = -deltaPct                when direction = lower
```

Classification is deterministic:

- `abs(benefitPct) <= neutralLimitPct` is `NEUTRAL`;
- beneficial outside neutral but below material is `IMPROVEMENT`;
- beneficial at or above material is `MATERIAL_IMPROVEMENT`;
- harmful outside neutral but below material is `WARNING`;
- harmful at or above material is `POSSIBLE_REGRESSION`.

Equality at the neutral threshold remains `NEUTRAL`. Equality at the material
threshold enters the material class. No display rounding occurs before classification.

If the baseline median is zero, `deltaPct`, thresholds, and classification are null
with reason `baseline_median_zero`. If either relative variation is unavailable,
classification is null with reason `independent_variation_unavailable`. This includes
run-to-run and run-to-set views; Phase 3 does not substitute fork confidence intervals
or the fixed five-percent floor for missing independent-run evidence.

Sample percentiles remain `median_of_run_percentile`. Reports must not call them pooled
request percentiles. Confidence intervals are not synthesized across runs.

### Categorical and diagnostic metrics

Policy `health-consensus-v1` recognizes evidence-health facts:

- `errors` must be unanimously numeric zero;
- `analysis_status` must be unanimously `VALID`;
- `status` must be unanimously `PASS` where it is exposed as a metric;
- `review_required` and `flag_*` are healthy only when unanimously `false`.

An unhealthy baseline is `INVALID`; an unhealthy candidate is `INVALID` except
`review_required=true` or `flag_*=true`, which is `WARNING`. Matching healthy values are
`NEUTRAL`. Non-unanimous health consensus is `INVALID`. No percentage is calculated.

Other categorical metrics use `categorical-observation-v1`: equal unanimous values are
`NEUTRAL`; changed or non-unanimous values have null classification with reason
`categorical_change_has_no_ordered_policy`.

Diagnostic counters, allocation rate, GC totals/time, drift, queue depth, heap growth,
and unknown metrics use `diagnostic-only-v1`. Their baseline and candidate values are
reported, but classification is null and they do not affect classification counts.
Unknown metric IDs are never silently assigned a generic lower-is-better rule.

### Overall summary and exit behavior

The JSON summary counts every non-null metric classification plus `unclassified`.
It does not combine metrics into a score, choose one headline metric, or translate a
count into a pass/fail result.

`WARNING`, `POSSIBLE_REGRESSION`, and metric-level `INVALID` findings are reported with
process exit `0` when the two evidence inputs were valid and comparable. A future policy
gate may choose otherwise, but Phase 3 does not.

## Comparison identity and output layout

The comparison identity payload has schema version 1 and contains only:

```text
ordered baseline evidence kind, immutable ID, manifest digest, and metrics digest
ordered candidate evidence kind, immutable ID, manifest digest, and metrics digest
comparison policy ID/schema version
requested mode: direct or exploratory
```

The ID is:

```text
gse-comparison-v1-<SHA-256 of the canonical identity payload>
```

Registry name, local path, timestamps, report formatting environment, and output
directory are excluded. Direct and exploratory requests intentionally have different
IDs because their compatibility claims differ.

Completed output is written atomically to:

```text
benchmark-results/v3-production/comparisons/<comparison-id>/v1/
  comparison.json
  comparison.md
  comparison-checksums.sha256
```

An existing directory succeeds only if the exact expected file set and every byte are
identical. Otherwise it exits `82`. Invalid evidence produces no completed directory.

## `comparison.json` schema version 1

The canonical JSON document records:

- `schemaVersion=1`, `kind=benchmark-comparison`, comparison ID, and
  `status=COMPLETE`;
- policy ID/schema and requested direct/exploratory mode;
- compact baseline and candidate evidence identities, source commits, profiles, modes,
  suites, fingerprints, member counts, and manifest/metric digests;
- compatibility status, sorted reason codes, and sorted warnings;
- metrics sorted by metric ID;
- exact baseline/candidate values, absolute delta, percentage delta, variation,
  thresholds, policy ID, classification, and explicit unavailable reason;
- deterministic classification counts and unclassified count.

The document contains no generated timestamp, local absolute path, username, registry
display name, Markdown rounding, or mutable GCS lookup result. It uses the Phase 0
canonical JSON serialization and one trailing newline.

For a valid but incomparable pair, JSON and Markdown are still generated with
compatibility `INCOMPARABLE`; metric arithmetic and performance classifications are
omitted, `metrics=[]`, and `metricsCompared=0`. A direct request then exits `84`.
Invalid input does not create a final comparison artifact.

## `comparison.md` report contract

Markdown is a deterministic rendering of `comparison.json`, never a separately parsed
source. It contains:

1. title and comparison ID;
2. baseline and candidate evidence/source summaries;
3. an explicit compatibility status with warnings/reasons;
4. classification counts;
5. a continuous-performance table;
6. categorical/health findings;
7. diagnostic and unclassified observations;
8. evidence limitations and the statement that Phase 3 is not a hard gate.

Tables show canonical units and clearly label `median of run percentiles` where
applicable. Display values use a fixed locale-independent formatter and at most six
decimal places without changing JSON arithmetic. Markdown escapes pipes, backslashes,
control characters, and line breaks from evidence-derived labels. It ends with one
newline and contains no generated-at time.

## Baseline registry schema and Phase 5 boundary

The tracked registry path remains:

```text
docs/v3/cloud-benchmark-baselines.json
```

Phase 3 initializes and validates this canonical schema-1 document:

```json
{"baselines":{},"kind":"cloud-benchmark-baseline-registry","schemaVersion":1}
```

Baseline names match `[a-z0-9][a-z0-9._-]{0,63}`. Entries are keyed by name and contain
only the Phase 0 fields:

```text
set ID and set-manifest SHA-256
canonical evidence profile
source commit and optional reviewed release label
environment and benchmark-configuration fingerprints
immutable gs:// set-manifest URI and numeric object generation
upload-receipt ID and SHA-256
```

Set IDs match `gse-set-v1-<64 lowercase hex>`. Receipt IDs match
`gse-upload-receipt-v1-<64 lowercase hex>`. SHA-256 fields use
`sha256:<64 lowercase hex>`. Commits are exact 40-character lowercase Git IDs. Object
generation is a nonzero decimal string so JSON/JavaScript integer limits cannot change
it. The immutable manifest URI is exactly below:

```text
gs://<bucket>/general-search-engine/sets/<setId>/v1/benchmark-set-manifest.json
```

An optional reviewed release label is a non-empty single-line UTF-8 string of at most
100 characters. It is human provenance and never replaces the measured source commit.

The registry is canonical JSON with sorted names, no duplicate keys, no local paths,
no raw metrics, no credentials, and no timestamps. Listing is lexicographically sorted.
Resolution validates every field and requires the local set to match the registered set
ID, manifest digest, profile, commit, and fingerprints.

Phase 0 requires a verified durable upload receipt before registration, but Phase 5 is
the first phase that creates and remotely verifies such receipts. Therefore Phase 3 is
strictly read-only for the tracked registry:

- it ships schema validation, listing, named lookup, and immutable-name validation
  primitives;
- it may test non-empty registry fixtures with synthetic structurally valid receipt
  references;
- it does not ship `register-cloud-baseline.sh` and does not add a real baseline entry;
- Phase 5 adds the mutating registration command only after freezing and implementing
  the upload-receipt schema and verification path.

This is a dependency boundary, not a relaxation. Manual editing that omits a receipt is
invalid. A later registration command must reject replacement of an existing name; a
superseding baseline uses a new reviewed name.

Registry syntax, missing names, invalid immutable URIs/generations, local-set mismatch,
or immutable-name conflict exits `85`. Lack of a local copy for a named baseline also
exits `85` in Phase 3 because automatic GCS retrieval is not implemented.

## Exit codes

Phase 3 preserves the Phase 0 analysis exit model:

| Exit | Meaning |
|---:|---|
| `0` | comparison/report completed, including warnings or suspected regressions |
| `2` | CLI, operand, or local output configuration error |
| `80` | missing, malformed, checksum-invalid, or unreadable evidence |
| `81` | unsupported evidence kind, schema, or policy version |
| `82` | contradictory evidence, duplicate metric identity, or output collision |
| `84` | valid evidence is not comparable under the requested mode |
| `85` | registry schema, lookup, local binding, or immutable-name validation failed |

Exit `83` remains owned by Phase 2 incomplete/incompatible set construction. Exit `86`
remains reserved for Phase 5 upload failures. Performance classifications never become
process exits in Phase 3.

## Safety and no-cost implementation gates

Phase 3 implementation must not create a VM or contact GCS. Tests use temporary
directories and synthetic valid Phase 1/2 artifacts. Required coverage includes:

- byte-stable comparison ID, JSON, Markdown, checksums, and idempotent collision;
- two canonical sets with different source commits and identical fingerprints;
- baseline/candidate ordering and reversed comparison identity;
- direct rejection of run views, experiment sets, and Spot/Standard mismatch;
- explicit exploratory run/run, run/set, experiment, and provisioning-only warnings;
- machine, zone, CPU/topology, memory, image, kernel, JDK/VM, JVM-option, suite, mode,
  preset, configuration, metric-set, identity, unit, direction, percentile, and
  aggregation-kind mismatch;
- lower/higher direction, neutral/material threshold equality, variation dominance,
  and fastest/slowest candidate values without member selection;
- baseline zero, unavailable variation, sample-percentile labeling, and no invented
  confidence interval;
- health consensus, categorical changes, diagnostic values, and unknown metrics;
- a synthetic harmful 20-percent latency change classified as
  `POSSIBLE_REGRESSION` with exit `0`;
- malformed JSON, missing files, checksum corruption, duplicate metric IDs, digest
  contradiction, unsupported schemas, and conflicting existing output;
- empty and non-empty registry fixtures, name validation, sorted listing, duplicate
  names, invalid GCS/generation/receipt fields, local binding, and immutable-name
  conflict;
- Markdown escaping, stable formatting, and no absolute paths or timestamps;
- all Phase 1/2, fake-gcloud, soak, reactor, compatibility, and release gates.

No production test seam may execute an arbitrary command supplied through an untrusted
environment variable. Normal CI remains unauthenticated and free of paid triggers.

## Phase 3 completion checklist

- [ ] Direct canonical comparison requires two compatible completed sets.
- [ ] Exploratory comparison is explicit, warning-labeled, and allowlist-bounded.
- [ ] Every operand is checksum-, digest-, schema-, and identity-validated.
- [ ] Continuous classification follows policy v1 without rounded arithmetic.
- [ ] Categorical, health, diagnostic, zero-baseline, and missing-variation cases are explicit.
- [ ] Suspected regressions produce evidence and exit `0`; there is no hard gate.
- [ ] Comparison ID and final artifacts are deterministic and collision-safe.
- [ ] Markdown is a faithful, escaped rendering of canonical JSON.
- [ ] Registry schema/list/lookup are read-only until Phase 5 receipt production exists.
- [ ] No placeholder baseline, local-path baseline, VM, GCS, IAM, or workflow work is included.
- [ ] Synthetic comparison/registry tests and all existing gates pass.
