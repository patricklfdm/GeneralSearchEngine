package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Original typed/INTENT/stage reopen, not fabricated joined-voter admission.
 * Conditional historical quorum fixtures; cold opens are not SIGKILL coverage. */
class V53LearnerPlacementRecoveryTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo test){System.out.println("v53LearnerPlacementRecoveryCase="+test.getTestMethod().orElseThrow().getName());}
    V53LearnerCancellationTest.Fixture fixture(boolean promoted)throws Exception {
        var helper=new V53LearnerIntentTest();helper.temp=temp;return helper.fixture("JOINT",3,"ADD",promoted);
    }
    void start(V53LearnerCancellationTest.Fixture f,String event)throws Exception {
        var hit=new AtomicBoolean();
        try(var intent=V53LearnerIntentTest.retain(f,e->{});var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
            assertThrows(IOException.class,()->MembershipLearnerPlacement.install(custody,e->{if(e.equals(event)){hit.set(true);throw new IOException(e);}}));
        }
        assertTrue(hit.get());assertEquals(0,f.local.source.client.usage().leases());
    }
    MembershipLearnerPlacement recover(V53LearnerCancellationTest.Fixture f,MembershipBallotAllocator.Cut cut)throws Exception {
        return MembershipLearnerPlacement.recover(f.local.summary,f.local.source.client,f.local.captured,f.local.config,cut);
    }
    @Test void initialOriginalsReopenAtEachMovedPrefixWithoutReleasingTheNewOwner()throws Exception {
        try(var f=fixture(false)) {
            start(f,"LEARNER_PLACEMENT_DECISION_FORCED");
            Path plan=MembershipLearnerPlacement.directory(f.local.summary).resolve(MembershipLearnerPlacement.PLAN);
            var identity=MembershipBasisSources.inspect(plan,Files.size(plan),MembershipFormat.hash(Files.readAllBytes(plan)));
            Path root=f.local.source.request.replicaDirectory().resolve("replica.lock");Object key=MembershipBasisSources.key(root);
            int count=0;
            for(String name:MembershipLearnerPlacement.MOVES) {
                System.out.println("v53LearnerColdPrefix="+name);
                var verified=new AtomicBoolean();var moved=new AtomicBoolean();
                assertThrows(IOException.class,()->recover(f,event->{
                    if(event.equals("LEARNER_PLACEMENT_RECOVERY_VERIFIED")){verified.set(true);try{new V53MembershipOwnershipTest().probe(root);}catch(Exception failure){throw new IOException(failure);}}
                    else assertTrue(verified.get(),"no mutation/force cut before original semantic validation");
                    if(event.equals("LEARNER_PLACEMENT_MOVED:"+name)){moved.set(true);throw new IOException(event);}
                }));assertTrue(verified.get());assertTrue(moved.get());assertEquals(0,f.local.source.client.usage().leases());
                assertEquals(++count,MembershipLearnerPlacement.inspectOriginal(f.local.summary).moved());assertEquals(key,MembershipBasisSources.key(root));
                assertEquals(identity,MembershipBasisSources.inspect(plan,identity.bytes(),identity.digest()));
            }
            try(var placement=recover(f,event->{})) {
                placement.check();assertEquals("PLACED",MembershipLearnerPlacement.inspectOriginal(f.local.summary).status());
                assertEquals(2,f.local.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
                assertEquals(1,f.local.source.client.usage().counts().get(MembershipResources.Unit.LEARNER));
                f.typed.close();f.local.store.close();placement.check();new V53MembershipOwnershipTest().probe(root);
                assertThrows(Exception.class,()->recover(f,event->fail("duplicate owner must not write")));
                placement.check();
            }
            assertEquals(0,f.local.source.client.usage().leases());
            try(var again=recover(f,event->{})){again.check();assertEquals(key,MembershipBasisSources.key(root));}
        }
    }
    @Test void promotedOriginalsReopenWithoutRecreatingRetiredInitialSource()throws Exception {
        try(var f=fixture(true)) {
            start(f,"LEARNER_PLACEMENT_MOVED:generations");
            Path replica=f.local.source.request.replicaDirectory();assertFalse(Files.exists(replica.resolve("learner")));
            assertFalse(Files.exists(MembershipLearnerMaterialization.directory(f.local.summary)));
            try(var placed=recover(f,event->{})) {
                placed.check();assertFalse(Files.exists(replica.resolve("learner")));
                assertFalse(Files.exists(MembershipLearnerMaterialization.directory(f.local.summary)));
                new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"),
                        MembershipLearnerSuccessor.directory(f.local.summary).resolve(MembershipLearnerSuccessor.LOCK));
            }
            assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void selectedSlotReopensItsOriginalSeedAndTypedOwnersAfterPlacement()throws Exception {
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
            var network=new V53LearnerProgressNetworkTest();network.temp=temp;
            var history=V53CapsuleFixture.fromHistory(f.source.fixture.fixture.source,6);
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store.currentSource(),1),f.captured,f.config,e->{});
                    var peer=network.new Peer(history,true);
                    var server=new MembershipTransport(peer.owner,f.config.bounds(),peer.server,(sender,frame)->
                        frame.kind().equals("STATUS_PROBE")?MembershipDiscovery.answer(peer.owner.activationContext(),peer.owner.activationIdentity(),sender,frame):
                            peer.service.handle(sender,frame),MembershipTransport.Events.NONE)) {
                MembershipLearnerIntent retained;
                try(var progress=new MembershipLearnerProgress(typed.currentHead(),peer.owner.activationIdentity(),f.config.bounds(),MembershipTransport.Events.NONE,
                        System::nanoTime,System.nanoTime(),java.util.concurrent.TimeUnit.SECONDS.toNanos(60))) {
                    progress.fetch(f.base.resolve("slot-intent-source"));retained=progress.retainIntent(e->{});
                }
                var hit=new AtomicBoolean();
                try(var intent=retained;var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                        var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
                    assertThrows(IOException.class,()->MembershipLearnerPlacement.install(custody,event->{
                        if(event.equals("LEARNER_PLACEMENT_MOVED:generations")){hit.set(true);throw new IOException(event);}
                    }));
                }
                assertTrue(hit.get());assertEquals(0,f.source.client.usage().leases());
                Path cleared=MembershipLearnerSlot.directory(f.summary).resolve(MembershipLearnerSlot.CLEARED);
                byte[] originalClear=Files.readAllBytes(cleared);
                Files.writeString(cleared,"invalid-retirement-proof");
                assertThrows(Exception.class,()->MembershipLearnerPlacement.recover(f.summary,f.source.client,f.captured,f.config,
                        event->fail("invalid retirement proof must not force")));
                assertEquals("invalid-retirement-proof",Files.readString(cleared));assertEquals(0,f.source.client.usage().leases());
                Files.write(cleared,originalClear);
                try(var placed=MembershipLearnerPlacement.recover(f.summary,f.source.client,f.captured,f.config,e->{})) {
                    placed.check();new V53MembershipOwnershipTest().probe(f.source.request.replicaDirectory().resolve("replica.lock"),
                            MembershipLearnerSuccessor.directory(f.summary).resolve(MembershipLearnerSuccessor.LOCK),
                            MembershipLearnerSlot.directory(f.summary).resolve(MembershipLearnerSlot.LOCK),
                            MembershipLearnerSlot.typedDirectory(f.summary).resolve(MembershipLearnerMaterialization.LOCK));
                    assertFalse(Files.exists(MembershipLearnerSuccessor.directory(f.summary).resolve(MembershipLearnerSuccessor.SOURCE)));
                    assertFalse(Files.exists(MembershipLearnerSuccessor.typedDirectory(f.summary)));
                    assertEquals(2,f.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
                }
                assertEquals(0,f.source.client.usage().leases());
            }
        }
    }
    @Test void corruptOriginalsAndLastReadBoundaryRefuseBeforeAnyRecoveryForce()throws Exception {
        try(var f=fixture(false)) {
            start(f,"LEARNER_PLACEMENT_MOVED:genesis.gsr");
            Path plan=MembershipLearnerPlacement.directory(f.local.summary).resolve(MembershipLearnerPlacement.PLAN);
            byte[] bytes=Files.readAllBytes(plan);
            Path receipt=MembershipLearnerMaterialization.directory(f.local.summary).resolve(MembershipLearnerMaterialization.RECEIPT);
            Path replica=f.local.source.request.replicaDirectory(),saved=f.local.base.resolve("saved-placement-member");
            for(String fault:List.of("receipt-missing","typed-missing","replica-missing","lock-missing","payload-copy","plan-corrupt")) {
                Path original=switch(fault) {
                    case "receipt-missing" -> receipt;
                    case "typed-missing" -> receipt.getParent();
                    case "replica-missing" -> replica;
                    case "lock-missing" -> replica.resolve("replica.lock");
                    default -> replica.resolve("genesis.gsr");
                };
                if(fault.equals("plan-corrupt"))Files.writeString(plan,"changed");
                else {Files.move(original,saved);if(fault.equals("payload-copy"))Files.copy(saved,original);}
                var before=MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null);
                assertThrows(Exception.class,()->recover(f,event->fail("invalid originals must not force")));
                assertEquals(before,MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null));
                assertEquals(0,f.local.source.client.usage().leases());
                if(fault.equals("plan-corrupt"))Files.write(plan,bytes);
                else {Files.deleteIfExists(original);Files.move(saved,original);}
            }
            var verified=new AtomicBoolean();
            assertThrows(Exception.class,()->recover(f,event->{
                assertEquals("LEARNER_PLACEMENT_RECOVERY_VERIFIED",event);verified.set(true);Files.writeString(plan,"changed-after-validation");
            }));assertTrue(verified.get());assertEquals("changed-after-validation",Files.readString(plan));
            assertEquals(0,f.local.source.client.usage().leases());Files.write(plan,bytes);
            // Same persisted descriptor and original bytes, but a failing real
            // application decoder: metadata-only replay must not admit it.
            var decoded=new AtomicBoolean();var original=f.local.config.materialization();var delegate=original.codec();
            var codec=new io.github.patricklfdm.generalsearch.durability.DurableCodec<Integer,io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc>() {
                public String codecId(){return delegate.codecId();}
                public int codecVersion(){return delegate.codecVersion();}
                public byte[] encodeKey(Integer key){return delegate.encodeKey(key);}
                public Integer decodeKey(byte[] value){return delegate.decodeKey(value);}
                public byte[] encodeDocument(io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc value){return delegate.encodeDocument(value);}
                public io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc decodeDocument(byte[] value){decoded.set(true);throw new IllegalArgumentException("semantic decoder refused");}
            };
            var storage=io.github.patricklfdm.generalsearch.durability.DurableStorageConfig.builder(original.directory(),codec).format(original.format())
                    .storageIdentity(original.storageIdentity()).schemaIdentity(original.schemaIdentity()).maxEncodedKeyBytes(original.maxEncodedKeyBytes())
                    .maxEncodedDocumentBytes(original.maxEncodedDocumentBytes()).maxBulkElements(original.maxBulkElements()).maxDocuments(original.maxDocuments())
                    .checkpointWalBytes(original.checkpointWalBytes()).maxRetainedBytes(original.maxRetainedBytes()).maxDerivedStateBytes(original.maxDerivedStateBytes()).build();
            var config=new MembershipReplicaConfig<>(f.local.config.root(),f.local.config.localIdentity(),List.of(),f.local.config.replicaDirectory(),storage,
                    f.local.config.bounds(),f.local.config.leadershipPolicy());
            var before=MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null);
            assertThrows(Exception.class,()->MembershipLearnerPlacement.recover(f.local.summary,f.local.source.client,f.local.captured,config,event->fail("semantic refusal must not force")));
            assertTrue(decoded.get());assertEquals(before,MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null));
            assertEquals(0,f.local.source.client.usage().leases());
            try(var occupied=f.local.source.client.reserve(MembershipResources.Unit.CONTROL,"busy",1)) {
                assertThrows(IllegalArgumentException.class,()->recover(f,event->fail("busy resources must not reopen")));
                assertEquals(1,f.local.source.client.usage().leases());
            }
            try(var placed=recover(f,event->{})){placed.check();}
        }
    }
}
