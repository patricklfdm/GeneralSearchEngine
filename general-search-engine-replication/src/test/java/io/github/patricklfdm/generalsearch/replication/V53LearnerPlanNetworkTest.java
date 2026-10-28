package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipLearnerAdmissionFiles.*;

/** Actual native acquisition followed by plan force and fresh-JVM interruption.
 * Planning is deliberately distinct from learner store/image/INTENT admission. */
class V53LearnerPlanNetworkTest {
    @TempDir Path temp;
    @Test void nativeOriginalPlanAndEveryProcessCutPreserveNonvotingIdentity()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-learner-plan/run-"+UUID.randomUUID()));
        System.out.println("v53LearnerPlanEvidence="+raw.toAbsolutePath());
        var helper=new V53LearnerSourceNetworkTest();helper.temp=temp;
        var history=new AtomicReference<Path>();var cases=new ArrayList<Map<String,Object>>();
        try {
            helper.exercise((source,request,nativeRaw)->{
                history.set(nativeRaw);var original=source.source();
                var summary=source.plan(event->{});
                assertEquals(request,summary.request());assertFalse(Files.exists(request.replicaDirectory()));
                V53JournalApplicationTest.copy(request.operationDirectory(),raw.resolve("native-plan"));
                var freshResources=new MembershipResources(512*MembershipResources.MIB);
                try(var reopened=MembershipLearnerAdmissionFiles.open(summary,freshResources,event->{})) {
                    assertEquals(summary,reopened.summary());reopened.retained().checkOriginal(original);
                }
                assertEquals(0,freshResources.usage().leases());
                // Capture every original plan while the real acquired source is live.
                // Run process persistence later, outside that original network deadline.
                for(String point:V53LearnerAdmissionPlanTest.CUTS)for(String mode:List.of("halt","kill")) {
                    Path evidence=Files.createDirectory(raw.resolve(point+"-"+mode));
                    Path parent=Files.createDirectory(temp.resolve("plan-process-"+UUID.randomUUID()));
                    var perCase=new MembershipLearnerRequest(request.root(),request.identity(),request.change(),parent.resolve("replica"),parent.resolve("operation"));
                    var plan=MembershipLearnerAdmissionPlan.create(perCase,original);plan.checkOriginal(source.source());
                    Files.write(evidence.resolve("original.gslp"),plan.bytes());
                }
            });
            for(int index=0;index<V53LearnerAdmissionPlanTest.CUTS.size();index++)for(String mode:List.of("halt","kill")) {
                String point=V53LearnerAdmissionPlanTest.CUTS.get(index);Path evidence=raw.resolve(point+"-"+mode);
                var plan=MembershipLearnerAdmissionPlan.decode(Files.readAllBytes(evidence.resolve("original.gslp")));
                var child=start(evidence,"create",mode,point,"interrupted");boolean locked=false;
                try {
                    long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
                    while(child.isAlive() && !Files.readString(evidence.resolve("interrupted.stdout")).contains("CUT "+point) && System.nanoTime()<deadline)Thread.sleep(20);
                    assertTrue(Files.readString(evidence.resolve("interrupted.stdout")).contains("CUT "+point),Files.readString(evidence.resolve("interrupted.stderr")));
                    if(mode.equals("kill")) {
                        if(index>0){assertThrows(ReplicationException.class,()->MembershipOwnership.own(plan.request.operationDirectory().resolve(LOCK),false));locked=true;}
                        child.destroyForcibly();
                    }
                    assertTrue(child.waitFor(15,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                    V53JournalApplicationTest.copy(plan.request.operationDirectory(),evidence.resolve("interrupted"));
                    var resumed=start(evidence,"resume","normal","none","resumed");
                    try {
                        assertTrue(resumed.waitFor(30,TimeUnit.SECONDS));
                        boolean success=index>=4;assertEquals(success,resumed.exitValue()==0,Files.readString(evidence.resolve("resumed.stderr")));
                        assertFalse(Files.exists(plan.request.replicaDirectory()));
                        V53JournalApplicationTest.copy(plan.request.operationDirectory(),evidence.resolve("resumed"));
                        if(success)assertArrayEquals(plan.bytes(),Files.readAllBytes(plan.request.operationDirectory().resolve(FILE)));
                        else assertEquals(V53ReplayFilesTest.files(evidence.resolve("interrupted")),V53ReplayFilesTest.files(evidence.resolve("resumed")));
                        cases.add(Map.of("point",point,"mode",mode,"pid",child.pid(),"resumePid",resumed.pid(),"exit",(long)child.exitValue(),
                                "resumeExit",(long)resumed.exitValue(),"resumed",success,"lockRefused",locked,"replicaExists",false));
                    }finally {V53TransitionProcessTest.stop(resumed);}
                }finally {V53TransitionProcessTest.stop(child);}
            }
            Files.write(raw.resolve("cases.json"),canonical(cases,65536));
        }finally {if(history.get()!=null)V53JournalApplicationTest.copy(history.get(),raw.resolve("source-history"));}
    }
    private static Process start(Path evidence,String action,String mode,String point,String log)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53LearnerPlanWorker.class.getName(),evidence.resolve("original.gslp").toAbsolutePath().toString(),action,mode,point)
                .redirectOutput(evidence.resolve(log+".stdout").toFile()).redirectError(evidence.resolve(log+".stderr").toFile()).start();
    }
}
