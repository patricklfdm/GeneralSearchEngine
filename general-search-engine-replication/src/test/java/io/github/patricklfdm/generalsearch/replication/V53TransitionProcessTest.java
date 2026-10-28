package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.Arguments;
import java.util.stream.Stream;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Original retained operation crosses an actual proposer-process death. */
class V53TransitionProcessTest {
    @TempDir Path temp;
    static Stream<Arguments> cuts() {
        var cases=new ArrayList<Arguments>();
        String selected=System.getProperty("v53.transition.process.profile","");
        for(long index:List.of(5L,6L))for(String point:List.of("PUBLICATION_SELECTOR_FORCED","PUBLICATION_BEFORE_RETURN"))
            for(String mode:List.of("halt","kill")) {
                String name=index+"-"+point+"-"+mode;
                if(selected.isEmpty() || selected.equals(name))cases.add(Arguments.of(index,point,mode));
            }
        if(cases.isEmpty())throw new IllegalArgumentException("unknown transition process profile");
        return cases.stream();
    }
    @ParameterizedTest @MethodSource("cuts")
    void sameOperationResumesAfterNativeProposerDeath(long index,String point,String mode)throws Exception {
        var helper=new V53TransitionRoundDriverTest();helper.temp=temp;
        Path raw=Files.createDirectories(Path.of("target/v53-transition-process/run-"+UUID.randomUUID()));
        System.out.println("v53TransitionProcessEvidence="+raw.toAbsolutePath());
        Path history=null;
        Files.write(raw.resolve("profile.json"),canonical(Map.of("index",index,"point",point,"mode",mode),4096));
        try(var network=helper.network("SEALED")) {
            var target=network.f.request.targets().getFirst();history=network.f.raw;
            Files.writeString(raw.resolve("native-history.txt"),history.toAbsolutePath()+"\n");
            network.endpoints.getFirst().close();network.transports.getFirst().close();network.owners.getFirst().close();
            network.f.snapshot("before-child");
            Path attempt=Files.createDirectory(raw.resolve("interrupted-worker"));
            var child=process(target,attempt,mode,index,point,temp.resolve("child-"+UUID.randomUUID()));
            try {
                await(child,attempt,"CUT ",network);
                assertFalse(Files.exists(attempt.resolve("ready.json")),"interrupted transition admitted service");
                if(mode.equals("kill")) {
                    var locked=assertThrows(ReplicationException.class,()->{
                        try(var unexpected=network.f.open(target,"live-proposer-lock")){fail("live proposer lost its lock");}
                    });
                    assertEquals(ReplicationException.Reason.STORAGE_FAILURE,locked.reason());
                    assertEquals("offline authority is owned by another process",locked.getMessage());
                    child.destroyForcibly();
                }
                assertTrue(child.waitFor(15,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue(),Files.readString(attempt.resolve("stderr")));
                network.f.snapshot("interrupted");
                Path recovered=Files.createDirectory(raw.resolve("resumed-worker"));
                var resumed=process(target,recovered,"resume",index,"none",temp.resolve("child-"+UUID.randomUUID()));
                try {
                    await(resumed,recovered,"READY resume",network);
                    resumed.getOutputStream().write('s');resumed.getOutputStream().flush();
                    assertTrue(resumed.waitFor(30,TimeUnit.SECONDS));assertEquals(0,resumed.exitValue(),Files.readString(recovered.resolve("stderr")));
                    assertTrue(Files.readString(recovered.resolve("stdout")).contains("CLOSED resume"));
                    network.f.snapshot("after-resume");
                    var inspectResources=new MembershipResources(512*MembershipResources.MIB);
                    try(var actual=MembershipGrantJournal.openRetainingFuturePeers(target.replicaDirectory(),target.materialization().directory(),
                            network.f.result.root(),target.identity(),inspectResources,MembershipGrantJournal.MAXIMUM,event->{})) {
                        var context=actual.activationContext();assertEquals(7L,context.cut.get("index"));assertNull(context.catalog.get("active"));
                        assertEquals("COMPLETED",object(list(context.catalog.get("results")).getLast()).get("phase"));
                    }
                    assertEquals(0,inspectResources.usage().leases());
                    Files.write(raw.resolve("process.json"),canonical(Map.of("parentPid",ProcessHandle.current().pid(),"childPid",child.pid(),"resumePid",resumed.pid(),
                            "mode",mode,"index",index,"point",point,"exit",(long)child.exitValue(),"resumeExit",(long)resumed.exitValue(),"publicReady",false,"liveLockRefused",mode.equals("kill")),16384));
                }finally {stop(resumed);}
            }finally {stop(child);}
        }finally {
            if(history!=null)V53JournalApplicationTest.copy(history,raw.resolve("history"));
        }
    }
    static void stop(Process process)throws Exception {
        if(process.isAlive()){process.destroyForcibly();assertTrue(process.waitFor(15,TimeUnit.SECONDS));}
    }
    static void await(Process child,Path evidence,String marker,V53NativeDispatchTest.Network network)throws Exception {
        Path out=evidence.resolve("stdout"),err=evidence.resolve("stderr");long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(700);
        var recorded=new HashSet<String>();
        while(child.isAlive() && !Files.readString(out).contains(marker) && System.nanoTime()<deadline) {
            for(String line:Files.readString(out).split("\n"))if(line.startsWith("SNAPSHOT ")) {
                String stage=line.substring("SNAPSHOT ".length());
                if(recorded.add(stage)) {
                    assertTrue(stage.matches("(halt|kill|resume)-(installed|applied|published)-[1-7]"),"unsafe snapshot stage");
                    network.f.snapshot(stage);child.getOutputStream().write('c');child.getOutputStream().flush();
                }
            }
            Thread.sleep(20);
        }
        String text=Files.readString(out);
        assertTrue(text.contains(marker),Files.readString(err)+"\n"+text.substring(Math.max(0,text.length()-6000)));
    }
    static Process process(MembershipBootstrapTarget<?,?> target,Path evidence,String mode,long index,String point,Path scratch)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53TransitionProcessWorker.class.getName(),target.replicaDirectory().toString(),target.materialization().directory().toString(),
                evidence.toAbsolutePath().toString(),mode,Long.toString(index),point,scratch.toString())
                .redirectOutput(evidence.resolve("stdout").toFile()).redirectError(evidence.resolve("stderr").toFile()).start();
    }
}
