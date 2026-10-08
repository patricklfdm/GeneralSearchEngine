# V5.1 first native experiment acceptance

**Status:** the four-cell native experiment is accepted on source
`500a41f30a5149703b81c4c2d01da75cd3baf1ed` (PR #304), with protected
[CI 37718123364](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37718123364)
and [native run 37723402614](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37723402614),
attempt 1. Full Phase 6 and the five-member evidence set remain open.

## Original execution and identity

| Item | Original value |
| --- | --- |
| Workflow | `V5.1 Preflight and Experiment Runner`, `.github/workflows/v51-replication-evidence.yml` |
| Manual cleanup | `37720968258`, same source, no active lease |
| Prepared run | `37722737290`; earlier prepare `37721234781` expired unused |
| Sequence | `6b5e3706fd1e488f911513c841ae5c02` |
| Plan SHA-256 | `e51c8b6a37a79b307d2dc2ff9cfeeba9bb04654a7e5a5eec8a7a12eb6db5cd40` |
| Request SHA-256 | `b68d4d2b7d700a77d3fbace74cd7b75e48be162f42d8dfef8b9cf17b8fa10d6f` |
| Artifact | `v51-experiment-37723402614-1`, ID `11529630454` |
| Original ZIP | 349728213 bytes; SHA-256 `43dc2246fbaa5f5527e99390b65a82323219569c1149197bb220884d9aa9f6eb` |
| Run step | 2026-10-08 03:36:20–04:51:29 UTC, 75m09s |
| Recorded scope | `owned-complete-experiment`; `ownedExperimentQualified=true`; `fullRemoteQualification=false` |

The previously failed run `37706121942` remains failed and retained. Its healthy
final cuts differed after leader-first shutdown; see the
[correction and original evidence](PHASE_6_NATIVE_EXPERIMENT_HEADROOM.md#healthy-shutdown-correction).
The successful run observed leader node 1 and stopped voters in order 2, 3, 1,
retaining the original acknowledgements and strict all-voter final-cut check.

## Accepted cells

| Cell / mode | Original calls | Evidence mutations rejected | Result |
| --- | ---: | ---: | --- |
| healthy / published V4.4 local | 90 | — | PASS |
| healthy / published V5.0 configured | 90 | 10 | PASS |
| healthy / candidate V5.1 automatic | 90 | 10 | PASS |
| leader-loss | 7 | 6 | PASS |
| maintenance | 10 | 10 | PASS |
| no-quorum | 9 | 6 | PASS |

All four cells passed independent physical/history validation, with 42 evidence
negative variants rejected. Backup/restore qualification passed. Counts include
the actual fault histories; their frozen maximums are bounds, not padded calls.

Cleanup recorded all thirteen original resources absent with matching expected
IDs, no leftovers and no errors. Retention was `VERIFIED`; the lease was released.
These are the original execution's observations. Offline review does not query
current GCP resources or establish current permission/cleanup readiness.

The original plan reserved USD 20 on top of USD 50 in the restarted ledger:
**USD 70 / 200** after this attempt. This is conservative reservation accounting,
not an observed bill. No failed charge was refunded and this review changes no ledger.

## Measured controller time

| Stage | Observed seconds | Admitted ceiling, seconds |
| --- | ---: | ---: |
| preparation | 1432.606 | 3600 |
| healthy, three modes | 819.866 | 2700 |
| leader-loss | 170.218 | 600 |
| maintenance | 305.525 | 900 |
| no-quorum | 264.446 | 600 |
| validation and retention | 1278.858 | 1800 |
| cleanup | 223.294 | 900 |
| intervening control | 1.706 | 900 |

The disjoint controller intervals total 4496.519 seconds, within the
14400-second native v2 lease. Preparation and validation/retention dominate this
run. One successful execution is insufficient to tighten ceilings or infer a
failover SLA. Preserve the bounded retry and terminal-failure rules. These v2
ceilings apply to this four-cell experiment only.

## Portable offline review

Download the **original artifact ZIP** through the Actions artifact API; an
unpacked download repacked locally will have a different archive digest. Obtain
the source, run/attempt, request and archive pins from the trusted original run.
With this archive saved as `target/v51-native-success-37723402614/experiment.zip`:

```bash
python3.11 -m scripts.v51.native_experiment_review \
  target/v51-native-success-37723402614/experiment.zip \
  --output target/v51-native-experiment-review/replay \
  --source 500a41f30a5149703b81c4c2d01da75cd3baf1ed \
  --run 37723402614 --attempt 1 \
  --archive-sha256 43dc2246fbaa5f5527e99390b65a82323219569c1149197bb220884d9aa9f6eb \
  --request-sha256 b68d4d2b7d700a77d3fbace74cd7b75e48be162f42d8dfef8b9cf17b8fa10d6f
```

Use a fresh output directory for each review. The command checks archive safety,
original plan/approval and run binding, exact resource IDs, cleanup/retention
receipts and all disjoint budget arithmetic. It unpacks the original digest-bound
binary parts and reruns the existing independent four-cell validator, including
the physical traces and evidence negatives. Its aggregate must exactly equal the
original aggregate. A retained `PASS` receipt alone cannot qualify the input.

The verified member inventory is moved outside the disposable replay root to
respect the existing validator's reserved filename. Original ZIP and part bytes
remain intact; no sealed path, authority byte, or evidence outcome is rewritten.
The output includes `review.json`, `aggregate.json` and all replay diagnostics.
A validation failure retains a `FAIL` review and propagates a nonzero exit.

The offline tool validates the historical plan at its original creation time;
this does not renew its expired approval. It fetches no GitHub provenance, rebuilds
no candidate artifact, reruns no workload and grants no paid admission. Maintenance
review does compile and execute the independent published-V4.4 backup restore;
provide Java 21 and the pinned published controls in `target/v51-published-controls`
to keep dependency resolution offline. The caller must independently trust the
supplied pins. Future incompatible plan or
validator changes must be reviewed explicitly, rather than relabeling old evidence.

## Remaining acceptance boundary

Local qualification of the combined review/network batch passed 236 related Python tests
and complete replay of the original successful archive. Its protected CI remains
pending; PR #304's CI qualifies the original runtime, not this later review tool.

This result establishes the four-cell native integration milestone. The current
native entry has no complete `failure-drill` or `canonical` implementation.
See the [full-preset entry plan](PHASE_6_NATIVE_PRESET_ENTRY_PLAN.md).

The formal experiment, failure drill and three canonical repetitions must share
one source/artifact/configuration/workload identity. Subsequent implementation
changes therefore require a fresh experiment in the eventual five-member set.
Preserve this successful run as historical evidence; do not combine it with
future-source members or register a Phase 6 baseline from it alone.
