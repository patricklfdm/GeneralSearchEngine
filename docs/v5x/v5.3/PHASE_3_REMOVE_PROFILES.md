# Phase 3 — continuous original REMOVE profiles

The existing four-to-three automatic round qualification now has explicit,
separate 4-REMOVE and 5-REMOVE execution inputs. This extends the actual
`MembershipRoundDriver` path rather than substituting an ADD/REPLACE learner
fixture for removal. REMOVE adds no new permanent identity or learner.

## Execution and independent reduction

Each invocation creates a new admitted bootstrap and its own original absolute
stores. Test preparation publishes RESERVE, PREPARE, READY and SEAL. One bounded
native round owner then performs INTENT, joint activation, FINAL, new-stable
activation and BARRIER. The test does not sequence these three native slots for
the owner. All network owners remain open across the native transition; no store
is restored from an intermediate snapshot.

The request removes the last original identity. The expected old, joint and new
majorities are derived from the declared original size:

| Original profile | INTENT selected voters | FINAL selected voters | New-stable BARRIER voters |
| --- | --- | --- | --- |
| 4-REMOVE | node-1/2/3 | node-1/2/3 | node-1/2 |
| 5-REMOVE | node-1/2/3 | node-1/2/3 | node-1/2/3 |

The physical reader derives the original bootstrap, exact target identities,
preparation commands, selections, applied/published bytes and retention state.
It compares every node, including unchanged nonparticipants. The lifecycle reader
requires three original installations and completions, the original fresh
BARRIER at index 7 and its exact readiness reply. A size label or PASS receipt
cannot stand in for this reduction. Legacy unnamed four-node evidence retains
its old entry and cannot be passed as a named five-node profile.

`remove_profile_run` retains the source/toolchain/build manifests, exact JUnit
case, entire raw history, input inventory, original-first negative replay and
terminal receipt. It refuses existing output directories and cannot nest a new
execution inside its original source provider. Native or replay failure remains
FAIL, with no retry or successful substage promoted into acceptance. Progress is
reported every minute.

```bash
python3 -B -m scripts.v53.remove_profile_run target/v53-remove-5 --profile 5-REMOVE
python3 -B -m scripts.v53.remove_profile_run target/v53-remove-4 --profile 4-REMOVE \
  --source-from target/v53-remove-5
```

The two independent histories may run concurrently after the common immutable
source exists. One member's preparation, activations, slots and evidence may not
be split across workers or spliced with another execution. Long process/fault
cohorts remain suitable for later hosted parallel jobs at whole-history boundaries.

## Retained results and reader correction

Both native executions passed the single declared Java test, using identical
producer source, toolchain and compiled classes. The runner measured 322.708
seconds for 4-REMOVE and 403.748 seconds for 5-REMOVE. These are execution
observations, not a service latency guarantee.

Both original wrappers then failed independent replay at the first native
INTENT's applied snapshot. The legacy reducer expected older source files and
grant rows to remain, and represented complete-copy observations as bare endpoint
updates. The current runtime had already retired superseded sources after
installation and retained confirmations plus renewal obligations. The original
FAIL receipts, Maven successes, reader failures and diagnostic file differences
remain intact; no native history was rerun to repair the reader.

Explicit profiles now use a separately frozen maintenance reducer. It validates
complete governing copies against previously derived generations, preserves
confirmation and renewal bytes, checks all retained/source ancestor coverage,
and only removes covered sources outside the current promise and latest ballot.
It derives the compacted grant journal and exact deleted-file count, requires
the source/journal forces and floor release before vote creation, and separately
checks pre-grant generation retirement. Selected installation conservatively
merges the independently derived peer ledgers. The legacy unnamed reader keeps
its earlier semantics; no observed snapshot is copied into expected state.

The unchanged originals pass corrected replay in 35.625 and 44.985 seconds,
including sixteen original-first negative cases each. Six new negatives target
missing source force, late floor release, unexpected pre-grant source retirement,
restored obsolete files, missing confirmation and missing renewal debt. The
retained legacy four-node history separately passes its ten exact negatives;
that is another replay, not a new workload. All 653 selected Python regressions
pass, including eleven runner and fourteen maintenance tests. Production Java,
resource limits, operation/request deadlines and retries are unchanged.

The batch archive separates both original producer histories and failed readers
from the corrected reader, preserving their complete source manifests, shared
build, raw inventories, diagnostics and test reports. Its member and directory
hash checks and assertion-disabled relocated replay are recorded in the receipt.

## Acceptance boundary

The [batch receipt](phase3-evidence/remove-profiles.json) records actual executions,
frozen sources, all original-first negatives, focused regressions and portable
replay. A successful member is **PARTIAL**: continuous original physical/lifecycle
qualification is distinct from complete attempted-network validation, fresh-process
cuts, autonomous election scheduling, removed-proposer/follower variants, public
operations and the complete frozen Phase 3 mapping. Earlier departing-node process
evidence retains its original source and scope; it is not relabelled as a new
five-node process run.

The existing ten-minute native round budget, request timeout, resource bounds,
wire/storage formats and runtime implementation are unchanged. No workflow or
paid-cloud action is introduced, and Phase 3 remains open.
