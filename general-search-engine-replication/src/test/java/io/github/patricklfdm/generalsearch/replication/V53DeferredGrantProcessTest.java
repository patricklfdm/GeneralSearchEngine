package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Bounded fresh-JVM regression for the unexposed promise, not a native quorum matrix. */
class V53DeferredGrantProcessTest {
    static final List<String> CUTS=List.of("PROMISE_FORCED","FLOOR_BEFORE_RETURN","SOURCE_RETIREMENT_JOURNAL_PRUNED",
            "FLOOR_RELEASE_BEFORE_RETURN","CAPTURE_INTENT_FORCED","SOURCE_PACKET_PREFIX_WRITTEN","BASIS_FORCED");
    @Test @EnabledIfSystemProperty(named="v53.deferred.process",matches="true")
    void originalPromiseSurvivesDeathBeforeAndAfterCaptureIntent()throws Exception {
        Path root=Files.createDirectories(Path.of("target/v53-deferred-grant-process/run-"+UUID.randomUUID()));
        System.out.println("v53DeferredGrantProcessEvidence="+root.toAbsolutePath());
        var fixture=new V53DeferredGrantTest();fixture.temp=root;var seed=fixture.provision("seed");
        Files.write(root.resolve("inputs.json"),canonical(Map.of("sources",seed.sources()),65536));
        var original=V53ReplayFilesTest.files(root.resolve("seed"));var rows=new ArrayList<Object>();boolean success=false;
        try {
            for(String mode:List.of("halt","kill"))for(String cut:CUTS) {
                String name=mode+"-"+cut;Path path=Files.createDirectory(root.resolve(name));
                V53RetirementImagesTest.copy(root.resolve("seed"),path.resolve("owners"));
                var fault=child(path,"fault",cut,mode);V53DeferredGrantProcessWorker.snapshot(path.resolve("owners/node-1"),path,"crash");
                var resumed=child(path,"resume","none","none");var cold=child(path,"inspect","none","none");
                assertEquals(3,Set.of(fault.get("pid"),resumed.get("pid"),cold.get("pid")).size());
                assertEquals(V53ReplayFilesTest.files(path.resolve("final")),V53ReplayFilesTest.files(path.resolve("cold")));
                rows.add(Map.of("case",name,"cut",cut,"mode",mode,"processes",List.of(fault,resumed,cold),"status","PASS"));
                System.out.println("v53DeferredGrantProcessCase="+name+" PASS");System.out.flush();
            }
            assertEquals(original,V53ReplayFilesTest.files(root.resolve("seed")));success=true;
        }finally {
            Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-deferred-grant-process-v1",
                    "status",success?"PASS":"FAIL","cases",rows,"expectedCases",2*CUTS.size(),
                    "historicalAuthority","conditional-fixture","nativeHistoryQualified",false,"powerLossQualified",false,"phase3Complete",false),65536));
        }
    }
    static Map<String,Object> child(Path path,String action,String cut,String mode)throws Exception {
        Path stdout=path.resolve(action+".stdout"),stderr=path.resolve(action+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53DeferredGrantProcessWorker.class.getName(),path.toAbsolutePath().toString(),action,cut,mode)
                .redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",cut),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";
                long deadline=System.nanoTime()+60_000_000_000L;
                while(!Files.exists(stdout) || !Files.readString(stdout).endsWith(marker)) {
                    assertTrue(process.isAlive(),"worker ended before marker: "+Files.readString(stderr));
                    assertTrue(System.nanoTime()<deadline,"deferred kill marker timeout");Thread.sleep(20);
                }
                new V53MembershipOwnershipTest().probe(path.resolve("owners/node-1/replica.lock"));process.destroyForcibly();
            }
            assertTrue(process.waitFor(90,TimeUnit.SECONDS),"deferred child timeout");
            int expected=mode.equals("halt")?73:mode.equals("kill")?137:0;
            assertEquals(expected,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(expected==0,Files.readString(stdout).contains("\"status\":\"PASS\""));
            return Map.of("pid",process.pid(),"action",action,"exit",process.exitValue(),"lockProbe",mode.equals("kill"));
        }finally{if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
}
