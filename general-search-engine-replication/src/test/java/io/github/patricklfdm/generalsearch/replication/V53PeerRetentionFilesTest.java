package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53PeerRetentionFilesTest {
    @TempDir Path temp;
    private Path evidence;
    V53BootstrapPublicationTest.Fixture fixture(String name)throws Exception {
        if(evidence==null){evidence=Files.createDirectories(Path.of("target/v53-peer-retention-storage/run-"+UUID.randomUUID()));System.out.println("v53PeerRetentionEvidence="+evidence.toAbsolutePath());}
        Path root=Files.createDirectory(temp.resolve(name));Path raw=Files.createDirectory(evidence.resolve(name));
        var f=new V53BootstrapPublicationTest.Fixture(root,raw,3,false);f.ownedHistory=true;return f;
    }
    @Test void nativeDispatchRetainsBothEndpointsAcrossReopenAndOldReplies()throws Exception {
        var f=fixture("native");var self=f.request.targets().getFirst();var peer=f.request.targets().get(1);MembershipFloor.Copy zero;
        try(var owner=f.open(peer,"old-copy")){zero=owner.floorCopyCurrent();}
        try(var owner=f.open(self,"initialize")){
            assertEquals(0,owner.initializePeerRetention().revision());assertEquals(1,f.resources.usage().counts().get(MembershipResources.Unit.MISC));
            assertEquals(0,owner.initializePeerRetention().revision());
        }
        for(var target:f.request.targets().subList(1,3))try(var owner=f.open(target,"initialize-peer")){owner.initializePeerRetention();}
        f.campaign(1);f.publish(1,false);
        try(var owner=f.open(self,"dispatch")){
            var state=owner.retainPeerDispatch(peer.identity());assertEquals(1,state.revision());
            assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(state.plan().possible(peer.identity())));
            assertThrows(IllegalArgumentException.class,()->owner.retainPeerDispatch(peer.identity()));
            assertEquals(1,owner.peerRetentionState().revision());
        }
        try(var owner=f.open(self,"stale-copy")){
            assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
            assertEquals(List.of(0L,1L),V53PeerRetentionPlanTest.cuts(owner.retainPeerObservation(zero).plan().possible(peer.identity())));
        }
        MembershipFloor.Copy one;try(var owner=f.open(peer,"new-copy")){one=owner.floorCopyCurrent();}
        try(var owner=f.open(self,"observed")){
            assertEquals(List.of(1L),V53PeerRetentionPlanTest.cuts(owner.retainPeerObservation(one).plan().possible(peer.identity())));
        }
        for(var target:f.request.targets().subList(1,3))try(var owner=f.open(target,"observed-peer")){owner.retainPeerObservation(one);}
        f.publish(2,true);
        try(var owner=f.open(self,"after-publication")){
            assertEquals(List.of(1L),V53PeerRetentionPlanTest.cuts(owner.peerRetentionState().plan().possible(peer.identity())));
            var current=owner.floorCopyCurrent();assertTrue(current.capsule.ancestryAnchors(current.fileBytes("ancestry.gsr")).keySet().stream().anyMatch(c->number(c.get("index"))==1));
        }
        // A new selection must preserve the pinned intermediate ancestor, even
        // when all offered current cuts agree and would otherwise omit it.
        var offers=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();var obsolete=new TreeMap<String,String>();
        try(var owner=f.open(self,"allocate-retained")){f.ballot=Map.of("counter",owner.reserveCounter(),"proposer",self.identity().nodeId().value(),"incarnation",self.identity().storageId().toString());}
        for(var target:f.request.targets())try(var owner=f.open(target,"prepare-retained")) {
            obsolete.put(target.identity().nodeId().value(),(String)owner.originalBasis().orElseThrow().value().get("basisId"));
            owner.prepareCurrent(f.ballot);var source=owner.originalSource();offers.add(source);
            for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(target.replicaDirectory().resolve("sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
        }
        for(var target:f.request.targets())try(var owner=f.open(target,"select-retained")){owner.selectCurrent(offers,List.of());}
        for(var target:f.request.targets())try(var owner=f.open(target,"install-retained")) {
            var before=V53ReplayFilesTest.files(target.replicaDirectory());
            var local=owner.floorCopyCurrent();
            var parents=owner.peerRetentionState().plan().required(local.capsule,local.fileBytes("ancestry.gsr"));
            var decision=new MembershipSelection.Campaign(offers.getFirst()).select(offers,List.of());
            assertEquals(owner.originalSelection().orElseThrow().digest(),decision.selected().digest());
            // Since native local-ancestry inheritance was introduced, an empty
            // caller list is valid when this owner already retains the proof.
            // Removing both sources of the required proof must still fail.
            assertThrows(IllegalArgumentException.class,()->MembershipGenerationPlan.installation(
                    decision,List.of(),List.of(),parents,local.capsule,new byte[0]));
            assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
            var installed=owner.installCurrent(offers,List.of(),List.of(),images);
            assertArrayEquals(installed.bytes(),owner.installCurrent(offers,List.of(),f.bridges,images).bytes());
            var copy=owner.floorCopyCurrent();assertTrue(copy.capsule.ancestryAnchors(copy.fileBytes("ancestry.gsr")).keySet().stream().anyMatch(c->number(c.get("index"))==1));
        }
        f.maintain("retention-round-settled",obsolete);f.publish(3,false);
        Files.write(f.raw.resolve("native-result.json"),canonical(Map.of("status","PASS","publications",3L,"campaigns",2L,"retainedPeerCut",1L,"events",f.calls),1024*1024));
        Path file=self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE);Files.delete(file);
        try(var owner=f.open(self,"missing-state")){assertThrows(IllegalArgumentException.class,owner::initializePeerRetention);}
        assertThrows(IllegalArgumentException.class,()->MembershipGrantJournal.openRetainingPeers(self.replicaDirectory(),self.materialization().directory(),
                f.result.root(),self.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{}));
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void requiredEntryCannotReinitializeAfterAnyNewBallotAllocation()throws Exception {
        var f=fixture("lost-before-publication");var self=f.request.targets().getFirst();
        try(var owner=MembershipGrantJournal.openRetainingPeers(self.replicaDirectory(),self.materialization().directory(),
                f.result.root(),self.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{})) {
            assertEquals(0,owner.peerRetentionState().revision());owner.reserveCounter();
        }
        Files.delete(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));
        assertThrows(ReplicationException.class,()->MembershipGrantJournal.openRetainingPeers(self.replicaDirectory(),self.materialization().directory(),
                f.result.root(),self.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{}));
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void retainedAndCandidateBytesShareTheOriginalJournalCeiling()throws Exception {
        var f=fixture("capacity");var self=f.request.targets().getFirst();
        try(var owner=f.open(self,"init")){owner.initializePeerRetention();}
        Path directory=self.replicaDirectory();var original=V53ReplayFilesTest.files(directory);
        int maximum=Math.toIntExact(Files.size(directory.resolve(MembershipGrantJournal.FILE))
                +Files.size(directory.resolve(MembershipPendingAccept.FILE))+MembershipPendingAccept.PREFIX
                +MembershipAppliedEndFiles.METADATA+MembershipReplayFiles.METADATA
                +Files.size(directory.resolve(MembershipPeerRetentionFiles.FILE))+1);
        try(var owner=MembershipGrantJournal.openRetainingPeers(directory,self.materialization().directory(),f.result.root(),self.identity(),f.resources,maximum,e->{})) {
            assertThrows(IllegalArgumentException.class,()->owner.reconcilePeerRetention(List.of()));
            assertEquals(original,V53ReplayFilesTest.files(directory));assertFalse(Files.exists(directory.resolve(MembershipPeerRetentionFiles.NEXT)));
        }
        try(var owner=f.open(self,"capacity-reopen")){assertEquals(0,owner.peerRetentionState().revision());}
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void canonicalCodecRejectsUnknownFieldsAndMutatedOwnedBytes()throws Exception {
        var f=fixture("corrupt");var self=f.request.targets().getFirst();byte[] original;
        try(var owner=f.open(self,"init")){
            var state=owner.initializePeerRetention();original=Files.readAllBytes(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));
            assertArrayEquals(state.plan().bytes(),MembershipPeerRetentionPlan.decode(state.plan().bytes()).bytes());
            var fields=new TreeMap<>(object(parse(state.plan().bytes(),32768)));fields.put("ignored",true);
            assertThrows(IllegalArgumentException.class,()->MembershipPeerRetentionPlan.decode(canonical(fields,32768)));
        }
        Path file=self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE);
        for(int offset:new int[]{0,7,11,12,original.length-1}) {
            byte[] bad=original.clone();bad[offset]^=1;Files.write(file,bad);
            assertThrows(IllegalArgumentException.class,()->f.open(self,"corrupt-open"));assertEquals(0,f.resources.usage().leases());Files.write(file,original);
        }
        var foreign=f.request.targets().get(1);Files.write(foreign.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE),original);
        assertThrows(IllegalArgumentException.class,()->f.open(foreign,"foreign-owner"));
        try(var owner=f.open(self,"live-substitution")){
            Path saved=file.resolveSibling("temporary-exact-copy");Files.write(saved,original);Files.move(saved,file,StandardCopyOption.REPLACE_EXISTING);
            assertThrows(IllegalArgumentException.class,owner::peerRetentionState);
            assertThrows(IllegalArgumentException.class,owner::reserveCounter);
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void unexposedPartialCandidatesCanBeDiscardedButDamagedCompleteOnesCannot()throws Exception {
        var f=fixture("candidate");var self=f.request.targets().getFirst();byte[] active;
        try(var owner=f.open(self,"init")){owner.initializePeerRetention();active=Files.readAllBytes(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));}
        Path next=self.replicaDirectory().resolve(MembershipPeerRetentionFiles.NEXT);
        Files.write(next,Arrays.copyOf(active,20));
        try(var owner=f.open(self,"partial-discard")){assertEquals(0,owner.peerRetentionState().revision());assertFalse(Files.exists(next));}
        Files.write(next,active);assertThrows(IllegalArgumentException.class,()->f.open(self,"wrong-candidate-parent"));assertTrue(Files.exists(next));Files.delete(next);
        Files.createSymbolicLink(next,self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE));
        assertThrows(ReplicationException.class,()->f.open(self,"symlink"));Files.delete(next);
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void actualHaltAndKillPreserveTheLastExposableRevision()throws Exception {
        String[] points={"RETENTION_BEFORE_WRITE","RETENTION_PREFIX_WRITTEN","RETENTION_WRITTEN","RETENTION_FORCED",
                "RETENTION_CANDIDATE_PARENT_FORCED","RETENTION_RENAMED","RETENTION_PARENT_FORCED"};
        for(String mode:List.of("halt","kill"))for(String point:points) {
            var f=fixture(mode+"-"+point);var self=f.request.targets().getFirst();
            try(var owner=f.open(self,"init")){owner.initializePeerRetention();}
            Files.copy(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE),f.raw.resolve("before.gspr"));
            Path log=f.raw.resolve("worker.log");
            var process=new ProcessBuilder(Path.of(System.getProperty("java.home"),"bin/java").toString(),"-cp",System.getProperty("java.class.path"),
                    V53PeerRetentionWorker.class.getName(),self.replicaDirectory().toString(),self.materialization().directory().toString(),"update",mode,point)
                    .redirectErrorStream(true).redirectOutput(log.toFile()).start();
            try {
                long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
                while(process.isAlive() && !Files.readString(log).contains("CUT "+point) && System.nanoTime()<deadline)Thread.sleep(10);
                assertTrue(Files.readString(log).contains("CUT "+point),Files.readString(log));
                assertFalse(Files.readString(log).contains("\"status\":\"PASS\""));
                if(mode.equals("kill")) {
                    assertThrows(Exception.class,()->f.open(self,"lock-probe"));assertEquals(0,f.resources.usage().leases());
                    process.destroyForcibly();
                }
                assertTrue(process.waitFor(10,TimeUnit.SECONDS));assertEquals(mode.equals("halt")?23:137,process.exitValue());
                // Only an atomically selected active record can survive as the next revision.
                long expected=Set.of("RETENTION_RENAMED","RETENTION_PARENT_FORCED").contains(point)?1:0;
                if(Files.exists(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.NEXT)))
                    Files.copy(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.NEXT),f.raw.resolve("interrupted.next.gspr"));
                Files.copy(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE),f.raw.resolve("interrupted.active.gspr"));
                try(var owner=f.open(self,"recover")){
                    assertEquals(expected,owner.peerRetentionState().revision(),point);
                    assertFalse(Files.exists(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.NEXT)));
                    Files.copy(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE),f.raw.resolve("recovered.gspr"));
                    assertEquals(expected+1,owner.reconcilePeerRetention(List.of()).revision());
                }
                Files.copy(self.replicaDirectory().resolve(MembershipPeerRetentionFiles.FILE),f.raw.resolve("continued.gspr"));
                Files.write(f.raw.resolve("result.json"),canonical(Map.of("status","PASS","mode",mode,"cut",point,"exit",(long)process.exitValue(),
                        "recoveredRevision",expected,"continuedRevision",expected+1,"events",f.calls),65536));
                System.out.println("v53PeerRetentionCrash="+mode+":"+point+" PASS");
                assertEquals(0,f.resources.usage().leases());
            }finally{if(process.isAlive()){process.destroyForcibly();process.waitFor(10,TimeUnit.SECONDS);}}
        }
    }
}
