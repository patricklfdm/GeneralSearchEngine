# Phase 3 — carried application and publication file capture

Phase 3 remains **OPEN**. This batch follows the
[vote-prefix component](PHASE_3_CARRIED_VOTE_CAPTURE.md). It implements the next
collector and independent native projection, with short real-writer checks.
The complete new crash/reopen composition has not been executed or admitted.

## Boundaries

The optional completion recorder shares the original resource observer's owner,
root, child PID, lifetime, terminal and event digest. Application captures run
from `APPLY_VALIDATED` to `APPLY_BEFORE_RETURN`. Publication captures run from
`PUBLICATION_VALIDATED` to `PUBLICATION_BEFORE_RETURN`; INSTALL and CURRENT
callbacks are included only inside that same owner's publication. Campaign
installation, network ACKs and source capture are separate operations.

The [file model](../../../scripts/v53/native_completion_files.py) checks the
entire replica inventory, including empty directories and unrelated files:

- The end plan and metadata are written as empty, half and complete files before
  their force callbacks. Application images and the complete end precede ACK
  creation. Parent/ancestor ordering and nonvoting completion have model tests;
  the three executed components exercise the ordinary seven-file ends.
- A new generation is installed before selector replacement. The old selector
  remains active through the new selector's file force. Reload and directory
  force callbacks retain the installed original bytes.
- Covered end members are removed in sorted order, with `plan.json` last, then
  the end directory. The old pending vote remains active until the empty
  candidate is renamed; the candidate cannot survive replacement.
- The independently derived future-ACK ledger already exists at publication
  validation. Peer promotion and future-ledger clearing happen after
  `PUBLICATION_RETIRED` and before return. Their intermediate file writes are
  still a separate ledger-prefix obligation; this collector does not claim them.

The [native projection](../../../scripts/v53/native_carried_transition_forces.py)
reuses the original physical reducer's future-ACK derivation. New sidecar bytes
never supply expected states. Every modeled callback must bind exactly once to
its original node, lifetime and event index. Fresh end/install paths reject
partial candidates; application-ACK crash recovery remains separate work.

The [native reader](../../../scripts/v53/native_carried_completion_prefixes.py)
requires the full prior vote/campaign/FLOOR/retirement/resource/history chain.
Its layout is `previous/` containing the entire vote wrapper, and
`completion/life-1`, `completion/life-2` containing the new sidecars. The two
declared ACCEPT/PROOF rename cuts precede application: life 1 has zero completion
captures and cannot invent a post-cut tail. An incomplete application/publication
cannot claim a normal close or borrow the vote rename exception. The existing
capture count, file, aggregate-byte and resource limits are unchanged.

## Development evidence and limits

The [development index](phase3-evidence/carried-completion-prefix-development.json)
records the following separately scoped checks:

- Twenty-one focused Java tests pass, including three real local DATA/INTENT/FINAL
  application/publication components, writer-lock probes, zero resources after
  close, transaction-boundary rejection and all five optional observer bindings.
- The [short reader](../../../scripts/v53/completion_prefix_component.py) compares
  all 270 captured inventories with conditional complete-snapshot inputs. All 39
  physical mutations reject for their exact declared reason, and each original
  replays identically after relocation with Python assertions disabled. These
  component fixtures do not establish native protocol authority or crash recovery.
- The unchanged previously qualified FINAL and INTENT histories yield 450 and
  720 expected completion prefixes. Existing force receipts remain identical.
  These are original-derived expectations, not new native captures.
- The full reader defines 29 negative cases; native execution and those full-chain
  negatives are deferred. Original validation precedes every negative, and an
  unrelated failure cannot count as a rejection. All original evidence is retained.

The first short Java attempt exposed ACK ordering in the new fixture; it is
corrected without changing runtime code. A first component reader attempt used
the full ROOT-frame hash instead of its manifest digest; the reader now validates
the ROOT frame and binds its manifest digest. Both diagnostic logs remain in
the development output directory.

For the later composed acceptance run:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl :general-search-engine-replication -am \
  -Dtest=V53NativeCarriedCompletionPrefixProcessTest \
  -Dsurefire.failIfNoSpecifiedTests=false test

python3 -B -m scripts.v53.native_carried_completion_prefixes \
  general-search-engine-replication/target/v53-native-carried-completion-prefixes/run-<id> \
  --qualify
```

Remaining: actual composed native qualification, ledger and core scratch
transients, complete simultaneous resource maxima, the other carried-process
axes, application-ACK recovery and final-source hosted admission. This batch
changes no production Java, POM, workflow, runtime bounds, frozen workload or
hosted subset catalogue, and runs no cloud or hosted experiment.
