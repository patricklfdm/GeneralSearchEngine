# Required-four native replacement topology

Status: **native execution failed; topology qualification remains OPEN**.
This batch adds the opt-in regression and reader, preserves the failed original,
and diagnoses a real source/floor capacity conflict. It does not change production
Java or claim that the conflict is fixed.

Follow-up: [deferred grant capture](PHASE_3_DEFERRED_GRANT.md) now implements
the clean-source scheduling correction. The failed execution and development
index below describe the preceding source; a successful complete native run
on the corrected implementation is still required.

The earlier 5-REPLACE floor histories retain four physical copies, but their
three live common members already satisfy both majorities. Four observed copies
do not establish the availability case in which four distinct voters are necessary.
This development entry exercises that separate topology without changing the
seven frozen membership profiles, quorum rules, resource limits or time budgets.

| Role | Members |
| --- | --- |
| Old configuration | 1, 2, 3, 4, 5 |
| New configuration | 1, 2, 4, 5, 6 |
| Reachable old members | 1, 2, 3 |
| Joining member | 6 |
| Offline common members | 4, 5 |
| Required JOINT set | 1, 2, 3, 6 |
| Successor stable majority | 1, 2, 6 |

Removing any member from the four-member JOINT set loses an old or new majority.
The departing member 3 participates in FINAL ACCEPT/PROOF under the joint view.
After applying FINAL it retains a nonvoting applied end: it must not create a
successor checkpoint ACK or ancestor endorsements. The three successor members
provide the stable checkpoint and fresh BARRIER.

## Native execution and independent replay

`V53JoiningProfile` adds the explicit `5-REPLACE-required-four` development
selector. The optional JUnit method reuses the complete typed learner,
RESERVE/PREPARE/READY/SEAL/INTENT, retention initialization, native continuation
and joining-owner cold reopen. It closes the existing listeners for 4/5 and
checks the actual selected sets at JOINT and stable installation. It neither
manufactures a vote nor changes the existing forty-minute fixture lifetime.

`required_four_evidence` fixes this topology independently of producer labels.
The shared semantic reader reconstructs all eleven original slots, selected
BASIS/source bytes, distinct ACCEPT/PROOF receipts, catalogs, applied files and
published checkpoints. The explicit override leaves all existing profile defaults
unchanged. The reader checks the exact voter sets, all four insufficient
three-member subsets, absence of departing successor votes and the original
stable cold owner. Native internal readiness remains distinct from public READY.

The publication reader additionally derives all 34 applied-to-published file
inventories. The departing FINAL owner has the exact nonvoting force sequence,
and its checkpoint receipts must come from original delivered transfers by the
successor voters. Its future-retention record omits a local checkpoint ACK;
the complete future/peer transition and original generation files are compared.
These are the reader's required publication checks. They have component tests,
but have not passed on a complete required-four native history.

The reader first validates the unmodified history. Its thirteen copy-only negatives
remove each required FINAL proof, forge a departing ACK, remove a successor ACK,
corrupt the original joining ACK, change an offline owner or remove/reorder the
final readiness event. They also alter the departing owner's retained grant,
future ledger and force sequence. Every negative requires its exact rejection reason;
an unrelated failure cannot qualify a rejection.

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl ../general-search-engine-replication -am \
  -Dsurefire.failIfNoSpecifiedTests=false -Dv53.joining.requiredFour=true \
  -Dv53.publication.resources=true \
  '-Dtest=V53JoiningIntentExportTest#requiredFourVotersCompleteReplacementFinalAndStableBarrier' test
python3 -m scripts.v53.required_four_evidence "$ORIGINAL" --qualify
```

Preserve the printed `v53NativeDispatchEvidence` directory, Maven log and exact
source/build hashes. Do not run another Maven build over these outputs during
the native execution. Resource observation collection is retained for later
physical composition; this semantic reader does not qualify those counters.

## Scope and remaining work

The first native execution failed after **955.6 seconds**, during a second
old-side retention preparation, before JOINT selection, FINAL and the stable
BARRIER. The new joining owner had completed retention initialization and cold
reopen. The retained result is `resource ownership/count` from floor reservation;
this was not a fixture deadline or an unsuccessful transport retry.

The proposer retained three original source directories and one current
generation. The four required floor copies would need seven SOURCE slots,
exceeding the frozen six. At the failed allocation it also held the three
authenticated receiving sources: they cannot be released before the corresponding
floor copies are forced. The existing per-copy handoff cannot solve the final
`3 + 4 > 6` obligation. Original images in this history were only 837 bytes;
increasing a byte or time allowance would not fix the slot conflict.

`V53RequiredFourCapacityTest` isolates this arithmetic with original conditional
joint copies: two sources plus four copies succeed at SOURCE=6/APPLICATION=7;
three sources reject without modifying physical files or reservations. That
deliberate storage rejection fences the owner; the first diagnostic test draft
incorrectly queried a live-only accessor afterwards. The assertion was corrected,
and all 22 diagnostic/profile/reservation tests pass. This is a conditional
storage diagnosis, not a native liveness result.

The unmodified failed history is rejected at `joining complete control order`,
before any of the thirteen copy-only mutations runs. Zero required-four histories
or native negative qualifications are accepted. The 844 relevant Python tests
pass, and the earlier ordinary 5-REPLACE original still passes semantic and
physical replay with these reader changes. Those historical checks do not
qualify the new topology. The [development evidence index](phase3-evidence/required-four.json)
retains the native failure, both diagnostic attempts and exact source/class hashes.

The next implementation work must order new-grant capture and source retirement
so that a third source does not consume headroom needed by its governing floor.
Retirement still needs a strictly newer **durable PROMISE**, the complete floor,
exact ancestry/tail preservation and forced retirement/journal replacement.
A volatile observation or reserved ballot counter is insufficient. A split
promise/capture path would also need exact handling of higher-ballot fencing,
incomplete-PROMISE reopen, same-ballot refusal, pending capture/ACCEPT exclusion,
and incoming PREPARE as well as the outgoing controller. This is a design
direction to test, not implemented permission to delete or reuse a ballot.
Do not raise the frozen limits, release original files early, or retry the
unchanged long history merely to obtain a green result.

This is an unqualified development semantic/publication gate. Complete physical/network and continuous
ledger replay of this topology, combined resource maxima, process cuts and
final-source cohort admission remain required. It adds no accepted cohort slot
and no hosted subset: the existing twelve subsets / 544 planned histories remain
unchanged. Phase 3 remains **OPEN**.

Rollback removes this opt-in topology and its reader/tests together; the ordinary
ADD/REPLACE profiles and production quorum/publication logic are unchanged.
