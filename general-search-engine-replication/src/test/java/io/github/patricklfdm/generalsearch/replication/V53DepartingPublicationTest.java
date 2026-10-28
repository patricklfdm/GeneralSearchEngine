package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Publication/reopen representation under conditional original observations;
 * actual distributed departure is tested separately by the native round. */
class V53DepartingPublicationTest {
    @TempDir Path temp;
    @Test void allFiveFinalGenerationsRetainTheirDepartedOwnerWithoutGrantingAVote()throws Exception {
        for(String profile:V53DepartingEndTest.PROFILES) {
            int size=Integer.parseInt(profile.substring(0,1));String kind=profile.split("-")[1];
            var f=new V53PublishedGenerationTest.Fixture(size,kind,6);var owner=V53DeclarationsTest.node(size);
            var source=f.decision.sources().stream().filter(s->s.owner.equals(owner)).findFirst().orElseThrow();
            var basis=source.basis;var fields=new TreeMap<>(basis.value());fields.keySet().retainAll(Set.of("root","view","ballot","basisId"));
            var promise=decode(encode("records","PROMISE",fields),"records","PROMISE");
            var plan=MembershipGenerationPlan.published(f.root(),owner,"b",promise,basis,f.selected,f.checkpoint,f.ends.acks(),f.ends.owned(),f.bridges,
                    MembershipSelectedSources.encodeSources(f.decision));
            plan.verifyOwned(f.f.capsule.source.root,owner,List.of(f.checkpoint.originalParent()));
            plan.verify(f.f.capsule.source.root,owner,f::verify,List.of(f.checkpoint.originalParent()));
            assertEquals("node-"+size,plan.manifest.value().get("node"));assertFalse(plan.verifiedMaterialization().context.voters().contains(owner.nodeId().value()));
            Path home=temp.resolve(profile);V53BallotAllocatorWorker.provision(home,f.f.capsule.source);
            Files.write(home.resolve("node.gsr"),encode("records","NODE",Map.of("root",f.root().manifestDigest(),"identity",MembershipPeerRetentionPlan.identity(owner))));
            Path original=home.resolve("sources").resolve((String)basis.value().get("basisId"));Files.createDirectories(original);
            Files.write(original.resolve("source.gscp"),source.capsule.packet.bytes());
            for(var row:f.f.capsule.source.images.entrySet())Files.write(original.resolve(row.getKey()+".image"),row.getValue());
            Path generation=home.resolve("generations/b");Files.createDirectories(generation);
            for(var row:plan.files.entrySet())Files.write(generation.resolve(row.getKey()),row.getValue());
            Files.write(home.resolve("selector.gsr"),plan.selector.bytes());
            var resources=new MembershipResources(512*MembershipResources.MIB);
            try(var current=new MembershipCurrentGeneration(home,f.root(),owner,resources,List.of(promise),List.of(basis),List.of(f.selected),f::verify,e->{},true)) {
                assertEquals(7L,current.capsule.context.cut.get("index"));assertFalse(current.adopted);
                assertFalse(current.capsule.context.voters().contains(owner.nodeId().value()));
            }assertEquals(0,resources.usage().leases());
        }
    }
    @Test void removedOwnerCannotBecomeASuccessorCheckpointOrAuthorizeMissingJointProof() {
        var f=new V53PublishedGenerationTest.Fixture(4,"REMOVE",6);var id=V53DeclarationsTest.node(4);
        var local=f.decision.sources().stream().filter(s->s.owner.equals(id)).findFirst().orElseThrow();
        var fields=new TreeMap<>(local.basis.value());fields.keySet().retainAll(Set.of("root","view","ballot","basisId"));
        var promise=decode(encode("records","PROMISE",fields),"records","PROMISE");
        var invalid=V53CheckpointPlanTest.endorsements(f.checkpoint,List.of("node-1","node-4"));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.published(f.root(),id,"b",promise,local.basis,f.selected,
                f.checkpoint,invalid.acks(),invalid.owned(),List.of()));
        var incomplete=new HashSet<>(f.observations);incomplete.removeAll(V53CheckpointPlanTest.votes(f.f.capsule.source,f.f.capsule.source.steps.get(6)));
        var plan=MembershipGenerationPlan.published(f.root(),id,"b",promise,local.basis,f.selected,f.checkpoint,f.ends.acks(),f.ends.owned(),List.of());
        assertThrows(IllegalArgumentException.class,()->plan.verify(f.f.capsule.source.root,id,(root,packet,images)->MembershipCapsule.verify(root,packet,images,incomplete),List.of()));
    }
    @Test void departedPublicationCannotBeRelabelledAsUnselectedOrLaterStableOwnership() {
        var f=new V53PublishedGenerationTest.Fixture(4,"REMOVE",6);var id=V53DeclarationsTest.node(4);var capsule=f.capsule();
        var altered=new TreeMap<>(f.selected.value());altered.put("sources",list(altered.get("sources")).stream().filter(v->!object(v).get("voter").equals("node-4")).toList());
        assertEquals("departing publication original selected owner",assertThrows(IllegalArgumentException.class,
                ()->MembershipSelectionCoverage.departingOwner(capsule,decode(encode("records","SELECTED",altered),"records","SELECTED"),id)).getMessage());
        var stable=new V53CapsuleFixture(4,"REMOVE",8).verify();
        assertEquals("departing publication must end at FINAL",assertThrows(IllegalArgumentException.class,
                ()->MembershipSelectionCoverage.departingOwner(stable,f.selected,id)).getMessage());
    }
    @Test void expectedApplicationReplyDistinguishesDepartureFromEligibleAndForeignOwners() {
        for(String profile:V53DepartingEndTest.PROFILES) {
            var plan=V53DepartingEndTest.plan(profile);var local=V53DepartingEndTest.local(profile);String selected=V53ContextFixture.H;
            var departure=MembershipSlotDelivery.applicationPayload(plan,local,selected);
            assertNull(departure.get("acknowledgement"));assertEquals(plan.originalCertificate().digest(),departure.get("certificate"));
            assertEquals(plan.statement.digest(),departure.get("statement"));assertEquals(selected,departure.get("selection"));
            var survivor=MembershipSlotDelivery.applicationPayload(plan,V53DeclarationsTest.node(1),selected);
            assertEquals(V53CheckpointPlanTest.endorsements(plan,List.of("node-1")).acks().getFirst().digest(),survivor.get("acknowledgement"));
            var foreign=new MembershipIdentity(local.nodeId(),new UUID(99,99),local.endpoint());
            assertThrows(IllegalArgumentException.class,()->MembershipSlotDelivery.applicationPayload(plan,foreign,selected));
            assertThrows(IllegalArgumentException.class,()->MembershipSlotDelivery.applicationPayload(plan,V53DeclarationsTest.node(9),selected));
        }
        var f=new V53CapsuleFixture(4,"REMOVE",7);var stable=V53CheckpointPlanTest.plan(f.verify(),f.source,7);
        assertThrows(IllegalArgumentException.class,()->MembershipSlotDelivery.applicationPayload(stable,V53DeclarationsTest.node(4),V53ContextFixture.H));
    }
}
