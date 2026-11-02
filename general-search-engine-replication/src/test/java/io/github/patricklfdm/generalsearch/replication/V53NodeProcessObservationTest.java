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
}
