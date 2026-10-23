package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53BootstrapTransactionProcessTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("BOOTSTRAP_PREPARING_PREFIX_WRITTEN","BOOTSTRAP_PREPARING_DURABLE",
        "BOOTSTRAP_TARGET_1_CREATED","BOOTSTRAP_DIRECTORY_0_generations/a_CREATED","BOOTSTRAP_PAYLOAD_0_root.gsr_PREFIX_WRITTEN",
        "BOOTSTRAP_PAYLOAD_0_grants.gsr_FORCED","BOOTSTRAP_PAYLOAD_0_selector.gsr_PARENT_FORCED","BOOTSTRAP_PREPARATION_0_PREFIX_WRITTEN",
        "BOOTSTRAP_PREPARATION_2_PARENT_FORCED","BOOTSTRAP_PREPARED_PREFIX_WRITTEN","BOOTSTRAP_PREPARED_DURABLE",
        "BOOTSTRAP_COMMITTING_PREFIX_WRITTEN","BOOTSTRAP_COMMITTING_DURABLE","BOOTSTRAP_RECEIPT_CANDIDATE_PREFIX_WRITTEN",
        "BOOTSTRAP_RECEIPT_CANDIDATE_PARENT_FORCED","BOOTSTRAP_RECEIPT_RENAMED","BOOTSTRAP_RECEIPT_ACTIVE_FORCED",
        "BOOTSTRAP_COMMITTED_PREFIX_WRITTEN","BOOTSTRAP_COMMITTED_DURABLE","BOOTSTRAP_SEAL_0_CANDIDATE_PREFIX_WRITTEN",
        "BOOTSTRAP_SEAL_0_RENAMED","BOOTSTRAP_SEAL_2_CANDIDATE_PARENT_FORCED","BOOTSTRAP_SEAL_2_ACTIVE_PARENT_FORCED","BOOTSTRAP_COMMITTED_BEFORE_RETURN");
    static void child(Path root,String label,String point,String mode,boolean resume)throws Exception {
        Path stdout=root.resolve(label+".stdout"),stderr=root.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53BootstrapTransactionWorker.class.getName(),root.toAbsolutePath().toString(),point,mode,Boolean.toString(resume)).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
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
    @Test void repeatedHaltAndSigkillKeepOriginalDecisionsAndPublishOnlyCommittedSeals()throws Exception {
        var helper=new V53BootstrapTransactionTest();helper.temp=temp;
        Path evidence=Path.of("target/v53-bootstrap-transaction-process/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();int n=0;
        for(String cut:CUTS)for(String mode:List.of("halt","kill")) {
            var plan=helper.fixture("case-"+n,3,false);Path member=Files.createDirectory(evidence.resolve(String.format("case-%03d",n)));
            Files.write(member.resolve("original-plan.gsbp"),plan.bytes());Files.write(member.resolve("original-application.image"),plan.seed.application());
            child(member,"first",cut,mode,false);V53BootstrapTransactionTest.copy(plan,member.resolve("crash"));
            child(member,"second","BOOTSTRAP_RESEAL_0_root.gsr_FORCED",mode,true);V53BootstrapTransactionTest.copy(plan,member.resolve("second-crash"));
            child(member,"resumed","none","none",true);V53BootstrapTransactionTest.verify(plan);V53BootstrapTransactionTest.copy(plan,member.resolve("final"));
            rows.add(Map.of("case",member.getFileName().toString(),"cut",cut,"mode",mode,"plan",plan.digest(),"status","PASS"));n++;
            if(n%4==0)System.out.println("v53BootstrapTransactionProcessProgress="+n+"/"+(CUTS.size()*2));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-transaction-process-v1","status","PASS","cases",rows,"freshProcesses",3*n,"publicBootstrap",false),65536));
        System.out.println("v53BootstrapTransactionProcessEvidence="+evidence.toAbsolutePath());
    }
}
