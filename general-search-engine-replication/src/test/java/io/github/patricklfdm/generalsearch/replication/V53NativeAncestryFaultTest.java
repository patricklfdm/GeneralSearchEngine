package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Actual compacted histories: proof I/O retains the fixed source set and deadline. */
class V53NativeAncestryFaultTest {
    @TempDir Path temp;
    final class Local implements AutoCloseable {
        final V53BootstrapPublicationTest.Fixture fixture;
        final List<MembershipGrantJournal> owners=new ArrayList<>();
        final List<MembershipResources> budgets=new ArrayList<>();
        final List<MembershipActivationEndpoint> endpoints=new ArrayList<>();
        final List<MembershipTransport> transports=new ArrayList<>();
        final List<List<String>> events=new ArrayList<>();
        final Path raw;
        final String ancestry;
        final AtomicLong clock=new AtomicLong(System.nanoTime());
        MembershipActivationDriver driver;
        Local()throws Exception {
            raw=Files.createDirectories(Path.of("target/v53-native-ancestry-fault/run-"+UUID.randomUUID()));
            System.out.println("v53NativeAncestryFaultEvidence="+raw.toAbsolutePath());
            fixture=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve("group-"+UUID.randomUUID())),3,false));
            fixture.ownedHistory=true;fixture.campaign(1);fixture.publish(1,false);
            byte[] payload=V53DistinctMinorityTest.payload(fixture,404,"majority-selected");
            var entry=V53DistinctMinorityTest.entry(fixture,payload,"DATA");
            V53DistinctMinorityTest.publishWithSequence(fixture,2,entry,payload,fixture.request.targets().subList(1,3),fixture.result.applicationSequence()+1);
            for(var target:fixture.request.targets()) {
                var budget=resources();budgets.add(budget);var trace=Collections.synchronizedList(new ArrayList<String>());events.add(trace);
                owners.add(MembershipGrantJournal.openBootstrapped(target.replicaDirectory(),target.materialization().directory(),fixture.result.root(),
                        target.identity(),budget,MembershipGrantJournal.MAXIMUM,trace::add));
            }
            var cap=owners.get(1).activationCapsule();ancestry=hash(canonical(Map.of("root",cap.context.root,"cut",cap.context.cut,"scope","retained-current-ancestry"),65536));
            for(int i=0;i<3;i++) {
                int node=i;MembershipSourcePull.Link link=(peer,request,kind,deadline)->transports.get(node).exchange(peer,request,kind,deadline);
                var endpoint=new MembershipActivationEndpoint(owners.get(i),budgets.get(i),bounds(),link,List.of(),List.of(),temp.resolve("endpoint-"+UUID.randomUUID()),System::nanoTime,BUDGET);
                endpoints.add(endpoint);transports.add(new MembershipTransport(cap,fixture.request.targets().get(i).identity(),bounds(),budgets.get(i),endpoint,MembershipTransport.Events.NONE));
            }
        }
        boolean offer(Decoded request){return request.kind().equals("CHUNK") && ancestry.equals(object(request.value().get("payload")).get("digest"));}
        CompletableFuture<Decoded> send(MembershipIdentity peer,Decoded request,String kind,long deadline){return transports.getFirst().exchange(peer,request,kind,deadline);}
        Decoded run(MembershipSourcePull.Link link)throws IOException {
            driver=new MembershipActivationDriver(owners.getFirst(),endpoints.getFirst(),budgets.getFirst(),bounds(),link,List.of(),List.of(),temp.resolve("driver-"+UUID.randomUUID()),clock::get,BUDGET,2);
            return driver.run();
        }
        void noSelection(){assertEquals(1,driver.campaigns());for(var trace:events){assertFalse(trace.contains("SELECTED_FORCED"));assertFalse(trace.contains("INSTALL_BEFORE_RETURN"));}}
        @Override public void close()throws Exception {
            if(driver!=null)driver.close();for(var endpoint:endpoints)endpoint.close();for(var transport:transports)transport.close();for(var owner:owners)owner.close();
            Files.write(raw.resolve("events.json"),canonical(events,1024*1024));fixture.snapshot("after");
            for(var budget:budgets){assertEquals(0,budget.usage().leases());assertEquals(0,budget.usage().queued());}
        }
    }
    static <T> CompletableFuture<T> lost(){return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"injected lost ancestry response",null));}

    @Test void lostAncestryReplyRetriesExactRequestWithoutNewSourceOrDeadline()throws Exception {
        try(var local=new Local()) {
            var calls=new AtomicInteger();var original=new AtomicReference<byte[]>();var deadline=new AtomicLong();
            var selected=local.run((peer,request,kind,end)->{
                if(!local.offer(request))return local.send(peer,request,kind,end);
                int call=calls.incrementAndGet();
                if(call==1){original.set(request.bytes());deadline.set(end);return local.send(peer,request,kind,end).thenCompose(reply->lost());}
                assertArrayEquals(original.get(),request.bytes());assertEquals(deadline.get(),end);return local.send(peer,request,kind,end);
            });
            assertEquals(2,calls.get());assertEquals(1,local.driver.campaigns());assertEquals(3L,object(selected.value().get("ballot")).get("counter"));
            assertEquals(List.of("node-1","node-2"),list(selected.value().get("sources")).stream().map(v->object(v).get("voter")).toList());
            assertFalse(local.events.get(2).contains("GRANT_BEFORE_RETURN"));
        }
    }
    @Test void exhaustedProofSourceRequiresFreshBallotAndPreservesOriginalFailedSource()throws Exception {
        try(var local=new Local()) {
            var calls=new AtomicInteger();var original=new AtomicReference<byte[]>();var deadline=new AtomicLong();
            var selected=local.run((peer,request,kind,end)->{
                if(!local.offer(request) || !peer.nodeId().value().equals("node-2"))return local.send(peer,request,kind,end);
                if(calls.incrementAndGet()==1){original.set(request.bytes());deadline.set(end);}else{assertArrayEquals(original.get(),request.bytes());assertEquals(deadline.get(),end);}
                return local.send(peer,request,kind,end).thenCompose(reply->lost());
            });
            assertEquals(Math.min(3,bounds().maxRetryAttempts()),calls.get());assertEquals(2,local.driver.campaigns());
            assertEquals(4L,object(selected.value().get("ballot")).get("counter"));
            assertEquals(List.of("node-1","node-3"),list(selected.value().get("sources")).stream().map(v->object(v).get("voter")).toList());
            assertFalse(local.events.get(1).contains("SELECTED_FORCED"));
            assertEquals(3L,object(local.owners.get(1).originalBasis().orElseThrow().value().get("ballot")).get("counter"));
        }
    }
    @Test void malformedManifestOfferFailsWithoutRetryOrReselectingSources()throws Exception {
        try(var local=new Local()) {
            var calls=new AtomicInteger();assertThrows(IllegalArgumentException.class,()->local.run((peer,request,kind,end)->local.send(peer,request,kind,end).thenApply(reply->{
                if(!local.offer(request))return reply;calls.incrementAndGet();var payload=new TreeMap<>(object(reply.value().get("payload")));payload.put("kind","CAPSULE");
                var fields=new TreeMap<>(reply.value());fields.put("payload",payload);return decode(encode("wire",reply.kind(),fields),"wire",reply.kind());
            })));
            assertEquals(1,calls.get());local.noSelection();assertFalse(local.events.get(2).contains("GRANT_BEFORE_RETURN"));
        }
    }
    @Test void higherPromiseDuringAncestryDeliveryFencesBeforeAnySelection()throws Exception {
        try(var local=new Local()) {
            var calls=new AtomicInteger();assertThrows(Exception.class,()->local.run((peer,request,kind,end)->local.send(peer,request,kind,end).thenApply(reply->{
                if(local.offer(request)){calls.incrementAndGet();var identity=local.fixture.request.targets().get(1).identity();
                    local.owners.getFirst().observeCurrent(Map.of("counter",4L,"proposer","node-2","incarnation",identity.storageId().toString()));}
                return reply;
            })));
            assertEquals(1,calls.get());local.noSelection();
        }
    }
    @Test void ancestryCannotResetTheOriginalDeadlineOrStartAnotherBallot()throws Exception {
        try(var local=new Local()) {
            var calls=new AtomicInteger();assertThrows(Exception.class,()->local.run((peer,request,kind,end)->local.send(peer,request,kind,end).thenApply(reply->{
                if(local.offer(request)){calls.incrementAndGet();local.clock.set(end);}return reply;
            })));
            assertEquals(1,calls.get());local.noSelection();
        }
    }
}
