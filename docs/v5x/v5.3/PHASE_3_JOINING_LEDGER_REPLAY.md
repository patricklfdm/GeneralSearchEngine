# Original-source joining ledger replay

Phase 3 remains **OPEN**. This layer reconstructs the joining initialization
bytes independently of the Java test's reported seed/plan/PASS fields. It does
not establish complete capsule ancestry, force/network provenance, process-death
recovery, FINAL/BARRIER completion, or public readiness.

`scripts.v53.joining_retention_evidence` first reads the strict portable native
joining snapshot. The installed generation and its actual capsule supply the
new identity, root and cut. Each retained old source must occur in its actual
old owner's grant journal and original `sources/<basisId>/source.gscp`. A copied
standalone source or a claimed endpoint alone cannot pass this binding.

The independent decoder checks the exact old majority, distinct ordered owners,
same original ballot, settled tails, full packet/BASIS inventories, included
peer/learner wrappers and their matching capture promises. It conservatively
unions every retained endpoint, including pending learner renewals. Decoded
confirmations cannot discard uncertainty. Different same-index endpoints, a
future endpoint, wrong permanent identities and excess endpoint counts reject.

From those inputs, derive the canonical seed and all three revision-zero ledgers
for the original joining identity. Reconstruct the initialization decision and
completion frames, including their recorded original inode keys and native-owner
binding; compare every byte to the actual files. Current initial ledgers must
still match exactly. A later used-owner snapshot is deliberately not accepted as
an initialization snapshot. Recorded paths are data, never opened as live paths.

The reader deliberately returns **PARTIAL**, including separate false fields for
capsule ancestry, force/network and whole-history qualification. The original
source snapshots still need the complete protocol history oracle: the inventory
and source binding checked here do not turn stored claims into consensus proof.

## Validation

- 42 focused Python tests pass, including all five conditional ADD/REPLACE
  profiles, source/ballot/identity rejection, conservative union and strict copied
  inventories. Conditional fixtures are never native-history evidence.
- Replayed the initialized/cold-reopened substage of the retained failed native
  run `joiningearlyhistory-4f644ca2`. Its two original old sources reconstruct
  exactly the actual seed, peer/future/learner ledgers and both transaction files.
  That execution still failed later at the coordinator scratch-parent defect.
- All 13 exact evidence negatives reject. Mutated copied files have their copied
  inventory hashes updated where appropriate, so these cases exercise semantic
  checks rather than merely stopping at a checksum. Validate the unmodified
  original before any mutation; an invalid original cannot count as successful
  negative qualification.
- No Java, workflow, POM, wire/resource limits or cloud behavior changes in this
  increment. The corrected coordinator whole history remains independently
  tracked in [native qualification](PHASE_3_NATIVE_JOINING_QUALIFICATION.md).

Portable source/data hashes and command results are recorded in
[the receipt](phase3-evidence/joining-ledger-replay.json). The corresponding
archive retains the reader dependencies and original failed-history raw bytes;
each archive member is hash checked after packing.

```bash
python3 -B -m scripts.v53.joining_retention_evidence /path/to/native/raw --qualify
```

This command qualifies only the stated ledger derivation layer. Complete
initialization authority, full native/process histories, all actual profiles and
alternative majorities remain in the [acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md).
