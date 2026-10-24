package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextInstalledSourceProcessTest {
    @TempDir Path temp;
    @Test void repeatedProcessDeathReclaimsObsoleteInstalledSourceAndForcesExactSuccessor()throws Exception {
        var driver=new V53ContextInstallationLifetimeTest();driver.temp=Files.createDirectory(temp.resolve("seed"));var scenario=driver.scenario();
        Path root=Path.of("target/v53-context-installed-source-process/run-"+UUID.randomUUID());Files.createDirectories(root);
        driver.snapshot(scenario.evidence(),root.resolve("reference"));
        driver.snapshot(scenario.evidence().resolve("round-23/generation-retired/node-1"),root.resolve("initial"));
        byte[] inputs=canonical(Map.of("observations",V53JournalApplicationTest.observations(driver.reference.seed().fixture().f.observations)),65536);
        Files.write(root.resolve("inputs.json"),inputs);
        var points=new ArrayList<>(V53ContextSourceReleaseTest.CUTS);points.add("SOURCE_RETIREMENT_FILE_DELETED@2");assertEquals(15,points.size());
        var rows=new ArrayList<Map<String,Object>>();System.out.println("v53ContextInstalledSourceProcessEvidence="+root.toAbsolutePath());
        try {
            for(String mode:List.of("halt","kill"))for(String point:points) {
                String name=mode+"-"+point;Path path=Files.createDirectory(root.resolve(name));driver.snapshot(root.resolve("initial"),path.resolve("store"));
                int first=child(path,"fault",point,mode,false);V53ContextCompletionProcessTest.snapshot(path,"crash");
                int second=child(path,"recovery","CONTEXT_SOURCE_PARENT_FORCED","halt",true);V53ContextCompletionProcessTest.snapshot(path,"recovery-crash");
                int resumed=child(path,"resume","none","none",false);V53ContextCompletionProcessTest.snapshot(path,"final");
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(path.resolve("final/pending.accept")));
                assertEquals(23L,object(vote.accept().value().get("ballot")).get("counter"));assertEquals(20L,object(vote.entry().value().get("origin")).get("counter"));
                assertFalse(Files.exists(path.resolve("final/pending.context")));assertFalse(Files.exists(path.resolve("final/floor-copies")));
                rows.add(Map.of("case",name,"mode",mode,"cut",point,"status","PASS","exitCodes",List.of(first,second,resumed)));
                System.out.println("v53ContextInstalledSourceProcessCase="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-installed-source-process-v1","status",rows.size()==30?"PASS":"FAIL",
                    "cases",rows,"expectedCases",30,"freshProcesses",rows.size()*3,"lockProbes",rows.stream().filter(v->v.get("mode").equals("kill")).count(),
                    "inputsSha256",hash(inputs),"historicalBootstrap","conditional-fixture","powerLoss",false,"runtimeEnabled",false),65536));
        }
        assertEquals(30,rows.size());
    }
    static int child(Path path,String label,String point,String mode,boolean duringOpen)throws Exception {
        Path stdout=path.resolve(label+".stdout"),stderr=path.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53ContextInstalledSourceWorker.class.getName(),path.toAbsolutePath().toString(),point,mode,Boolean.toString(duringOpen))
                .redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",point),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";
                long deadline=System.nanoTime()+60_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {
                    assertTrue(process.isAlive(),"worker ended before kill marker: "+Files.readString(stderr));assertTrue(System.nanoTime()<deadline,"installed source kill marker timeout");Thread.sleep(20);
                }
                new V53MembershipOwnershipTest().probe(path.resolve("store/replica.lock"));process.destroyForcibly();
            }
            assertTrue(process.waitFor(60,java.util.concurrent.TimeUnit.SECONDS),"installed source child timeout");
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));return process.exitValue();
        }finally {if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
}
