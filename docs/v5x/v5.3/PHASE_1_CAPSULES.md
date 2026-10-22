# Phase 1 complete capsule walk

Status: **locally qualified conditional verifier and physical byte fixtures**.
The membership runtime remains disabled. This is not live replica/crash acceptance
and Phase 1 is not closed.

## Verified chain

`MembershipCapsule.verify` starts with exact ROOT/GENESIS bytes and reconstructs
the initial catalog digest. It walks linked CHECKPOINTs to the current catalog,
application and cut. Historical full catalogs and ordinary entries can be absent.

- RANGE advances within exactly the same stable view and binds both catalog and
  application endpoints. It has no member certificate/descriptor; adjacent ranges
  in one era are refused, since extension replaces the trailing range.
- MEMBERSHIP advances one index and retains original ENTRY, payload, ACCEPT,
  PROOF, certificate and full sealed descriptor. Phased records satisfy both
  **preceding** majorities and exact owned parent observations. Original origin
  bytes are not rewritten for recovery.
- INTENT moves old stable to joint; FINAL moves that exact operation to new stable
  generation + 1. Neither changes application materialization. INTENT operation
  numbers increase, and the current catalog allocator must remain beyond them.
- Every CHECKPOINT_ACK binds the complete framed statement, durable voter identity
  and end cut, with authenticated ownership **after that exact end was applied**.
  Count the end cut's **next** majority: both sides after INTENT, new stable after
  FINAL. ACCEPT/PROOF witnesses cannot substitute for checkpoint endorsements.
- Terminal catalog/image/cut must equal the walked endpoint. Result retirement
  never erases historical descriptors or permanent identity reservations.
- Actual referenced bytes fit 16 KiB per range / 48 KiB per member edge, in addition
  to the complete packet/envelope/catalog bounds. At most `3 * INTENTs + 1` items
  are accepted, with the frozen 256-change lifetime limit.

The result has a private constructor and immutable verified boundary anchors.
It records actual starts/ends, not an invented entry at an index hidden inside a
range. Historical certificate checking now uses its original governing view;
current control admission still separately checks the applied operation catalog.

## Ownership assumption and fixture scope

Authenticated `Owned` observations must come from the later storage/transport
integration, never an untrusted wire tuple. Digests are not signatures and this
does not provide Byzantine tolerance. The verifier does not establish actual force
ownership on its own or authorize service, campaign activation, selectors or file
deletion. Phase 2/3 must obtain these observations from actual owned events.

The Java worker produces all seven original byte histories, then compacts every
cut 0..9: **70 packets**. Ordinary entries and historical full catalogs are actually
absent from the packed inventory; only the current full catalog remains. The
retirement case still retains both original member edges and their descriptor.

The independent Python reader validates each original history and derives every
catalog from its original commands before checking the packed result. It checks
exact originals, byte budgets, identities, both end-view majorities, and owned
applied/ACK file pairs. The 524 checkpoint ACK fixture copies have paired file-force
traces. These are one JVM's actual fixture writes, not distributed replica execution
or a claim that a removed live process later endorsed an old cut.

Sixteen original-first negatives cover hidden/missing edges, lost descriptors and
PROOF bodies, either joint majority alone, duplicate ACKs, altered checkpoints and
catalogs, missing ownership, wrong applied cuts, force ordering, missing/linked
files, scope relabelling and incomplete cut coverage. Relocated replay must agree;
an invalid original cannot qualify any negative case.

## Repeat and inspect

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53CapsuleTest,V53ContextTest,V53ResourceTransferTest,V53SourcePacketTest,V53FormatTest,V53DeclarationsTest,V53PublicApiInventoryTest,V51VersionBoundaryTest \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_capsule_evidence \
  scripts.v53.test_context_evidence scripts.v53.test_source_packet \
  scripts.test_ci_v51_bundle scripts.test_build_coordinates
python3 -m scripts.v53.capsule_qualification target/v53-capsules/run-UNIQUE
```

The driver refuses existing output and retains source/JAR/class hashes and failed
attempts. The 5.3 build bundle adds the executed, unskipped capsule suite while
preserving earlier prerequisites. It also requires the exact worker/helper classes
and golden byte resource used after restoration. The [retained receipt](phase1-evidence/capsules.json)
records 45 focused Java tests and 34 Python tests passing. Logs: `target/v53-phase1-capsules/`. The first
test compile exposed a wildcard-list mutation; the corrected typed list and passing
qualification are retained separately.

## Remaining Phase 1 requirements

[Original frozen-source selection](PHASE_1_SELECTION.md) now verifies proposer-inclusive
quorums, exact references, compatible cut/catalog/application anchors, longest
proven prefix and highest next-slot tail. Supplemental existing-format checkpoint
proofs bridge hidden same-era anchors without resampling a basis. A covered slot
can settle a different minority accepted value; the original tail remains evidence.
This local conditional calculation still needs actual grant/force/install integration.

Same-round/catalog/compacted-source model composition, the full finite S/N schedule
inventory and the final requirement audit remain open. These fixtures do not replace
those deliverables or later public runtime/fault qualification.
