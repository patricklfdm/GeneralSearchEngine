package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53BootstrapStoreAdmissionTest.*;

class V53BootstrapTypedProcessTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("BOOTSTRAP_TYPED_RECHECKED","BOOTSTRAP_PREPARED_DURABLE","BOOTSTRAP_COMMITTING_DURABLE",
            "BOOTSTRAP_ADMISSION_0_FORCED","BOOTSTRAP_SEAL_0_ACTIVE_PARENT_FORCED","BOOTSTRAP_COMMITTED_BEFORE_RETURN");
    static void child(Path root,String label,String point,String mode,boolean resume)throws Exception {
        Path stdout=root.resolve(label+".stdout"),stderr=root.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53BootstrapTypedWorker.class.getName(),root.toAbsolutePath().toString(),point,mode,Boolean.toString(resume)).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                long end=System.nanoTime()+120_000_000_000L;
                while(!Files.readString(stdout).contains("AWAITING_KILL")){assertTrue(process.isAlive(),Files.readString(stderr));assertTrue(System.nanoTime()<end,"worker cut deadline");Thread.sleep(20);}
                process.destroyForcibly();
            }
            assertTrue(process.waitFor(120,TimeUnit.SECONDS),"worker completion deadline");assertEquals(mode.equals("halt")?83:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
        }finally{if(process.isAlive()){process.destroyForcibly();process.waitFor(10,TimeUnit.SECONDS);}}
    }
    @Test void actualTypedCoordinatorSurvivesRepeatedProcessDeathWithAndWithoutLiveCompletedVoters()throws Exception {
        var helper=new V53BootstrapCoordinatorTest();helper.temp=temp;
        Path evidence=Path.of("target/v53-bootstrap-typed-process/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();int n=0;
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true))for(String cut:CUTS)for(String mode:List.of("halt","kill")) {
            var request=helper.request("case-"+n,size,backup);var reviewed=MembershipBootstrapCoordinator.plan(builder().configuration(),request,e->{});
            var plan=V53BootstrapCoordinatorTest.original(reviewed.operationDirectory(),false);Path member=Files.createDirectory(evidence.resolve(String.format("case-%03d",n)));
            Files.write(member.resolve("original-plan.gsbp"),plan.bytes());Files.write(member.resolve("original-application.image"),plan.seed.application());
            child(member,"first",cut,mode,false);V53BootstrapProgressResumeTest.copy(plan,member.resolve("crash"));
            if(!Set.of("BOOTSTRAP_TYPED_RECHECKED","BOOTSTRAP_PREPARED_DURABLE").contains(cut)) {
                Files.move(MembershipBootstrapCoordinator.projection(plan.operation()),temp.resolve("saved-projection-"+n));
                if(backup)Files.move(request.sourcePath().orElseThrow(),temp.resolve("saved-source-"+n));
            }
            var resources=resources();MembershipGrantJournal live=null;var events=new ArrayList<String>();
            boolean progressed=Files.exists(node(plan,0).resolve(MembershipBootstrapCommitData.SEAL));
            String second=cut.equals("BOOTSTRAP_COMMITTED_BEFORE_RETURN")?"BOOTSTRAP_RECOVERY_JOURNAL_FORCED":"BOOTSTRAP_SEAL_1_CANDIDATE_PREFIX_WRITTEN";
            try {
                if(progressed) {
                    live=open(plan,0,resources,events::add);assertEquals(2,live.reserveCounter());var id=identity(plan,0);
                    live.prepareCurrent(Map.of("counter",2L,"proposer",id.nodeId().value(),"incarnation",id.storageId().toString()));
                    Files.createDirectory(core(plan,0));Files.writeString(core(plan,0).resolve("derived-marker"),"retained");assertEquals(3,live.reserveCounter());
                }
                V53BootstrapProgressResumeTest.copy(plan,member.resolve("before"));var before=progressed?V53BootstrapProgressResumeTest.safeFiles(node(plan,0)):Map.<String,String>of();
                child(member,"second",second,mode,true);V53BootstrapProgressResumeTest.copy(plan,member.resolve("second-crash"));
                if(progressed){assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node(plan,0)));new V53MembershipOwnershipTest().probe(node(plan,0).resolve("replica.lock"));}
                child(member,"resumed","none","none",true);
                assertEquals(new MembershipBootstrapCommitData(plan).result(),MembershipBootstrapCoordinator.readResult(plan.operation()));
                if(progressed) {
                    assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node(plan,0)));new V53MembershipOwnershipTest().probe(node(plan,0).resolve("replica.lock"));assertEquals(4,live.reserveCounter());
                }
            }finally{if(live!=null)live.close();}
            assertEquals(0,resources.usage().leases());V53BootstrapProgressResumeTest.copy(plan,member.resolve("final"));Files.write(member.resolve("store-events.json"),canonical(events,1024*1024));
            rows.add(Map.of("case",member.getFileName().toString(),"size",size,"source",request.source().name(),"cut",cut,"secondCut",second,"mode",mode,"progressed",progressed,"plan",plan.digest(),"status","PASS"));
            n++;if(n%4==0)System.out.println("v53BootstrapTypedProcessProgress="+n+"/72");
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-typed-process-v1","status","PASS","cases",rows,"freshWorkers",3*n,"lockProbeProcesses",48,"freshProcesses",3*n+48,"typedCoordinator",true,"planningInParent",true,"publicRuntime",false),65536));
        System.out.println("v53BootstrapTypedProcessEvidence="+evidence.toAbsolutePath());
    }
}
