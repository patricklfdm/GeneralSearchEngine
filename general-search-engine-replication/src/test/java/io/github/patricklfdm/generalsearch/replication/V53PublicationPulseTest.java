package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Native publication changes the peer view before the proposer's view. A
 * cooperative diagnostic sample must not demand old-view contact in that gap. */
class V53PublicationPulseTest {
    @TempDir Path temp;
    @Test void finalPublicationDoesNotSampleTheObsoleteJointView()throws Exception {run("FINAL","complete");}
    @Test void intentPublicationDoesNotSampleTheObsoleteStableView()throws Exception {run("INTENT","complete");}
    @Test void stablePublicationKeepsCooperativeSampling()throws Exception {run("BARRIER","complete");}
    @Test void transitionStillChecksHigherBallotAtPublicationWrite()throws Exception {run("FINAL","higher");}
    @Test void transitionStillChecksOriginalDeadlineAtPublicationWrite()throws Exception {run("FINAL","deadline");}

    private void run(String kind,String fault)throws Exception {
        boolean transition=!kind.equals("BARRIER");var helper=new V53NativeDispatchTest();helper.temp=temp;
        var b=ReplicationBounds.defaults();
        var bounds=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
                b.maxRetryAttempts(),30_000,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
        long budget=TimeUnit.MINUTES.toNanos(10);var offset=new AtomicLong();
        try(var n=helper.new Network(transition?4:3,bounds,budget,f->{
            if(transition)V53TransitionRoundDriverTest.prepare(f,"CARRIED_"+kind,4);
        })) {
            n.activate();var owner=n.owners.getFirst();var before=owner.activationContext();
            Decoded entry;byte[] payload;
            if(transition) {
                int index=kind.equals("FINAL")?6:5;
                entry=decode(Files.readAllBytes(n.f.raw.resolve("entry-"+index+".gsr")),"records","ENTRY");
                payload=Files.readAllBytes(n.f.raw.resolve("payload-"+index+".bin"));
                assertEquals(entry.digest(),n.selected.value().get("nextEntry"));
            }else {var fixture=new V53SlotDriverTest();fixture.temp=temp;var input=fixture.input(n,false);entry=input.entry();payload=input.payload();}
            var sent=new AtomicInteger();var beforePulses=new AtomicInteger();var afterPulses=new AtomicInteger();
            var futureQuorums=new AtomicInteger();
            n.beforeSend.set(request->{if(request.kind().equals("PUBLISH")) {
                assertEquals(n.voters.size()-1,futureQuorums.get(),"every receiver retained before first dispatch");
                sent.incrementAndGet();
                if(fault.equals("higher")) {var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);owner.observeCurrent(higher);}
                if(fault.equals("deadline"))offset.set(budget);
            }});
            MembershipSourcePull.Guard sample=()->{
                if(sent.get()==0)beforePulses.incrementAndGet();
                else {afterPulses.incrementAndGet();assertFalse(transition,"old-view liveness sampled after a transition publication could reach a peer");}
            };
            long started=System.nanoTime();
            try(var slot=new MembershipSlotDriver(owner,n.endpoints.getFirst(),n.resources.getFirst(),bounds,n.transports.getFirst(),
                    ()->System.nanoTime()+offset.get(),started,budget,builder().configuration(),n.f.request.targets().getFirst().materialization(),
                    (event,record,voters)->{if(event.equals("FUTURE_QUORUM_COMPLETE"))futureQuorums.incrementAndGet();},sample)) {
                if(fault.equals("complete")) {
                    assertEquals("PUBLISH_ACK",slot.run(entry,payload).kind());assertTrue(slot.published().isPresent());
                    assertEquals(n.voters.size()-1,sent.get());
                    for(int voter:n.voters)assertEquals(entry.value().get("index"),n.owners.get(voter).activationContext().cut.get("index"));
                    assertEquals(transition,!before.view.equals(owner.activationContext().view));
                    assertEquals(transition,afterPulses.get()==0);
                }else {
                    var failure=assertThrows(Exception.class,()->slot.run(entry,payload));
                    if(fault.equals("higher"))assertInstanceOf(MembershipGrantJournal.HigherBallot.class,failure);
                    else assertTrue(failure.getMessage().contains("deadline"),failure.toString());
                    assertEquals(1,sent.get());assertTrue(slot.published().isEmpty());
                    for(int voter:n.voters)assertEquals(before.cut,n.owners.get(voter).activationContext().cut);
                    assertTrue(owner.currentCertificate().isPresent());
                    assertTrue(Files.isDirectory(n.f.request.targets().getFirst().replicaDirectory().resolve("applied-end")));
                    assertTrue(n.wire.stream().noneMatch(row->MembershipWire.decode(Base64.getDecoder().decode((String)row.get("request")),FRAME).kind().equals("PUBLISH")));
                }
                assertTrue(beforePulses.get()>0,"liveness before publication must remain enabled");
            }
        }
    }
}
