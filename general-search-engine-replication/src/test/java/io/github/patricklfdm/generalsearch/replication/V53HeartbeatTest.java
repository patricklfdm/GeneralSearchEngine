package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53HeartbeatTest {
    @TempDir Path temp;
    V53ActivationDriverTest.Local local()throws Exception {var helper=new V53ActivationDriverTest();helper.temp=temp;return helper.local();}
    static Decoded request(MembershipContext context,MembershipIdentity sender,MembershipIdentity recipient,long counter,boolean activated) {
        Map<String,Object> ballot=Map.of("counter",counter,"proposer",sender.nodeId().value(),"incarnation",sender.storageId().toString());
        return MembershipActivation.frame("HEARTBEAT",context,sender,recipient,ballot,UUID.randomUUID(),1,
                Map.of("cut",context.cut,"activated",activated));
    }
    static Decoded request(V53ActivationDriverTest.Local l,long counter,boolean activated)throws Exception {
        return request(l.owners.getFirst().activationContext(),l.group.identities.get(1),l.group.identities.getFirst(),counter,activated);
    }
    static Map<String,String> files(V53ActivationDriverTest.Local l)throws Exception {
        return V53ReplayFilesTest.files(l.group.fixture.request.targets().getFirst().replicaDirectory());
    }
    @Test void bothActivatedFlagsOnlyReturnOriginalCutWithoutGrantOrScope()throws Exception {
        try(var l=local()) {
            var owner=l.owners.getFirst();var before=files(l);var usage=l.endpoints.getFirst().usage();
            l.events.values().forEach(List::clear);
            for(boolean activated:List.of(false,true)) {
                var request=request(l,100,activated);var reply=l.endpoints.getFirst().handle(l.group.identities.get(1),request);
                MembershipWire.correlated(request,reply,"HEARTBEAT_ACK");
                assertEquals(Map.of("cut",owner.activationContext().cut),object(reply.value().get("payload")));
                assertEquals(usage,l.endpoints.getFirst().usage());assertEquals(before,files(l));
                assertTrue(l.events.values().stream().allMatch(List::isEmpty));
            }
            // The next real campaign must allocate beyond the volatile observation.
            assertTrue(number(object(owner.beginActivation().basis.value().get("ballot")).get("counter"))>100);
        }
    }
    @Test void higherHeartbeatFencesBeforeWaitingForWriter()throws Exception {
        try(var l=local()) {
            var owner=l.owners.getFirst();var original=owner.discoveryState(l.budgets.getFirst());var before=files(l);
            var request=request(l,100,true);var result=new CompletableFuture<Decoded>();Thread worker;
            synchronized(owner) {
                worker=Thread.ofPlatform().start(()->{try{result.complete(l.endpoints.getFirst().handle(l.group.identities.get(1),request));}
                    catch(Throwable error){result.completeExceptionally(error);}});
                V53MembershipTransportTest.waitFor(()->worker.getState()==Thread.State.BLOCKED || result.isDone());
                // The waiter may already be blocked on scratch validation. Poll
                // only the non-writing cancellation hint while owning the writer.
                V53MembershipTransportTest.waitFor(()->{
                    try{owner.checkActivationWait(original.context().authority(),original.ballot());return false;}
                    catch(IllegalArgumentException fenced){return true;}
                });
                assertFalse(result.isDone());assertEquals(before,files(l));
            }
            assertEquals("HEARTBEAT_ACK",result.get(5,TimeUnit.SECONDS).kind());worker.join(5000);assertFalse(worker.isAlive());
            assertEquals(before,files(l));
        }
    }
    @Test void oldHeartbeatCannotAcknowledgeOrLowerObservedBallot()throws Exception {
        try(var l=local()) {
            var endpoint=l.endpoints.getFirst();var peer=l.group.identities.get(1);var high=request(l,100,true);
            endpoint.handle(peer,high);var before=files(l);
            assertThrows(IllegalArgumentException.class,()->endpoint.handle(peer,request(l,99,true)));
            l.owners.getFirst().checkActivationBallot((String)high.value().get("view"),object(high.value().get("ballot")));
            assertEquals(before,files(l));
        }
    }
    @Test void advertisedProgressCannotInstallPrefixOrEnableReadiness()throws Exception {
        try(var l=local()) {
            var original=request(l,100,true);var fields=new TreeMap<>(original.value());
            var payload=new TreeMap<>(object(fields.get("payload")));var cut=new TreeMap<>(object(payload.get("cut")));
            cut.put("index",100L);cut.put("entry","a".repeat(64));payload.put("cut",cut);fields.put("payload",payload);
            var hint=decode(encode("wire","HEARTBEAT",fields),"wire","HEARTBEAT");var before=files(l);
            var local=l.owners.getFirst().activationContext().cut;
            var reply=l.endpoints.getFirst().handle(l.group.identities.get(1),hint);
            assertEquals(local,object(reply.value().get("payload")).get("cut"));assertEquals(before,files(l));
            assertTrue(l.endpoints.getFirst().usage().scopeEnded());assertNotEquals(cut,local);
        }
    }
    @Test void unauthenticatedOrOtherViewTrafficCannotFence()throws Exception {
        try(var l=local()) {
            var owner=l.owners.getFirst();var original=owner.discoveryState(l.budgets.getFirst());var before=files(l);
            for(String mode:List.of("root","view","storage","endpoint","proposer","cut-view","self","authenticated-sender")) {
                var r=request(l,100,true);var fields=new TreeMap<>(r.value());var peer=l.group.identities.get(1);
                switch(mode) {
                    case "root" -> fields.put("root","a".repeat(64));
                    case "view" -> fields.put("view","a".repeat(64));
                    case "storage","endpoint" -> {
                        peer=new MembershipIdentity(peer.nodeId(),mode.equals("storage")?UUID.randomUUID():peer.storageId(),
                                mode.equals("endpoint")?new ReplicationEndpoint("127.0.0.1",1):peer.endpoint());
                        fields.put("sender",MembershipBootstrapSeed.identity(peer));
                    }
                    case "proposer" -> {var ballot=new TreeMap<>(object(fields.get("ballot")));var id=l.group.identities.get(2);
                        ballot.put("proposer",id.nodeId().value());ballot.put("incarnation",id.storageId().toString());fields.put("ballot",ballot);}
                    case "cut-view" -> {var payload=new TreeMap<>(object(fields.get("payload")));var cut=new TreeMap<>(object(payload.get("cut")));
                        var view=new TreeMap<>(object(cut.get("view")));view.put("generation",number(view.get("generation"))+1);cut.put("view",view);payload.put("cut",cut);fields.put("payload",payload);}
                    case "self" -> {peer=l.group.identities.getFirst();fields=new TreeMap<>(request(owner.activationContext(),peer,peer,100,true).value());}
                    case "authenticated-sender" -> peer=l.group.identities.get(2);
                    default -> throw new AssertionError(mode);
                }
                var changed=decode(encode("wire","HEARTBEAT",fields),"wire","HEARTBEAT");var sender=peer;
                assertThrows(IllegalArgumentException.class,()->l.endpoints.getFirst().handle(sender,changed),mode);
                owner.checkActivationBallot(original.context().authority(),original.ballot());assertEquals(before,files(l));
            }
        }
    }
    @Test void heartbeatCannotReviveEndedScopeOrBypassClosedEndpoint()throws Exception {
        try(var l=local();var driver=l.driver(2)) {
            driver.run();var selected=driver.selection();l.endpoints.getFirst().abandon(object(selected.value().get("ballot")));
            var before=files(l);var usage=l.endpoints.getFirst().usage();assertTrue(usage.scopeEnded());
            var request=request(l,100,true);l.endpoints.getFirst().handle(l.group.identities.get(1),request);
            assertEquals(usage,l.endpoints.getFirst().usage());assertEquals(before,files(l));
            l.endpoints.getFirst().close();assertThrows(IllegalArgumentException.class,()->l.endpoints.getFirst().handle(l.group.identities.get(1),request));
        }
    }
    @Test void heartbeatWaitingForWriterStillUsesItsOriginalDeadline()throws Exception {
        var clock=new AtomicLong();var helper=new V53ActivationDriverTest();helper.temp=temp;
        try(var l=helper.local(clock,1000)) {
            var owner=l.owners.getFirst();var before=files(l);var request=request(l,100,true);
            var result=new CompletableFuture<Throwable>();Thread worker;
            synchronized(owner) {
                worker=Thread.ofPlatform().start(()->{try{l.endpoints.getFirst().handle(l.group.identities.get(1),request);result.complete(null);}
                    catch(Throwable error){result.complete(error);}});
                V53MembershipTransportTest.waitFor(()->worker.getState()==Thread.State.BLOCKED);clock.set(BUDGET);
            }
            var error=assertInstanceOf(IllegalArgumentException.class,result.get(5,TimeUnit.SECONDS));
            assertEquals("heartbeat endpoint closed/original deadline",error.getMessage());worker.join(5000);assertFalse(worker.isAlive());assertEquals(before,files(l));
        }
    }
    @Test void removedAndLearnerIdentitiesCannotSendOrReceiveVotingHeartbeats() {
        for(int through:List.of(3,6,7)) {
            var context=new V53CapsuleFixture(3,"REPLACE",through).verify().context;
            var local=context.identities.get("node-1");var nonvoter=context.identities.get(through==3?"node-6":"node-3");
            var heartbeat=request(context,nonvoter,local,100,true);
            if(through==6)assertDoesNotThrow(()->MembershipHeartbeat.incoming(context,local,nonvoter,heartbeat));
            else {
                assertThrows(IllegalArgumentException.class,()->MembershipHeartbeat.incoming(context,local,nonvoter,heartbeat));
                var outgoing=request(context,local,nonvoter,100,true);
                assertThrows(IllegalArgumentException.class,()->MembershipHeartbeat.incoming(context,nonvoter,local,outgoing));
            }
        }
    }
    @Test void nativeTcpHeartbeatsLeaveAllOriginalStorageUnchangedAtEveryStableSize()throws Exception {
        for(int size:List.of(3,4,5)) {
            var helper=new V53NativeDispatchTest();helper.temp=temp;
            try(var n=helper.new Network(size)) {
                var originals=new ArrayList<Map<String,String>>();
                for(var target:n.f.request.targets())originals.add(V53ReplayFilesTest.files(target.replicaDirectory()));
                n.events.clear();long counter=10;
                for(int from=0;from<size;from++)for(int to=0;to<size;to++)if(from!=to) {
                    var sender=n.owners.get(from);var recipient=n.owners.get(to);
                    var request=request(sender.activationContext(),sender.activationIdentity(),recipient.activationIdentity(),++counter,true);
                    var reply=n.transports.get(from).exchange(recipient.activationIdentity(),request,"HEARTBEAT_ACK",System.nanoTime()+BUDGET).get(10,TimeUnit.SECONDS);
                    assertEquals(recipient.activationContext().cut,object(reply.value().get("payload")).get("cut"));
                    assertTrue(n.endpoints.get(to).usage().scopeEnded());
                }
                assertTrue(n.events.stream().allMatch(v->Set.of("WIRE_RESPONSE","NETWORK_RECEIVED").contains(v.get("event"))));
                for(int i=0;i<size;i++)assertEquals(originals.get(i),V53ReplayFilesTest.files(n.f.request.targets().get(i).replicaDirectory()));
            }
        }
    }
}
