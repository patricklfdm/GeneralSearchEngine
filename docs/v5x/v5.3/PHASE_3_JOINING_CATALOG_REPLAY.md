# Native joining catalog, certificate and checkpoint replay

The complete `3-ADD` early-start joining history now has a successful execution
on source `df22c3987ab7f1e6af47fae83bc2e1becc51bf35`. One isolated Maven/JUnit invocation
took 954.740 seconds and completed initialization, FINAL, the new-view BARRIER,
stable retaining cold reopen and close. There was no retry. The bounded writer
retained all 17,616 events and 2,211 wire pairs. The earlier trace-encoding failure
remains a separate failed attempt and is not stitched into this result.

The [source/build-bound receipt](phase3-evidence/joining-catalog.json) separates
that executed history from the independent reader introduced in this batch.
Phase 3 remains **OPEN**: complete physical-state derivation, force/network causal
replay, process-death and the remaining profile matrix are not implied by this pass.

## Independent semantic chain

`scripts.v53.joining_catalog_evidence` starts with the original bootstrap plan,
image and exact derived initial files. It does not use fixture result booleans as
authority. The actual eleven slots are:

| Index | Entry | Governing effect |
| --- | --- | --- |
| 1 | BARRIER | Initial stable internal readiness |
| 2 | RESERVE | Reserve the original new permanent identity |
| 3 | BARRIER | Fresh maintenance selection and stable readiness |
| 4 | PREPARE | Freeze the exact preparation revision and predecessor |
| 5 | BARRIER | Fresh maintenance selection and stable readiness |
| 6 | READY | Bind the actual typed receipt and unchanged image |
| 7 | BARRIER | Fresh maintenance selection and stable readiness |
| 8 | SEAL | Bind request, preparation and receipt |
| 9 | INTENT | Old certificate and separate old/new checkpoint majorities |
| 10 | FINAL | Joint ACCEPT/PROOF majority; new stable checkpoint majority |
| 11 | BARRIER | Fresh new-view selection before internal readiness |

Node 3 stays offline. Nodes 1 and 2 provide the original old majority; node 4
supplies its separately retained joining checkpoint ACK, then participates in
the joint and new-view phases. The reader checks that the offline node's actual
files remain unchanged through close.

For every slot the reader independently checks:

- The original entry's root, predecessor, authority, permanent proposer identity
  and ballot; distinct ACCEPT and PROOF bytes, receipts and both governing
  majorities; exact copies in the participating owners' actual applied snapshots.
- The fixed selected set, original BASIS bytes in each owner's journal, original
  frozen source packet, highest selected prefix and no source-identity reuse or
  same-ballot selection drift.
- Catalog reduction from the previously derived catalog, rather than accepting
  the resulting catalog as its own proof. READY also matches the retained typed
  learner receipt and exact backup members of the original application image.
- Applied-end inventory, exact application/catalog/certificate/checkpoint bytes,
  immediate parent and retained ancestor endpoints, and original ACK identity.
- Published capsule continuity and every membership edge, original certificate
  and sealed descriptor. Each endorsement must equal an observed original ACK
  from the corresponding applied end; INTENT's new-side ACK must also match the
  original pending-intent snapshot. A compacted range cannot hide INTENT/FINAL.
- Every original round installation, slot start/completion and readiness record.
  The publication result binds certificate, selection, published endpoint and
  generation; READY must follow that same stable BARRIER completion. The observed
  internal READY cuts are 1, 3, 5, 7 and 11.

The resulting semantic chain contains six selections and 49 checkpoint ACK
observations. Fifteen original-first negative variants reject missing slots,
wrong parents, incorrect phase receipts, duplicate or premature voters, missing
new-side majorities, stale preparation, wrong FINAL binding, altered applied
catalogs, hidden membership boundaries, changed offline state and early/missing
readiness. Every rejection must match its declared reason; unrelated corruption
cannot count as a passed negative.

The same original also passes the existing confirmed-ledger derivation and its
15 negatives. Those results remain separately scoped. Ten new lightweight Python
tests plus the relevant existing readers total 65 passing tests.

## Replay and portability

```bash
python3 -B -m scripts.v53.joining_catalog_evidence <original-raw-directory> --qualify
python3 -B -m scripts.v53.joining_retention_evidence <original-raw-directory> \
  --confirmed-peers --qualify
```

The retained archive contains the complete original raw history, source inputs,
source/build/toolchain inventories, Maven/JUnit results, collector results and
the independent reader source. Extraction verifies every archived member hash
and preserves empty evidence directories. Replaying from the archived reader in
a new directory must reproduce both original results and all 30 negative results
exactly; this relocated replay passed in 17.123 seconds. Recorded original paths
and file keys remain observations, not locations
to open or permission to reconstruct ownership.

The executed producer and archived reader have separate source manifests. Their
only source differences are the two new Python reader/test files. All 1,511
checked Java, POM and V5.3 contract JSON inputs still match the producer; this
does not make the two source snapshots identical or qualify a changed runtime.

Successful execution, collection and semantic replay are distinct gates.
`semanticChainQualified=true` does **not** imply
`completePhysicalQualified`, `forceAndNetworkQualified`, `processDeathQualified`
or `phase3Complete`. Remaining force/network replay must account for the original
transfers and callback order, and remaining physical replay must derive the
complete ownership, generation, retention and reclamation state. Preserve this
original filesystem history and its producer identity when extending those gates.
