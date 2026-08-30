# Cloud Benchmark Selection and Cost Guide

This guide explains how to select the protected `Cloud performance` workflow inputs,
which workload mode to use, and how to estimate elapsed time and Compute Engine cost.
It is an operational aid, not a replacement for the frozen Cloud Benchmark V2
contracts. If this guide and an enforced validation rule ever differ, the workflow,
runner, and phase contracts are authoritative.

## Workflow eligibility matrix

The protected workflow accepts these combinations:

| Evidence profile | Modes | Repeats | Provisioning | Retention |
|---|---|---:|---|---|
| `experiment` | `quick`, `full`, `concurrency`, `soak`, `ranked-v31`, `all` | `1`, `3`, `5` | Spot or Standard | Actions or GCS |
| `canonical` | `full`, `concurrency`, `soak`, `ranked-v31`, `all` | `3`, `5` | Standard only | GCS only |

Additional rules are:

- `2h` is accepted only for a one-repeat experiment in `soak` or `all` mode;
- canonical and multi-repeat `soak` or `all` runs use the frozen `30m` duration;
- `quick`, `full`, `concurrency`, and `ranked-v31` require the UI's default `30m`
  selection, but do not execute a soak;
- canonical mode selects the matching `v3-production-<mode>-v1` preset, except that
  `ranked-v31` selects the isolated `v3.1-ranked-v1` preset;
- an experiment never becomes canonical merely because its controls resemble a
  canonical run; and
- invalid combinations fail preflight before authentication or cloud mutation.

## Input reference

### Evidence profile

`experiment` is for calibration, investigation, tooling validation, and temporary
comparisons. Its evidence may be valid and reproducible, but it is never registry
eligible.

`canonical` freezes the production preset and requires strict environment evidence,
Standard provisioning, three or five independent members, and GCS retention. A
successful canonical run is only baseline-eligible: registration still requires human
review and a separate tracked change.

### Mode

| Mode | Work performed |
|---|---|
| `quick` | Shortened JMH smoke over the core workload shapes and one `4,1` concurrency group |
| `full` | Full scale, corpus-shape, top-K, and core concurrency JMH suite |
| `concurrency` | Focused latency and throughput sweep over the extended concurrency groups |
| `soak` | Sustained reads and writes with GC, heap, queue, drift, snapshot, and index-cycle evidence |
| `ranked-v31` | Fixed 100k/1M phrase-slop, BOOL-minimum, fuzzy-trie, dictionary-publication, and 1M `16,1` feature suite |
| `all` | The complete `full` suite followed by the production soak |

Concurrency groups use `readers,writers` notation. `full` and `all` cover:

```text
1,1  4,1  16,1
```

The dedicated `concurrency` preset covers:

```text
1,1  4,1  8,1  16,1  24,1  30,1
```

Consequently, `all` includes core concurrency evidence but is not a strict superset of
the dedicated concurrency sweep.

`ranked-v31` is a separate suite and comparison family. It uses the fixed `16,1`
mixed cell, a 60-minute per-slot cap, and `-Xms32g -Xmx64g`; it neither executes a soak
nor changes any `v3-production-*` identity.

### Repeats

Each repeat is a fresh ephemeral VM slot. Slots run sequentially and are cleaned up
before the next slot starts.

| Repeats | Interpretation |
|---:|---|
| `1` | One observed value; no independent-VM variation estimate |
| `3` | Recommended default; aggregate by median and retain the three-run range |
| `5` | Stronger variation evidence at roughly 1.67 times the time and cost of three repeats |

The runner does not select or replace a member based on its score. Replacement is only
for independently classified infrastructure failures and requires a recorded reason.

### Provisioning

`spot` is appropriate for inexpensive, fault-tolerant experiments. Google can reclaim
a Spot VM, so a long run may yield only partial evidence and require another attempt.

`standard` reduces interruption risk and is mandatory for canonical evidence. Switching
between Spot and Standard also changes the environment fingerprint; the two are not
members of one directly comparable set.

### Machine type

The workflow exposes two reviewed C3D shapes:

| Machine type | vCPUs | Memory | Use |
|---|---:|---:|---|
| `c3d-standard-30` | 30 | 120 GiB | Default V3 reference platform |
| `c3d-standard-60` | 60 | 240 GiB | Explicit scale-up experiment or separately established baseline |

Changing the machine type changes the environment fingerprint. C3D-60 costs about
twice as much per VM-hour and is not guaranteed to finish twice as fast, because not
every workload scales linearly with CPU count.

### Soak duration

`30m` is the production canonical soak length. `2h` is a bounded investigation option
and is accepted only for a one-repeat experiment in `soak` or `all` mode. The duration
selection is ignored by non-soak modes.

### Retention

`actions` creates a bounded GitHub Actions artifact, currently retained for 14 days. It
is intended for experiment review and should be downloaded outside the repository, for
example below `/tmp`.

`gcs` uploads checksum-bound evidence to the configured bucket and creates an immutable
upload receipt. Canonical evidence requires this durable path. The workflow never
registers a baseline automatically.

### Source commit

When `source_commit` is empty, the workflow binds the dispatch SHA of the selected
branch. With `master` selected, that is the protected-master commit visible when the
workflow is dispatched.

An explicit value must be a complete 40-character commit reachable from protected
`master`. Use it only to reproduce a particular historical commit. Always verify the
resolved source SHA in the workflow summary before interpreting results.

Project, zone, exact image, WIF identity, service account, bucket, JVM options, disk,
and network policy are reviewed Environment configuration rather than free-form
workflow inputs.

## Mode selection

### Cheap workflow smoke

Use:

```text
experiment / quick / 1 / spot / actions
```

This validates configuration, WIF, VM lifecycle, result recovery, derivation, and
artifact handling. It is not adequate for small regression claims or tail-latency
interpretation.

### Independent-VM calibration

Use:

```text
experiment / quick / 3 / standard / actions
```

This is the cheapest way to validate cross-VM fingerprints, metric identities, and set
aggregation under the same provisioning model used by canonical evidence.

### General search-performance comparison

Use:

```text
experiment / full / 3 / standard / actions
```

Use canonical/GCS controls instead when creating a durable pure-performance baseline:

```text
canonical / full / 3 / standard / gcs
```

`full` covers document scale, corpus shape, top-K, and the three core concurrency
groups, but does not run the production soak.

### Concurrency investigation

Use:

```text
experiment / concurrency / 3 / standard / actions
```

This mode is preferable when the question concerns reader scaling, writer starvation,
allocation pressure, or latency behavior across all six concurrency groups. A durable
concurrency baseline uses the canonical profile and GCS.

### Stability and lifecycle investigation

Use the production-sized short soak for comparable evidence:

```text
canonical / soak / 3 / standard / 30m / gcs
```

Use the two-hour form only for a specific long-tail investigation:

```text
experiment / soak / 1 / standard / 2h / actions
```

### V3.1 ranked feature calibration and evidence

After the implementation commit is merged to protected `master`, calibrate the fixed
feature suite before requesting a multi-member set:

```text
experiment / ranked-v31 / 1 / standard / 30m / actions
```

If the complete 84-cell member finishes below the fixed 60-minute cap and its derived
evidence is valid, create the independent feature family with:

```text
canonical / ranked-v31 / 3 / standard / 30m / gcs
```

This set is intentionally incomparable with `v3.0.0-cloud`. Run the unchanged
regression preset separately for before/after claims.

### Comprehensive release baseline

Use:

```text
canonical / all / 3 / standard / 30m / gcs
```

This is the recommended single baseline before starting development of a new version.
It preserves the full JMH surface and the production soak in one independently repeated
set. Add a separate canonical `concurrency` set only when the complete six-group
scaling curve must also be frozen.

## Duration and cost planning snapshot

The following estimates were recorded on 2026-08-29. They use:

- the repository's existing C3D-30 run durations;
- the frozen production presets;
- sequential ephemeral VM slots; and
- the observed Las Vegas billing rate of approximately `$1.535` per Standard
  `c3d-standard-30` VM-hour, before credits.

The estimates exclude small balanced-disk, external-IP/network, GCS operation, and GCS
storage charges. They are planning ranges, not a pricing guarantee. Check the
[Compute Engine pricing page](https://cloud.google.com/products/compute/pricing/general-purpose)
and the billing account before each material run.

### Standard C3D-30

| Mode | Expected VM lifecycle per slot | Repeat 1 | Repeat 3 | Repeat 5 |
|---|---:|---:|---:|---:|
| `quick` | 4–5 minutes | `$0.10–0.13` | `$0.31–0.38` | `$0.51–0.64` |
| `full` | 20–24 minutes | `$0.51–0.61` | `$1.54–1.84` | `$2.56–3.07` |
| `concurrency` | 13–16 minutes | `$0.33–0.41` | `$1.00–1.23` | `$1.66–2.05` |
| `soak 30m` | 32–35 minutes | `$0.82–0.90` | `$2.46–2.69` | `$4.09–4.48` |
| `ranked-v31` | at most 60 minutes by contract; first calibration pending | at most `$1.54` | at most `$4.61` | at most `$7.68` |
| `all 30m` | 51–56 minutes | `$1.30–1.43` | `$3.91–4.30` | `$6.52–7.16` |
| `soak 2h` | 122–125 minutes | `$3.12–3.20` | not accepted | not accepted |
| `all 2h` | 141–149 minutes | `$3.61–3.81` | not accepted | not accepted |

For a normal three-member `canonical / all` run, plan for roughly 2 hours 35 minutes to
2 hours 50 minutes of workflow time and about `$5` of gross budget after allowing for
minor non-compute charges.

### Spot reference

At the time of this snapshot, Google's published C3D-30 Spot reference price was about
`$0.27318` per VM-hour, or roughly 18% of the billing rate used in the Standard table.
Spot prices can change and capacity can be reclaimed. Current pricing is available on
the [Spot VM pricing page](https://cloud.google.com/spot-vms/pricing).

| Mode / repeats | Approximate Spot compute cost at the snapshot rate |
|---|---:|
| `quick / 3` | `$0.06–0.07` |
| `full / 3` | `$0.27–0.33` |
| `concurrency / 3` | `$0.18–0.22` |
| `soak 30m / 3` | `$0.44–0.48` |
| `all 30m / 3` | `$0.70–0.77` |

Failed or preempted Spot attempts can erase part of this saving through retries. Spot
is therefore a cost optimization for experiments, not an alternative canonical
platform.

### Runtime safety caps

The protected GitHub workflow also assigns a maximum VM runtime. These values are
cleanup guards, not expected durations and not amounts prepaid at instance creation.
They are the caps passed by `cloud_workflow_v2.py`; lower-level local runners may have
broader defaults when invoked directly.

| Mode | Per-VM maximum |
|---|---:|
| `quick` | 2 hours |
| `full` | 6 hours |
| `concurrency` | 6 hours |
| `soak 30m` | 2.5 hours |
| `soak 2h` | 4 hours |
| `all` | 6 hours |

An unexpected approach toward one of these limits indicates a hung or severely
degraded run and should be investigated rather than treated as normal benchmark cost.

## Recommended routine

```text
Tooling smoke:
experiment / quick / 1 / spot / actions

Cross-VM calibration:
experiment / quick / 3 / standard / actions

Routine version comparison:
experiment / full / 3 / standard / actions

Focused concurrency work:
experiment / concurrency / 3 / standard / actions

Long-tail stability investigation:
experiment / soak / 1 / standard / 2h / actions

Formal version baseline:
canonical / all / 3 / standard / 30m / gcs
```

Keep downloaded Actions artifacts outside the repository. Canonical evidence belongs
in GCS, while only reviewed receipts, registry entries, and concise interpretation
documents belong in Git.
