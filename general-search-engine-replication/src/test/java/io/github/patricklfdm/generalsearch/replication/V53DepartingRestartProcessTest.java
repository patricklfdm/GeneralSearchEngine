package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53DepartingRestartProcessTest {
    @TempDir Path temp;
    @ParameterizedTest @ValueSource(strings={"proposer","follower"})
    void originalNativeDepartureRemainsNonvotingInFreshProcess(String profile)throws Exception {
        var ref=new AtomicReference<V53NativeDispatchTest.Network>();
        var helper=new V53TransitionRoundDriverTest() {
            @Override V53NativeDispatchTest.Network network(String phase)throws Exception {
                var made=super.network(phase);ref.set(made);return made;
            }
        };
        helper.temp=temp;
        if(profile.equals("proposer"))helper.removedProposerCannotServeTheNewConfiguration();
        else helper.removedSelectedFollowerCompletesFinalWithoutSuccessorAck();
        var network=ref.get();var target=network.f.request.targets().get(3);
        Path raw=Files.createDirectories(Path.of("target/v53-departure-restart/run-"+UUID.randomUUID()));
        System.out.println("v53DepartingRestartEvidence="+raw.toAbsolutePath());
        Files.writeString(raw.resolve("profile.txt"),profile+"\n");
        Files.writeString(raw.resolve("native-history.txt"),network.f.raw.toAbsolutePath()+"\n");
        V53JournalApplicationTest.copy(network.f.raw,raw.resolve("history"));
        Decoded request,reply;
        if(profile.equals("follower")) {
            var row=network.wire.stream().filter(v->{var response=MembershipWire.decode(Base64.getDecoder().decode((String)v.get("response")),FRAME);
                return response.kind().equals("PUBLISH_ACK") && object(response.value().get("sender")).get("node").equals("node-4");}).findFirst().orElseThrow();
            request=MembershipWire.decode(Base64.getDecoder().decode((String)row.get("request")),FRAME);
            reply=MembershipWire.decode(Base64.getDecoder().decode((String)row.get("response")),FRAME);
        } else {
            var row=network.events.stream().filter(v->v.get("event").equals("ROUND_SLOT_COMPLETE")).findFirst().orElseThrow();
            reply=MembershipWire.decode(Base64.getDecoder().decode((String)row.get("bytes")),FRAME);
            // The proposer completed a local call, not a TCP request to itself.
            // Reconstruct its exact envelope from the retained original reply.
            var values=new TreeMap<>(reply.value());values.put("sender",reply.value().get("recipient"));values.put("recipient",reply.value().get("sender"));
            values.put("payload",Map.of("certificate",object(reply.value().get("payload")).get("certificate")));
            request=decode(encode("wire","PUBLISH",values),"wire","PUBLISH");
        }
        Files.write(raw.resolve("publication-request.gsrp"),request.bytes());Files.write(raw.resolve("publication-ack.gsrp"),reply.bytes());
        var before=V53ReplayFilesTest.files(target.replicaDirectory());
        for(String mode:List.of("halt","kill"))for(int attempt=1;attempt<=2;attempt++) {
            Path interrupted=Files.createDirectories(raw.resolve("interruptions/"+mode+"-"+attempt));
            Path out=interrupted.resolve("worker.stdout"),err=interrupted.resolve("worker.stderr");
            var crashed=process(target,raw,temp.resolve("interrupted-"+mode+"-"+attempt),out,err,mode);
            try {
                long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(90);
                while(crashed.isAlive() && !Files.readString(out).contains("CUT PUBLICATION_ACK_BEFORE_RETURN") && System.nanoTime()<deadline)Thread.sleep(10);
                assertEquals("CUT PUBLICATION_ACK_BEFORE_RETURN\n",Files.readString(out),Files.readString(err));
                boolean lockChecked=false;
                if(mode.equals("kill")) {
                    var refusal=assertThrows(ReplicationException.class,()->{
                        try(var unexpected=network.f.open(target,"departure-lock-probe")){fail("live child lost its storage lock");}
                    });
                    assertEquals(ReplicationException.Reason.STORAGE_FAILURE,refusal.reason());
                    assertEquals("offline authority is owned by another process",refusal.getMessage());lockChecked=true;
                    crashed.destroyForcibly();
                }
                assertTrue(crashed.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,crashed.exitValue(),Files.readString(err));
                assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
                assertFalse(Files.exists(raw.resolve("duplicate-1.gsrp")),"interrupted call returned an acknowledgement");
                V53JournalApplicationTest.copy(target.replicaDirectory(),interrupted.resolve("store"));
                Files.write(interrupted.resolve("process.json"),canonical(Map.of("parentPid",ProcessHandle.current().pid(),"workerPid",crashed.pid(),
                        "exit",(long)crashed.exitValue(),"mode",mode,"attempt",(long)attempt,"liveLockRefused",lockChecked),4096));
            }finally {if(crashed.isAlive()){crashed.destroyForcibly();assertTrue(crashed.waitFor(10,TimeUnit.SECONDS));}}
        }
        Path stdout=raw.resolve("worker.stdout"),stderr=raw.resolve("worker.stderr");
        var child=process(target,raw,temp.resolve("restart-"+profile),stdout,stderr,"resume");
        try {
            assertTrue(child.waitFor(180,TimeUnit.SECONDS),"departure worker deadline: "+Files.readString(stderr));
            assertEquals(0,child.exitValue(),Files.readString(stderr));assertTrue(Files.readString(stdout).contains("v53DepartingRestart=PASS"));
            assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
            V53JournalApplicationTest.copy(target.replicaDirectory(),raw.resolve("reopened"));
            Files.write(raw.resolve("process.json"),canonical(Map.of("parentPid",ProcessHandle.current().pid(),"workerPid",child.pid(),
                    "exit",(long)child.exitValue(),"profile",profile,"publicationRequestOrigin",profile.equals("proposer")?"original-local-reply-envelope":"original-tcp-request"),4096));
        }finally {if(child.isAlive()){child.destroyForcibly();assertTrue(child.waitFor(10,TimeUnit.SECONDS));}}
    }
    static Process process(MembershipBootstrapTarget<?,?> target,Path evidence,Path scratch,Path stdout,Path stderr,String mode)throws Exception {
        return new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53DepartingRestartWorker.class.getName(),target.replicaDirectory().toString(),target.materialization().directory().toString(),
                evidence.toAbsolutePath().toString(),scratch.toString(),mode).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
    }
}
