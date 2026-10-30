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

/** One whole real TCP history. The native adapter is only decorated to retain
 * snapshots and stop after the declared DATA; grants/replies are never injected. */
class V53AutomaticServiceTest {
    @TempDir Path temp;
    @Test void automaticWaitDiscoveryBarrierHeartbeatAndQueuedDataShareOneHistory()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE)) {
            var policy=AutomaticLeadershipPolicy.forBounds(n.bounds);var nativeSession=round.automaticSession(policy);
            var firstPulse=new CountDownLatch(1);var dataQueued=new CountDownLatch(1);
            var completedData=new AtomicBoolean();var holder=new AtomicReference<MembershipAutomaticOwner>();
            var pulses=new AtomicInteger();
            n.beforeSend.set(request->{if(request.kind().equals("HEARTBEAT"))n.events.add(Map.of("node","node-1","event","HEARTBEAT_SEND",
                    "bytes",Base64.getEncoder().encodeToString(request.bytes())));});
            var observed=new MembershipAutomaticOwner.Session() {
                public Decoded start(long began)throws IOException{return nativeSession.start(began);}
                public void idle()throws IOException{nativeSession.idle();}
                public Decoded readiness()throws IOException{return nativeSession.readiness();}
                public Decoded submit(String kind,byte[] bytes)throws IOException {
                    var result=nativeSession.submit(kind,bytes);assertEquals("DATA",kind);completedData.set(true);return result;
                }
                public MembershipHeartbeatRound.Contact heartbeat()throws IOException {
                    if(pulses.incrementAndGet()>1) {
                        assertTrue(completedData.get(),"fixture requires first queued DATA before stop");
                        holder.get().close();throw new IOException("fixture closed after declared DATA");
                    }
                    try{n.f.snapshot("heartbeat-before");}catch(Exception error){throw new IOException(error);}
                    n.events.add(Map.of("node","node-1","event","HEARTBEAT_BEGIN"));
                    var contact=nativeSession.heartbeat();
                    var hints=contact.hints().entrySet().stream().sorted(Map.Entry.comparingByKey())
                        .map(v->Map.of("node",v.getKey(),"cut",v.getValue())).toList();
                    n.events.add(Map.of("node","node-1","event","HEARTBEAT_CONTACT","responding",contact.responding().stream().sorted().toList(),"hints",hints));
                    try{n.f.snapshot("heartbeat-after");}catch(Exception error){throw new IOException(error);}
                    firstPulse.countDown();V53AutomaticOwnerTest.await(dataQueued);return contact;
                }
                public void close()throws IOException{dataQueued.countDown();nativeSession.close();}
            };
            try(var owner=new MembershipAutomaticOwner(observed,n.resources.getFirst(),n.bounds,policy,()->System.nanoTime()+n.offset.get(),V53NativeDispatchTest.BUDGET)) {
                holder.set(owner);assertThrows(IllegalArgumentException.class,owner::readiness);
                var barrier=owner.start().await(180,TimeUnit.SECONDS);assertEquals("PUBLISH_ACK",barrier.kind());
                assertTrue(firstPulse.await(30,TimeUnit.SECONDS),"native automatic heartbeat");
                var data=owner.submit("DATA",helper.data(n));dataQueued.countDown();assertEquals("PUBLISH_ACK",data.await(180,TimeUnit.SECONDS).kind());
                owner.close();assertTrue(completedData.get());assertEquals(0,owner.pending());
                assertEquals(MembershipAutomaticOwner.State.CLOSED,owner.state());assertEquals(MembershipRoundDriver.State.CLOSED,round.state());
                Files.write(n.f.raw.resolve("result.json"),canonical(Map.of("status","PASS","slots",2,"network",true,"autonomous",false),4096));
                Files.write(n.f.raw.resolve("round-result.json"),canonical(Map.of("status","PASS","mode","stable","internalReady",true,"publicReady",false),4096));
            }
        }
    }
}
