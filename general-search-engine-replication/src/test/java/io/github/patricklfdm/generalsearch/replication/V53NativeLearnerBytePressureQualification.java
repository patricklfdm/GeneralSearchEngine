package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** One native READY/CANCEL original, then three same-file cold lifetimes with
 * caller budgets fixed before opening. No synthetic pressure reservations. */
class V53NativeLearnerBytePressureQualification {
    @TempDir Path temp;
    static final List<String> MODES=List.of("pool-full","packet-short","source-exact");
    @Test void actualCancelledLearnerRejectsBytePressureAndCompletesColdRecovery()throws Exception {
        Path root=Files.createDirectories(Path.of("target/v53-native-learner-byte-pressure/run-"+UUID.randomUUID()));
        System.out.println("v53NativeLearnerBytePressureEvidence="+root.toAbsolutePath());
        var original=new V53NativeLearnerResourcesQualification();original.temp=temp;
        original.run(Files.createDirectory(root.resolve("original")));
        Path pressure=Files.createDirectory(root.resolve("pressure"));
        for(String mode:MODES) {
            runMode(Files.createDirectory(pressure.resolve(mode)),root.resolve("original/original"),original.fixture,mode);
            System.out.println("v53NativeLearnerBytePressureMode="+mode+" PASS");
        }
    }
    static long sumImages(Map<String,byte[]> files) {return files.entrySet().stream().filter(v->v.getKey().endsWith(".image")).mapToLong(v->v.getValue().length).sum();}
    static long steady(Map<String,byte[]> prepared,Map<String,byte[]> terminal) {
        return 64*MembershipResources.MIB+sumImages(prepared)+terminal.values().stream().mapToLong(v->v.length).sum();
    }
    static long limit(String mode,long steady,long packet,long images) {
        return switch(mode) {
            case "pool-full"->steady;
            case "packet-short"->Math.addExact(steady,packet-1);
            case "source-exact"->Math.addExact(steady,Math.addExact(packet,images));
            default->throw new IllegalArgumentException("exact byte pressure mode");
        };
    }
    static Map<String,byte[]> files(Path dir)throws Exception {
        var files=new TreeMap<String,byte[]>();
        try(var paths=Files.list(dir)){for(Path path:paths.sorted().toList())files.put(path.getFileName().toString(),AdmissionPaths.read(path,MembershipApplicationImage.MAXIMUM));}
        return files;
    }
    void runMode(Path root,Path original,V53LearnerCancellationQualification fixture,String mode)throws Exception {
        var plan=fixture.retainedPlan;var config=fixture.retainedConfig;
        var prepared=files(original.resolve("learner-source-copy"));
        Path terminalPath=MembershipLearnerCancellation.directory(plan).resolve(MembershipLearnerCancellation.SOURCE);
        var terminal=files(terminalPath);var packet=MembershipSourcePacket.decode(terminal.get("source.gscp"));
        long steady=steady(prepared,terminal),limit=limit(mode,steady,packet.bytes().length,sumImages(terminal));
        var capture=new V53LearnerResourceCapture(root.resolve("resources"),limit);var resources=capture.resources;
        var events=new ArrayList<String>();var proof=new ArrayList<Map<String,Object>>();boolean success=false;
        MembershipBallotAllocator.Cut callback=point->{
            events.add(point);capture.mark("CALLBACK","resume",point);
            if(point.equals("LEARNER_CANCEL_BEFORE_RETURN")) {
                try {
                    assertTrue(proof.isEmpty());assertEquals(steady,resources.usage().staging());
                    V53LearnerCancellationQualification.snapshot(root.resolve("before-probe"),plan,resources);capture.mark("PROBE_BEGIN",mode,point);
                    proof.add(probe(root,mode,plan,packet,terminal,capture));
                    capture.mark("PROBE_RETURN",mode,point);V53LearnerCancellationQualification.snapshot(root.resolve("after-probe"),plan,resources);
                }catch(Exception error){throw new java.io.IOException("learner byte pressure probe",error);}
            }
        };
        try {
            try(var store=V53LearnerResourceCapture.own(capture,"resume-store",MembershipLearnerStore.resume(plan,resources,callback));
                    var typed=V53LearnerResourceCapture.own(capture,"resume-typed",MembershipLearnerMaterialization.prepare(
                            MembershipLearnerPreparation.from(store.value,1),builder().configuration(),config,callback))) {
                var head=typed.value.retainGeneration();
                try(var cancelled=V53LearnerResourceCapture.own(capture,"resume-cancel",MembershipLearnerCancellation.resume(head,callback))) {
                    assertEquals("CANCELLED",cancelled.value.result().get("phase"));assertEquals(1,proof.size());
                    assertArrayEquals(Files.readAllBytes(original.resolve("learner-receipt.gsr")),typed.value.receipt().bytes());
                    assertThrows(IllegalArgumentException.class,store.value::requireActive);
                    V53LearnerCancellationQualification.snapshot(root.resolve("returned"),plan,resources);capture.mark("SNAPSHOT","returned","");
                }
            }
            assertEquals(0,resources.usage().leases());assertFalse(Files.exists(config.materialization().directory()));
            V53LearnerCancellationQualification.snapshot(root.resolve("closed"),plan,resources);capture.mark("SNAPSHOT","closed","");success=true;
        }finally {
            capture.finish(original,success);
            Files.write(root.resolve("events.json"),canonical(events,65536),StandardOpenOption.CREATE_NEW);
            Files.write(root.resolve("probe.json"),V53CurrentHeadNetworkTest.evidenceJson(proof,65536),StandardOpenOption.CREATE_NEW);
            Files.write(root.resolve("result.json"),canonical(Map.of("status",success?"PARTIAL":"FAIL","mode",mode,
                "steadyStagingBytes",steady,"stagingLimit",limit,"packetBytes",packet.bytes().length,"imageBytes",sumImages(terminal),
                "sameOriginalColdRecovery",true,"wholeRuntimeResourcesQualified",false,"phase3Complete",false),65536),StandardOpenOption.CREATE_NEW);
        }
    }
    Map<String,Object> probe(Path root,String mode,MembershipLearnerPlan plan,MembershipSourcePacket packet,
            Map<String,byte[]> terminal,V53LearnerResourceCapture capture)throws Exception {
        var resources=capture.resources;var before=resources.usage();Path scratch=temp.resolve("source-"+mode);
        UUID session=UUID.randomUUID(),transfer=UUID.randomUUID();var peer=plan.request().change().target().getFirst();
        var offer=new MembershipSourceExport.Content(hash(packet.bytes()),packet.bytes().length,MembershipTransfer.Kind.CAPSULE);
        var result=new TreeMap<String,Object>();result.put("transfer",transfer.toString());result.put("session",session.toString());
        result.put("source",MembershipBootstrapSeed.identity(peer));result.put("scratch",scratch.toAbsolutePath().toString());
        try(var receiver=new MembershipSourceReceive(scratch,plan.request().root().manifestDigest(),peer,object(packet.capsule().value().get("cut")),
                session,transfer,offer,resources,1024,System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60))) {
            assertEquals("source-exact",mode);send(receiver,receiver.packetBinding(),packet.bytes());
            var bindings=new ArrayList<Map<String,Object>>();
            for(var binding:receiver.imageBindings()) {
                bindings.add(Map.of("transfer",binding.transfer().toString(),"digest",binding.digest(),"bytes",binding.bytes()));
                send(receiver,binding,terminal.get(binding.digest()+".image"));
            }
            assertArrayEquals(packet.bytes(),receiver.packet().bytes());receiver.images();receiver.recheck();
            capture.mark("PROBE_COMPLETE",mode,"");
            V53JournalApplicationTest.copy(scratch,root.resolve("received"));
            result.put("images",bindings);result.put("outcome","ACCEPTED");result.put("reason","");
        }catch(IllegalArgumentException error) {
            if(mode.equals("source-exact"))throw error;
            assertEquals("shared staging capacity",error.getMessage());result.put("outcome","REJECTED");result.put("reason",error.getMessage());result.put("images",List.of());
        }
        assertFalse(Files.exists(scratch));assertEquals(before,resources.usage());result.put("scratchRemoved",true);return result;
    }
    static void send(MembershipSourceReceive receiver,MembershipTransfer.Binding binding,byte[] bytes)throws Exception {
        assertEquals(binding.bytes(),bytes.length);
        for(int i=0;i<bytes.length;i+=1024){byte[] chunk=Arrays.copyOfRange(bytes,i,Math.min(i+1024,bytes.length));receiver.chunk(binding,i,chunk,hash(chunk));}
        receiver.finish(binding);
    }
}
