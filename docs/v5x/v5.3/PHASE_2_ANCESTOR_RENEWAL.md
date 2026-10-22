# Bounded renewal of original ancestor checkpoints

Status: private local Phase 2 storage integration. Phase 2 and pre-cloud closure
remain OPEN. This extends [immediate-parent endorsements](PHASE_2_PARENT_CHECKPOINT.md).

## Original ancestry survives a larger range

An installed selected generation can have original BASIS cuts at 1, 2 and 4,
with earlier authenticated bridges 1→4 and 2→4. Publishing an enlarged RANGE 0→5
would hide all three endpoints. New ACKs over 4→5 alone cannot preserve the
original frozen sources. The owner must additionally renew 1→5 and 2→5.

The journal obtains required ancestors from its authenticated current ancestry,
actual retained original BASIS packets and governing floor. Before replay, every
required cut/catalog/application is checked against the original complete capsule
and original ancestry endorsements. Inventory extras and witness hashes alone
cannot authorize renewal. After exact certified replay, checkpoint planning derives
only the lower endpoints hidden within the enlarged same-era RANGE. It deduplicates
identical anchors, rejects conflicting state, and emits deterministic increasing
lower-index order. Membership boundaries cannot be hidden by this operation.

The local applied-end transaction prebinds the extra statement/ACK inventory to
the original plan. It forces all original authority, statements and the one exact
application image, then completes local ACK files sequentially. Every return and
write boundary rechecks exclusive ownership and the original ballot fence. A
partial later ACK requires all earlier ACKs and all end materialization members
to be complete. Recovery can only continue the same exact bytes.

## Fixed bounds and covered cleanup

The immediate parent plus additional ancestors remain bounded to six groups;
at most five additional pairs are stored. There is one application end image and
at most 19 stage members. The exact plan remains at most 4 KiB. The expanded
reservation is charged to the existing 32 MiB journal; global generation/image
counts and frozen 96 KiB ancestry capacity are unchanged. This transaction writes
local receipts in sequence; it does not introduce additional remote quorum
accumulators or authorize parallel protocol collection.

Private generation coverage records the exact additional local endpoints. The
complete generation must contain authenticated ancestry for them. Publication
matches every returned local receipt to its original forced files, and remote
ACKs still require separate actual observations. Reopening validates the same
coverage, including through governing-floor copies. Covered cleanup derives the
exact extra files from the published end and bound endpoints, validates every
remaining byte before deletion, and removes the plan last.

Old seven- and nine-member stages remain unchanged when no additional ancestors
are needed. No public API or frozen wire/record kind is added.

## Qualification

The [source/build/raw index](phase2-evidence/ancestor-checkpoint.json) distinguishes
the actual current local votes/ends from historical fixture authority. It covers
real separate original captures at cuts 1/2/4, immutable BASIS preservation, new
three-group endorsements, publication/reopen, missing or stale proofs, foreign
local observations, file corruption, sixteen additional write interruption labels
and repeated recovery with higher-ballot fencing.

Twelve halt/SIGKILL cases run in 36 fresh JVMs, spanning extra statement/ACK writes,
selector publication and covered retirement. Independent replay reconstructs the
new DATA catalog and all statements from actual original BASIS/source packets,
the older retained `ancestry.gsr`, original votes and peer ends. It then compares
the exact write/force/deletion sequence and intermediate/final inventories. Ten
negative evidence mutations reject; portable and optimized Python replay are
separate checks. The earlier parent-only process evidence is also replayed using
the extended independent driver.

The initial fixture test compilation error and the initial replay layout-assumption
failure remain retained. They are not counted as successful qualification. Earlier
checkpoint ownership/bootstrap is conditional; process crashes do not establish
power-loss durability or distributed public runtime acceptance.

## Remaining work

This completes renewal for a bounded set of authenticated hidden ancestors. Stable
same-round continuation still needs a bounded proof of the original selected first
choice separate from the latest parent/certificate. It must preserve original
SELECTED/BASIS and never reconstruct READY after restart.

Coordinated lifetime work must prune ancestry only after original source/floor
obligations permit it, and maintain next-publication ancestry headroom. The subsequent
[admission check](PHASE_2_PUBLICATION_ADMISSION.md) now refuses excessive group/coverage
requirements before new ACCEPT, retaining original authority; that refusal alone
is not a complete long-lived progress guarantee. Full-size/profile resource qualification, remaining
PROMISE recovery and complete bootstrap remain open in the
[Phase 2 checklist](PHASE_2_CLOSURE_CHECKLIST.md).

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  '-Dtest=V53AncestorCheckpointTest,V53AncestorCapacityTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.ancestor_checkpoint_evidence <v53AncestorCheckpointEvidence-directory>
```
