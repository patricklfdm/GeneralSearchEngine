package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53SelectedRetentionCrashTest {
    @TempDir Path temp;
    @Test void selectorAndMergeRecoverTogetherAcrossRealProcessDeath()throws Exception {
        var helper=new V53SelectedRetentionTest();helper.temp=temp;var f=helper.fixture("crash");
        f.campaign(1);f.publish(1,false);var self=f.request.targets().get(1);var first=f.request.targets().getFirst();var peer=f.request.targets().get(2);
        try(var owner=f.open(first,"dispatch")){owner.retainPeerDispatch(peer.identity());}
        Map<String,Object> ballot;try(var owner=f.open(first,"allocate")){ballot=Map.of("counter",owner.reserveCounter(),"proposer",first.identity().nodeId().value(),"incarnation",first.identity().storageId().toString());}
        var sources=new ArrayList<MembershipSelection.Source>();
        for(var t:f.request.targets())try(var owner=f.open(t,"prepare")){owner.prepareCurrent(ballot);sources.add(owner.originalSource());}
        for(var t:f.request.targets())try(var owner=f.open(t,"select")){owner.selectCurrent(sources,List.of());}
        f.snapshot("ready");
        Path inputs=f.raw.resolve("nodes.json");Files.write(inputs,canonical(f.request.targets().stream().map(t->Map.of("replica",t.replicaDirectory().toString(),"application",t.materialization().directory().toString())).toList(),65536));
        int ordinal=0;
        for(String mode:List.of("halt","kill"))for(String point:List.of("INSTALL_GENERATION_FORCED","INSTALL_SELECTOR_RENAMED","INSTALL_PARENT_FORCED",
                "RETENTION_PREFIX_WRITTEN","RETENTION_FORCED","RETENTION_RENAMED","RETENTION_PARENT_FORCED","SELECTED_RETENTION_COMPLETED")) {
            // Each fault starts from the same actual prepared history, copied only
            // with all owners closed. Preserve every interrupted and continued state.
            Files.move(self.replicaDirectory(),temp.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(f.raw.resolve("ready/node-2"),self.replicaDirectory());
            Path raw=Files.createDirectory(f.raw.resolve(mode+"-"+point)),log=raw.resolve("worker.log");
            var child=process(inputs,mode,point,log);
            try {
                long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(60);
                while(child.isAlive() && !Files.readString(log).contains("CUT "+point) && System.nanoTime()<deadline)Thread.sleep(10);
                assertTrue(Files.readString(log).contains("CUT "+point),Files.readString(log));assertFalse(Files.readString(log).contains("RESPONSE"));
                if(mode.equals("kill")){assertThrows(Exception.class,()->f.open(self,"lock-probe"));child.destroyForcibly();}
                assertTrue(child.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                V53JournalApplicationTest.copy(self.replicaDirectory(),raw.resolve("interrupted"));
                var resume=process(inputs,"resume","none",raw.resolve("resume.log"));
                try{assertTrue(resume.waitFor(60,TimeUnit.SECONDS));assertEquals(0,resume.exitValue(),Files.readString(raw.resolve("resume.log")));}
                finally{if(resume.isAlive()){resume.destroyForcibly();resume.waitFor(10,TimeUnit.SECONDS);}}
                V53JournalApplicationTest.copy(self.replicaDirectory(),raw.resolve("recovered"));
                try(var owner=f.open(self,"reopen-after-merge")) {
                    assertEquals(1,owner.peerRetentionState().revision());
                    assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
                }
                assertEquals(0,f.resources.usage().leases());
                Files.write(raw.resolve("result.json"),canonical(Map.of("status","PASS","mode",mode,"cut",point,"exit",(long)child.exitValue()),16384));
                System.out.println("v53SelectedRetentionCrash="+mode+":"+point+" PASS");
            }finally{if(child.isAlive()){child.destroyForcibly();child.waitFor(10,TimeUnit.SECONDS);}}
        }
        Files.write(f.raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));
    }
    private static Process process(Path inputs,String mode,String point,Path log)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                V53SelectedRetentionWorker.class.getName(),inputs.toString(),mode,point).redirectErrorStream(true).redirectOutput(log.toFile()).start();
    }
}
