# Heterogeneous discovered transition and maintenance ordering

Phase 3 remains **OPEN**. `V53DiscoveredTransitionTest` now keeps a surviving
node at original cut 0 while four other original members complete an actual
5-to-4 REMOVE. Node 5 remains at JOINT cut 6; nodes 1–3 reach stable cut 7.
The preparation drives real forces explicitly. Recovery uses the existing
native TCP owners and `MembershipRoundDriver.startDiscovered()`, without
supplied discovery hints, repaired offline disks or historical observations.

The removed node first acquires and adopts the original cut 7, then must fail
the local eligibility check before PREPARE. The stale survivor must separately
acquire/adopt cut 7, install a fresh selected quorum, publish BARRIER 8 and DATA 9.
Only that whole method can report its producer PASS; successful adoption alone
does not establish recovery of service or autonomous election scheduling.

## Original failure and bounded correction

The first unchanged-bound execution reached both adoptions and installed the
survivor's new round, but exhausted three five-second ACCEPT attempts. Both
receivers were still collecting/forcing maintenance copies when the sender
failed and closed them. Their later `activation endpoint closed` diagnostics
are shutdown consequences, not the first failure.

The trace showed nodes 1 and 2 contacting unselected node 3 for their floor,
although node 4 had just acknowledged the same installed selection. Maintenance
previously ordered all voters by node name. It now orders a required joining
copy first, then the original installed selection's members, then other known
eligible voters. Each group remains sorted. Before-grant maintenance keeps its
existing order because it has no current installed cohort.

This is a source preference, not floor authority. Every selected peer must still
supply the complete original packet, image inventory, generation and ancestry;
the original governing-majority floor and durable retirement checks are unchanged.
Failure to obtain a preferred copy retains the existing finite fallback path.
Selection/cut/fence checks surround reading the preference, and a member outside
the current authority is rejected. No timeout, retry count, quorum, format,
resource cap, POM or workflow is changed.

The same complete native history was then executed once on the corrected source.
It still exhausted the first ACCEPT exchanges after both adoptions and selected
installation. Thus the ordering change is **not a demonstrated timing fix**.
Both executions are retained as failed (runner elapsed 355.126 and 347.656
seconds, respectively). The two explicit independent inspections stop at the
qualified adoption boundary; neither turns these failures into a green service
history. Remaining maintenance latency requires further investigation before
this native method or Phase 3 can be considered qualified.

## Independent inspection boundary

`scripts.v53.discovered_transition_evidence` derives the original bootstrap,
seven slots, peer/future ledgers and all 54 preparation/adoption snapshots.
It then validates each actual STATUS, complete prefix and separate ancestry
transfer against those original bytes, including response delivery before
adoption. The removed owner's final original files must remain unchanged after
its adoption. No producer result supplies authority to this reader.

This entry deliberately returns **PARTIAL**, even if the Java producer passes.
It does not replay the subsequent selected installation, BARRIER/DATA history,
floor mutations or all wire traffic. Its eleven negative variants first validate
the unchanged originals, then require the exact expected rejection. Three Python
regressions cover invalid originals, mutation qualification order and invalid
bootstrap sizes; inherited readers retain their four-member default.

```bash
python3 -m scripts.v53.discovered_transition_evidence RAW_DIRECTORY --qualify
```

The [source-bound receipt](phase3-evidence/discovered-transition.json) records
each execution, retained failed evidence, timing diagnostics and the exact
inspection scope. Fourteen focused Java checks passed, including all thirteen
ordering cases and the existing maintenance lifetime gate's eighteen two-crash
histories (72 fresh child JVMs). These conditional ordering/storage histories
are separate from the native heterogeneous producer and its independent replay.

## Remaining acceptance and rollback

Complete service-round replay, native minimum-majority availability, source
rotation during transfer, all seven profiles, process-death cuts and automatic
elections remain required. Keep each continuous history on one runner; independent
complete histories may run in parallel during the later hosted campaign.

Rollback restores the former voter-name maintenance order. Persisted bytes and
adoption recovery remain compatible; never undo an already forced adoption by
restoring an obsolete configuration directory.
