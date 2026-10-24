package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextGenerationProcessTest {
    @TempDir Path temp;
    @Test void installationAndIntermediateRetirementSurviveRepeatedProcessDeath()throws Exception {
        var driver=new V53ContextInstallationLifetimeTest();driver.temp=Files.createDirectory(temp.resolve("seed"));var seed=driver.scenario();
        Path root=Path.of("target/v53-context-generation-process/run-"+UUID.randomUUID());Files.createDirectories(root);
        driver.snapshot(seed.evidence(),root.resolve("reference"));
        Files.write(root.resolve("inputs.json"),canonical(Map.of("observations",V53JournalApplicationTest.observations(driver.reference.seed().fixture().f.observations)),65536));
        var install=new ArrayList<>(V53GenerationInstallTest.CUTS);install.add("INSTALL_MEMBER_WRITTEN@2");
        var retire=new ArrayList<>(V53RetirementTest.CUTS);retire.add("RETIREMENT_FILE_DELETED@2");retire.add("RETIREMENT_SAVED_FILE_DELETED@2");
        var rows=new ArrayList<Map<String,Object>>();System.out.println("v53ContextGenerationProcessEvidence="+root.toAbsolutePath());System.out.flush();
        try {
            for(String operation:List.of("install","retire"))for(String mode:List.of("halt","kill"))for(String point:operation.equals("install")?install:retire) {
                String name=operation+"-"+mode+"-"+point;Path path=Files.createDirectory(root.resolve(name));
                String initial=operation.equals("install")?"selected":"installed";
                driver.snapshot(root.resolve("reference/round-22/"+initial+"/node-1"),path.resolve("store"));Files.createDirectory(path.resolve("peers"));
                for(int n:List.of(2,3))driver.snapshot(root.resolve("reference/round-22/selected/node-"+n),path.resolve("peers/node-"+n));
                int first=child(path,"fault",operation,point,mode,false);V53ContextCompletionProcessTest.snapshot(path,"crash");
                int second=child(path,"recovery",operation,"CONTEXT_SOURCE_PARENT_FORCED","halt",true);V53ContextCompletionProcessTest.snapshot(path,"recovery-crash");
                int last=child(path,"resume",operation,"none","none",false);V53ContextCompletionProcessTest.snapshot(path,"final");
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(path.resolve("final/pending.accept")));
                assertEquals(22L,object(vote.accept().value().get("ballot")).get("counter"));assertEquals(20L,object(vote.entry().value().get("origin")).get("counter"));
                assertFalse(Files.exists(path.resolve("final/pending.context")));assertFalse(Files.exists(path.resolve("final/floor-copies")));
                rows.add(Map.of("case",name,"operation",operation,"mode",mode,"cut",point,"status","PASS","exitCodes",List.of(first,second,last)));
                System.out.println("v53ContextGenerationProcessCase="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-generation-process-v1","status",rows.size()==84?"PASS":"FAIL",
                    "cases",rows,"expectedCases",84,"freshProcesses",rows.size()*3,"lockProbes",rows.stream().filter(v->v.get("mode").equals("kill")).count(),
                    "inputsSha256",hash(Files.readAllBytes(root.resolve("inputs.json"))),"historicalBootstrap","conditional-fixture","powerLoss",false,"runtimeEnabled",false),65536));
        }
        assertEquals(84,rows.size());
    }
    static int child(Path path,String label,String operation,String point,String mode,boolean duringOpen)throws Exception {
        Path stdout=path.resolve(label+".stdout"),stderr=path.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53ContextGenerationWorker.class.getName(),path.toAbsolutePath().toString(),operation,point,mode,Boolean.toString(duringOpen))
                .redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",point),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";
                long deadline=System.nanoTime()+60_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {
                    assertTrue(process.isAlive(),"worker ended before kill marker: "+Files.readString(stderr));assertTrue(System.nanoTime()<deadline,"generation kill marker timeout");Thread.sleep(20);
                }
                new V53MembershipOwnershipTest().probe(path.resolve("store/replica.lock"));process.destroyForcibly();
            }
            assertTrue(process.waitFor(60,java.util.concurrent.TimeUnit.SECONDS),"generation child timeout");
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));return process.exitValue();
        }finally {if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
}
