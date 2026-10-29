package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real deletion and exception/cold reopen. Not a halt/SIGKILL qualification. */
class V53LearnerJoinedRetirementTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo info){System.out.println("v53JoinedRetirementCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerJoinedAdmissionTest helper(){var h=new V53LearnerJoinedAdmissionTest();h.temp=temp;return h;}
    MembershipLearnerJoinedRetirement recover(V53LearnerCancellationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipLearnerJoinedRetirement.recover(f.local.summary,f.local.source.client,f.local.captured,f.local.config,cut);
    }
    @Test void deletesOnlyDerivedPredecessorsKeepsLocksProofsAndFullChargesAcrossColdOpen()throws Exception {
        var h=helper();try(var f=h.fixture()) {
            MembershipResources.Usage usage;MembershipLearnerJoinedOriginal.Inspection before;int deleted;
            try(var placement=h.place(f)) {
                var joined=h.join(placement,f,e->{});usage=f.local.source.client.usage();before=MembershipLearnerJoinedOriginal.verify(joined,f.local.captured,f.local.config);
                var derived=new MembershipLearnerJoinedRetirementPlan(f.local.summary);
                var preserved=new LinkedHashMap<Path,Object>();for(Path lock:derived.locks)preserved.put(lock,MembershipBasisSources.key(lock));
                try(var retired=MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{})) {
                    deleted=retired.deleted();assertEquals(derived.deletions.size(),deleted);assertTrue(deleted>10);
                    assertEquals(usage,f.local.source.client.usage());
                    for(var entry:derived.deletions)assertFalse(Files.exists(derived.path(entry)));
                    for(var lock:preserved.entrySet())assertEquals(lock.getValue(),MembershipBasisSources.key(lock.getKey()));
                    assertTrue(Files.exists(f.local.typed().resolve(MembershipLearnerMaterialization.PLAN)));
                    assertTrue(Files.exists(f.local.typed().resolve(MembershipLearnerMaterialization.RECEIPT)));
                    assertEquals(before,MembershipLearnerJoinedOriginal.verifyRetirement(retired,f.local.captured,f.local.config));
                    new V53MembershipOwnershipTest().probe(f.local.config.replicaDirectory().resolve("replica.lock"));
                    f.local.store.close();f.typed.close();retired.check();
                }
            }
            assertEquals(0,f.local.source.client.usage().leases());
            var original=MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null);
            try(var retired=recover(f,e->{})) {
                assertEquals(deleted,retired.deleted());assertEquals(usage,f.local.source.client.usage());
                assertEquals(before,MembershipLearnerJoinedOriginal.verifyRetirement(retired,f.local.captured,f.local.config));
                assertThrows(Exception.class,()->h.recover(f,e->fail("ordinary placement must not recreate retired originals")));
                new V53MembershipOwnershipTest().probe(f.local.config.replicaDirectory().resolve("replica.lock"));
            }
            assertEquals(original,MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null));assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void interruptedOriginalDecisionResumesLiveAndDeletionResumesColdWithoutRecreatingFiles()throws Exception {
        var h=helper();try(var f=h.fixture()) {
            try(var placement=h.place(f)) {var joined=h.join(placement,f,e->{});var custody=placement.custody();var usage=f.local.source.client.usage();
            var hit=new AtomicBoolean();assertThrows(IOException.class,()->MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{
                if(e.equals("JOINED_RETIREMENT_CREATED:retirement.json")){hit.set(true);throw new IOException(e);}}));assertTrue(hit.get());
            Path record=MembershipLearnerJoinedRetirement.directory(f.local.summary).resolve(MembershipLearnerJoinedRetirement.PLAN);Object inode=MembershipBasisSources.key(record);
            for(String event:List.of("JOINED_RETIREMENT_PREFIX_WRITTEN:retirement.json","JOINED_RETIREMENT_WRITTEN:retirement.json","JOINED_RETIREMENT_DECISION_FORCED","JOINED_RETIREMENT_DELETED:0")) {
                hit.set(false);assertThrows(IOException.class,()->MembershipLearnerJoinedRetirement.resume(custody,e->{if(e.equals(event)){hit.set(true);throw new IOException(e);}}));
                assertTrue(hit.get(),event);assertEquals(usage,f.local.source.client.usage());assertEquals(inode,MembershipBasisSources.key(record));
            }
            placement.close();assertEquals(0,f.local.source.client.usage().leases());
            for(String event:List.of("JOINED_RETIREMENT_RECOVERY_VERIFIED","JOINED_RETIREMENT_DELETE_FORCED:1","JOINED_RETIREMENT_PREFIX_WRITTEN:retired.json","JOINED_RETIREMENT_FORCED:retired.json")) {
                hit.set(false);assertThrows(IOException.class,()->recover(f,e->{if(e.equals(event)){hit.set(true);throw new IOException(e);}}));
                assertTrue(hit.get(),event);assertEquals(0,f.local.source.client.usage().leases());assertEquals(inode,MembershipBasisSources.key(record));
            }
            try(var retired=recover(f,e->{})){retired.check();assertEquals(usage,f.local.source.client.usage());}
            }
        }
    }
    @Test void missingTornCopiedDecisionAndNonprefixDeletionRefuseBeforeAnyMutation()throws Exception {
        var h=helper();try(var f=h.fixture()) {
            try(var placement=h.place(f)) {
                var joined=h.join(placement,f,e->{});var hit=new AtomicBoolean();
                assertThrows(IOException.class,()->MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{if(e.equals("JOINED_RETIREMENT_DECISION_FORCED")){hit.set(true);throw new IOException(e);}}));assertTrue(hit.get());
            }
            Path file=MembershipLearnerJoinedRetirement.directory(f.local.summary).resolve(MembershipLearnerJoinedRetirement.PLAN),saved=temp.resolve("saved-decision");
            byte[] bytes=Files.readAllBytes(file);var before=MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null);
            Files.move(file,saved);
            try {
                assertThrows(Exception.class,()->recover(f,e->fail("missing decision")));assertFalse(Files.exists(file));
                Files.copy(saved,file);assertThrows(Exception.class,()->recover(f,e->fail("copied decision")));Files.delete(file);
            }finally{Files.move(saved,file);}
            for(byte[] torn:List.of(new byte[0],Arrays.copyOf(bytes,bytes.length/2))) {
                try {Files.write(file,torn);assertThrows(Exception.class,()->recover(f,e->fail("torn decision")));assertArrayEquals(torn,Files.readAllBytes(file));}
                finally{Files.write(file,bytes);}
            }
            var plan=new MembershipLearnerJoinedRetirementPlan(f.local.summary);Path second=plan.path(plan.deletions.get(1)),unavailable=temp.resolve("missing-nonprefix");
            Files.move(second,unavailable);
            try {assertThrows(Exception.class,()->recover(f,e->fail("nonprefix deletion")));assertFalse(Files.exists(second));}
            finally{Files.move(unavailable,second);}
            var modified=new TreeMap<>(object(parse(bytes,MembershipLearnerJoinedRetirement.MAXIMUM)));modified.put("deletions",List.of());
            try {Files.write(file,canonical(modified,MembershipLearnerJoinedRetirement.MAXIMUM));assertThrows(Exception.class,()->recover(f,e->fail("caller deletion list")));}
            finally{Files.write(file,bytes);}
            assertEquals(before,MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null));assertEquals(0,f.local.source.client.usage().leases());
            try(var retired=recover(f,e->{})){retired.check();}
        }
    }
    @Test void coldOriginalReservationUnderchargeAndCopiedCompletionAreRejected()throws Exception {
        var h=helper();try(var f=h.fixture()) {
            try(var placement=h.place(f)){var joined=h.join(placement,f,e->{});try(var retired=MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{})){retired.check();}}
            Path directory=MembershipLearnerJoinedRetirement.directory(f.local.summary),plan=directory.resolve(MembershipLearnerJoinedRetirement.PLAN),done=directory.resolve(MembershipLearnerJoinedRetirement.DONE);
            byte[] bytes=Files.readAllBytes(plan);var value=object(V53ContextFixture.mutable(parse(bytes,MembershipLearnerJoinedRetirement.MAXIMUM)));
            for(Object raw:list(value.get("reservations")))object(raw).put("bytes",1L);
            try {Files.write(plan,canonical(value,MembershipLearnerJoinedRetirement.MAXIMUM));assertThrows(Exception.class,()->recover(f,e->fail("undercharged decision")));}
            finally{Files.write(plan,bytes);}
            Path saved=temp.resolve("original-completion");Files.move(done,saved);Files.copy(saved,done);
            try{assertThrows(Exception.class,()->recover(f,e->fail("copied completion")));}finally{Files.delete(done);Files.move(saved,done);}
            assertEquals(0,f.local.source.client.usage().leases());try(var retired=recover(f,e->{})){retired.check();}
        }
    }
    @Test void promotedCompletedReplacementRetiresItsOldPayloadsAndKeepsSelectedTypedProof()throws Exception {
        var h=helper();var fixture=new V53LearnerIntentTest();fixture.temp=temp;
        try(var f=fixture.fixture("COMPLETED",3,"REPLACE",true)) {
            MembershipResources.Usage usage;
            try(var placement=h.place(f)) {
                var joined=h.join(placement,f,e->{});usage=f.local.source.client.usage();
                try(var retired=MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{})) {
                    retired.check();assertEquals(usage,f.local.source.client.usage());
                    assertFalse(Files.exists(f.local.typed().resolve(MembershipLearnerMaterialization.RECEIPT)));
                    assertTrue(Files.exists(MembershipLearnerSuccessor.typedDirectory(f.local.summary).resolve(MembershipLearnerMaterialization.RECEIPT)));
                }
            }
            try(var retired=recover(f,e->{})) {
                retired.check();assertEquals(usage,f.local.source.client.usage());
                for(Path lock:new MembershipLearnerJoinedRetirementPlan(f.local.summary).locks)
                    assertThrows(Exception.class,()->{try(var ignored=MembershipOwnership.own(lock,false)){fail("all original authority locks remain held");}});
            }
            assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void changedOriginalAtLastPredeleteBoundaryStopsWithoutDeletingIt()throws Exception {
        var h=helper();try(var f=h.fixture();var placement=h.place(f)) {
            var joined=h.join(placement,f,e->{});var original=new MembershipLearnerJoinedRetirementPlan(f.local.summary);Path first=original.path(original.deletions.get(0));
            assertTrue(Files.isRegularFile(first));var hit=new AtomicBoolean();
            assertThrows(Exception.class,()->MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,e->{
                if(e.equals("JOINED_RETIREMENT_BEFORE_DELETE:0")){hit.set(true);Files.writeString(first,"changed");}}));
            assertTrue(hit.get());assertEquals("changed",Files.readString(first));
        }
    }
}
