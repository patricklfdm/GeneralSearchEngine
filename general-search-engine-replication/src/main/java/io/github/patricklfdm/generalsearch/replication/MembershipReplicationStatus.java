package io.github.patricklfdm.generalsearch.replication;

import java.time.Instant;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Variable-membership diagnostics. Neither progress nor reachability grants authority. */
public record MembershipReplicationStatus(
        ReplicationNodeId localNodeId, AutomaticReplicationState state,
        Optional<MembershipView> membership, Optional<ReplicationNodeId> observedLeader,
        long promisedCounter, Optional<MembershipIdentity> promisedBy, long activeCounter,
        long provenIndex, long appliedIndex, long applicationSequence, int pendingOperations,
        Optional<Instant> lastQuorumSuccess, List<ReplicationPeerStatus> peers) {
    public MembershipReplicationStatus {
        Objects.requireNonNull(localNodeId, "localNodeId"); Objects.requireNonNull(state, "state");
        Objects.requireNonNull(membership, "membership"); Objects.requireNonNull(observedLeader, "observedLeader");
        Objects.requireNonNull(promisedBy, "promisedBy"); Objects.requireNonNull(lastQuorumSuccess, "lastQuorumSuccess");
        position(promisedCounter); position(activeCounter); position(provenIndex); position(appliedIndex);
        position(applicationSequence);
        require(activeCounter <= promisedCounter && appliedIndex <= provenIndex, "status progress ordering");
        require(pendingOperations >= 0 && pendingOperations <= 64, "pending waiter bound");
        require((promisedCounter > 0) == promisedBy.isPresent(), "promise proposer mismatch");
        Objects.requireNonNull(peers, "peers"); require(peers.size() <= 5, "peer bound"); peers = List.copyOf(peers);
        var nodes = new HashSet<ReplicationNodeId>(); nodes.add(localNodeId);
        for (var peer : peers) require(nodes.add(peer.nodeId()), "duplicate or local peer");
        require((state == AutomaticReplicationState.LEADER_READY) == (activeCounter > 0), "active role mismatch");
        if (membership.isPresent()) {
            var view = membership.get();
            require(view.applied().index() == appliedIndex, "view/status cut mismatch");
            var voters = new HashSet<ReplicationNodeId>();
            for (var member : view.oldVoters()) voters.add(member.nodeId());
            for (var member : view.newVoters()) voters.add(member.nodeId());
            require(observedLeader.isEmpty() || voters.contains(observedLeader.get()), "leader outside view");
            require(view.localState() != MembershipLocalState.VOTER || voters.contains(localNodeId), "voter outside view");
            require(view.localState() != MembershipLocalState.LEARNER && view.localState() != MembershipLocalState.REMOVED
                    || !voters.contains(localNodeId), "nonvoter inside view");
            if (activeCounter > 0) require(activeCounter == promisedCounter
                    && promisedBy.orElseThrow().nodeId().equals(localNodeId)
                    && view.localState() == MembershipLocalState.VOTER && voters.contains(localNodeId)
                    && (view.oldVoters().contains(promisedBy.orElseThrow()) || view.newVoters().contains(promisedBy.orElseThrow()))
                    && provenIndex == appliedIndex, "unqualified active leader");
        } else {
            require(EnumSet.of(AutomaticReplicationState.STOPPED, AutomaticReplicationState.STARTING,
                    AutomaticReplicationState.FAILED, AutomaticReplicationState.CLOSED).contains(state), "missing current view");
            require(observedLeader.isEmpty(), "leader without view");
        }
        if (state == AutomaticReplicationState.STOPPED) require(membership.isEmpty() && promisedCounter == 0
                && provenIndex == 0 && appliedIndex == 0 && applicationSequence == 0 && pendingOperations == 0
                && lastQuorumSuccess.isEmpty() && peers.isEmpty(), "stopped handle claims runtime observations");
    }
}
