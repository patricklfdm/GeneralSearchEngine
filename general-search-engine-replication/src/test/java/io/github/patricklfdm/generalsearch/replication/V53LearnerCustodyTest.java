package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Actual typed owners and TCP originals; historical checkpoint quorums remain
 * conditional. Custody transfer is not joined-voter admission or process replay. */
class V53LearnerCustodyTest {
    @TempDir Path temp;
    @BeforeEach void progress(TestInfo info){System.out.println("v53LearnerCustodyCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerCancellationTest.Fixture fixture(boolean promoted)throws Exception {
        var helper=new V53LearnerIntentTest();helper.temp=temp;return helper.fixture("JOINT",3,"ADD",promoted);
    }
    @Test void initialHeadTransfersEveryRealLockAndLeaseWithoutOldCloseReleasingThem()throws Exception {exercise(false);}
    @Test void promotedHeadTransfersCurrentAndRetainedOwnersWithoutThirdGeneration()throws Exception {exercise(true);}
    @Test void selectedSlotColdOwnerTransfersSeedAndTypedLocksWithoutRecreatingRetiredFiles()throws Exception {
        var helper=new V53LearnerSlotTest();helper.temp=temp;
        try(var f=helper.fixture(3,"ADD")) {
            MembershipLearnerSlot.View selected;
            try(var old=helper.current(f)) {
                var pending=helper.install(f,old.currentHead(),e->{});
                try(var next=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(pending,1),f.captured,f.config,e->{})) {
                    selected=next.promoteSlot(old.currentHead());
                }
            }
            selected.retirePredecessor();f.reopen();
            // Start the real TCP export only after the slot preparation/reopen.
            var network=new V53LearnerProgressNetworkTest();network.temp=temp;
            var history=V53CapsuleFixture.fromHistory(f.source.fixture.fixture.source,6);
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store.currentSource(),1),f.captured,f.config,e->{});
                    var peer=network.new Peer(history,true);
                    var server=new MembershipTransport(peer.owner,f.config.bounds(),peer.server,(sender,frame)->
                        frame.kind().equals("STATUS_PROBE")?MembershipDiscovery.answer(peer.owner.activationContext(),peer.owner.activationIdentity(),sender,frame):
                            peer.service.handle(sender,frame),MembershipTransport.Events.NONE)) {
                var head=typed.currentHead();MembershipLearnerIntent retained;
                try(var progress=new MembershipLearnerProgress(head,peer.owner.activationIdentity(),f.config.bounds(),MembershipTransport.Events.NONE,
                        System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60))) {
                    progress.fetch(f.base.resolve("slot-intent-source"));retained=progress.retainIntent(e->{});
                }
                try(var intent=retained;var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{})) {
                    var usage=f.source.client.usage();var originals=V53ReplayFilesTest.files(f.source.request.replicaDirectory());
                    Path seed=MembershipLearnerSuccessor.directory(f.summary),slot=MembershipLearnerSlot.directory(f.summary);
                    var locks=new Path[]{f.source.request.replicaDirectory().resolve("replica.lock"),seed.resolve(MembershipLearnerSuccessor.LOCK),
                            slot.resolve(MembershipLearnerSlot.LOCK),MembershipLearnerSlot.typedDirectory(f.summary).resolve("preparation.lock")};
                    try(var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
                        assertThrows(Exception.class,head::check);typed.close();f.store.close();intent.close();stage.close();custody.check();
                        assertEquals(usage,custody.usage());assertEquals(2,usage.counts().get(MembershipResources.Unit.GENERATION));
                        new V53MembershipOwnershipTest().probe(locks);assertEquals(originals,V53ReplayFilesTest.files(f.source.request.replicaDirectory()));
                        assertFalse(Files.exists(seed.resolve(MembershipLearnerSuccessor.SOURCE)));assertFalse(Files.exists(MembershipLearnerSuccessor.typedDirectory(f.summary)));
                    }
                    assertEquals(0,f.source.client.usage().leases());
                }
            }
        }
    }
    private void exercise(boolean promoted)throws Exception {
        try(var f=fixture(promoted);var intent=V53LearnerIntentTest.retain(f,e->{});
                var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{})) {
            var old=f.head;String receipt=old.receipt().digest();var ready=stage.readyCapability();var usage=f.local.source.client.usage();var events=new ArrayList<String>();
            Path replica=f.local.source.request.replicaDirectory();Object rootKey=MembershipBasisSources.key(replica.resolve("root.gsr"));
            var probe=new V53MembershipOwnershipTest();var locks=new ArrayList<Path>(List.of(replica.resolve("replica.lock"),
                    f.local.source.request.operationDirectory().resolve("operation.lock"),
                    (promoted?MembershipLearnerSuccessor.typedDirectory(f.local.summary):f.local.typed()).resolve("preparation.lock"),
                    MembershipLearnerIntent.directory(f.local.summary).resolve("source/source.gscp")));
            if(promoted)locks.add(MembershipLearnerSuccessor.directory(f.local.summary).resolve(MembershipLearnerSuccessor.LOCK));
            try(var custody=MembershipLearnerCustody.take(ready,events::add)) {
                assertEquals(replica,custody.replica());assertEquals(usage,custody.usage());assertEquals(2,usage.counts().get(MembershipResources.Unit.GENERATION));
                assertEquals(rootKey,MembershipBasisSources.key(replica.resolve("root.gsr")));probe.probe(locks.toArray(Path[]::new));
                assertThrows(Exception.class,old::check);assertThrows(Exception.class,ready::check);assertThrows(Exception.class,intent::forced);
                f.typed.close();intent.close();stage.close();f.local.store.close();
                custody.check();assertEquals(usage,f.local.source.client.usage());probe.probe(locks.toArray(Path[]::new));
                assertTrue(events.indexOf("LEARNER_CUSTODY_PARENT_FORCED")<events.indexOf("LEARNER_CUSTODY_TRANSFERRED"));
                assertEquals(receipt,custody.receipt().digest());assertFalse(Files.exists(replica.resolve("selector.gsr")));
                assertThrows(Exception.class,()->MembershipLearnerStore.resume(f.local.summary,f.local.source.client,e->{}));
                custody.check();probe.probe(locks.toArray(Path[]::new));
            }
            assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void foreignStorageOrInflightWorkRefusesBeforeDecisionAndLeavesHeadLive()throws Exception {
        try(var f=fixture(false);var intent=V53LearnerIntentTest.retain(f,e->{});var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{})) {
            for(var unit:List.of(MembershipResources.Unit.SOURCE,MembershipResources.Unit.CONTROL))try(var unrelated=f.local.source.client.reserve(unit,"foreign",1)) {
                var before=f.local.source.client.usage();assertThrows(IllegalArgumentException.class,()->MembershipLearnerCustody.take(stage.readyCapability(),e->fail("preflight must not write")));
                assertEquals(before,f.local.source.client.usage());assertFalse(Files.exists(MembershipLearnerCustody.directory(f.local.summary)));f.head.check();
            }
            try(var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})){custody.check();}
        }
    }
    @Test void originalForcedDecisionRecoversBeforeAndAfterInMemoryTransfer()throws Exception {
        try(var f=fixture(false)) {
            var intent=V53LearnerIntentTest.retain(f,e->{});var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});var ready=stage.readyCapability();
            var hit=new AtomicBoolean();assertThrows(IOException.class,()->MembershipLearnerCustody.take(ready,e->{if(e.equals("LEARNER_CUSTODY_BEFORE_TRANSFER")){hit.set(true);throw new IOException(e);}}));
            assertTrue(hit.get());f.head.check();ready.check();Path decision=MembershipLearnerCustody.directory(f.local.summary).resolve(MembershipLearnerCustody.FILE);
            byte[] original=AdmissionPaths.read(decision,MembershipLearnerCustody.MAXIMUM);Object key=MembershipBasisSources.key(decision);
            hit.set(false);assertThrows(IOException.class,()->MembershipLearnerCustody.resume(ready,e->{if(e.equals("LEARNER_CUSTODY_TRANSFERRED")){hit.set(true);throw new IOException(e);}}));
            assertTrue(hit.get());assertEquals(0,f.local.source.client.usage().leases());assertThrows(Exception.class,ready::check);
            f.reopen();
            try(var retained=MembershipLearnerIntent.resume(f.head,e->{});var staged=MembershipLearnerVoterStage.resume(retained.forced(),e->{});
                    var custody=MembershipLearnerCustody.resume(staged.readyCapability(),e->{})) {
                custody.check();assertArrayEquals(original,AdmissionPaths.read(decision,MembershipLearnerCustody.MAXIMUM));assertEquals(key,MembershipBasisSources.key(decision));
                new V53MembershipOwnershipTest().probe(f.local.source.request.replicaDirectory().resolve("replica.lock"));
            }
        }
    }
    @Test void tornDecisionAndLastBoundaryCorruptionNeverRevokeOriginalCustody()throws Exception {
        for(String fault:List.of("prefix","corrupt"))try(var f=fixture(false);var intent=V53LearnerIntentTest.retain(f,e->{});
                var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{})) {
            Path decision=MembershipLearnerCustody.directory(f.local.summary).resolve(MembershipLearnerCustody.FILE);var hit=new AtomicBoolean();
            assertThrows(Exception.class,()->MembershipLearnerCustody.take(stage.readyCapability(),e->{
                if(fault.equals("prefix") && e.equals("LEARNER_CUSTODY_PREFIX_WRITTEN")){hit.set(true);throw new IOException(e);}
                if(fault.equals("corrupt") && e.equals("LEARNER_CUSTODY_BEFORE_TRANSFER")){hit.set(true);Files.writeString(decision,"changed");}
            }));assertTrue(hit.get());byte[] original=AdmissionPaths.read(decision,MembershipLearnerCustody.MAXIMUM);var usage=f.local.source.client.usage();
            f.head.check();stage.readyCapability().check();assertThrows(Exception.class,()->MembershipLearnerCustody.resume(stage.readyCapability(),e->fail("invalid original must not write")));
            assertArrayEquals(original,AdmissionPaths.read(decision,MembershipLearnerCustody.MAXIMUM));assertEquals(usage,f.local.source.client.usage());
            new V53MembershipOwnershipTest().probe(f.local.source.request.replicaDirectory().resolve("replica.lock"));
        }
    }
}
