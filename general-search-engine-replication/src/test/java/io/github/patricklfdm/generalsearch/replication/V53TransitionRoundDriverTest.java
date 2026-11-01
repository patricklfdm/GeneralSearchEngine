package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** The internal owner must finish a sealed operation without a test sequencing
 * INTENT, the joint campaign, FINAL or the stable readiness barrier for it. */
class V53TransitionRoundDriverTest {
    @TempDir Path temp;
    V53NativeDispatchTest.Network network(String phase)throws Exception {
        return network(phase,4);
    }
    V53NativeDispatchTest.Network network(String phase,int size)throws Exception {
        assertTrue(size==4 || size==5,"REMOVE original voter count");
        var helper=new V53NativeDispatchTest();helper.temp=temp;var b=ReplicationBounds.defaults();
        var bounds=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
                b.maxRetryAttempts(),30_000,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
        return helper.new Network(size,bounds,TimeUnit.MINUTES.toNanos(10),f->{
            var walk=new V53AdmittedCrossViewTest.Walk(f);
            var request=Map.of("root",f.result.root().manifestDigest(),"expected",walk.current().authority(),"number",1L,"kind","REMOVE",
                    "target",f.request.targets().subList(0,size-1).stream().map(t->MembershipBootstrapSeed.identity(t.identity())).toList());
            walk.publish("RESERVE",Map.of("request",request));walk.publish("PREPARE",Map.of("number",1L,"revision",1L));
            walk.publish("READY",V53ContextFixture.map("number",1L,"receipt",null));
            if(!phase.equals("READY"))walk.publish("SEAL",Map.of("number",1L));
            if(phase.equals("JOINT") || phase.equals("CARRIED_FINAL")) {
                var op=object(list(walk.current().catalog.get("results")).getLast());
                walk.publish("INTENT",Map.of("sealed",V53ContextFixture.map("request",op.get("request"),"prepared",op.get("prepared"),"receipt",op.get("receipt"))));
            }
            if(phase.startsWith("CARRIED_")) {
                if(phase.equals("CARRIED_FINAL"))walk.campaign(f.request.targets());
                String kind=phase.substring("CARRIED_".length());int index=kind.equals("INTENT")?5:6;
                var op=object(list(walk.current().catalog.get("results")).getLast());
                Object command=kind.equals("INTENT")?Map.of("sealed",V53ContextFixture.map("request",op.get("request"),"prepared",op.get("prepared"),"receipt",op.get("receipt"))):Map.of("binding",op.get("binding"));
                f.observer=(target,operation,event)->{if(operation.equals("proof-"+index))throw new V53CarriedSlotDriverTest.Stop();};
                try {assertThrows(V53CarriedSlotDriverTest.Stop.class,()->walk.publish(kind,command));}
                finally {f.observer=(target,operation,event)->{};}
                f.observations.clear();
            }
        });
    }
    MembershipRoundDriver<?,?> driver(V53NativeDispatchTest.Network n,AtomicInteger ordinal,
            MembershipRoundDriver.Events callback)throws Exception {
        return driver(n,ordinal,callback,0);
    }
    MembershipRoundDriver<?,?> driver(V53NativeDispatchTest.Network n,AtomicInteger ordinal,
            MembershipRoundDriver.Events callback,int proposer)throws Exception {
        String local=n.owners.get(proposer).activationIdentity().nodeId().value();
        return new MembershipRoundDriver<>(n.owners.get(proposer),n.endpoints.get(proposer),n.resources.get(proposer),n.bounds,n.transports.get(proposer),
                    temp.resolve("transition-"+UUID.randomUUID()),()->System.nanoTime()+n.offset.get(),TimeUnit.MINUTES.toNanos(10),2,
                    builder().configuration(),n.f.request.targets().get(proposer).materialization(),(event,record)->{
                        n.events.add(Map.of("node",local,"event","ROUND_"+event,"record",record.digest(),"bytes",Base64.getEncoder().encodeToString(record.bytes())));
                        if(event.equals("INSTALLED")) {
                            int at=ordinal.incrementAndGet();n.selected=record;n.ballot=object(record.value().get("ballot"));
                            n.voters=list(record.value().get("sources")).stream().map(v->Integer.parseInt(((String)object(v).get("voter")).substring(5))-1).sorted().toList();
                            try{n.f.snapshot("installed-"+at);}catch(Exception error){throw new java.io.IOException(error);}
                            Files.write(n.f.raw.resolve("selected-"+at+".gsr"),record.bytes());
                            n.events.add(Map.of("node",local,"event","CONTINUOUS_INSTALLED","ordinal",at,"selection",record.digest()));
                        }
                        if(event.equals("SLOT_BEGIN")) {
                            long index=number(record.value().get("index"));String kind=(String)record.value().get("kind");
                            var catalog=n.owners.get(proposer).activationContext().catalog;var operation=object(list(catalog.get("results")).getLast());
                            byte[] payload=kind.equals("INTENT")?canonical(Map.of("sealed",V53ContextFixture.map("request",operation.get("request"),"prepared",operation.get("prepared"),"receipt",operation.get("receipt"))),8192):
                                    kind.equals("FINAL")?canonical(Map.of("binding",operation.get("binding")),8192):
                                    kind.equals("SEAL")?canonical(Map.of("number",1L),8192):new byte[0];
                            Files.write(n.f.raw.resolve("native-entry-"+index+".gsr"),record.bytes());Files.write(n.f.raw.resolve("native-payload-"+index+".bin"),payload);
                            n.events.add(Map.of("node",local,"event",event,"index",index));
                        }
                        callback.at(event,record);
                    },(event,record,voters)->{
                        n.events.add(Map.of("node",local,"event","DRIVER_"+event,"index",record.value().get("index"),"voters",voters.stream().sorted().toList()));
                        if(event.equals("APPLIED") || event.equals("PUBLISHED"))try{n.f.snapshot(event.toLowerCase(Locale.ROOT)+"-"+record.value().get("index"));}
                        catch(Exception error){throw new java.io.IOException(error);}
                    });
    }
    @Test void sealedRemoveFinishesThroughOneOriginalRoundLifetime()throws Exception {
        var ordinal=new AtomicInteger();
        try(var n=network("SEALED");var round=driver(n,ordinal,MembershipRoundDriver.Events.NONE)) {
                var completed=round.start();assertEquals("PUBLISH_ACK",completed.kind());assertEquals(3,ordinal.get());
                assertEquals(MembershipRoundDriver.State.READY,round.state());assertArrayEquals(completed.bytes(),round.readiness().bytes());
                assertEquals(7L,n.owners.getFirst().activationContext().cut.get("index"));
                assertNull(n.owners.getFirst().activationContext().catalog.get("active"));
                assertEquals("COMPLETED",object(list(n.owners.getFirst().activationContext().catalog.get("results")).getLast()).get("phase"));
                Files.write(n.f.raw.resolve("transition-round-result.json"),canonical(Map.of("status","PASS","kind","REMOVE","activations",3,
                        "internalReady",true,"publicReady",false,"originalBudgetSeconds",600),4096));

        }
    }
    @Test void removalProfileCompletesOneOriginalRoundLifetime()throws Exception {
        String profile=System.getProperty("v53.remove.profile","4-REMOVE");
        assertTrue(Set.of("4-REMOVE","5-REMOVE").contains(profile),"exact REMOVE profile");
        int size=profile.charAt(0)-'0';var ordinal=new AtomicInteger();
        try(var n=network("SEALED",size);var round=driver(n,ordinal,MembershipRoundDriver.Events.NONE)) {
            var completed=round.start();assertEquals("PUBLISH_ACK",completed.kind());assertEquals(3,ordinal.get());
            assertEquals(MembershipRoundDriver.State.READY,round.state());assertArrayEquals(completed.bytes(),round.readiness().bytes());
            var context=n.owners.getFirst().activationContext();assertEquals(7L,context.cut.get("index"));
            assertNull(context.catalog.get("active"));
            assertEquals("COMPLETED",object(list(context.catalog.get("results")).getLast()).get("phase"));
            var expected=java.util.stream.IntStream.range(1,size).mapToObj(i->"node-"+i).toList();
            assertEquals(expected,list(context.view.get("old")));assertEquals(expected,list(context.view.get("new")));
            assertNull(context.view.get("operation"));
            assertEquals(size/2+1,list(decode(Files.readAllBytes(n.f.raw.resolve("selected-1.gsr")),"records","SELECTED").value().get("sources")).size());
            assertEquals((size-1)/2+1,n.voters.size());
            Files.write(n.f.raw.resolve("transition-round-result.json"),canonical(Map.of("status","PASS","kind","REMOVE","profile",profile,
                    "activations",3,"internalReady",true,"publicReady",false,"originalBudgetSeconds",600),4096));
        }
    }
    @Test void originalJointConfigurationFinishesBeforeItsFirstBarrier()throws Exception {
        var ordinal=new AtomicInteger();
        try(var n=network("JOINT");var round=driver(n,ordinal,MembershipRoundDriver.Events.NONE)) {
            assertEquals("PUBLISH_ACK",round.start().kind());assertEquals(2,ordinal.get());round.readiness();
            assertEquals(7L,n.owners.getFirst().activationContext().cut.get("index"));
            assertNull(n.owners.getFirst().activationContext().catalog.get("active"));
        }
    }
    @Test void submittingSealRevokesOldReadinessUntilTheNewStableBarrier()throws Exception {
        var ordinal=new AtomicInteger();var ref=new AtomicReference<MembershipRoundDriver<?,?>>();
        try(var n=network("READY");var round=driver(n,ordinal,(event,record)->{
            if(event.equals("SLOT_BEGIN") && Set.of("SEAL","INTENT","FINAL").contains(record.value().get("kind"))) {
                assertNotEquals(MembershipRoundDriver.State.READY,ref.get().state());
                assertThrows(IllegalArgumentException.class,ref.get()::readiness);
            }
        })) {
            ref.set(round);var old=round.start();
            var seal=round.submit("SEAL",canonical(Map.of("number",1L),8192));
            assertEquals(5L,object(object(object(seal.value().get("payload")).get("published")).get("cut")).get("index"));
            assertEquals(3,ordinal.get());var fresh=round.readiness();assertNotEquals(old.digest(),fresh.digest());assertNotEquals(seal.digest(),fresh.digest());
            assertEquals(8L,n.owners.getFirst().activationContext().cut.get("index"));
            assertNull(n.owners.getFirst().activationContext().catalog.get("active"));
        }
    }
    @ParameterizedTest @CsvSource({"SEALED,higher","SEALED,close","SEALED,deadline","JOINT,higher","JOINT,close","JOINT,deadline"})
    void authorityBoundaryCannotReactivateAfterFencing(String phase,String cut)throws Exception {
        var ordinal=new AtomicInteger();var ref=new AtomicReference<MembershipRoundDriver<?,?>>();
        try(var n=network(phase);var round=driver(n,ordinal,(event,record)->{
            if(event.equals("SLOT_COMPLETE")) {
                assertEquals(MembershipRoundDriver.State.ACTIVATING,ref.get().state());
                assertThrows(IllegalArgumentException.class,ref.get()::readiness);
                if(cut.equals("close"))ref.get().close();
                else if(cut.equals("deadline"))n.offset.set(TimeUnit.MINUTES.toNanos(10));
                else {
                    var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);
                    n.owners.getFirst().observeCurrent(higher);
                }
            }
        })) {
            ref.set(round);var error=assertThrows(Exception.class,round::start);
            assertTrue(error.getMessage().contains(cut.equals("higher")?"higher ballot observed":cut.equals("deadline")?"original deadline":"closed/interrupted"),error.toString());
            assertEquals(cut.equals("close")?MembershipRoundDriver.State.CLOSED:MembershipRoundDriver.State.FAILED,round.state());
            assertEquals(1,ordinal.get());assertEquals(phase.equals("SEALED")?5L:6L,n.owners.getFirst().activationContext().cut.get("index"));
            assertFalse(n.events.stream().anyMatch(row->row.get("event").equals("ROUND_BEFORE_READY")));
            assertThrows(IllegalArgumentException.class,round::readiness);
            assertThrows(IllegalArgumentException.class,n.endpoints.getFirst()::checkInstalled);
        }
    }
    @ParameterizedTest @CsvSource({"CARRIED_INTENT,5,3","CARRIED_FINAL,6,2"})
    void originalCarriedTransitionCompletesWithoutChangingItsEntry(String phase,int index,int campaigns)throws Exception {
        var ordinal=new AtomicInteger();
        try(var n=network(phase);var round=driver(n,ordinal,MembershipRoundDriver.Events.NONE)) {
            byte[] original=Files.readAllBytes(n.f.raw.resolve("entry-"+index+".gsr"));
            assertEquals("PUBLISH_ACK",round.start().kind());assertEquals(campaigns,ordinal.get());round.readiness();
            assertArrayEquals(original,Files.readAllBytes(n.f.raw.resolve("native-entry-"+index+".gsr")));
            assertEquals(7L,n.owners.getFirst().activationContext().cut.get("index"));
            assertNull(n.owners.getFirst().activationContext().catalog.get("active"));
        }
    }
    @Test void removedSelectedFollowerCompletesFinalWithoutSuccessorAck()throws Exception {
        var ordinal=new AtomicInteger();
        try(var n=network("JOINT")) {
            // With node-3 unavailable, the only governing original joint quorum
            // is nodes 1,2,4. Node 4 must actually apply and publish FINAL.
            n.transports.get(2).close();
            try(var round=driver(n,ordinal,MembershipRoundDriver.Events.NONE)) {
                assertEquals("PUBLISH_ACK",round.start().kind());round.readiness();assertEquals(2,ordinal.get());
                var removed=n.owners.get(3);assertEquals(6L,removed.activationContext().cut.get("index"));
                assertNull(removed.activationContext().catalog.get("active"));assertFalse(removed.activationContext().voters().contains("node-4"));
                assertEquals(7L,n.owners.getFirst().activationContext().cut.get("index"));
                assertTrue(n.wire.stream().map(v->MembershipWire.decode(Base64.getDecoder().decode((String)v.get("response")),FRAME))
                        .anyMatch(v->v.kind().equals("APPLY_ACK") && object(v.value().get("sender")).get("node").equals("node-4")
                                && object(v.value().get("payload")).get("acknowledgement")==null));
                assertThrows(IllegalArgumentException.class,n.endpoints.get(3)::checkInstalled);
                Files.write(n.f.raw.resolve("departure-result.json"),canonical(Map.of("status","PASS","profile","removed-follower",
                        "proposer","node-1","removed","node-4","published",6,"ready",7,"activations",2,"publicReady",false),4096));
            }
        }
    }
    @Test void removedProposerCannotServeTheNewConfiguration()throws Exception {
        var installed=new AtomicInteger();var ready=new AtomicInteger();
        try(var n=network("JOINT")) {
            int index=3;var own=n.owners.get(index);
            try(var round=driver(n,installed,(event,record)->{
                        if(event.equals("BEFORE_READY"))ready.incrementAndGet();
                    },index)) {
                var failure=assertThrows(Exception.class,round::start);
                try(var writer=new java.io.PrintWriter(Files.newBufferedWriter(n.f.raw.resolve("removed-proposer-failure.txt")))) {
                    failure.printStackTrace(writer);
                }
                assertEquals("native round local member not eligible for activation",failure.getMessage());
                // Failure before FINAL would not establish removed-node fencing.
                assertEquals(6L,own.activationContext().cut.get("index"));
                assertNull(own.activationContext().catalog.get("active"));
                assertFalse(own.activationContext().voters().contains("node-4"));
                assertEquals(1,installed.get());assertEquals(0,ready.get());
                assertEquals(MembershipRoundDriver.State.FAILED,round.state());
                assertThrows(IllegalArgumentException.class,round::readiness);
                assertThrows(IllegalArgumentException.class,()->round.submit("BARRIER",new byte[0]));
                assertThrows(IllegalArgumentException.class,n.endpoints.get(index)::checkInstalled);
                int complete=-1;
                for(int i=0;i<n.events.size();i++)if(n.events.get(i).get("event").equals("ROUND_SLOT_COMPLETE"))complete=i;
                assertTrue(complete>=0);
                assertFalse(n.events.subList(complete+1,n.events.size()).stream().anyMatch(v->v.get("node").equals("node-4")
                        && Set.of("ALLOCATOR_FORCED","PROMISE_FORCED","FLOOR_COPIES_FORCED").contains(v.get("event"))));
                Files.write(n.f.raw.resolve("departure-result.json"),canonical(Map.of("status","PASS","profile","removed-proposer",
                        "proposer","node-4","removed","node-4","published",6,"ready",0,"activations",1,"publicReady",false),4096));
            }
        }
    }
}
