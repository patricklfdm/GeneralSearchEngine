package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53NativeVotingProcessTest {
    @TempDir Path temp;
    static final List<String> POINTS=List.of("ACCEPT_CANDIDATE_FORCED","ACCEPT_ACK_BEFORE_RETURN","PROOF_CANDIDATE_FORCED","PROOF_ACK_BEFORE_RETURN");
    @Test void forcedVotesRecoverAfterHaltAndSigkillWithoutFreshRemoteObservations()throws Exception {
        for(String mode:List.of("halt","kill"))for(String point:POINTS) {
            var helper=new V53NativeVotingTest();helper.temp=temp;
            try(var network=helper.new Network(3,false)) {
                var f=network.f;boolean proof=point.startsWith("PROOF");Decoded record=network.accept;
                if(proof){for(int i=1;i<3;i++)network.send(i,network.request(i,network.accept));record=network.proof();Files.write(f.raw.resolve("proof.gsr"),record.bytes());}
                var target=f.request.targets().getLast();var request=network.request(2,record);Files.write(f.raw.resolve("vote-request.gsrp"),request.bytes());
                network.endpoints.getLast().close();network.transports.getLast().close();network.owners.getLast().close();f.snapshot("crash-ready");
                Path log=f.raw.resolve("worker.log"),resumeLog=f.raw.resolve("resume.log");var child=process(target,mode,point,log);
                try{await(child,log,"READY "+mode);
                    try(var executor=Executors.newSingleThreadExecutor()) {
                        var dispatch=executor.submit(()->network.send(2,request));await(child,log,"CUT "+point);
                        if(mode.equals("kill")){assertThrows(Exception.class,()->f.open(target,"lock-probe"));child.destroyForcibly();}
                        assertTrue(child.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                        assertThrows(ExecutionException.class,()->dispatch.get(30,TimeUnit.SECONDS));
                        V53JournalApplicationTest.copy(target.replicaDirectory(),f.raw.resolve("interrupted"));
                        var resumed=process(target,"resume","none",resumeLog);
                        try{await(resumed,resumeLog,"READY resume");var stable=V53ReplayFilesTest.files(target.replicaDirectory());
                            var first=network.send(2,request);assertArrayEquals(first.bytes(),network.send(2,request).bytes());
                            assertEquals(stable,V53ReplayFilesTest.files(target.replicaDirectory()));Files.write(f.raw.resolve("vote-ack.gsrp"),first.bytes());
                            resumed.getOutputStream().write('s');resumed.getOutputStream().flush();assertTrue(resumed.waitFor(30,TimeUnit.SECONDS));assertEquals(0,resumed.exitValue(),Files.readString(resumeLog));
                        }finally{if(resumed.isAlive()){resumed.destroyForcibly();resumed.waitFor(10,TimeUnit.SECONDS);}}
                        V53JournalApplicationTest.copy(target.replicaDirectory(),f.raw.resolve("recovered"));
                        Files.write(f.raw.resolve("restart-result.json"),canonical(Map.of("status","PASS","mode",mode,"cut",point,"exit",child.exitValue(),"resumeExit",0,
                                "duplicateReceipts",2,"originalDispatch","FAILED","freshRemoteObservations",0),16384));
                        System.out.println("v53NativeVotingRestart="+mode+":"+point+" PASS");
                    }
                }finally{if(child.isAlive()){child.destroyForcibly();child.waitFor(10,TimeUnit.SECONDS);}}
            }
        }
    }
    private static void await(Process child,Path log,String marker)throws Exception {
        long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(90);
        while(child.isAlive() && !Files.readString(log).contains(marker) && System.nanoTime()<deadline)Thread.sleep(10);
        assertTrue(Files.readString(log).contains(marker),Files.readString(log));
    }
    private static Process process(MembershipBootstrapTarget<?,?> target,String mode,String point,Path log)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),V53NativeVotingWorker.class.getName(),
                target.replicaDirectory().toString(),target.materialization().directory().toString(),mode,point).redirectErrorStream(true).redirectOutput(log.toFile()).start();
    }
}
