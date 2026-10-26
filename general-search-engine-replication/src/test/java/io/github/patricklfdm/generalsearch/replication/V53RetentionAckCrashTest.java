package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53RetentionAckCrashTest {
    @TempDir Path temp;
    @Test void actualReceiverCrashesKeepTheIntentAndExactRetryAfterReopen()throws Exception {
        var helper=new V53RetentionQuorumTest();helper.temp=temp;
        try(var group=helper.new Group(3)) {
            var f=group.fixture;var local=group.owners.getFirst();var receiver=group.owners.get(1);
            var intent=local.peerRetentionIntent(f.request.targets().getLast().identity(),f.ballot);
            var request=MembershipActivation.frame("RETENTION_INTENT",local.activationContext(),local.activationIdentity(),receiver.activationIdentity(),f.ballot,UUID.randomUUID(),1,intent.payload);
            Path input=f.raw.resolve("request.gsrp");Files.write(input,request.bytes());
            for(var owner:group.owners)owner.close();f.snapshot("crash-ready");var target=f.request.targets().get(1);int ordinal=0;
            for(String mode:List.of("halt","kill"))for(String point:List.of("RETENTION_PREFIX_WRITTEN","RETENTION_FORCED","RETENTION_RENAMED","RETENTION_PARENT_FORCED","RETENTION_ACK_BEFORE_RETURN")) {
                Files.move(target.replicaDirectory(),temp.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(f.raw.resolve("crash-ready/node-2"),target.replicaDirectory());
                Path raw=Files.createDirectory(f.raw.resolve(mode+"-"+point)),log=raw.resolve("worker.log");
                var child=process(target,input,mode,point,log);
                try {
                    long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(60);
                    while(child.isAlive() && !Files.readString(log).contains("CUT "+point) && System.nanoTime()<deadline)Thread.sleep(10);
                    assertTrue(Files.readString(log).contains("CUT "+point),Files.readString(log));assertFalse(Files.readString(log).contains("RESPONSE"));
                    if(mode.equals("kill")){assertThrows(Exception.class,()->f.open(target,"lock-probe"));child.destroyForcibly();}
                    assertTrue(child.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                    V53JournalApplicationTest.copy(target.replicaDirectory(),raw.resolve("interrupted"));
                    var resume=process(target,input,"resume","none",raw.resolve("resume.log"));
                    try{assertTrue(resume.waitFor(60,TimeUnit.SECONDS));assertEquals(0,resume.exitValue(),Files.readString(raw.resolve("resume.log")));}
                    finally{if(resume.isAlive()){resume.destroyForcibly();resume.waitFor(10,TimeUnit.SECONDS);}}
                    V53JournalApplicationTest.copy(target.replicaDirectory(),raw.resolve("recovered"));
                    try(var owner=f.open(target,"reopen-after-ack")) {
                        assertEquals(1,owner.peerRetentionState().revision());
                        assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(f.request.targets().getLast().identity())));
                    }
                    Files.write(raw.resolve("result.json"),canonical(Map.of("mode",mode,"cut",point,"exit",(long)child.exitValue()),16384));
                    System.out.println("v53RetentionAckCrash="+mode+":"+point+" PASS");
                }finally{if(child.isAlive()){child.destroyForcibly();child.waitFor(10,TimeUnit.SECONDS);}}
            }
        }
    }
    private static Process process(MembershipBootstrapTarget<?,?> target,Path input,String mode,String point,Path log)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                V53RetentionAckWorker.class.getName(),target.replicaDirectory().toString(),target.materialization().directory().toString(),input.toString(),mode,point)
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
    }
}
