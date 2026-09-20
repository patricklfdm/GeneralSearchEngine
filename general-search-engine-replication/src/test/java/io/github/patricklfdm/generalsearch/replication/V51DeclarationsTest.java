package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class V51DeclarationsTest {
    private static final ReplicationNodeId SELF=new ReplicationNodeId("node-1");
    private static final List<ReplicationPeerStatus> PEERS=List.of(
            new ReplicationPeerStatus(new ReplicationNodeId("node-2"),false,0,0,0,Optional.empty()),
            new ReplicationPeerStatus(new ReplicationNodeId("node-3"),false,0,0,0,Optional.empty()));
    @Test void policyUsesBoundedArithmeticAndRequestTimeoutCrossRules() {
        assertEquals(new AutomaticLeadershipPolicy(5000,15000,25000,20000),AutomaticLeadershipPolicy.forBounds(ReplicationBounds.defaults()));
        for(int[] bad:new int[][]{{0,1,2,1},{1,2,4,1},{1,3,3,1},{300001,900003,1500005,1200000},
                {5000,Integer.MAX_VALUE,Integer.MAX_VALUE,1},{5000,15000,25000,1200001}}) {
            assertThrows(IllegalArgumentException.class,()->new AutomaticLeadershipPolicy(bad[0],bad[1],bad[2],bad[3]));
        }
        assertDoesNotThrow(()->new AutomaticLeadershipPolicy(300000,900000,1500000,1200000));
    }
    @Test void statusCannotInventAPromiseReadyRoleOrPeer() {
        assertDoesNotThrow(()->status(AutomaticReplicationState.STOPPED,0,new UUID(0,0),0,Optional.empty(),PEERS));
        assertDoesNotThrow(()->status(AutomaticReplicationState.LEADER_READY,2,UUID.randomUUID(),2,Optional.of(SELF),PEERS));
        assertThrows(IllegalArgumentException.class,()->status(AutomaticReplicationState.FOLLOWER,2,new UUID(0,0),0,Optional.of(SELF),PEERS));
        assertThrows(IllegalArgumentException.class,()->status(AutomaticReplicationState.LEADER_READY,2,UUID.randomUUID(),0,Optional.of(SELF),PEERS));
        assertThrows(IllegalArgumentException.class,()->status(AutomaticReplicationState.FOLLOWER,2,UUID.randomUUID(),2,Optional.of(SELF),PEERS));
        assertThrows(IllegalArgumentException.class,()->status(AutomaticReplicationState.STOPPED,0,new UUID(0,0),0,Optional.empty(),List.of(PEERS.getFirst(),PEERS.getFirst())));
        assertThrows(UnsupportedOperationException.class,()->status(AutomaticReplicationState.STOPPED,0,new UUID(0,0),0,Optional.empty(),PEERS).peers().clear());
    }
    private AutomaticReplicationStatus status(AutomaticReplicationState state,long promised,UUID incarnation,long active,
            Optional<ReplicationNodeId> proposer,List<ReplicationPeerStatus> peers) {
        return new AutomaticReplicationStatus(SELF,state,Optional.empty(),proposer,promised,incarnation,active,0,0,0,0,Optional.empty(),peers);
    }
    @Test void structuredFailureRetainsCauseWithoutRedefiningOldReasons() {
        var cause=new IllegalStateException("fixture");
        var failure=new AutomaticReplicationException(AutomaticReplicationException.Reason.STALE_EPOCH,
                AutomaticReplicationException.Outcome.INDETERMINATE,Optional.of(SELF),"after dispatch",cause);
        assertSame(cause,failure.getCause());assertEquals(Optional.of(SELF),failure.observedLeader());
        assertEquals(AutomaticReplicationException.Outcome.INDETERMINATE,failure.outcome());
        assertThrows(NullPointerException.class,()->new AutomaticReplicationException(null,failure.outcome(),Optional.empty(),"bad"));
    }
}
