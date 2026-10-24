package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextMixedProcessTest {
    @TempDir Path temp;
    @Test void mixedBallotsRecoverAcrossRepeatedProcessDeath()throws Exception {
        var producer=new V53ContextMixedAcceptanceTest();producer.temp=Files.createDirectory(temp.resolve("seed"));var seed=producer.scenario(false);var driver=seed.driver();
        Path root=Path.of("target/v53-context-mixed-process/run-"+UUID.randomUUID());Files.createDirectories(root);driver.snapshot(seed.raw(),root.resolve("reference"));
        byte[] inputs=canonical(Map.of("observations",V53JournalApplicationTest.observations(driver.reference.seed().fixture().f.observations)),65536);Files.write(root.resolve("inputs.json"),inputs);
        var acceptPoints=new ArrayList<>(V53ContextAcceptanceTest.CUTS);acceptPoints.add("FLOOR_RELEASE_FILE_DELETED@2");
        var sourcePoints=new ArrayList<>(V53ContextSourceReleaseTest.CUTS);sourcePoints.add("SOURCE_RETIREMENT_FILE_DELETED@2");
        assertEquals(42,acceptPoints.size()+sourcePoints.size());var rows=new ArrayList<Map<String,Object>>();System.out.println("v53ContextMixedProcessEvidence="+root.toAbsolutePath());
        try {
            for(boolean accept:List.of(true,false))for(String mode:List.of("halt","kill"))for(String point:accept?acceptPoints:sourcePoints) {
                String name=mode+"-"+point,operation=accept?"accept":"source-retirement";Path path=Files.createDirectory(root.resolve(name));
                driver.snapshot(root.resolve("reference/"+(accept?"round-24/source-retired/node-1":"retired/node-2")),path.resolve("store"));
                int first=child(path,"fault",point,mode,false,operation);V53ContextCompletionProcessTest.snapshot(path,"crash");
                int second=child(path,"recovery",accept?"ACCEPT_ACTIVE_FORCED":"CONTEXT_SOURCE_PARENT_FORCED","halt",true,operation);V53ContextCompletionProcessTest.snapshot(path,"recovery-crash");
                int resumed=child(path,"resume","none","none",false,operation);V53ContextCompletionProcessTest.snapshot(path,"final");
                Path expected=root.resolve("reference/"+(accept?"accepted/node-1":"predecessors-retired/node-2"));
                assertEquals(V53BootstrapProgressResumeTest.safeFiles(expected),V53BootstrapProgressResumeTest.safeFiles(path.resolve("final")));
                rows.add(Map.of("case",name,"operation",operation,"mode",mode,"cut",point,"status","PASS","exitCodes",List.of(first,second,resumed)));
                System.out.println("v53ContextMixedProcessCase="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-mixed-process-v1","status",rows.size()==84?"PASS":"FAIL","cases",rows,"expectedCases",84,
                    "freshProcesses",rows.size()*3,"lockProbes",rows.stream().filter(v->v.get("mode").equals("kill")).count(),"inputsSha256",hash(inputs),
                    "historicalBootstrap","conditional-fixture","powerLoss",false,"runtimeEnabled",false),65536));
        }
        assertEquals(84,rows.size());
    }
    static int child(Path path,String label,String point,String mode,boolean duringOpen,String operation)throws Exception {
        Path stdout=path.resolve(label+".stdout"),stderr=path.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53ContextMixedProcessWorker.class.getName(),path.toAbsolutePath().toString(),point,mode,Boolean.toString(duringOpen),operation)
                .redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",point),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";long deadline=System.nanoTime()+60_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {
                    assertTrue(process.isAlive(),"mixed worker ended before kill marker: "+Files.readString(stderr));assertTrue(System.nanoTime()<deadline,"mixed process kill marker timeout");Thread.sleep(20);
                }
                new V53MembershipOwnershipTest().probe(path.resolve("store/replica.lock"));process.destroyForcibly();
            }
            assertTrue(process.waitFor(60,java.util.concurrent.TimeUnit.SECONDS),"mixed child timeout");
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));return process.exitValue();
        }finally {if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
}
