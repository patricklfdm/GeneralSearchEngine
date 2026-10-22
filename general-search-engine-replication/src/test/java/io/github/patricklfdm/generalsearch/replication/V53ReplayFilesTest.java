package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Bounded disposable scratch and actual core writes; the claim's protocol history is conditional here. */
class V53ReplayFilesTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("REPLAY_RESERVED","REPLAY_DIRECTORY_CREATED","REPLAY_CLAIM_CREATED","REPLAY_CLAIM_PREFIX_WRITTEN",
            "REPLAY_CLAIM_WRITTEN","REPLAY_CLAIM_FORCED","REPLAY_BEFORE_APPLICATION","REPLAY_APPLICATION_FINISHED","REPLAY_BEFORE_DELETE","REPLAY_DELETED","REPLAY_BEFORE_RETURN");
    static final List<String> CORE_CUTS=List.of("v41-backup-after-marker-force-v1","v41-backup-after-manifest-force-v1","v41-backup-after-manifest-rename-v1",
            "v41-backup-before-final-rename-v1","v41-backup-after-final-rename-v1","v41-backup-after-parent-force-v1","v41-backup-before-future-completion-v1");
    final V53CapsuleFixture f=new V53CapsuleFixture(3,"ADD",0);
    final MembershipCheckpointPlan plan=V53CheckpointPlanTest.plan(f.verify(),f.source,0);
    final Decoded selector=decode(encode("records","SELECTOR",Map.of("root",plan.catalog.value().get("root"),"node","node-1","generation","a","digest",V53ContextFixture.H)),"records","SELECTOR");
    final MembershipIdentity identity=V53DeclarationsTest.node(1);
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipResources.Lease journal(MembershipResources r){return r.reserve(MembershipResources.Unit.JOURNAL,"owner",MembershipResources.Unit.JOURNAL.bytes);}
    <T> T execute(MembershipReplayFiles store,MembershipReplayFiles.Action<T> action,MembershipBallotAllocator.Cut cut)throws IOException {
        return store.execute(selector,plan.originalCertificate(),identity,action,()->{},cut);
    }
    static byte[] base(Path root)throws Exception {
        var test=new V53ApplicationReplayTest();test.temp=root;return test.initial(41);
    }
    static MembershipApplicationReplay.Result replay(Path root,byte[] base,Path work)throws IOException {
        var test=new V53ApplicationReplayTest();test.temp=root;byte[] payload;
        try(var encoder=test.encoder()){payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(3,"new"))));}
        return MembershipApplicationReplay.replay(test.configuration(),test.storage(),base,hash(base),V53ApplicationImageTest.HISTORY,41,0,
                List.of(new MembershipApplicationReplay.Step(1,"DATA",payload)),work);
    }
    @Test void realCoreReplayCleansOnlyScratchAndReturnsItsTwoFullReservations()throws Exception {
        byte[] base=base(temp),expected=replay(temp,base,temp.resolve("expected")).image();Path path=temp.resolve("scratch");var r=resources();
        try(var lease=journal(r);var store=new MembershipReplayFiles(path,r)) {
            for(int n=0;n<3;n++) {
                var result=execute(store,work->{assertEquals(2,r.usage().counts().get(MembershipResources.Unit.APPLICATION));return replay(temp,base,work);},e->{});
                assertArrayEquals(expected,result.image());assertEquals(42,result.sequence());assertFalse(Files.exists(path));assertEquals(1,r.usage().leases());
            }
        }
        assertEquals(0,r.usage().leases());assertTrue(Files.isDirectory(temp.resolve("expected")));assertFalse(Files.exists(temp.resolve("anchor")));
    }
    @Test void everyInterruptionRetainsReservationsAndResumesExactClaimIncludingInterruptedDeletion()throws Exception {
        byte[] base=base(temp);
        for(String point:CUTS) {
            Path path=temp.resolve(point);var r=resources();
            try(var lease=journal(r);var store=new MembershipReplayFiles(path,r)) {
                assertThrows(IOException.class,()->execute(store,work->replay(temp,base,work),event->{if(event.equals(point))throw new IOException(point);}));
                if(Files.exists(path))assertEquals(2,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
            }
            assertEquals(0,r.usage().leases());
            try(var lease=journal(r);var store=new MembershipReplayFiles(path,r)) {
                if(Files.exists(path))assertEquals(2,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                assertThrows(IOException.class,()->execute(store,work->replay(temp,base,work),event->{if(event.equals("REPLAY_DELETED"))throw new IOException("recovery");}));
            }
            try(var lease=journal(r);var store=new MembershipReplayFiles(path,r)) {assertEquals(42,execute(store,work->replay(temp,base,work),e->{}).sequence());}
            assertFalse(Files.exists(path));assertEquals(0,r.usage().leases());
        }
    }
    @Test void originalClaimAndGuardPreventChangedRequestsOrLostOwnerFromDeletingFiles()throws Exception {
        byte[] base=base(temp);Path path=temp.resolve("scratch");var r=resources();
        try(var lease=journal(r);var store=new MembershipReplayFiles(path,r)) {
            assertThrows(IOException.class,()->execute(store,work->replay(temp,base,work),e->{if(e.equals("REPLAY_APPLICATION_FINISHED"))throw new IOException("retain");}));
        }
        var original=files(path);var altered=new TreeMap<>(selector.value());altered.put("digest",hash(new byte[]{9}));
        try(var lease=journal(r);var store=new MembershipReplayFiles(path,r)) {
            assertThrows(IllegalArgumentException.class,()->store.execute(decode(encode("records","SELECTOR",altered),"records","SELECTOR"),plan.originalCertificate(),identity,w->0,()->{},e->{}));
            assertEquals(original,files(path));
            assertThrows(IOException.class,()->store.execute(selector,plan.originalCertificate(),identity,w->0,()->{throw new IOException("lost");},e->{}));assertEquals(original,files(path));
            assertThrows(IOException.class,()->execute(store,w->0,e->{if(e.equals("REPLAY_BEFORE_DELETE"))throw new IOException("lost before delete");}));assertEquals(original,files(path));
        }
    }
    @Test void forgedMembersLinksChangedInodesAndOversizedBundlesArePreservedAndRejected()throws Exception {
        byte[] base=base(temp);
        for(String variant:List.of("extra","symlink","hardlink","oversize","marker","replace")) {
            Path path=temp.resolve(variant);var r=resources();
            try(var lease=journal(r);var store=new MembershipReplayFiles(path,r)) {
                assertThrows(IOException.class,()->execute(store,w->replay(temp,base,w),e->{if(e.equals("REPLAY_APPLICATION_FINISHED"))throw new IOException("retain");}));
            }
            Path member=path.resolve("work/input/gse-backup-checkpoint");
            if(variant.equals("replace")) {
                try(var lease=journal(r);var store=new MembershipReplayFiles(path,r)) {
                    Path other=temp.resolve("copy");Files.copy(member,other);Files.move(other,member,StandardCopyOption.REPLACE_EXISTING);assertThrows(IllegalArgumentException.class,store::check);
                }continue;
            }
            switch(variant) {
                case "extra" -> Files.writeString(path.resolve("work/unlisted"),"preserve");
                case "symlink" -> {Files.delete(member);Files.createSymbolicLink(member,temp.resolve("base-41/gse-backup-checkpoint"));}
                case "hardlink" -> {Files.delete(member);Files.createLink(member,temp.resolve("base-41/gse-backup-checkpoint"));}
                case "oversize" -> {try(var channel=java.nio.channels.FileChannel.open(member,StandardOpenOption.WRITE)){channel.position(MembershipApplicationImage.MAXIMUM);channel.write(java.nio.ByteBuffer.wrap(new byte[]{0}));}}
                case "marker" -> Files.writeString(path.resolve("work/.gse-v41-backup-00000000000000000000000000000001.staging.operation"),"foreign-target");
            }
            try(var lease=journal(r)){assertThrows(RuntimeException.class,()->new MembershipReplayFiles(path,r));assertEquals(1,r.usage().leases());}
            assertTrue(Files.exists(path));
        }
    }
    @Test void insufficientSlotsOrStagingRefuseBeforeAnyFileAndReleasePartialReservation()throws Exception {
        for(boolean slots:List.of(false,true)) {
            var r=slots?resources():new MembershipResources(64*MembershipResources.MIB);var held=new ArrayList<MembershipResources.Lease>();Path path=temp.resolve("small-"+slots);
            try(var lease=journal(r);var store=new MembershipReplayFiles(path,r)) {
                if(slots)for(int i=0;i<6;i++)held.add(r.reserve(MembershipResources.Unit.APPLICATION,"held-"+i,1));
                int count=r.usage().leases();assertThrows(IllegalArgumentException.class,()->execute(store,w->0,e->{}));assertEquals(count,r.usage().leases());assertFalse(Files.exists(path));
            }finally{held.forEach(MembershipResources.Lease::close);}
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void realCoreCrashRemnantsAndScratchCutsRecoverInFreshProcesses()throws Exception {
        Path retained=Path.of("target/v53-replay-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(retained);
        byte[] base=base(retained);Files.write(retained.resolve("base.image"),base);String expected=hash(replay(retained,base,retained.resolve("expected")).image());
        var points=new ArrayList<>(CUTS);points.addAll(CORE_CUTS);var receipt=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(String point:points) {
                Path root=retained.resolve(mode+"-"+point);Files.createDirectory(root);Files.write(root.resolve("owner.lock"),new byte[0]);
                child(root,"fault",point,mode);snapshot(root,"crash");
                child(root,"recovery-fault","REPLAY_DELETED","halt");snapshot(root,"recovery-crash");
                child(root,"resume","none","none");assertFalse(Files.exists(root.resolve("scratch")));
                assertTrue(Files.readString(root.resolve("resume.stdout")).contains(expected));
                receipt.add(Map.of("mode",mode,"cut",point,"status","PASS","image",expected));
            }
        }finally {
            Files.write(retained.resolve("receipt.json"),canonical(Map.of("cases",receipt,"expectedCases",(long)points.size()*2,"freshJvms",(long)receipt.size()*3,
                    "protocolAuthority","conditional-fixture","powerLoss",false),65536));System.out.println("v53ReplayProcessEvidence="+retained.toAbsolutePath());
        }
        assertEquals(points.size()*2,receipt.size());
    }
    static Map<String,String> files(Path path)throws IOException {
        var result=new TreeMap<String,String>();try(var stream=Files.walk(path)){for(Path p:stream.filter(Files::isRegularFile).toList())result.put(path.relativize(p).toString(),hash(Files.readAllBytes(p)));}return result;
    }
    static void snapshot(Path root,String name)throws IOException {
        Path to=root.resolve(name),from=root.resolve("scratch");Files.createDirectory(to);if(!Files.exists(from))return;
        try(var stream=Files.walk(from)){for(Path source:stream.toList()){Path target=to.resolve(from.relativize(source));if(Files.isDirectory(source)){if(!Files.exists(target))Files.createDirectory(target);}else Files.copy(source,target);}}
    }
    static void child(Path root,String label,String point,String mode)throws Exception {
        Path stdout=root.resolve(label+".stdout"),stderr=root.resolve(label+".stderr");
        var proc=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53ReplayFilesWorker.class.getName(),root.toAbsolutePath().toString(),point,mode).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=point.startsWith("v41-")?"GSE_BARRIER_READY=":"AWAITING_KILL";long end=System.nanoTime()+30_000_000_000L;
                while(!Files.readString(stdout).contains(marker)){assertTrue(proc.isAlive(),Files.readString(stderr));assertTrue(System.nanoTime()<end,"kill marker deadline");Thread.sleep(20);}proc.destroyForcibly();
            }
            assertTrue(proc.waitFor(30,java.util.concurrent.TimeUnit.SECONDS),"worker deadline");
            assertEquals(mode.equals("halt")?(point.startsWith("v41-")?86:73):mode.equals("kill")?137:0,proc.exitValue(),Files.readString(stderr));
            assertEquals("",Files.readString(stderr));assertEquals(mode.equals("none"),Files.readString(stdout).contains("\"status\":\"PASS\""));
        }finally{if(proc.isAlive())proc.destroyForcibly();proc.waitFor();}
    }
}
