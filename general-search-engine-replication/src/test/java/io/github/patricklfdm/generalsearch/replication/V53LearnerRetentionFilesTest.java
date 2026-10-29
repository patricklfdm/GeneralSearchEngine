package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual local native owners. Does not claim remote learner/quorum qualification. */
class V53LearnerRetentionFilesTest {
    @TempDir Path temp;
    V53BootstrapPublicationTest.Fixture fixture(String name)throws Exception {
        var root=Files.createDirectory(temp.resolve(name));
        var raw=Files.createDirectories(Path.of("target/v53-learner-retention/run-"+UUID.randomUUID()).resolve(name));
        System.out.println("v53LearnerRetentionEvidence="+raw.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(root,raw,3,false);f.ownedHistory=true;f.nativeApplication=true;return f;
    }
    @Test void nativePublicationsRenewPreparedSourceAndConservativelyKeepBothAcrossCancel()throws Exception {
        var f=fixture("native");
        for(var target:f.request.targets())try(var owner=f.open(target,"learner-init")){owner.initializeLearnerRetention();}
        var walk=new V53AdmittedCrossViewTest.Walk(f);walk.publish("BARRIER",null);
        var joining=V53DeclarationsTest.node(6);var targets=new ArrayList<MembershipIdentity>();f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
        var request=Map.of("root",f.result.root().manifestDigest(),"expected",walk.current().authority(),"number",1L,"kind","ADD",
                "target",targets.stream().map(MembershipBootstrapSeed::identity).toList());
        walk.publish("RESERVE",Map.of("request",request));walk.publish("PREPARE",Map.of("number",1L,"revision",1L));
        MembershipCapsule.Anchor prepared;
        try(var owner=f.open(f.request.targets().getFirst(),"source")){prepared=owner.floorCopyCurrent().capsule.terminal();}
        for(var target:f.request.targets())try(var owner=f.open(target,"pin-prepared")) {
            assertEquals(1,owner.retainLearnerOffer(joining).revision());
            var before=V53ReplayFilesTest.files(target.replicaDirectory());assertEquals(1,owner.retainLearnerOffer(joining).revision());
            assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
            assertThrows(IllegalArgumentException.class,owner::checkLearnerRetentionExport);
        }
        walk.publish("BARRIER",null);
        var first=f.request.targets().getFirst();
        for(String cut:List.of("WRITTEN","RENAMED")) {
            f.observer=(target,operation,event)->{if(operation.equals("pin-interrupted") && event.equals("LEARNER_RETENTION_"+cut))throw new IOException("update cut");};
            try(var owner=f.open(first,"pin-interrupted")) {
                assertThrows(IOException.class,()->owner.retainLearnerOffer(joining));
                assertThrows(IllegalArgumentException.class,owner::learnerRetentionState);
            }
            f.observer=(target,operation,event)->{};f.snapshot("learner-update-"+cut+"-interrupted");
            try(var owner=f.open(first,"pin-recovered")){assertEquals(cut.equals("RENAMED")?2:1,owner.learnerRetentionState().revision());}
        }
        for(var target:f.request.targets())try(var owner=f.open(target,"pin-progress")){assertEquals(2,owner.retainLearnerOffer(joining).revision());}
        walk.publish("CANCEL",Map.of("number",1L));
        for(var target:f.request.targets()) {
            try(var owner=MembershipGrantJournal.openRetainingLearners(target.replicaDirectory(),target.materialization().directory(),f.result.root(),target.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{})) {
                var plan=owner.learnerRetentionState().plan();var current=owner.floorCopyCurrent();
                assertEquals(List.of(3L,4L),plan.recorded().stream().map(a->number(a.cut().get("index"))).toList());
                assertEquals(prepared,plan.recorded().getFirst());assertEquals(5L,current.capsule.context.cut.get("index"));
                current.capsule.verifyAncestry(current.fileBytes("ancestry.gsr"),plan.recorded());
                var before=V53ReplayFilesTest.files(target.replicaDirectory());
                assertTrue(assertThrows(IllegalArgumentException.class,()->owner.retainLearnerOffer(joining)).getMessage().contains("endpoint capacity"));
                var ballot=new TreeMap<>(f.ballot);ballot.put("counter",number(ballot.get("counter"))+1);
                byte[] payload=canonical(Map.of("through",1L),8192);var context=current.capsule.context;
                var entry=decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),"index",6L,
                        "previous",context.cut.get("entry"),"origin",f.ballot,"kind","RETIRE","payload",hash(payload))),"records","ENTRY");
                var rejected=assertThrows(MembershipOperationException.class,()->owner.acceptCurrent(entry,payload));
                assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,rejected.reason());
                assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,rejected.outcome());
                assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));assertEquals(2,owner.learnerRetentionState().revision());
                owner.prepareCurrent(ballot);var frozen=MembershipLearnerRetentionSource.read(owner.originalSource());
                assertArrayEquals(owner.learnerRetentionState().plan().bytes(),frozen.state().plan().bytes());
                assertEquals(2,frozen.state().revision());
            }
            assertEquals(0,f.resources.usage().leases());
        }
    }
    @Test void requiredOpenCannotReconstructMissingLedgerAfterGenesis()throws Exception {
        var f=fixture("missing");var self=f.request.targets().getFirst();
        try(var owner=MembershipGrantJournal.openRetainingLearners(self.replicaDirectory(),self.materialization().directory(),f.result.root(),self.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{})) {
            assertTrue(owner.learnerRetentionState().plan().empty());owner.reserveCounter();
        }
        Files.delete(self.replicaDirectory().resolve(MembershipLearnerRetentionFiles.FILE));
        assertThrows(ReplicationException.class,()->MembershipGrantJournal.openRetainingLearners(self.replicaDirectory(),self.materialization().directory(),f.result.root(),self.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{}));
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void privateStorageRefusesCorruptionForeignOwnerReplacementAndWrongPredecessor()throws Exception {
        var f=fixture("corrupt");var self=f.request.targets().getFirst();byte[] bytes;
        try(var owner=f.open(self,"init")){owner.initializeLearnerRetention();bytes=Files.readAllBytes(self.replicaDirectory().resolve(MembershipLearnerRetentionFiles.FILE));}
        var file=self.replicaDirectory().resolve(MembershipLearnerRetentionFiles.FILE);var next=self.replicaDirectory().resolve(MembershipLearnerRetentionFiles.NEXT);
        for(int offset:List.of(0,7,11,12,bytes.length-1)) {
            var bad=bytes.clone();bad[offset]^=1;Files.write(file,bad);
            assertThrows(IllegalArgumentException.class,()->f.open(self,"bad"));assertEquals(0,f.resources.usage().leases());Files.write(file,bytes);
        }
        var foreign=f.request.targets().get(1);Files.write(foreign.replicaDirectory().resolve(MembershipLearnerRetentionFiles.FILE),bytes);
        assertThrows(IllegalArgumentException.class,()->f.open(foreign,"foreign"));
        Files.write(next,bytes);assertThrows(IllegalArgumentException.class,()->f.open(self,"predecessor"));Files.delete(next);
        Files.write(next,Arrays.copyOf(bytes,20));
        try(var owner=f.open(self,"partial")){assertEquals(0,owner.learnerRetentionState().revision());assertFalse(Files.exists(next));}
        try(var owner=f.open(self,"substitution")) {
            var replacement=file.resolveSibling("substitute");Files.write(replacement,bytes);Files.move(replacement,file,StandardCopyOption.REPLACE_EXISTING);
            assertThrows(IllegalArgumentException.class,owner::learnerRetentionState);
            assertThrows(IllegalArgumentException.class,owner::reserveCounter);
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void initializationIoCutsPoisonOldOwnerAndRecoverWithoutInventingAnOffer()throws Exception {
        for(String at:List.of("BEFORE_WRITE","PREFIX_WRITTEN","WRITTEN","FORCED","CANDIDATE_PARENT_FORCED","RENAMED","PARENT_FORCED")) {
            var f=fixture(at);var self=f.request.targets().getFirst();
            f.observer=(t,operation,event)->{if(event.equals("LEARNER_RETENTION_"+at))throw new IOException("cut");};
            try(var owner=f.open(self,"init")) {
                assertThrows(IOException.class,owner::initializeLearnerRetention);
                assertThrows(IllegalArgumentException.class,owner::reserveCounter);
            }
            f.observer=(t,operation,event)->{};
            try(var owner=MembershipGrantJournal.openRetainingLearners(self.replicaDirectory(),self.materialization().directory(),f.result.root(),self.identity(),f.resources,MembershipGrantJournal.MAXIMUM,e->{})) {
                assertEquals(0,owner.learnerRetentionState().revision());assertTrue(owner.learnerRetentionState().plan().empty());
                assertFalse(Files.exists(self.replicaDirectory().resolve(MembershipLearnerRetentionFiles.NEXT)));
                assertThrows(IllegalArgumentException.class,owner::checkLearnerRetentionExport);
            }
            assertEquals(0,f.resources.usage().leases());
        }
    }
    @Test void candidateRequiresRemainingSharedJournalCapacityBeforeAnyWrite()throws Exception {
        var f=fixture("capacity");var self=f.request.targets().getFirst();
        int maximum=Math.toIntExact(Files.size(self.replicaDirectory().resolve(MembershipGrantJournal.FILE))
                +Files.size(self.replicaDirectory().resolve(MembershipPendingAccept.FILE))+MembershipPendingAccept.PREFIX
                +MembershipAppliedEndFiles.METADATA+MembershipReplayFiles.METADATA+1);
        var before=V53ReplayFilesTest.files(self.replicaDirectory());
        try(var owner=MembershipGrantJournal.openBootstrapped(self.replicaDirectory(),self.materialization().directory(),f.result.root(),self.identity(),f.resources,maximum,e->{})) {
            assertThrows(IllegalArgumentException.class,owner::initializeLearnerRetention);
        }
        assertEquals(before,V53ReplayFilesTest.files(self.replicaDirectory()));assertEquals(0,f.resources.usage().leases());
    }
}
