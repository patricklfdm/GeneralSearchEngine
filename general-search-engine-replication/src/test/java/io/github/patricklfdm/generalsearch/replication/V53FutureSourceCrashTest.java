package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53FutureSourceCrashTest {
    @TempDir Path temp;
    @Test void processDeathCannotLoseOrReplaceTheFrozenFutureProof()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-future-source/process-"+UUID.randomUUID()));
        System.out.println("v53FutureSourceEvidence="+raw.toAbsolutePath());
        var f=V53FutureRetentionSourceTest.pending(Files.createDirectory(temp.resolve("native")),raw);var self=f.request.targets().getFirst();
        byte[] original=Files.readAllBytes(self.replicaDirectory().resolve(MembershipFutureRetentionFiles.FILE));int ordinal=0;
        try {
            for(String mode:List.of("halt","kill"))for(String point:List.of("CAPTURE_INTENT_PREFIX_WRITTEN","CAPTURE_INTENT_FORCED",
                    "SOURCE_PACKET_PREFIX_WRITTEN","SOURCE_PACKET_FORCED","BASIS_WRITTEN","BASIS_FORCED","GRANT_BEFORE_RETURN")) {
                Files.move(self.replicaDirectory(),temp.resolve("previous-"+ordinal++));
                V53JournalApplicationTest.copy(raw.resolve("pending-future/node-1"),self.replicaDirectory());
                Path evidence=Files.createDirectory(raw.resolve(mode+"-"+point)),log=evidence.resolve("worker.log");
                var child=process(self,mode,point,log);
                try {
                    long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(90);
                    while(child.isAlive() && !Files.readString(log).contains("CUT "+point) && System.nanoTime()<deadline)Thread.sleep(10);
                    assertTrue(Files.readString(log).contains("CUT "+point),Files.readString(log));assertFalse(Files.readString(log).contains("RESPONSE"));
                    if(mode.equals("kill")){assertThrows(Exception.class,()->f.open(self,"live-lock-probe"));child.destroyForcibly();}
                    assertTrue(child.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                    V53JournalApplicationTest.copy(self.replicaDirectory(),evidence.resolve("interrupted"));
                    var resumed=process(self,"resume","none",evidence.resolve("resume.log"));
                    try {assertTrue(resumed.waitFor(90,TimeUnit.SECONDS));assertEquals(0,resumed.exitValue(),Files.readString(evidence.resolve("resume.log")));}
                    finally{if(resumed.isAlive()){resumed.destroyForcibly();resumed.waitFor(10,TimeUnit.SECONDS);}}
                    V53JournalApplicationTest.copy(self.replicaDirectory(),evidence.resolve("recovered"));
                    try(var owner=f.open(self,"inspect-recovered")) {
                        var source=owner.originalSource();var frozen=MembershipPeerRetentionSource.read(source);
                        assertArrayEquals(original,frozen.futureBytes());assertEquals(1,owner.futureRetentionState().revision);
                        Files.write(evidence.resolve("promise.gsr"),owner.promised().orElseThrow().bytes());Files.write(evidence.resolve("basis.gsr"),source.basis.bytes());
                        Files.write(evidence.resolve("source.gscp"),source.capsule.packet.bytes());
                        var before=V53ReplayFilesTest.files(self.replicaDirectory());
                        assertEquals(source.basis.digest(),owner.prepareCurrent(object(source.basis.value().get("ballot"))).digest());
                        assertEquals(before,V53ReplayFilesTest.files(self.replicaDirectory()));
                    }
                    assertEquals(0,f.resources.usage().leases());
                    Files.write(evidence.resolve("result.json"),canonical(Map.of("status","PASS","mode",mode,"cut",point,"exit",(long)child.exitValue()),16384));
                    System.out.println("v53FutureSourceCrash="+mode+":"+point+" PASS");
                }finally{if(child.isAlive()){child.destroyForcibly();child.waitFor(10,TimeUnit.SECONDS);}}
            }
        }finally{V53NativeApplicationTest.save(f);}
    }
    private static Process process(MembershipBootstrapTarget<?,?> self,String mode,String point,Path log)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                V53FutureSourceWorker.class.getName(),self.replicaDirectory().toString(),self.materialization().directory().toString(),mode,point)
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
    }
}
