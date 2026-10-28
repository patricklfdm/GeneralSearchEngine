package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53DepartingEndProcessTest {
    @Test void allFiveProfilesRecoverRepeatedProcessDeathWithoutAcknowledgements()throws Exception {
        Path retained=Path.of("target/v53-departing-end-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(retained);
        var rows=new ArrayList<Map<String,Object>>();
        try {
            for(String profile:V53DepartingEndTest.PROFILES) {
                var plan=V53DepartingEndTest.plan(profile);var local=V53DepartingEndTest.local(profile);
                for(String mode:List.of("halt","kill"))for(String point:V53DepartingEndTest.cuts()) {
                    Path root=retained.resolve(profile+"-"+mode+"-"+point);Files.createDirectory(root);Files.write(root.resolve("owner.lock"),new byte[0]);
                    Files.write(root.resolve("entry.gsr"),plan.originalEntry().bytes());
                    Files.write(root.resolve("parent.json"),canonical(MembershipRetentionIntent.anchor(plan.originalParent()),16384));
                    child(root,"fault",point,mode,profile);V53AppliedEndFilesTest.snapshot(root,"crash");
                    child(root,"recovery-fault","APPLY_IMAGE_PREFIX_WRITTEN","halt",profile);V53AppliedEndFilesTest.snapshot(root,"recovery-crash");
                    child(root,"resume","none","none",profile);V53AppliedEndFilesTest.snapshot(root,"final");
                    assertEquals(V53DepartingEndTest.FILES,V53DepartingEndTest.files(root.resolve("end")).keySet());
                    assertArrayEquals(plan.application.image(),Files.readAllBytes(root.resolve("end/application.image")));
                    rows.add(Map.of("profile",profile,"mode",mode,"cut",point,"status","PASS","statement",plan.statement.digest(),"node",local.nodeId().value()));
                    System.out.println("v53DepartingEndCase="+root.getFileName());
                }
            }
        }finally {
            Files.write(retained.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-departing-end-v1","cases",rows,
                    "expectedCases",170L,"powerLoss",false,"protocolAuthority","conditional-fixture"),262144));
            System.out.println("v53DepartingEndEvidence="+retained.toAbsolutePath());
        }
        assertEquals(170,rows.size());
    }
    static void child(Path root,String label,String point,String mode,String profile)throws Exception {
        Path stdout=root.resolve(label+".stdout"),stderr=root.resolve(label+".stderr");
        var proc=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53DepartingEndWorker.class.getName(),root.toAbsolutePath().toString(),point,mode,profile)
                .redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",point),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";
                long deadline=System.nanoTime()+30_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {
                    assertTrue(proc.isAlive(),"worker exited before kill marker: "+Files.readString(stderr));assertTrue(System.nanoTime()<deadline,"kill marker deadline");Thread.sleep(20);
                }
                proc.destroyForcibly();
            }
            assertTrue(proc.waitFor(30,java.util.concurrent.TimeUnit.SECONDS),"worker deadline: "+root);
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,proc.exitValue(),Files.readString(stderr));
            assertEquals("",Files.readString(stderr));assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));
        }finally{if(proc.isAlive())proc.destroyForcibly();proc.waitFor();}
    }
}
