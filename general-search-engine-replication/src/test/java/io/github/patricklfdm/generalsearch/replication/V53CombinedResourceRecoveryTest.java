package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** One original history: retain the pressure failure, release imposed copies,
 * then cold-open the same owner directories. Native maintenance reacquires the
 * exact original floor before this required voter participates in continuation. */
@EnabledIfSystemProperty(named="v53.combined.recovery.probe",matches="true")
class V53CombinedResourceRecoveryTest {
    @TempDir Path temp;
    static Map<String,String> disk(Path path)throws Exception {
        var files=new TreeMap<String,String>();try(var walk=Files.walk(path)) {
            for(var p:walk.filter(p->!p.equals(path)).toList()) {
                assertFalse(Files.isSymbolicLink(p));files.put(path.relativize(p).toString(),Files.isDirectory(p)?"directory":hash(Files.readAllBytes(p)));
            }
        }return files;
    }
    @Test void partialFloorVoterAutomaticallyResumesBeforeCarriedIntent()throws Exception {
        run(false);
    }
    void run(boolean completeOriginalFloor)throws Exception {
        Path root=Files.createDirectories(Path.of((completeOriginalFloor?"target/v53-partial-floor-resume/":"target/v53-automatic-floor-resume/")+"run-"+UUID.randomUUID()));
        System.out.println("v53CombinedRecoveryEvidence="+root.toAbsolutePath());boolean success=false;
        var probe=new V53CombinedTransitionResourcesTest();probe.temp=temp;
        Path pressure=Files.createDirectory(root.resolve("pressure"));
        try {
            var failure=assertThrows(Exception.class,()->probe.scenario(Files.createDirectory(pressure.resolve("4-REMOVE")),4));
            Files.write(pressure.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-combined-transition-v1",
                "status","INCOMPLETE","cases",List.of(),"network",true,"simultaneousMaximumQualified",false,
                "publicRuntime",false,"phase3Complete",false),65536));
            Path original=pressure.resolve("4-REMOVE/history");
            var errors=list(parse(Files.readAllBytes(original.resolve("failures.json")),1024*1024));
            assertTrue(errors.stream().map(MembershipFormat::object).anyMatch(v->v.get("node").equals("node-2") &&
                v.get("failure").equals("java.lang.IllegalArgumentException: resource ownership/count")),failure.toString());
            byte[] entry=Files.readAllBytes(original.resolve("native-entry-5.gsr"));
            byte[] payload=Files.readAllBytes(original.resolve("native-payload-5.bin"));
            var local=probe.retained.request.targets().getFirst();
            assertArrayEquals(Files.readAllBytes(original.resolve("after-close/node-1/pending.accept")),
                Files.readAllBytes(local.replicaDirectory().resolve("pending.accept")));
            if(completeOriginalFloor)V53PartialFloorResumeTest.resume(probe.retained,Files.createDirectory(root.resolve("storage-resume")));
            Path resumed=Files.createDirectory(root.resolve("recovery"));
            var fixture=new V53BootstrapPublicationTest.Fixture(resumed,probe.retained);
            var paths=fixture.request.targets().stream().map(t->Map.of("node",t.identity().nodeId().value(),
                "replica",t.replicaDirectory().toString(),"application",t.materialization().directory().toString())).toList();
            Files.write(root.resolve("lineage.json"),canonical(Map.of("root",fixture.result.root().manifestDigest(),
                "directories",paths,"retainedEntry",hash(entry),"retainedPayload",hash(payload)),65536));
            var helper=new V53NativeDispatchTest();helper.temp=temp;
            var rounds=new V53TransitionRoundDriverTest();rounds.temp=temp;var ordinal=new AtomicInteger();
            try(var n=helper.new Network(fixture,probe.retainedBounds,TimeUnit.MINUTES.toNanos(10));
                var driver=rounds.driver(n,ordinal,MembershipRoundDriver.Events.NONE)) {
                n.observeRequests=true;
                var captured=new java.util.concurrent.atomic.AtomicBoolean();
                var usage=new ArrayList<Map<String,Object>>();
                if(!completeOriginalFloor)n.hook.set(event->{
                    if(captured.get())return;
                    usage.add(Map.of("event",event,"usage",V53CombinedReceiveResourcesTest.usage(n.resources.get(1))));
                    if(event.equals("FLOOR_BEFORE_RETURN")) {
                        V53JournalApplicationTest.copy(fixture.request.targets().get(1).replicaDirectory(),root.resolve("automatic-floor"));
                        Files.write(root.resolve("floor-usage.json"),canonical(usage,1024*1024));
                        synchronized(n.events){Files.write(root.resolve("floor-events.json"),canonical(n.events,4*1024*1024));}
                        captured.set(true);
                    }
                });
                var completed=driver.start();assertEquals("PUBLISH_ACK",completed.kind());
                assertEquals(MembershipRoundDriver.State.READY,driver.state());assertEquals(3,ordinal.get());
                assertArrayEquals(completed.bytes(),driver.readiness().bytes());
                assertArrayEquals(entry,Files.readAllBytes(resumed.resolve("native-entry-5.gsr")));
                assertArrayEquals(payload,Files.readAllBytes(resumed.resolve("native-payload-5.bin")));
                var context=n.owners.getFirst().activationContext();assertEquals(7L,context.cut.get("index"));
                assertNull(context.catalog.get("active"));assertNull(context.view.get("operation"));
                assertEquals(List.of("node-1","node-2","node-3"),list(context.view.get("new")));
                {
                    assertEquals(7L,n.owners.get(1).activationContext().cut.get("index"));
                    for(int i=1;i<=3;i++)assertTrue(list(decode(Files.readAllBytes(resumed.resolve("selected-"+i+".gsr")),"records","SELECTED").value().get("sources"))
                        .stream().map(MembershipFormat::object).anyMatch(v->v.get("voter").equals("node-2")),"resumed owner remains required");
                }
                if(!completeOriginalFloor)assertTrue(captured.get(),"original floor forced before continuation");
                Files.write(resumed.resolve("result.json"),canonical(Map.of("status","PASS","activations",ordinal.get(),
                    "internalReady",true,"publicReady",false),65536));
            }
            success=true;
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("schema",completeOriginalFloor?"gse-v53-partial-floor-resume-v1":"gse-v53-automatic-floor-resume-v1",
                "status",success?"PASS":"FAIL","profile","4-REMOVE","pressureOutcome","FAIL",
                "sameDirectories",true,"partialFloorRecoveryQualified",false,"automaticRuntimeReachabilityQualified",false,"phase3Complete",false),65536));
        }
    }
}
