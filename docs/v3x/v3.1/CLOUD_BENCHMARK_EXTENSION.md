# V3.1 Cloud Benchmark feature-lane extension contract

## Purpose and boundary

This contract freezes the repository-controlled extension needed to run the distinct
V3.1 ranked feature lane. It is subordinate to the completed Cloud Benchmark V2
manifest, set, comparison, profile, retention, and protected-workflow contracts.

The extension adds one bounded workload identity. It does not change existing V3
production presets, comparison compatibility, evidence schemas, authentication,
infrastructure creation, upload receipts, baseline immutability, or human review.

No workflow or runner implementation begins until V3.1 benchmark classes have local
correctness guards and smoke evidence.

## Frozen identity

```text
mode                 = ranked-v31
preset               = v3.1-ranked-v1
suite identity       = v3.1-ranked-suite-v1
raw/derived schemas  = existing supported Cloud Benchmark V2 schemas
```

The existing `quick`, `full`, `concurrency`, `soak`, and `all` modes and every
`v3-production-<mode>-v1` preset remain byte-for-byte configuration identities. New
V3.1 metrics are never added to them.

`ranked-v31` performs no production soak. The workflow's `30m` soak input is required
as the unchanged UI default and ignored for this mode; `2h` is invalid.

## Workload

The preset executes only reviewed benchmark classes and parameters covering:

- phrase slop `0`, `1`, `2`, and `4` at 100,000 and 1,000,000 documents;
- low/high-frequency terms, repeated terms, analyzer gaps, and same-position
  alternatives;
- BOOL widths `4`, `16`, and `64`, with minimum `1`, half, and all, both with and
  without MUST;
- fuzzy trie traversal by vocabulary size, query length, Unicode shape, hit density,
  exact hit, near hit, and miss;
- text-index build and publication where vocabulary membership is unchanged, added,
  or removed;
- a 1,000,000-document mixed TEXT/PHRASE/FUZZY read workload with one writer.

JMH uses the same production fork, warmup, measurement, heap, collector, result format,
and profiler policy frozen for the existing reference lane unless the preset records a
different complete configuration fingerprint. Correctness/checksum guards are
mandatory; debug or full-scan oracle work is excluded from timed production cells.

The per-slot VM runtime cap is 60 minutes. The protected workflow retains its six-hour
job cap, sequential slots, repository-wide concurrency group, and non-cancelling
behavior. If local calibration cannot fit a five-member set within those bounds, the
contract must be amended before paid execution; the implementation may not silently
raise a cap or drop workload cells.

## Eligibility

The protected workflow adds `ranked-v31` as one fixed mode choice.

| Profile | Repeats | Provisioning | Machine | Retention |
|---|---:|---|---|---|
| experiment | `1`, `3`, or `5` | Spot or Standard | existing reviewed C3D choices | Actions or GCS |
| canonical | `3` or `5` | Standard only | existing reviewed C3D choices | GCS only |

All existing source-commit, protected-master ancestry, exact-image, JVM, network,
WIF, service-account, bucket, manual-environment approval, and pre-authentication
validation rules remain unchanged. The benchmark VM still receives no service account
or cloud scopes.

## Evidence and comparison

Every member must expose the same complete V3.1 metric-ID set, preset, suite,
configuration fingerprint, and normalized environment fingerprint. Set aggregation,
replacement authorization, checksum derivation, upload, receipt verification, and
baseline registration use the existing V2 logic without score-based member selection.

The first valid canonical `v3.1-ranked-v1` set establishes a new comparison family. It
is `INCOMPARABLE` with `v3.0.0-cloud` because preset, suite, configuration, and metric
identities differ. Later sets are directly comparable only when all ordinary Cloud
Benchmark V2 compatibility requirements match.

Registration remains a separate human-reviewed operation. The protected workflow
never registers or replaces a baseline automatically. A recommended first immutable
registry name is `v3.1.0-ranked-cloud`; the actual registration change records the
reviewed source commit, set ID, receipt, generations, and release label.

## Workflow and artifact boundary

Implementation may update only the existing runner, set wrapper, no-cloud workflow
control plane, protected manual workflow, tests, selection guide, and allowlists needed
for this fixed mode. It must not create a second orchestrator, accept benchmark regexes
or JVM options from dispatch input, add automatic triggers, broaden IAM, upload raw
benchmark directories as GitHub artifacts, or weaken final cleanup/failure precedence.

Artifact staging remains bounded and checksum-inventoried. Any new allowlisted summary
or manifest role must be frozen in tests before workflow execution. Synthetic tests use
fake runners/storage and cannot create a VM, request OIDC, or write GCS.

## Validation gates

- input matrix and invalid pre-authentication combinations;
- dry-run propagation of exact mode/preset/runtime controls;
- runner result recovery and cleanup on every classified failure;
- set resume/reconcile/replacement behavior;
- complete member metric identity and feature-set aggregation;
- explicit incomparability with `v3.0.0-cloud`;
- canonical upload and receipt verification through fake storage;
- bounded artifact allowlist and failure summary;
- proof that existing mode plans and preset identities did not change;
- proof that no path automatically registers a baseline.
