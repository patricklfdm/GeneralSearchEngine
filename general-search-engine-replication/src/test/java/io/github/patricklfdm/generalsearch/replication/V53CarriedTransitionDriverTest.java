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
        V53RemoveRetirementCapture captures=null;
        try(var n=helper.network("CARRIED_"+kind);var round=helper.driver(n,ordinal,MembershipRoundDriver.Events.NONE)) {
            if(Boolean.getBoolean("v53.carried.retirement.captures")) {
                captures=new V53RemoveRetirementCapture(n.f.raw);n.removeRetirementCapture=captures;
            }
            // Retain every original send/receive and terminal failure before
            // the first higher-ballot campaign; replies alone are insufficient.
            n.observeRequests=true;
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
            // Ordinary DATA/BARRIER cold-recovery permission must not change
            // the original context command's source-retention lifetime.
            var first=decode(Files.readAllBytes(n.f.raw.resolve("selected-1.gsr")),"records","SELECTED");
            for(Object source:list(first.value().get("sources"))) {
                String node=(String)object(source).get("voter");
                var before=sourceFiles(n.f.raw.resolve("installed-1").resolve(node));
                assertTrue(before.size()>1,"context carried original sources");
                assertEquals(before,sourceFiles(n.f.raw.resolve("applied-"+index).resolve(node)),
                        "context carried sources remain through application");
            }
            var result=Map.of("status","PASS","kind",kind,"oldIndex",index,"oldEntry",hash(entry),
                    "activations",campaigns,"internalReady",true,"publicReady",false,"originalBudgetSeconds",600);
            Files.write(n.f.raw.resolve("carried-transition-result.json"),canonical(result,4096));
        }
        if(captures!=null)captures.finishCarried(kind);
    }
    private static Map<String,String> sourceFiles(Path path)throws Exception {
        var files=new TreeMap<>(V53ReplayFilesTest.files(path));
        files.keySet().removeIf(name->!name.equals("grants.gsr") && !name.startsWith("sources/"));
        return files;
    }
    @Test void carriedIntentFinishesBeforeFreshStableBarrier()throws Exception {run("INTENT",5,3);}
    @Test void carriedFinalFinishesBeforeFreshStableBarrier()throws Exception {run("FINAL",6,2);}
}
