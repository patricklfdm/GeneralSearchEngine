# Phase 3 — carried-process vote file capture

Phase 3 remains **OPEN**. The vote observer and independent prefix model are
implemented after the [campaign-prefix qualification](PHASE_3_CARRIED_PROCESS_CAMPAIGNS.md).
A short local writer fixture qualifies the file transaction component. Complete
native crash/reopen execution with the new observer is deferred to the composed
acceptance run; it has not been executed or credited in this batch.

## Boundaries and original state

The optional vote mode retains complete replica inventories at the nine original
ACCEPT, PROOF and CERTIFICATE write callbacks: validation, candidate creation,
half-prefix write, complete write, file force, candidate parent force, rename,
active parent force and return. Old active bytes survive until rename. Every
other replica file and empty directory must retain its original state. Existing
2048-capture, 512-file, 64-MiB-file and 256-MiB-per-child limits remain unchanged.

A first-child CUT_PREFIX may end with the node-1 ACCEPT or PROOF transaction at
its declared rename cut. This cannot become CLOSED, and another partial phase or
owner cannot borrow that exception. Successor closure requires completed
transactions. Capture identity remains bound to the same resource observer's
root, PID, life, terminal state and original event digest. Active-file reseals,
network ACKs, covered-vote cleanup and replay of a partial candidate are different
operations; they are not relabelled as these nine fresh-write boundaries.

The [model](../../../scripts/v53/native_vote_files.py) derives phase containers
from original validated selector, promise, selection, entry, payload and vote
frames. It models the empty candidate, exact half prefix, completed file and
atomic replacement. The optional [force-reader projection](../../../scripts/v53/native_carried_transition_forces.py)
places those states across cold rebinds, the interrupted first slot, maintenance
and later complete slots. First-slot maintenance occurs after ACCEPT; subsequent
slots maintain before ACCEPT. Every applicable original callback must bind once
to its actual owner, lifetime and event index.

The [native reader](../../../scripts/v53/native_carried_vote_prefixes.py) requires
the complete campaign/FLOOR/retirement/resource/history prerequisite before it
compares new observations. Its outer layout is `previous/` for that entire prior
wrapper and `votes/life-1/`, `votes/life-2/` for new sidecars. Generic identity,
coverage and object negatives plus six physical mutations per phase are defined.
Full originals must pass before negative credit; every rejection needs its exact
reason and original storage must remain unchanged.

## Local development checks

The [development index](phase3-evidence/carried-vote-prefix-development.json)
records these separately scoped results:

- Eighteen focused Java tests pass. Three real local voting owners perform nine
  ACCEPT/PROOF/CERTIFICATE transactions under their writer locks. All 81 captured
  inventories match the independent file model, and all 18 physical mutations
  reject for the declared reason. The fixture's initial history is conditional;
  it does not establish carried-process protocol or crash qualification.
- The strengthened node-observer binding suite passes five tests, including shared
  identity/event hashes and actual close across all four optional recorders.
- Related Python suites pass 219 tests; 46 boundary tests also pass with assertions
  disabled. The original short component replays identically after relocation
  under Python optimization.
- The unchanged two previously qualified originals produce 169 FINAL and 241
  INTENT **expected** vote prefixes. Their existing force receipts remain equal.
  These are derived expectations, not newly captured native bytes. No new process
  death, cloud run or hosted acceptance is claimed.

The long-running entry is available for the later composed run:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl :general-search-engine-replication -am \
  -Dtest=V53NativeCarriedVotePrefixProcessTest \
  -Dsurefire.failIfNoSpecifiedTests=false test

python3 -B -m scripts.v53.native_carried_vote_prefixes \
  general-search-engine-replication/target/v53-native-carried-vote-prefixes/run-<id> \
  --qualify
```

Remaining work includes actual native vote-prefix qualification, application and
ledger transient bytes, publication installation, scratch and combined resource
maxima, the remaining carried-process axes, application-ACK recovery and the
final-source cohort. No production Java, runtime bounds, workflow, frozen workload
or hosted-subset catalogue changes in this component.
