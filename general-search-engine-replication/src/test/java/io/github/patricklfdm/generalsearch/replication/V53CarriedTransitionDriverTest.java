package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Retain the complete existing carried transition as an independent raw history. */
class V53CarriedTransitionDriverTest {
    @TempDir Path temp;
    private void run(String kind,int index,int campaigns)throws Exception {
        var helper=new V53TransitionRoundDriverTest();helper.temp=temp;
        var ordinal=new AtomicInteger();
        try(var n=helper.network("CARRIED_"+kind);var round=helper.driver(n,ordinal,MembershipRoundDriver.Events.NONE)) {
            byte[] entry=Files.readAllBytes(n.f.raw.resolve("entry-"+index+".gsr"));
            byte[] payload=Files.readAllBytes(n.f.raw.resolve("payload-"+index+".bin"));
            var completed=round.start();assertEquals("PUBLISH_ACK",completed.kind());
            assertEquals(campaigns,ordinal.get());assertEquals(MembershipRoundDriver.State.READY,round.state());
            assertArrayEquals(completed.bytes(),round.readiness().bytes());
            assertArrayEquals(entry,Files.readAllBytes(n.f.raw.resolve("native-entry-"+index+".gsr")));
            assertArrayEquals(payload,Files.readAllBytes(n.f.raw.resolve("native-payload-"+index+".bin")));
            var context=n.owners.getFirst().activationContext();assertEquals(7L,context.cut.get("index"));
            assertNull(context.catalog.get("active"));assertNull(context.view.get("operation"));
            assertEquals(List.of("node-1","node-2","node-3"),list(context.view.get("new")));
            assertEquals(0L,context.catalog.get("applicationSequence"));
            var result=Map.of("status","PASS","kind",kind,"oldIndex",index,"oldEntry",hash(entry),
                    "activations",campaigns,"internalReady",true,"publicReady",false,"originalBudgetSeconds",600);
            Files.write(n.f.raw.resolve("carried-transition-result.json"),canonical(result,4096));
        }
    }
    @Test void carriedIntentFinishesBeforeFreshStableBarrier()throws Exception {run("INTENT",5,3);}
    @Test void carriedFinalFinishesBeforeFreshStableBarrier()throws Exception {run("FINAL",6,2);}
}
