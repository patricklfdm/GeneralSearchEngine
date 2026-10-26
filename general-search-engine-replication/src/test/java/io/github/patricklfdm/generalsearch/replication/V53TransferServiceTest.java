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
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53TransferServiceTest {
    @TempDir Path temp;
    static ReplicationBounds bound(int inFlight) {
        var b=bounds();return new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),inFlight,b.maxPendingClientOperations(),b.maxRetryAttempts(),b.requestTimeoutMillis(),b.retryBackoffMillis(),1024,b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
    }
    static Map<String,Object> observed(MembershipTransferService.Usage usage) {
        return Map.of("traces",usage.traces(),"live",usage.live(),"calls",usage.calls(),"closed",usage.closed());
    }
    final class Local implements AutoCloseable {
        final V53RecordExchangeTest.Local f;
        final Map<String,Object> ballot;
        final AtomicBoolean fenced=new AtomicBoolean();
        final MembershipTransferService service;
        Local()throws Exception {this(2,MembershipTransport.Events.NONE);}
        Local(int concurrent,MembershipTransport.Events events)throws Exception {
            var helper=new V53RecordExchangeTest();helper.temp=temp;f=helper.new Local();ballot=object(f.source.basis.value().get("ballot"));
            service=new MembershipTransferService(f.owner,ballot,f.fixture.resources,bound(concurrent),()->{if(fenced.get())throw new IOException("runtime fenced");},f.clock::get,0,BUDGET,events);
        }
        MembershipIdentity peer(int n){return f.fixture.request.targets().get(n-1).identity();}
        Decoded request(int reader,UUID trace,String digest) {
            return decode(encode("wire","CHUNK",Map.of("root",f.source.capsule.context.root,"view",f.source.capsule.context.authority(),"ballot",ballot,
                    "sender",MembershipBootstrapSeed.identity(peer(reader)),"recipient",MembershipBootstrapSeed.identity(peer(1)),"trace",trace.toString(),"sequence",1L,
                    "payload",Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,"digest",digest,"bytes",""))),"wire","CHUNK");
        }
        @Override public void close()throws Exception {service.close();assertEquals(new MembershipTransferService.Usage(0,0,0,true),service.usage());f.close();}
    }
    @Test void realTcpRoutesWholeSourceAndSeparateRecordWithoutPreRegisteredSessions()throws Exception {
        Path evidence=Files.createDirectories(Path.of("target/v53-transfer-service/run-"+UUID.randomUUID()));
        System.out.println("v53TransferServiceEvidence="+evidence.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5)) {
            Path raw=Files.createDirectory(evidence.resolve("stable-"+size));var helper=new V53MembershipTransportTest();helper.temp=temp;
            try(var group=helper.new Group(size,raw)) {
                var f=group.fixture;var receiving=resources();var records=resources();var wire=new ArrayList<Map<String,Object>>();var recordWire=new ArrayList<Map<String,Object>>();
                try(var owner=f.open(f.request.targets().getFirst(),"service-source")) {
                    var original=owner.beginActivation();var promise=owner.promised().orElseThrow();var ballot=object(original.basis.value().get("ballot"));long start=System.nanoTime();
                    Path captured=Files.createDirectory(raw.resolve("captured"));for(var member:f.request.targets())V53JournalApplicationTest.copy(member.replicaDirectory(),captured.resolve(member.identity().nodeId().value()));
                    var rows=new ArrayList<Map<String,Object>>();Path output=Files.createDirectory(raw.resolve("exported"));
                    try(var export=owner.exportSource(original.basis,BUDGET)) {
                        for(var content:export.contents()){Files.write(output.resolve(content.digest()+".bin"),V53SourceExportTest.complete(export,content));rows.add(Map.of("digest",content.digest(),"bytes",content.bytes(),"kind",content.kind().name()));}
                    }
                    Files.write(raw.resolve("contents.json"),ReplicaJson.encode(rows,65536));
                    var service=new MembershipTransferService(owner,ballot,f.resources,bound(2),()->owner.checkActivation(original.basis,null,false),System::nanoTime,start,BUDGET);
                    var lifetime=new TreeMap<String,Object>();
                    try(service) {
                        group.start(0,service,MembershipTransport.Events.NONE,bound(2),f.resources);
                        var transport=group.start(1,group::status,MembershipTransport.Events.NONE,bound(2),receiving);
                        var other=group.start(2,group::status,MembershipTransport.Events.NONE,bound(2),records);
                        MembershipSourcePull.Link link=(peer,request,kind,deadline)->transport.exchange(peer,request,kind,deadline).thenApply(reply->{
                            wire.add(Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(reply.bytes())));return reply;});
                        MembershipSourcePull.Link recordLink=(peer,request,kind,deadline)->other.exchange(peer,request,kind,deadline).thenApply(reply->{
                            recordWire.add(Map.of("request",Base64.getEncoder().encodeToString(request.bytes()),"response",Base64.getEncoder().encodeToString(reply.bytes())));return reply;});
                        Path scratch=temp.resolve("service-scratch-"+size);
                        try(var client=new MembershipSourcePull(original.capsule,group.identities.get(1),original.owner,ballot,UUID.randomUUID(),receiving,bound(2),link,()->{},System::nanoTime,start,BUDGET);
                            var recordClient=new MembershipSourcePull(original.capsule,group.identities.get(2),original.owner,ballot,UUID.randomUUID(),records,bound(2),recordLink,()->{},System::nanoTime,start,BUDGET)) {
                            var first=CompletableFuture.runAsync(()->{try{var received=client.fetch(scratch,original.basis.digest());received.packet().verifyImages(received.images());V53JournalApplicationTest.copy(scratch,raw.resolve("received"));}catch(Exception error){throw new CompletionException(error);}});
                            var second=CompletableFuture.runAsync(()->{try{var received=recordClient.fetchRecord(promise.digest(),"PROMISE",v->V53RecordExchangeTest.promise(v,original.capsule.context,ballot));Files.write(raw.resolve("record.gsr"),received.bytes());}catch(Exception error){throw new CompletionException(error);}});
                            CompletableFuture.allOf(first,second).get(40,TimeUnit.SECONDS);
                        }
                        assertFalse(Files.exists(scratch));assertEquals(new MembershipTransferService.Usage(2,2,0,false),service.usage());
                        lifetime.put("beforeClose",observed(service.usage()));
                    }
                    assertEquals(new MembershipTransferService.Usage(0,0,0,true),service.usage());
                    lifetime.put("afterClose",observed(service.usage()));Files.write(raw.resolve("lifetime.json"),canonical(lifetime,65536));
                }
                for(var transport:group.transports)transport.close();f.snapshot("after");
                Files.write(raw.resolve("wire.json"),ReplicaJson.encode(wire,16*1024*1024));Files.write(raw.resolve("record-wire.json"),canonical(recordWire,1024*1024));
                cases.add(Map.of("size",size,"sourceExchanges",wire.size(),"recordExchanges",recordWire.size()));
            }
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-transfer-service-v1","status","PASS","cases",cases,"publicRuntime",false,"network",true,"scope","runtime-scoped-transfer-dispatch"),65536));
    }
    @Test void exactDuplicatesKeepOneSessionWhileFailedTraceCannotReopen()throws Exception {
        try(var l=new Local()) {
            var request=l.request(2,UUID.randomUUID(),l.f.source.basis.digest());var offer=l.service.handle(l.peer(2),request);
            assertArrayEquals(offer.bytes(),l.service.handle(l.peer(2),request).bytes());assertEquals(new MembershipTransferService.Usage(1,1,0,false),l.service.usage());
            var changed=new TreeMap<>(request.value());var payload=new TreeMap<>(object(changed.get("payload")));payload.put("digest",l.f.owner.promised().orElseThrow().digest());changed.put("payload",payload);
            assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),change(request,changed)));
            assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),request));assertEquals(new MembershipTransferService.Usage(1,0,0,false),l.service.usage());
            var fresh=l.request(2,UUID.randomUUID(),l.f.owner.promised().orElseThrow().digest());assertEquals("SOURCE_OFFER",l.service.handle(l.peer(2),fresh).kind());
        }
    }
    @Test void unknownReferenceCreatesOnlyATombstoneAndChangedRetryCannotResample()throws Exception {
        try(var l=new Local()) {
            var request=l.request(2,UUID.randomUUID(),"0".repeat(64));var usage=l.f.fixture.resources.usage();
            assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),request));
            assertEquals(usage.queued()+1024,l.f.fixture.resources.usage().queued());assertEquals(new MembershipTransferService.Usage(1,0,0,false),l.service.usage());
            var changed=new TreeMap<>(request.value());var payload=new TreeMap<>(object(changed.get("payload")));payload.put("digest",l.f.owner.promised().orElseThrow().digest());changed.put("payload",payload);
            assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),change(request,changed)));
        }
    }
    @Test void wrongContextIdentitySequenceAndNonRequestDoNotAllocateTraces()throws Exception {
        try(var l=new Local()) {
            var request=l.request(2,UUID.randomUUID(),l.f.source.basis.digest());var before=l.f.fixture.resources.usage();
            var variants=new ArrayList<Map<String,Object>>();
            for(var entry:List.of(Map.entry("root",(Object)"a".repeat(64)),Map.entry("view",(Object)"b".repeat(64)),Map.entry("sequence",(Object)2L),Map.entry("recipient",(Object)MembershipBootstrapSeed.identity(l.peer(3))))) {var v=new TreeMap<>(request.value());v.put(entry.getKey(),entry.getValue());variants.add(v);}
            var v=new TreeMap<>(request.value());var ballot=new TreeMap<>(l.ballot);ballot.put("counter",number(ballot.get("counter"))+1);v.put("ballot",ballot);variants.add(v);
            for(var fields:variants)assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),change(request,fields)));
            var impostor=new MembershipIdentity(l.peer(2).nodeId(),UUID.randomUUID(),l.peer(2).endpoint());assertThrows(IllegalArgumentException.class,()->l.service.handle(impostor,request));
            var commitFields=new TreeMap<>(request.value());commitFields.put("payload",Map.of("id",UUID.randomUUID().toString(),"digest",l.f.source.basis.digest()));
            var commit=decode(encode("wire","TRANSFER_COMMIT",commitFields),"wire","TRANSFER_COMMIT");
            assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),commit));assertEquals(before,l.f.fixture.resources.usage());assertEquals(0,l.service.usage().traces());
        }
    }
    @Test void originalDeadlinePollAndFencingReleaseEverythingWithoutRevival()throws Exception {
        for(String reason:List.of("time","fence","close"))try(var l=new Local()) {
            var request=l.request(2,UUID.randomUUID(),l.f.source.basis.digest());l.service.handle(l.peer(2),request);
            if(reason.equals("time")){l.f.clock.set(BUDGET);assertFalse(l.service.poll());}
            else if(reason.equals("fence")){l.fenced.set(true);assertThrows(IOException.class,()->l.service.handle(l.peer(2),request));}
            else l.service.close();
            assertEquals(new MembershipTransferService.Usage(0,0,0,true),l.service.usage());assertEquals(0,l.f.fixture.resources.usage().queued());
            l.f.clock.set(0);l.fenced.set(false);assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),request));
        }
    }
    @Test void peerConcurrencyIsBoundedAndAnotherPeerProgressesWhileFirstIsDelayed()throws Exception {
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var delayed=new AtomicBoolean();
        try(var l=new Local(1,(event,request,response)->{if(event.equals("TRANSFER_ADMITTED") && delayed.compareAndSet(false,true)){entered.countDown();V53MembershipTransportTest.await(release);}})) {
            var request=l.request(2,UUID.randomUUID(),l.f.owner.promised().orElseThrow().digest());
            var first=CompletableFuture.supplyAsync(()->{try{return l.service.handle(l.peer(2),request);}catch(IOException error){throw new CompletionException(error);}});
            try {
                assertTrue(entered.await(5,TimeUnit.SECONDS));assertEquals(1,l.service.usage().calls());
                var excess=l.request(2,UUID.randomUUID(),l.f.owner.promised().orElseThrow().digest());
                assertEquals(MembershipTransport.Reason.CAPACITY,assertThrows(MembershipTransport.Failure.class,()->l.service.handle(l.peer(2),excess)).reason);
                assertEquals("SOURCE_OFFER",l.service.handle(l.peer(3),l.request(3,UUID.randomUUID(),l.f.owner.promised().orElseThrow().digest())).kind());
                assertEquals(2,l.service.usage().traces());
            }finally{release.countDown();}
            assertEquals("SOURCE_OFFER",first.get(5,TimeUnit.SECONDS).kind());assertEquals(0,l.service.usage().calls());
        }
    }
    @Test void sharedControlExhaustionRejectsBeforeTraceAndReturnsOnClose()throws Exception {
        try(var l=new Local()) {
            var held=new ArrayList<MembershipResources.Lease>();int existing=l.f.fixture.resources.usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0);
            try {
                for(int i=existing;i<256;i++)held.add(l.f.fixture.resources.reserve(MembershipResources.Unit.CONTROL,"filled-"+i,1));
                var full=l.f.fixture.resources.usage();var request=l.request(2,UUID.randomUUID(),l.f.source.basis.digest());
                assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),request));assertEquals(full,l.f.fixture.resources.usage());assertEquals(0,l.service.usage().traces());
            }finally{held.forEach(MembershipResources.Lease::close);}
            assertEquals("SOURCE_OFFER",l.service.handle(l.peer(2),l.request(2,UUID.randomUUID(),l.f.source.basis.digest())).kind());
        }
    }
    @Test void delayAfterAdmissionDoesNotRenewTheBudgetOrReturnALateReply()throws Exception {
        var expired=new AtomicBoolean();var holder=new AtomicReference<Local>();
        try(var l=new Local(2,(event,request,response)->{if(event.equals("TRANSFER_BEFORE_REPLY") && expired.compareAndSet(false,true))holder.get().f.clock.set(BUDGET);})) {
            holder.set(l);var request=l.request(2,UUID.randomUUID(),l.f.source.basis.digest());
            assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),request));assertEquals(new MembershipTransferService.Usage(0,0,0,true),l.service.usage());
        }
    }
    @Test void lostRepliesReuseTheAutomaticallyOpenedSessionAndExactRequest()throws Exception {
        try(var l=new Local()) {
            var trace=UUID.randomUUID();var dropped=new AtomicBoolean();var requests=new ArrayList<String>();
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                try{var reply=l.service.handle(l.peer(2),request);if(kind.equals("SOURCE_OFFER")){requests.add(request.digest());if(dropped.compareAndSet(false,true))return CompletableFuture.failedFuture(lost());}return CompletableFuture.completedFuture(reply);}
                catch(Exception error){return CompletableFuture.failedFuture(error);}};
            try(var pull=new MembershipSourcePull(l.f.source.capsule,l.peer(2),l.peer(1),l.ballot,trace,l.f.receiving,bound(2),link,()->{},l.f.clock::get,0,BUDGET)) {
                var promise=l.f.owner.promised().orElseThrow();assertArrayEquals(promise.bytes(),pull.fetchRecord(promise.digest(),"PROMISE",v->V53RecordExchangeTest.promise(v,l.f.source.capsule.context,l.ballot)).bytes());
            }
            assertEquals(2,requests.size());assertEquals(1,new HashSet<>(requests).size());assertEquals(1,l.service.usage().traces());
        }
    }
    @Test void closeDuringAdmittedRequestReleasesResourcesAndCannotReopenTheTrace()throws Exception {
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var l=new Local(2,(event,request,response)->{if(event.equals("TRANSFER_ADMITTED")){entered.countDown();V53MembershipTransportTest.await(release);}})) {
            var request=l.request(2,UUID.randomUUID(),l.f.source.basis.digest());
            var pending=CompletableFuture.runAsync(()->assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),request)));
            try {
                assertTrue(entered.await(5,TimeUnit.SECONDS));l.service.close();
                assertEquals(0,l.f.fixture.resources.usage().queued());assertEquals(new MembershipTransferService.Usage(0,0,1,true),l.service.usage());
            }finally{release.countDown();}
            pending.get(5,TimeUnit.SECONDS);assertEquals(new MembershipTransferService.Usage(0,0,0,true),l.service.usage());
            assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),request));
        }
    }
    @Test void allSevenOriginalKindsAreResolvedWithoutCallerSuppliedType()throws Exception {
        var fixture=new V53JournalApplicationTest();fixture.temp=temp;Path root=temp.resolve("votes");fixture.setup(root);
        var r=resources();var receiving=resources();var clock=new AtomicLong();
        try(var owner=fixture.open(root,1,r,e->{})) {
            var vote=MembershipPendingAccept.decode(Files.readAllBytes(fixture.f.f.node(root,1).resolve(MembershipPendingAccept.FILE)));
            var original=List.of(owner.originalBasis().orElseThrow(),vote.promise(),vote.selected(),vote.entry(),vote.accept(),vote.proof(),vote.certificate());
            var ballot=object(vote.accept().value().get("ballot"));var reader=V53DeclarationsTest.node(2);var kinds=new HashSet<String>();
            try(var service=new MembershipTransferService(owner,ballot,r,bound(2),()->{},clock::get,0,BUDGET)) {
                for(var record:original) {
                    try(var pull=new MembershipSourcePull(owner.floorCopyCurrent().capsule,reader,V53DeclarationsTest.node(1),ballot,UUID.randomUUID(),receiving,bound(2),
                        (peer,request,kind,deadline)->{try{return CompletableFuture.completedFuture(service.handle(reader,request));}catch(Exception error){return CompletableFuture.failedFuture(error);}},()->{},clock::get,0,BUDGET)) {
                        assertArrayEquals(record.bytes(),pull.fetchRecord(record.digest(),record.kind(),v->assertEquals(record.value(),v.value())).bytes());kinds.add(record.kind());
                    }
                    assertEquals(0,receiving.usage().leases());
                }
                assertEquals(MembershipRecordExport.KINDS,kinds);assertEquals(7,service.usage().traces());
            }
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void publishedPacketReferencesResolveAfterPendingVotesAreRetired()throws Exception {
        Path root=Files.createDirectory(temp.resolve("published"));var f=new V53BootstrapPublicationTest.Fixture(root,Files.createDirectory(root.resolve("raw")),3,false);
        f.campaign(1);f.publish(1,false);var clock=new AtomicLong();var receiving=resources();
        try(var owner=f.open(f.request.targets().getFirst(),"service-published");var service=new MembershipTransferService(owner,f.ballot,f.resources,bound(2),()->{},clock::get,0,BUDGET)) {
            assertTrue(owner.currentCertificate().isEmpty());var capsule=owner.floorCopyCurrent().capsule;var kinds=object(CATALOG.get("records"));int count=0;
            for(String digest:capsule.packet.objectNames()) {
                byte[] bytes=capsule.packet.objectBytes(digest);if(bytes.length<HEADER || java.nio.ByteBuffer.wrap(bytes).getInt()!=0x47534552)continue;
                int id=Short.toUnsignedInt(java.nio.ByteBuffer.wrap(bytes).getShort(8));
                String kind=kinds.entrySet().stream().filter(v->number(object(v.getValue()).get("id"))==id).map(Map.Entry::getKey).findFirst().orElseThrow();
                if(!MembershipRecordExport.KINDS.contains(kind) || kind.equals("BASIS"))continue;
                var reader=f.request.targets().get(1).identity();
                try(var pull=new MembershipSourcePull(capsule,reader,f.request.targets().getFirst().identity(),f.ballot,UUID.randomUUID(),receiving,bound(2),
                    (peer,request,wanted,deadline)->{try{return CompletableFuture.completedFuture(service.handle(reader,request));}catch(Exception error){return CompletableFuture.failedFuture(error);}},()->{},clock::get,0,BUDGET)) {
                    assertArrayEquals(bytes,pull.fetchRecord(digest,kind,v->assertEquals(capsule.context.root,v.value().get("root"))).bytes());count++;
                }
            }
            assertTrue(count>=2,"published packet retains actual original entry and proof records");
        }
        assertEquals(0,f.resources.usage().leases());assertEquals(0,receiving.usage().leases());
    }
}
