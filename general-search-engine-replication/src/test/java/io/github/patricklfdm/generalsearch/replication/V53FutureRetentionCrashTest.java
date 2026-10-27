package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53FutureRetentionCrashTest {
    @TempDir Path temp;
    @Test void originalFutureProofAndPromotionSurviveProcessDeath()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-future-retention/process-"+UUID.randomUUID()));
        System.out.println("v53FutureRetentionProcessEvidence="+raw.toAbsolutePath());
        var f=V53FutureRetentionTest.ready(Files.createDirectory(temp.resolve("native")),raw);
        var self=f.request.targets().getFirst();var peer=f.request.targets().get(1);
        Path inputs=raw.resolve("nodes.json");Files.write(inputs,canonical(f.request.targets().stream().map(t->Map.of("replica",t.replicaDirectory().toString(),"application",t.materialization().directory().toString())).toList(),65536));
        try {
            try(var owner=f.open(self,"reference-future")) {
                owner.retainFutureDispatch(peer.identity(),owner.pendingPublication(owner.applyCurrent(builder().configuration(),self.materialization())));
            }
            f.snapshot("pending-future");int ordinal=0;
            for(String action:List.of("record","publish"))for(String mode:List.of("halt","kill")) {
                var points=action.equals("record")?List.of("FUTURE_RETENTION_PREFIX_WRITTEN","FUTURE_RETENTION_FORCED","FUTURE_RETENTION_RENAMED","FUTURE_RETENTION_BEFORE_RETURN"):
                        List.of("PUBLICATION_SELECTOR_FORCED","RETENTION_PREFIX_WRITTEN","RETENTION_RENAMED","FUTURE_RETENTION_PREFIX_WRITTEN","FUTURE_RETENTION_RENAMED");
                for(String point:points) {
                    Files.move(self.replicaDirectory(),temp.resolve("previous-"+ordinal++));
                    V53JournalApplicationTest.copy(raw.resolve((action.equals("record")?"before-future":"pending-future")+"/node-1"),self.replicaDirectory());
                    Path evidence=Files.createDirectory(raw.resolve(action+"-"+mode+"-"+point)),log=evidence.resolve("worker.log");
                    var child=process(inputs,action,mode,point,log);
                    try {
                        long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(90);
                        while(child.isAlive() && !Files.readString(log).contains("CUT "+point) && System.nanoTime()<deadline)Thread.sleep(10);
                        assertTrue(Files.readString(log).contains("CUT "+point),Files.readString(log));assertFalse(Files.readString(log).contains("RESPONSE"));
                        if(mode.equals("kill")){assertThrows(Exception.class,()->f.open(self,"lock-probe"));child.destroyForcibly();}
                        assertTrue(child.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                        V53JournalApplicationTest.copy(self.replicaDirectory(),evidence.resolve("interrupted"));
                        var resumed=process(inputs,action.equals("record")?"record":"recover","resume","none",evidence.resolve("resume.log"));
                        try{assertTrue(resumed.waitFor(90,TimeUnit.SECONDS));assertEquals(0,resumed.exitValue(),Files.readString(evidence.resolve("resume.log")));}
                        finally{if(resumed.isAlive()){resumed.destroyForcibly();resumed.waitFor(10,TimeUnit.SECONDS);}}
                        V53JournalApplicationTest.copy(self.replicaDirectory(),evidence.resolve("recovered"));
                        try(var owner=f.open(self,"reopen-future")) {
                            assertEquals(action.equals("record"),owner.futureRetentionState().pending());
                            assertEquals(action.equals("record")?1:2,owner.futureRetentionState().revision);
                            assertEquals(action.equals("record")?List.of(0L):List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
                        }
                        assertEquals(0,f.resources.usage().leases());
                        Files.write(evidence.resolve("result.json"),canonical(Map.of("status","PASS","action",action,"mode",mode,"cut",point,"exit",(long)child.exitValue()),16384));
                        System.out.println("v53FutureRetentionCrash="+action+":"+mode+":"+point+" PASS");
                    }finally{if(child.isAlive()){child.destroyForcibly();child.waitFor(10,TimeUnit.SECONDS);}}
                }
            }
        }finally{V53NativeApplicationTest.save(f);}
    }
    private static Process process(Path inputs,String action,String mode,String point,Path log)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                V53FutureRetentionWorker.class.getName(),inputs.toString(),action,mode,point).redirectErrorStream(true).redirectOutput(log.toFile()).start();
    }
}
