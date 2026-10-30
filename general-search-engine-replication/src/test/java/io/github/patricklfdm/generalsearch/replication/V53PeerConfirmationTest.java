package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53PeerRetentionPlanTest.cuts;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53PeerConfirmationTest {
    @TempDir Path temp;
    @Test void completeCopyConfirmationDischargesStaleSelectedEndpoints()throws Exception {
        var helper=new V53SelectedRetentionTest();helper.temp=temp;var f=helper.fixture("confirmed-merge");
        var one=f.request.targets().getFirst();var two=f.request.targets().get(1);var three=f.request.targets().get(2);
        f.campaign(1);f.publish(1,false);
        try(var owner=f.open(one,"old-dispatch")){owner.retainPeerDispatch(three.identity());}
        f.campaign(2);f.publish(2,true);
        f.snapshot("before-confirmation");
        MembershipFloor.Copy actual;
        try(var owner=f.open(three,"actual-original-copy")){actual=owner.floorCopyCurrent();}
        try(var owner=f.open(two,"confirmed-copy")) {
            assertEquals(List.of(0L,1L),cuts(owner.peerRetentionState().plan().possible(three.identity())));
            var before=owner.peerRetentionState();var confirmed=owner.retainPeerObservation(actual);
            assertEquals(List.of(2L),cuts(owner.peerRetentionState().plan().possible(three.identity())));
            assertEquals(List.of(0L,1L,2L),cuts(confirmed.plan().required(actual.capsule,actual.fileBytes("ancestry.gsr"))));
            var row=object(list(object(parse(confirmed.plan().bytes(),32768)).get("peers")).get(2));
            assertArrayEquals(actual.generation.bytes(),Base64.getDecoder().decode((String)row.get("confirmation")));
            assertEquals(List.of(0L,1L),list(row.get("renewals")).stream().map(MembershipFormat::object)
                    .map(a->number(object(a.get("cut")).get("index"))).toList());
            assertEquals(confirmed.digest(),owner.retainPeerObservation(actual).digest());
            var decoded=MembershipPeerRetentionPlan.decode(confirmed.plan().bytes());
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionPlan.mergeRecorded(actual.capsule.context.root,
                    actual.capsule.context.view,List.of(before.plan(),decoded)));
        }
        f.snapshot("after-confirmation");
        // A real complete copy was observed, but the other owner's frozen
        // ledger still has [0,1]. Merely choosing its larger revision is unsafe.
        try(var owner=f.open(one,"still-stale")) {
            assertEquals(List.of(0L,1L),cuts(owner.peerRetentionState().plan().possible(three.identity())));
        }
        f.campaign(3);
        for(var member:f.request.targets())try(var owner=f.open(member,"merged-confirmed-copy")) {
            assertEquals(List.of(2L),cuts(owner.peerRetentionState().plan().possible(three.identity())));
        }
        f.publish(3,false);
        for(var member:f.request.targets())try(var owner=f.open(member,"reopened-confirmed-copy")) {
            assertEquals(List.of(2L),cuts(owner.peerRetentionState().plan().possible(three.identity())));
        }
        Files.write(f.raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));
        assertEquals(0,f.resources.usage().leases());
    }

    MembershipPeerRetentionPlan confirmed()throws Exception {
        var helper=new V53PeerRetentionPlanTest();helper.temp=temp;
        var zero=V53PeerRetentionPlanTest.capsule(3,0);var one=V53PeerRetentionPlanTest.capsule(3,1);
        return MembershipPeerRetentionPlan.genesis(zero).dispatch(one,new byte[0],V53DeclarationsTest.node(2))
                .observe(one,new byte[0],helper.copy(3,1,2));
    }
    @Test void decodedConfirmationCannotDischargeWithoutOriginalProvenance()throws Exception {
        var plan=confirmed();var decoded=MembershipPeerRetentionPlan.decode(plan.bytes());var one=V53PeerRetentionPlanTest.capsule(3,1);
        var conservative=MembershipPeerRetentionPlan.mergeRecorded(one.context.root,one.context.view,List.of(decoded));
        assertEquals(List.of(0L,1L),cuts(conservative.possible(V53DeclarationsTest.node(2))));
        assertFalse(object(list(object(parse(conservative.bytes(),32768)).get("peers")).get(1)).containsKey("confirmation"));
    }
    @Test void originalManifestBindingsAndCanonicalEncodingAreRequired()throws Exception {
        byte[] original=confirmed().bytes();
        for(String mutation:List.of("root","node","catalog","base64","unknown","renewal-empty","renewal-duplicate","renewal-future","renewal-capacity")) {
            var plan=object(V53ContextFixture.mutable(parse(original,32768)));var row=object(list(plan.get("peers")).get(1));
            String encoded=(String)row.get("confirmation");
            if(Set.of("root","node","catalog").contains(mutation)) {
                var generation=object(V53ContextFixture.mutable(decode(Base64.getDecoder().decode(encoded),"records","GENERATION").value()));
                generation.put(mutation,mutation.equals("node")?"node-3":"f".repeat(64));
                row.put("confirmation",Base64.getEncoder().encodeToString(encode("records","GENERATION",generation)));
            }else if(mutation.equals("base64"))row.put("confirmation",encoded+"\n");
            else if(mutation.equals("unknown"))row.put("trusted",true);
            else if(mutation.equals("renewal-empty"))row.put("renewals",List.of());
            else if(mutation.equals("renewal-future"))row.put("renewals",row.get("possible"));
            else {Object point=list(row.get("renewals")).getFirst();row.put("renewals",Collections.nCopies(mutation.equals("renewal-capacity")?3:2,point));}
            byte[] bytes=canonical(plan,32768);
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionPlan.decode(bytes),mutation);
        }
        assertArrayEquals(original,MembershipPeerRetentionPlan.decode(original).bytes());
    }
    @Test void conflictsInDischargedHistoryStillRefuseAndGenesisIsIdempotent()throws Exception {
        var helper=new V53PeerRetentionPlanTest();helper.temp=temp;
        var zero=V53PeerRetentionPlanTest.capsule(3,0);var one=V53PeerRetentionPlanTest.capsule(3,1);
        var initial=MembershipPeerRetentionPlan.genesis(zero);
        assertArrayEquals(initial.bytes(),initial.observe(zero,new byte[0],helper.copy(3,0,2)).bytes());
        var confirmed=confirmed();var changed=object(V53ContextFixture.mutable(parse(confirmed.bytes(),32768)));
        object(list(object(list(changed.get("peers")).get(1)).get("renewals")).getFirst()).put("catalog","f".repeat(64));
        var conflicting=MembershipPeerRetentionPlan.decode(canonical(changed,32768));
        assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionPlan.mergeRecorded(one.context.root,one.context.view,List.of(confirmed,conflicting)));
        var peer=V53DeclarationsTest.node(2);var identity=new MembershipIdentity(peer.nodeId(),UUID.randomUUID(),peer.endpoint());
        changed=object(V53ContextFixture.mutable(parse(confirmed.bytes(),32768)));object(list(changed.get("peers")).get(1)).put("identity",MembershipPeerRetentionPlan.identity(identity));
        var foreign=MembershipPeerRetentionPlan.decode(canonical(changed,32768));
        assertThrows(IllegalArgumentException.class,()->foreign.required(one,new byte[0]));
    }
}
