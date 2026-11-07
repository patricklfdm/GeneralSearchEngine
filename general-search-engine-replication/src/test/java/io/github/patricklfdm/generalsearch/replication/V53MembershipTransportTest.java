package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.BooleanSupplier;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ActivationTest.*;

/** Real TCP component qualification over public offline bootstrap; not distributed consensus acceptance. */
class V53MembershipTransportTest {
    @TempDir Path temp;
    static long deadline(){return System.nanoTime()+TimeUnit.SECONDS.toNanos(10);}
    static ReplicationBounds bounds(int inFlight,int millis,int frame) {
        var b=ReplicationBounds.defaults();return new ReplicationBounds(frame,b.maxEntriesPerAppend(),inFlight,b.maxPendingClientOperations(),
                b.maxRetryAttempts(),millis,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
    }
    static MembershipResources resources(long queue){return new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,queue);}
    static void waitFor(BooleanSupplier done)throws Exception {
        long end=deadline();while(!done.getAsBoolean() && System.nanoTime()<end)Thread.sleep(5);assertTrue(done.getAsBoolean(),"bounded completion");
    }
    static void await(CountDownLatch latch)throws IOException {
        try{if(!latch.await(10,TimeUnit.SECONDS))throw new IOException("test barrier timeout");}
        catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("test barrier interrupted",e);}
    }
    static MembershipTransport.Failure failure(CompletableFuture<?> future)throws Exception {
        return assertInstanceOf(MembershipTransport.Failure.class,assertThrows(ExecutionException.class,()->future.get(10,TimeUnit.SECONDS)).getCause());
    }
    final class Group implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture fixture;
        final MembershipCapsule capsule;
        final List<MembershipIdentity> identities;
        final List<MembershipTransport> transports=new ArrayList<>();
        final List<MembershipResources> budgets=new ArrayList<>();
        Group(int size)throws Exception {this(size,Files.createDirectories(temp.resolve(UUID.randomUUID().toString()+"-raw")));}
        Group(int size,Path raw)throws Exception {
            this(size,raw,null);
        }
        Group(int size,Path raw,Path source)throws Exception {
            this(size,raw,source,V53NativeResourceProfile.SMALL_FIXTURE);
        }
        Group(int size,Path raw,Path source,V53NativeResourceProfile profile)throws Exception {
            var helper=new V53BootstrapSeedTest();helper.temp=temp;
            var request=helper.request(temp.resolve(UUID.randomUUID().toString()),size,source);
            var sockets=new ArrayList<ServerSocket>();var targets=new ArrayList<MembershipBootstrapTarget<Integer,Doc>>();
            try {
                for(var old:request.targets()) {
                    var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"));sockets.add(socket);
                    var id=new MembershipIdentity(old.identity().nodeId(),old.identity().storageId(),new ReplicationEndpoint("127.0.0.1",socket.getLocalPort()));
                    targets.add(new MembershipBootstrapTarget<>(id,old.replicaDirectory(),old.materialization()));
                }
            }finally{for(var socket:sockets)socket.close();}
            var dynamic=new MembershipBootstrapRequest<>(request.groupId(),request.configurationId(),request.source(),request.sourcePath(),targets,
                    request.operationDirectory(),request.maxSourceBytes(),request.maxOperationBytes());
            fixture=new V53BootstrapPublicationTest.Fixture(raw,dynamic,profile);capsule=fixture.original.seed.capsule;
            identities=targets.stream().map(MembershipBootstrapTarget::identity).toList();
        }
        Decoded request(int from,int to){return request(from,to,"STATUS_PROBE",Map.of("nonce",new UUID(51,53).toString()));}
        Decoded request(int from,int to,String kind,Map<String,Object> payload) {
            var sender=identities.get(from);var ballot=Map.of("counter",2L,"proposer",sender.nodeId().value(),"incarnation",sender.storageId().toString());
            return decode(encode("wire",kind,Map.of("root",capsule.context.root,"view",capsule.context.authority(),"ballot",ballot,
                    "sender",MembershipBootstrapSeed.identity(sender),"recipient",MembershipBootstrapSeed.identity(identities.get(to)),
                    "trace",new UUID(53,1).toString(),"sequence",1L,"payload",payload)),"wire",kind);
        }
        Decoded status(MembershipIdentity sender,Decoded request) {
            return response(request,"STATUS",Map.of("cut",capsule.context.cut,"nonce",object(request.value().get("payload")).get("nonce"),"ready",false));
        }
        MembershipTransport start(int node,MembershipTransport.Handler handler,MembershipTransport.Events events,ReplicationBounds bound,MembershipResources budget)throws Exception {
            var transport=new MembershipTransport(capsule,identities.get(node),bound,budget,handler,events);transports.add(transport);budgets.add(budget);return transport;
        }
        MembershipTransport start(int node)throws Exception{return start(node,this::status,MembershipTransport.Events.NONE,bounds(2,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));}
        @Override public void close() {
            for(var transport:transports)transport.close();
            for(var transport:transports)assertEquals(new MembershipTransport.Usage(0,0,0,true),transport.usage());
            for(var budget:budgets){assertEquals(0,budget.usage().leases());assertEquals(0,budget.usage().queued());}
        }
    }
    @Test void fullMeshUsesExactFrozenFramesAtEveryStableSize()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-transport/run-"+UUID.randomUUID()));
        System.out.println("v53TransportEvidence="+evidence.toAbsolutePath());var profiles=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));var wire=new ArrayList<Map<String,Object>>();
            try(var group=new Group(size,raw)) {
                var nodes=new ArrayList<MembershipTransport>();for(int n=0;n<size;n++)nodes.add(group.start(n));
                for(int from=0;from<size;from++)for(int to=0;to<size;to++)if(from!=to) {
                    var request=group.request(from,to);var reply=nodes.get(from).exchange(group.identities.get(to),request,"STATUS",deadline()).get(10,TimeUnit.SECONDS);
                    assertArrayEquals(group.status(group.identities.get(from),request).bytes(),reply.bytes());
                    wire.add(Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(reply.bytes())));
                }
                var hello=group.request(0,1,"HELLO",Map.of("mode","VOTER","protocol","gse-replication/1.3","rootRecord",group.fixture.original.seed.rootRecord.digest()));
                assertDoesNotThrow(()->MembershipWire.envelope(hello,group.capsule.context.root,group.identities.getFirst(),group.identities.get(1)));
                group.fixture.snapshot("after");
            }
            Files.write(raw.resolve("wire.json"),ReplicaJson.encode(wire,1024*1024));profiles.add(Map.of("size",size,"exchanges",wire.size()));
        }
        Files.write(evidence.resolve("receipt.json"),ReplicaJson.encode(Map.of("schema","gse-v53-transport-component-v1","status","PASS","profiles",profiles,
                "execution","loopback-tcp-component","publicRuntime",false,"distributedProtocolQualification",false),1024*1024));
    }
    @Test void stalledPeerCannotBlockAnotherPeerOrReverseSourceRequest()throws Exception {
        try(var group=new Group(3)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var first=group.start(0);
            var reverse=new AtomicReference<MembershipTransport>();
            group.start(1,(sender,request)->{entered.countDown();await(release);try {
                var back=group.request(1,0);reverse.get().exchange(group.identities.get(0),back,"STATUS",deadline()).get(10,TimeUnit.SECONDS);
            }catch(Exception e){throw new IOException(e);}return group.status(sender,request);},MembershipTransport.Events.NONE,bounds(1,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            reverse.set(group.transports.getLast());group.start(2);
            var held=first.exchange(group.identities.get(1),group.request(0,1),"STATUS",deadline());assertTrue(entered.await(5,TimeUnit.SECONDS));
            assertNotNull(first.exchange(group.identities.get(2),group.request(0,2),"STATUS",deadline()).get(5,TimeUnit.SECONDS));
            release.countDown();assertNotNull(held.get(5,TimeUnit.SECONDS));
        }
    }
    @Test void lostResponseNeedsExplicitIdenticalRetryAndNeverMultipliesAttempts()throws Exception {
        try(var group=new Group(3)) {
            var seen=new CopyOnWriteArrayList<String>();var lost=new AtomicBoolean(true);var first=group.start(0);
            group.start(1,(sender,request)->{seen.add(request.digest());return group.status(sender,request);},(event,request,response)->{
                if(event.equals("BEFORE_RESPONSE_WRITE") && lost.get())throw new IOException("lost response");
            },bounds(2,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            var request=group.request(0,1);long start=System.nanoTime(),budget=TimeUnit.SECONDS.toNanos(10);var exchange=new MembershipExchange(request.digest(),start,budget);
            for(int n=0;n<3;n++) {
                exchange.attempt(request.digest(),System.nanoTime());
                assertEquals(MembershipTransport.Reason.IO,failure(first.exchange(group.identities.get(1),request,"STATUS",start+budget)).reason);
                assertEquals(n+1,seen.size());
            }
            assertThrows(IllegalArgumentException.class,()->exchange.attempt(request.digest(),System.nanoTime()));
            assertEquals(List.of(request.digest(),request.digest(),request.digest()),seen);
            // A different protocol exchange may succeed; no hidden transport retry rescued the exhausted one.
            lost.set(false);assertNotNull(first.exchange(group.identities.get(1),group.request(0,1),"STATUS",deadline()).get(5,TimeUnit.SECONDS));
        }
    }
    @Test void cancellationDoesNotFreeCapacityUntilHeldWorkerUnwinds()throws Exception {
        try(var group=new Group(3)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var budget=resources(MembershipResources.QUEUE_LIMIT);
            var first=group.start(0,group::status,(event,request,response)->{if(event.equals("BEFORE_REQUEST_WRITE")){entered.countDown();await(release);}},bounds(1,5000,FRAME),budget);group.start(1);
            var request=group.request(0,1);var pending=first.exchange(group.identities.get(1),request,"STATUS",deadline());assertTrue(entered.await(5,TimeUnit.SECONDS));
            assertTrue(pending.cancel(true));assertEquals(request.size(),budget.usage().queued());
            assertEquals(MembershipTransport.Reason.CAPACITY,failure(first.exchange(group.identities.get(1),request,"STATUS",deadline())).reason);
            release.countDown();waitFor(()->budget.usage().leases()==0 && first.usage().outgoing()==0);
        }
    }
    @Test void deadlineIncludesBeforeWritePauseAndCannotBeRenewedByTheTransport()throws Exception {
        try(var group=new Group(3)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var calls=new AtomicInteger();
            var first=group.start(0,group::status,(event,request,response)->{if(event.equals("BEFORE_REQUEST_WRITE")){entered.countDown();await(release);}},bounds(1,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            group.start(1,(sender,request)->{calls.incrementAndGet();return group.status(sender,request);},MembershipTransport.Events.NONE,bounds(2,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(1);var pending=first.exchange(group.identities.get(1),group.request(0,1),"STATUS",end);
            assertTrue(entered.await(5,TimeUnit.SECONDS));waitFor(()->System.nanoTime()>end);release.countDown();
            assertEquals(MembershipTransport.Reason.DEADLINE,failure(pending).reason);assertEquals(0,calls.get());
            assertEquals(MembershipTransport.Reason.DEADLINE,failure(first.exchange(group.identities.get(1),group.request(0,1),"STATUS",end)).reason);
        }
    }
    @Test void continuationCanReuseSinglePermitAndCloseItsOwnTransport()throws Exception {
        try(var group=new Group(3)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var once=new AtomicBoolean();
            var first=group.start(0,group::status,MembershipTransport.Events.NONE,bounds(1,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            group.start(1,(sender,request)->{if(once.compareAndSet(false,true)){entered.countDown();await(release);}return group.status(sender,request);},MembershipTransport.Events.NONE,bounds(2,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            var request=group.request(0,1);var call=first.exchange(group.identities.get(1),request,"STATUS",deadline());assertTrue(entered.await(5,TimeUnit.SECONDS));
            var chained=call.thenCompose(reply->first.exchange(group.identities.get(1),request,"STATUS",deadline())).thenRun(first::close);
            release.countDown();chained.get(5,TimeUnit.SECONDS);first.close();
            assertEquals(MembershipTransport.Reason.CLOSED,failure(first.exchange(group.identities.get(1),request,"STATUS",deadline())).reason);
        }
    }
    @Test void closeInterruptsHeldHandlerAndReclaimsAllSocketAndQueueOwners()throws Exception {
        try(var group=new Group(3)) {
            var entered=new CountDownLatch(1);var never=new CountDownLatch(1);var first=group.start(0);
            var receiver=group.start(1,(sender,request)->{entered.countDown();await(never);return group.status(sender,request);},MembershipTransport.Events.NONE,bounds(2,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            var pending=first.exchange(group.identities.get(1),group.request(0,1),"STATUS",deadline());assertTrue(entered.await(5,TimeUnit.SECONDS));
            receiver.close();assertEquals(MembershipTransport.Reason.IO,failure(pending).reason);
            first.close();assertEquals(0,receiver.usage().incoming());assertEquals(0,first.usage().sockets());
        }
    }
    @Test void wrongRootSenderStorageRecipientAndReplyCorrelationFailClosed()throws Exception {
        try(var group=new Group(3)) {
            var calls=new AtomicInteger();var first=group.start(0);
            var receiver=group.start(1,(sender,request)->{calls.incrementAndGet();return changed(group.status(sender,request),"sequence",2L);},MembershipTransport.Events.NONE,bounds(2,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            var request=group.request(0,1);var sender=new TreeMap<>(object(request.value().get("sender")));sender.put("storage",new UUID(99,99).toString());
            for(var bad:List.of(changed(request,"root","0".repeat(64)),changed(request,"sender",sender),changed(request,"recipient",request.value().get("sender")))) {
                assertEquals(MembershipTransport.Reason.PROTOCOL,failure(first.exchange(group.identities.get(1),bad,"STATUS",deadline())).reason);
                rawRejected(group.identities.get(1),bad.bytes());
            }
            assertEquals(0,calls.get());
            // Receiver also enforces correlation; the bad reply is never put on the wire.
            assertEquals(MembershipTransport.Reason.IO,failure(first.exchange(group.identities.get(1),request,"STATUS",deadline())).reason);
            assertEquals(1,calls.get());waitFor(()->receiver.usage().incoming()==0);
        }
    }
    static void rawRejected(MembershipIdentity recipient,byte[] bytes)throws Exception {
        try(var socket=new Socket(recipient.endpoint().host(),recipient.endpoint().port())) {
            socket.setSoTimeout(5000);socket.getOutputStream().write(bytes);socket.getOutputStream().flush();
            try{assertEquals(-1,socket.getInputStream().read());}catch(SocketException closed){/* reset also refuses the frame */}
        }
    }
    @Test void oversizedAndUnreservedBodiesAreRefusedFromTheHeaderAlone()throws Exception {
        try(var group=new Group(3)) {
            var calls=new AtomicInteger();var budget=resources(HEADER);var receiver=group.start(1,(sender,request)->{calls.incrementAndGet();return group.status(sender,request);},
                    MembershipTransport.Events.NONE,bounds(2,5000,1024),budget);
            byte[] header=Arrays.copyOf(group.request(0,1).bytes(),HEADER);
            rawRejected(group.identities.get(1),header); // valid body, but no receive reservation can fit
            ByteBuffer.wrap(header).putInt(12,2048);rawRejected(group.identities.get(1),header); // caller limit, no body sent
            ByteBuffer.wrap(header).putInt(12,-1);rawRejected(group.identities.get(1),header);
            assertEquals(0,calls.get());waitFor(()->receiver.usage().incoming()==0 && budget.usage().leases()==0);
            var first=group.start(0,group::status,MembershipTransport.Events.NONE,bounds(1,5000,FRAME),resources(HEADER));
            assertEquals(MembershipTransport.Reason.CAPACITY,failure(first.exchange(group.identities.get(1),group.request(0,1),"STATUS",deadline())).reason);
        }
    }
    @Test void globalIncompleteConnectionsAreBoundedAndCloseReleasesTheirHeaders()throws Exception {
        try(var group=new Group(3)) {
            var budget=resources(MembershipResources.QUEUE_LIMIT);var receiver=group.start(1,group::status,MembershipTransport.Events.NONE,bounds(1,5000,FRAME),budget);
            var sockets=new ArrayList<Socket>();var peer=group.identities.get(1);
            try {
                for(int n=0;n<6;n++)sockets.add(new Socket(peer.endpoint().host(),peer.endpoint().port()));
                waitFor(()->receiver.usage().incoming()==6 && budget.usage().leases()==6);
                rawRejected(peer,group.request(0,1).bytes());assertEquals(6,receiver.usage().incoming());assertEquals(6*HEADER,budget.usage().queued());
                receiver.close();assertEquals(0,budget.usage().queued());
            }finally{for(var socket:sockets)socket.close();}
        }
    }
    @Test void directoryCannotAcceptAnotherRootAndRelearningKeepsPeerCapacity()throws Exception {
        try(var group=new Group(3);var foreign=new Group(3)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
            var first=group.start(0,group::status,(event,request,response)->{if(event.equals("BEFORE_REQUEST_WRITE")){entered.countDown();await(release);}},bounds(1,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));group.start(1);
            assertThrows(IllegalArgumentException.class,()->first.learn(foreign.capsule));
            var request=group.request(0,1);var pending=first.exchange(group.identities.get(1),request,"STATUS",deadline());assertTrue(entered.await(5,TimeUnit.SECONDS));
            first.learn(group.capsule);
            assertEquals(MembershipTransport.Reason.CAPACITY,failure(first.exchange(group.identities.get(1),request,"STATUS",deadline())).reason);
            release.countDown();assertNotNull(pending.get(5,TimeUnit.SECONDS));
        }
    }
    @Test void receiverEnforcesPerPeerLimitWithoutConsumingAnotherPeersProgress()throws Exception {
        try(var group=new Group(3)) {
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var calls=new AtomicInteger();var first=group.start(0);var third=group.start(2);
            group.start(1,(sender,request)->{
                calls.incrementAndGet();if(sender.equals(group.identities.getFirst())){entered.countDown();await(release);}return group.status(sender,request);
            },MembershipTransport.Events.NONE,bounds(1,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            var request=group.request(0,1);var pending=first.exchange(group.identities.get(1),request,"STATUS",deadline());assertTrue(entered.await(5,TimeUnit.SECONDS));
            assertEquals(MembershipTransport.Reason.IO,failure(first.exchange(group.identities.get(1),request,"STATUS",deadline())).reason);
            assertNotNull(third.exchange(group.identities.get(1),group.request(2,1),"STATUS",deadline()).get(5,TimeUnit.SECONDS));
            assertEquals(2,calls.get());release.countDown();assertNotNull(pending.get(5,TimeUnit.SECONDS));
        }
    }
    @Test void clientRejectsWrongReplyKindAndOversizedReplyButPassesExactProtocolReject()throws Exception {
        try(var group=new Group(3)) {
            var mode=new AtomicInteger();var first=group.start(0);var request=group.request(0,1);
            group.start(1,(sender,input)->switch(mode.get()) {
                case 0 -> response(input,"HELLO",Map.of("mode","VOTER","protocol","gse-replication/1.3","rootRecord",group.fixture.original.seed.rootRecord.digest()));
                case 1 -> response(input,"REJECT",Map.of("reason","NOT_READY","promised",input.value().get("ballot")));
                default -> group.status(sender,input);
            },MembershipTransport.Events.NONE,bounds(2,5000,FRAME),resources(MembershipResources.QUEUE_LIMIT));
            assertEquals(MembershipTransport.Reason.PROTOCOL,failure(first.exchange(group.identities.get(1),request,"STATUS",deadline())).reason);
            mode.set(1);assertEquals("REJECT",first.exchange(group.identities.get(1),request,"STATUS",deadline()).get(5,TimeUnit.SECONDS).kind());
            first.close();mode.set(2);
            var small=group.start(0,group::status,MembershipTransport.Events.NONE,bounds(2,5000,request.size()),resources(MembershipResources.QUEUE_LIMIT));
            assertTrue(group.status(group.identities.getFirst(),request).size()>request.size());
            assertEquals(MembershipTransport.Reason.PROTOCOL,failure(small.exchange(group.identities.get(1),request,"STATUS",deadline())).reason);
        }
    }
}
