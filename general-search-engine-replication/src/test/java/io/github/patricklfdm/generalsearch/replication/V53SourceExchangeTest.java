package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

class V53SourceExchangeTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(60);
    static MembershipResources resources(){return new MembershipResources(512*MIB);}
    static ReplicationBounds bounds(){return V53MembershipTransportTest.bounds(2,10000,FRAME);}
    final class Local implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture fixture;
        final MembershipGrantJournal owner;
        final MembershipSelection.Source original;
        final MembershipSourceExport export;
        final MembershipIdentity reader;
        final MembershipResources receiving=resources();
        final AtomicLong clock=new AtomicLong();
        final UUID trace=UUID.randomUUID();
        final MembershipSourceSession server;
        Local()throws Exception {this(3,1024,FRAME);}
        Local(int size,int chunk,int frame)throws Exception {
            Path root=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
            fixture=new V53BootstrapPublicationTest.Fixture(root,Files.createDirectory(root.resolve("raw")),size,false);
            owner=fixture.open(fixture.request.targets().getFirst(),"exchange");original=owner.beginActivation();
            export=owner.exportSource(original.basis,BUDGET);reader=fixture.request.targets().get(1).identity();
            server=new MembershipSourceSession(export,reader,trace,fixture.resources,chunk,frame,clock::get,0,BUDGET);
        }
        CompletableFuture<Decoded> deliver(MembershipIdentity peer,Decoded request,String kind,long deadline) {
            assertEquals(original.owner,peer);assertEquals(BUDGET,deadline);
            try{return CompletableFuture.completedFuture(server.handle(reader,request));}
            catch(Throwable error){return CompletableFuture.failedFuture(error);}
        }
        MembershipSourcePull client(MembershipSourcePull.Link link,MembershipSourcePull.Guard guard) {
            return new MembershipSourcePull(original.capsule,reader,original.owner,object(original.basis.value().get("ballot")),trace,
                    receiving,bounds(),link,guard,clock::get,0,BUDGET);
        }
        @Override public void close()throws Exception {server.close();owner.close();assertEquals(0,fixture.resources.usage().leases());assertEquals(0,receiving.usage().leases());}
    }
    static MembershipTransport.Failure lost(){return new MembershipTransport.Failure(MembershipTransport.Reason.IO,"injected lost response",null);}
    static Decoded change(Decoded frame,Map<String,Object> fields){return decode(encode("wire",frame.kind(),fields),"wire",frame.kind());}
    @Test void realTcpFetchesOriginalRecordsPacketAndImagesAtEveryStableSize()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-source-exchange/run-"+UUID.randomUUID()));
        System.out.println("v53SourceExchangeEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));var helper=new V53MembershipTransportTest();helper.temp=temp;
            try(var group=helper.new Group(size,raw)) {
                var f=group.fixture;var receiving=resources();var wire=new ArrayList<Map<String,Object>>();
                try(var owner=f.open(f.request.targets().getFirst(),"tcp-source")) {
                    var original=owner.beginActivation();var trace=UUID.randomUUID();long start=System.nanoTime();
                    var export=owner.exportSource(original.basis,BUDGET);var reader=group.identities.get(1);
                    Path captured=Files.createDirectory(raw.resolve("captured"));for(var member:f.request.targets())V53JournalApplicationTest.copy(member.replicaDirectory(),captured.resolve(member.identity().nodeId().value()));
                    var rows=new ArrayList<Map<String,Object>>();Path output=Files.createDirectory(raw.resolve("exported"));
                    for(var content:export.contents()){Files.write(output.resolve(content.digest()+".bin"),V53SourceExportTest.complete(export,content));rows.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));}
                    Files.write(raw.resolve("contents.json"),ReplicaJson.encode(rows,65536));
                    try(var server=new MembershipSourceSession(export,reader,trace,f.resources,1024,FRAME,System::nanoTime,start,BUDGET)) {
                        group.start(0,server,MembershipTransport.Events.NONE,bounds(),f.resources);
                        var transport=group.start(1,group::status,MembershipTransport.Events.NONE,bounds(),receiving);
                        MembershipSourcePull.Link link=(peer,request,kind,deadline)->transport.exchange(peer,request,kind,deadline).thenApply(reply->{
                            wire.add(Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(reply.bytes())));return reply;});
                        Path scratch=temp.resolve("tcp-scratch-"+size);
                        try(var client=new MembershipSourcePull(original.capsule,reader,original.owner,object(original.basis.value().get("ballot")),trace,
                                receiving,bounds(),link,()->{},System::nanoTime,start,BUDGET)) {
                            var received=client.fetch(scratch,original.basis.digest());assertArrayEquals(original.basis.bytes(),received.basis().bytes());
                            assertArrayEquals(original.capsule.packet.bytes(),received.packet().bytes());received.packet().verifyImages(received.images());
                            V53JournalApplicationTest.copy(scratch,raw.resolve("received"));
                        }
                        assertFalse(Files.exists(scratch));assertEquals(0,receiving.usage().counts().getOrDefault(Unit.SOURCE,0));
                    }
                }
                // Stop the TCP servers before asserting the owner's full resource baseline.
                for(var transport:group.transports)transport.close();
                f.snapshot("after");Files.write(raw.resolve("wire.json"),ReplicaJson.encode(wire,16*1024*1024));cases.add(Map.of("size",size,"exchanges",wire.size()));
            }
        }
        Files.write(evidence.resolve("receipt.json"),ReplicaJson.encode(Map.of("schema","gse-v53-source-exchange-v1","status","PASS","cases",cases,
                "publicRuntime",false,"network",true,"scope","complete-original-source-delivery"),65536));
    }
    @Test void lostOfferDataAndCommitRepliesRepeatOnlyIdenticalRequests()throws Exception {
        for(String kind:List.of("SOURCE_OFFER","CHUNK","TRANSFER_COMMIT"))try(var f=new Local()) {
            var dropped=new AtomicBoolean();var requestDigest=new AtomicReference<String>();var repeats=new AtomicInteger();
            MembershipSourcePull.Link link=(peer,request,expected,deadline)->{
                var response=f.deliver(peer,request,expected,deadline);
                if(expected.equals(kind) && dropped.compareAndSet(false,true)){requestDigest.set(request.digest());return CompletableFuture.failedFuture(lost());}
                if(request.digest().equals(requestDigest.get()))repeats.incrementAndGet();return response;
            };
            try(var client=f.client(link,()->{})){var received=client.fetch(temp.resolve("lost-"+kind),f.original.basis.digest());received.packet().verifyImages(received.images());}
            assertTrue(dropped.get());assertEquals(1,repeats.get());
        }
    }
    @Test void threeLostRepliesExhaustOneRequestAndNeverCreateScratch()throws Exception {
        try(var f=new Local()) {
            var requests=new ArrayList<String>();Path scratch=temp.resolve("scratch");
            try(var client=f.client((peer,request,kind,deadline)->{requests.add(request.digest());f.deliver(peer,request,kind,deadline).join();return CompletableFuture.failedFuture(lost());},()->{})) {
                assertThrows(MembershipTransport.Failure.class,()->client.fetch(scratch,f.original.basis.digest()));
            }
            assertEquals(3,requests.size());assertEquals(1,new HashSet<>(requests).size());assertFalse(Files.exists(scratch));
        }
    }
    @Test void protocolCapacityClosedAndExplicitRejectAreNotRetried()throws Exception {
        for(var reason:List.of(MembershipTransport.Reason.PROTOCOL,MembershipTransport.Reason.CAPACITY,MembershipTransport.Reason.CLOSED))try(var f=new Local()) {
            var calls=new AtomicInteger();
            try(var client=f.client((peer,request,kind,deadline)->{calls.incrementAndGet();return CompletableFuture.failedFuture(new MembershipTransport.Failure(reason,"injected",null));},()->{})) {
                assertThrows(MembershipTransport.Failure.class,()->client.fetch(temp.resolve(reason.name()),f.original.basis.digest()));
            }
            assertEquals(1,calls.get());
        }
        try(var f=new Local()) {
            var calls=new AtomicInteger();var observed=new AtomicReference<Decoded>();
            try(var client=f.client((peer,request,kind,deadline)->{
                calls.incrementAndGet();var reply=V53ActivationTest.response(request,"REJECT",Map.of("promised",f.original.basis.value().get("ballot"),"reason","NOT_READY"));observed.set(reply);return CompletableFuture.completedFuture(reply);
            },()->{})) {
                var error=assertThrows(MembershipSourcePull.Rejected.class,()->client.fetch(temp.resolve("reject"),f.original.basis.digest()));assertArrayEquals(observed.get().bytes(),error.response.bytes());
            }
            assertEquals(1,calls.get());
        }
    }
    @Test void changedOffersDataAndCorrelationRejectBeforeInstallingAnything()throws Exception {
        for(String fault:List.of("offer-id","offer-digest","offer-kind","oversized-record","data-id","data-offset","data-digest","trace"))try(var f=new Local()) {
            var changed=new AtomicBoolean();Path scratch=temp.resolve(fault);
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->f.deliver(peer,request,kind,deadline).thenApply(reply->{
                boolean target=fault.startsWith("data")?kind.equals("CHUNK"):kind.equals("SOURCE_OFFER");if(!target || !changed.compareAndSet(false,true))return reply;
                var fields=new TreeMap<>(reply.value());var payload=new TreeMap<>(object(fields.get("payload")));
                switch(fault) {
                    case "offer-id","data-id"->payload.put("id",UUID.randomUUID().toString());
                    case "offer-digest","data-digest"->payload.put("digest","01".repeat(32));
                    case "offer-kind"->payload.put("kind","APPLICATION");
                    case "oversized-record"->payload.put("bytes",16385L);
                    case "data-offset"->payload.put("offset",99L);
                    case "trace"->fields.put("trace",UUID.randomUUID().toString());
                }
                fields.put("payload",payload);return change(reply,fields);
            });
            try(var client=f.client(link,()->{})){assertThrows(RuntimeException.class,()->client.fetch(scratch,f.original.basis.digest()));}
            assertTrue(changed.get());assertFalse(Files.exists(scratch));assertEquals(0,f.receiving.usage().leases());
        }
    }
    @Test void deadlineAndLiveFencingGuardCoverRepliesAndCannotRestartThePull()throws Exception {
        for(boolean expiry:List.of(false,true))try(var f=new Local()) {
            var failed=new AtomicBoolean();var calls=new AtomicInteger();
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                calls.incrementAndGet();var response=f.deliver(peer,request,kind,deadline);failed.set(true);if(expiry)f.clock.set(BUDGET);return response;
            };
            try(var client=f.client(link,()->{if(!expiry && failed.get())throw new IOException("higher ballot fence");})) {
                assertThrows(Exception.class,()->client.fetch(temp.resolve("deadline-"+expiry),f.original.basis.digest()));f.clock.set(0);
                assertThrows(IllegalArgumentException.class,()->client.fetch(temp.resolve("again-"+expiry),f.original.basis.digest()));
            }
            assertEquals(1,calls.get());
        }
    }
    @Test void cancellationInterruptsPendingIoAndReleasesItsRecordReservation()throws Exception {
        try(var f=new Local()) {
            var pending=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);var client=f.client((peer,request,kind,deadline)->{entered.countDown();return pending;},()->{});
            var result=new CompletableFuture<Throwable>();var thread=Thread.ofVirtual().start(()->{try{client.fetch(temp.resolve("cancel"),f.original.basis.digest());result.complete(null);}catch(Throwable error){result.complete(error);}});
            assertTrue(entered.await(5,TimeUnit.SECONDS));client.close();assertInstanceOf(IOException.class,result.get(5,TimeUnit.SECONDS));thread.join(5000);
            assertFalse(thread.isAlive());assertTrue(pending.isCancelled());assertEquals(0,f.receiving.usage().leases());
        }
    }
    @Test void sourceRejectsChangedDuplicateAndExpiredSessionWithoutReturningCachedBytes()throws Exception {
        for(boolean expiry:List.of(false,true))try(var f=new Local()) {
            var requests=new ArrayList<Decoded>();
            try(var client=f.client((peer,request,kind,deadline)->{requests.add(request);return f.deliver(peer,request,kind,deadline);},()->{})) {
                client.fetch(temp.resolve("complete-"+expiry),f.original.basis.digest());
                var last=requests.getLast();
                if(expiry)f.clock.set(BUDGET);
                else {var fields=new TreeMap<>(last.value());var p=new TreeMap<>(object(fields.get("payload")));p.put("digest","02".repeat(32));fields.put("payload",p);last=change(last,fields);}
                var invalid=last;assertThrows(IllegalArgumentException.class,()->f.server.handle(f.reader,invalid));
                f.clock.set(0);assertThrows(IllegalArgumentException.class,()->f.server.handle(f.reader,requests.getLast()));
            }
        }
    }
    @Test void completedTransferIdentityCannotBeReusedForAnotherMember()throws Exception {
        try(var f=new Local()) {
            var first=new AtomicReference<String>();var offers=new AtomicInteger();var rejected=new AtomicBoolean();
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                if(kind.equals("SOURCE_OFFER")) {
                    int n=offers.incrementAndGet();if(n==1)first.set((String)object(request.value().get("payload")).get("id"));
                    if(n==3) {
                        var fields=new TreeMap<>(request.value());var p=new TreeMap<>(object(fields.get("payload")));p.put("id",first.get());fields.put("payload",p);var reused=change(request,fields);
                        var error=assertThrows(IllegalArgumentException.class,()->f.server.handle(f.reader,reused));rejected.set(true);return CompletableFuture.failedFuture(error);
                    }
                }
                return f.deliver(peer,request,kind,deadline);
            };
            try(var client=f.client(link,()->{})){assertThrows(IllegalArgumentException.class,()->client.fetch(temp.resolve("reuse"),f.original.basis.digest()));}
            assertTrue(rejected.get());
        }
    }
    @Test void lostPacketChunksExhaustAtThreeAndRemovePartialFiles()throws Exception {
        try(var f=new Local()) {
            var packet=new AtomicBoolean();var failures=new ArrayList<String>();Path scratch=temp.resolve("partial");var before=V53ReplayFilesTest.files(f.fixture.request.targets().getFirst().replicaDirectory());
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                var reply=f.deliver(peer,request,kind,deadline);Decoded result=reply.join();
                if(kind.equals("SOURCE_OFFER") && object(result.value().get("payload")).get("kind").equals("CAPSULE"))packet.set(true);
                if(packet.get() && kind.equals("CHUNK")){assertTrue(Files.exists(scratch));failures.add(request.digest());return CompletableFuture.failedFuture(lost());}
                return reply;
            };
            try(var client=f.client(link,()->{})){assertThrows(MembershipTransport.Failure.class,()->client.fetch(scratch,f.original.basis.digest()));}
            assertEquals(3,failures.size());assertEquals(1,new HashSet<>(failures).size());assertFalse(Files.exists(scratch));
            assertEquals(0,f.receiving.usage().leases());assertEquals(before,V53ReplayFilesTest.files(f.fixture.request.targets().getFirst().replicaDirectory()));
        }
    }
    @Test void lateFenceAfterPacketForceAlsoDisposesPreallocatedImages()throws Exception {
        try(var f=new Local()) {
            var commits=new AtomicInteger();var fenced=new AtomicBoolean();Path scratch=temp.resolve("fenced");
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                var reply=f.deliver(peer,request,kind,deadline);
                if(kind.equals("TRANSFER_COMMIT") && commits.incrementAndGet()==3) {
                    assertTrue(Files.exists(scratch.resolve("source.gscp")));assertTrue(f.receiving.usage().counts().getOrDefault(Unit.APPLICATION,0)>0);fenced.set(true);
                }
                return reply;
            };
            try(var client=f.client(link,()->{if(fenced.get())throw new IOException("higher ballot after packet force");})) {
                assertThrows(IOException.class,()->client.fetch(scratch,f.original.basis.digest()));
            }
            assertTrue(fenced.get());assertFalse(Files.exists(scratch));assertEquals(0,f.receiving.usage().leases());
        }
    }
    @Test void serverAccountsItsReplyCacheAndRejectsWhenTheGlobalQueueIsFull()throws Exception {
        try(var f=new Local()) {
            var leases=new ArrayList<MembershipResources.Lease>();
            try {
                for(int n=0;f.fixture.resources.usage().queued()<QUEUE_LIMIT;n++)leases.add(f.fixture.resources.reserve(Unit.CONTROL,"queue-"+n,Math.min(Unit.CONTROL.bytes,QUEUE_LIMIT-f.fixture.resources.usage().queued())));
                var calls=new AtomicInteger();
                try(var client=f.client((peer,request,kind,deadline)->{calls.incrementAndGet();return f.deliver(peer,request,kind,deadline);},()->{})) {
                    assertThrows(IllegalArgumentException.class,()->client.fetch(temp.resolve("full"),f.original.basis.digest()));
                }
                assertEquals(1,calls.get());assertFalse(Files.exists(temp.resolve("full")));
            }finally{leases.forEach(MembershipResources.Lease::close);}
        }
    }
    @Test void senderFitsBase64DataAndHeadersInsideTheCallerFrameBound()throws Exception {
        try(var f=new Local(5,4*1024*1024,4096)) {
            var largest=new AtomicInteger();var bound=V53MembershipTransportTest.bounds(2,10000,4096);
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->f.deliver(peer,request,kind,deadline).thenApply(reply->{
                assertTrue(reply.size()<=4096);if(kind.equals("CHUNK"))largest.accumulateAndGet(Base64.getDecoder().decode((String)object(reply.value().get("payload")).get("bytes")).length,Math::max);return reply;});
            try(var client=new MembershipSourcePull(f.original.capsule,f.reader,f.original.owner,object(f.original.basis.value().get("ballot")),f.trace,
                    f.receiving,bound,link,()->{},f.clock::get,0,BUDGET)) {
                var received=client.fetch(temp.resolve("bounded"),f.original.basis.digest());received.packet().verifyImages(received.images());
            }
            assertTrue(largest.get()>1024);assertTrue(largest.get()<f.original.capsule.packet.bytes().length);
        }
    }
    @Test void smallerCallerRetryLimitIsPreserved()throws Exception {
        try(var f=new Local()) {
            var b=bounds();var bound=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),1,
                    b.requestTimeoutMillis(),b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());var calls=new AtomicInteger();
            try(var client=new MembershipSourcePull(f.original.capsule,f.reader,f.original.owner,object(f.original.basis.value().get("ballot")),f.trace,
                    f.receiving,bound,(peer,request,kind,deadline)->{calls.incrementAndGet();return CompletableFuture.failedFuture(lost());},()->{},f.clock::get,0,BUDGET)) {
                assertThrows(MembershipTransport.Failure.class,()->client.fetch(temp.resolve("one-attempt"),f.original.basis.digest()));
            }
            assertEquals(1,calls.get());
        }
    }
}
