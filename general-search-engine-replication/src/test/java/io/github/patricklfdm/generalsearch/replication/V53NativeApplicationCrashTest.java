package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53NativeApplicationCrashTest {
    @TempDir Path temp;
    @Test void nativeApplicationSurvivesRealDeathWithoutCallerVotingObservations()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-native-application/process-"+UUID.randomUUID()));
        System.out.println("v53NativeApplicationProcessEvidence="+raw.toAbsolutePath());
        var f=V53NativeApplicationTest.certified(Files.createDirectory(temp.resolve("group")),raw);var target=f.request.targets().getFirst();
        f.snapshot("certified");int ordinal=0;
        try {
            for(String mode:List.of("halt","kill"))for(String point:List.of("NATIVE_CERTIFICATE_RETAINED","REPLAY_APPLICATION_FINISHED","APPLY_IMAGE_PREFIX_WRITTEN","APPLY_END_FORCED","APPLY_ACK_DIRECTORY_FORCED")) {
                Files.move(target.replicaDirectory(),temp.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(raw.resolve("certified/node-1"),target.replicaDirectory());
                Path evidence=Files.createDirectory(raw.resolve(mode+"-"+point)),log=evidence.resolve("worker.log");
                var child=process(target,mode,point,log);
                try {
                    long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(60);
                    while(child.isAlive() && !Files.readString(log).contains("CUT "+point) && System.nanoTime()<deadline)Thread.sleep(10);
                    assertTrue(Files.readString(log).contains("CUT "+point),Files.readString(log));assertFalse(Files.readString(log).contains("RESULT "));
                    if(mode.equals("kill")){assertThrows(Exception.class,()->f.open(target,"lock-probe"));child.destroyForcibly();}
                    assertTrue(child.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                    V53JournalApplicationTest.copy(target.replicaDirectory(),evidence.resolve("interrupted"));
                    var resume=process(target,"resume","none",evidence.resolve("resume.log"));
                    try{assertTrue(resume.waitFor(60,TimeUnit.SECONDS));assertEquals(0,resume.exitValue(),Files.readString(evidence.resolve("resume.log")));}
                    finally{if(resume.isAlive()){resume.destroyForcibly();resume.waitFor(10,TimeUnit.SECONDS);}}
                    V53JournalApplicationTest.copy(target.replicaDirectory(),evidence.resolve("recovered"));
                    for(String name:List.of("selector.gsr","pending.accept","grants.gsr"))
                        assertArrayEquals(Files.readAllBytes(raw.resolve("certified/node-1").resolve(name)),Files.readAllBytes(target.replicaDirectory().resolve(name)));
                    Files.write(evidence.resolve("result.json"),canonical(Map.of("mode",mode,"cut",point,"exit",(long)child.exitValue()),16384));
                    System.out.println("v53NativeApplicationCrash="+mode+":"+point+" PASS");
                }finally{if(child.isAlive()){child.destroyForcibly();child.waitFor(10,TimeUnit.SECONDS);}}
            }
        }finally{V53NativeApplicationTest.save(f);}
    }
    private static Process process(MembershipBootstrapTarget<?,?> target,String mode,String point,Path log)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                V53NativeApplicationWorker.class.getName(),target.replicaDirectory().toString(),target.materialization().directory().toString(),mode,point)
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
    }
}
