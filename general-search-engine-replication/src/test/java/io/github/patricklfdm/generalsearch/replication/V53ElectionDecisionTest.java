package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53ElectionWaitTest.*;

class V53ElectionDecisionTest {
    @TempDir Path temp;
    V53ElectionWaitTest.Fixture fixture()throws Exception {
        var h=new V53ElectionWaitTest();h.temp=temp;return h.new Fixture();
    }
    static boolean current(MembershipElectionWait.Decision d,V53ElectionWaitTest.Fixture f)throws Exception {
        return d.current(f.l.owners.getFirst(),f.l.endpoints.getFirst(),f.l.budgets.getFirst());
    }
    static MembershipElectionWait.Decision expired(V53ElectionWaitTest.Fixture f)throws Exception {
        f.heartbeat(100,true);f.clock.set(millis(20));
        try(var wait=f.waitFor(100)){return wait.awaitDecision();}
    }
    @Test void unchangedExpiredDecisionReadsOriginalsWithoutAllocating()throws Exception {
        try(var f=fixture()) {
            var d=expired(f);var files=V53HeartbeatTest.files(f.l);
            assertTrue(current(d,f));f.clock.set(millis(30));assertTrue(current(d,f));
            f.heartbeat(100,false);assertTrue(current(d,f));assertEquals(files,V53HeartbeatTest.files(f.l));
        }
    }
    @Test void sameBallotContactDuringDiscoveryInvalidatesExpiredDecision()throws Exception {
        try(var f=fixture()) {
            var d=expired(f);f.clock.set(millis(21));f.heartbeat(100,true);assertFalse(current(d,f));
            var done=new CompletableFuture<MembershipGrantJournal.DiscoveryState>();
            try(var wait=f.waitFor(100)) {
                Thread worker=run(wait,done);
                try{idle(worker);f.clock.set(millis(35));assertFalse(done.isDone());f.clock.set(millis(36));done.get(5,TimeUnit.SECONDS);}
                finally{wait.close();worker.join(5000);}
                assertFalse(worker.isAlive());
            }
            // The original arrival has now expired; checking it never starts a
            // new delay at poll time and cannot invent another grant.
            try(var wait=f.waitFor(100)){assertTrue(current(wait.awaitDecision(),f));}
        }
    }
    @Test void newerFenceWithoutActivatedContactStillInvalidatesDecision()throws Exception {
        try(var f=fixture()) {
            var d=expired(f);f.heartbeat(101,false);assertFalse(current(d,f));
        }
    }
    @Test void invalidOriginalBytesAndClosedEndpointCannotBecomeAnotherWait()throws Exception {
        try(var f=fixture()) {
            var d=expired(f);Path p=f.l.group.fixture.request.targets().getFirst().replicaDirectory().resolve("selector.gsr");
            byte[] original=Files.readAllBytes(p),bad=original.clone();bad[bad.length-1]^=1;
            try{Files.write(p,bad);assertThrows(Exception.class,()->current(d,f));}finally{Files.write(p,original);}
            f.l.endpoints.getFirst().close();assertEquals("election decision endpoint closed",
                assertThrows(IllegalArgumentException.class,()->current(d,f)).getMessage());
        }
    }
    @Test void completedGrantInvalidatesDecisionButDuplicateGrantDoesNotRenewIt()throws Exception {
        var h=new V53ActivationProgressTest();h.temp=temp;
        try(var l=h.local()) {
            l.endpoint.handle(l.proposer(),V53ActivationProgressTest.heartbeat(l));l.base.clock.set(millis(20));
            MembershipElectionWait.Decision decision;
            try(var wait=V53ActivationProgressTest.waitFor(l,100)){decision=wait.awaitDecision();}
            assertTrue(decision.current(l.base.peer,l.endpoint,l.base.peerResources));
            var prepare=l.prepare();l.endpoint.handle(l.proposer(),prepare);assertFalse(decision.current(l.base.peer,l.endpoint,l.base.peerResources));
            l.base.clock.set(millis(40));
            try(var wait=V53ActivationProgressTest.waitFor(l,100)){decision=wait.awaitDecision();}
            l.base.clock.set(millis(45));l.endpoint.handle(l.proposer(),prepare);
            assertTrue(decision.current(l.base.peer,l.endpoint,l.base.peerResources));
        }
    }
}
