package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53BootstrapAdmissionProcessTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of(
        "BOOTSTRAP_COMMITTED_PREFIX_WRITTEN",
        "BOOTSTRAP_COMMITTED_DURABLE",
        "BOOTSTRAP_ADMISSION_0_CREATED",
        "BOOTSTRAP_ADMISSION_0_PREFIX_WRITTEN",
        "BOOTSTRAP_ADMISSION_0_WRITTEN",
        "BOOTSTRAP_ADMISSION_0_FORCED",
        "BOOTSTRAP_ADMISSION_0_PARENT_FORCED",
        "BOOTSTRAP_ADMISSION_2_CREATED",
        "BOOTSTRAP_ADMISSION_2_PREFIX_WRITTEN",
        "BOOTSTRAP_ADMISSION_2_WRITTEN",
        "BOOTSTRAP_ADMISSION_2_FORCED",
        "BOOTSTRAP_ADMISSION_2_PARENT_FORCED",
        "BOOTSTRAP_SEAL_0_CANDIDATE_CREATED",
        "BOOTSTRAP_SEAL_0_CANDIDATE_PREFIX_WRITTEN",
        "BOOTSTRAP_SEAL_0_CANDIDATE_WRITTEN",
        "BOOTSTRAP_SEAL_0_CANDIDATE_FORCED",
        "BOOTSTRAP_SEAL_0_CANDIDATE_PARENT_FORCED",
        "BOOTSTRAP_SEAL_0_RENAMED",
        "BOOTSTRAP_SEAL_0_ACTIVE_FORCED",
        "BOOTSTRAP_SEAL_0_ACTIVE_PARENT_FORCED",
        "BOOTSTRAP_COMMITTED_BEFORE_RETURN");
    static void child(Path root,String label,String point,String mode,boolean resume)throws Exception {
        Path stdout=root.resolve(label+".stdout"),stderr=root.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53BootstrapAdmissionWorker.class.getName(),root.toAbsolutePath().toString(),point,mode,Boolean.toString(resume)).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                long end=System.nanoTime()+120_000_000_000L;
                while(!Files.readString(stdout).contains("AWAITING_KILL")){assertTrue(process.isAlive(),Files.readString(stderr));assertTrue(System.nanoTime()<end,"worker cut deadline");Thread.sleep(20);}
                process.destroyForcibly();
            }
            assertTrue(process.waitFor(120,TimeUnit.SECONDS),"worker completion deadline");assertEquals(mode.equals("halt")?83:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));
            assertEquals("",Files.readString(stderr));
        }finally{if(process.isAlive()){process.destroyForcibly();process.waitFor(10,TimeUnit.SECONDS);}}
    }
    @Test void repeatedHaltAndSigkillPreserveAdmissionBeforeSeals()throws Exception {
        var helper=new V53BootstrapTransactionTest();helper.temp=temp;
        Path evidence=Path.of("target/v53-bootstrap-admission-process/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();int n=0;
        for(String cut:CUTS)for(String mode:List.of("halt","kill")) {
            var plan=helper.fixture("case-"+n,3,false);Path member=Files.createDirectory(evidence.resolve(String.format("case-%03d",n)));
            Files.write(member.resolve("original-plan.gsbp"),plan.bytes());Files.write(member.resolve("original-application.image"),plan.seed.application());
            child(member,"first",cut,mode,false);V53BootstrapTransactionTest.copy(plan,member.resolve("crash"));
            child(member,"second","BOOTSTRAP_ADMISSION_0_FORCED",mode,true);V53BootstrapTransactionTest.copy(plan,member.resolve("second-crash"));
            child(member,"resumed","none","none",true);V53BootstrapAdmissionFilesTest.verify(plan);V53BootstrapTransactionTest.copy(plan,member.resolve("final"));
            rows.add(Map.of("case",member.getFileName().toString(),"cut",cut,"mode",mode,"plan",plan.digest(),"status","PASS"));n++;
            if(n%4==0)System.out.println("v53BootstrapAdmissionProcessProgress="+n+"/"+(CUTS.size()*2));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-admission-process-v1","status","PASS","cases",rows,"freshProcesses",3*n,"publicBootstrap",false,"typedCoordinator",false),65536));
        System.out.println("v53BootstrapAdmissionProcessEvidence="+evidence.toAbsolutePath());
    }
}
