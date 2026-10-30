package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import static org.junit.jupiter.api.Assertions.*;

/** Conditional scheduling/retention projections, not native floor authority. */
class V53JoiningMaintenanceTest {
    @Test void installedMajorityPrecedesUnselectedVoterButDoesNotRemoveFallback() {
        var stable=new V53CapsuleFixture(5,"REMOVE",7).verify();
        var cohort=Set.of("node-1","node-2","node-4");
        assertEquals(List.of("node-1","node-2","node-4","node-3"),
                MembershipGenerationMaintenance.copyOrder(stable.context,Set.of(),cohort));
        assertEquals(List.of("node-1","node-2","node-3","node-4"),
                MembershipGenerationMaintenance.copyOrder(stable.context,Set.of()));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationMaintenance.copyOrder(stable.context,Set.of(),Set.of("node-5")));
    }
    @ParameterizedTest @CsvSource({"3,ADD","4,ADD","3,REPLACE","4,REPLACE","5,REPLACE"})
    void joiningCopyRemainsFirstEvenOutsideInstalledPreference(int size,String kind) {
        var joint=new V53CapsuleFixture(size,kind,6).verify();
        var order=MembershipGenerationMaintenance.copyOrder(joint.context,Set.of("node-6"),Set.of("node-1","node-2"));
        assertEquals("node-6",order.getFirst());assertEquals(List.of("node-1","node-2"),order.subList(1,3));
        assertEquals(joint.context.voters(),new HashSet<>(order));
    }
    @ParameterizedTest @CsvSource({"3,ADD","4,ADD","3,REPLACE","4,REPLACE","5,REPLACE","4,REMOVE","5,REMOVE"})
    void prioritizeTheJoiningCopyWithoutCollectingMoreThanThreeRemoteMembers(int size,String kind) {
        var genesis=new V53CapsuleFixture(size,kind,0).verify();var joint=new V53CapsuleFixture(size,kind,6).verify();
        var plan=MembershipPeerRetentionPlan.genesis(genesis);byte[] original=plan.bytes();
        var joining=plan.joining(joint,new byte[0]);assertEquals(kind.equals("REMOVE")?Set.of():Set.of("node-6"),joining);
        var order=MembershipGenerationMaintenance.copyOrder(joint.context,joining);
        assertEquals(joint.context.voters(),new HashSet<>(order));
        if(!joining.isEmpty())assertEquals("node-6",order.getFirst());
        for(String local:joint.context.voters()) {
            var acquired=new HashSet<>(Set.of(local));int receiving=0;
            for(String node:order) {
                if(quorum(joint.context,acquired) && acquired.containsAll(joining))break;
                if(acquired.add(node))receiving++;
            }
            assertTrue(quorum(joint.context,acquired));assertTrue(acquired.containsAll(joining));
            // Each member owns one SOURCE prefix plus CONTROL-accounted
            // generation metadata. This is an ordering bound, not a proof of
            // maximum combined storage headroom with all original sources.
            assertTrue(receiving<=3,"unexpected extra remote copy for "+local);
        }
        assertArrayEquals(original,plan.bytes());
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationMaintenance.copyOrder(joint.context,Set.of("unknown")));
        assertThrows(IllegalArgumentException.class,()->MembershipGenerationMaintenance.copyOrder(joint.context,Set.of("node-1","node-2")));
        assertThrows(UnsupportedOperationException.class,()->order.add("node-x"));
    }
    private static boolean quorum(MembershipContext context,Set<String> names) {
        for(String side:List.of("old","new")) {
            var members=MembershipContext.nodes(context.view,side);
            if(names.stream().filter(members::contains).count()<=members.size()/2)return false;
        }
        return true;
    }
}
