package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticProtocol.Kind.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationState.*;
import static org.junit.jupiter.api.Assertions.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V51AutomaticProtocolTest {
    @TempDir Path root;
    Record ballot(byte[] manifest,long epoch) {return decode(V51StorageFixture.promise(manifest,epoch),"PROMISE");}
    @Test void timerElectsAndPublicationMustCompleteBeforeReadiness() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.holdPublication=true;group.elect(1);
            assertEquals(RECOVERING,group.node(1).view().state());
            assertEquals(1,group.node(1).view().provenIndex());assertEquals(0,group.node(1).view().publishedIndex());
            assertEquals(1,group.held.size());group.holdPublication=false;group.releaseApplications();
            assertEquals(LEADER_READY,group.node(1).view().state());
            assertEquals(1,group.node(1).view().publishedIndex());
            var snapshot=decode(unbase(group.publications.getFirst().get("snapshot")),"SNAPSHOT");
            assertEquals(snapshot.value().get("baseSequence"),snapshot.value().get("applicationSequence"));
        }
    }
    @Test void writeCompletionRequiresBothProofAcknowledgementsAndLocalPublication() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);group.loss=m->m.response()&&m.kind()==PROOF;
            group.node(1).submit(11,1,new byte[]{42},group.now);group.pump();
            assertTrue(group.outcomes.isEmpty());assertEquals(2,group.node(1).view().provenIndex());
            group.holdPublication=true;group.loss=m->false;group.deliver(group.dropped.getLast());group.pump();
            assertTrue(group.outcomes.isEmpty());group.holdPublication=false;group.releaseApplications();
            assertEquals(11,group.outcomes.getFirst().request());assertEquals(2,group.outcomes.getFirst().index());
            assertNull(group.outcomes.getFirst().reason());
        }
    }
    @Test void entryChosenWithoutProofSurvivesAnotherCandidatesPrepareQuorum() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);group.loss=m->m.response()&&m.kind()==ACCEPT;
            group.node(1).submit(12,1,new byte[]{73},group.now);group.pump();
            Record original=(Record)group.requests(ACCEPT).getLast().payload();
            byte[] carried=unbase(original.value().get("entry"));assertTrue(group.outcomes.isEmpty());
            group.stop(1);group.loss=m->false;group.elect(3);
            assertEquals(LEADER_READY,group.node(3).view().state());assertEquals(3,group.node(3).view().publishedIndex());
            var carriedAgain=group.requests(ACCEPT).stream().filter(m->m.sender().equals("node-3"))
                    .map(m->(Record)m.payload()).filter(a->number(decode(unbase(a.value().get("entry")),"ENTRY").value(),"index")==2).findFirst().orElseThrow();
            assertArrayEquals(carried,unbase(carriedAgain.value().get("entry")));
            assertTrue(number(carriedAgain.value(),"epoch")>number(original.value(),"epoch"));
            var fresh=decode(unbase(((Record)group.requests(ACCEPT).getLast().payload()).value().get("entry")),"ENTRY");
            assertEquals(9L,number(fresh.value(),"operation"));assertEquals(group.node(3).view().promisedEpoch(),number(fresh.value(),"originEpoch"));
        }
    }
    @Test void higherPrepareIsServicedWhileAnOlderCampaignWaitsForNetwork() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);group.loss=m->m.response()&&m.kind()==ACCEPT;
            group.node(1).submit(13,1,new byte[]{8},group.now);group.pump();
            var late=group.dropped.getLast();
            group.now=31_000;group.node(2).tick(group.now);group.pump();
            assertEquals(6,group.node(1).view().promisedEpoch());assertNotEquals(LEADER_READY,group.node(1).view().state());
            assertEquals(AutomaticReplicationException.Outcome.INDETERMINATE,group.outcomes.getFirst().outcome());
            int published=group.node(1).view().publishedIndex();group.deliver(late);group.pump();
            assertEquals(published,group.node(1).view().publishedIndex());
        }
    }
    @Test void lostAcceptAndProofRepliesRetryExactRecordsWithoutDuplicateRows() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);
            for(var kind:List.of(ACCEPT,PROOF)) {
                group.loss=m->m.response()&&m.kind()==kind;
                group.node(1).submit(kind.ordinal()+100,1,new byte[]{3},group.now);group.pump();
                var lost=group.dropped.getLast();String file=kind==ACCEPT?"accepted.gsr":"proofs.gsr";
                byte[] before=Files.readAllBytes(root.resolve("node-2").resolve(file));
                group.loss=m->false;group.node(1).transportFailed(lost.id(),group.now);
                group.now+=250;group.node(1).tick(group.now);group.pump();
                assertArrayEquals(before,Files.readAllBytes(root.resolve("node-2").resolve(file)));
                assertNull(group.outcomes.getLast().reason());
            }
        }
    }
    @Test void hiddenProofRemainsProtectedAfterOriginatingLeaderStops() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);group.loss=m->m.response()&&m.kind()==PROOF;
            group.node(1).submit(14,1,new byte[]{9},group.now);group.pump();
            assertEquals(2,group.node(2).view().provenIndex());assertTrue(group.outcomes.isEmpty());
            group.stop(1);group.loss=m->false;group.elect(3);
            assertEquals(3,group.node(3).view().publishedIndex());assertEquals(LEADER_READY,group.node(3).view().state());
            var snapshot=decode(unbase(group.publications.getLast().get("snapshot")),"SNAPSHOT");
            assertEquals(9,unbase(snapshot.value().get("application"))[unbase(snapshot.value().get("application")).length-1]);
        }
    }
    @Test void retainedRestartIsFollowerAndItsNextCampaignUsesAHigherEpoch() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);long old=group.node(1).view().promisedEpoch();group.stop(1);
            group.open(1,AutomaticStore.Faults.NONE);group.pump();
            assertEquals(FOLLOWER,group.node(1).view().state());assertEquals(0,group.node(1).view().publishedIndex());
            group.elect(1);assertEquals(LEADER_READY,group.node(1).view().state());
            assertTrue(group.node(1).view().promisedEpoch()>old);
        }
    }
    @Test void repeatedEqualPrefixElectionsDoNotConsumeGenerationSlots() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            for(int attempt=0;attempt<5;attempt++) {
                group.elect(1);assertEquals(LEADER_READY,group.node(1).view().state());
                group.stop(1);group.open(1,AutomaticStore.Faults.NONE);group.pump();
            }
            assertFalse(Files.exists(root.resolve("node-1/current.gsr")));
            assertEquals(5,group.node(1).view().provenIndex());
        }
    }
    @Test void healthyIdleHeartbeatsSuppressRepeatedElections() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);long epoch=group.node(1).view().promisedEpoch();group.advance(90_000);
            for(var node:group.nodes.values())assertEquals(epoch,node.view().promisedEpoch());
            assertEquals(LEADER_READY,group.node(1).view().state());
        }
    }
    @Test void replayedOrNonprogressingRecoveryHeartbeatsDoNotSuppressElection() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);var promise=ballot(group.manifest,2);
            // Match the actual incarnation from an emitted request, not a test-created ballot.
            promise=group.requests(PREPARE).getFirst().ballot();
            for(int i=0;i<4;i++) {
                group.now+=5000;
                group.node(3).receive(new AutomaticProtocol.Message(900+i,HEARTBEAT,"node-1","node-3",promise,false,true,
                        new AutomaticProtocol.Pulse(i+1,false,1,0),null),group.now);group.pump();
            }
            group.now+=3000;group.node(3).tick(group.now);group.pump();
            assertTrue(group.node(3).view().promisedEpoch()>2);
        }
    }
    @Test void noQuorumNeverActivatesAndFiniteExchangeDeadlinesRetireCampaigns() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.loss=m->!m.response();group.elect(1);
            assertEquals(CANDIDATE,group.node(1).view().state());group.advance(21_000);
            assertEquals(UNAVAILABLE,group.node(1).view().state());assertTrue(group.publications.isEmpty());
            assertEquals(0,group.node(1).view().pendingExchanges());
            group.node(1).submit(15,1,new byte[]{1},group.now);group.pump();
            assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,group.outcomes.getFirst().outcome());
        }
    }
    @Test void forgedReceiptDoesNotAdvanceProofOrPublish() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);group.loss=m->m.response()&&m.kind()==ACCEPT;
            group.node(1).submit(16,1,new byte[]{1},group.now);group.pump();var reply=group.dropped.getLast();
            group.deliver(new AutomaticProtocol.Message(reply.id(),reply.kind(),reply.sender(),reply.recipient(),reply.ballot(),true,true,"0".repeat(64),reply.promised()));group.pump();
            assertEquals(FAILED,group.node(1).view().state());assertEquals(1,group.node(1).view().provenIndex());
            assertEquals(AutomaticReplicationException.Outcome.INDETERMINATE,group.outcomes.getFirst().outcome());
        }
    }
    @Test void publicationAfterStepDownCannotRestoreReadiness() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.holdPublication=true;group.elect(1);group.now=31_000;group.node(2).tick(group.now);group.pump();
            group.holdPublication=false;group.releaseApplications();
            assertNotEquals(LEADER_READY,group.node(1).view().state());
            assertEquals(0,group.node(1).view().publishedIndex());
        }
    }
    @Test void closeRetainsOwnershipUntilApplicationActionsQuiesce() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.holdPublication=true;group.elect(1);
            assertThrows(AutomaticReplicationException.class,()->group.node(1).close());
            assertThrows(AutomaticReplicationException.class,()->AutomaticStore.open(root.resolve("node-1"),group.manifest,"node-1",ReplicationBounds.defaults(),AutomaticStore.Faults.NONE));
            group.holdPublication=false;group.releaseApplications();group.stop(1);
            try(var reopened=AutomaticStore.open(root.resolve("node-1"),group.manifest,"node-1",ReplicationBounds.defaults(),AutomaticStore.Faults.NONE)) {
                assertEquals(1,reopened.status().get("provenThrough"));
            }
        }
    }
    @Test void epochArithmeticIsRankedStrictlyNewerAndNeverWraps() {
        for(long observed:List.of(1L,2L,4L,5L,123456L))for(int rank=0;rank<3;rank++) {
            long next=AutomaticProtocol.nextEpoch(observed,rank);assertTrue(next>observed);assertEquals(rank,(next-2)%3);
        }
        assertThrows(AutomaticReplicationException.class,()->AutomaticProtocol.nextEpoch(Long.MAX_VALUE,2));
    }
    @Test void lateExactInstallRetryDoesNotRollBackSubsequentCommits() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);var install=group.requests(INSTALL).getFirst();
            group.node(1).submit(17,1,new byte[]{7},group.now);group.pump();
            byte[] accepted=Files.readAllBytes(root.resolve("node-2/accepted.gsr"));
            group.deliver(install);group.pump();
            assertEquals(2,group.node(2).view().provenIndex());assertNotEquals(FAILED,group.node(2).view().state());
            assertArrayEquals(accepted,Files.readAllBytes(root.resolve("node-2/accepted.gsr")));
        }
    }
    @Test void cancellationAfterAcceptCannotReportNotSubmittedOrReviveFromLateReply() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);group.loss=m->m.response()&&m.kind()==ACCEPT;
            group.node(1).submit(18,1,new byte[]{7},group.now);group.pump();var late=group.dropped.getLast();
            group.node(1).cancel(18,group.now);group.pump();group.deliver(late);group.pump();
            assertEquals(1,group.outcomes.size());assertEquals(AutomaticReplicationException.Outcome.INDETERMINATE,group.outcomes.getFirst().outcome());
            assertEquals(1,group.node(1).view().publishedIndex());
        }
    }
    @Test void publicationAfterDeadlineCannotActivateEvenWithoutAnInterveningTick() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.holdPublication=true;group.elect(1);group.now=35_000;
            group.holdPublication=false;group.releaseApplications();
            assertEquals(UNAVAILABLE,group.node(1).view().state());assertEquals(0,group.node(1).view().publishedIndex());
        }
    }
    @Test void carriedValueAndFreshActivationShareTheOriginalCampaignDeadline() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);group.loss=m->m.response()&&m.kind()==ACCEPT;
            group.node(1).submit(20,1,new byte[]{7},group.now);group.pump();
            group.stop(1);group.loss=m->false;group.holdPublication=true;group.elect(3);
            long started=group.now;group.now=started+10_000;
            var carried=group.held.removeFirst();group.application(carried.getKey(),carried.getValue());group.pump();
            assertEquals(RECOVERING,group.node(3).view().state());assertEquals(1,group.held.size());
            group.now=started+20_000;group.holdPublication=false;group.releaseApplications();
            assertEquals(UNAVAILABLE,group.node(3).view().state());assertEquals(2,group.node(3).view().publishedIndex());
        }
    }
    @Test void applicationFailureCannotBecomeClientSuccess() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.elect(1);group.holdReconstruction=true;
            group.node(1).submit(19,1,new byte[]{7},group.now);group.pump();
            var task=group.held.removeFirst();var rebuild=(AutomaticProtocol.Reconstruct)task.getValue();
            group.node(1).reconstructed(rebuild.id(),null,new IllegalStateException("callback failed"),group.now);group.pump();
            assertEquals(FAILED,group.node(1).view().state());assertEquals(1,group.node(1).view().publishedIndex());
            assertEquals(AutomaticReplicationException.Outcome.INDETERMINATE,group.outcomes.getLast().outcome());
        }
    }
    @Test void ambiguousForceQuarantinesTheProtocolAndRetainedOwner() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.stop(1);group.open(1,new AutomaticStore.Faults() {
                public void at(String event) throws java.io.IOException {
                    if(event.equals("ACCEPT_AFTER_FORCE"))throw new java.io.IOException("injected force ambiguity");
                }
            });group.pump();group.elect(1);
            assertEquals(FAILED,group.node(1).view().state());assertTrue(group.publications.isEmpty());
            assertThrows(AutomaticReplicationException.class,()->AutomaticStore.open(root.resolve("node-1"),group.manifest,"node-1",ReplicationBounds.defaults(),AutomaticStore.Faults.NONE));
        }
    }
}
