package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Physical component qualification. Actual exclusive file owner; protocol transitions remain supplied fixtures. */
final class V53PendingContextFilesProcess {
    static final List<String> WRITE_CUTS=List.of("CONTEXT_CANDIDATE_CREATED","CONTEXT_PREFIX_WRITTEN","CONTEXT_CANDIDATE_WRITTEN",
            "CONTEXT_CANDIDATE_FORCED","CONTEXT_CANDIDATE_PARENT_FORCED","CONTEXT_RENAMED","CONTEXT_PARENT_FORCED");
    static final List<String> REPLAY_CUTS=List.of("CONTEXT_ACTIVE_FORCED","CONTEXT_ACTIVE_PARENT_FORCED");
    static void qualify(Path evidence,byte[] rootRecord,byte[] first,byte[] replacement)throws Exception {
        Files.createDirectories(evidence);Files.write(evidence.resolve("root.gsr"),rootRecord);
        Files.write(evidence.resolve("first.gspc"),first);Files.write(evidence.resolve("replacement.gspc"),replacement);
        assertFalse(Arrays.equals(first,replacement));var cases=new ArrayList<Map<String,Object>>();
        try {
            for(String transition:List.of("create","replace","replay"))for(String mode:List.of("halt","kill"))
                    for(String point:transition.equals("replay")?REPLAY_CUTS:WRITE_CUTS) {
                String name=transition+"-"+mode+"-"+point;Path path=evidence.resolve(name);Files.createDirectory(path);
                Path store=path.resolve("store"),inputs=path.resolve("inputs");Files.createDirectory(store);Files.createDirectory(inputs);
                Files.write(store.resolve("owner.lock"),new byte[0]);Files.write(inputs.resolve("root.gsr"),rootRecord);
                byte[] expected=transition.equals("create")?first:replacement;
                Files.write(inputs.resolve("expected.gspc"),expected);
                if(!transition.equals("create"))Files.write(inputs.resolve("prior.gspc"),first);
                if(!transition.equals("create"))initialise(store,rootRecord,transition.equals("replace")?first:replacement);
                int faultExit=child(path,"fault",point,mode);snapshot(path,"crash");
                String again=Files.exists(store.resolve(MembershipPendingContextFiles.FILE))
                        && Arrays.equals(Files.readAllBytes(store.resolve(MembershipPendingContextFiles.FILE)),expected)
                        ?"CONTEXT_ACTIVE_FORCED":"CONTEXT_PREFIX_WRITTEN";
                int recoveryExit=child(path,"recovery-fault",again,"halt");snapshot(path,"recovery-crash");
                int resumeExit=child(path,"resume","none","none");snapshot(path,"final");
                assertArrayEquals(expected,Files.readAllBytes(store.resolve(MembershipPendingContextFiles.FILE)));
                assertFalse(Files.exists(store.resolve(MembershipPendingContextFiles.NEXT)));
                cases.add(Map.of("case",name,"transition",transition,"mode",mode,"cut",point,"recoveryCut",again,"status","PASS","exitCodes",Map.of("fault",faultExit,"recoveryFault",recoveryExit,"resume",resumeExit)));
            }
            assertEquals(32,cases.size());
        }finally {
            Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-pending-context-process-v1",
                    "status",cases.size()==32?"PASS":"FAIL","cases",cases,"expectedCases",32,"freshProcesses",cases.size()*3,
                    "protocolAuthority","conditional-fixture","ownerIntegration",false,"powerLoss",false),65536));
            System.out.println("v53PendingContextProcessEvidence="+evidence.toAbsolutePath());
        }
    }
    static void initialise(Path path,byte[] rootBytes,byte[] context)throws Exception {
        var record=decode(rootBytes,"records","ROOT");
        var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)record.value().get("groupId"))),
                UUID.fromString((String)record.value().get("historyId")),record.rootDigest());
        var identity=MembershipContext.identity(object(list(record.value().get("initial")).getFirst()));
        var resources=new MembershipResources(512*MembershipResources.MIB);Path lock=path.resolve("owner.lock");Object key=MembershipBasisSources.key(lock);
        try(var owner=AdmissionPaths.own(lock,false);
                var journal=resources.reserve(MembershipResources.Unit.JOURNAL,"context-process-parent",MembershipResources.Unit.JOURNAL.bytes);
                var files=new MembershipPendingContextFiles(path,root,identity,resources,2L*MembershipPendingContext.MAXIMUM)) {
            files.install(MembershipPendingContext.decode(context),null,()->{
                if(!owner.lock().isValid() || !key.equals(MembershipBasisSources.key(lock)))throw new java.io.IOException("lost process parent owner");
            },event->{});
        }
        assertEquals(0,resources.usage().leases());
    }
    static void snapshot(Path path,String stage)throws Exception {
        Path target=path.resolve(stage);Files.createDirectory(target);
        for(String name:List.of(MembershipPendingContextFiles.FILE,MembershipPendingContextFiles.NEXT))
            if(Files.exists(path.resolve("store").resolve(name)))Files.copy(path.resolve("store").resolve(name),target.resolve(name));
    }
    static int child(Path path,String label,String point,String mode)throws Exception {
        Path stdout=path.resolve(label+".stdout"),stderr=path.resolve(label+".stderr");
        var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53PendingContextFilesWorker.class.getName(),path.resolve("store").toAbsolutePath().toString(),path.resolve("inputs").toAbsolutePath().toString(),point,mode)
                .redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",point),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";
                long deadline=System.nanoTime()+30_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {
                    assertTrue(process.isAlive(),"worker ended before kill marker: "+stderr);assertTrue(System.nanoTime()<deadline,"context kill marker timeout");Thread.sleep(20);
                }
                process.destroyForcibly();
            }
            assertTrue(process.waitFor(30,java.util.concurrent.TimeUnit.SECONDS),"context child timeout");
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,process.exitValue(),Files.readString(stderr));assertEquals("",Files.readString(stderr));
            assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));
            return process.exitValue();
        }finally {if(process.isAlive())process.destroyForcibly();process.waitFor();}
    }
    private V53PendingContextFilesProcess() {}
}
