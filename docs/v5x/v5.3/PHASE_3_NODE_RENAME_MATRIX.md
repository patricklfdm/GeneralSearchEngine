# Phase 3 — exact-source node rename process matrix

This entry implements capture and independent qualification for four whole
`V53NodeRenameProcessTest` histories. Final-source native execution is **pending**;
the workflow, unit fixtures and historical replays do not close Phase 3.

| Case | Exact JUnit method |
| --- | --- |
| `ACCEPT_RENAMED,halt` | `haltAfterAcceptRename` |
| `ACCEPT_RENAMED,kill` | `killAfterAcceptRename` |
| `PROOF_RENAMED,halt` | `haltAfterProofRename` |
| `PROOF_RENAMED,kill` | `killAfterProofRename` |

Each member keeps both leader JVM lifetimes, the original filesystem, surviving
followers, three campaigns and five published slots on one worker. It interrupts
after the named atomic rename and before its parent directory force. The resumed
leader must recover the carried mutation, publish a fresh barrier and complete
its new client operation. The interrupted client never reports success or retries
its mutation. This establishes process-loss behavior only, not host power loss.

## Capture and acceptance

[`node_rename_run.py`](../../../scripts/v53/node_rename_run.py) runs exactly one
method in a fresh source copy, offline after dependency preparation. It retains
source, compiled classes, portable Java/Maven identities, command, execution log,
JUnit and complete original history. A failed execution stays failed and is not
retried. Collection checks both process observations and returns only `PARTIAL`.
The existing 180-second service/call and 210-second parent command bounds remain
unchanged. Progress is emitted every minute while an external command runs.

[`node_rename_matrix.py`](../../../scripts/v53/node_rename_matrix.py) requires
the same exact source/build/toolchain/reader hashes for every member. The current
reader must be present with identical bytes in the recorded producer source;
running a later reader on an older history is diagnostic only. The single exact
JUnit method must pass without skips, flaky results or reruns. Every source and
class file, the execution receipt and collection are independently rechecked.

The gate invokes [current physical/network replay](PHASE_3_NODE_RENAME_PROCESS.md)
before its 34 exact evidence negatives. An original exercising the
[late unused PREPARE path](PHASE_3_NODE_LATE_PREPARE.md) additionally requires all
three corresponding negatives. Failure of the unmodified original cannot count
as successful negative qualification. Originals are checked unchanged after
replay. Missing cases, aliases, duplicate original plans, changed readers and
unrelated rejection reasons refuse acceptance. The local aggregate supports one
to four replay processes, records each failure and never retries a member.

## Hosted execution

[`v53-node-renames.yml`](../../../.github/workflows/v53-node-renames.yml) is an
opt-in workflow: `workflow_dispatch` or a push to `experiment/v53-node-renames`.
It does not change Required, ordinary CI, release authority or V5.2 experiments.
No hosted execution is claimed by adding this entry.

1. Prepare one immutable source, reference class inventory, pinned tools and
   offline dependencies. The reference build uses the existing allocator test;
   it does not execute a rename history.
2. Execute four whole histories, with at most four workers and `fail-fast: false`.
   Retain failed originals as well as successful ones. Each worker's classes and
   dependencies must still match the prepared seed.
3. Download and independently replay each complete original, with up to four
   verifier workers. Verifier receipts remain `PARTIAL`.
4. Aggregate exactly four verifier receipts. All execution and verification jobs
   must succeed; each receipt must bind the same repository, workflow, source,
   run, attempt and seed archive. Original plan and raw archive identities must
   be distinct. A complete subset may set `declaredNodeRenameMatrixQualified`,
   while `phase3Complete` and complete observation coverage remain false.

Artifacts include run, attempt, source and case in their names and are retained
for 90 days. Shared archive validation bounds bytes/member counts and rejects
links, path traversal, modified inventories and wrong artifact roles. SHA-pinned
Actions and the existing Java 21 / Python 3.11 / Maven 3.9.11 setup are reused.
Whole histories are never split at crash, installation or publication boundaries.
The workflow's platform timeout is 360 minutes; it does not extend native bounds.
Hosted orchestration also emits minute progress and writes a parameter summary.

For inspection without execution:

```bash
python3 -B -m scripts.v53.node_rename_matrix plan
```

For one explicitly selected local capture, after preparing offline dependencies:

```bash
python3 -B -m scripts.v53.node_rename_run target/v53-node-rename-local/accept-halt \
  --maven /opt/maven/bin/mvn --case ACCEPT_RENAMED,halt
```

All output directories must be new. Standalone matrix `member` and `aggregate`
commands require explicit `--source-sha256`, `--build-sha256`,
`--toolchain-sha256` and `--reader-sha256` pins; inspect `--help` for their inputs.
Use the hosted seed for a portable cohort rather than combining unrelated local
builds. Do not import the earlier two successful histories as final-source members.

## Verification and remaining work

Focused tests exercise four-case coverage, exact commands/JUnit, failed native
retention, source/class/reader drift, process recollection, original-first replay,
conditional negatives, archive relocation, same-attempt provenance and aggregate
refusal. Synthetic orchestration tests do not claim actual JVM or hosted success.
Historical ACCEPT/halt and PROOF/kill originals are separately used to check
archive round trips and current independent replay; their producer sources differ.

The [development receipt](phase3-evidence/node-rename-matrix.json) records 2068
passing V5.3 Python tests and 28 focused tests under both normal and optimized
Python. The focused checks were repeated after tightening portable seed-toolchain
validation. Both historical archive round trips passed complete replay and all
71 applicable negatives, with originals unchanged. YAML and five shell blocks
were checked; `actionlint` was unavailable. No new native matrix, Maven reactor
or GitHub execution was run in this batch.

The four-case final-source run, joining process composition, other final-source
cohorts, combined resource bounds and frozen acceptance mapping remain open.
Rollback removes these optional capture/matrix/workflow entries and their tests;
runtime Java, persisted formats, protocol readers and existing workflows are
unchanged. Retain all original evidence, including failed runs.
