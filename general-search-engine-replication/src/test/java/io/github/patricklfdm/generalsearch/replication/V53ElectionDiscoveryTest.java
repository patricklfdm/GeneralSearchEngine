package io.github.patricklfdm.generalsearch.replication;

import java.io.UncheckedIOException;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.Path;
import static org.junit.jupiter.api.Assertions.*;

/** Incoming election activity before our first grant is still follower work.
 * Do not spend the finite recovery rounds on a campaign we have not started. */
class V53ElectionDiscoveryTest {
    @TempDir Path temp;

    @Test void higherContactDuringDiscoveryDoesNotSpendCampaignRecoveryRounds()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE);
                var automatic=round.automaticOwner(V53ElectionWaitTest.POLICY)) {
            var injected=new AtomicInteger();
            n.beforeSend.set(request->{
                if(!request.kind().equals("STATUS_PROBE") || injected.get()>=4)return;
                int next=injected.incrementAndGet();
                try {
                    var owner=n.owners.getFirst();var peer=n.owners.get(1).activationIdentity();
                    var heartbeat=V53HeartbeatTest.request(owner.activationContext(),peer,owner.activationIdentity(),100+next,true);
                    n.endpoints.getFirst().handle(peer,heartbeat);
                }catch(java.io.IOException error){throw new UncheckedIOException(error);}
            });
            assertEquals("PUBLISH_ACK",automatic.start().await(120,TimeUnit.SECONDS).kind());
            assertEquals(4,injected.get());assertEquals(1,automatic.rounds());assertTrue(automatic.losses().isEmpty());
            assertEquals(1,n.events.stream().filter(e->e.get("node").equals("node-1") && e.get("event").equals("ALLOCATOR_BEFORE_RETURN")).count());
        }
    }
    @Test void sameBallotHeartbeatDuringDiscoveryRequiresFreshScanBeforeGrant()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE)) {
            var owner=n.owners.getFirst();var peer=n.owners.get(1).activationIdentity();
            var heartbeat=V53HeartbeatTest.request(owner.activationContext(),peer,owner.activationIdentity(),100,true);
            n.endpoints.getFirst().handle(peer,heartbeat);
            var queries=new AtomicInteger();var beforeGrant=new AtomicInteger(-1);
            n.beforeSend.set(request->{
                if(request.kind().equals("PREPARE"))beforeGrant.compareAndSet(-1,queries.get());
                if(request.kind().equals("STATUS_PROBE") && queries.incrementAndGet()==2)try {
                    // Same actual root/fence, with a newer accepted arrival.
                    n.endpoints.getFirst().handle(peer,heartbeat);
                }catch(java.io.IOException error){throw new UncheckedIOException(error);}
            });
            assertEquals("PUBLISH_ACK",round.startAutomatic(V53ElectionWaitTest.POLICY,(a,b)->a).kind());
            assertEquals(4,beforeGrant.get(),"fresh discovery follows the renewed contact wait");
        }
    }
    @Test void repeatedPreGrantContactCannotRenewOriginalLifetime()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null);var round=helper.driver(n,MembershipRoundDriver.Events.NONE)) {
            n.beforeSend.set(request->{
                if(!request.kind().equals("STATUS_PROBE"))return;
                try {
                    var owner=n.owners.getFirst();var peer=n.owners.get(1).activationIdentity();
                    n.endpoints.getFirst().handle(peer,V53HeartbeatTest.request(owner.activationContext(),peer,owner.activationIdentity(),100,true));
                    n.offset.set(V53NativeDispatchTest.BUDGET);
                }catch(java.io.IOException error){throw new UncheckedIOException(error);}
            });
            var failure=assertThrows(IllegalArgumentException.class,()->round.startAutomatic(V53ElectionWaitTest.POLICY,(a,b)->a));
            assertTrue(failure.getMessage().contains("original deadline"));
            assertTrue(n.events.stream().noneMatch(e->e.get("node").equals("node-1") && e.get("event").equals("ALLOCATOR_BEFORE_RETURN")));
            assertEquals(MembershipRoundDriver.State.FAILED,round.state());
        }
    }
}
