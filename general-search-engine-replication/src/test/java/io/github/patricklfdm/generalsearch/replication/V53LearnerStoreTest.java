package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipLearnerAdmissionFiles.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.key;

/** Real transfer, durable installation and exclusive recovery. Historical source
 * forces are explicitly conditional; a separate network gate uses native originals. */
class V53LearnerStoreTest {
    @TempDir Path temp;
    @Test void processShardSelectionPreservesTheDefaultMatrixAndRejectsTypos() {
        assertEquals(12,V53LearnerStoreNetworkTest.cases(null).size());
        for(String name:V53LearnerStoreNetworkTest.cases(null))assertEquals(List.of(name),V53LearnerStoreNetworkTest.cases(name));
        for(String name:List.of("","unknown","LEARNER_SOURCE_MOVED","LEARNER_SOURCE_MOVED-kill "))
            assertThrows(IllegalArgumentException.class,()->V53LearnerStoreNetworkTest.cases(name));
    }
    final class Fixture implements AutoCloseable {
        final V53LearnerSourceTest.Fixture source;
        final MembershipSourcePull prefix,generation;
        final MembershipFloor.Copy original;
        final MembershipLearnerAdmissionPlan plan;
        final Path scratch;
        Fixture(int size,String kind,int index)throws Exception {
            var helper=new V53LearnerSourceTest();helper.temp=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
            source=helper.new Fixture(size,kind,index);scratch=Files.createDirectory(helper.temp.resolve("receiving")).resolve("scratch");prefix=source.pull();generation=source.pull();
            prefix.fetchPrefix(scratch);original=generation.fetchGeneration(prefix);plan=MembershipLearnerAdmissionPlan.create(source.request,original);
            try(var files=MembershipLearnerAdmissionFiles.create(plan,source.client,e->{},()->plan.checkOriginal(original))){files.summary();}
        }
        Fixture()throws Exception{this(3,"ADD",2);}
        MembershipLearnerStore install(MembershipBallotAllocator.Cut cut)throws IOException {
            var receive=prefix.completeLearnerSource(original,cut);
            return MembershipLearnerStore.install(MembershipLearnerAdmissionFiles.openAdmission(plan.summary(),source.client,cut),receive,original,cut);
        }
        MembershipLearnerStore resume(MembershipBallotAllocator.Cut cut)throws IOException {
            return MembershipLearnerStore.resume(plan.summary(),source.client,cut);
        }
        Path replica(){return plan.request.replicaDirectory();}
        Path operation(){return plan.request.operationDirectory();}
        Path destination(){return replica().resolve("learner");}
        void disconnect()throws IOException {generation.close();prefix.close();}
        @Override public void close()throws Exception {disconnect();source.close();}
    }
    @Test void allFiveLearnerShapesRetainOriginalInodesAndNeverCreateVotingState()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            for(int index:List.of(2,3,4,5))try(var f=new Fixture(size,kind,index)) {
                var original=V53ReplayFilesTest.files(f.source.path);var cut=f.original.capsule.context.cut;
                Object directory=key(f.scratch);var keys=new TreeMap<String,Object>();
                try(var paths=Files.list(f.scratch)){for(Path p:paths.toList())keys.put(p.getFileName().toString(),key(p));}
                var events=new ArrayList<String>();
                try(var store=f.install(events::add)) {
                    f.disconnect();assertEquals(cut,store.capsule().context.cut);assertEquals(f.plan.summary(),store.summary());
                    assertFalse(Files.exists(f.scratch));assertEquals(directory,key(f.destination()));
                    for(var file:keys.entrySet())assertEquals(file.getValue(),key(f.destination().resolve(file.getKey())));
                    assertEquals(Set.of("root.gsr","node.gsr","replica.lock","learner-admission.gslp","learner"),MembershipBasisSources.children(f.replica(),5));
                    assertEquals(1,f.source.client.usage().counts().get(MembershipResources.Unit.LEARNER));
                    assertFalse(f.source.client.usage().counts().containsKey(MembershipResources.Unit.SOURCE));
                    assertEquals(original,V53ReplayFilesTest.files(f.source.path));
                    assertTrue(events.indexOf("LEARNER_SOURCE_DIRECTORY_FORCED")<events.indexOf("LEARNER_RETENTION_ACTIVE_PARENT_FORCED"));
                    assertTrue(events.indexOf("LEARNER_RETENTION_ACTIVE_PARENT_FORCED")<events.indexOf("LEARNER_REPLICA_CREATED"));
                }
                var retained=V53ReplayFilesTest.files(f.replica());assertEquals(0,f.source.client.usage().leases());
                for(int repeat=0;repeat<2;repeat++)try(var store=f.resume(e->{})) {
                    assertEquals(cut,store.capsule().context.cut);assertEquals(retained,V53ReplayFilesTest.files(f.replica()));
                }
            }
        }
    }
    @Test void everyRetentionAndInstallationCutResumesOnlyCompleteOriginalDecisions()throws Exception {
        var points=new ArrayList<String>();
        try(var f=new Fixture();var store=f.install(points::add)){store.summary();}
        points.removeIf(p->p.startsWith("LEARNER_SOURCE_MEMBER") || p.equals("LEARNER_SOURCE_METADATA_RESERVED") || p.equals("LEARNER_SOURCE_DIRECTORY_FORCED"));
        points.removeIf(V53LearnerAdmissionPlanTest.CUTS::contains);
        assertEquals(points.size(),new HashSet<>(points).size());assertTrue(points.contains("LEARNER_SOURCE_MOVED"));
        for(String point:points)try(var f=new Fixture()) {
            var hit=new AtomicBoolean();
            assertThrows(IOException.class,()->f.install(e->{if(e.equals(point)){hit.set(true);throw new IOException("cut "+point);}}),point);
            assertTrue(hit.get(),point);f.disconnect();assertEquals(0,f.source.client.usage().leases());
            var before=V53ReplayFilesTest.files(f.source.request.operationDirectory());
            if(Set.of("LEARNER_RETENTION_CREATED","LEARNER_RETENTION_PREFIX_WRITTEN").contains(point)) {
                assertThrows(Exception.class,()->f.resume(e->{}),point);assertEquals(before,V53ReplayFilesTest.files(f.operation()));
                assertFalse(Files.exists(f.replica()));assertTrue(Files.isDirectory(f.scratch));
            }else try(var store=f.resume(e->{})) {
                assertEquals(f.plan.summary(),store.summary());assertFalse(Files.exists(f.scratch));assertTrue(Files.isDirectory(f.destination()));
            }
        }
    }
    @Test void sourceCompletionFailureRemainsScratchAndCannotMintAStore()throws Exception {
        for(String point:List.of("LEARNER_SOURCE_METADATA_RESERVED","LEARNER_SOURCE_MEMBER_CREATED","LEARNER_SOURCE_MEMBER_PREFIX_WRITTEN",
                "LEARNER_SOURCE_MEMBER_WRITTEN","LEARNER_SOURCE_MEMBER_FORCED","LEARNER_SOURCE_DIRECTORY_FORCED"))try(var f=new Fixture()) {
            var hit=new AtomicBoolean();assertThrows(IOException.class,()->f.install(e->{if(e.equals(point)){hit.set(true);throw new IOException(point);}}));
            assertTrue(hit.get());assertFalse(Files.exists(f.replica()));assertFalse(Files.exists(f.operation().resolve(RETAIN)));
            f.disconnect();assertFalse(Files.exists(f.scratch));assertEquals(0,f.source.client.usage().leases());
            assertThrows(Exception.class,()->f.resume(e->{}));
        }
    }
    @Test void liveOwnershipAndFileReplacementRefuseWithoutTakingOtherOwners()throws Exception {
        try(var f=new Fixture();var store=f.install(e->{})) {
            var separate=new MembershipResources(512*MembershipResources.MIB);
            assertThrows(ReplicationException.class,()->MembershipLearnerStore.resume(f.plan.summary(),separate,e->{}));
            assertEquals(0,separate.usage().leases());store.summary();
            Path file=f.destination().resolve("source.gscp"),saved=f.source.path.resolveSibling("original.gscp");
            Files.move(file,saved);Files.copy(saved,file);assertThrows(IllegalArgumentException.class,store::summary);
            assertArrayEquals(Files.readAllBytes(saved),Files.readAllBytes(file));
        }
    }
    @Test void changedRetainedFilesAndDuplicateLocationsRefuseAndPreserveAllBytes()throws Exception {
        for(String mode:List.of("duplicate","missing","extra","inode","partial","hardlink","symlink","decision"))try(var f=new Fixture()) {
            try(var store=f.install(e->{})){store.summary();}f.disconnect();
            Path source=f.destination().resolve("source.gscp");
            switch(mode) {
                case "duplicate" -> V53JournalApplicationTest.copy(f.destination(),f.scratch);
                case "missing" -> Files.move(f.destination(),f.replica().resolveSibling("original-source"));
                case "extra" -> Files.write(f.destination().resolve("foreign"),new byte[]{9});
                case "inode" -> {Files.move(source,source.resolveSibling("held"));Files.copy(source.resolveSibling("held"),source);Files.move(source.resolveSibling("held"),f.replica().resolveSibling("original-source"));}
                case "partial" -> Files.write(source,Arrays.copyOf(Files.readAllBytes(source),100));
                case "hardlink" -> Files.createLink(f.replica().resolveSibling("source-link"),source);
                case "symlink" -> {Path old=f.replica().resolveSibling("original-source");Files.move(source,old);Files.createSymbolicLink(source,old);}
                case "decision" -> Files.write(f.operation().resolve(RETAIN),new byte[]{1});
                default -> throw new AssertionError(mode);
            }
            // The physical checker deliberately rejects links; preserve exact bytes
            // for ordinary files and separately assert that the foreign link survives.
            var before=mode.equals("symlink")||mode.equals("hardlink")?null:V53ReplayFilesTest.files(f.replica());
            assertThrows(Exception.class,()->f.resume(e->{}),mode);assertEquals(0,f.source.client.usage().leases());
            if(before!=null)assertEquals(before,V53ReplayFilesTest.files(f.replica()));
            if(mode.equals("symlink"))assertTrue(Files.isSymbolicLink(source));
            if(mode.equals("hardlink"))assertTrue(Files.isSameFile(source,f.replica().resolveSibling("source-link")));
        }
    }
    @Test void imageCapacityIsHandedOffWithoutASecondLearnerOrImageSlot()throws Exception {
        try(var f=new Fixture()) {
            var occupied=new ArrayList<MembershipResources.Lease>();
            try {
                int original=f.source.client.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0);
                for(int i=original;i<7;i++)occupied.add(f.source.client.reserve(MembershipResources.Unit.APPLICATION,"occupied-"+i,1024));
                try(var store=f.install(e->{})) {
                    f.disconnect();store.summary();assertEquals(7,f.source.client.usage().counts().get(MembershipResources.Unit.APPLICATION));
                    assertEquals(1,f.source.client.usage().counts().get(MembershipResources.Unit.LEARNER));
                }
            }finally{occupied.forEach(MembershipResources.Lease::close);}
            assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void foreignOriginalRefusalDoesNotFirstRemoveRedundantDecisions()throws Exception {
        for(String mode:List.of("source","replica"))try(var f=new Fixture()) {
            try(var store=f.install(e->{})){store.summary();}f.disconnect();
            Files.copy(f.operation().resolve(FILE),f.operation().resolve(NEXT));
            Files.copy(f.operation().resolve(RETAIN),f.operation().resolve(RETAIN_NEXT));
            if(mode.equals("source"))Files.write(f.destination().resolve("foreign"),new byte[]{3});
            else Files.write(f.replica().resolve("foreign"),new byte[]{4});
            var before=V53ReplayFilesTest.files(f.operation());var replica=V53ReplayFilesTest.files(f.replica());
            assertThrows(Exception.class,()->f.resume(e->{}));
            assertEquals(before,V53ReplayFilesTest.files(f.operation()));assertEquals(replica,V53ReplayFilesTest.files(f.replica()));
            assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void resumeCapacityFailurePreservesTheCompleteOriginalAndReleasesPartialReservations()throws Exception {
        try(var f=new Fixture()) {
            try(var store=f.install(e->{})){store.summary();}f.disconnect();var before=V53ReplayFilesTest.files(f.replica());
            var limited=new MembershipResources(1);
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerStore.resume(f.plan.summary(),limited,e->{}));
            assertEquals(0,limited.usage().leases());assertEquals(before,V53ReplayFilesTest.files(f.replica()));
            try(var store=f.resume(e->{})){store.summary();}
        }
    }
    @Test void admissionMetadataGrowthPreservesProtectedHeadroomAndUnitLimits() {
        var r=new MembershipResources(MembershipResources.HEADROOM+1024,1024,1024);
        try(var data=r.reserve(MembershipResources.Unit.LEARNER,"data",1024);var misc=r.reserve(MembershipResources.Unit.MISC,"plan",64)) {
            misc.reserveMisc(MembershipResources.Unit.MISC.bytes);assertEquals(1024+MembershipResources.Unit.MISC.bytes,r.usage().metadata());
            assertThrows(IllegalArgumentException.class,()->misc.reserveMisc(MembershipResources.Unit.MISC.bytes+1));
            assertThrows(IllegalArgumentException.class,()->data.reserveStorage(1025));assertEquals(1024,r.usage().staging());
        }
        assertEquals(0,r.usage().metadata());assertEquals(0,r.usage().leases());
    }
    @Test void onlyCompletedAdmissionCanOutliveItsOriginalStagingParent()throws Exception {
        for(boolean complete:List.of(false,true))try(var f=new Fixture()) {
            if(complete)try(var store=f.install(e->{})){store.summary();}
            else assertThrows(IOException.class,()->f.install(e->{if(e.equals("LEARNER_SOURCE_MOVED"))throw new IOException("moved before force");}));
            f.disconnect();Files.delete(f.scratch.getParent());var before=V53ReplayFilesTest.files(f.replica());
            if(complete)try(var store=f.resume(e->{})){store.summary();}
            else assertThrows(Exception.class,()->f.resume(e->{}));
            assertEquals(before,V53ReplayFilesTest.files(f.replica()));
        }
    }
    @Test void replacedStagingParentNeverReceivesARecoveryForce()throws Exception {
        try(var f=new Fixture()) {
            try(var store=f.install(e->{})){store.summary();}f.disconnect();
            Path parent=f.scratch.getParent();Files.move(parent,parent.resolveSibling("original-parent"));Files.createDirectory(parent);
            Files.copy(f.operation().resolve(RETAIN),f.operation().resolve(RETAIN_NEXT));var before=V53ReplayFilesTest.files(f.operation());
            assertThrows(Exception.class,()->f.resume(e->{}));assertEquals(before,V53ReplayFilesTest.files(f.operation()));
        }
    }
    @Test void completedLearnerStoreCannotBeOpenedAsAnOrdinaryVoter()throws Exception {
        try(var f=new Fixture()) {
            try(var store=f.install(e->{})){store.summary();}f.disconnect();
            var before=V53ReplayFilesTest.files(f.replica());
            assertThrows(Exception.class,()->MembershipGrantJournal.openGenerations(f.replica(),f.plan.request.root(),f.plan.request.identity(),
                    f.source.client,f.source.fixture::verify,e->{}));
            assertEquals(before,V53ReplayFilesTest.files(f.replica()));assertEquals(0,f.source.client.usage().leases());
        }
    }
    @Test void repeatedCompleteWritesMustBeForcedAgainBeforeRetention()throws Exception {
        for(String point:List.of("LEARNER_SOURCE_MEMBER_WRITTEN","LEARNER_SOURCE_DIRECTORY_FORCED"))try(var f=new Fixture()) {
            assertThrows(IOException.class,()->f.prefix.completeLearnerSource(f.original,e->{if(e.equals(point))throw new IOException("complete bytes before durable return");}));
            var events=new ArrayList<String>();
            try(var store=f.install(events::add)) {
                store.summary();long metadata=f.original.fileNames().stream().filter(n->!n.equals("source.gscp")&&!n.endsWith(".image")).count();
                assertEquals(metadata,events.stream().filter("LEARNER_SOURCE_MEMBER_FORCED"::equals).count());
                assertTrue(events.indexOf("LEARNER_SOURCE_MEMBER_FORCED")<events.indexOf("LEARNER_SOURCE_DIRECTORY_FORCED"));
            }
        }
    }
}
