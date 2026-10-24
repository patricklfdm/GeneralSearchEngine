package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Sequential actual owners: source retirement, successor force, context and floor withdrawal. */
class V53ContextCompletionProcessTest {
    @TempDir Path temp;
    @Test void processDeathAndRepeatedRecoveryPreserveTheOnlyExactSuccessor()throws Exception {
        V53ContextSourceReleaseTest.fixtures=Files.createDirectory(temp.resolve("seed"));V53ContextSourceReleaseTest.originalRetirement();
        var producer=new V53ContextSourceReleaseTest();producer.temp=Files.createDirectory(temp.resolve("reference"));Path reference=producer.releaseScenario();
        Path root=Path.of("target/v53-context-completion-process/run-"+UUID.randomUUID());Files.createDirectories(root);
        V53JournalApplicationTest.copy(reference,root.resolve("reference"));
        byte[] inputs=canonical(Map.of("observations",V53JournalApplicationTest.observations(V53ContextRetirementTest.seed.fixture().f.observations)),65536);
        Files.write(root.resolve("inputs.json"),inputs);
        var points=new ArrayList<>(V53ContextSourceReleaseTest.CUTS);points.add("SOURCE_RETIREMENT_FILE_DELETED@2");
        points.addAll(V53ContextAcceptanceTest.CUTS);points.addAll(List.of("FLOOR_RELEASE_FILE_DELETED@2","FLOOR_RELEASE_FILE_DELETED@4"));
        assertEquals(43,points.size());var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(String point:points) {
                String name=mode+"-"+point;Path path=Files.createDirectory(root.resolve(name));
                boolean source=point.startsWith("SOURCE_") || point.startsWith("JOURNAL_");
                V53JournalApplicationTest.copy(reference.resolve(source?"original-retirement/retired":"reopened"),path.resolve("store"));
                int first=child(path,"fault",point,mode);snapshot(path,"crash");
                int second=child(path,"recovery","ACCEPT_ACTIVE_FORCED","halt");snapshot(path,"recovery-crash");
                int resumed=child(path,"resume","none","none");snapshot(path,"final");
                V53ContextAcceptanceTest.completed(path.resolve("final"),V53BootstrapProgressResumeTest.safeFiles(reference.resolve("reopened")));
                rows.add(Map.of("case",name,"mode",mode,"cut",point,"sourceRetirement",source,"status","PASS","exitCodes",List.of(first,second,resumed)));
                System.out.println("v53ContextCompletionProcessCase="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-completion-process-v1","status",rows.size()==86?"PASS":"FAIL",
                    "cases",rows,"expectedCases",86,"freshProcesses",rows.size()*3,"lockProbes",rows.stream().filter(v->v.get("mode").equals("kill")).count(),
                    "inputsSha256",hash(inputs),"historicalBootstrap","conditional-fixture","powerLoss",false,"runtimeEnabled",false),65536));
            System.out.println("v53ContextCompletionProcessEvidence="+root.toAbsolutePath());
        }
        assertEquals(86,rows.size());
    }
    static void snapshot(Path path,String name)throws Exception {V53JournalApplicationTest.copy(path.resolve("store"),path.resolve(name));}
    static int child(Path path,String label,String point,String mode)throws Exception {
        Path stdout=path.resolve(label+".stdout"),stderr=path.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53ContextCompletionWorker.class.getName(),path.toAbsolutePath().toString(),point,mode)
                .redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",point),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";
                long deadline=System.nanoTime()+60_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {
                    assertTrue(process.isAlive(),"worker ended before kill marker: "+Files.readString(stderr));assertTrue(System.nanoTime()<deadline,"context completion kill marker timeout");Thread.sleep(20);
                }
                new V53MembershipOwnershipTest().probe(path.resolve("store/replica.lock"));process.destroyForcibly();
            }
            assertTrue(process.waitFor(60,java.util.concurrent.TimeUnit.SECONDS),"context completion child timeout");
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));return process.exitValue();
        }finally {if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
}
