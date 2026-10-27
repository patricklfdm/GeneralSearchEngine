package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53SlotDriverTest {
    @TempDir Path temp;
    record Input(Decoded entry,byte[] payload) {}
    V53NativeDispatchTest.Network network(int size)throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;var b=ReplicationBounds.defaults();
        // Three independently forced floor copies may outlive the default socket
        // deadline on this filesystem. Qualify the larger profiles under an
        // explicit supported caller setting, without changing the 180s round.
        var bounds=size==3?b:new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
            b.maxRetryAttempts(),30_000,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
        return helper.new Network(size,bounds);
    }
    Input input(V53NativeDispatchTest.Network n,boolean data)throws Exception {
        var own=n.owners.getFirst();var context=own.activationContext();byte[] payload=new byte[0];
        if(data)try(var encoder=new ReplicaApplication<>(builder().configuration(),n.f.request.targets().getFirst().materialization(),ReplicationBounds.defaults())) {
            payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(100,"next-slot"))));
        }
        return new Input(decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),"index",number(context.cut.get("index"))+1,
            "previous",context.cut.get("entry"),"origin",n.ballot,"kind",data?"DATA":"BARRIER","payload",hash(payload))),"records","ENTRY"),payload);
    }
    MembershipSlotDriver driver(V53NativeDispatchTest.Network n,long started,MembershipSlotDriver.Events events)throws Exception {
        return new MembershipSlotDriver(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,n.transports.getFirst(),
            System::nanoTime,started,V53NativeDispatchTest.BUDGET,builder().configuration(),n.f.request.targets().getFirst().materialization(),events);
    }
    @Test void wholeCoordinatorPublishesTwoSlotsAtThreeStableSizes()throws Exception {
        for(int size:List.of(3,4,5))try(var n=network(size)) {
            long started=System.nanoTime();n.activate();
            var retiring=new AtomicInteger();n.hook.set(event->{if(event.equals("RETIREMENT_OLD_FILES_FORCED")) {
                var usage=n.resources.get(1).usage();retiring.incrementAndGet();
                assertTrue(usage.counts().getOrDefault(MembershipResources.Unit.SOURCE,0)<=1+n.voters.size(),"receiving copies must leave before retirement reservation");
                assertTrue(usage.counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)<=3+n.voters.size(),"floor must reuse current receiving images");
            }});
            for(boolean data:List.of(false,true)) {
                long slotStarted=System.nanoTime();
                var input=input(n,data);long index=number(input.entry.value().get("index"));n.events.add(Map.of("node","node-1","event","SLOT_BEGIN","index",index));
                try(var driver=driver(n,started,(event,record,voters)->{
                    if(event.equals("FUTURE_QUORUM_COMPLETE"))n.events.add(Map.of("node","node-1","event",event,"index",index,"voters",voters.stream().sorted().toList()));
                    if(event.equals("APPLIED") || event.equals("PUBLISHED"))try{n.f.snapshot((event.equals("APPLIED")?"applied-":"published-")+index);}catch(Exception error){throw new IOException(error);}
                })) {
                    assertTrue(driver.published().isEmpty());var done=driver.run(input.entry,input.payload);assertEquals("PUBLISH_ACK",done.kind());
                    assertArrayEquals(done.bytes(),driver.published().orElseThrow().bytes());
                    for(int i:n.voters)assertEquals(index,n.owners.get(i).activationContext().cut.get("index"));
                    assertThrows(IllegalArgumentException.class,()->driver.run(input.entry,input.payload));
                }
                System.out.println("v53SlotDriverWindow size="+size+" index="+index+" seconds="+(System.nanoTime()-slotStarted)/1_000_000_000.0+" requestTimeoutMillis="+n.bounds.requestTimeoutMillis());
            }
            for(int i=0;i<size;i++)if(!n.voters.contains(i))assertEquals(0L,n.owners.get(i).activationContext().cut.get("index"));
            assertEquals(2,retiring.get());
            if(size==3)Files.write(n.f.raw.resolve("result.json"),canonical(Map.of("status","PASS","slots",2,"network",true,"autonomous",false),4096));
            System.out.println("v53SlotDriverProfile=PASS size="+size+" raw="+n.f.raw.toAbsolutePath());
        }
    }
    @Test void lostControlAckRetriesWithoutAnotherVoteOrPartialSuccess()throws Exception {
        try(var n=network(3)) {
            long started=System.nanoTime();n.activate();var input=input(n,false);n.drop.set("ACCEPT_ACK");
            try(var driver=driver(n,started,MembershipSlotDriver.Events.NONE)) {
                assertEquals("PUBLISH_ACK",driver.run(input.entry,input.payload).kind());assertEquals("",n.drop.get());
                assertEquals(1,n.events.stream().filter(v->v.get("node").equals("node-2") && v.get("event").equals("ACCEPT_PARENT_FORCED")).count());
            }
        }
    }
    @Test void invalidAckDoesNotRetryOrCountAsAnOriginalReceipt()throws Exception {
        try(var n=network(3)) {
            long started=System.nanoTime();n.activate();var input=input(n,false);var attempts=new AtomicInteger();
            n.beforeSend.set(request->{if(request.kind().equals("ACCEPT"))n.events.add(Map.of("node","node-1","event","TEST_ACCEPT_SEND"));});
            n.response.set((request,reply)->{if(!reply.kind().equals("ACCEPT_ACK"))return reply;attempts.incrementAndGet();var value=new TreeMap<>(reply.value());
                var payload=new TreeMap<>(object(value.get("payload")));payload.put("receipt","0".repeat(64));value.put("payload",payload);return decode(encode("wire",reply.kind(),value),"wire",reply.kind());});
            try(var driver=driver(n,started,MembershipSlotDriver.Events.NONE)) {
                assertThrows(IllegalArgumentException.class,()->driver.run(input.entry,input.payload));assertTrue(driver.published().isEmpty());
                // The first real maintenance may outlive a socket attempt. Only
                // receipt of the invalid ACK, not its production at the server,
                // makes a subsequent retry a protocol error.
                assertTrue(attempts.get()>=1 && attempts.get()<=3);int received=-1,count=0;
                for(int i=0;i<n.events.size();i++) {var event=n.events.get(i);
                    if(event.get("event").equals("NETWORK_RECEIVED") && "ACCEPT_ACK".equals(event.get("kind"))){received=i;count++;}}
                assertEquals(1,count);assertTrue(n.events.subList(received+1,n.events.size()).stream().noneMatch(v->v.get("event").equals("TEST_ACCEPT_SEND")));
                assertTrue(n.events.stream().noneMatch(v->v.get("event").equals("PROOF_PARENT_FORCED")));
                assertEquals(0L,n.owners.getFirst().activationContext().cut.get("index"));
            }
        }
    }
    @Test void cancellationDrainsOutgoingPhaseAndNeverReportsSuccess()throws Exception {
        try(var n=network(3)) {
            long started=System.nanoTime();n.activate();var input=input(n,false);n.holdNextQuery.set(true);
            try(var driver=driver(n,started,MembershipSlotDriver.Events.NONE)) {
                var result=CompletableFuture.runAsync(()->assertThrows(Exception.class,()->driver.run(input.entry,input.payload)));
                assertTrue(n.queryEntered.await(10,TimeUnit.SECONDS));driver.close();result.get(10,TimeUnit.SECONDS);
                assertTrue(driver.published().isEmpty());assertEquals(0L,n.owners.getFirst().activationContext().cut.get("index"));
                assertTrue(n.events.stream().noneMatch(v->v.get("event").equals("PROOF_PARENT_FORCED")));
            }
        }
    }
    @Test void invalidPayloadAndDuplicateCoordinatorRefuseBeforeNativeVoting()throws Exception {
        try(var n=network(3)) {
            long started=System.nanoTime();n.activate();var input=input(n,false);
            var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            try(var driver=driver(n,started,MembershipSlotDriver.Events.NONE)) {
                assertThrows(IllegalArgumentException.class,()->driver(n,started,MembershipSlotDriver.Events.NONE));
                assertThrows(IllegalArgumentException.class,()->driver.run(input.entry,new byte[]{1}));assertTrue(driver.published().isEmpty());
                assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
            }
        }
    }
    @Test void failureAfterDurablePublicationDoesNotInventAnUndispatchedOutcome()throws Exception {
        try(var n=network(3)) {
            long started=System.nanoTime();n.activate();var input=input(n,false);
            try(var driver=driver(n,started,(event,record,voters)->{if(event.equals("PUBLISHED"))throw new IOException("lost completion after publication");})) {
                assertThrows(IOException.class,()->driver.run(input.entry,input.payload));assertTrue(driver.published().isEmpty());
                assertEquals(1L,n.owners.getFirst().activationContext().cut.get("index"));
                assertEquals(1L,n.owners.get(1).activationContext().cut.get("index"));
            }
        }
    }
    @Test void parentCancellationAtActualSocketWritePreventsRemoteAcceptance()throws Exception {
        try(var n=network(3)) {
            n.activate();var accepted=n.begin(false);var request=n.request(1,"ACCEPT",Map.of("acceptance",accepted.digest()));var cancelled=new AtomicBoolean();
            n.beforeSend.set(sent->{if(sent.kind().equals("ACCEPT"))cancelled.set(true);});
            assertThrows(IOException.class,()->MembershipSlotDelivery.deliver(n.owners.getFirst(),n.owners.get(1).activationIdentity(),request,n.resources.getFirst(),
                n.transports.getFirst(),System::nanoTime,System.nanoTime(),V53NativeDispatchTest.BUDGET,()->{if(cancelled.get())throw new IOException("parent cancelled");}));
            assertTrue(cancelled.get());assertTrue(n.events.stream().noneMatch(v->v.get("node").equals("node-2") && v.get("event").equals("ACCEPT_PARENT_FORCED")));
        }
    }
    @Test void expiredOriginalDeadlineCannotStartOrResetTheSlot()throws Exception {
        try(var n=network(3)) {
            n.activate();var input=input(n,false);var clock=new AtomicLong();
            var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            try(var driver=new MembershipSlotDriver(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),ReplicationBounds.defaults(),n.transports.getFirst(),
                    clock::get,0,V53NativeDispatchTest.BUDGET,builder().configuration(),n.f.request.targets().getFirst().materialization(),MembershipSlotDriver.Events.NONE)) {
                clock.set(V53NativeDispatchTest.BUDGET);assertThrows(IllegalArgumentException.class,()->driver.run(input.entry,input.payload));
                assertTrue(driver.published().isEmpty());assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
            }
        }
    }
    @Test void receiptCapacityIsReservedBeforeAnyVoteOrMaintenance()throws Exception {
        try(var n=network(3)) {
            long started=System.nanoTime();n.activate();var input=input(n,false);var resources=n.resources.getFirst();
            var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());var reservations=new ArrayList<MembershipResources.Lease>();
            try(var driver=driver(n,started,MembershipSlotDriver.Events.NONE)) {
                long consume=MembershipResources.QUEUE_LIMIT-resources.usage().queued()-(MembershipSlotDriver.RECORD_CAPACITY-2);
                try {
                    while(consume>0){long part=Math.min(consume,MembershipResources.Unit.CONTROL.bytes);reservations.add(resources.reserve(MembershipResources.Unit.CONTROL,"occupied-"+UUID.randomUUID(),part));consume-=part;}
                    assertThrows(IllegalArgumentException.class,()->driver.run(input.entry,input.payload));assertTrue(driver.published().isEmpty());
                    assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
                }finally{for(var lease:reservations)lease.close();}
            }
        }
    }
    @Test void higherBallotBeforeTheFinalReturnPreventsSuccess()throws Exception {
        try(var n=network(3)) {
            long started=System.nanoTime();n.activate();var input=input(n,false);
            try(var driver=driver(n,started,(event,record,voters)->{if(event.equals("PUBLISHED")){
                var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);n.owners.getFirst().observeCurrent(higher);
            }})) {
                assertThrows(IllegalArgumentException.class,()->driver.run(input.entry,input.payload));assertTrue(driver.published().isEmpty());
                assertEquals(1L,n.owners.getFirst().activationContext().cut.get("index"));
            }
        }
    }
}
