package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.Unit;

/** Actual pending/published TCP acquisition and native ownership. Old-voter
 * certificates are conditional fixtures; injected IO cuts are not SIGKILL. */
class V53PendingJoinedCustodyTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo info){System.out.println("v53PendingJoinedCase="+info.getDisplayName());}
    V53PendingPublishedProgressTest.Fixture fixture(int through)throws Exception {
        var helper=new V53PendingPublishedProgressTest();helper.temp=temp;return helper.new Fixture(through);
    }
    MembershipLearnerIntent retain(V53PendingPublishedProgressTest.Fixture f)throws Exception {
        try(var progress=f.progress(MembershipTransport.Events.NONE)){progress.fetch(f.scratch());return progress.retainPublishedIntent(e->{});}
    }
    MembershipLearnerPlacement recover(V53PendingPublishedProgressTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        var local=f.f.f.local;return MembershipLearnerPlacement.recover(local.summary,local.source.client,local.captured,local.config,cut);
    }
    MembershipLearnerJoinedRetirement recoverRetired(V53PendingPublishedProgressTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        var local=f.f.f.local;return MembershipLearnerJoinedRetirement.recover(local.summary,local.source.client,local.captured,local.config,cut);
    }
    @ParameterizedTest @ValueSource(ints={6,7})
    void linkedOriginalsReachNativeJournalAndColdReopenWithoutLosingChargesOrLocks(int through)throws Exception {
        try(var f=fixture(through)) {
            var local=f.f.f.local;var resources=local.source.client;
            Path pending=f.f.directory(),root=local.config.replicaDirectory().resolve("replica.lock");
            var original=V53ReplayFilesTest.files(pending);long counter;Decoded grant;
            try(var intent=retain(f);var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                    var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
                var decision=object(parse(Files.readAllBytes(MembershipLearnerCustody.directory(local.summary).resolve(MembershipLearnerCustody.FILE)),MembershipLearnerCustody.MAXIMUM));
                assertEquals(10,list(decision.get("roots")).size());assertTrue(decision.containsKey("pendingSource"));
                MembershipLearnerPendingLink.inventory(local.summary,object(decision.get("pendingSource")),list(decision.get("roots")),(String)decision.get("receipt"));
                var usage=resources.usage();assertEquals(2,usage.counts().get(Unit.GENERATION));assertEquals(1,usage.counts().get(Unit.SOURCE));
                assertEquals(1,usage.counts().get(Unit.JOURNAL));assertEquals(1,usage.counts().get(Unit.LEARNER));
                assertTrue(usage.counts().get(Unit.APPLICATION)<=7);assertEquals(original,V53ReplayFilesTest.files(pending));
                f.pending.close();intent.close();stage.close();local.store.close();assertEquals(usage,resources.usage());
                new V53MembershipOwnershipTest().probe(root);
                try(var placement=MembershipLearnerPlacement.install(custody,e->{})) {
                    var joined=MembershipLearnerJoinedAdmission.install(placement,local.captured,local.config,e->{});
                    MembershipLearnerJoinedOriginal.verify(joined,local.captured,local.config);
                    assertEquals(original,V53ReplayFilesTest.files(pending));
                    try(var retired=MembershipLearnerJoinedRetirement.retire(joined,local.captured,local.config,e->{})) {
                        assertEquals(usage,resources.usage());assertTrue(Files.isDirectory(pending));
                        try(var children=Files.list(pending)){assertEquals(0,children.count());}
                        MembershipLearnerJoinedOriginal.verifyRetirement(retired,local.captured,local.config);
                        try(var nativeOwner=MembershipGrantJournal.openJoined(retired,local.captured,local.config,e->{})) {
                            assertFalse(resources.usage().counts().containsKey(Unit.SOURCE));assertFalse(resources.usage().counts().containsKey(Unit.LEARNER));
                            assertEquals(1,resources.usage().counts().get(Unit.GENERATION));assertEquals(1,resources.usage().counts().get(Unit.JOURNAL));
                            assertTrue(resources.usage().staging()<usage.staging());new V53MembershipOwnershipTest().probe(root);
                            counter=nativeOwner.reserveCounter();grant=nativeOwner.prepareCurrent(ballot(f,counter));assertEquals("BASIS",grant.kind());
                        }
                    }
                }
            }
            assertEquals(0,resources.usage().leases());
            try(var nativeOwner=MembershipGrantJournal.reopenJoined(local.summary,resources,local.captured,local.config,e->{})) {
                assertArrayEquals(grant.bytes(),nativeOwner.prepareCurrent(ballot(f,counter)).bytes());assertTrue(nativeOwner.reserveCounter()>counter);
                new V53MembershipOwnershipTest().probe(root);try(var children=Files.list(pending)){assertEquals(0,children.count());}
            }
            assertEquals(0,resources.usage().leases());
        }
    }
    Map<String,Object> ballot(V53PendingPublishedProgressTest.Fixture f,long counter) {
        var identity=f.f.f.local.config.localIdentity();return Map.of("counter",counter,"proposer",identity.nodeId().value(),"incarnation",identity.storageId().toString());
    }
    void interruptedPlacement(V53PendingPublishedProgressTest.Fixture f)throws Exception {
        var hit=new AtomicBoolean();
        try(var intent=retain(f);var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
            assertThrows(IOException.class,()->MembershipLearnerPlacement.install(custody,e->{
                if(e.equals("LEARNER_PLACEMENT_MOVED:generations")){hit.set(true);throw new IOException(e);}
            }));
        }
        assertTrue(hit.get());assertEquals(0,f.f.f.local.source.client.usage().leases());
    }
    @Test void coldPlacementBindsBothOriginalEndsAndRejectsMissingCopiedOrChangedPendingBeforeForce()throws Exception {
        try(var f=fixture(6)) {
            var local=f.f.f.local;interruptedPlacement(f);Path ack=f.f.directory().resolve(MembershipLearnerDisposition.PENDING_ACK),saved=temp.resolve("saved-ack");
            byte[] bytes=Files.readAllBytes(ack);var original=V53ReplayFilesTest.files(f.f.directory());
            Files.move(ack,saved);
            try {
                assertThrows(Exception.class,()->recover(f,e->fail("missing pending ACK must not force")));assertFalse(Files.exists(ack));
                Files.copy(saved,ack);assertThrows(Exception.class,()->recover(f,e->fail("copied pending ACK must not force")));Files.delete(ack);
            }finally{Files.move(saved,ack);}
            try {Files.writeString(ack,"changed");assertThrows(Exception.class,()->recover(f,e->fail("changed pending ACK must not force")));assertEquals("changed",Files.readString(ack));}
            finally{Files.write(ack,bytes);}
            Path custody=MembershipLearnerCustody.directory(local.summary).resolve(MembershipLearnerCustody.FILE);byte[] plan=Files.readAllBytes(custody);
            var unlinked=new TreeMap<>(object(parse(plan,MembershipLearnerCustody.MAXIMUM)));unlinked.remove("pendingSource");
            try {Files.write(custody,canonical(unlinked,MembershipLearnerCustody.MAXIMUM));assertThrows(Exception.class,()->recover(f,e->fail("missing original link must not force")));}
            finally{Files.write(custody,plan);}
            assertEquals(original,V53ReplayFilesTest.files(f.f.directory()));assertEquals(0,local.source.client.usage().leases());var verified=new AtomicBoolean();
            try(var placed=recover(f,e->{if(e.equals("LEARNER_PLACEMENT_RECOVERY_VERIFIED"))verified.set(true);else assertTrue(verified.get(),"originals first");})) {
                assertTrue(verified.get());placed.check();assertEquals(1,local.source.client.usage().counts().get(Unit.SOURCE));
                assertEquals(2,local.source.client.usage().counts().get(Unit.GENERATION));assertEquals(original,V53ReplayFilesTest.files(f.f.directory()));
                var joined=MembershipLearnerJoinedAdmission.install(placed,local.captured,local.config,e->{});
                MembershipLearnerJoinedOriginal.verify(joined,local.captured,local.config);
                new V53MembershipOwnershipTest().probe(local.config.replicaDirectory().resolve("replica.lock"));
            }
            assertEquals(0,local.source.client.usage().leases());
        }
    }
    @Test void pendingMutationAtLastReadBoundaryStopsColdCustodyBeforeAnyForce()throws Exception {
        try(var f=fixture(7)) {
            var local=f.f.f.local;interruptedPlacement(f);Path ack=f.f.directory().resolve(MembershipLearnerDisposition.PENDING_ACK);
            byte[] bytes=Files.readAllBytes(ack);var hit=new AtomicBoolean();int moved=MembershipLearnerPlacement.inspectOriginal(local.summary).moved();
            try {
                assertThrows(Exception.class,()->recover(f,e->{
                    assertEquals("LEARNER_PLACEMENT_RECOVERY_VERIFIED",e,"no force after pending mutation");hit.set(true);Files.writeString(ack,"changed-at-read-boundary");
                }));assertTrue(hit.get());assertEquals("changed-at-read-boundary",Files.readString(ack));assertEquals(0,local.source.client.usage().leases());
            }finally{Files.write(ack,bytes);}
            assertEquals(moved,MembershipLearnerPlacement.inspectOriginal(local.summary).moved());
            try(var placed=recover(f,e->{})){placed.check();assertEquals("PLACED",MembershipLearnerPlacement.inspectOriginal(local.summary).status());}
            assertEquals(0,local.source.client.usage().leases());
        }
    }
    @Test void interruptedPendingRetirementRestoresFullChargesAndNeverRecreatesDeletedPayloads()throws Exception {
        try(var f=fixture(6)) {
            var local=f.f.f.local;MembershipResources.Usage usage;Path deleted;
            try(var intent=retain(f);var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                    var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{});var placed=MembershipLearnerPlacement.install(custody,e->{})) {
                var joined=MembershipLearnerJoinedAdmission.install(placed,local.captured,local.config,e->{});usage=local.source.client.usage();
                var plan=new MembershipLearnerJoinedRetirementPlan(local.summary);int index=-1;
                for(int i=0;i<plan.deletions.size();i++)if(plan.deletions.get(i).get("root").equals(MembershipLearnerPendingLink.ROOT)){index=i;break;}
                assertTrue(index>=0);deleted=plan.path(plan.deletions.get(index));String cut="JOINED_RETIREMENT_DELETED:"+index;var hit=new AtomicBoolean();
                assertThrows(IOException.class,()->MembershipLearnerJoinedRetirement.retire(joined,local.captured,local.config,e->{if(e.equals(cut)){hit.set(true);throw new IOException(e);}}));
                assertTrue(hit.get());assertFalse(Files.exists(deleted));assertEquals(usage,local.source.client.usage());
            }
            assertEquals(0,local.source.client.usage().leases());
            Path record=MembershipLearnerJoinedRetirement.directory(local.summary).resolve(MembershipLearnerJoinedRetirement.PLAN);byte[] bytes=Files.readAllBytes(record);
            var plan=new MembershipLearnerJoinedRetirementPlan(local.summary);var original=object(parse(bytes,MembershipLearnerJoinedRetirement.MAXIMUM));
            plan.accounting(list(original.get("reservations")));
            for(String unit:List.of("SOURCE","JOURNAL")) {
                var changed=object(V53ContextFixture.mutable(original));var reservations=list(changed.get("reservations"));
                for(Object raw:reservations)if(object(raw).get("unit").equals(unit))object(raw).put("bytes",1L);
                assertThrows(IllegalArgumentException.class,()->plan.accounting(reservations));
                try {Files.write(record,canonical(changed,MembershipLearnerJoinedRetirement.MAXIMUM));assertThrows(Exception.class,()->recoverRetired(f,e->fail("undercharged pending originals")));}
                finally{Files.write(record,bytes);}
            }
            assertFalse(Files.exists(deleted));var verified=new AtomicBoolean();
            try(var retired=recoverRetired(f,e->{if(e.equals("JOINED_RETIREMENT_RECOVERY_VERIFIED"))verified.set(true);else assertTrue(verified.get());})) {
                assertTrue(verified.get());assertEquals(usage,local.source.client.usage());assertFalse(Files.exists(deleted));
                try(var children=Files.list(f.f.directory())){assertEquals(0,children.count());}
                MembershipLearnerJoinedOriginal.verifyRetirement(retired,local.captured,local.config);
                try(var nativeOwner=MembershipGrantJournal.openJoined(retired,local.captured,local.config,e->{})){assertTrue(nativeOwner.reserveCounter()>0);}
            }
            assertEquals(0,local.source.client.usage().leases());assertFalse(Files.exists(deleted));
        }
    }
    @Test void custodyDrainsActualPendingListenerAndValidatesLinkAgainstItsOriginalInventory()throws Exception {
        try(var f=fixture(6);var intent=retain(f);
                var endpoint=f.pending.listen(f.f.f.local.config.bounds(),MembershipTransport.Events.NONE,System::nanoTime,System.nanoTime(),V53PendingPublishedProgressTest.BUDGET)) {
            var local=f.f.f.local;assertFalse(endpoint.closed());assertTrue(local.source.client.usage().counts().containsKey(Unit.CONTROL));
            try(var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
                assertTrue(endpoint.closed());assertFalse(local.source.client.usage().counts().containsKey(Unit.CONTROL));
                var decision=object(parse(Files.readAllBytes(MembershipLearnerCustody.directory(local.summary).resolve(MembershipLearnerCustody.FILE)),MembershipLearnerCustody.MAXIMUM));
                var link=object(decision.get("pendingSource"));var roots=list(decision.get("roots"));String receipt=(String)decision.get("receipt");
                MembershipLearnerPendingLink.inventory(local.summary,link,roots,receipt);
                for(String field:List.of("ack","ackKey","marker","sourceKey","receipt")) {
                    var changed=new TreeMap<>(link);changed.put(field,Set.of("ack","marker","receipt").contains(field)?"f".repeat(64):"different-inode");
                    assertThrows(IllegalArgumentException.class,()->MembershipLearnerPendingLink.inventory(local.summary,changed,roots,receipt));
                }
                var missing=roots.stream().filter(v->!object(v).get("name").equals(MembershipLearnerPendingLink.ROOT)).toList();
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerPendingLink.inventory(local.summary,link,missing,receipt));
                custody.check();
            }
            assertEquals(0,local.source.client.usage().leases());
        }
    }
}
