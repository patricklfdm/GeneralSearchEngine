package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticProtocol.Kind.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationState.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Virtual time over real stores: local admission must not masquerade as wire failure. */
class V51AutomaticAdmissionTest {
    @TempDir Path root;
    private static final ReplicationBounds BOUNDS=ReplicationBounds.defaults();
    private AutomaticProtocol.Message hold(V51ProtocolFixture group) {
        group.elect(1);group.loss=m->!m.response()&&m.kind()==ACCEPT;
        group.submit(1,81,new byte[]{7});return group.requests(ACCEPT).getLast();
    }
    private void tick(V51ProtocolFixture group,long time) {
        group.now=time;group.node(1).tick(time);group.pump();
    }
    @Test void repeatedLocalDeferralsKeepOneImmutableMessageAndDoNotExhaustWireAttempts() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            var original=hold(group);int count=group.requests(ACCEPT).size();
            for(int i=0;i<BOUNDS.maxRetryAttempts()+2;i++) {
                group.node(1).transportDeferred(original.id(),group.now);
                long retry=group.now+BOUNDS.retryBackoffMillis();
                tick(group,retry-1);assertEquals(count,group.requests(ACCEPT).size(),"must honor backoff");
                tick(group,retry);assertEquals(++count,group.requests(ACCEPT).size());
                assertSame(original,group.requests(ACCEPT).getLast());assertEquals(1,group.node(1).view().pendingExchanges());
                assertTrue(group.outcomes.isEmpty());assertEquals(LEADER_READY,group.node(1).view().state());
            }
            group.loss=m->false;group.deliver(original);group.pump();
            assertEquals(1,group.outcomes.size());assertNull(group.outcomes.getFirst().reason());
            assertEquals(2,group.node(1).view().publishedIndex());
        }
    }
    @Test void deferralCannotExtendTheOriginalDeadlineOrPublishALateReply() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            var request=hold(group);long deadline=group.now+BOUNDS.requestTimeoutMillis();
            tick(group,deadline-1);group.node(1).transportDeferred(request.id(),group.now);
            int count=group.requests(ACCEPT).size();tick(group,deadline);
            assertEquals(count,group.requests(ACCEPT).size());assertEquals(0,group.node(1).view().pendingExchanges());
            assertEquals(QUORUM_UNAVAILABLE,group.outcomes.getFirst().reason());
            assertEquals(INDETERMINATE,group.outcomes.getFirst().outcome());
            group.node(1).transportDeferred(request.id(),group.now);
            group.loss=m->false;group.deliver(request);group.pump();
            assertEquals(1,group.outcomes.size());assertEquals(1,group.node(1).view().publishedIndex());
        }
    }
    @Test void genuineFailuresStillExhaustTheirOriginalRetryBudgetAfterLocalDeferrals() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            var request=hold(group);long deadline=group.now+BOUNDS.requestTimeoutMillis();
            for(int attempt=0;attempt<=BOUNDS.maxRetryAttempts();attempt++) {
                if(attempt<3) {
                    group.node(1).transportDeferred(request.id(),group.now);
                    tick(group,group.now+BOUNDS.retryBackoffMillis());assertTrue(group.outcomes.isEmpty());
                }
                group.node(1).transportFailed(request.id(),group.now);group.pump();
                if(attempt<BOUNDS.maxRetryAttempts()) {
                    assertTrue(group.outcomes.isEmpty());tick(group,group.now+BOUNDS.retryBackoffMillis());
                }
            }
            assertTrue(group.now<deadline,"must fail on attempts, not elapsed time");
            assertEquals(1,group.outcomes.size());assertEquals(QUORUM_UNAVAILABLE,group.outcomes.getFirst().reason());
            assertEquals(1,group.node(1).view().publishedIndex());
        }
    }
    @Test void cancellationFencingAndCloseRetireDeferredWork() throws Exception {
        for(String boundary:List.of("cancel","fence","close"))try(var group=new V51ProtocolFixture(java.nio.file.Files.createDirectory(root.resolve(boundary)))) {
            var request=hold(group);group.node(1).transportDeferred(request.id(),group.now);
            int count=group.requests(ACCEPT).size();
            switch(boundary) {
                case "cancel" -> group.node(1).cancel(81,group.now);
                case "fence" -> group.node(1).observePromise(AutomaticRecords.decode(V51StorageFixture.promise(group.manifest,20),"PROMISE"));
                case "close" -> group.node(1).quiesce();
            }
            group.node(1).transportDeferred(request.id(),group.now);tick(group,group.now+BOUNDS.retryBackoffMillis());
            assertEquals(count,group.requests(ACCEPT).size());assertEquals(0,group.node(1).view().pendingExchanges());
            assertEquals(1,group.outcomes.size());assertEquals(INDETERMINATE,group.outcomes.getFirst().outcome());
            group.loss=m->false;group.deliver(request);group.pump();
            assertEquals(1,group.node(1).view().publishedIndex());assertEquals(1,group.outcomes.size());
        }
    }
    @Test void peerCapacityRejectionStillFailsInsteadOfBecomingLocalBackpressure() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            var request=hold(group);
            group.deliver(new AutomaticProtocol.Message(request.id(),request.kind(),request.recipient(),request.sender(),
                    request.ballot(),true,false,CAPACITY_EXCEEDED,request.ballot()));group.pump();
            assertEquals(1,group.outcomes.size());assertEquals(QUORUM_UNAVAILABLE,group.outcomes.getFirst().reason());
            assertEquals(0,group.node(1).view().pendingExchanges());assertEquals(1,group.node(1).view().publishedIndex());
        }
    }
}
