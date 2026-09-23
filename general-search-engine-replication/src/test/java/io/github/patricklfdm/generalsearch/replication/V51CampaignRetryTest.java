package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticProtocol.Kind.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationState.*;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Deterministic delivery order: fast unusable voter versus slower healthy voter. */
class V51CampaignRetryTest {
    @TempDir Path root;
    private static final int REQUEST = ReplicationBounds.defaults().requestTimeoutMillis();

    private static boolean slowHealthyBasis(AutomaticProtocol.Message message) {
        return message.response() && message.kind() == PREPARE && message.sender().equals("node-2");
    }
    private static boolean minorityInstall(AutomaticProtocol.Message message) {
        return !message.response() && message.kind() == INSTALL && message.recipient().equals("node-3");
    }
    private static void reject(V51ProtocolFixture group, AutomaticProtocol.Message request) {
        group.deliver(new AutomaticProtocol.Message(request.id(), request.kind(), request.recipient(), request.sender(),
                request.ballot(), true, false, AutomaticReplicationException.Reason.CAPACITY_EXCEEDED, group.node(3).promise()));
    }
    private static List<AutomaticProtocol.Message> prepares(V51ProtocolFixture group, long epoch) {
        return group.requests(PREPARE).stream().filter(m ->
                AutomaticRecords.number(m.ballot().value(), "epoch") == epoch).toList();
    }
    private static void releaseHealthyBasis(V51ProtocolFixture group) {
        var response = group.dropped.stream().filter(V51CampaignRetryTest::slowHealthyBasis).reduce((a, b) -> b).orElseThrow();
        group.deliver(response); group.pump();
    }
    private static void failedMinorityCampaign(V51ProtocolFixture group, boolean timeout) {
        group.loss = message -> {
            if (slowHealthyBasis(message)) return true;
            if (!minorityInstall(message)) return false;
            if (!timeout) reject(group, message);
            return true;
        };
        group.elect(1);
        assertEquals(timeout ? RECOVERING : UNAVAILABLE, group.node(1).view().state());
        if (timeout) { group.now += REQUEST; group.node(1).tick(group.now); group.pump(); }
        assertEquals(UNAVAILABLE, group.node(1).view().state());
        // This was a delayed healthy reply, not an absent voter. It cannot change
        // the already selected pair or revive the abandoned campaign.
        releaseHealthyBasis(group);
        assertEquals(UNAVAILABLE, group.node(1).view().state());
    }
    private void healthyPeerGetsNextCampaign(boolean timeout) throws Exception {
        try (var group = new V51ProtocolFixture(root)) {
            failedMinorityCampaign(group, timeout);
            long failedEpoch = group.node(1).view().promisedEpoch();
            group.elect(1);
            long epoch = group.node(1).view().promisedEpoch();
            assertTrue(epoch > failedEpoch);
            // Before the fix node 3 wins again and rejects INSTALL before the
            // complete healthy basis is delivered, indefinitely repeating failure.
            releaseHealthyBasis(group);
            assertEquals(LEADER_READY, group.node(1).view().state());
            assertEquals(List.of("node-2"), prepares(group, epoch).stream().map(AutomaticProtocol.Message::recipient).toList());
            assertEquals("node-2", group.requests(INSTALL).getLast().recipient());
            group.submit(1, 101, new byte[]{42});
            assertNull(group.outcomes.getLast().reason());
            assertEquals(2, group.node(1).view().publishedIndex());
        }
    }
    @Test void fasterCapacityRejectedPeerCannotStarveHealthyQuorum() throws Exception {
        healthyPeerGetsNextCampaign(false);
    }
    @Test void installationTimeoutAlsoGivesOtherPeerTheNextOpportunity() throws Exception {
        healthyPeerGetsNextCampaign(true);
    }
    @Test void unavailablePreferredPeerFallsBackWithoutExcludingRecoveredVoter() throws Exception {
        try (var group = new V51ProtocolFixture(root)) {
            failedMinorityCampaign(group, false);
            group.loss = V51CampaignRetryTest::slowHealthyBasis;
            group.elect(1);
            long epoch = group.node(1).view().promisedEpoch();
            assertEquals(CANDIDATE, group.node(1).view().state());
            assertEquals(List.of("node-2"), prepares(group, epoch).stream().map(AutomaticProtocol.Message::recipient).toList());
            group.now += REQUEST; group.node(1).tick(group.now); group.pump();
            assertEquals(LEADER_READY, group.node(1).view().state());
            assertEquals(List.of("node-2", "node-3"), prepares(group, epoch).stream().map(AutomaticProtocol.Message::recipient).toList());
            var fallback = group.requests(INSTALL).getLast();
            assertEquals("node-3", fallback.recipient());
            assertEquals(epoch, group.node(1).view().promisedEpoch());
            // Late preferred reply cannot replace the fallback selection.
            releaseHealthyBasis(group);
            assertEquals(fallback, group.requests(INSTALL).getLast());
            assertEquals(1, group.node(1).view().publishedIndex());
        }
    }
    @Test void higherBallotCancelsDeferredPrepare() throws Exception {
        try (var group = new V51ProtocolFixture(root)) {
            failedMinorityCampaign(group, false);
            group.loss = V51CampaignRetryTest::slowHealthyBasis;
            group.elect(1);
            long epoch = group.node(1).view().promisedEpoch();
            group.elect(2);
            assertEquals(LEADER_READY, group.node(2).view().state());
            assertEquals(FOLLOWER, group.node(1).view().state());
            group.now += REQUEST; group.node(1).tick(group.now); group.pump();
            assertEquals(List.of("node-2"), prepares(group, epoch).stream().map(AutomaticProtocol.Message::recipient).toList());
            assertEquals(FOLLOWER, group.node(1).view().state());
        }
    }
    @Test void campaignDeadlineNeverStartsDeferredPrepare() throws Exception {
        try (var group = new V51ProtocolFixture(root)) {
            failedMinorityCampaign(group, false);
            group.loss = V51CampaignRetryTest::slowHealthyBasis;
            group.elect(1);
            long epoch = group.node(1).view().promisedEpoch();
            group.now += AutomaticLeadershipPolicy.forBounds(ReplicationBounds.defaults()).operationTimeoutMillis();
            group.node(1).tick(group.now); group.pump();
            assertEquals(UNAVAILABLE, group.node(1).view().state());
            assertEquals(List.of("node-2"), prepares(group, epoch).stream().map(AutomaticProtocol.Message::recipient).toList());
            releaseHealthyBasis(group);
            assertEquals(UNAVAILABLE, group.node(1).view().state());
        }
    }
    @Test void lostActivationProofReplyRetainsProofThroughAlternativeQuorum() throws Exception {
        try (var group = new V51ProtocolFixture(root)) {
            group.loss = message -> message.response() && message.kind() == PROOF;
            group.elect(1);
            assertEquals(RECOVERING, group.node(1).view().state());
            assertEquals(1, group.node(1).view().provenIndex());
            var late = group.dropped.getLast();
            group.now += REQUEST; group.node(1).tick(group.now); group.pump();
            assertEquals(UNAVAILABLE, group.node(1).view().state());
            group.loss = message -> false;
            group.elect(1);
            long epoch = group.node(1).view().promisedEpoch();
            assertEquals(List.of("node-3"), prepares(group, epoch).stream().map(AutomaticProtocol.Message::recipient).toList());
            assertEquals(LEADER_READY, group.node(1).view().state());
            assertEquals(2, group.node(1).view().publishedIndex());
            group.deliver(late); group.pump();
            assertEquals(2, group.node(1).view().publishedIndex());
        }
    }
}
