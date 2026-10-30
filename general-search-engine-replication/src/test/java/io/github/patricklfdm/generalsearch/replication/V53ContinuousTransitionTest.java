package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.io.IOException;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Same live journals, endpoints and original history through both authority
 * changes. No intermediate store reset or synthetic remote vote observations. */
class V53ContinuousTransitionTest {
    @TempDir Path temp;
    @Test void sameCutSourceSweepNeedsNewDurablePromiseAndOriginalGoverningCopies()throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network()) {
            var own=n.owners.getFirst();var identity=own.activationIdentity();
            var ballot=new TreeMap<String,Object>(Map.of("counter",own.reserveCounter(),"proposer",identity.nodeId().value(),
                    "incarnation",identity.storageId().toString()));
            var first=own.prepareCurrent(ballot);assertFalse(own.publishedMaintenanceRequired());
            ballot.put("counter",own.reserveCounter());own.observeCurrent(ballot);
            assertFalse(own.publishedMaintenanceRequired(),"an observed ballot is not durable retirement authority");
            var latest=own.prepareCurrent(ballot);var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            assertTrue(own.publishedMaintenanceRequired());assertFalse(own.nativeGenerationMaintenanceRequired());
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
            var permit=own.publishedMaintenance(n.resources.getFirst());
            assertThrows(IllegalArgumentException.class,()->own.supersededPublishedSources(permit));
            own.establishFloor(List.of(own.floorCopyCurrent(),n.owners.get(1).floorCopyCurrent()));
            var obsolete=own.supersededPublishedSources(permit);
            assertEquals(List.of(first.value().get("basisId")),obsolete);
            own.retireSource(obsolete.getFirst());permit.check();own.releaseFloor();
            assertArrayEquals(latest.bytes(),own.originalBasis().orElseThrow().bytes());
            assertFalse(own.publishedMaintenanceRequired());
            assertFalse(Files.exists(n.f.request.targets().getFirst().replicaDirectory().resolve("sources/"+first.value().get("basisId"))));
            assertEquals(1,n.resources.getFirst().usage().counts().get(MembershipResources.Unit.SOURCE));
        }
    }
    @Test void closeDuringPreGrantMaintenanceCannotPublishANewPromise()throws Exception {
        preGrantInterrupted(false);
    }
    @Test void higherBallotDuringPreGrantMaintenanceCannotPublishANewPromise()throws Exception {
        preGrantInterrupted(true);
    }
    private void preGrantInterrupted(boolean higher)throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network()) {
            n.activate();n.driver.close();n.driver=null;
            var entered=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();
            var before=n.owners.getFirst().originalSelection().orElseThrow().digest();
            int promises=(int)n.events.stream().filter(v->v.get("node").equals("node-1") && v.get("event").equals("PROMISE_FORCED")).count();
            try(var next=new MembershipActivationDriver(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,
                    (peer,request,kind,deadline)->{if(request.kind().equals("STATUS_PROBE")){entered.countDown();return pending;}
                        return n.transports.getFirst().exchange(peer,request,kind,deadline);},
                    List.of(),List.of(),temp.resolve("pregrant-"+UUID.randomUUID()),System::nanoTime,V53NativeDispatchTest.BUDGET,2)) {
                var result=CompletableFuture.supplyAsync(()->assertThrows(Exception.class,next::run));
                assertTrue(entered.await(30,TimeUnit.SECONDS));
                if(higher) {
                    var ballot=new TreeMap<>(n.ballot);ballot.put("counter",number(ballot.get("counter"))+1);
                    n.owners.getFirst().observeCurrent(ballot);
                    // A retryable transport failure must check the higher
                    // ballot before another exchange. An ordinary IOException
                    // instead propagates immediately as a terminal failure.
                    pending.completeExceptionally(new MembershipTransport.Failure(MembershipTransport.Reason.IO,
                            "held maintenance discovery",new IOException("interrupted connection")));
                    assertEquals("higher ballot observed; fresh campaign required",result.get(10,TimeUnit.SECONDS).getMessage());
                } else {next.close();result.get(10,TimeUnit.SECONDS);}
                assertTrue(pending.isDone());assertEquals(0,next.campaigns());
                assertEquals(before,n.owners.getFirst().originalSelection().orElseThrow().digest());
                assertEquals(promises,n.events.stream().filter(v->v.get("node").equals("node-1") && v.get("event").equals("PROMISE_FORCED")).count());
            } finally {pending.cancel(true);}
        }
    }
    @Test void preGrantMaintenanceCannotBorrowPendingVoteAuthority()throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network()) {
            n.activate();var own=n.owners.getFirst();var permit=own.publishedMaintenance(n.resources.getFirst());permit.check();
            n.begin(false);
            assertFalse(own.publishedMaintenanceRequired());
            assertThrows(IllegalArgumentException.class,()->own.publishedMaintenance(n.resources.getFirst()));
            assertEquals("published maintenance cannot retire pending vote",assertThrows(IllegalArgumentException.class,permit::check).getMessage());
        }
    }
    @Test void preGrantMaintenanceRetainsTheOriginalObservedFence()throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network()) {
            n.activate();var own=n.owners.getFirst();var permit=own.publishedMaintenance(n.resources.getFirst());permit.check();
            assertEquals("published maintenance foreign owner",assertThrows(IllegalArgumentException.class,
                    ()->n.owners.get(1).supersededPublishedSources(permit)).getMessage());
            var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);own.observeCurrent(higher);
            assertEquals("higher ballot observed; fresh campaign required",assertThrows(IllegalArgumentException.class,permit::check).getMessage());
        }
    }
    @Test void nativeRemoveReactivatesJointThenStableBeforeService()throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;var b=ReplicationBounds.defaults();
        var bounds=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
                b.maxRetryAttempts(),30_000,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
        try(var n=helper.new Network(4,bounds,f->{
            var walk=new V53AdmittedCrossViewTest.Walk(f);
            var request=Map.of("root",f.result.root().manifestDigest(),"expected",walk.current().authority(),"number",1L,"kind","REMOVE",
                    "target",f.request.targets().subList(0,3).stream().map(t->MembershipBootstrapSeed.identity(t.identity())).toList());
            walk.publish("RESERVE",Map.of("request",request));walk.publish("PREPARE",Map.of("number",1L,"revision",1L));
            walk.publish("READY",V53ContextFixture.map("number",1L,"receipt",null));walk.publish("SEAL",Map.of("number",1L));
        })) {
            activate(n,1);var own=n.owners.getFirst();var operation=object(list(own.activationContext().catalog.get("results")).getLast());
            var intent=publish(n,"INTENT",canonical(Map.of("sealed",V53ContextFixture.map("request",operation.get("request"),
                    "prepared",operation.get("prepared"),"receipt",operation.get("receipt"))),8192));
            assertEquals("PUBLISH_ACK",intent.kind());assertNotNull(own.activationContext().view.get("operation"));
            assertThrows(IllegalArgumentException.class,n.endpoints.getFirst()::checkInstalled);
            activate(n,2);assertNotNull(own.activationContext().view.get("operation"));
            for(int i:n.voters)assertEquals(2,n.resources.get(i).usage().counts().get(MembershipResources.Unit.SOURCE));
            operation=object(list(own.activationContext().catalog.get("results")).getLast());
            var finalized=publish(n,"FINAL",canonical(Map.of("binding",operation.get("binding")),8192));
            assertEquals("PUBLISH_ACK",finalized.kind());assertNull(own.activationContext().view.get("operation"));
            assertEquals(List.of("node-1","node-2","node-3"),list(own.activationContext().view.get("old")));
            assertThrows(IllegalArgumentException.class,n.endpoints.getFirst()::checkInstalled);
            activate(n,3);var barrier=publish(n,"BARRIER",new byte[0]);assertEquals("PUBLISH_ACK",barrier.kind());
            n.endpoints.getFirst().checkInstalled();assertEquals(7L,own.activationContext().cut.get("index"));
            assertNull(own.activationContext().catalog.get("active"));
            assertEquals("COMPLETED",object(list(own.activationContext().catalog.get("results")).getLast()).get("phase"));
            Files.write(n.f.raw.resolve("continuous-result.json"),canonical(Map.of("status","PASS","kind","REMOVE",
                    "activations",3,"publicReady",false,"automaticLifecycle",false),4096));
            System.out.println("v53ContinuousTransition=PASS raw="+n.f.raw.toAbsolutePath());
        }
    }
    private void activate(V53NativeDispatchTest.Network n,int ordinal)throws Exception {
        if(n.driver!=null){n.driver.close();n.driver=null;}
        n.driver=new MembershipActivationDriver(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,
                n.transports.getFirst()::exchange,List.of(),List.of(),temp.resolve("activation-"+ordinal),System::nanoTime,V53NativeDispatchTest.BUDGET,2);
        n.selected=n.driver.run();n.ballot=object(n.selected.value().get("ballot"));
        n.voters=list(n.selected.value().get("sources")).stream().map(v->Integer.parseInt(((String)object(v).get("voter")).substring(5))-1).sorted().toList();
        n.f.snapshot("installed-"+ordinal);Files.write(n.f.raw.resolve("selected-"+ordinal+".gsr"),n.selected.bytes());
        n.events.add(Map.of("node","node-1","event","CONTINUOUS_INSTALLED","ordinal",ordinal,"selection",n.selected.digest()));
        System.out.println("v53ContinuousTransitionStage=installed ordinal="+ordinal);
    }
    private Decoded publish(V53NativeDispatchTest.Network n,String kind,byte[] payload)throws Exception {
        var own=n.owners.getFirst();var context=own.activationContext();long index=number(context.cut.get("index"))+1;
        var entry=decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),"index",index,
                "previous",context.cut.get("entry"),"origin",n.ballot,"kind",kind,"payload",hash(payload))),"records","ENTRY");
        Files.write(n.f.raw.resolve("native-entry-"+index+".gsr"),entry.bytes());Files.write(n.f.raw.resolve("native-payload-"+index+".bin"),payload);
        n.events.add(Map.of("node","node-1","event","SLOT_BEGIN","index",index));
        try(var driver=new MembershipSlotDriver(own,n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,n.transports.getFirst(),
                System::nanoTime,System.nanoTime(),V53NativeDispatchTest.BUDGET,builder().configuration(),n.f.request.targets().getFirst().materialization(),
                (event,record,voters)->{
                    n.events.add(Map.of("node","node-1","event","DRIVER_"+event,"index",record.value().get("index"),"voters",voters.stream().sorted().toList()));
                    if(event.equals("APPLIED") || event.equals("PUBLISHED"))try{n.f.snapshot(event.toLowerCase(Locale.ROOT)+"-"+record.value().get("index"));}
                    catch(Exception error){throw new java.io.IOException(error);}
                })) {
            var done=driver.run(entry,payload);System.out.println("v53ContinuousTransitionStage="+kind+" index="+index);return done;
        }
    }
}
