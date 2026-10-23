# Retained pending context reconstruction

Status: private bounded reconstruction component, locally qualified. Phase 2
remains **OPEN**; no public runtime is enabled.

## Why a separate original context is needed

The [staged handoff](PHASE_2_STAGED_HANDOFF.md) can retire derived work after one
higher installed selection. The original pending vote still depends on its own
generation, round coverage and selected sources. A later observed ballot must
fence the intermediate round; retaining that original generation indefinitely
can prevent another selected installation. Deleting it would lose verification
authority. The next storage integration needs an exact bounded representation of
the original context before transferring any reference or reclaiming its files.

This component reconstructs original bytes from an immutable description and an
exact separately retained source. It does not force that description, grant a
vote, establish a floor, delete a generation/source or authorize a publication.

## Representation

The private GSPC 1.3 container retains the original selector and bounded generation metadata, the old packet's
bounded envelope, and exact original vote identity/phase bindings. The backing
source must supply each original object and image at its original length/hash.
The reconstructed packet, generation inventory and pending vote must exactly
match their recorded bytes. A semantically similar capsule is insufficient.
The maximum encoded container is **1,466,800 bytes**, derived from the admitted
metadata, envelope and field maxima. Large payloads (up to the existing 8 MiB
FRAME bound) and application images remain in the separately charged source; the
container stores their bindings. It introduces no frozen record/wire kind or
resource-ceiling increase.

The backing source is bound to its original local owner, promise, BASIS and whole
packet. Reconstructing a context creates no remote force observation. Existing
capsule, round-coverage, selected-source and pending-vote validators remain
necessary, and callers must preserve their authenticated original observations.

## Integration still required

The [private persistence component](PHASE_2_PENDING_CONTEXT_FILES.md) now supplies
a qualified candidate/active transaction. The owner must integrate it, account
for every live/candidate byte inside the existing JOURNAL allowance, recover it
before verifying detached pending authority, and pin exact source identities.
Only then may existing floor-authorized storage retirement use it. Higher live
observations and the highest durable promise must never decrease.

Qualification must cover three-, four- and five-voter storage budgets. A
five-voter governing floor needs three copies; adding a retirement backup after
two generations and two original sources can exceed the seven-image limit. [Exact floor image borrowing](PHASE_2_RETIREMENT_IMAGES.md)
now qualifies that first retirement without an eighth image; it does not solve
arbitrary accumulated source pins.
Repeated observations and repeated source turnover need a bounded progress path,
including retention of the old certificate after a new ACCEPT replaces the old
pending file and until the exact logical entry is published. The component alone
does not solve those owner/lifetime obligations. The file component has separate
process-crash qualification; complete owner integration remains pending.

## Local qualification

The final unchanged-source targeted reactor run passes **47 Java tests**,
including nine context tests, existing source packet/floor/source-retirement
planning regressions and declaration/version boundaries. The tests reconstruct
actual ACCEPT, PROOF and certificate stages, retain a local certificate when the
new selected longest source contains only a proof, restore old selected-round
coverage after the original physical generation is unavailable to the codec, and
reject changed identities, metadata, lengths, hashes, source bytes and images.
A separate actual local ACCEPT/capture test exercises an 8 MiB opaque payload;
it does not claim typed application or quorum certification for that payload.

Returned metadata and vote bytes are defensive copies. Existing floor-copy force
checks remain mandatory: the extracted structural validator returns no copy
observation or retirement permission.

The independent replay and negative results, raw inventory, exact compiled source
hashes, build artifacts and logs are indexed in
[the local evidence record](phase2-evidence/pending-context.json). The retained
main case uses an actual small typed certified mutation. Its raw bytes do not
independently establish the separate maximal-payload Java test or filesystem force
semantics. Original conditional bootstrap remains explicit.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -pl :general-search-engine-replication -am \
  '-Dtest=V53PendingContextTest,V53SourcePacketTest,V53FloorTest,V53SourceRetirementPlanTest,V53DeclarationsTest,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
# Use the v53PendingContextEvidence path printed by the test.
python3 -m scripts.v53.pending_context_evidence <retained-pending-context-directory>
```

All work remains local. No protected CI, cloud execution or live owner-context
persistence/reclamation is claimed by this component.
