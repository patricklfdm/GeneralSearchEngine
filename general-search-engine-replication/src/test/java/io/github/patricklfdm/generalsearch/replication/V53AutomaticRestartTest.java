package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Real three-node service recovery; original-first multi-round replay remains
 * a separate gate. The only fault is an authenticated higher-ballot heartbeat
 * from node 2, after its real allocator force. No reply or chosen value is faked. */
class V53AutomaticRestartTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(300);
    static final AutomaticLeadershipPolicy POLICY=AutomaticLeadershipPolicy.forBounds(ReplicationBounds.defaults());
    @Test void higherBallotAutomaticallyDrainsAndReactivatesBeforeNewData()throws Exception {
        var nativeHelper=new V53NativeDispatchTest();nativeHelper.temp=temp;
        // Whole-history semantics include reverse checkpoint pulls. Use the
        // declared control profile, not the default five-second RPC latency
        // gate; the original lifetime and finite retry count remain unchanged.
        var n=nativeHelper.new Network(3,new V53RoundDriverTest().controlBounds(),BUDGET,f->{});
        var sends=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
        n.beforeSend.set(request->{synchronized(n.events) {
            if(sends.size()>=65536)throw new IllegalStateException("restart send evidence bound");
            sends.add(Map.of("afterEvent",n.events.size()-1,"bytes",Base64.getEncoder().encodeToString(request.bytes())));
        }});
        V53RestartLifecycleCapture capture=null;MembershipAutomaticOwner observedOwner=null;boolean passed=false;Throwable primary=null;
        try(n) {
            if(Boolean.getBoolean("v53.restart.lifecycle.captures")) {
                synchronized(n.events){capture=new V53RestartLifecycleCapture(n.f.raw,n.events);n.restartLifecycleCapture=capture;}
            }
            var installed=new AtomicInteger();
            var round=new MembershipRoundDriver<>(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,n.transports.getFirst(),
                temp.resolve("restart-round"),()->System.nanoTime()+n.offset.get(),BUDGET,2,builder().configuration(),n.f.request.targets().getFirst().materialization(),
                (event,record)->{
                    n.events.add(Map.of("node","node-1","event","ROUND_"+event,"record",record.digest(),"bytes",Base64.getEncoder().encodeToString(record.bytes())));
                    if(event.equals("INSTALLED")) {
                        n.selected=record;n.ballot=object(record.value().get("ballot"));
                        int at=installed.incrementAndGet();Files.write(n.f.raw.resolve("selected-"+at+".gsr"),record.bytes());
                        try{n.f.snapshot("installed-"+at);}catch(Exception error){throw new IOException(error);}
                    }
                    if(event.equals("SLOT_BEGIN"))n.events.add(Map.of("node","node-1","event",event,"index",record.value().get("index")));
                },(event,record,voters)->{
                    if(event.equals("FUTURE_QUORUM_COMPLETE"))n.events.add(Map.of("node","node-1","event",event,"index",record.value().get("index"),"voters",voters.stream().sorted().toList()));
                    if(event.equals("APPLIED") || event.equals("PUBLISHED"))try{n.f.snapshot(event.toLowerCase(Locale.ROOT)+"-"+record.value().get("index"));}
                    catch(Exception error){throw new IOException(error);}
                });
            long began=System.nanoTime();
            var collected=capture;
            try(round;var owner=round.automaticOwner(POLICY,
                    collected==null?MembershipAutomaticOwner.Events.NONE:event->collected.lifecycle.at("node-1",event))) {
                observedOwner=owner;if(capture!=null)capture.opened(BUDGET);
                var first=owner.start().await(300,TimeUnit.SECONDS);assertEquals(1,owner.rounds());n.f.snapshot("first-ready");
                var proposer=n.owners.get(1);long counter=proposer.reserveCounter();var peer=proposer.activationIdentity();
                var higher=Map.<String,Object>of("counter",counter,"proposer",peer.nodeId().value(),"incarnation",peer.storageId().toString());
                assertTrue(MembershipContext.compareBallot(higher,n.ballot)>0);
                var context=proposer.activationContext();
                var request=MembershipActivation.frame("HEARTBEAT",context,peer,n.owners.getFirst().activationIdentity(),higher,UUID.randomUUID(),1,
                    Map.of("cut",context.cut,"activated",false));
                Files.write(n.f.raw.resolve("fence-request.gsw"),request.bytes());
                assertEquals("HEARTBEAT_ACK",n.transports.get(1).exchange(n.owners.getFirst().activationIdentity(),request,"HEARTBEAT_ACK",began+BUDGET).get(30,TimeUnit.SECONDS).kind());
                n.f.snapshot("after-fence");
                while(owner.rounds()<2 || owner.state()!=MembershipAutomaticOwner.State.READY) {
                    assertNotEquals(MembershipAutomaticOwner.State.FAILED,owner.state(),()->"automatic restart failed: "+owner.failure());
                    assertNotEquals(MembershipAutomaticOwner.State.CLOSED,owner.state());
                    assertTrue(System.nanoTime()-began<BUDGET,"original whole-history deadline");Thread.sleep(25);
                }
                var second=owner.readiness().await(180,TimeUnit.SECONDS);assertNotEquals(first.digest(),second.digest());
                assertEquals(2,installed.get());assertEquals(2,owner.rounds());
                assertEquals(List.of(MembershipCampaignLost.Reason.HIGHER_BALLOT),owner.losses());
                assertEquals(2L,n.owners.getFirst().activationContext().cut.get("index"));
                n.f.snapshot("second-ready");var helper=new V53RoundDriverTest();helper.temp=temp;
                assertEquals("PUBLISH_ACK",owner.submit("DATA",helper.data(n)).await(180,TimeUnit.SECONDS).kind());
                int campaigns=installed.get();assertTrue(campaigns==2 || campaigns==3,"at most one pre-DATA retention reconciliation");
                assertEquals(campaigns+1L,n.owners.getFirst().activationContext().cut.get("index"));owner.close();
                Files.write(n.f.raw.resolve("restart-result.json"),canonical(Map.of("status","PARTIAL","producerPassed",true,"rounds",2,
                    "barriers",campaigns,"dataCalls",1,"originalBudgetNanos",BUDGET,"requestTimeoutMillis",n.bounds.requestTimeoutMillis(),
                    "leadershipPolicyMillis",List.of(POLICY.heartbeatIntervalMillis(),POLICY.minElectionTimeoutMillis(),POLICY.maxElectionTimeoutMillis(),POLICY.operationTimeoutMillis()),
                    "physicalReplay",false,"phase3Complete",false),4096));
                passed=true;
            }
        }catch(Exception|Error error){primary=error;throw error;}
        finally {
            V53NodeProcessDiagnostics.finish(primary,()->{},
                ()->Files.write(n.f.raw.resolve("restart-sends.json"),canonical(sends,32*1024*1024)));
            if(capture!=null) {
                var retained=capture;var observed=observedOwner;boolean producerPassed=passed;
                V53NodeProcessDiagnostics.finish(primary,()->{},()->retained.save(n.f.raw,producerPassed,observed!=null && observed.drained(),
                    observed==null?Optional.of(new IOException("automatic owner not constructed")):observed.observationFailure(),n.resources));
            }
        }
    }
}
