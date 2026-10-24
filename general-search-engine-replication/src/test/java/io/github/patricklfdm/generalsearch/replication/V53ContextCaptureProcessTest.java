package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextCaptureProcessTest {
    @TempDir Path temp;
    @Test void repeatedProcessDeathCompletesCaptureRetirementAndAnotherFreshGrant()throws Exception {
        V53ContextCaptureTest.fixtures=Files.createDirectory(temp.resolve("seed"));V53ContextCaptureTest.retainedOriginal();
        Path reference=V53ContextCaptureTest.base,root=Path.of("target/v53-context-capture-process/run-"+UUID.randomUUID());Files.createDirectories(root);
        V53JournalApplicationTest.copy(reference,root.resolve("reference"));V53JournalApplicationTest.copy(reference.resolve("reopened"),root.resolve("initial"));
        var used=V53ContextRetirementTest.resources();
        try(var owner=V53ContextCaptureTest.open(root.resolve("initial"),used,e->{})){owner.prepareCurrent(V53ContextCaptureTest.ballot(22));}
        assertEquals(0,used.usage().leases());
        byte[] input=canonical(Map.of("observations",V53JournalApplicationTest.observations(V53ContextRetirementTest.seed.fixture().f.observations)),65536);Files.write(root.resolve("inputs.json"),input);
        var points=new ArrayList<>(V53ContextCaptureTest.CUTS);points.add("CONTEXT_SOURCE_MEMBER_FORCED@2");points.addAll(V53ContextBackingRetirementTest.CUTS);points.add("SOURCE_RETIREMENT_FILE_DELETED@2");
        assertEquals(50,points.size());var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(String point:points) {
                String name=mode+"-"+point;Path path=Files.createDirectory(root.resolve(name));V53JournalApplicationTest.copy(root.resolve("initial"),path.resolve("store"));
                int first=child(path,"fault",point,mode,false);V53ContextCompletionProcessTest.snapshot(path,"crash");
                int second=child(path,"recovery","CONTEXT_SOURCE_PARENT_FORCED","halt",true);V53ContextCompletionProcessTest.snapshot(path,"recovery-crash");
                int resumed=child(path,"resume","none","none",false);V53ContextCompletionProcessTest.snapshot(path,"final");
                assertArrayEquals(Files.readAllBytes(root.resolve("initial/pending.accept")),Files.readAllBytes(path.resolve("final/pending.accept")));
                rows.add(Map.of("case",name,"mode",mode,"cut",point,"status","PASS","exitCodes",List.of(first,second,resumed)));
                System.out.println("v53ContextCaptureProcessCase="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-capture-process-v1","status",rows.size()==100?"PASS":"FAIL",
                    "cases",rows,"expectedCases",100,"freshProcesses",rows.size()*3,"lockProbes",rows.stream().filter(v->v.get("mode").equals("kill")).count(),
                    "inputsSha256",hash(input),"historicalBootstrap","conditional-fixture","powerLoss",false,"runtimeEnabled",false),65536));
            System.out.println("v53ContextCaptureProcessEvidence="+root.toAbsolutePath());
        }
        assertEquals(100,rows.size());
    }
    static int child(Path path,String label,String point,String mode,boolean duringOpen)throws Exception {
        Path stdout=path.resolve(label+".stdout"),stderr=path.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53ContextCaptureWorker.class.getName(),path.toAbsolutePath().toString(),point,mode,Boolean.toString(duringOpen))
                .redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",point),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";
                long deadline=System.nanoTime()+60_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {
                    assertTrue(process.isAlive(),"worker ended before kill marker: "+Files.readString(stderr));assertTrue(System.nanoTime()<deadline,"capture kill marker timeout");Thread.sleep(20);
                }
                new V53MembershipOwnershipTest().probe(path.resolve("store/replica.lock"));process.destroyForcibly();
            }
            assertTrue(process.waitFor(60,java.util.concurrent.TimeUnit.SECONDS),"capture child timeout");
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));return process.exitValue();
        }finally {if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
}
