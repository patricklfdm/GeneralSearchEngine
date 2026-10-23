# Pending-context capture and rebinding

Status: pure transfer admission locally qualified; Phase 2 remains **OPEN**.

A selected generation can come from another voter's longer source and omit a
local original certificate or packet extras. Capturing only that generation and
its current vote is insufficient to move an old
[pending context](PHASE_2_PENDING_CONTEXT.md) away from its pinned backing source.

`MembershipPendingTransfer.capture` takes an already reconstructed original
context and a verified current capsule with the same root and complete terminal
anchor. It retains exactly:

- Every current packet object and image.
- Every object and image from the original packet envelope.
- The original ENTRY, payload, ACCEPT, and any original PROOF/certificate.

Only the current capsule's inventory digest changes. Root, cut, catalog,
application, items and original phase bytes remain unchanged. It verifies exact
hashes/materializations, admits the frozen packet/envelope/image bounds before
encoding the complete result, and requires the verifier to return that exact
packet. No filesystem operation or ownership observation occurs here.

`MembershipPendingContext.rebind` first reconstructs the old context against its
exact original backing. It then requires a strictly newer backing ballot and
reconstructs the same original generation and vote against the new source. Only
the backing packet identity and PROMISE/BASIS may change. Original selector,
metadata, packet envelope and vote identities cannot change. Replacing an old
pending ACCEPT with a newer one is a separate owner transition.

The union does not recursively copy previous backing packets. Thus a current-only
extra from one abandoned capture is not added to all subsequent captures. This
does not remove bytes already legitimately present in the current generation.

## Local qualification

The targeted reactor passes **59 Java tests**, including six new transfer cases:

- Capture from an actually installed generation lacking the original certificate.
- Six successive rebindings, from backing ballot 21 through 27, preserving one
  exact original ballot-20 vote/generation and discarding prior capture-only extras.
- Missing certificate, wrong accepted tail, same/older ballot, stale backing and
  corrupted image rejection; original input and returned array isolation.
- Changed root/parent and substituted verifier output rejection.
- Two individually valid inventories whose union admits exactly seven images
  and rejects an eighth.
- A valid current packet near 32 MiB whose protected union exceeds the existing
  bound; the original extra cannot be silently omitted to fit.

Original input material uses actual local ACCEPT/PROOF/certificate operations and
an actual selected-generation installation. New backing source ownership in the
pure six-transfer fixture is **conditional**, not a new physical source force.
The two capacity tests use explicitly re-bound synthetic inventory extensions;
they do not claim maximum-size application semantics or global lease admission.

Independent Python replay checks all seven original-byte contexts and the exact
current-plus-original union at every transfer, unchanged authorities, no prior
capture accumulation and scope receipts. It rejects **12 exact-reason mutations**
after validating the original, and validates relocated evidence. Normal and
optimized Python give identical results. The unchanged original-context replay
also rejects 22 mutations, and the existing context-file component passes its
32 repeated-crash cases/96 JVMs and 22 negative replays in this build.

Retained source/build/raw hashes and limits:
[local evidence index](phase2-evidence/pending-transfer.json).

```bash
/opt/maven/bin/mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -pl :general-search-engine-replication -am \
  '-Dtest=V53PendingContextTest,V53PendingContextFilesTest,V53SourcePacketTest,V53FloorTest,V53ResourceTransferTest,V53DeclarationsTest,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
# Use the v53PendingTransferEvidence directory printed by the test.
python3 -m scripts.v53.pending_transfer_evidence <transfer-evidence-directory>
python3 -O -m scripts.v53.pending_transfer_evidence <transfer-evidence-directory>
```

## Remaining integration

These helpers are not yet used by the live journal owner. The owner still needs
to reserve all physical copies, force the new source and exact context before
retiring old authority, recover interrupted replacement, and preserve higher
observations without returning an old ACK. Capture intent currently obtains
images from the selected generation alone; expanded protected materializations
need explicit lifetime and recovery binding before that path can use this result.

The near-limit rejection is a real remaining admission constraint. It is not a
proof that every maximal valid current/original pair can progress. Before granting
a transition, the complete owner must demonstrate a bounded completion path or
refuse admission while the previous usable authority remains intact. Full
three/four/five and joint-voter repeated recovery, original-certificate lifetime
after replacement, global peak resources, offline initialization and the complete
physical closure audit remain outstanding. No public runtime, remote force,
power-loss, protected CI or paid-cloud claim is made by this batch.
