package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Explicit native qualification: keep old sources while selected-prefix
 * recovery catches up a voter in the same view. No fabricated adoption/votes. */
class V53LaggingSourceQualification {
    @TempDir Path temp;
    @Test void laggingVoterKeepsOriginalSourcesUntilFreshSelectionAdvancesIt()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        try(var n=helper.network(null)) {
            var lagging=n.owners.get(2);var resources=n.resources.get(2);
            for(int i=0;i<2;i++)try(var c=new MembershipActivation(lagging,resources,System::nanoTime,V53NativeDispatchTest.BUDGET)) {assertNotNull(c.ownSource());}
            assertTrue(lagging.publishedMaintenanceRequired());assertFalse(lagging.nativeGenerationMaintenanceRequired());
            try(var first=helper.driver(n,MembershipRoundDriver.Events.NONE)){first.start();}
            assertEquals(1L,n.owners.getFirst().activationContext().cut.get("index"));
            assertEquals(0L,lagging.activationContext().cut.get("index"));
            try(var round=new MembershipRoundDriver<>(lagging,n.endpoints.get(2),resources,n.bounds,n.transports.get(2),
                    temp.resolve("lagging"),System::nanoTime,V53NativeDispatchTest.BUDGET,2,builder().configuration(),
                    n.f.request.targets().get(2).materialization(),(event,record)->n.events.add(Map.of("node","node-3","event","LAGGING_"+event,"bytes",Base64.getEncoder().encodeToString(record.bytes()))),MembershipSlotDriver.Events.NONE)) {
                var result=round.startDiscovered();assertEquals("PUBLISH_ACK",result.kind());round.readiness();
                assertEquals(2L,lagging.activationContext().cut.get("index"));
                Files.write(n.f.raw.resolve("lagging-result.json"),canonical(Map.of("status","PARTIAL","native",true,"physicalReplay",false,
                    "before",0,"selected",1,"afterFreshBarrier",2,"phase3Complete",false),4096));
            }
        }
    }
}
