package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual native DATA and publication with an admitted automatic-call backlog.
 * The decorator holds only the current caller before dispatch; all protocol
 * work, grants, typed application and responses use the original native adapter. */
class V53AutomaticWaiterCompletionTest {
    @TempDir Path temp;

    @Test void saturatedClientBacklogLeavesRoomForNativePublication()throws Exception {
        var settings=List.of("v53.resource.transitions","v53.resource.slot.control");
        var previous=new HashMap<String,String>();
        for(var key:settings){previous.put(key,System.getProperty(key));System.setProperty(key,"true");}
        try { nativePublication(); }
        finally { for(var key:settings)if(previous.get(key)==null)System.clearProperty(key);else System.setProperty(key,previous.get(key)); }
    }
    private void nativePublication()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var n=helper.network(null,helper.controlBounds());var round=helper.driver(n,MembershipRoundDriver.Events.NONE)) {
            // Keep the original 180-second lifetime and 30-second RPC bound;
            // queue completion is independent of the supported election delay.
            var policy=AutomaticLeadershipPolicy.forBounds(ReplicationBounds.defaults());
            var nativeSession=round.automaticSession(policy);
            byte[] input=helper.data(n);
            var observed=new MembershipAutomaticOwner.Session() {
                public Decoded start(long began)throws IOException{return nativeSession.start(began);}
                public void idle()throws IOException{nativeSession.idle();}
                public MembershipHeartbeatRound.Contact heartbeat()throws IOException{return nativeSession.heartbeat();}
                public Decoded readiness()throws IOException{return nativeSession.readiness();}
                public Decoded submit(String kind,byte[] bytes)throws IOException {
                    entered.countDown();V53AutomaticOwnerTest.await(release);return nativeSession.submit(kind,bytes);
                }
                public void close()throws IOException{release.countDown();nativeSession.close();}
            };
            try(var owner=new MembershipAutomaticOwner(observed,n.resources.getFirst(),n.bounds,policy,
                    ()->System.nanoTime()+n.offset.get(),V53NativeDispatchTest.BUDGET)) {
                assertEquals("PUBLISH_ACK",owner.start().await(180,TimeUnit.SECONDS).kind());
                var active=owner.submit("DATA",input);assertTrue(entered.await(5,TimeUnit.SECONDS));
                var queued=new ArrayList<MembershipAutomaticOwner.Call>();String refusal=null;
                for(int i=0;i<MembershipResources.Unit.WAITER.count;i++) {
                    try{queued.add(owner.readiness());}
                    catch(IllegalArgumentException error){refusal=error.getMessage();break;}
                }
                assertNotNull(refusal,"bounded admission must refuse the next caller");
                var saturated=n.resources.getFirst().usage();int admitted=owner.pending();
                assertEquals(queued.size()+1,admitted);assertTrue(admitted>1);assertFalse(active.isDone());
                assertTrue(queued.stream().noneMatch(MembershipAutomaticOwner.Call::isDone));
                System.out.println("v53AutomaticWaiterPressure=admitted:"+admitted+" usage:"+saturated+" refusal:"+refusal);
                release.countDown();assertEquals("PUBLISH_ACK",active.await(180,TimeUnit.SECONDS).kind());
                for(var call:queued)assertEquals("PUBLISH_ACK",call.await(30,TimeUnit.SECONDS).kind());
                V53MembershipTransportTest.waitFor(()->owner.pending()==0);
                assertEquals(MembershipAutomaticOwner.State.READY,owner.state());assertTrue(owner.failure().isEmpty());
                assertEquals("PUBLISH_ACK",owner.readiness().await(30,TimeUnit.SECONDS).kind());
                assertEquals(62,admitted);n.assertLocalSlots(2);
                assertEquals("automatic waiter completion headroom",refusal);
                var trace=n.resources.getFirst().observations();assertFalse(trace.failed());assertFalse(trace.truncated());
                var live=new HashSet<MembershipResourceObservations.Charge>();boolean overlap=false;
                for(var change:trace.changes()) {
                    assertTrue(live.containsAll(change.removed()));live.removeAll(change.removed());live.addAll(change.added());
                    var waiters=live.stream().filter(c->c.unit()==MembershipResources.Unit.WAITER).toList();
                    assertTrue(waiters.size()<=64);
                    if(waiters.size()==64 && waiters.stream().filter(c->c.owner().startsWith("automatic-call-")).count()==62
                            && waiters.stream().anyMatch(c->c.owner().startsWith("activation-waiter-"))
                            && waiters.stream().anyMatch(c->c.owner().startsWith("slot-waiter-")))overlap=true;
                }
                assertTrue(overlap,"actual local native handlers must coexist with all admitted clients");
                for(int peer:n.voters)assertEquals(2L,number(n.owners.get(peer).activationContext().cut.get("index")));
                Files.write(n.f.raw.resolve("automatic-waiter-result.json"),canonical(Map.of(
                    "status","PASS","admitted",admitted,"queued",queued.size(),"refusal",refusal,
                    "slots",2,"nativePublicationCompleted",true,"publicReady",false,"phase3Complete",false),4096));
            }finally{release.countDown();}
        }
    }
}
