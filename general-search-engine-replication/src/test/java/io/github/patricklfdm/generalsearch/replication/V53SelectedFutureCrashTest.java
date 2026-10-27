package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Actual inherited obligations, original majority and fresh-process completion. */
class V53SelectedFutureCrashTest {
    @TempDir Path temp;
    @Test void inheritedPublicationSurvivesSelectorLedgerAndClearCuts()throws Exception {
        var helper=new V53SelectedFutureContinuationTest();helper.temp=temp;helper.continuation(true);
    }
    static void publicationCuts(V53BootstrapPublicationTest.Fixture f,List<MembershipBootstrapTarget<Integer,Doc>> targets)throws Exception {
        Path root=Files.createDirectory(f.raw.resolve("publication-process"));int ordinal=0;
        // Preserve every replaced tree as original diagnostic evidence. The same
        // path is reused because native application ownership binds these paths.
        Path retired=Files.createDirectory(targets.getFirst().replicaDirectory().getParent().resolve("process-replaced"));
        for(var self:targets)for(String mode:List.of("halt","kill")) {
            var points=new ArrayList<>(List.of("PUBLICATION_SELECTOR_FORCED","RETENTION_PREFIX_WRITTEN","RETENTION_RENAMED"));
            if(self.identity().nodeId().value().equals("node-2"))points.addAll(List.of("INHERITED_FUTURE_RETENTION_PROMOTED","FUTURE_RETENTION_PREFIX_WRITTEN","FUTURE_RETENTION_RENAMED"));
            for(String point:points) {
                for(var t:targets) {
                    Files.move(t.replicaDirectory(),retired.resolve(Integer.toString(ordinal++)));
                    V53JournalApplicationTest.copy(f.raw.resolve("future-reapplied/"+t.identity().nodeId().value()),t.replicaDirectory());
                }
                String node=self.identity().nodeId().value();Path evidence=Files.createDirectory(root.resolve(node+"-"+mode+"-"+point));
                var ordered=new ArrayList<>(targets);ordered.remove(self);ordered.addFirst(self);
                Path inputs=evidence.resolve("nodes.json");Files.write(inputs,canonical(ordered.stream().map(t->Map.of("replica",t.replicaDirectory().toString(),"application",t.materialization().directory().toString())).toList(),65536));
                Path log=evidence.resolve("worker.log");var child=process(inputs,"publish",mode,point,log);
                try {
                    long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(90);
                    while(child.isAlive() && !Files.readString(log).contains("CUT "+point) && System.nanoTime()<deadline)Thread.sleep(10);
                    assertTrue(Files.readString(log).contains("CUT "+point),Files.readString(log));assertFalse(Files.readString(log).contains("RESPONSE"));
                    if(mode.equals("kill")) {
                        assertThrows(Exception.class,()->f.open(self,"inherited-lock-probe"));
                        assertEquals(0,f.resources.usage().leases());child.destroyForcibly();
                    }
                    assertTrue(child.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                    V53JournalApplicationTest.copy(self.replicaDirectory(),evidence.resolve("interrupted"));
                    var resumed=process(inputs,"recover","resume","none",evidence.resolve("resume.log"));
                    try{assertTrue(resumed.waitFor(90,TimeUnit.SECONDS));assertEquals(0,resumed.exitValue(),Files.readString(evidence.resolve("resume.log")));}
                    finally{if(resumed.isAlive()){resumed.destroyForcibly();resumed.waitFor(10,TimeUnit.SECONDS);}}
                    V53JournalApplicationTest.copy(self.replicaDirectory(),evidence.resolve("recovered"));
                    try(var owner=f.open(self,"inherited-process-reopen")) {
                        assertFalse(owner.futureRetentionState().pending());assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
                        for(var peer:targets)assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
                    }
                    for(var other:targets)if(other!=self)assertEquals(V53ReplayFilesTest.files(f.raw.resolve("future-reapplied/"+other.identity().nodeId().value())),V53ReplayFilesTest.files(other.replicaDirectory()));
                    assertEquals(0,f.resources.usage().leases());
                    Files.write(evidence.resolve("result.json"),canonical(Map.of("status","PASS","node",node,"mode",mode,"cut",point,"exit",(long)child.exitValue()),16384));
                    System.out.println("v53InheritedFutureCrash="+node+":"+mode+":"+point+" PASS");
                }finally{if(child.isAlive()){child.destroyForcibly();child.waitFor(10,TimeUnit.SECONDS);}}
            }
        }
        for(var t:targets) {
            Files.move(t.replicaDirectory(),retired.resolve(Integer.toString(ordinal++)));
            V53JournalApplicationTest.copy(f.raw.resolve("future-reapplied/"+t.identity().nodeId().value()),t.replicaDirectory());
        }
    }
    private static Process process(Path inputs,String action,String mode,String point,Path log)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                V53FutureRetentionWorker.class.getName(),inputs.toString(),action,mode,point).redirectErrorStream(true).redirectOutput(log.toFile()).start();
    }
}
