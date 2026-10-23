package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Unmarked promises preserve their fence; damaged promises preserve all bytes and refuse open. */
class V53PromiseBoundaryTest {
    @TempDir Path temp;
    static List<Map<String,Object>> profiles() {
        var rows=new ArrayList<Map<String,Object>>();
        for(int size:List.of(3,4,5))for(int through:List.of(0,6,7))for(String mode:List.of("halt","kill"))
            rows.add(Map.of("size",(long)size,"through",(long)through,"mode",mode,"cut","PROMISE_FORCED"));
        for(String cut:List.of("PROMISE_BEFORE_WRITE","PROMISE_WRITTEN","DAMAGED_HEADER","DAMAGED_BODY"))for(String mode:List.of("halt","kill"))
            rows.add(Map.of("size",3L,"through",1L,"mode",mode,"cut",cut));
        return rows;
    }
    static String name(Map<String,Object> row){return row.get("size")+"-"+row.get("through")+"-"+row.get("mode")+"-"+row.get("cut");}
    @Test void unmarkedPromisesAndInjectedTornPrefixesKeepTheirOriginalAuthorityAcrossProcesses()throws Exception {
        Path retained=Path.of("target/v53-promise-boundaries").resolve("run-"+UUID.randomUUID());Files.createDirectories(retained);
        var rows=new ArrayList<Map<String,Object>>();int processes=0;
        try {
            for(var profile:profiles()) {
                Path work=retained.resolve(name(profile)),node=work.resolve("node-1");Files.createDirectory(work);
                Files.write(work.resolve("profile.json"),canonical(profile,4096));
                var f=new V53CurrentGenerationFixture(Math.toIntExact((long)profile.get("size")),Math.toIntExact((long)profile.get("through")),true);f.provision(node);
                V53JournalApplicationTest.copy(node,work.resolve("initial"));var exits=new TreeMap<String,Object>();String point=(String)profile.get("cut"),mode=(String)profile.get("mode");
                exits.put("fault",child(work,"fault","fault",mode));processes++;V53JournalApplicationTest.copy(node,work.resolve("crash"));
                exits.put("inspect",child(work,"inspect","inspect","none"));processes++;V53JournalApplicationTest.copy(node,work.resolve("inspected"));
                if(point.startsWith("DAMAGED_")) {
                    exits.put("inspectAgain",child(work,"inspectAgain","inspect","none"));processes++;
                    assertEquals(V53ReplayFilesTest.files(work.resolve("crash")),V53ReplayFilesTest.files(node));
                }else {
                    exits.put("resume",child(work,"resume","resume","none"));processes++;V53JournalApplicationTest.copy(node,work.resolve("resumed"));
                    exits.put("duplicate",child(work,"duplicate","duplicate","none"));processes++;
                    assertEquals(V53ReplayFilesTest.files(work.resolve("resumed")),V53ReplayFilesTest.files(node));
                }
                V53JournalApplicationTest.copy(node,work.resolve("final"));
                rows.add(Map.of("profile",profile,"processes",exits,"status","PASS"));System.out.println("v53PromiseBoundaryCase="+name(profile)+" PASS");
            }
        }finally {
            Files.write(retained.resolve("receipt.json"),canonical(Map.of("execution","private-promise-boundaries","cases",rows,"expectedCases",26L,
                    "freshJvms",(long)processes,"historicalOwnership","conditional-fixture","damageInjection","test-only-truncate-after-whole-frame-write","powerLoss",false,"runtimeEnabled",false),65536));
            System.out.println("v53PromiseBoundaryEvidence="+retained.toAbsolutePath());
        }
        assertEquals(26,rows.size());assertEquals(100,processes);
    }
    static int child(Path work,String label,String command,String mode)throws Exception {
        Path stdout=work.resolve(label+".stdout"),stderr=work.resolve(label+".stderr");
        var proc=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53PromiseBoundaryWorker.class.getName(),work.toAbsolutePath().toString(),command,mode).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                long end=System.nanoTime()+30_000_000_000L;
                while(!Files.readString(stdout).contains("AWAITING_KILL")){assertTrue(proc.isAlive(),Files.readString(stderr));assertTrue(System.nanoTime()<end,"kill deadline");Thread.sleep(20);}proc.destroyForcibly();
            }
            assertTrue(proc.waitFor(30,java.util.concurrent.TimeUnit.SECONDS),"worker deadline");int code=proc.exitValue();
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,code,Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));return code;
        }finally {if(proc.isAlive())proc.destroyForcibly();proc.waitFor();}
    }
    @Test void everyPartialOriginalPromiseRefusesWithoutRepairOrOwnerLeak()throws Exception {
        Path node=temp.resolve("node");var f=new V53CurrentGenerationFixture(3,1,true);f.provision(node);byte[] original=Files.readAllBytes(node.resolve("grants.gsr"));
        var helper=new V53CaptureRecoveryTest();helper.interrupt(node,f,"PROMISE_WRITTEN");byte[] complete=Files.readAllBytes(node.resolve("grants.gsr"));
        for(int length=1;length<complete.length-original.length;length++) {
            Files.write(node.resolve("grants.gsr"),Arrays.copyOf(complete,original.length+length));var before=V53ReplayFilesTest.files(node);var r=helper.resources();
            String reason=length<HEADER?"torn grant journal header":"torn grant journal body";
            for(int repeat=0;repeat<2;repeat++) {
                assertEquals(reason,assertThrows(IllegalArgumentException.class,()->helper.open(node,f,r,e->{})).getMessage());
                assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,r.usage().leases());
            }
        }
        Files.write(node.resolve("grants.gsr"),complete);var r=helper.resources();
        try(var store=helper.open(node,f,r,e->{})){assertTrue(store.originalBasis().isEmpty());assertEquals(20L,object(store.promised().orElseThrow().value().get("ballot")).get("counter"));}
        assertEquals(0,r.usage().leases());
    }
}
