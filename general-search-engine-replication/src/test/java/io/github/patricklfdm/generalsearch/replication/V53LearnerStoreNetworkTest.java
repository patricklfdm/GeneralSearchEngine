package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipLearnerAdmissionFiles.*;

/** Native TCP acquisition into retained originals; fresh JVMs resume the actual
 * transaction through force/move/install cuts. No copied fixture is admitted. */
class V53LearnerStoreNetworkTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("LEARNER_RETENTION_RENAMED","LEARNER_ROOT_PREFIX_WRITTEN","LEARNER_NODE_PREFIX_WRITTEN",
            "LEARNER_SOURCE_MOVED","LEARNER_ADMISSION_PREFIX_WRITTEN","LEARNER_STORE_BEFORE_RETURN");
    static List<String> cases(String selected) {
        var all=CUTS.stream().flatMap(point->List.of("halt","kill").stream().map(mode->point+"-"+mode)).toList();
        if(selected==null)return all;
        if(!all.contains(selected))throw new IllegalArgumentException("unknown learner store process case");
        return List.of(selected);
    }
    @Test void originalNativeStoreSurvivesHaltAndKillAtPromotionBoundaries()throws Exception {
        var selected=cases(System.getProperty("gse.v53.learnerStoreCase"));
        Path raw=Files.createDirectories(Path.of("target/v53-learner-store/run-"+UUID.randomUUID()));
        System.out.println("v53LearnerStoreEvidence="+raw.toAbsolutePath());var cases=new ArrayList<Map<String,Object>>();
        for(String point:CUTS)for(String mode:List.of("halt","kill")) {
            if(!selected.contains(point+"-"+mode))continue;
            Path evidence=Files.createDirectory(raw.resolve(point+"-"+mode));var helper=new V53LearnerSourceNetworkTest();
            helper.temp=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
            var captured=new AtomicReference<MembershipLearnerAdmissionPlan>();var history=new AtomicReference<Path>();var events=new ArrayList<String>();
            try {
                helper.exercise((source,request,nativeRaw)->{
                    history.set(nativeRaw);var summary=source.plan(events::add);
                    captured.set(MembershipLearnerAdmissionPlan.decode(Files.readAllBytes(request.operationDirectory().resolve(FILE))));
                    var hit=new AtomicBoolean();
                    assertThrows(IOException.class,()->source.admit(summary,e->{events.add(e);if(e.equals("LEARNER_RETENTION_WRITTEN")){hit.set(true);throw new IOException("retain original for fresh-process continuation");}}));
                    assertTrue(hit.get());assertFalse(Files.exists(request.replicaDirectory()));
                },true);
            }finally{if(history.get()!=null)V53JournalApplicationTest.copy(history.get(),evidence.resolve("source-history"));}
            var plan=captured.get();Files.write(evidence.resolve("original.gslp"),plan.bytes());
            Files.write(evidence.resolve("preparation.json"),canonical(events,65536));snapshot(evidence.resolve("before"),plan);
            var child=start(evidence,"interrupted",mode,point);boolean locked=false;
            try {
                long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(45);
                while(child.isAlive() && !Files.readString(evidence.resolve("interrupted.stdout")).contains("CUT "+point) && System.nanoTime()<deadline)Thread.sleep(20);
                assertTrue(Files.readString(evidence.resolve("interrupted.stdout")).contains("CUT "+point),Files.readString(evidence.resolve("interrupted.stderr")));
                if(mode.equals("kill")) {
                    assertThrows(ReplicationException.class,()->MembershipOwnership.own(plan.request.operationDirectory().resolve(LOCK),false));locked=true;
                    child.destroyForcibly();
                }
                assertTrue(child.waitFor(15,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                snapshot(evidence.resolve("interrupted"),plan);
                var resumed=start(evidence,"resumed","normal","none");
                try {
                    assertTrue(resumed.waitFor(45,TimeUnit.SECONDS));assertEquals(0,resumed.exitValue(),Files.readString(evidence.resolve("resumed.stderr")));
                    snapshot(evidence.resolve("resumed"),plan);
                    cases.add(Map.of("point",point,"mode",mode,"pid",child.pid(),"resumePid",resumed.pid(),
                            "exit",(long)child.exitValue(),"resumeExit",(long)resumed.exitValue(),"lockRefused",locked));
                }finally{V53TransitionProcessTest.stop(resumed);}
            }finally{V53TransitionProcessTest.stop(child);}
        }
        Files.write(raw.resolve("cases.json"),canonical(cases,65536));
    }
    static void snapshot(Path out,MembershipLearnerAdmissionPlan plan)throws IOException {
        Files.createDirectory(out);Path operation=plan.request.operationDirectory(),replica=plan.request.replicaDirectory();
        byte[] bytes=Files.readAllBytes(operation.resolve(Files.exists(operation.resolve(RETAIN))?RETAIN:RETAIN_NEXT));
        var decision=MembershipLearnerRetention.decode(bytes,plan);Path source=decision.locate();
        V53JournalApplicationTest.copy(operation,out.resolve("operation"));V53JournalApplicationTest.copy(source,out.resolve("source"));
        if(Files.exists(replica)) {
            Files.createDirectory(out.resolve("replica"));
            try(var paths=Files.list(replica)){for(Path p:paths.toList())if(!p.getFileName().toString().equals("learner"))Files.copy(p,out.resolve("replica").resolve(p.getFileName()));}
        }
        var keys=new ArrayList<Map<String,Object>>();
        for(var row:plan.inventory()){String name=(String)row.get("path");keys.add(Map.of("path",name,"key",MembershipBasisSources.key(source.resolve(name)).toString()));}
        Files.write(out.resolve("identity.json"),canonical(Map.of("location",source.equals(decision.staging)?"staging":"retained",
                "directoryKey",MembershipBasisSources.key(source).toString(),"files",keys),65536));
    }
    private static Process start(Path evidence,String label,String mode,String point)throws IOException {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53LearnerStoreWorker.class.getName(),evidence.resolve("original.gslp").toAbsolutePath().toString(),mode,point)
                .redirectOutput(evidence.resolve(label+".stdout").toFile()).redirectError(evidence.resolve(label+".stderr").toFile()).start();
    }
}
