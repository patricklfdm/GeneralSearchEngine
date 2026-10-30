package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53JointContinuationTest {
    @TempDir Path temp;
    @Test void coordinatorOwnsTheRequestedScratchRootBeforeNativePrelude()throws Exception {
        var helper=new V53JoiningRetentionCampaignTest();helper.temp=temp;
        try(var l=helper.new Local(3,"ADD");
            var transport=new MembershipTransport(l.owners.getFirst(),V53SourceExchangeTest.bounds(),l.pools.getFirst(),
                    (peer,request)->{throw new AssertionError("conditional history must not send");},MembershipTransport.Events.NONE)) {
            var owner=l.owners.getFirst();var pool=l.pools.getFirst();var usage=pool.usage();
            var before=V53ReplayFilesTest.files(l.directories.getFirst());Path scratch=temp.resolve("joint-scratch");
            assertFalse(Files.exists(scratch));
            try(var continuation=new MembershipJointContinuation<>(owner,l.endpoints.getFirst(),pool,V53SourceExchangeTest.bounds(),transport,
                    scratch,l.clock::get,V53SourceExchangeTest.BUDGET,2,builder().configuration(),
                    storage(temp.resolve("unused-materialization"),2),MembershipRoundDriver.Events.NONE,(e,r,v)->{})) {
                var error=assertThrows(IllegalArgumentException.class,continuation::start);
                assertEquals("native generation maintenance owner required",error.getMessage());
                assertEquals(MembershipJointContinuation.State.FAILED,continuation.state());
            }
            // Conditional originals cannot pass the native maintenance gate, but
            // the coordinator must first create exactly the caller's owned scope.
            assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(scratch,8));
            assertEquals(before,V53ReplayFilesTest.files(l.directories.getFirst()));assertEquals(usage,pool.usage());
            try(var reopened=owner.openScratch(scratch,MembershipScratch.Role.OUTGOING,pool,e->{})) {
                assertEquals(scratch.toAbsolutePath(),reopened.directory());
            }
            assertEquals(usage,pool.usage());
        }
    }
    @Test void preparationDrainsBeforeActivationReusesItsOriginalScratchOwner()throws Exception {
        var helper=new V53JoiningRetentionCampaignTest();helper.temp=temp;
        try(var l=helper.new Local(3,"ADD")) {
            var owner=l.owners.getFirst();var pool=l.pools.getFirst();var usage=pool.usage();
            var before=V53ReplayFilesTest.files(l.directories.getFirst());Path scratch=temp.resolve("handoff");
            var link=l.link.get();
            try(var prepared=new MembershipJoiningRetentionCampaign(owner,l.endpoints.getFirst(),pool,V53SourceExchangeTest.bounds(),link,()->{},
                    scratch,l.clock::get,0,V53SourceExchangeTest.BUDGET,V53DeclarationsTest.node(6))) {
                assertThrows(ReplicationException.class,()->new MembershipActivationDriver(owner,l.endpoints.getFirst(),pool,V53SourceExchangeTest.bounds(),
                        link,List.of(),List.of(),scratch,l.clock::get,V53SourceExchangeTest.BUDGET,2));
            }
            var marker=Files.readAllBytes(scratch.resolve("owner.json"));
            try(var active=new MembershipActivationDriver(owner,l.endpoints.getFirst(),pool,V53SourceExchangeTest.bounds(),link,List.of(),List.of(),
                    scratch,l.clock::get,V53SourceExchangeTest.BUDGET,2)) {
                assertArrayEquals(marker,Files.readAllBytes(scratch.resolve("owner.json")));
            }
            assertEquals(Set.of("owner.json","scope.lock"),MembershipBasisSources.children(scratch,8));
            assertEquals(before,V53ReplayFilesTest.files(l.directories.getFirst()));assertEquals(usage,pool.usage());
        }
    }
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
