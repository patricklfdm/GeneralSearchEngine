package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53JointContinuationTest {
    @TempDir Path temp;
    @Test void everyJointProfileDerivesJoiningIdentityButStableOrForeignCannotCoordinate()throws Exception {
        for(var profile:V53SelectionTest.PROFILES) {
            var fixture=new V53CurrentGenerationFixture(profile.getKey(),new V53CapsuleFixture(profile.getKey(),profile.getValue(),6));
            var context=fixture.admitted.context;
            var joining=MembershipJointContinuation.joining(context,V53DeclarationsTest.node(1));
            assertEquals(!profile.getValue().equals("REMOVE"),joining.isPresent());
            if(joining.isPresent())assertEquals(V53DeclarationsTest.node(6),joining.get());
            assertThrows(IllegalArgumentException.class,()->MembershipJointContinuation.joining(context,V53DeclarationsTest.node(6)));
        }
    }
    @Test void stableNativeOwnerRefusesJointEntryBeforeAllocatingOrSending()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null)) {
            var owner=n.owners.getFirst();var pool=n.resources.getFirst();var usage=pool.usage();var files=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            try(var continuation=new MembershipJointContinuation<>(owner,n.endpoints.getFirst(),pool,n.bounds,n.transports.getFirst(),temp.resolve("joint"),
                    System::nanoTime,V53NativeDispatchTest.BUDGET,2,builder().configuration(),n.f.request.targets().getFirst().materialization(),
                    MembershipRoundDriver.Events.NONE,(event,record,voters)->{})) {
                assertThrows(IllegalArgumentException.class,continuation::start);assertEquals(MembershipJointContinuation.State.FAILED,continuation.state());
                assertThrows(IllegalArgumentException.class,continuation::readiness);assertThrows(IllegalArgumentException.class,continuation::start);
                assertEquals(files,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
            }
            assertEquals(usage,pool.usage());
        }
    }
    @Test void closeOrExpiredOriginalClockPreventsAnyPreparation()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null)) {
            var owner=n.owners.getFirst();var pool=n.resources.getFirst();var usage=pool.usage();
            var files=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            for(boolean close:List.of(false,true)) {
                var clock=new AtomicLong();
                try(var continuation=new MembershipJointContinuation<>(owner,n.endpoints.getFirst(),pool,n.bounds,n.transports.getFirst(),
                        temp.resolve("unused-"+close),()->clock.getAndAdd(V53NativeDispatchTest.BUDGET),V53NativeDispatchTest.BUDGET,2,
                        builder().configuration(),n.f.request.targets().getFirst().materialization(),MembershipRoundDriver.Events.NONE,(event,record,voters)->{})) {
                    if(close)continuation.close();
                    assertThrows(IllegalArgumentException.class,continuation::start);
                    assertEquals(close?MembershipJointContinuation.State.CLOSED:MembershipJointContinuation.State.FAILED,continuation.state());
                    assertThrows(IllegalArgumentException.class,continuation::readiness);
                    assertEquals(files,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
                }
                assertEquals(usage,pool.usage());
            }
            assertTrue(n.events.stream().noneMatch(row->"PROMISE_FORCED".equals(row.get("event"))));
        }
    }
}
