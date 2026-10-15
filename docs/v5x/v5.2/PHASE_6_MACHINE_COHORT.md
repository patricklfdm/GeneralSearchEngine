# V5.2 Phase 6T machine freeze and complete local cohort

**Status:** machine/cohort implementation and fixture tests are locally verified.
Freeze `ee9bdb9` preceded the first formal M01 history. Its cohort was interrupted
during replay as recorded in [Phase 6U](PHASE_6_REPLAY_EFFICIENCY.md). Freeze
`cfc32c6` then failed its first M01 drain as recorded in
[Phase 6V](PHASE_6_M01_DRAIN.md). Complete M01–M04 qualification and hosted/cloud
acceptance remain open. Continue under the
[local development authorization](LOCAL_DEVELOPMENT_SEQUENCE.md).

## Freeze implementation before measurement

`measurement_machine.py` requires a clean committed checkout and the existing
shared-build bundle produced from that exact source and JVM. The bundle's two
candidate JARs must match the current build outputs. Published controls retain
their frozen identities. Preparation compiles both published and candidate
consumer/observer/query families and bootstraps their seed fixtures without
starting a three-voter measured history.

The generated `phase6-local-machine.json` records:

- Implementation SHA and complete checkout fingerprint, build manifest/archive
  hashes, all control/candidate JARs and compiled class hashes.
- Linux kernel, CPU model/count/affinity, memory, boot identity, cgroup limits,
  Python/Java/compiler executables, monotonic clock and native Linux filesystem.
- Exact program/corpus/query hashes, all 28 profiles, node targeting, wait and
  capacity parameters, fault schedules, runtime/evidence decoder bounds and exact
  negative case/status/reason lists.
- Serial execution order, no business/workload retries, failure preservation and
  local-only acceptance. At least 16 GiB free filesystem space is required before
  each history; this is a storage prerequisite, not a performance threshold.

The next commit must change **only** this JSON and directly follow the implementation
commit. This avoids putting a commit's own hash inside itself. Every actual
history independently binds the resulting freeze commit and full checkout hash.
Execution checks source and machine identity before and after each history;
changing source, JARs, compiled classes, machine or process attempt rejects.

Offline replay reconstructs the recorded checkout from immutable Git objects,
checks the exact parent and sole plan change, and compares the committed plan
bytes. It can run from a later checkout without relabelling that checkout as the
measured source. The exact source commits must remain available.

## Complete cohort, never successful fragments

The entry runs 15 M01 histories (five modes × three repetitions), nine M02 wait
histories, two M03 capacity histories and two M04 recovery histories. All use fresh
groups, histories, manifests and paths. M01 retains all 60-second warmup and
120-second measurement windows: 2,700 nominal seconds in total. Including setup
and fault calls, the complete ledger has 27,373 reads and 2,745 updates.

Each stopped history is inventoried, packed, fully replayed at its original and
relocated locations, and checked against the independent published-core query
oracle. There are 439 declared negative mutations at each location, 878 rejection
checks across the complete cohort. All original outcomes remain in the reports;
there is no latency/speedup acceptance target or selective successful-call filter.

The aggregate obtains member results from these independent replays in its own
process. It rejects missing/extra members, mixed sources/builds/attempts, reused
domains, changed call counts or missing/wrong negative categories. Member PASS
remains unqualified. Only the complete aggregate can set
`qualifiedMeasurement=true`, with `hostedAcceptance=false` and
`cloudAcceptance=false` explicitly retained.

An execution failure stops the cohort, preserves completed receipts and the
original failed history, and does not retry or resume that workload. Replay of
already retained complete bytes is a separate operation and never resubmits
business calls. A corrected implementation requires a newly reviewed freeze and
fresh cohort; earlier results cannot be silently spliced into it.

## Entry and validation

After the implementation commit and fresh reactor build/bundle:

```bash
python3 -m scripts.v52.measurement_machine \
  --build target/ci-v52-measurement-build \
  --storage-root target/v52-formal-measurement/cohort-1
# Commit only docs/v5x/v5.2/phase6-local-machine.json before running:
python3 -m scripts.v52.measurement_cohort run
# Independent later replay of retained inputs to a new output directory:
python3 -m scripts.v52.measurement_cohort replay \
  target/v52-formal-measurement/cohort-1 target/v52-formal-replay/replay-1
```

Five unit tests cover the exact cohort/counts, frozen-contract drift, incomplete or
mixed/reused members, fail-fast original-failure retention without retries, and
real temporary Git commits for parent/plan/checkout admission. These fixtures do
not count as physical measurements. Existing short integration gates keep their
scope; the formal 28-history workload is not silently inserted into CI.

Validation receipts are retained at `target/v52-machine-freeze/`. Exact-source
reactor build, machine freeze, formal histories and any later failures must be
recorded separately. No workflow, production Java, POM, control hash or paid-cloud
behavior changes in this stage.
