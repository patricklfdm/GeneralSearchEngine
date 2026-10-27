package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53PublicationRestartProcessTest {
    @TempDir Path temp;
    static final List<String> POINTS=List.of("PUBLICATION_SELECTOR_FORCED","FUTURE_RETENTION_PROMOTED","PUBLICATION_BEFORE_RETURN","PUBLICATION_ACK_BEFORE_RETURN");
    @Test void originalPublicationSurvivesProcessLossBeforeAcknowledgement()throws Exception {
        for(String mode:List.of("halt","kill"))for(String point:POINTS) {
            var helper=new V53RemotePublicationTest();helper.temp=temp;
            try(var network=helper.new Network(3)) {
                var group=network.group;var f=group.fixture;var target=f.request.targets().getLast();
                network.endpoints.getLast().close();network.transports.getLast().close();group.owners.getLast().close();
                // The live recording majority must include the receiver; node 2 stays offline.
                network.transports.get(1).close();f.snapshot("crash-ready");
                Path log=f.raw.resolve("worker.log"),resumeLog=f.raw.resolve("resume.log");
                var child=process(target,mode,point,temp.resolve("unused-"+UUID.randomUUID()),log);
                try {
                    await(child,log,"READY "+mode);
                    try(var quorum=network.quorum();var executor=Executors.newSingleThreadExecutor()) {
                        var recorded=quorum.record();assertEquals(Set.of("node-1","node-3"),recorded.voters());
                        group.timeline.add(Map.of("node","node-1","event","FUTURE_QUORUM_COMPLETE","voters",List.of("node-1","node-3")));
                        var dispatch=executor.submit(()->recorded.dispatch(network.transports.getFirst()));
                        await(child,log,"CUT "+point);
                        if(mode.equals("kill")){assertThrows(Exception.class,()->f.open(target,"lock-probe"));child.destroyForcibly();}
                        assertTrue(child.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,child.exitValue());
                        var failure=assertThrows(ExecutionException.class,()->dispatch.get(30,TimeUnit.SECONDS));
                        assertEquals(MembershipTransport.Reason.IO,assertInstanceOf(MembershipTransport.Failure.class,failure.getCause()).reason);
                        assertTrue(group.owners.getFirst().futureRetentionState().pending());
                        V53JournalApplicationTest.copy(target.replicaDirectory(),f.raw.resolve("interrupted"));
                        var requests=Files.readAllLines(log).stream().filter(v->v.startsWith("REQUEST "))
                                .map(v->MembershipWire.decode(Base64.getDecoder().decode(v.substring(8)),FRAME)).filter(v->v.kind().equals("PUBLISH")).toList();
                        assertFalse(requests.isEmpty());assertEquals(1,requests.stream().map(Decoded::digest).distinct().count());
                        var request=requests.getFirst();Files.write(f.raw.resolve("publication-request.gsrp"),request.bytes());
                        for(String line:Files.readAllLines(log))if(line.startsWith("WIRE ")) {
                            var row=object(parse(line.substring(5).getBytes(java.nio.charset.StandardCharsets.UTF_8),1048576));
                            assertNotEquals("PUBLISH_ACK",MembershipWire.decode(Base64.getDecoder().decode((String)row.get("response")),FRAME).kind());
                        }
                        var resume=process(target,"resume","none",temp.resolve("resume-"+UUID.randomUUID()),resumeLog);
                        try {
                            await(resume,resumeLog,"READY resume");var stable=V53ReplayFilesTest.files(target.replicaDirectory());Decoded ack=null;
                            for(int n=0;n<2;n++) {
                                var response=network.transports.getFirst().exchange(target.identity(),request,"PUBLISH_ACK",System.nanoTime()+V53RemotePublicationTest.BUDGET).get(120,TimeUnit.SECONDS);
                                if(ack!=null)assertArrayEquals(ack.bytes(),response.bytes());ack=response;
                            }
                            assertEquals(stable,V53ReplayFilesTest.files(target.replicaDirectory()));
                            Files.write(f.raw.resolve("publication-ack.gsrp"),ack.bytes());
                            resume.getOutputStream().write('s');resume.getOutputStream().flush();
                            assertTrue(resume.waitFor(30,TimeUnit.SECONDS));assertEquals(0,resume.exitValue(),Files.readString(resumeLog));
                        }finally {if(resume.isAlive()){resume.destroyForcibly();resume.waitFor(10,TimeUnit.SECONDS);}}
                        V53JournalApplicationTest.copy(target.replicaDirectory(),f.raw.resolve("recovered"));
                        Files.write(f.raw.resolve("restart-result.json"),canonical(Map.of("status","PASS","mode",mode,"cut",point,
                                "exit",(long)child.exitValue(),"resumeExit",0L,"duplicateReceipts",2L,"originalDispatch","IO_FAILED"),16384));
                        System.out.println("v53PublicationRestart="+mode+":"+point+" PASS");
                    }
                }finally {if(child.isAlive()){child.destroyForcibly();child.waitFor(10,TimeUnit.SECONDS);}}
            }
        }
    }
    private static void await(Process child,Path log,String marker)throws Exception {
        long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(90);
        while(child.isAlive() && !Files.readString(log).contains(marker) && System.nanoTime()<deadline)Thread.sleep(10);
        assertTrue(Files.readString(log).contains(marker),Files.readString(log));
    }
    private static Process process(MembershipBootstrapTarget<?,?> target,String mode,String point,Path scratch,Path log)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                V53PublicationRestartWorker.class.getName(),target.replicaDirectory().toString(),target.materialization().directory().toString(),mode,point,scratch.toString())
                .redirectErrorStream(true).redirectOutput(log.toFile()).start();
    }
}
