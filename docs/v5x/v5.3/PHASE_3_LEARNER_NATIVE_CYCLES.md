# Phase 3 — continuous native learner alternation entry

`V53LearnerAlternationNetworkTest` extends the original three-revision native
history to six PREPARE revisions. It uses one reservation, one native voter
group, the original round deadline and one learner resource pool. Revisions
1/2 establish admission and the immutable seed; revision 3 selects B1; revisions
4/5/6 select A2/B3/A4. CANCEL is submitted only after all cycles finish.

Each added revision retains native voter states before/after PREPARE, original
received source bytes and a typed receipt. Six learner snapshots cover before
transfer, installed, before selection, selected, retired and cold-reopened states.
Snapshots preserve recorded original paths/inodes as data alongside copied bytes
and resource usage. The trace records each added revision's received-exchange
interval and exact selected source/generation/receipt digests. The learner never
opens a voting listener, remains outside the native source's voter set, and cold
reopen must preserve its original authority bytes and typed state.

Selection happens after the transfer closes. Old typed/source views must revoke;
covered retirement must reduce the two generations to one; every complete store
close must return all learner leases. Cold reopen must decode the same receipt
and empty application from that exact revision. The original 900-second round
profile remains unchanged. Existing three-revision acquisition/installation/
selection entries retain their modes and output shapes.

## Execution and acceptance boundary

The [compile receipt](phase3-evidence/learner-native-cycles.json) records
**COMPILED_NOT_RUN**. Compilation includes the complete core/replication test
sources and confirms unchanged production sources/binaries relative to A28.
It does not execute the native history, establish process-death behavior, or
satisfy an acceptance gate. No hosted workflow has been dispatched for it.

Run the whole history as one isolated hosted unit on the final source:

```bash
mvn -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false \
  -Dtest=V53LearnerAlternationNetworkTest test
```

The entry prints `v53LearnerAlternationEvidence=...` and progress at each added
revision. A hosted wrapper must also provide periodic process/elapsed updates
and retain failed attempts. Never shard the revisions or merge snapshots from
unrelated histories. Independent physical/wire/force replay and exact evidence
negatives must validate the original successful history before acceptance; the
Java result explicitly leaves `independentReplayQualified` and `phase3Complete`
false. The existing A25 vacancy reader is intentionally limited to first-B
snapshots and is not a validator for these rolling histories.

The first entry is the native 3→4 ADD profile. All five joining profiles,
maximum combined resources, partial/process-death cuts, cancellation recovery,
matching local INTENT and autonomous integration remain in the
[deferred acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).
