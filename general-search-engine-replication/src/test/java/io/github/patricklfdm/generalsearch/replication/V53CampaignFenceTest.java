package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53HeartbeatTest.*;

class V53CampaignFenceTest {
    @TempDir Path temp;
    @Test void authenticatedHigherObservationHasTypedLossWithoutAuthorityWritesOrWriterWait()throws Exception {
        var h=new V53ActivationDriverTest();h.temp=temp;
        try(var l=h.local(new AtomicLong(),1000);var workers=Executors.newVirtualThreadPerTaskExecutor()) {
            var owner=l.owners.getFirst();var state=owner.discoveryState(l.budgets.getFirst());var before=files(l);
            owner.checkCampaignWait(state.context().authority(),state.ballot());
            l.endpoints.getFirst().handle(l.group.identities.get(1),request(l,100,false));
            synchronized(owner) {
                var result=workers.submit(()->assertThrows(MembershipCampaignLost.class,()->owner.checkCampaignWait(state.context().authority(),state.ballot())));
                assertEquals(MembershipCampaignLost.Reason.HIGHER_BALLOT,result.get(2,TimeUnit.SECONDS).reason);
            }
            assertEquals(before,files(l));
            assertEquals("higher ballot observed; fresh campaign required",assertThrows(IllegalArgumentException.class,
                ()->owner.checkActivationWait(state.context().authority(),state.ballot())).getMessage());
        }
    }
    @Test void futureOrMissingOriginalFenceIsNotTreatedAsObservedHigherBallot()throws Exception {
        var h=new V53ActivationDriverTest();h.temp=temp;
        try(var l=h.local(new AtomicLong(),1000)) {
            var owner=l.owners.getFirst();var state=owner.discoveryState(l.budgets.getFirst());
            var future=object(request(l,100,false).value().get("ballot"));
            assertEquals("campaign fence does not match original ballot",assertThrows(IllegalArgumentException.class,
                ()->owner.checkCampaignWait(state.context().authority(),future)).getMessage());
            assertThrows(NullPointerException.class,()->owner.checkCampaignWait(state.context().authority(),null));
            assertEquals(state,owner.discoveryState(l.budgets.getFirst()));
        }
    }
    @Test void viewChangeHintCannotBypassOriginalChecksOrClosedOwner()throws Exception {
        var h=new V53ActivationDriverTest();h.temp=temp;
        try(var l=h.local(new AtomicLong(),1000)) {
            var owner=l.owners.getFirst();var state=owner.discoveryState(l.budgets.getFirst());var before=files(l);
            assertEquals(MembershipCampaignLost.Reason.VIEW_CHANGED,assertThrows(MembershipCampaignLost.class,
                ()->owner.checkCampaignWait("0".repeat(64),state.ballot())).reason);
            assertEquals(before,files(l));owner.close();
            assertEquals("grant journal closed or failed",assertThrows(IllegalArgumentException.class,
                ()->owner.checkCampaignWait(state.context().authority(),state.ballot())).getMessage());
        }
    }
}
