# Native joining initialization physical replay

`scripts.v53.joining_initialization_evidence` connects the derived
[retired native owner](PHASE_3_JOINING_RETIREMENT_REPLAY.md) to old-majority joint
preparation, three-ledger initialization, the new owner's own frozen grant and
retaining cold reopen. It uses the same original `df22c398` `3-ADD` execution.
The [batch receipt](phase3-evidence/joining-initialization-replay.json) records source,
original inputs, exact negatives, related tests and portable replay. No native
workload was rerun or stitched.

## Derived history

1. Reconstruct both old voters' original LEARNER_HEAD query/ACK bytes, observing
   only their trace UUIDs. Identity, operation, correlation and the SEALED
   endpoint come from the derived history. Confirmation moves cut 4 to renewal
   while retaining cut 8; it does not discharge the old obligation.
2. Reconcile the actual newly installed node 4 at joint cut 9. Its complete
   original generation comes from placement. All existing old-peer uncertainty,
   confirmations and renewals survive adding the new identity. Original floor
   copies satisfy both joint majorities. Optional observations preserve existing
   debt when the bounded renewal capacity is full.
3. Derive maintenance, then the old proposer's next ballot and each original
   PROMISE/BASIS. Only fresh source UUIDs are observed. Exact peer/learner ledgers
   are frozen into complete packets, with their original images. Preparation
   adds no SELECTED, installation or READY. All three old-node inventories match
   `before-joint-continuation`, including the offline node and retained older
   source. This extends the composed old history to 72 complete comparisons.
4. Check the early joining generation/capsule/ancestry against the derived adopted
   generation. Derive the seed from the two original frozen old-voter sources,
   preserving unconfirmed obligations, and generate revision-zero peer, future
   and learner ledgers. The native decision/completion transaction is checked
   against that seed and the already derived immutable owner records.
5. Derive the new owner's own PROMISE/BASIS and source from those initialized
   ledgers. Cold reopen preserves the same BASIS/source and then reserves one
   additional counter without another PREPARE. The entire native snapshot now
   compares exactly: 33 files across all ten present families, with the five
   absent families still absent.

The reader also checks the original initialization write/force/rename/parent
sequence, retaining-open reseals, first source/grant force order and repeated
BASIS reuse across the three original callback scopes. Aggregate events use the
collection's bounded trace contract, not the parser limit for one wire message.
This local order check does not establish complete network or crash causality.

The 26 negatives must pass the preceding retirement gate before failing their
declared new reason. They cover head confirmation and debt, peer reconciliation,
old-ledger/source changes, premature selection, source UUID reuse, seed/initial
ledger/transaction changes, adopted and new grants, copied image corruption,
extra allocation, orphan files, omitted/reordered forces and a rewritten BASIS
or premature reopen. Changed snapshot hashes are refreshed; source and grant
mutations remain structurally well encoded where the new transition is tested.

```bash
python3 -B -m scripts.v53.joining_initialization_evidence <original-raw-directory> --qualify
```

## Remaining closure work

`joiningInitializationPhysicalQualified` and
`joiningInitializationLocalOrderQualified` cover this original initialization
boundary. Joint continuation rediscovery/recapture, FINAL and new-stable
installations still require physical derivation. Complete force/network order,
the fresh execution with complete send/arrival observations, process-death
cases, all seven profiles and frozen requirement mappings remain open. Phase 3
is **OPEN**; no failover SLA or power-loss guarantee follows from this replay.

Only Python readers/tests and progress/evidence documentation change. Runtime
Java, POMs, workflows, persisted formats and frozen limits are unchanged.
