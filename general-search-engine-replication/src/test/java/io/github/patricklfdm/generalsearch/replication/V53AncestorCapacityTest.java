package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Bounds of the storage component; old checkpoint quorum observations are conditional fixtures. */
class V53AncestorCapacityTest {
    @TempDir Path temp;
    record Fixture(MembershipCheckpointPlan plan,MembershipCheckpointPlan unowned,List<MembershipCapsule.Anchor> lower,byte[] ancestry) {}
    static Fixture fixture() {
        var source=new V53ContextFixture(3,"ADD");var before=V53CheckpointPlanTest.initial(source);var lower=new ArrayList<MembershipCapsule.Anchor>();
        for(int i=0;i<8;i++){source.commit("BARRIER",null,()->{});before=V53CheckpointPlanTest.finish(V53CheckpointPlanTest.plan(before,source,i));if(i<6)lower.add(before.terminal());}
        var objects=new TreeMap<String,byte[]>();for(String h:before.packet.objectNames())objects.put(h,before.packet.objectBytes(h));
        var bridges=new ArrayList<MembershipSelection.Bridge>();var observations=new HashSet<Owned>();
        for(var anchor:lower) {
            var statement=decode(encode("records","CHECKPOINT",Map.of("root",before.context.root,"scope","RANGE","start",anchor.cut(),"end",before.context.cut,
                    "catalogBefore",anchor.catalog(),"catalogAfter",before.terminal().catalog(),"applicationBefore",anchor.application(),"applicationAfter",before.terminal().application())),"records","CHECKPOINT");
            objects.put(statement.digest(),statement.bytes());var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
            for(int n:List.of(1,2,3)) {
                var id=V53DeclarationsTest.node(n);var ack=decode(encode("records","CHECKPOINT_ACK",Map.of("root",before.context.root,"cut",before.context.cut,"statement",statement.digest(),
                        "voter",id.nodeId().value(),"incarnation",id.storageId().toString())),"records","CHECKPOINT_ACK");
                acks.add(ack);objects.put(ack.digest(),ack.bytes());owned.add(new Owned(id.nodeId().value(),id.storageId(),ack.digest(),cutDigest(before.context.cut)));
            }
            observations.addAll(owned);bridges.add(new MembershipSelection.Bridge(statement,acks,owned));
        }
        var cap=new TreeMap<>(before.packet.capsule().value());cap.put("inventory",hash(MembershipSourcePacket.index(objects,before.packet.images())));
        var packet=MembershipSourcePacket.decode(MembershipSourcePacket.encode(decode(encode("records","CAPSULE",cap),"records","CAPSULE"),objects,before.packet.images()));
        var unowned=before.verifyExtension(packet,source.images,Set.of());before=before.verifyExtension(packet,source.images,observations);
        source.commit("BARRIER",null,()->{});
        return new Fixture(V53CheckpointPlanTest.plan(before,source,8),V53CheckpointPlanTest.plan(unowned,source,8),List.copyOf(lower),MembershipGenerationPlan.ancestry(bridges));
    }
    @Test void sixGroupsFitOneImageAndBoundedJournalButASeventhRefusesBeforeWriting()throws Exception {
        var f=fixture();var plan=f.plan.renewAncestors(f.lower.subList(0,5),f.ancestry);assertEquals(5,plan.additionalParents().size());
        var refused=assertThrows(IllegalArgumentException.class,()->f.plan.renewAncestors(f.lower,f.ancestry));assertEquals("checkpoint renewed ancestry count",refused.getMessage());
        var limits=new MembershipResources(512*MembershipResources.MIB);Path end=temp.resolve("end");
        var selector=decode(encode("records","SELECTOR",Map.of("root",plan.catalog.value().get("root"),"node","node-1","generation","a","digest",V53ContextFixture.H)),"records","SELECTOR");
        try(var journal=limits.reserve(MembershipResources.Unit.JOURNAL,"owner",MembershipResources.Unit.JOURNAL.bytes);
                var store=new MembershipAppliedEndFiles(end,limits,MembershipAppliedEndFiles.METADATA)) {
            var events=new ArrayList<String>();var result=store.force(plan,selector,V53DeclarationsTest.node(1),()->{},events::add);
            assertEquals(5,result.ancestors().size());assertEquals(1,limits.usage().counts().get(MembershipResources.Unit.APPLICATION));
            try(var paths=Files.list(end)){assertEquals(19,paths.count());}
            assertTrue(Files.size(end.resolve("plan.json"))<=4096);
            assertTrue(events.indexOf("APPLY_END_FORCED")<events.indexOf("APPLY_ANCESTOR_0_ACK_CREATED"));
            for(int i=1;i<5;i++)assertTrue(events.indexOf("APPLY_ANCESTOR_"+(i-1)+"_ACK_FORCED")<events.indexOf("APPLY_ANCESTOR_"+i+"_ACK_CREATED"));
            store.completed(plan,selector,V53DeclarationsTest.node(1),result);
        }
        assertEquals(0,limits.usage().leases());
    }
    @Test void inventoryExtrasMissingHistoryAndAlteredOriginalStateNeverAuthorizeRenewal() {
        var f=fixture();var one=f.lower.subList(0,1);
        assertThrows(IllegalArgumentException.class,()->f.unowned.renewAncestors(one,f.ancestry));
        assertThrows(IllegalArgumentException.class,()->f.plan.renewAncestors(one,new byte[0]));
        var lower=one.getFirst();var altered=new MembershipCapsule.Anchor(lower.cut(),V53ContextFixture.H,lower.application());
        assertThrows(IllegalArgumentException.class,()->f.plan.renewAncestors(List.of(altered),f.ancestry));
        var requested=new ArrayList<>(one);requested.add(lower);assertEquals(1,f.plan.renewAncestors(requested,f.ancestry).additionalParents().size());
        requested.add(altered);assertThrows(IllegalArgumentException.class,()->f.plan.renewAncestors(requested,f.ancestry));
    }
}
