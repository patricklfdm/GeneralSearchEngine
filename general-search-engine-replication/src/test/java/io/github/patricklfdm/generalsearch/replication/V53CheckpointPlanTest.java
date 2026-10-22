package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;

/** Conditional historical/checkpoint observations test construction; no test ACK implies an actual force. */
class V53CheckpointPlanTest {
    @org.junit.jupiter.api.io.TempDir java.nio.file.Path temp;
    static MembershipCapsule initial(V53ContextFixture f) {
        var catalog=f.catalog();var objects=new TreeMap<String,byte[]>();
        for(String h:List.of(f.root.digest(),(String)f.root.value().get("genesis"),catalog.digest()))objects.put(h,f.inventory.get(h));
        var images=new TreeMap<String,Long>();f.images.forEach((h,b)->images.put(h,(long)b.length));
        var cap=f.record("CAPSULE",map("root",f.rootHash,"initial",f.root.value().get("genesis"),"cut",f.state.get("cut"),
                "catalog",catalog.digest(),"application",f.state.get("application"),"inventory",hash(MembershipSourcePacket.index(objects,images)),"items",List.of()));
        return MembershipCapsule.verify(f.root,MembershipSourcePacket.decode(MembershipSourcePacket.encode(cap,objects,images)),f.images,Set.of());
    }
    static MembershipSourcePacket certified(MembershipCapsule before,V53ContextFixture source,Map<String,Object> step) {
        var objects=new TreeMap<String,byte[]>();for(String h:before.packet.objectNames())objects.put(h,before.packet.objectBytes(h));
        for(String field:List.of("entry","accept","proof","certificate")){String h=(String)step.get(field);objects.put(h,source.inventory.get(h));}
        var entry=decode(source.inventory.get(step.get("entry")),"records","ENTRY");String payload=(String)entry.value().get("payload");objects.put(payload,source.inventory.get(payload));
        var cap=new TreeMap<>(before.packet.capsule().value());cap.put("inventory",hash(MembershipSourcePacket.index(objects,before.packet.images())));
        return MembershipSourcePacket.decode(MembershipSourcePacket.encode(decode(encode("records","CAPSULE",cap),"records","CAPSULE"),objects,before.packet.images()));
    }
    static Set<Owned> votes(V53ContextFixture f,Map<String,Object> step) {
        var result=new HashSet<Owned>();for(var o:f.owned)if(o.record().equals(step.get("accept")) || o.record().equals(step.get("proof")))result.add(o);return result;
    }
    static MembershipCheckpointPlan plan(MembershipCapsule before,V53ContextFixture f,int at) {
        var step=f.steps.get(at);var catalog=decode(f.inventory.get(step.get("catalogAfter")),"records","CATALOG");
        return MembershipCheckpointPlan.project(before,certified(before,f,step),decode(f.inventory.get(step.get("certificate")),"records","CERTIFICATE"),
                f.images,votes(f,step),new MembershipApplicationReplay.Result(at+1,number(catalog.value().get("applicationSequence")),f.images.get(catalog.value().get("application"))));
    }
    record Endorsements(List<Decoded> acks,Set<Owned> owned) {}
    static Endorsements endorsements(MembershipCheckpointPlan plan,Collection<String> voters) {
        var cut=object(plan.catalog.value().get("cut"));var result=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
        for(String voter:voters) {
            var id=V53DeclarationsTest.node(Integer.parseInt(voter.substring(5)));
            var ack=decode(encode("records","CHECKPOINT_ACK",Map.of("root",plan.catalog.value().get("root"),"cut",cut,"statement",plan.statement.digest(),
                    "voter",voter,"incarnation",id.storageId().toString())),"records","CHECKPOINT_ACK");
            result.add(ack);owned.add(new Owned(voter,id.storageId(),ack.digest(),cutDigest(cut)));
        }
        return new Endorsements(List.copyOf(result),Set.copyOf(owned));
    }
    static Endorsements endorsements(MembershipCheckpointPlan plan) {
        var view=object(object(plan.catalog.value().get("cut")).get("view"));var voters=new TreeSet<>(nodes(view,"old"));voters.addAll(nodes(view,"new"));return endorsements(plan,voters);
    }
    static MembershipCapsule finish(MembershipCheckpointPlan p) {var e=endorsements(p);return p.complete(e.acks,e.owned);}

    @Test void buildsAllSixtyThreeTransitionsExactlyLikeIndependentCompactionFixtures() {
        for(Object[] p:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},{3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}}) {
            int size=(int)p[0];String change=(String)p[1];var fixture=new V53CapsuleFixture(size,change,0);var current=fixture.verify();
            for(int at=0;at<9;at++) {
                byte[] original=current.packet.bytes();var next=plan(current,fixture.source,at);current=finish(next);
                var expected=new V53CapsuleFixture(size,change,at+1).packet();assertArrayEquals(expected.bytes(),current.packet.bytes(),size+"/"+change+"/"+at);
                assertArrayEquals(original,at==0?fixture.packet().bytes():new V53CapsuleFixture(size,change,at).packet().bytes());
            }
        }
    }
    @Test void newRangeNeedsNewExactEndorsementsAndCannotReuseOldOrPhasedReceipts() {
        var fixture=new V53CapsuleFixture(3,"ADD",1);var before=fixture.verify();var p=plan(before,fixture.source,1);var e=endorsements(p);
        assertThrows(IllegalArgumentException.class,()->p.complete(e.acks,Set.of()));
        assertThrows(IllegalArgumentException.class,()->p.complete(e.acks,votes(fixture.source,fixture.source.steps.get(1))));
        var item=object(list(before.packet.capsule().value().get("items")).getFirst());
        var old=list(item.get("endorsements")).stream().map(h->decode(before.packet.objectBytes((String)h),"records","CHECKPOINT_ACK")).toList();
        assertThrows(IllegalArgumentException.class,()->p.complete(old,e.owned));
        var wrong=new HashSet<Owned>();for(var o:e.owned)wrong.add(new Owned(o.voter(),o.storage(),o.record(),cutDigest(before.context.cut)));
        assertThrows(IllegalArgumentException.class,()->p.complete(e.acks,wrong));
        var next=finish(p);assertEquals(1,list(next.packet.capsule().value().get("items")).size());assertFalse(next.containsCut(before.context.cut));
        // Replacing a range does not fabricate a bridge for a retained original source.
        assertThrows(IllegalArgumentException.class,()->next.verifyAncestry(new byte[0],List.of(before.terminal())));
    }
    @Test void membershipEndorsementsUseBothSuccessorMajoritiesAndFinalNewVoters() {
        var fixture=new V53CapsuleFixture(5,"REPLACE",5);var p=plan(fixture.verify(),fixture.source,5);
        for(var nodes:List.of(List.of("node-1","node-2","node-5"),List.of("node-1","node-2","node-6"))) {
            var e=endorsements(p,nodes);assertThrows(IllegalArgumentException.class,()->p.complete(e.acks,e.owned));
        }
        var overlap=endorsements(p,List.of("node-1","node-2","node-3"));var joint=p.complete(overlap.acks,overlap.owned);
        var finalPlan=plan(joint,fixture.source,6);var removed=endorsements(finalPlan,List.of("node-1","node-2","node-5"));
        assertThrows(IllegalArgumentException.class,()->finalPlan.complete(removed.acks,removed.owned));
        var stable=finish(finalPlan);assertNull(stable.context.view.get("operation"));
    }
    @Test void staleChangedDuplicateAndForeignCheckpointAcksReject() {
        var fixture=new V53CapsuleFixture(3,"ADD",0);var p=plan(fixture.verify(),fixture.source,0);var e=endorsements(p);
        var duplicate=new ArrayList<>(e.acks);duplicate.set(1,duplicate.getFirst());assertThrows(IllegalArgumentException.class,()->p.complete(duplicate,e.owned));
        var reversed=new ArrayList<>(e.acks);Collections.reverse(reversed);assertThrows(IllegalArgumentException.class,()->p.complete(reversed,e.owned));
        for(String key:List.of("root","statement","incarnation")) {
            var value=new TreeMap<>(e.acks.getFirst().value());value.put(key,key.equals("incarnation")?new UUID(99,99).toString():H);
            var changed=new ArrayList<>(e.acks);changed.set(0,decode(encode("records","CHECKPOINT_ACK",value),"records","CHECKPOINT_ACK"));
            assertThrows(IllegalArgumentException.class,()->p.complete(changed,e.owned));
        }
        assertThrows(IllegalArgumentException.class,()->p.complete(List.of(),Set.of()));assertNotNull(finish(p));
    }
    @Test void certificateRequiresExactOwnedPhasesAndCannotChangeTheBase() {
        var f=new V53CapsuleFixture(3,"ADD",0);var before=f.verify();var step=f.source.steps.getFirst();var packet=certified(before,f.source,step);
        var cert=decode(f.source.inventory.get(step.get("certificate")),"records","CERTIFICATE");var app=new MembershipApplicationReplay.Result(1,0,f.source.images.values().iterator().next());
        assertThrows(IllegalArgumentException.class,()->MembershipCheckpointPlan.project(before,packet,cert,f.source.images,Set.of(),app));
        var incomplete=votes(f.source,step);incomplete.removeIf(o->o.record().equals(step.get("proof")));
        assertThrows(IllegalArgumentException.class,()->MembershipCheckpointPlan.project(before,packet,cert,f.source.images,incomplete,app));
        var other=new V53CapsuleFixture(3,"ADD",1).verify();
        assertThrows(IllegalArgumentException.class,()->MembershipCheckpointPlan.project(other,packet,cert,f.source.images,votes(f.source,step),app));
    }
    @Test void stableProgressReplacesRangeInventoryWithoutRetainingEveryEntryOrCatalog() {
        var f=new V53ContextFixture(3,"ADD");var before=initial(f);int count=0;long largest=0;
        for(int i=0;i<100;i++) {
            f.commit("BARRIER",null,()->{});var prior=before;var p=plan(before,f,i);before=finish(p);
            assertEquals(1,list(before.packet.capsule().value().get("items")).size());
            if(i==0)count=before.packet.objectNames().size();assertEquals(count,before.packet.objectNames().size());
            assertFalse(before.packet.objectNames().contains(f.steps.get(i).get("certificate")));
            assertFalse(before.packet.objectNames().contains(f.steps.get(i).get("entry")));
            assertFalse(before.packet.objectNames().contains(prior.packet.capsule().value().get("catalog")));
            largest=Math.max(largest,before.packet.bytes().length);
        }
        assertTrue(largest<16*1024);assertEquals(100L,before.context.cut.get("index"));
    }
    @Test void completeDataProjectionReusesActualCoreSemanticsBeforeAnyCheckpointAck()throws Exception {
        var app=new V53ApplicationReplayTest();app.temp=temp;byte[] original=app.initial(41);
        var f=new V53ContextFixture(3,"ADD",original,V53ApplicationImageTest.HISTORY,41);var before=initial(f);
        byte[] payload;try(var encoder=app.encoder()){payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(3,"new"))));}
        var expected=app.replay(original,41,0,List.of(new MembershipApplicationReplay.Step(1,"DATA",payload)),"expected");
        f.commit("DATA",payload,()->{f.state.put("application",hash(expected.image()));f.state.put("applicationSequence",42L);f.state.put("lastDataIndex",1L);f.images.put(hash(expected.image()),expected.image());});
        var step=f.steps.getFirst();var packet=certified(before,f,step);var cert=decode(f.inventory.get(step.get("certificate")),"records","CERTIFICATE");
        var originalImages=Map.of(hash(original),original);
        assertThrows(IllegalArgumentException.class,()->MembershipCheckpointPlan.replay(app.configuration(),app.storage(),before,packet,cert,originalImages,Set.of(),temp.resolve("rejected")));
        assertFalse(java.nio.file.Files.exists(temp.resolve("rejected")),"reject authority before application scratch");
        var plan=MembershipCheckpointPlan.replay(app.configuration(),app.storage(),before,packet,cert,originalImages,votes(f,step),temp.resolve("actual"));
        assertArrayEquals(expected.image(),plan.application.image());assertEquals(42L,plan.catalog.value().get("applicationSequence"));
        var next=finish(plan);assertEquals(hash(expected.image()),next.context.catalog.get("application"));
        assertEquals(Set.of(hash(expected.image())),next.packet.images().keySet());
    }
}
