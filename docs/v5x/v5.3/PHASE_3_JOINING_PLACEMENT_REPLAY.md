# Native joining placement replay

`scripts.v53.joining_placement_evidence` connects the independently derived old
owners' history to the original joining node's placement. It first runs the
[bootstrap-through-INTENT derivation](PHASE_3_JOINING_TRANSITION_REPLAY.md), then
derives all 65 files in eight present joining directory families. All seven
absent families remain absent. The [batch receipt](phase3-evidence/joining-placement.json)
binds the reader source, original producer, tests and portable replay.

The input remains the one unchanged `df22c398` native `3-ADD` execution. No second
workload, synthesized owner, retry or combined attempt supplies missing state.

## Independent physical derivation

The old owners' PREPARE, SEALED and INTENT publications at cuts 4, 8 and 9 are
derived from bootstrap. Their exact generation members, including source packet,
images, selected-source records and ancestry, supply the three received copies.
The reader reconstructs:

1. The learner plan and retained-source framing, nonvoting replica identity and
   admission file, typed application backup, original prepared receipt and
   prepared-location marker. Configuration comes from the original bootstrap
   descriptor; the receipt comes from the independently reduced operation.
2. Pending INTENT metadata from the original ENTRY/ACCEPT/PROOF/CERTIFICATE,
   reduced catalog and checkpoint. The new node's checkpoint ACK, retained-source
   marker and link are reconstructed without treating the earlier SEALED packet
   as an installed joint generation.
3. The published INTENT source and its link to that same original pending owner.
   Old preparation, SEALED and joint source copies are not interchangeable.
4. The adopted generation, certificate-derived promise, allocator, empty pending
   vote, root/genesis/node and selector. The joining node imports no selected
   basis or owned tail from the old voter, and starts in generation `a`.
5. The voter-stage decision and complete ready inventory, the custody decision,
   the ordered atomic placement moves, placement completion and joined-admission
   record. The custody inventory is reconstructed by reversing only the seven
   declared moves from the fully derived placed files.

Paths and inode keys are original observations read from the retained inventory.
The reader checks deterministic sidecar names, shared original parent identity,
the same-filesystem move requirement, and disjoint receiving locations. It never
opens recorded paths or uses the inodes of a downloaded copy. File contents,
hashes and sizes in ownership records are calculated from the derived bytes;
ownership receipts cannot attest to themselves.

The negatives refresh the portable inventory after mutation, and must pass the
previous whole transition reader before the new placement reader rejects their
declared reason. They cover altered preparation/configuration, stale source use,
broken pending-owner links, forged adopted generation/selector, missing ancestry,
premature voting ledgers, extra staging files, changed moved inode identities,
incomplete custody roots, reordered moves and forged admission fingerprints.

```bash
python3 -B -m scripts.v53.joining_placement_evidence <original-raw-directory> --qualify
```

## Remaining closure requirements

This qualifies the complete original **placed** inventory, before predecessor
retirement and native initialization. The next physical integration must derive
retirement/native-owner records and exact original deletions, old-voter joint
source preparation, the joining retention transaction, its own grant/cold reopen,
then joint recapture and FINAL/new-stable installations.

Exact physical inventories do not establish complete force/network ordering or
process-crash safety. The producer's added send/arrival observations still need
a fresh whole execution, and all seven profiles, remaining process cuts and
frozen requirement mappings remain open. `joiningPlacementPhysicalQualified`
is scoped to this original history; full physical, force/network, process and
Phase 3 flags remain false.

This batch changes Python readers/tests and progress documentation only. Runtime
Java, POMs, workflows, persisted formats and frozen limits are unchanged.
