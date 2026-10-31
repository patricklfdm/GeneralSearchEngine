package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.function.Consumer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53LearnerHeadProtocolTest {
    @TempDir Path temp;
    static Decoded changed(Decoded original,Consumer<Map<String,Object>> mutation) {
        var value=object(V53ContextFixture.mutable(original.value()));mutation.accept(value);
        return decode(encode("wire",original.kind(),value),"wire",original.kind());
    }
    static Decoded query(MembershipLearnerHead head,MembershipIdentity voter)throws IOException {
        var original=head.request();return decode(encode("wire","LEARNER_HEAD_QUERY",Map.of(
                "root",original.root().manifestDigest(),"view",original.change().expectedConfigurationDigest(),
                "sender",MembershipPeerRetentionPlan.identity(voter),"recipient",MembershipPeerRetentionPlan.identity(original.identity()),
                "ballot",MembershipLearnerDiscovery.correlation(original.identity()),"trace",UUID.randomUUID().toString(),"sequence",1L,
                "payload",Map.of("request",MembershipLearnerDiscovery.request(original.change())))),"wire","LEARNER_HEAD_QUERY");
    }
    @Test void rejectedHeadQueryForwardsTheOriginalTransportTerminal()throws Exception {
        var helper=new V53LearnerMaterializationTest();helper.temp=temp;
        try(var f=helper.new Fixture();var typed=f.prepare(e->{})) {
            var head=typed.retainGeneration();var voter=f.source.owner.activationIdentity();
            var request=changed(query(head,voter),v->v.put("sequence",2L));
            var seen=new CompletableFuture<MembershipTransport.Reason>();
            var observer=new MembershipTransport.Events() {
                @Override public void at(String event,Decoded q,Decoded a) {}
                @Override public void failed(boolean outbound,Decoded q,MembershipTransport.Reason reason) {
                    assertFalse(outbound);assertArrayEquals(request.bytes(),q.bytes());seen.complete(reason);
                }
            };
            var before=V53ReplayFilesTest.files(f.base);
            try(var server=new MembershipLearnerHeadEndpoint(head,V53SourceExchangeTest.bounds(),observer);
                var client=new MembershipTransport(head.source(),voter,V53SourceExchangeTest.bounds(),f.source.server,
                        (p,q)->{throw new IOException("read-only test contact");},MembershipTransport.Events.NONE)) {
                var failure=assertThrows(ExecutionException.class,()->client.exchange(head.request().identity(),request,"LEARNER_HEAD_ACK",
                        System.nanoTime()+TimeUnit.SECONDS.toNanos(10)).get(15,TimeUnit.SECONDS));
                assertEquals(MembershipTransport.Reason.IO,((MembershipTransport.Failure)failure.getCause()).reason);
                assertEquals(MembershipTransport.Reason.PROTOCOL,seen.get(5,TimeUnit.SECONDS));
            }
            assertEquals(before,V53ReplayFilesTest.files(f.base));
        }
    }
    @Test void endpointRequiresForcedHeadExactVoterAndRequestWithoutWritingOrVoting()throws Exception {
        var helper=new V53LearnerMaterializationTest();helper.temp=temp;
        try(var f=helper.new Fixture();var typed=f.prepare(e->{})) {
            var head=typed.retainGeneration();var baseline=f.source.client.usage();
            var before=V53ReplayFilesTest.files(f.base);
            try(var server=new MembershipLearnerHeadEndpoint(head,V53SourceExchangeTest.bounds(),MembershipTransport.Events.NONE)) {
                assertEquals(baseline.queued()+MembershipLearnerHeadObservation.BYTES,f.source.client.usage().queued());
                var voter=f.source.owner.activationIdentity();var request=query(head,voter);var reply=server.answer(voter,request);
                MembershipWire.correlated(request,reply,"LEARNER_HEAD_ACK");
                assertEquals(MembershipRetentionIntent.anchor(head.source().terminal()),object(reply.value().get("payload")).get("endpoint"));
                var negatives=List.<Consumer<Map<String,Object>>>of(
                        v->v.put("root","ab".repeat(32)),v->v.put("view","ab".repeat(32)),v->v.put("sequence",2L),
                        v->object(v.get("ballot")).put("counter",2L),
                        v->object(v.get("sender")).put("storage",UUID.randomUUID().toString()),
                        v->object(object(v.get("payload")).get("request")).put("number",2L),
                        v->object(object(v.get("payload")).get("request")).put("expected","ab".repeat(32)));
                for(var mutation:negatives)assertThrows(IllegalArgumentException.class,()->server.answer(voter,changed(request,mutation)));
                var self=query(head,head.request().identity());assertThrows(IllegalArgumentException.class,()->server.answer(head.request().identity(),self));
                var vote=new TreeMap<>(request.value());vote.put("payload",Map.of("promise","ab".repeat(32)));
                assertThrows(IllegalArgumentException.class,()->server.answer(voter,decode(encode("wire","PREPARE",vote),"wire","PREPARE")));
                assertEquals(before,V53ReplayFilesTest.files(f.base));
                typed.close();assertThrows(IllegalArgumentException.class,()->server.answer(voter,request));
                server.close();assertEquals(baseline,f.source.client.usage());
            }
        }
    }
    @Test void nativeProbeRetriesOnlyExactTransientQueriesAndNeverDischargesTheLedger()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;var network=new V53NativeDispatchTest();network.temp=temp;
        long budget=TimeUnit.SECONDS.toNanos(600);
        try(var n=network.new Network(3,helper.controlBounds(),budget,f->{
            for(var target:f.request.targets())try(var owner=f.open(target,"initialize-learner-retention")){owner.initializeLearnerRetention();}
        },true);var round=helper.driver(n,MembershipRoundDriver.Events.NONE,budget)) {
            System.out.println("v53LearnerHeadProtocolEvidence="+n.f.raw.toAbsolutePath());round.start();
            int port;try(var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
            var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
            var targets=new ArrayList<MembershipIdentity>();n.f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
            var owner=n.owners.getFirst();var pool=n.resources.getFirst();
            var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),owner.activationContext().authority(),MembershipChangeKind.ADD,targets);
            var request=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("replica"),temp.resolve("operation"));
            round.submit("RESERVE",canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192));
            var unbound=pool.usage();assertThrows(IllegalArgumentException.class,()->new MembershipLearnerHeadProbe(owner,joining,pool,n.bounds,
                    n.transports.getFirst()::exchange,System::nanoTime,System.nanoTime(),budget));assertEquals(unbound,pool.usage());
            try(var recording=new MembershipLearnerRetentionQuorum(owner,joining,n.ballot,pool,n.transports.getFirst()::exchange,
                    System::nanoTime,System.nanoTime(),budget)){recording.run();}
            round.submit("PREPARE",canonical(Map.of("number",1L,"revision",1L),8192));
            var resources=new MembershipResources(512*MembershipResources.MIB);
            var config=new MembershipReplicaConfig<>(request.root(),joining,List.of(),request.replicaDirectory(),storage(temp.resolve("core"),2),
                    n.bounds,AutomaticLeadershipPolicy.forBounds(n.bounds));
            try(var source=new MembershipLearnerSource(request,targets.getFirst(),resources,n.bounds,MembershipTransport.Events.NONE,
                    ()->{},System::nanoTime,System.nanoTime(),budget)) {
                source.fetch(temp.resolve("receiving"));var summary=source.plan(e->{});
                try(var store=source.admit(summary,e->{})) {
                    source.close();
                    try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store,1),builder().configuration(),config,e->{})) {
                        var head=typed.retainGeneration();var wires=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
                        var suppress=new AtomicBoolean(true);
                        try(var server=new MembershipLearnerHeadEndpoint(head,n.bounds,(event,q,a)->{
                            if(event.equals("BEFORE_RESPONSE_WRITE")) {
                                wires.add(V53SelectedPullTest.wire(q,a));
                                if(suppress.compareAndSet(true,false))throw new IOException("lost real head acknowledgement");
                            }
                        })) {
                            var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
                            var ledger=owner.learnerRetentionState();var baseline=pool.usage();n.f.snapshot("before-head-query");
                            V53JournalApplicationTest.copy(request.operationDirectory(),n.f.raw.resolve("learner-head-originals"));
                            Files.write(n.f.raw.resolve("learner-head-original-paths.json"),canonical(Map.of(
                                    "operationDirectory",request.operationDirectory().toString(),"replicaDirectory",request.replicaDirectory().toString(),
                                    "typedDirectory",MembershipLearnerMaterialization.directory(summary).toString()),8192));
                            assertEquals(List.of(2L,3L),ledger.plan().recorded().stream().map(a->number(a.cut().get("index"))).toList());
                            var sent=new ArrayList<String>();var deadlines=new HashSet<Long>();
                            try(var probe=new MembershipLearnerHeadProbe(owner,joining,pool,n.bounds,(p,q,k,d)->{
                                sent.add(q.digest());deadlines.add(d);return n.transports.getFirst().exchange(p,q,k,d);
                            },System::nanoTime,System.nanoTime(),budget)) {
                                var result=probe.run();assertEquals(head.source().terminal(),result.endpoint());
                                assertEquals(2,sent.size());assertEquals(1,new HashSet<>(sent).size());assertEquals(1,deadlines.size());
                                probe.close();assertThrows(IllegalArgumentException.class,result::check);
                            }
                            assertEquals(baseline,pool.usage());
                            var occupied=new ArrayList<MembershipResources.Lease>();
                            try {
                                while(pool.usage().queued()<MembershipResources.QUEUE_LIMIT)
                                    occupied.add(pool.reserve(MembershipResources.Unit.CONTROL,"head-probe-pressure-"+occupied.size(),
                                            Math.min(MembershipResources.Unit.CONTROL.bytes,MembershipResources.QUEUE_LIMIT-pool.usage().queued())));
                                var full=pool.usage();assertThrows(IllegalArgumentException.class,()->new MembershipLearnerHeadProbe(owner,joining,pool,n.bounds,
                                        n.transports.getFirst()::exchange,System::nanoTime,System.nanoTime(),budget));assertEquals(full,pool.usage());
                            }finally {occupied.forEach(MembershipResources.Lease::close);}
                            for(var reason:MembershipTransport.Reason.values()) {
                                var calls=new AtomicInteger();
                                try(var probe=new MembershipLearnerHeadProbe(owner,joining,pool,n.bounds,(p,q,k,d)->{
                                    calls.incrementAndGet();return CompletableFuture.failedFuture(new MembershipTransport.Failure(reason,"injected",null));
                                },System::nanoTime,System.nanoTime(),budget)) {
                                    assertThrows(IOException.class,probe::run);
                                    assertEquals(reason==MembershipTransport.Reason.IO || reason==MembershipTransport.Reason.DEADLINE?3:1,calls.get());
                                }
                            }
                            var mutations=List.<Consumer<Map<String,Object>>>of(
                                    v->v.put("trace",UUID.randomUUID().toString()),v->v.put("root","ab".repeat(32)),
                                    v->v.put("sequence",2L),v->object(v.get("payload")).put("request","ab".repeat(32)),
                                    v->object(object(v.get("payload")).get("endpoint")).put("catalog","ab".repeat(32)));
                            for(var mutation:mutations) {
                                var calls=new AtomicInteger();
                                try(var probe=new MembershipLearnerHeadProbe(owner,joining,pool,n.bounds,(p,q,k,d)->{
                                    calls.incrementAndGet();return n.transports.getFirst().exchange(p,q,k,d).thenApply(a->changed(a,mutation));
                                },System::nanoTime,System.nanoTime(),budget)) {
                                    assertThrows(IllegalArgumentException.class,probe::run);assertEquals(1,calls.get());
                                }
                            }
                            var clock=new AtomicLong(System.nanoTime());long start=clock.get();
                            try(var probe=new MembershipLearnerHeadProbe(owner,joining,pool,n.bounds,(p,q,k,d)->n.transports.getFirst().exchange(p,q,k,d)
                                    .thenApply(a->{clock.set(start+budget);return a;}),clock::get,start,budget)) {
                                assertThrows(IllegalArgumentException.class,probe::run);
                            }
                            closeDuringSubmission(owner,joining,pool,n.bounds,budget);
                            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
                            assertEquals(ledger,owner.learnerRetentionState());assertEquals(baseline,pool.usage());
                            n.f.snapshot("after-head-query");
                            Files.write(n.f.raw.resolve("learner-head-wire.json"),canonical(wires,1024*1024));
                            // Actual native terminal publication invalidates the retained
                            // reservation, even though the typed head object still exists.
                            try(var probe=new MembershipLearnerHeadProbe(owner,joining,pool,n.bounds,n.transports.getFirst()::exchange,
                                    System::nanoTime,System.nanoTime(),budget)) {
                                var result=probe.run();round.submit("CANCEL",canonical(Map.of("number",1L),8192));
                                assertThrows(IllegalArgumentException.class,result::check);
                            }
                        }
                    }
                }
            }
            assertEquals(0,resources.usage().leases());
        }
    }
    private static void closeDuringSubmission(MembershipGrantJournal owner,MembershipIdentity joining,MembershipResources pool,
            ReplicationBounds bounds,long budget)throws Exception {
        var baseline=pool.usage();var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();
        try(var probe=new MembershipLearnerHeadProbe(owner,joining,pool,bounds,(p,q,k,d)->{
            entered.countDown();try{assertTrue(release.await(30,TimeUnit.SECONDS));}catch(InterruptedException e){throw new AssertionError(e);}return pending;
        },System::nanoTime,System.nanoTime(),budget);var executor=Executors.newSingleThreadExecutor()) {
            var result=executor.submit(()->assertThrows(IllegalArgumentException.class,probe::run));
            try {
                assertTrue(entered.await(30,TimeUnit.SECONDS));probe.close();
                assertEquals(baseline.queued()+MembershipLearnerHeadProbe.BYTES,pool.usage().queued(),"submission still holds query bytes");
            }finally{release.countDown();}
            result.get(30,TimeUnit.SECONDS);assertTrue(pending.isCancelled());assertEquals(baseline,pool.usage());
        }
    }
}
