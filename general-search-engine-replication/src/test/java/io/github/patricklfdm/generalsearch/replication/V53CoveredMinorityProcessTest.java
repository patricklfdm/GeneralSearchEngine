package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53CoveredMinorityProcessTest {
    @TempDir Path temp;
    @Test void admittedCoveredMinorityRecoversFromRepeatedProcessDeath()throws Exception {
        var producer=new V53CoveredMinorityTest();producer.temp=Files.createDirectory(temp.resolve("producer"));var prepared=producer.prepared();var f=prepared.f();
        Path out=Path.of("target/v53-covered-minority-process/run-"+UUID.randomUUID());Files.createDirectories(out);
        Files.write(f.raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
        V53JournalApplicationTest.copy(f.raw,out.resolve("reference"));
        var targets=f.request.targets().stream().map(t->Map.of("node",t.replicaDirectory().toString(),"materialization",t.materialization().directory().toString())).toList();
        Path inputs=out.resolve("inputs.json");Files.write(inputs,canonical(Map.of("targets",targets,"observations",V53JournalApplicationTest.observations(f.observations)),1024*1024));
        Path node=f.request.targets().getFirst().replicaDirectory(),seed=temp.resolve("seed");V53JournalApplicationTest.copy(node,seed);
        System.out.println("v53CoveredMinorityProcessEvidence="+out.toAbsolutePath());var rows=new ArrayList<Map<String,Object>>();int ordinal=0;
        try {
            for(String mode:List.of("halt","kill"))for(String cut:List.of("INSTALL_MANIFEST_FORCED","INSTALL_SELECTOR_RENAMED","INSTALL_SELECTOR_FORCED","SETTLED_VOTE_VALIDATED",
                    "SETTLED_VOTE_CANDIDATE_CREATED","SETTLED_VOTE_PREFIX_WRITTEN","SETTLED_VOTE_CANDIDATE_WRITTEN","SETTLED_VOTE_CANDIDATE_FORCED",
                    "SETTLED_VOTE_CANDIDATE_PARENT_FORCED","SETTLED_VOTE_RENAMED","SETTLED_VOTE_PARENT_FORCED","SETTLED_VOTE_BEFORE_RETURN")) {
                producer.reset(prepared,seed,"process-original-"+ordinal++);String name=mode+"-"+cut;Path path=Files.createDirectory(out.resolve(name));
                int first=child(inputs,node,path,"fault",cut,mode);V53JournalApplicationTest.copy(node,path.resolve("first"));
                String second=Set.of("INSTALL_MANIFEST_FORCED","SETTLED_VOTE_RENAMED","SETTLED_VOTE_PARENT_FORCED","SETTLED_VOTE_BEFORE_RETURN").contains(cut)?"ACCEPT_ACTIVE_FORCED":"SETTLED_VOTE_CANDIDATE_PARENT_FORCED";
                int again=child(inputs,node,path,"recovery",second,"halt");V53JournalApplicationTest.copy(node,path.resolve("second"));
                int resumed=child(inputs,node,path,"resume","none","none");V53JournalApplicationTest.copy(node,path.resolve("final"));
                rows.add(Map.of("case",name,"mode",mode,"cut",cut,"second",second,"status","PASS","exitCodes",List.of(first,again,resumed)));
                System.out.println("v53CoveredMinorityProcessCase="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-covered-minority-process-v1","status",rows.size()==24?"PASS":"FAIL","cases",rows,
                    "freshProcesses",rows.size()*3,"lockProbes",rows.stream().filter(row->row.get("mode").equals("kill")).count(),"inputsSha256",hash(Files.readAllBytes(inputs)),
                    "publicBootstrap",true,"powerLoss",false,"runtimeEnabled",false),65536));
        }
        assertEquals(24,rows.size());
    }
    static int child(Path inputs,Path node,Path path,String label,String cut,String mode)throws Exception {
        Path stdout=path.resolve(label+".stdout"),stderr=path.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53CoveredMinorityProcessWorker.class.getName(),inputs.toAbsolutePath().toString(),cut,mode).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",cut),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";long deadline=System.nanoTime()+60_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {
                    assertTrue(process.isAlive(),"covered worker exited before kill marker: "+Files.readString(stderr));assertTrue(System.nanoTime()<deadline,"covered kill marker timeout");Thread.sleep(20);
                }
                new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));process.destroyForcibly();
            }
            assertTrue(process.waitFor(60,java.util.concurrent.TimeUnit.SECONDS),"covered child timeout");
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));return process.exitValue();
        }finally {if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
}
