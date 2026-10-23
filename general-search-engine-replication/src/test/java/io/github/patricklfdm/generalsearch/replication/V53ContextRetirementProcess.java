package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Sequential fresh JVMs against the actual contextual journal owner, not the file component. */
final class V53ContextRetirementProcess {
    static void qualify(Path reference,Set<MembershipContext.Owned> observations)throws Exception {
        Path root=Path.of("target/v53-context-retirement-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(root);
        V53JournalApplicationTest.copy(reference,root.resolve("reference"));
        byte[] inputs=canonical(Map.of("observations",V53JournalApplicationTest.observations(observations)),65536);
        Files.write(root.resolve("inputs.json"),inputs);
        var points=new ArrayList<>(V53RetirementTest.CUTS);points.addAll(List.of("CONTEXT_SOURCE_PARENT_FORCED","CONTEXT_ACTIVE_FORCED"));
        var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(String point:points) {
                String name=mode+"-"+point;Path path=Files.createDirectory(root.resolve(name));
                V53JournalApplicationTest.copy(root.resolve("reference/floor"),path.resolve("store"));
                int fault=child(path,"fault",point,mode);snapshot(path,"crash");
                int recovery=child(path,"recovery","CONTEXT_SOURCE_PARENT_FORCED","halt");snapshot(path,"recovery-crash");
                assertEquals(V53ReplayFilesTest.files(path.resolve("crash")),V53ReplayFilesTest.files(path.resolve("recovery-crash")));
                int resume=child(path,"resume","none","none");snapshot(path,"final");
                assertEquals(V53ReplayFilesTest.files(root.resolve("reference/retired")),V53ReplayFilesTest.files(path.resolve("final")));
                rows.add(Map.of("case",name,"mode",mode,"cut",point,"status","PASS","exitCodes",List.of(fault,recovery,resume)));
                System.out.println("v53ContextRetirementProcessCase="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-retirement-process-v1","status",rows.size()==54?"PASS":"FAIL",
                    "cases",rows,"expectedCases",54,"freshProcesses",rows.size()*3,"inputsSha256",hash(inputs),
                    "historicalBootstrap","conditional-fixture","powerLoss",false,"nextCampaign",false),65536));
            System.out.println("v53ContextRetirementProcessEvidence="+root.toAbsolutePath());
        }
        assertEquals(54,rows.size());
    }
    static void snapshot(Path path,String name)throws Exception {V53JournalApplicationTest.copy(path.resolve("store"),path.resolve(name));}
    static int child(Path path,String label,String point,String mode)throws Exception {
        Path stdout=path.resolve(label+".stdout"),stderr=path.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53ContextRetirementWorker.class.getName(),path.toAbsolutePath().toString(),point,mode)
                .redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",point),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";
                long deadline=System.nanoTime()+60_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {
                    assertTrue(process.isAlive(),"worker ended before kill marker: "+stderr);assertTrue(System.nanoTime()<deadline,"context retirement kill marker timeout");Thread.sleep(20);
                }
                process.destroyForcibly();
            }
            assertTrue(process.waitFor(60,java.util.concurrent.TimeUnit.SECONDS),"context retirement child timeout");
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));return process.exitValue();
        }finally {if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
    private V53ContextRetirementProcess() {}
}
