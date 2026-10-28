package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipLearnerAdmissionFiles.*;

/** Conditional source history, real forced plan bytes and exclusive disk owner.
 * Full native history and fresh-JVM interruptions are qualified separately. */
class V53LearnerAdmissionPlanTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("LEARNER_OPERATION_CREATED","LEARNER_OPERATION_LOCKED","LEARNER_PLAN_CREATED",
            "LEARNER_PLAN_PREFIX_WRITTEN","LEARNER_PLAN_WRITTEN","LEARNER_PLAN_FORCED","LEARNER_PLAN_PARENT_FORCED",
            "LEARNER_RESEAL_PLAN_FORCED","LEARNER_RESEAL_PLAN_PARENT_FORCED","LEARNER_PLAN_RENAMED",
            "LEARNER_ACTIVE_PLAN_FORCED","LEARNER_ACTIVE_PLAN_PARENT_FORCED","LEARNER_PLAN_BEFORE_RETURN");
    final class Fixture implements AutoCloseable {
        final V53LearnerSourceTest.Fixture source;
        final MembershipLearnerAdmissionPlan plan;
        final MembershipResources resources=new MembershipResources(512*MembershipResources.MIB);
        Fixture(int size,String kind,int index)throws Exception {
            var helper=new V53LearnerSourceTest();helper.temp=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));
            source=helper.new Fixture(size,kind,index);plan=MembershipLearnerAdmissionPlan.create(source.request,source.owner.floorCopyCurrent());
        }
        Fixture()throws Exception{this(3,"ADD",2);}
        MembershipLearnerAdmissionFiles create(MembershipBallotAllocator.Cut cut)throws IOException {
            return MembershipLearnerAdmissionFiles.create(plan,resources,cut,()->plan.checkOriginal(source.owner.floorCopyCurrent()));
        }
        MembershipLearnerAdmissionFiles open()throws IOException{return MembershipLearnerAdmissionFiles.open(plan.summary(),resources,e->{});}
        Path directory(){return plan.request.operationDirectory();}
        @Override public void close()throws Exception{source.close();assertEquals(0,resources.usage().leases());}
    }
    @Test void exactPlansForAllPreJointAddAndReplaceShapes()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            for(int index:List.of(2,3,4,5))try(var f=new Fixture(size,kind,index)) {
                var decoded=MembershipLearnerAdmissionPlan.decode(f.plan.bytes());assertEquals(f.plan.summary(),decoded.summary());
                decoded.checkOriginal(f.source.owner.floorCopyCurrent());assertFalse(Files.exists(f.directory()));
                assertFalse(Files.exists(f.plan.request.replicaDirectory()));
                byte[] bytes=decoded.bytes();bytes[0]^=1;assertArrayEquals(f.plan.bytes(),decoded.bytes());
            }
        }
    }
    @Test void malformedOrSubstitutedMetadataFailsClosed()throws Exception {
        try(var f=new Fixture()) {
            byte[] original=f.plan.bytes();
            for(int index:List.of(0,5,7,9,11,15,16,original.length-1)) {
                byte[] bytes=original.clone();bytes[index]^=1;assertThrows(IllegalArgumentException.class,()->MembershipLearnerAdmissionPlan.decode(bytes));
            }
            for(String mode:List.of("extra","request","source","inventory","path","parent","root")) {
                var v=object(mutable(parse(Arrays.copyOfRange(original,HEADER,original.length),65536)));
                if(mode.equals("extra"))v.put("extra",true);
                if(mode.equals("request"))object(v.get("request")).put("root","0".repeat(64));
                if(mode.equals("source"))v.put("source",v.get("learner"));
                if(mode.equals("inventory"))list(v.get("files")).removeFirst();
                if(mode.equals("path"))object(list(v.get("paths")).getFirst()).put("path","../elsewhere");
                if(mode.equals("parent"))object(list(v.get("paths")).getFirst()).put("parentRealPath","/different");
                if(mode.equals("root"))v.put("root",MembershipBootstrapPlanData.base(f.plan.generation.bytes()));
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerAdmissionPlan.decode(MembershipLearnerAdmissionPlan.encode(v)),mode);
            }
        }
    }
    private static Object mutable(Object value) {
        if(value instanceof Map<?,?> map){var copy=new TreeMap<String,Object>();map.forEach((k,v)->copy.put((String)k,mutable(v)));return copy;}
        if(value instanceof List<?> list){var copy=new ArrayList<Object>();list.forEach(v->copy.add(mutable(v)));return copy;}
        return value;
    }
    @Test void forcedPlanReopensWithoutAnyReplicaOrVotingState()throws Exception {
        try(var f=new Fixture()) {
            var points=new ArrayList<String>();try(var files=f.create(points::add)) {
                assertEquals(f.plan.summary(),files.summary());assertEquals(1,f.resources.usage().counts().get(MembershipResources.Unit.MISC));
                assertFalse(f.resources.usage().counts().containsKey(MembershipResources.Unit.LEARNER));
                assertThrows(ReplicationException.class,f::open);assertEquals(f.plan.summary(),files.summary());
            }
            assertEquals(CUTS,points);var before=V53ReplayFilesTest.files(f.directory());
            for(int i=0;i<2;i++)try(var files=f.open()){assertEquals(f.plan.summary(),files.summary());assertArrayEquals(f.plan.bytes(),files.retained().bytes());}
            assertEquals(before,V53ReplayFilesTest.files(f.directory()));assertFalse(Files.exists(f.plan.request.replicaDirectory()));
            assertEquals(Set.of(LOCK,FILE),before.keySet());
        }
    }
    @Test void everyInterruptionPreservesOriginalAndOnlyCompletePlansResume()throws Exception {
        for(int index=0;index<CUTS.size();index++)try(var f=new Fixture()) {
            String target=CUTS.get(index);var reached=new AtomicBoolean();
            assertThrows(IOException.class,()->f.create(cut->{if(cut.equals(target)){reached.set(true);throw new IOException(target);}}));assertTrue(reached.get());
            var before=V53ReplayFilesTest.files(f.directory());
            if(index<4) {
                assertThrows(Exception.class,f::open);assertEquals(before,V53ReplayFilesTest.files(f.directory()));
            }else try(var files=f.open()){assertEquals(f.plan.summary(),files.summary());assertArrayEquals(f.plan.bytes(),Files.readAllBytes(f.directory().resolve(FILE)));}
            assertFalse(Files.exists(f.plan.request.replicaDirectory()));
        }
    }
    @Test void exactRedundantCandidateCanBeRemovedButNotUsedToRepairActiveBytes()throws Exception {
        for(boolean corrupt:List.of(false,true))try(var f=new Fixture()) {
            try(var files=f.create(e->{})){files.summary();}
            Files.write(f.directory().resolve(NEXT),f.plan.bytes());
            if(corrupt)Files.write(f.directory().resolve(FILE),new byte[]{0});
            var before=V53ReplayFilesTest.files(f.directory());
            if(corrupt){assertThrows(IllegalArgumentException.class,f::open);assertEquals(before,V53ReplayFilesTest.files(f.directory()));}
            else try(var files=f.open()){files.summary();assertFalse(Files.exists(f.directory().resolve(NEXT)));}
        }
    }
    @Test void wrongSummaryForeignFilesLinksAndOccupiedReplicaArePreserved()throws Exception {
        for(String mode:List.of("summary","extra","symlink","hardlink","replica"))try(var f=new Fixture()) {
            try(var files=f.create(e->{})){files.summary();}
            if(mode.equals("extra"))Files.write(f.directory().resolve("foreign"),new byte[]{9});
            if(mode.equals("symlink")) {Files.move(f.directory().resolve(FILE),f.directory().resolveSibling("original.gslp"));Files.createSymbolicLink(f.directory().resolve(FILE),f.directory().resolveSibling("original.gslp"));}
            if(mode.equals("hardlink"))Files.createLink(f.directory().resolveSibling("hardlink.gslp"),f.directory().resolve(FILE));
            if(mode.equals("replica"))Files.createDirectory(f.plan.request.replicaDirectory());
            if(mode.equals("summary"))assertThrows(IllegalArgumentException.class,()->MembershipLearnerAdmissionFiles.open(
                    new MembershipLearnerPlan("0".repeat(64),f.plan.request),f.resources,e->{}));
            else assertThrows(Exception.class,f::open,mode);
            assertTrue(Files.exists(f.directory().resolve(FILE),LinkOption.NOFOLLOW_LINKS));
            if(mode.equals("extra"))assertArrayEquals(new byte[]{9},Files.readAllBytes(f.directory().resolve("foreign")));
        }
    }
    @Test void exhaustedMetadataRefusesBeforeAnyWrite()throws Exception {
        try(var f=new Fixture();var occupied=f.resources.reserve(MembershipResources.Unit.MISC,"other",4096)) {
            assertThrows(IllegalArgumentException.class,()->f.create(e->{}));assertFalse(Files.exists(f.directory()));
        }
    }
    @Test void sourceInvalidationBeforePlanReturnPreservesBytesAndReleasesLock()throws Exception {
        try(var f=new Fixture()) {
            var valid=new AtomicBoolean(true);
            assertThrows(IOException.class,()->MembershipLearnerAdmissionFiles.create(f.plan,f.resources,
                    e->{if(e.equals("LEARNER_PLAN_FORCED"))valid.set(false);},()->{if(!valid.get())throw new IOException("source expired");}));
            assertEquals(0,f.resources.usage().leases());assertFalse(Files.exists(f.directory().resolve(FILE)));
            // Opening only reseals the retained plan; it grants no source/capsule authority.
            try(var files=f.open()){assertEquals(f.plan.summary(),files.summary());}
        }
    }
    @Test void receiveScratchCannotCreateOrOverlapAuthorityBeforeThePlan()throws Exception {
        try(var f=new Fixture()) {
            for(Path scratch:List.of(f.plan.request.operationDirectory(),f.plan.request.replicaDirectory(),f.plan.request.replicaDirectory().resolve("nested"))) {
                try(var source=new MembershipLearnerSource(f.plan.request,f.plan.source,f.resources,ReplicationBounds.defaults(),
                        MembershipTransport.Events.NONE,()->{},System::nanoTime,System.nanoTime(),java.util.concurrent.TimeUnit.SECONDS.toNanos(30))) {
                    assertThrows(ReplicationException.class,()->source.fetch(scratch));
                }
                assertFalse(Files.exists(f.directory()));assertFalse(Files.exists(f.plan.request.replicaDirectory()));
            }
        }
    }
    @Test void sameBytesOnAReplacementInodeDoNotRemainTheOriginalOwnedPlan()throws Exception {
        try(var f=new Fixture();var files=f.create(e->{})) {
            Path original=f.directory().resolve(FILE),held=f.directory().resolveSibling("retained-original.gslp");
            Files.move(original,held);Files.write(original,f.plan.bytes());
            assertThrows(IllegalArgumentException.class,files::summary);
            assertArrayEquals(f.plan.bytes(),Files.readAllBytes(held));assertArrayEquals(f.plan.bytes(),Files.readAllBytes(original));
        }
    }
}
