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

/** Actual native ADD reservation; no source export or learner eligibility is
 * inferred from the recording. Long all-profile/process qualification is separate. */
class V53LearnerRetentionQuorumTest {
    @TempDir Path temp;
    final class Group implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture f;
        final MembershipIdentity learner=V53DeclarationsTest.node(6);
        final List<MembershipGrantJournal> owners=new ArrayList<>();
        final List<MembershipResources> budgets=new ArrayList<>();
        final List<List<String>> events=new ArrayList<>();
        final List<AtomicReference<MembershipBallotAllocator.Cut>> hooks=new ArrayList<>();
        Group()throws Exception {
            Path raw=Files.createDirectories(Path.of("target/v53-learner-quorum/run-"+UUID.randomUUID()));
            System.out.println("v53LearnerQuorumEvidence="+raw.toAbsolutePath());
            f=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve("group-"+UUID.randomUUID())),3,false));
            f.ownedHistory=true;
            for(var target:f.request.targets())try(var owner=f.open(target,"initialize")){owner.initializePeerRetention();owner.initializeLearnerRetention();}
            var walk=new V53AdmittedCrossViewTest.Walk(f);walk.publish("BARRIER",null);
            var target=new ArrayList<MembershipIdentity>();f.request.targets().forEach(t->target.add(t.identity()));target.add(learner);
            walk.publish("RESERVE",Map.of("request",Map.of("root",f.result.root().manifestDigest(),"expected",walk.current().authority(),
                    "number",1L,"kind","ADD","target",target.stream().map(MembershipBootstrapSeed::identity).toList())));
            walk.publish("PREPARE",Map.of("number",1L,"revision",1L));f.snapshot("before-quorum");
            for(var t:f.request.targets()) {
                var pool=resources();budgets.add(pool);var trace=Collections.synchronizedList(new ArrayList<String>());events.add(trace);
                var hook=new AtomicReference<MembershipBallotAllocator.Cut>(e->{});hooks.add(hook);
                owners.add(MembershipGrantJournal.openRetainingLearners(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),pool,
                        MembershipGrantJournal.MAXIMUM,e->{trace.add(e);hook.get().at(e);}));
            }
        }
        MembershipLearnerRetentionQuorum round(MembershipSourcePull.Link link,java.util.function.LongSupplier clock,long start)throws Exception {
            return new MembershipLearnerRetentionQuorum(owners.getFirst(),learner,f.ballot,budgets.getFirst(),link,clock,start,BUDGET);
        }
        Decoded request(int recipient)throws Exception {
            var local=owners.getFirst();var intent=local.learnerRetentionIntent(learner,f.ballot);
            return MembershipActivation.frame("LEARNER_RETENTION_INTENT",local.activationContext(),local.activationIdentity(),owners.get(recipient).activationIdentity(),f.ballot,UUID.randomUUID(),1,intent.payload);
        }
        @Override public void close()throws Exception {
            for(var owner:owners)owner.close();for(var pool:budgets){assertEquals(0,pool.usage().leases());assertEquals(0,pool.usage().queued());}
            f.snapshot("after-quorum");Files.write(f.raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));
            Files.write(f.raw.resolve("events.json"),canonical(events,1024*1024));
        }
    }
    @Test void actualNetworkLostAckRecordsOneRevisionAndCannotEnableExport()throws Exception {
        try(var g=new Group()) {
            var endpoints=new ArrayList<MembershipActivationEndpoint>();var transports=new ArrayList<MembershipTransport>();
            var links=new ArrayList<AtomicReference<MembershipTransport>>();for(int i=0;i<3;i++)links.add(new AtomicReference<>());
            var dropped=new AtomicBoolean();var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            var sent=new TreeMap<String,List<String>>();
            try {
                for(int i=0;i<3;i++) {
                    int node=i;var endpoint=new MembershipActivationEndpoint(g.owners.get(i),g.budgets.get(i),bounds(),
                            (peer,request,kind,deadline)->links.get(node).get().exchange(peer,request,kind,deadline),List.of(),List.of(),
                            temp.resolve("endpoint-"+UUID.randomUUID()),System::nanoTime,BUDGET);endpoints.add(endpoint);
                    var transport=new MembershipTransport(g.owners.get(i).activationCapsule(),g.owners.get(i).activationIdentity(),bounds(),g.budgets.get(i),endpoint,
                            (event,request,response)->{if(event.equals("BEFORE_RESPONSE_WRITE")) {
                                wire.add(V53SelectedPullTest.wire(request,response));
                                if(node==1 && dropped.compareAndSet(false,true))throw new IOException("lost durable learner ACK");
                            }});transports.add(transport);links.get(i).set(transport);
                }
                MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                    sent.computeIfAbsent(peer.nodeId().value(),k->new ArrayList<>()).add(request.digest());
                    if(peer.nodeId().value().equals("node-3"))return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"offline",null));
                    return transports.getFirst().exchange(peer,request,kind,deadline);
                };
                MembershipLearnerRetentionQuorum.Recording recording;
                try(var round=g.round(link,System::nanoTime,System.nanoTime())) {
                    recording=round.run();recording.check();assertEquals(Set.of("node-1","node-2"),recording.voters());assertTrue(dropped.get());
                    assertEquals(2,sent.get("node-2").size());assertEquals(1,new HashSet<>(sent.get("node-2")).size());
                    for(var owner:g.owners.subList(0,2)) {
                        assertEquals(1,owner.learnerRetentionState().revision());
                        assertEquals(List.of(3L),owner.learnerRetentionState().plan().recorded().stream().map(a->number(a.cut().get("index"))).toList());
                        assertThrows(IllegalArgumentException.class,owner::checkLearnerRetentionExport);
                    }
                    assertEquals(0,g.owners.getLast().learnerRetentionState().revision());
                    Files.write(g.f.raw.resolve("network.json"),canonical(Map.of("voters",recording.voters().stream().sorted().toList(),
                            "intent",recording.intent(),"exportEnabled",false,"phase3Complete",false),16384));
                    var higher=new TreeMap<>(g.f.ballot);higher.put("counter",number(higher.get("counter"))+1);
                    g.owners.getFirst().observeCurrent(higher);assertThrows(IllegalArgumentException.class,recording::check);
                }
                assertThrows(IllegalArgumentException.class,recording::check);
            }finally {
                for(var endpoint:endpoints)endpoint.close();for(var transport:transports)transport.close();
                Files.write(g.f.raw.resolve("wire.json"),canonical(wire,1024*1024));
                Files.write(g.f.raw.resolve("requests.json"),canonical(sent.entrySet().stream()
                        .map(row->Map.of("node",row.getKey(),"digests",List.copyOf(row.getValue()))).toList(),65536));
            }
            var target=g.f.request.targets().get(1);g.owners.get(1).close();
            try(var owner=MembershipGrantJournal.openRetainingLearners(target.replicaDirectory(),target.materialization().directory(),g.f.result.root(),target.identity(),
                    g.budgets.get(1),MembershipGrantJournal.MAXIMUM,e->{})){assertEquals(1,owner.learnerRetentionState().revision());}
        }
    }
    @Test void failedMalformedExpiredAndClosedRoundsNeverReturnRecording()throws Exception {
        try(var g=new Group()) {
            var sent=new TreeMap<String,List<String>>();
            MembershipSourcePull.Link unavailable=(peer,request,kind,deadline)->{
                sent.computeIfAbsent(peer.nodeId().value(),k->new ArrayList<>()).add(request.digest());
                return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"offline",null));
            };
            try(var round=g.round(unavailable,System::nanoTime,System.nanoTime())) {
                assertEquals("learner retention quorum unavailable",assertThrows(IllegalArgumentException.class,round::run).getMessage());
            }
            for(var row:sent.values()){assertEquals(3,row.size());assertEquals(1,new HashSet<>(row).size());}
            for(boolean late:List.of(false,true)) {
                long start=System.nanoTime();var clock=new AtomicLong(start);
                MembershipSourcePull.Link bad=(peer,request,kind,deadline)->{
                    try {
                        var response=g.owners.get(Integer.parseInt(peer.nodeId().value().substring(5))-1).recordLearnerRetention(g.owners.getFirst().activationIdentity(),request);
                        if(late)clock.set(start+BUDGET);
                        else {var value=new TreeMap<>(response.value());var payload=new TreeMap<>(object(value.get("payload")));payload.put("intent","ff".repeat(32));value.put("payload",payload);response=decode(encode("wire","LEARNER_RETENTION_ACK",value),"wire","LEARNER_RETENTION_ACK");}
                        return CompletableFuture.completedFuture(response);
                    }catch(IOException error){return CompletableFuture.failedFuture(error);}
                };
                try(var round=g.round(bad,clock::get,start)){assertThrows(IllegalArgumentException.class,round::run);}
            }
            var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();
            MembershipSourcePull.Link blocked=(peer,request,kind,deadline)->{
                entered.countDown();try{if(!release.await(10,TimeUnit.SECONDS))throw new AssertionError("release missing");}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new CompletionException(error);}return pending;
            };
            var executor=Executors.newSingleThreadExecutor();
            try(var round=g.round(blocked,System::nanoTime,System.nanoTime())) {
                var task=executor.submit(()->assertThrows(IllegalArgumentException.class,round::run));assertTrue(entered.await(10,TimeUnit.SECONDS));
                round.close();release.countDown();task.get(10,TimeUnit.SECONDS);assertTrue(pending.isCancelled());
            }finally {release.countDown();executor.shutdownNow();assertTrue(executor.awaitTermination(10,TimeUnit.SECONDS));}
            for(var owner:g.owners)assertEquals(1,owner.learnerRetentionState().revision());
        }
    }
    @Test void exactNativeRequestsDuplicateForceAndHigherFence()throws Exception {
        try(var g=new Group()) {
            var local=g.owners.getFirst();var receiver=g.owners.get(1);var original=g.request(1);
            var before=V53ReplayFilesTest.files(g.f.request.targets().get(1).replicaDirectory());
            for(String field:List.of("root","selection","request","learner","endpoint","proposer")) {
                var value=new TreeMap<>(original.value());var payload=new TreeMap<>(object(value.get("payload")));
                switch(field) {
                    case "root"->value.put("root","ff".repeat(32));
                    case "selection"->payload.put("selection","ff".repeat(32));
                    case "request"->{var request=new TreeMap<>(object(payload.get("request")));request.put("number",2L);payload.put("request",request);}
                    case "learner"->{var identity=new TreeMap<>(object(payload.get("learner")));identity.put("storage",UUID.randomUUID().toString());payload.put("learner",identity);}
                    case "endpoint"->{var endpoint=new TreeMap<>(object(payload.get("endpoint")));endpoint.put("application","ff".repeat(32));payload.put("endpoint",endpoint);}
                    case "proposer"->{var ballot=new TreeMap<>(object(value.get("ballot")));ballot.put("proposer","node-3");value.put("ballot",ballot);}
                }
                value.put("payload",payload);var changed=decode(encode("wire","LEARNER_RETENTION_INTENT",value),"wire","LEARNER_RETENTION_INTENT");
                assertThrows(IllegalArgumentException.class,()->receiver.recordLearnerRetention(local.activationIdentity(),changed),field);
                assertEquals(before,V53ReplayFilesTest.files(g.f.request.targets().get(1).replicaDirectory()),field);
            }
            var ack=receiver.recordLearnerRetention(local.activationIdentity(),original);before=V53ReplayFilesTest.files(g.f.request.targets().get(1).replicaDirectory());
            assertArrayEquals(ack.bytes(),receiver.recordLearnerRetention(local.activationIdentity(),original).bytes());
            assertEquals(before,V53ReplayFilesTest.files(g.f.request.targets().get(1).replicaDirectory()));
            var events=g.events.get(1);assertTrue(events.indexOf("LEARNER_RETENTION_PARENT_FORCED")<events.indexOf("LEARNER_RETENTION_ACK_BEFORE_RETURN"));
            assertThrows(IllegalArgumentException.class,()->new MembershipLearnerRetentionQuorum(local,g.learner,g.f.ballot,resources(),
                    (p,r,k,d)->fail("foreign pool exchanged"),System::nanoTime,System.nanoTime(),BUDGET));
            var third=g.owners.get(2);g.hooks.get(2).set(event->{if(event.equals("LEARNER_RETENTION_PARENT_FORCED")) {
                var higher=new TreeMap<>(g.f.ballot);higher.put("counter",number(higher.get("counter"))+1);third.observeCurrent(higher);
            }});
            var request=g.request(2);assertThrows(IllegalArgumentException.class,()->third.recordLearnerRetention(local.activationIdentity(),request));
            assertEquals(1,third.learnerRetentionState().revision());assertFalse(g.events.get(2).contains("LEARNER_RETENTION_ACK_BEFORE_RETURN"));
        }
    }
}
