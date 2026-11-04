# Phase 3 cold majority continuation after resource refusal

This development probe extends the [failed combined-resource history](PHASE_3_COMBINED_RESOURCE_PROBE.md)
through a cold owner restart. It preserves that failed prefix and its original
unresolved INTENT. It does not qualify automatic recovery of the partial floor,
complete resource headroom or the complete Phase 3 cohort.

## Original directories and observed outcome

The opt-in `V53CombinedResourceRecoveryTest` first runs the original 4-REMOVE
pressure scenario. The two externally held receivers are closed after the
capacity failure. All old endpoints, transports and journals close. The test
then opens the **same replica and materialization directories**, with the same
bootstrap request/result and a new observation directory. It does not bootstrap
again, copy an evidence snapshot into a live store, delete a partial floor,
substitute the pending entry or modify a resource/timing limit.

The first development execution completed in 357.043 seconds (including its
isolated build). This is a successful majority continuation, not successful
recovery of every node:

| Stage | Observed original owners | Result |
| --- | --- | --- |
| Pressure failure | node-1 pending INTENT at index 5; node-2 partial floor | Original FAIL preserved and independently diagnosed |
| First cold selection | node-1, node-3, node-4; ballot counter 4 | Original index-5 INTENT selected without changing its origin or bytes |
| Joint completion | node-1, node-3, node-4; counter 5 | FINAL published at index 6 |
| Stable barrier | node-1, node-3; counter 6 | BARRIER published at index 7; internal readiness observed |
| Partial-floor owner | node-2 | Remains at index 4, byte-for-byte unchanged; refuses new PREPARE with `native maintenance requires recovered storage` |

The source was then tightened to assert explicitly that node-2 remains unchanged
and refuses maintenance admission. The final producer execution took 340.001 seconds and passed; its checks are
identified in the [development receipt](phase3-evidence/cold-resource-continuation.json).
Neither execution is a retry that turns the failed pressure segment green.
The first source did not assert the node-2 endpoint state; its retained bytes
already showed that state. The later assertions make the narrower scope explicit.

## What the reader establishes

`scripts.v53.combined_recovery_observations` first independently diagnoses the
entire original pressure prefix using the existing reader. It then checks exact
cold-start snapshots against those original closed stores; the inherited command;
selected surviving cohorts; current-generation inventories; derived membership
catalogs, ACCEPT/PROOF/CERTIFICATE records and unchanged application bytes;
publication/retention ordering and acknowledgements; original round completions;
and the unchanged node-2 state throughout the continuation.

It returns **OBSERVED**, not an admitted full-history PASS. In particular, it does
not independently derive every resumed selection, maintenance retirement or
transfer from bootstrap. Directory strings are producer observations, not a
portable proof of process identity. Java owner close/open and original-byte
continuity support this component's same-directory claim; this is not SIGKILL or
power-loss qualification. Its negative variants check these stated observation
boundaries and must not be counted as full Phase 3 qualification negatives.
Thirteen variants include changed certificates/catalogs, lost force observations,
and an invented successor checkpoint ACK from the departing FINAL owner. The
first reader incorrectly required that ACK boundary from node-4; the original
trace instead has the existing `APPLY_NONVOTING_DIRECTORY_FORCED` boundary. The
reader now derives this distinction from the exact before/after membership, with
a focused regression. That reader-development failure remains retained.

The test is explicitly selected with `-Dv53.combined.recovery.probe=true`.
No existing Required job, production implementation, POM, timeout or capacity
limit changes. Eleven optional hosted subsets and their 512 planned histories
remain unchanged. The fixture's extra receivers still have unproved reachability
through normal controller lifetimes.

## Remaining recovery work

1. [Explicit original-copy completion](PHASE_3_PARTIAL_FLOOR_RESUME.md) now has
   storage replay with the pending ACCEPT and predecessor authority preserved.
   Extend this to the automatic acquisition path and other interrupted positions.
2. Qualify interruptions during a native controller's real floor construction,
   separately from artificially extended external receiving lifetimes.
3. Supply an automatic continuation path only when the original missing copies
   can be acquired under the existing fence, capacity and original proposal.
   A different equal-cut generation or an available majority must not silently
   replace the durable proposal. Unavailable originals must remain a safe refusal.
4. Independently replay and admit that complete continuation before counting it
   toward phase-wide recovery or resource completion.

The current code's deliberate refusal of an unfinished floor preserves authority.
The observation that another majority can finish REMOVE does not discharge the
unfinished owner's recovery obligation.

## Local reproduction

Run from a fresh isolated source/build and retain both segments:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.combined.recovery.probe=true \
  -Dtest=V53CombinedResourceRecoveryTest test
python3 -B -m scripts.v53.combined_recovery_observations "$ORIGINAL_HISTORY" --qualify
```

Removing this optional producer/reader and its fixture constructor is a test-only
rollback. Preserve original failed and successful observations in either case.
