package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Pure-state tests over explicit conditional history, plus actual native bootstrap/publication. */
class V53PeerRetentionPlanTest {
    @TempDir Path temp;
    static MembershipCapsule capsule(int size,int cut){return new V53CapsuleFixture(size,"REPLACE",cut).verify();}
    static List<Long> cuts(List<MembershipCapsule.Anchor> values){return values.stream().map(a->number(a.cut().get("index"))).toList();}
    MembershipFloor.Copy copy(int size,int cut,int voter)throws Exception {
        var f=new V53CurrentGenerationFixture(size,cut,false);Path root=temp.resolve("copy-"+UUID.randomUUID());
        V53FloorWorker.provision(root,size,cut,voter);var resources=new MembershipResources(512*MembershipResources.MIB);
        try(var owner=MembershipGrantJournal.openFloors(root,f.root(),V53DeclarationsTest.node(voter),resources,f::verify,e->{})) {
            return owner.floorCopyCurrent();
        }finally{assertEquals(0,resources.usage().leases());}
    }
    @Test void genesisAndDispatchPreserveOldPossibilityUntilRealCopyAdvances()throws Exception {
        for(int size:List.of(3,4,5)) {
            var zero=capsule(size,0);var one=capsule(size,1);var peer=V53DeclarationsTest.node(2);
            var initial=MembershipPeerRetentionPlan.genesis(zero);var pending=initial.dispatch(one,new byte[0],peer);
            assertEquals(List.of(0L),cuts(initial.possible(peer)));assertEquals(List.of(0L,1L),cuts(pending.possible(peer)));
            assertEquals(List.of(0L,1L),cuts(pending.observe(one,new byte[0],copy(size,0,2)).possible(peer)));
            var confirmed=pending.observe(one,new byte[0],copy(size,1,2));assertEquals(List.of(1L),cuts(confirmed.possible(peer)));
            assertEquals(List.of(0L,1L),cuts(pending.possible(peer)));
            assertThrows(IllegalArgumentException.class,()->pending.dispatch(one,new byte[0],peer));
            assertThrows(IllegalArgumentException.class,()->confirmed.dispatch(one,new byte[0],peer));
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionPlan.genesis(one));
            assertThrows(UnsupportedOperationException.class,()->pending.possible(peer).clear());
            assertThrows(UnsupportedOperationException.class,()->pending.possible(peer).getFirst().cut().put("index",5L));
        }
    }
    @Test void staleClaimsCannotEraseAmbiguousEndpointsAndMergeRequiresActualProgress()throws Exception {
        var zero=capsule(3,0);var one=capsule(3,1);var peer=V53DeclarationsTest.node(2);
        var initial=MembershipPeerRetentionPlan.genesis(zero);var pending=initial.dispatch(one,new byte[0],peer);
        var newer=pending.observe(one,new byte[0],copy(3,1,2));
        for(var order:List.of(List.of(pending,newer),List.of(newer,pending))) {
            var merged=MembershipPeerRetentionPlan.merge(one,new byte[0],order,List.of());assertEquals(List.of(0L,1L),cuts(merged.possible(peer)));
            var observed=MembershipPeerRetentionPlan.merge(one,new byte[0],order,List.of(copy(3,1,2)));assertEquals(List.of(1L),cuts(observed.possible(peer)));
            assertEquals(List.of(0L,1L),cuts(MembershipPeerRetentionPlan.merge(one,new byte[0],order,List.of(copy(3,0,2))).possible(peer)));
        }
        var observed=copy(3,1,2);
        assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionPlan.merge(one,new byte[0],List.of(initial),List.of(observed,observed)));
        assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionPlan.merge(one,new byte[0],List.of(),List.of()));
    }
    @Test void missingExactAncestryAndForeignIdentityOrRootAreRejected()throws Exception {
        var zero=capsule(3,0);var one=capsule(3,1);var five=capsule(3,5);var peer=V53DeclarationsTest.node(2);
        var pin=MembershipPeerRetentionPlan.genesis(zero).dispatch(one,new byte[0],peer);
        assertThrows(IllegalArgumentException.class,()->pin.required(five,new byte[0]));
        assertThrows(IllegalArgumentException.class,()->pin.dispatch(one,new byte[0],V53DeclarationsTest.node(6)));
        assertThrows(IllegalArgumentException.class,()->pin.required(capsule(4,1),new byte[0]));
        var foreign=copy(4,1,2);assertThrows(IllegalArgumentException.class,()->pin.observe(one,new byte[0],foreign));
        var changed=new MembershipIdentity(peer.nodeId(),UUID.randomUUID(),peer.endpoint());
        assertThrows(IllegalArgumentException.class,()->pin.possible(changed));
    }
    @Test void learnerRequiresActualJointCopyAndRemovalWaitsForFinal()throws Exception {
        for(int size:List.of(3,4,5)) {
            var initial=MembershipPeerRetentionPlan.genesis(capsule(size,0));var joint=capsule(size,6);var stable=capsule(size,7);
            var learner=copy(size,6,6);var retiring=V53DeclarationsTest.node(size);
            assertThrows(IllegalArgumentException.class,()->initial.reconcile(joint,new byte[0],List.of()));
            var entered=initial.reconcile(joint,new byte[0],List.of(learner));
            assertEquals(List.of(0L),cuts(entered.possible(retiring)));assertEquals(List.of(6L),cuts(entered.possible(learner.owner)));
            assertThrows(IllegalArgumentException.class,()->entered.reconcile(capsule(size,0),new byte[0],List.of()));
            var completed=entered.reconcile(stable,new byte[0],List.of());
            assertThrows(IllegalArgumentException.class,()->completed.possible(retiring));
            assertEquals(List.of(6L),cuts(completed.possible(learner.owner)));
            assertThrows(IllegalArgumentException.class,()->completed.reconcile(joint,new byte[0],List.of()));
            assertThrows(IllegalArgumentException.class,()->entered.reconcile(joint,new byte[0],List.of(learner)));
        }
    }
    @Test void removalAndAdditionReconcileOnlyAuthenticatedConfigurations()throws Exception {
        for(Object[] profile:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"}}) {
            int size=(int)profile[0];String kind=(String)profile[1];
            var zero=new V53CapsuleFixture(size,kind,0).verify();var joint=new V53CapsuleFixture(size,kind,6).verify();var next=new V53CapsuleFixture(size,kind,7).verify();
            var original=MembershipPeerRetentionPlan.genesis(zero);
            List<MembershipFloor.Copy> joining=List.of();
            if(kind.equals("ADD")) {
                var fixture=new V53CurrentGenerationFixture(size,new V53CapsuleFixture(size,kind,6));
                Path path=temp.resolve("learner-"+size);fixture.provision(path);String node="node-6";
                Files.write(path.resolve("node.gsr"),encode("records","NODE",Map.of("identity",V53ContextFixture.member(6),"root",fixture.root().manifestDigest())));
                Files.write(path.resolve(MembershipBallotAllocator.CURRENT),encode("records","ALLOCATOR",Map.of("counter",0L,"node",node,"root",fixture.root().manifestDigest())));
                var manifest=new TreeMap<>(decode(Files.readAllBytes(path.resolve("generations/a/generation.gsr")),"records","GENERATION").value());manifest.put("node",node);
                byte[] bytes=encode("records","GENERATION",manifest);Files.write(path.resolve("generations/a/generation.gsr"),bytes);
                Files.write(path.resolve("selector.gsr"),encode("records","SELECTOR",Map.of("root",fixture.root().manifestDigest(),"node",node,"generation","a","digest",hash(bytes))));
                var resources=new MembershipResources(512*MembershipResources.MIB);
                try(var owner=MembershipGrantJournal.openFloors(path,fixture.root(),V53DeclarationsTest.node(6),resources,fixture::verify,e->{})) {joining=List.of(owner.floorCopyCurrent());}
                assertEquals(0,resources.usage().leases());
            }
            var entered=original.reconcile(joint,new byte[0],joining);
            assertEquals(List.of(0L),cuts(entered.possible(V53DeclarationsTest.node(size))));
            var completed=entered.reconcile(next,new byte[0],List.of());
            if(kind.equals("REMOVE"))assertThrows(IllegalArgumentException.class,()->completed.possible(V53DeclarationsTest.node(size)));
            else assertEquals(List.of(6L),cuts(completed.possible(V53DeclarationsTest.node(6))));
        }
    }
    @Test void actualNativePublicationKeepsARealEarlierOwnerCopy()throws Exception {
        Path raw=Files.createDirectory(temp.resolve("native-evidence"));
        var f=new V53BootstrapPublicationTest.Fixture(temp,raw,3,false);f.ownedHistory=true;
        try {
            var peer=f.request.targets().get(2);MembershipFloor.Copy old;
            try(var owner=f.open(peer,"retention-genesis")){old=owner.floorCopyCurrent();}
            var initial=MembershipPeerRetentionPlan.genesis(old.capsule);
            f.campaign(1);f.publish(1,false);
            MembershipFloor.Copy tip;
            try(var owner=f.open(f.request.targets().getFirst(),"retention-tip")){tip=owner.floorCopyCurrent();}
            var plan=initial.dispatch(tip.capsule,new byte[0],peer.identity());
            assertEquals(List.of(0L,1L),cuts(plan.observe(tip.capsule,new byte[0],old).possible(peer.identity())));
            MembershipFloor.Copy progress;
            try(var owner=f.open(peer,"retention-observed")){progress=owner.floorCopyCurrent();}
            var confirmed=plan.observe(tip.capsule,new byte[0],progress);
            assertEquals(List.of(1L),cuts(confirmed.possible(peer.identity())));
            f.publish(2,true);MembershipFloor.Copy second;
            try(var owner=f.open(peer,"retention-next-copy")){second=owner.floorCopyCurrent();}
            byte[] ancestry=second.fileBytes("ancestry.gsr");var pending=confirmed.dispatch(second.capsule,ancestry,peer.identity());
            assertEquals(List.of(1L,2L),cuts(pending.possible(peer.identity())));
            // Merging two unresolved histories cannot silently choose a latest cut.
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionPlan.merge(second.capsule,ancestry,List.of(plan,pending),List.of()));
            assertEquals(List.of(1L,2L),cuts(MembershipPeerRetentionPlan.merge(second.capsule,ancestry,List.of(plan,pending),List.of(progress)).possible(peer.identity())));
            assertEquals(List.of(2L),cuts(MembershipPeerRetentionPlan.merge(second.capsule,ancestry,List.of(plan,pending),List.of(second)).possible(peer.identity())));
            assertThrows(IllegalArgumentException.class,()->pending.required(second.capsule,new byte[0]));
        }finally{assertEquals(0,f.resources.usage().leases());}
    }
}
