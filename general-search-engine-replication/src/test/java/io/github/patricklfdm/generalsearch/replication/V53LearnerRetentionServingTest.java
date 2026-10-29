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
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53LearnerRetentionServingTest {
    @TempDir Path temp;
    V53LearnerRetentionQuorumTest.Group group()throws Exception {
        var helper=new V53LearnerRetentionQuorumTest();helper.temp=temp;return helper.new Group();
    }
    MembershipLearnerRequest learner(V53LearnerRetentionQuorumTest.Group g)throws Exception {
        var context=g.owners.getFirst().activationContext();var target=new ArrayList<MembershipIdentity>();
        g.f.request.targets().forEach(t->target.add(t.identity()));target.add(g.learner);
        return new MembershipLearnerRequest(g.f.result.root(),g.learner,
                new MembershipChangeRequest(new MembershipOperationId(g.f.result.root(),1),context.authority(),MembershipChangeKind.ADD,target),
                temp.resolve("absent-replica"),temp.resolve("absent-operation"));
    }
    Decoded request(V53LearnerRetentionQuorumTest.Group g,MembershipLearnerRequest learner,String scope)throws Exception {
        var owner=g.owners.getFirst();var context=owner.activationContext();
        return MembershipActivation.frame("CHUNK",context,g.learner,owner.activationIdentity(),MembershipLearnerDiscovery.correlation(g.learner),
                UUID.randomUUID(),1,Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,"bytes","",
                        "digest",MembershipLearnerPrefixExport.reference(learner,context.cut,scope)));
    }
    MembershipSourcePull.Link direct(V53LearnerRetentionQuorumTest.Group g) {
        return (peer,request,kind,deadline)->{
            try{return CompletableFuture.completedFuture(g.owners.get(Integer.parseInt(peer.nodeId().value().substring(5))-1)
                    .recordLearnerRetention(g.owners.getFirst().activationIdentity(),request));}
            catch(Exception error){return CompletableFuture.failedFuture(error);}
        };
    }
    @Test void actualTcpSourceSharesOneRecordedEndpointAcrossPrefixAndGeneration()throws Exception {
        try(var g=group()) {
            var endpoints=new ArrayList<MembershipActivationEndpoint>();var transports=new ArrayList<MembershipTransport>();
            var links=new ArrayList<AtomicReference<MembershipTransport>>();for(int i=0;i<3;i++)links.add(new AtomicReference<>());
            var dropped=new AtomicBoolean();var sends=new AtomicInteger();var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            var receiving=resources();var learner=learner(g);
            try {
                for(int i=0;i<3;i++) {
                    int node=i;MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                        if(node==0 && request.kind().equals("LEARNER_RETENTION_INTENT")) {
                            if(peer.nodeId().value().equals("node-3"))return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"offline",null));
                            sends.incrementAndGet();
                        }
                        return links.get(node).get().exchange(peer,request,kind,deadline);
                    };
                    var endpoint=new MembershipActivationEndpoint(g.owners.get(i),g.budgets.get(i),bounds(),link,List.of(),List.of(),
                            temp.resolve("endpoint-"+i),System::nanoTime,BUDGET);endpoints.add(endpoint);
                    var transport=new MembershipTransport(g.owners.get(i).activationCapsule(),g.owners.get(i).activationIdentity(),bounds(),g.budgets.get(i),endpoint,
                            (event,request,response)->{
                                if(event.equals("BEFORE_RESPONSE_WRITE")) {
                                    wire.add(V53SelectedPullTest.wire(request,response));
                                    if(node==1 && request.kind().equals("LEARNER_RETENTION_INTENT") && dropped.compareAndSet(false,true))throw new IOException("lost forced learner retention ACK");
                                    if(node==0 && response.kind().equals("SOURCE_OFFER") && !MembershipLearnerDiscovery.rootReference(g.owners.getFirst().activationContext(),g.learner,(String)object(request.value().get("payload")).get("digest"))) {
                                        assertEquals(1,g.owners.getFirst().learnerRetentionState().revision());
                                        assertEquals(1,g.owners.get(1).learnerRetentionState().revision());
                                    }
                                }
                            });transports.add(transport);links.get(i).set(transport);
                }
                try(var source=new MembershipLearnerSource(learner,g.owners.getFirst().activationIdentity(),receiving,bounds(),MembershipTransport.Events.NONE,
                        ()->{},System::nanoTime,System.nanoTime(),BUDGET)) {
                    var copy=source.fetch(temp.resolve("received"));var original=g.owners.getFirst().floorCopyCurrent();
                    assertEquals(original.fileNames(),copy.fileNames());var retained=Files.createDirectory(g.f.raw.resolve("served-copy"));
                    for(String file:original.fileNames()){assertArrayEquals(original.fileBytes(file),copy.fileBytes(file));Files.write(retained.resolve(file),copy.fileBytes(file));}
                    assertFalse(copy.capsule.context.voters().contains(g.learner.nodeId().value()));
                }
                assertEquals(0,receiving.usage().leases());assertEquals(2,sends.get());assertTrue(dropped.get());
                assertFalse(Files.exists(learner.replicaDirectory()));assertFalse(Files.exists(learner.operationDirectory()));
                assertEquals(0,g.owners.getLast().learnerRetentionState().revision());
                Files.write(g.f.raw.resolve("serving-result.json"),canonical(Map.of("status","PASS","phase3Complete",false,"nativeTcp",true,
                        "retentionAttempts",sends.get(),"lostAck",dropped.get(),"endpoint",3L),4096));
            }finally {
                for(var endpoint:endpoints)endpoint.close();for(var transport:transports)transport.close();
                Files.write(g.f.raw.resolve("serving-wire.json"),canonical(wire,16*1024*1024));
            }
        }
    }
    @Test void capabilityBindsOwnerReaderPoolAndRevokesLiveAndCompletedExports()throws Exception {
        try(var g=group()) {
            var owner=g.owners.getFirst();var pool=g.budgets.getFirst();var learner=learner(g);var first=request(g,learner,"generation");
            var baseline=pool.usage();var now=new AtomicLong(0);
            try(var round=g.round(direct(g),now::get,0)) {
                var recorded=round.run();
                assertThrows(IllegalArgumentException.class,()->new MembershipLearnerPrefixExport(owner,g.learner,first,pool,now::get,0,BUDGET));
                assertThrows(IllegalArgumentException.class,()->recorded.checkExport(g.owners.get(1),g.learner,pool));
                assertThrows(IllegalArgumentException.class,()->recorded.checkExport(owner,g.owners.get(1).activationIdentity(),pool));
                assertThrows(IllegalArgumentException.class,()->recorded.checkExport(owner,g.learner,resources()));
                try(var export=new MembershipLearnerPrefixExport(owner,g.learner,first,pool,now::get,0,BUDGET,false,recorded)) {
                    var content=export.references().values().iterator().next();assertTrue(export.read(content.digest(),0,1).length>0);
                    now.set(BUDGET);assertThrows(IllegalArgumentException.class,export::references);
                }
            }
            now.set(0);
            try(var round=g.round(direct(g),now::get,0)) {
                var recorded=round.run();try(var export=new MembershipLearnerPrefixExport(owner,g.learner,first,pool,now::get,0,BUDGET,false,recorded)) {
                    round.close();assertThrows(IllegalArgumentException.class,export::references);
                }
            }
            try(var service=MembershipTransferService.prefix(owner,pool,bounds(),()->{},now::get,0,BUDGET,direct(g))) {
                var contents=new TreeMap<String,MembershipSourceExport.Content>();
                try(var round=g.round(direct(g),now::get,0)) {
                    var recorded=round.run();try(var export=new MembershipLearnerPrefixExport(owner,g.learner,first,pool,now::get,0,BUDGET,false,recorded)) {
                        for(var content:export.references().values())contents.put(content.digest(),content);
                    }
                }
                Decoded last=null,reply=null;long sequence=0;
                // Fetch every distinct content through the production service,
                // then exercise its completed (session already closed) cache.
                var offer=service.handle(g.learner,first);String primary=(String)object(offer.value().get("payload")).get("digest");
                var ordered=new ArrayList<>(contents.values());ordered.sort(Comparator.comparing(c->!c.digest().equals(primary)));
                for(var content:ordered) {
                    var id=sequence==0?(String)object(first.value().get("payload")).get("id"):UUID.randomUUID().toString();
                    if(sequence==0){sequence=1;}else {
                        var fields=new TreeMap<>(first.value());fields.put("sequence",++sequence);fields.put("payload",Map.of("id",id,"action","REQUEST","offset",0L,"bytes","","digest",content.digest()));
                        service.handle(g.learner,decode(encode("wire","CHUNK",fields),"wire","CHUNK"));
                    }
                    long offset=0;
                    while(offset<content.bytes()) {
                        var fields=new TreeMap<>(first.value());fields.put("sequence",++sequence);fields.put("payload",Map.of("id",id,"action","REQUEST","offset",offset,"bytes","","digest",content.digest()));
                        reply=service.handle(g.learner,decode(encode("wire","CHUNK",fields),"wire","CHUNK"));
                        offset+=Base64.getDecoder().decode((String)object(reply.value().get("payload")).get("bytes")).length;
                    }
                    var fields=new TreeMap<>(first.value());fields.put("sequence",++sequence);fields.put("payload",Map.of("id",id,"digest",content.digest()));
                    last=decode(encode("wire","TRANSFER_COMMIT",fields),"wire","TRANSFER_COMMIT");reply=service.handle(g.learner,last);
                }
                assertEquals(0,service.usage().live());assertArrayEquals(reply.bytes(),service.handle(g.learner,last).bytes());
                var higher=new TreeMap<>(g.f.ballot);higher.put("counter",number(higher.get("counter"))+1);owner.observeCurrent(higher);
                var cached=last;assertThrows(IllegalArgumentException.class,()->service.handle(g.learner,cached));
            }
            assertEquals(baseline.queued(),pool.usage().queued());
        }
    }
    @Test void invalidAliasesDoNotRecordAndCloseCancelsSharedPendingQuorum()throws Exception {
        try(var g=group()) {
            var owner=g.owners.getFirst();var pool=g.budgets.getFirst();var learner=learner(g);var first=request(g,learner,"prefix");
            var before=pool.usage();var sent=new AtomicInteger();var entered=new CountDownLatch(2);var pending=new ArrayList<CompletableFuture<Decoded>>();
            MembershipSourcePull.Link stalled=(peer,request,kind,deadline)->{
                sent.incrementAndGet();var future=new CompletableFuture<Decoded>();synchronized(pending){pending.add(future);}entered.countDown();return future;
            };
            try(var obsolete=new MembershipLearnerRetentionServing(owner,g.f.original.seed.capsule.context,pool,
                    (peer,request,kind,deadline)->fail("obsolete source must not send an intent"),System::nanoTime,System.nanoTime(),BUDGET)) {
                assertEquals("learner serving original cut changed",assertThrows(IllegalArgumentException.class,()->obsolete.get(g.learner)).getMessage());
                assertEquals(0,owner.learnerRetentionState().revision());assertEquals(before.queued(),pool.usage().queued());
            }
            try(var service=MembershipTransferService.prefix(owner,pool,V53TransferServiceTest.bound(3),()->{},System::nanoTime,System.nanoTime(),BUDGET,stalled)) {
                for(String invalid:List.of("view","ballot","alias")) {
                    var fields=new TreeMap<>(first.value());fields.put("trace",UUID.randomUUID().toString());
                    if(invalid.equals("view"))fields.put("view","ff".repeat(32));
                    if(invalid.equals("ballot"))fields.put("ballot",g.f.ballot);
                    if(invalid.equals("alias")) {var payload=new TreeMap<>(object(fields.get("payload")));payload.put("digest",MembershipContext.cutDigest(owner.activationContext().cut));fields.put("payload",payload);}
                    var bad=decode(encode("wire","CHUNK",fields),"wire","CHUNK");assertThrows(IllegalArgumentException.class,()->service.handle(g.learner,bad));
                }
                assertEquals(0,owner.learnerRetentionState().revision());assertEquals(0,sent.get());
                var executor=Executors.newFixedThreadPool(3);
                try {
                    var task=executor.submit(()->assertThrows(Exception.class,()->service.handle(g.learner,first)));
                    assertTrue(entered.await(10,TimeUnit.SECONDS));
                    var duplicate=request(g,learner,"generation");var other=executor.submit(()->assertThrows(Exception.class,()->service.handle(g.learner,duplicate)));
                    long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(10);
                    while(service.usage().calls()!=2 && System.nanoTime()<deadline)Thread.sleep(10);
                    assertEquals(2,service.usage().calls(),"both entries must share the pending quorum before close");
                    var close=executor.submit(service::close);close.get(10,TimeUnit.SECONDS);task.get(10,TimeUnit.SECONDS);other.get(10,TimeUnit.SECONDS);
                    synchronized(pending){assertTrue(pending.stream().allMatch(CompletableFuture::isCancelled));}
                    assertEquals(2,sent.get());assertEquals(1,owner.learnerRetentionState().revision());
                    assertEquals(new MembershipTransferService.Usage(0,0,0,true),service.usage());
                }finally {executor.shutdownNow();assertTrue(executor.awaitTermination(10,TimeUnit.SECONDS));}
            }
            assertEquals(before.queued(),pool.usage().queued());
            var attempts=new AtomicInteger();MembershipSourcePull.Link unavailable=(peer,request,kind,deadline)->{
                attempts.incrementAndGet();return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"unavailable",null));
            };
            try(var service=MembershipTransferService.prefix(owner,pool,bounds(),()->{},System::nanoTime,System.nanoTime(),BUDGET,unavailable)) {
                for(String scope:List.of("prefix","generation")) {
                    var next=request(g,learner,scope);
                    assertEquals("learner retention quorum unavailable",assertThrows(IllegalArgumentException.class,()->service.handle(g.learner,next)).getMessage());
                    assertEquals(6,attempts.get(),"new trace cannot restart an exhausted quorum");
                }
            }
            assertEquals(before.queued(),pool.usage().queued());
        }
    }
}
