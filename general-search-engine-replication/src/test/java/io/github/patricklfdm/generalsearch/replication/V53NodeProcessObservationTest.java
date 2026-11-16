package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class V53NodeProcessObservationTest {
    @Test void repeatedInstallationsInOneChildHaveDistinctSnapshotIdentities()throws Exception {
        var rows=new ArrayList<Map<String,Object>>();
        var hooks=V53NodeProcessWorker.hooks("node-1",2,(action,value)->{
            if(action.equals("installed"))rows.add(MembershipFormat.object(value));
        });
        var first=new MembershipFormat.Decoded("records","SELECTED",Map.of(),new byte[]{1});
        var next=new MembershipFormat.Decoded("records","SELECTED",Map.of(),new byte[]{2});
        hooks.round().at("INSTALLED",first);hooks.round().at("BEFORE_READY",first);hooks.round().at("INSTALLED",next);
        assertEquals(List.of(Map.of("number",2L,"bytes","AQ=="),Map.of("number",3L,"bytes","Ag==")),rows);
    }
    @Test void repeatedSlotObservationsKeepEveryOriginalWithoutOverwriting()throws Exception {
        var paths=new ArrayList<String>();
        var hooks=V53NodeProcessWorker.hooks("node-1",2,(action,value)->{
            if(action.equals("snapshot"))paths.add((String)value);
        });
        var record=new MembershipFormat.Decoded("records","CERTIFICATE",Map.of("index",3L),new byte[]{1});
        hooks.slot().at("APPLIED",record,Set.of());hooks.slot().at("APPLIED",record,Set.of());
        hooks.slot().at("PUBLISHED",record,Set.of());hooks.slot().at("APPLIED",record,Set.of());
        assertEquals(List.of("applied-3","applied-3-repeat-2","published-3","applied-3-repeat-3"),paths);
        assertEquals(paths.size(),new HashSet<>(paths).size());
    }
    @Test void renameQualificationHasOneExplicitFiniteProfileAndLeavesOtherCutsUnchanged() {
        for(String point:List.of("ACCEPT_RENAMED","PROOF_RENAMED")) {
            assertEquals(600,V53NodeProcessWorker.serviceSeconds(point));
            assertEquals(java.util.concurrent.TimeUnit.SECONDS.toNanos(600),V53NodeProcessWorker.serviceBudget(point));
            assertEquals(30_000,V53NodeProcessWorker.bounds(point).requestTimeoutMillis());
            assertEquals(ReplicationBounds.defaults().maxRetryAttempts(),V53NodeProcessWorker.bounds(point).maxRetryAttempts());
        }
        for(String point:List.of("AFTER_DATA_RETURN","ACCEPT_PARENT_FORCED","PROOF_PARENT_FORCED")) {
            assertEquals(V53NodeOwnerNetworkTest.BUDGET,V53NodeProcessWorker.serviceBudget(point));
            assertEquals(ReplicationBounds.defaults(),V53NodeProcessWorker.bounds(point));
        }
    }
}
