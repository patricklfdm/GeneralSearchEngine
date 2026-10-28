package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipLearnerMaterialization.*;

/** Actual typed backups and original filesystem transactions; historical voter
 * forces are conditional fixtures, with native preparation qualified separately. */
class V53LearnerMaterializationTest {
    @TempDir Path temp;
    final class Fixture implements AutoCloseable {
        final Path base;
        final SearchEngineConfiguration<Integer,Doc> captured=builder().configuration();
        final V53LearnerSourceTest.Fixture source;
        final MembershipSourcePull prefix,generation;
        final MembershipLearnerPlan summary;
        final MembershipReplicaConfig<Integer,Doc> config;
        final DurableApplicationState<Doc> original;
        MembershipLearnerStore store;
        Fixture(int size,String kind)throws Exception {
            base=Files.createDirectory(temp.resolve(UUID.randomUUID().toString()));var storage=storage(base.resolve("core"),2);
            original=new DurableApplicationState<>(V53ApplicationImageTest.HISTORY,41,List.of(new Doc(7,"original"),new Doc(2,"你好")),captured.indexes());
            byte[] image=MembershipApplicationImage.capture(captured,storage,original,base.resolve("original-backup"));
            var descriptor=AdmissionConfiguration.application(captured);
            var initial=new V53ContextFixture(size,kind,image,original.history(),original.sequence(),
                    hash(canonical(Map.of("schemaIdentity",storage.schemaIdentity(),"application",descriptor),1024*1024)),
                    hash(canonical(descriptor.get("indexes"),262144)),storage.codec().codecId(),storage.codec().codecVersion());
            var capsule=new V53CapsuleFixture(initial,kind,3);var helper=new V53LearnerSourceTest();helper.temp=base;
            source=helper.new Fixture(size,kind,capsule);prefix=source.pull();generation=source.pull();prefix.fetchPrefix(base.resolve("receiving"));
            var copy=generation.fetchGeneration(prefix);var plan=MembershipLearnerAdmissionPlan.create(source.request,copy);summary=plan.summary();
            try(var files=MembershipLearnerAdmissionFiles.create(plan,source.client,e->{},()->plan.checkOriginal(copy))){files.summary();}
            var received=prefix.completeLearnerSource(copy,e->{});
            store=MembershipLearnerStore.install(MembershipLearnerAdmissionFiles.openAdmission(summary,source.client,e->{}),received,copy,e->{});
            generation.close();prefix.close();var bounds=ReplicationBounds.defaults();
            config=new MembershipReplicaConfig<>(source.request.root(),source.request.identity(),List.of(),source.request.replicaDirectory(),storage,bounds,AutomaticLeadershipPolicy.forBounds(bounds));
        }
        Fixture()throws Exception{this(3,"ADD");}
        Path typed(){return directory(summary);}
        MembershipLearnerMaterialization<Doc> prepare(MembershipBallotAllocator.Cut cut)throws IOException {
            return MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store,1),captured,config,cut);
        }
        void reopen()throws IOException {store.close();assertEquals(0,source.client.usage().leases());store=MembershipLearnerStore.resume(summary,source.client,e->{});}
        @Override public void close()throws Exception {store.close();generation.close();prefix.close();source.close();}
    }
    @Test void allFiveJoiningShapesForceRealTypedImagesAndExactReceipts()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            try(var f=new Fixture(size,kind)) {
                var original=V53ReplayFilesTest.files(f.source.request.replicaDirectory());var events=new ArrayList<String>();byte[] receipt;
                try(var typed=f.prepare(events::add)) {
                    assertEquals(f.original,typed.state());receipt=typed.receipt().bytes();
                    assertEquals("LEARNER",typed.receipt().kind());assertEquals(f.source.request.identity(),MembershipContext.identity(object(object(typed.receipt().value().get("receipt")).get("identity"))));
                    assertTrue(events.indexOf("LEARNER_TYPED_BACKUP_FORCED")<events.indexOf("LEARNER_TYPED_SEMANTICS_VERIFIED"));
                    assertTrue(events.indexOf("LEARNER_TYPED_SEMANTICS_VERIFIED")<events.indexOf("LEARNER_TYPED_RECEIPT_CREATED"));
                    assertTrue(events.indexOf("LEARNER_TYPED_RECEIPT_PARENT_FORCED")<events.indexOf("LEARNER_TYPED_BEFORE_RETURN"));
                    assertEquals(2,f.source.client.usage().counts().get(MembershipResources.Unit.APPLICATION));
                    assertThrows(ReplicationException.class,()->f.prepare(e->{}));
                }
                assertEquals(original,V53ReplayFilesTest.files(f.source.request.replicaDirectory()));assertFalse(Files.exists(f.config.materialization().directory()));
                var before=V53ReplayFilesTest.files(f.typed());f.reopen();
                assertEquals(2,f.source.client.usage().counts().get(MembershipResources.Unit.APPLICATION));
                try(var typed=f.prepare(e->{})){assertArrayEquals(receipt,typed.receipt().bytes());assertEquals(f.original,typed.state());}
                assertEquals(before,V53ReplayFilesTest.files(f.typed()));
            }
        }
    }
    @Test void interruptedOriginalPlanAndTypedWritesPreserveOrResumeExactly()throws Exception {
        var cuts=List.of("LEARNER_TYPED_DIRECTORY_FORCED","LEARNER_TYPED_PLAN_CREATED","LEARNER_TYPED_PLAN_PREFIX_WRITTEN",
                "LEARNER_TYPED_PLAN_WRITTEN","LEARNER_TYPED_PLAN_RENAMED","LEARNER_TYPED_MEMBER_PREFIX_WRITTEN",
                "LEARNER_TYPED_BACKUP_FORCED","LEARNER_TYPED_SEMANTICS_VERIFIED","LEARNER_TYPED_RECEIPT_PREFIX_WRITTEN",
                "LEARNER_TYPED_RECEIPT_FORCED","LEARNER_TYPED_BEFORE_RETURN");
        for(String cut:cuts)try(var f=new Fixture()) {
            var reached=new AtomicBoolean();assertThrows(IOException.class,()->f.prepare(event->{if(event.equals(cut)){reached.set(true);throw new IOException(cut);}}));assertTrue(reached.get(),cut);
            var before=V53ReplayFilesTest.files(f.typed());f.reopen();
            if(cuts.indexOf(cut)<3) {
                assertThrows(IllegalArgumentException.class,()->f.prepare(event->{throw new AssertionError("refusal forced bytes");}));
                assertEquals(before,V53ReplayFilesTest.files(f.typed()));
            }else try(var typed=f.prepare(e->{})){assertEquals(f.original,typed.state());}
        }
    }
    @Test void changedOriginalBackupOrPlanAndUnknownMembersAreNeverRepaired()throws Exception {
        for(String mode:List.of("backup","plan","extra","link","missing-backup","receipt"))try(var f=new Fixture()) {
            try(var typed=f.prepare(e->{})){typed.receipt();}
            Path root=f.typed();
            if(mode.equals("backup"))Files.write(root.resolve(BACKUP).resolve(MembershipApplicationImage.MEMBERS.getFirst()),new byte[]{0});
            if(mode.equals("plan"))Files.write(root.resolve(PLAN),new byte[]{0});
            if(mode.equals("extra"))Files.write(root.resolve("foreign"),new byte[]{7});
            if(mode.equals("link")) {
                Path path=root.resolve(BACKUP).resolve(MembershipApplicationImage.MEMBERS.getFirst()),other=f.base.resolve("original-member");
                Files.move(path,other);Files.createLink(path,other);
            }
            if(mode.equals("missing-backup"))Files.delete(root.resolve(BACKUP).resolve(MembershipApplicationImage.MEMBERS.getFirst()));
            if(mode.equals("receipt"))Files.write(root.resolve(RECEIPT),new byte[]{0});
            var before=V53ReplayFilesTest.files(root);
            assertThrows(Exception.class,()->f.prepare(event->{throw new AssertionError("foreign original forced");}),mode);
            assertEquals(before,V53ReplayFilesTest.files(root));
        }
    }
    @Test void semanticMismatchNeverForcesAReceiptAndCannotChangeTheRetainedDescriptor()throws Exception {
        try(var f=new Fixture()) {
            var wrong=DurableStorageConfig.builder(f.config.materialization().directory(),new Codec()).format(new DurableStorageFormat("gse-durable",1,2))
                    .storageIdentity("foreign").schemaIdentity("fixture-schema").maxEncodedKeyBytes(1024).maxEncodedDocumentBytes(65536).maxDocuments(10000).build();
            var config=new MembershipReplicaConfig<>(f.config.root(),f.config.localIdentity(),List.of(),f.config.replicaDirectory(),wrong,f.config.bounds(),f.config.leadershipPolicy());
            var error=assertThrows(DurableOperationException.class,()->MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(f.store,1),f.captured,config,e->{}));
            assertEquals(DurableOperationException.Reason.IDENTITY_MISMATCH,error.reason());assertFalse(Files.exists(f.typed().resolve(RECEIPT)));
            var before=V53ReplayFilesTest.files(f.typed());
            var changed=assertThrows(ReplicationException.class,()->f.prepare(e->{throw new AssertionError("changed configuration forced");}));
            assertEquals("authority member exceeds bound",changed.getMessage());
            assertEquals(before,V53ReplayFilesTest.files(f.typed()));
        }
    }
    @Test void imageBudgetIsSharedRetainedAcrossCloseAndReservedOnReopen()throws Exception {
        try(var f=new Fixture()) {
            var occupied=new ArrayList<MembershipResources.Lease>();
            try {
                for(int i=0;i<6;i++)occupied.add(f.source.client.reserve(MembershipResources.Unit.APPLICATION,"busy-"+i,1));
                assertThrows(IllegalArgumentException.class,()->f.prepare(e->{}));assertFalse(Files.exists(f.typed()));
                occupied.removeLast().close();
                try(var typed=f.prepare(e->{})){typed.receipt();assertEquals(7,f.source.client.usage().counts().get(MembershipResources.Unit.APPLICATION));}
                assertEquals(7,f.source.client.usage().counts().get(MembershipResources.Unit.APPLICATION));
            }finally{occupied.forEach(MembershipResources.Lease::close);}
            f.reopen();assertEquals(2,f.source.client.usage().counts().get(MembershipResources.Unit.APPLICATION));
        }
    }
    @Test void closingParentRevokesReceiptAndDrainsItsChildBeforeReleasingSources()throws Exception {
        try(var f=new Fixture()) {
            var typed=f.prepare(e->{});f.store.close();assertTrue(typed.closed());assertEquals(0,f.source.client.usage().leases());
            assertThrows(IllegalArgumentException.class,typed::receipt);assertThrows(IllegalArgumentException.class,typed::state);typed.close();
            try(var lock=MembershipOwnership.own(f.typed().resolve(LOCK),false)){assertTrue(lock.lock().isValid());}
        }
    }
}
