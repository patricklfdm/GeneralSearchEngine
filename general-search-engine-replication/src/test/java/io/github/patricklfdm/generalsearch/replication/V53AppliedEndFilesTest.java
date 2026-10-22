package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;

/** Actual file force/reopen tests; the input historical authority and external owner guard are conditional. */
class V53AppliedEndFilesTest {
    @TempDir Path temp;
    final V53CapsuleFixture fixture=new V53CapsuleFixture(3,"ADD",0);
    final MembershipCheckpointPlan plan=V53CheckpointPlanTest.plan(fixture.verify(),fixture.source,0);
    final MembershipIdentity local=V53DeclarationsTest.node(1);
    static final long LIMIT=MembershipResources.Unit.JOURNAL.bytes;
    static List<String> cuts() {
        var list=new ArrayList<>(List.of("APPLY_VALIDATED","APPLY_DIRECTORY_CREATED"));
        for(String prefix:List.of("APPLY_PLAN","APPLY_METADATA","APPLY_IMAGE","APPLY_ACK"))
            for(String suffix:List.of("CREATED","PREFIX_WRITTEN","WRITTEN","FORCED"))list.add(prefix+"_"+suffix);
        list.addAll(List.of("APPLY_END_FORCED","APPLY_ACK_DIRECTORY_FORCED","APPLY_BEFORE_RETURN"));return List.copyOf(list);
    }
    Decoded selector(MembershipCheckpointPlan plan,int node) {
        return decode(encode("records","SELECTOR",Map.of("root",plan.catalog.value().get("root"),"node","node-"+node,"generation","a","digest",H)),"records","SELECTOR");
    }
    MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    MembershipResources.Lease journal(MembershipResources r){return r.reserve(MembershipResources.Unit.JOURNAL,"test-owner",LIMIT);}
    Map<String,String> files(Path path)throws IOException {
        var result=new TreeMap<String,String>();if(Files.exists(path))try(var stream=Files.walk(path)){for(var p:stream.filter(Files::isRegularFile).toList())result.put(path.relativize(p).toString(),hash(Files.readAllBytes(p)));}return result;
    }
    @Test void actualEndAndAckForcesProduceExactLocalObservationAndIdempotentReopen()throws Exception {
        var r=resources();Path path=temp.resolve("end");var events=new ArrayList<String>();
        try(var lease=journal(r)) {
            MembershipAppliedEndFiles.Endorsement returned;
            try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                returned=store.force(plan,selector(plan,1),local,()->{},events::add);
                assertEquals(1,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                assertTrue(events.indexOf("APPLY_END_FORCED")<events.indexOf("APPLY_ACK_CREATED"));
                assertEquals("APPLY_BEFORE_RETURN",events.getLast());
                assertArrayEquals(plan.application.image(),Files.readAllBytes(path.resolve(MembershipAppliedEndFiles.IMAGE)));
            }
            var original=files(path);
            try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                var duplicate=store.force(plan,selector(plan,1),local,()->{},e->{});assertEquals(returned.owned(),duplicate.owned());
                assertArrayEquals(returned.acknowledgement().bytes(),duplicate.acknowledgement().bytes());assertEquals(original,files(path));
            }
            assertEquals(Map.of(MembershipResources.Unit.JOURNAL,1),r.usage().counts());
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void everyInterruptedWriteResumesExactBytesIncludingRepeatedRecoveryInterruption()throws Exception {
        for(String point:cuts()) {
            var r=resources();Path path=temp.resolve(point);try(var lease=journal(r)) {
                for(int attempt=0;attempt<2;attempt++)try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                    boolean[] hit={false};
                    // CREATED events only recur when their file has not yet been created.
                    String again=attempt==0?point:point.endsWith("CREATED")?"APPLY_BEFORE_RETURN":point;
                    assertThrows(IOException.class,()->store.force(plan,selector(plan,1),local,()->{},e->{if(e.equals(again)){hit[0]=true;throw new IOException("cut");}}));assertTrue(hit[0]);
                }
                try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {assertNotNull(store.force(plan,selector(plan,1),local,()->{},e->{}).owned());}
                assertEquals(Map.of(MembershipResources.Unit.JOURNAL,1),r.usage().counts());
            }
            assertEquals(0,r.usage().leases());
        }
    }
    @Test void ownerOrFenceRevocationAtEveryCutCannotReturnAnAcknowledgement()throws Exception {
        for(String point:cuts()) {
            var r=resources();Path path=temp.resolve(point);try(var lease=journal(r);var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                boolean[] revoked={false};MembershipGenerationFiles.Guard guard=()->{if(revoked[0])throw new IOException("fenced");};
                assertThrows(IOException.class,()->store.force(plan,selector(plan,1),local,guard,e->{if(e.equals(point))revoked[0]=true;}));assertTrue(revoked[0]);
                assertThrows(IOException.class,()->store.force(plan,selector(plan,1),local,guard,e->{}));
            }
        }
    }
    @Test void changedPlanMissingEndAndCorruptionPreserveAllOriginalBytes()throws Exception {
        var r=resources();Path path=temp.resolve("original");try(var lease=journal(r)) {
            try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)){store.force(plan,selector(plan,1),local,()->{},e->{});}
            var original=files(path);var changed=V53CheckpointPlanTest.plan(new V53CapsuleFixture(3,"ADD",1).verify(),fixture.source,1);
            try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                assertThrows(IllegalArgumentException.class,()->store.force(changed,selector(changed,1),local,()->{},e->{}));
                assertThrows(IllegalArgumentException.class,()->store.force(plan,selector(plan,2),local,()->{},e->{}));assertEquals(original,files(path));
            }
            Files.write(path.resolve("application.image"),new byte[0]);original=files(path);
            try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                assertThrows(IllegalArgumentException.class,()->store.force(plan,selector(plan,1),local,()->{},e->{}));assertEquals(original,files(path));
            }
            Files.write(path.resolve("application.image"),new byte[]{9});original=files(path);
            try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                assertThrows(IllegalArgumentException.class,()->store.force(plan,selector(plan,1),local,()->{},e->{}));assertEquals(original,files(path));
            }
        }
    }
    @Test void capacityAndIdentityRefuseBeforeCreatingFilesAndReleaseAllReservations()throws Exception {
        var r=resources();Path path=temp.resolve("small");assertThrows(IllegalArgumentException.class,()->new MembershipAppliedEndFiles(path,r,LIMIT));
        try(var lease=journal(r);var store=new MembershipAppliedEndFiles(path,r,1)) {
            assertThrows(IllegalArgumentException.class,()->store.force(plan,selector(plan,1),local,()->{},e->{}));assertFalse(Files.exists(path));
        }
        var low=new MembershipResources(1);try(var lease=journal(low);var store=new MembershipAppliedEndFiles(path,low,LIMIT)) {
            assertThrows(IllegalArgumentException.class,()->store.force(plan,selector(plan,1),local,()->{},e->{}));assertFalse(Files.exists(path));
        }
        try(var lease=journal(r);var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
            assertThrows(IllegalArgumentException.class,()->store.force(plan,selector(plan,6),V53DeclarationsTest.node(6),()->{},e->{}));assertFalse(Files.exists(path));
        }
        assertEquals(0,r.usage().leases());assertEquals(0,low.usage().leases());
    }
    @Test void sameByteInodeReplacementUnknownFilesAndLinksFailClosed()throws Exception {
        for(String event:List.of("APPLY_PLAN_FORCED","APPLY_IMAGE_FORCED","APPLY_BEFORE_RETURN")) {
            var r=resources();Path path=temp.resolve(event);try(var lease=journal(r);var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                assertThrows(IllegalArgumentException.class,()->store.force(plan,selector(plan,1),local,()->{},e->{if(e.equals(event)) {
                    Path file=path.resolve("plan.json"),replacement=temp.resolve("replacement");Files.write(replacement,Files.readAllBytes(file));Files.move(replacement,file,StandardCopyOption.REPLACE_EXISTING);
                }}));
            }
        }
        var r=resources();Path unknown=temp.resolve("unknown");Files.createDirectory(unknown);Files.writeString(unknown.resolve("extra"),"x");
        try(var lease=journal(r)) {
            assertThrows(IllegalArgumentException.class,()->new MembershipAppliedEndFiles(unknown,r,LIMIT));
            Path linked=temp.resolve("link");Files.createSymbolicLink(linked,unknown);assertThrows(RuntimeException.class,()->new MembershipAppliedEndFiles(linked,r,LIMIT));
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void actualEndFilesSupplyBothSuccessorMajoritiesWithoutPhasedReceiptSubstitution()throws Exception {
        var f=new V53CapsuleFixture(5,"REPLACE",5);var p=V53CheckpointPlanTest.plan(f.verify(),f.source,5);
        var acknowledgements=new ArrayList<Decoded>();var owned=new HashSet<MembershipContext.Owned>();
        for(int node:List.of(1,2,3)) {
            var r=resources();try(var lease=journal(r);var store=new MembershipAppliedEndFiles(temp.resolve("node-"+node),r,LIMIT)) {
                var end=store.force(p,selector(p,node),V53DeclarationsTest.node(node),()->{},e->{});
                acknowledgements.add(end.acknowledgement());owned.add(end.owned());
            }
            assertEquals(0,r.usage().leases());
        }
        var capsule=p.complete(acknowledgements,owned);assertNotNull(capsule.context.view.get("operation"));
        var finalPlan=V53CheckpointPlanTest.plan(capsule,f.source,6);var r=resources();Path removed=temp.resolve("removed");
        try(var lease=journal(r);var store=new MembershipAppliedEndFiles(removed,r,LIMIT)) {
            assertThrows(IllegalArgumentException.class,()->store.force(finalPlan,selector(finalPlan,5),V53DeclarationsTest.node(5),()->{},e->{}));assertFalse(Files.exists(removed));
        }
    }
    @Test void exhaustedImageSlotsAndRevokedJournalLeaseCannotStartOrFinish()throws Exception {
        var r=resources();Path path=temp.resolve("slots");var held=new ArrayList<MembershipResources.Lease>();
        try(var lease=journal(r);var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
            try {
                for(int i=0;i<7;i++)held.add(r.reserve(MembershipResources.Unit.APPLICATION,"held-"+i,1));
                assertThrows(IllegalArgumentException.class,()->store.force(plan,selector(plan,1),local,()->{},e->{}));assertFalse(Files.exists(path));
            }finally{held.forEach(MembershipResources.Lease::close);}
            assertThrows(IllegalArgumentException.class,()->store.force(plan,selector(plan,1),local,()->{},event->{if(event.equals("APPLY_END_FORCED"))lease.close();}));
            assertFalse(Files.exists(path.resolve(MembershipAppliedEndFiles.ACK)));
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void haltAndSigkillAtEveryCutRecoverAgainInFreshExclusivelyOwnedProcesses()throws Exception {
        Path retained=Path.of("target/v53-applied-end-process").resolve("run-"+UUID.randomUUID());Files.createDirectories(retained);
        var receipt=new ArrayList<Map<String,Object>>();
        try {
            for(String mode:List.of("halt","kill"))for(String point:cuts()) {
                Path root=retained.resolve(mode+"-"+point);Files.createDirectory(root);Files.write(root.resolve("owner.lock"),new byte[0]);
                child(root,"fault",point,mode);snapshot(root,"crash");
                child(root,"recovery-fault","APPLY_IMAGE_PREFIX_WRITTEN","halt");snapshot(root,"recovery-crash");
                child(root,"resume","none","none");snapshot(root,"final");
                var ack=decode(Files.readAllBytes(root.resolve("end/ack.gsr")),"records","CHECKPOINT_ACK");
                assertEquals(plan.statement.digest(),ack.value().get("statement"));assertArrayEquals(plan.application.image(),Files.readAllBytes(root.resolve("end/application.image")));
                receipt.add(Map.of("mode",mode,"cut",point,"status","PASS","ack",ack.digest()));
            }
        }finally {
            Files.write(retained.resolve("receipt.json"),canonical(Map.of("cases",receipt,"expectedCases",(long)cuts().size()*2,
                    "protocolAuthority","conditional-fixture","powerLoss",false),65536));
            System.out.println("v53AppliedEndProcessEvidence="+retained.toAbsolutePath());
        }
        assertEquals(cuts().size()*2,receipt.size());
    }
    static void snapshot(Path root,String name)throws IOException {
        Path target=root.resolve(name);Files.createDirectory(target);
        if(Files.exists(root.resolve("end")))try(var files=Files.list(root.resolve("end"))) {
            for(var file:files.toList())Files.copy(file,target.resolve(file.getFileName()));
        }
    }
    static void child(Path root,String label,String point,String mode)throws Exception {
        Path stdout=root.resolve(label+".stdout"),stderr=root.resolve(label+".stderr");
        var proc=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-XX:-UsePerfData","-cp",System.getProperty("java.class.path"),
                V53AppliedEndWorker.class.getName(),root.toAbsolutePath().toString(),point,mode).redirectOutput(stdout.toFile()).redirectError(stderr.toFile()).start();
        try {
            if(mode.equals("kill")) {
                String marker=new String(canonical(Map.of("event","AWAITING_KILL","cut",point),16384),java.nio.charset.StandardCharsets.US_ASCII)+"\n";
                long deadline=System.nanoTime()+30_000_000_000L;
                while(!Files.readString(stdout).endsWith(marker)) {assertTrue(proc.isAlive(),"worker exited before kill marker: "+stderr);assertTrue(System.nanoTime()<deadline,"kill marker deadline");Thread.sleep(20);}
                proc.destroyForcibly();
            }
            assertTrue(proc.waitFor(30,java.util.concurrent.TimeUnit.SECONDS),"worker deadline: "+root);
            assertEquals(mode.equals("halt")?73:mode.equals("kill")?137:0,proc.exitValue(),Files.readString(stderr));
            assertEquals("",Files.readString(stderr));String output=Files.readString(stdout);
            assertEquals(mode.equals("none"),output.contains("\"status\":\"PASS\""));
        }finally{if(proc.isAlive())proc.destroyForcibly();proc.waitFor();}
    }
}
