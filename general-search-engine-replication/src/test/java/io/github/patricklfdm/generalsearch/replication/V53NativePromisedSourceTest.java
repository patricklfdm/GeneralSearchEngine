package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Native copied history keeps the original control, grant and receive boundaries. */
class V53NativePromisedSourceTest {
    @TempDir Path temp;
    V53PromisedSourceTest helper(){var helper=new V53PromisedSourceTest();helper.temp=temp;return helper;}
    static void offer(V53PromisedSourceTest.Local local)throws Exception {
        local.campaign.promised(local.identity(),local.reply,local.received,local.pull,List.of());
    }
    @Test void completedPublishedCopySelectsWithoutManufacturingOldObservations()throws Exception {
        try(var l=helper().new Local("published")) {
            var packet=l.received.packet();
            assertThrows(IllegalArgumentException.class,()->MembershipCapsule.verify(l.f.original.seed.rootRecord,packet,l.received.images(),Set.of()));
            offer(l);assertEquals(MembershipActivation.State.INSTALLING,l.campaign.state());
            var selected=l.leader.originalSelection().orElseThrow();
            assertThrows(IllegalArgumentException.class,l.campaign::votingSelection);
            l.received.close();assertThrows(Exception.class,l.campaign::sources);
            assertArrayEquals(selected.bytes(),l.leader.originalSelection().orElseThrow().bytes());
            assertEquals(MembershipActivation.State.ABANDONED,l.campaign.state());
        }
    }
    @Test void nativeHistoryDoesNotReplaceTheCorrelatedPromise()throws Exception {
        try(var l=helper().new Local("genesis")) {
            var before=V53ReplayFilesTest.files(l.f.request.targets().getFirst().replicaDirectory());
            for(var altered:List.of(V53ActivationTest.changed(l.reply,"trace",UUID.randomUUID().toString()),
                    V53ActivationTest.changed(l.reply,"sequence",99L),
                    V53ActivationTest.changed(l.reply,"sender",MembershipBootstrapSeed.identity(l.f.request.targets().get(2).identity())))) {
                assertThrows(IllegalArgumentException.class,()->l.campaign.promised(l.identity(),altered,l.received,l.pull,List.of()));
                assertEquals(before,V53ReplayFilesTest.files(l.f.request.targets().getFirst().replicaDirectory()));
            }
            offer(l);assertEquals(MembershipActivation.State.INSTALLING,l.campaign.state());
        }
    }
    @Test void changedOriginalGrantCannotSelectEvenWithACompleteValidCopy()throws Exception {
        try(var l=helper().new Local("genesis")) {
            var reply=V53ActivationTest.changed(l.reply,"payload",Map.of("basis","0".repeat(64)));
            assertThrows(IllegalArgumentException.class,()->l.campaign.promised(l.identity(),reply,l.received,l.pull,List.of()));
            assertTrue(l.leader.originalSelection().isEmpty());assertEquals(MembershipActivation.State.ABANDONED,l.campaign.state());
        }
    }
    @Test void expiredClosedOrFencedSourceCannotBecomeASelection()throws Exception {
        for(String mode:List.of("expired","closed","fenced"))try(var l=helper().new Local("genesis")) {
            if(mode.equals("expired"))l.clock.set(V53SourceExchangeTest.BUDGET);
            else if(mode.equals("closed"))l.pull.close();
            else {var ballot=new TreeMap<>(l.campaign.ballot());ballot.put("counter",number(ballot.get("counter"))+1);l.leader.observeCurrent(ballot);}
            var before=V53ReplayFilesTest.files(l.f.request.targets().getFirst().replicaDirectory());
            assertThrows(Exception.class,()->offer(l));assertTrue(l.leader.originalSelection().isEmpty());
            assertEquals(before,V53ReplayFilesTest.files(l.f.request.targets().getFirst().replicaDirectory()));
        }
    }
    @Test void anotherCompletedPullCannotStandInForTheOriginalReceivedGrant()throws Exception {
        var helper=helper();try(var a=helper.new Local("genesis");var b=helper.new Local("genesis")) {
            assertEquals("native promised source original grant changed",assertThrows(IllegalArgumentException.class,
                    ()->a.campaign.promised(a.identity(),a.reply,a.received,b.pull,List.of())).getMessage());
            assertTrue(a.leader.originalSelection().isEmpty());assertEquals(MembershipActivation.State.ABANDONED,a.campaign.state());
        }
    }
    @Test void originalAcceptedTailStillPrecedesAnyFreshBarrier()throws Exception {
        try(var l=helper().new Local("tail")) {
            offer(l);var source=l.campaign.sources().stream().filter(s->s.owner.equals(l.identity())).findFirst().orElseThrow();
            assertArrayEquals(l.entry.bytes(),source.entry.bytes());
            assertEquals(l.entry.digest(),l.leader.originalSelection().orElseThrow().value().get("nextEntry"));
            assertThrows(IllegalArgumentException.class,l.campaign::votingSelection);
        }
    }
}
