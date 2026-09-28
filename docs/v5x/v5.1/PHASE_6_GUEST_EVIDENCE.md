# V5.1 Phase 6C3C9 — independent guest warmup evidence

**Status:** accepted through PR #240, master
`0ef49cb8f5f6c793b9fe03db4b4069dd04e059ac`.
[Exact-master CI 36378226619](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36378226619)
attempt 1 passed all 27 jobs. PR CI `36375225877` attempt 1 also passed. The
foundation log records all nine mode results and 21 member validations across the
plain packaged, complete-package SSH and isolated-mount gates. Each gate retains
its original thirty warmup calls. These are logical warmup/resource checks, not
full cells or physical history acceptance.
The following [owned bootstrap candidate](PHASE_6_OWNED_BOOTSTRAP.md) continues the
local admission bridge; it requires its own qualification and acceptance.

## Cut point and scope

6C3C8 connected owned allocation/volume preparation, authenticated complete-package
delivery and persistent idle services. The separate three-mode packaged guest,
SSH delivery and independent-mount bootstrap gates already execute ten frozen
experiment warmup calls per mode. Their collected journals were checked for JSON
decoding, counts and clean shutdown, without independently joining the complete
request/result chain.

This slice adds that independent replay as a prerequisite for the owned workload
bridge. It does not connect the owned runner to engine cells. Distributed source
delivery into that service set, complete measured windows, remote faults, physical
history/backup/restore evidence and full 6C remain unfinished. Native cloud writes,
trusted preflight, separate V5.1 workflows and paid admission remain subsequent
work. The existing owned idle gate still reports `engineWorkloadExecuted=false`.

## Independent replay contract

[The validator](../../../scripts/v51/guest_evidence.py) takes the relocated binary
collection, configuration, original authenticated package-manifest bytes, installed
package path and controller-retained command transcript. The transcript is retained
outside the guest collection; a guest's own `PASS` cannot supply missing controller
observations. Replay writes no guest state and submits no commands.
Each controller request is forced before submission, and each observed terminal
receipt is forced immediately on return. Interrupted commands therefore leave
their original controller records even when the aggregate transcript is not reached.

It rechecks the collection inventory and index digest; complete command coverage;
original request, started and terminal receipts; one service process/boot identity;
the JVM's PID, start ticks, boot, argv, loaded JAR hashes, pinned Java and frozen
plan; clean non-forced shutdown; and closed journal segments. The collect command
is excluded from its own archive and must match the controller's terminal binary
manifest. The deliberately failed live collection remains a failed command and
must carry its original specific rejection. Cancellation, unresolved commands and
unrelated failures cannot be promoted to a successful warmup.

For the issuing member, the validator independently reconstructs the ten-call
healthy experiment warmup. It joins every frozen call to the scheduler's raw
arrivals, persistent JVM request, original result journal and callback digest.
It checks dispatch deadlines and order, API intervals, payload and answer hashes,
before/after sequence and logical GET/QUERY answers against the independent model.
Control commands, window configuration and close must account for every JVM
response; passive voters cannot contribute hidden calls. Resource lifecycle,
periodic sampling, writer/queue bounds, maintenance drain and trace identities are
checked with the existing independent validators. Python and Java clock intervals
are checked within their own domains; clocks from different hosts are not ordered.

The result is explicitly `guest-warmup-evidence-only`, with
`physicalHistoryQualified=false`, `fullRemoteQualification=false` and
`paidCloud=false`. Logical warmup replay is not a physical authority/read-cut proof
or acceptance of a complete healthy cell, fault cell or cloud attempt.

## Qualification and retention

[The existing guest qualification](../../../scripts/v51/guest_qualification.py)
retains `package-manifest.json`, `controller-node-N.json` and
`validation-node-N.json`, then requires replay success for each of its seven
members across three modes. The plain packaged, loopback SSH and isolated-mount
gates share this path. No new JVM execution, workload retry, timing relaxation,
Maven build, job or paid workflow is introduced. Existing failed raw artifacts are
never rewritten.

[Portable regressions](../../../scripts/v51/test_guest_evidence.py) use explicitly
synthetic records, including correctly resealed counterexamples. They cover
three modes and passive voters; wrong logical reads; changed requests, sequences
and digests; mismatched controller/JVM receipts; duplicate/missing responses;
unplanned commands; process/package drift; sampling/queue failures; unexpected
members; segmented journal gaps; truncated gzip; and symlinks. These fixtures are
validator tests, not engine execution evidence.

```bash
python3 -m unittest scripts.v51.test_guest_evidence
# Replay one downloaded member; all paths are retained controller artifacts:
python3 -m scripts.v51.guest_evidence \
  target/v51-guest-services/candidate-v5.1-automatic/replay-node-1 \
  --controller target/v51-guest-services/candidate-v5.1-automatic/controller-node-1.json \
  --manifest target/v51-guest-services/package-manifest.json
```

The governing workload and evidence limits remain the
[cloud workload contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md), frozen
`phase6-cloud-workload-plan.json`, [local measurement contract](PHASE_6_LOCAL_MEASUREMENT_PLAN.md),
[guest service contract](PHASE_6_GUEST_SERVICE.md),
[bootstrap contract](PHASE_6_GUEST_BOOTSTRAP.md) and
[owned service contract](PHASE_6_OWNED_SERVICES.md). Protected acceptance must use
the exact candidate source/build and all existing required gates.
