# One native automatic service history

Phase 3 remains **OPEN**. The bounded automatic owner now has a complete local
three-voter TCP history from its election wait through STATUS discovery, fresh
selection, BARRIER, a scheduled heartbeat, queued DATA and close. The caller
submits DATA to the owner; it does not sequence the native activation or slots.

## Exact execution boundary

The native round exposes the same private session adapter used by
`automaticOwner`. The whole-history test decorates that adapter solely to retain
original snapshots, capture the diagnostic heartbeat result and delimit the
declared history. Its replies, votes, original files and publication remain real.

After the first heartbeat, a test latch waits for DATA admission before returning
to the owner loop. It does not renew the original deadline. The fixture closes
after DATA, either from the caller or at the next scheduled pulse before sending
it. These gates prevent an unbounded observation history; they are not proof of
ungated scheduling under arbitrary delays, repeated elections or failover.

The policy derives from unchanged default bounds: 5-second heartbeat/RPC,
15–25-second election wait and 20-second operation policy. The existing native
round lifetime remains 180 seconds. Full test execution, including the fourteen
owner regressions and build, completed in 114.904 seconds. This is one execution
measurement, not a latency target or availability claim.

## Independent acceptance

The [source-bound receipt](phase3-evidence/automatic-service.json) retains both
native histories from the final fifteen-test Java execution and their readers.

The complete service reader reconstructs original bootstrap, selected state,
publication, both slot recording majorities and both application outcomes. It
checks the two pre-grant STATUS discovery peers and all 39 original transfers.
The heartbeat is validated separately against the physically reconstructed
barrier cut: two immutable sends and two original replies, actual receipt before
the returned diagnostic majority, unchanged before/after storage and no read
lease. DATA then advances the original published prefix normally.

The existing heartbeat reader now accepts explicit `--discovery` for this
entry. That mode retains every existing physical/protocol check and adds the
original discovery replay plus its four negatives. Its default mode is unchanged.
Seventeen exact service mutations reject for their intended reasons. A separate
native WAITING-close history passes its original replay and six negatives, for
23 total. Twenty focused Python tests also pass. No unrelated original failure
is accepted as successful negative qualification.

The reader's `autonomousElection=false` remains intentional: original bytes and
wire establish this finite protocol history, not the full automatic election or
process-crash acceptance matrix. The producing Java entry establishes which
control loop invoked the work; it cannot substitute for those remaining gates.

## Remaining acceptance

Run this complete entry in one workspace when qualifying the eventual final
runtime; do not distribute activation, heartbeat, DATA or close across runners:

```bash
mvn -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53AutomaticServiceTest test
python3 -B -m scripts.v53.heartbeat_round_evidence RAW_DIRECTORY --qualify --discovery
```

The test prints `v53NativeDispatchEvidence=...` for `RAW_DIRECTORY`. Whole-history
hosted execution may parallelize independent bootstraps only. Repeated fresh
campaigns after failed activation/heartbeat, admitted activation-progress timers,
native failover/restart, all seven transition profiles and the full Phase 3
process/negative matrix remain required. No public runtime, workflow, frozen
format/budget or paid-cloud behavior changes.
