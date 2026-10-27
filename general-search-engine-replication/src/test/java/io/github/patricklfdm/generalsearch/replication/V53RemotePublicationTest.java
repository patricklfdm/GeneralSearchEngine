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

class V53RemotePublicationTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(120);
    final class Network implements AutoCloseable {
        final V53FutureRetentionEndpointTest.Group group;
        final List<MembershipPublicationEndpoint> endpoints=new ArrayList<>();
        final List<MembershipTransport> transports=new ArrayList<>();
        final List<AtomicReference<MembershipTransport>> links=new ArrayList<>();
        final List<Map<String,Object>> wire=Collections.synchronizedList(new ArrayList<>());
        final List<Map<String,Object>> transcript=Collections.synchronizedList(new ArrayList<>());
        final AtomicBoolean loseAck=new AtomicBoolean(),lost=new AtomicBoolean(),refusePull=new AtomicBoolean();
        final AtomicBoolean rejectCheckpoint=new AtomicBoolean();
        final AtomicReference<Runnable> beforeWrite=new AtomicReference<>(()->{});
        final AtomicInteger publicationReads=new AtomicInteger();
        Network(int size)throws Exception {
            var helper=new V53FutureRetentionEndpointTest();helper.temp=temp;group=helper.new Group(size,true);
            for(int i=0;i<size;i++)links.add(new AtomicReference<>());
            for(int i=0;i<size;i++) {
                int index=i;var owner=group.owners.get(i);var bounds=ReplicationBounds.defaults();
                var endpoint=new MembershipPublicationEndpoint(owner,group.applied.get(i),group.budgets.get(i),bounds,
                        (peer,request,kind,deadline)->{
                            if(refusePull.get())return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"offline checkpoint owner",null));
                            return links.get(index).get().exchange(peer,request,kind,deadline);
                        },System::nanoTime,System.nanoTime(),BUDGET,(event,statement,ack)->{
                            transcript.add(Map.of("event",event,"receiver",owner.activationIdentity().nodeId().value(),"statement",HexFormat.of().formatHex(statement.bytes()),
                                    "ack",HexFormat.of().formatHex(ack.bytes())));
                            group.timeline.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event",event,"digest",ack.digest()));
                        });endpoints.add(endpoint);
                var transport=new MembershipTransport(owner.activationCapsule(),owner.activationIdentity(),bounds,group.budgets.get(i),(sender,request)->{
                    if(index==0 && rejectCheckpoint.get() && request.kind().equals("CHUNK")) {
                        higher(0);var response=new TreeMap<>(request.value());response.put("sender",request.value().get("recipient"));response.put("recipient",request.value().get("sender"));
                        response.put("payload",Map.of("reason","STALE_EPOCH","promised",Map.of("counter",3L,"proposer","node-1","incarnation",owner.activationIdentity().storageId().toString())));
                        return decode(encode("wire","REJECT",response),"wire","REJECT");
                    }
                    return endpoint.handle(sender,request);
                },(event,request,response)->{
                    if(request.kind().equals("PUBLISH") && event.equals("BEFORE_REQUEST_WRITE")) {
                        group.timeline.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event","PUBLICATION_SEND_BOUNDARY","digest",request.digest()));beforeWrite.get().run();
                    }
                    if(request.kind().equals("PUBLISH") && event.equals("AFTER_REQUEST_READ")) {
                        publicationReads.incrementAndGet();group.timeline.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event","PUBLICATION_REQUEST_RECEIVED","digest",request.digest()));
                    }
                    if(event.equals("BEFORE_RESPONSE_WRITE")) {
                        boolean drop=response.kind().equals("PUBLISH_ACK") && loseAck.get() && lost.compareAndSet(false,true);
                        var row=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));row.put("withheld",drop);wire.add(row);
                        if(drop)throw new IOException("lost durable publication acknowledgement");
                    }
                    if(event.equals("AFTER_RESPONSE_READ"))group.timeline.add(Map.of("node",owner.activationIdentity().nodeId().value(),"event","NETWORK_RECEIVED",
                            "kind",response.kind(),"digest",response.digest()));
                });transports.add(transport);links.get(i).set(transport);
            }
        }
        MembershipFutureRetentionQuorum quorum()throws Exception {
            var local=group.owners.getFirst();return new MembershipFutureRetentionQuorum(local,group.peer(),group.fixture.ballot,
                    local.pendingPublication(group.applied.getFirst()),group.budgets.getFirst(),transports.getFirst()::exchange,
                    System::nanoTime,System.nanoTime(),BUDGET);
        }
        void higher(int index) {
            group.owners.get(index).observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",group.owners.getFirst().activationIdentity().storageId().toString()));
        }
        @Override public void close()throws Exception {
            for(var endpoint:endpoints)endpoint.close();for(var transport:transports)transport.close();
            Files.write(group.fixture.raw.resolve("publication-wire.json"),canonical(wire,8*1024*1024));
            Files.write(group.fixture.raw.resolve("publication-receipts.json"),canonical(transcript,8*1024*1024));group.close();
        }
    }
    @Test void recordingQuorumDispatchesRealNativePublicationWithLostAckAndIdenticalDuplicate()throws Exception {
        for(int size:List.of(3,4,5))try(var network=new Network(size);var quorum=network.quorum()) {
            network.loseAck.set(size==3);var recorded=quorum.record();recorded.check();
            network.group.timeline.add(Map.of("node","node-1","event","FUTURE_QUORUM_COMPLETE","voters",new ArrayList<>(new TreeSet<>(recorded.voters()))));
            var response=recorded.dispatch(network.transports.getFirst());assertEquals("PUBLISH_ACK",response.kind());
            assertEquals(size==3,network.lost.get());var target=network.group.owners.getLast();
            assertEquals(1L,target.activationContext().cut.get("index"));assertEquals(0L,network.group.owners.getFirst().activationContext().cut.get("index"));
            assertTrue(network.group.owners.getFirst().futureRetentionState().pending());
            assertFalse(target.futureRetentionState().pending());
            assertThrows(IllegalArgumentException.class,()->recorded.dispatch(network.transports.getFirst()));
            var row=network.wire.stream().filter(v->MembershipWire.decode(Base64.getDecoder().decode((String)v.get("request")),FRAME).kind().equals("PUBLISH")).findFirst().orElseThrow();
            var original=decode(Base64.getDecoder().decode((String)row.get("request")),"wire","PUBLISH");var files=network.group.files(size-1);
            var duplicate=network.transports.getFirst().exchange(target.activationIdentity(),original,"PUBLISH_ACK",System.nanoTime()+BUDGET).get(120,TimeUnit.SECONDS);
            assertArrayEquals(response.bytes(),duplicate.bytes());assertEquals(files,network.group.files(size-1));
            Files.write(network.group.fixture.raw.resolve("publication-result.json"),canonical(Map.of("status","PASS","size",size,
                    "target",target.activationIdentity().nodeId().value(),"quorum",new ArrayList<>(new TreeSet<>(recorded.voters())),"ack",response.digest(),"lostAck",network.lost.get()),65536));
        }
    }
    @Test void higherBallotBetweenQueueAndWritePreventsAnyPublicationRequest()throws Exception {
        try(var network=new Network(3);var quorum=network.quorum()) {
            var recorded=quorum.record();network.beforeWrite.set(()->network.higher(0));
            assertThrows(IllegalArgumentException.class,()->recorded.dispatch(network.transports.getFirst()));
            assertEquals(0,network.publicationReads.get());assertEquals(0L,network.group.owners.getLast().activationContext().cut.get("index"));
            assertTrue(network.group.owners.getFirst().futureRetentionState().pending());
        }
    }
    @Test void closingBetweenQueueAndWriteRevokesDispatchAndRetainsDurableResponsibility()throws Exception {
        try(var network=new Network(3);var quorum=network.quorum()) {
            var recorded=quorum.record();network.beforeWrite.set(quorum::close);
            assertThrows(Exception.class,()->recorded.dispatch(network.transports.getFirst()));
            assertEquals(0,network.publicationReads.get());assertTrue(network.group.owners.getFirst().futureRetentionState().pending());
        }
    }
    @Test void actualCheckpointMinorityCannotPublishEvenWithARecordedFutureQuorum()throws Exception {
        try(var network=new Network(3);var quorum=network.quorum()) {
            var recorded=quorum.record();network.refusePull.set(true);
            assertThrows(MembershipTransport.Failure.class,()->recorded.dispatch(network.transports.getFirst()));
            assertEquals(0L,network.group.owners.getLast().activationContext().cut.get("index"));
            assertTrue(network.group.owners.getFirst().futureRetentionState().pending());assertEquals(0,network.transcript.size());
        }
    }
    @Test void higherBallotAfterPublicationForceSuppressesAckAndPreservesPublishedCut()throws Exception {
        try(var network=new Network(3);var quorum=network.quorum()) {
            var recorded=quorum.record();network.group.hooks.getLast().set(event->{if(event.equals("PUBLICATION_ACK_BEFORE_RETURN"))network.higher(2);});
            assertThrows(MembershipTransport.Failure.class,()->recorded.dispatch(network.transports.getFirst()));
            assertEquals(1L,network.group.owners.getLast().activationContext().cut.get("index"));
            assertTrue(network.group.owners.getFirst().futureRetentionState().pending());
            assertTrue(network.wire.stream().noneMatch(row->MembershipWire.decode(Base64.getDecoder().decode((String)row.get("response")),FRAME).kind().equals("PUBLISH_ACK")));
        }
    }
    @Test void higherCheckpointResponseFencesTheReceivingOwnerBeforePublication()throws Exception {
        try(var network=new Network(3);var quorum=network.quorum()) {
            var recorded=quorum.record();network.rejectCheckpoint.set(true);
            assertThrows(IllegalArgumentException.class,()->recorded.dispatch(network.transports.getFirst()));
            var target=network.group.owners.getLast();assertEquals(0L,target.activationContext().cut.get("index"));
            assertThrows(IllegalArgumentException.class,()->target.checkActivationBallot(target.activationContext().authority(),network.group.fixture.ballot));
            assertTrue(network.group.owners.getFirst().futureRetentionState().pending());
        }
    }
    @Test void wrongCertificateAndExpiredScopeNeverAdvancePublication()throws Exception {
        try(var network=new Network(3)) {
            var local=network.group.owners.getFirst();var target=network.group.owners.getLast();
            var wrong=MembershipActivation.frame("PUBLISH",local.activationContext(),local.activationIdentity(),target.activationIdentity(),network.group.fixture.ballot,
                    UUID.randomUUID(),1,Map.of("certificate","0".repeat(64)));
            assertThrows(IllegalArgumentException.class,()->network.endpoints.getLast().handle(local.activationIdentity(),wrong));
            var clock=new AtomicLong();try(var endpoint=new MembershipPublicationEndpoint(target,network.group.applied.getLast(),network.group.budgets.getLast(),
                    ReplicationBounds.defaults(),network.transports.getLast()::exchange,clock::get,0,10,MembershipTransport.Events.NONE)) {
                clock.set(10);assertFalse(endpoint.poll());assertThrows(IllegalArgumentException.class,()->endpoint.handle(local.activationIdentity(),wrong));
            }
            assertEquals(0L,target.activationContext().cut.get("index"));
        }
    }
}
