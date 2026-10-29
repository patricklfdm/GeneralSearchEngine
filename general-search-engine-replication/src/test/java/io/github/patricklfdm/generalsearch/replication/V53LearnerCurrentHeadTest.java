package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;

/** Real TCP retrieval and typed storage with a conditional original history.
 * This is distinct from native multi-revision consensus qualification. */
class V53LearnerCurrentHeadTest {
    @TempDir Path temp;
    V53LearnerSuccessorTest helper(){var h=new V53LearnerSuccessorTest();h.temp=temp;return h;}
    MembershipLearnerSuccessor.View promote(V53LearnerMaterializationTest.Fixture f)throws Exception {
        var h=new V53LearnerRetirementTest();h.temp=temp;return h.head(f,e->{});
    }
    @Test void coldTypedHeadDrivesTcpRefreshWithoutAnotherGenerationOrAdmission()throws Exception {
        try(var f=helper().fixture(3,"ADD")) {
            promote(f).retirePredecessor();f.reopen();
            var current=f.store.promotedSuccessor();
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(current,1),f.captured,f.config,e->{});
                    var server=new MembershipTransport(f.source.owner,f.config.bounds(),f.source.server,(sender,frame)->{
                        try{return frame.kind().equals("STATUS_PROBE")?f.source.owner.discoveryStatus(sender,frame):f.source.service.handle(sender,frame);}
                        catch(java.io.IOException|RuntimeException error){error.printStackTrace();throw error;}
                    },MembershipTransport.Events.NONE)) {
                var head=typed.currentHead();assertSame(f.source.client,head.resources());
                var before=V53ReplayFilesTest.files(f.base);var baseline=f.source.client.usage();var seen=new ArrayList<String>();
                Path scratch=f.base.resolve("next-receiving");
                try(var refresh=MembershipLearnerSource.refresh(head,f.source.owner.activationIdentity(),f.config.bounds(),
                        (event,q,a)->{if(event.equals("AFTER_RESPONSE_READ"))seen.add(a.kind());},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(180))) {
                    var copy=refresh.fetch(scratch);assertSame(copy,refresh.source());
                    assertArrayEquals(head.source().packet.bytes(),copy.capsule.packet.bytes());
                    assertEquals(1,f.source.client.usage().counts().get(Unit.GENERATION));assertEquals(1,f.source.client.usage().counts().get(Unit.LEARNER));
                    assertFalse(copy.capsule.context.voters().contains(f.summary.request().identity().nodeId().value()));
                    assertThrows(IllegalArgumentException.class,()->refresh.plan(e->{}));
                    assertThrows(IllegalArgumentException.class,()->refresh.admit(f.summary,e->{}));
                    assertEquals("learner successor requires initial prepared predecessor; current head needs reusable-slot installation",
                            assertThrows(IllegalArgumentException.class,()->refresh.installSuccessor(e->{})).getMessage());
                    assertSame(copy,refresh.source());
                }
                assertTrue(seen.contains("SOURCE_OFFER") && seen.contains("TRANSFER_COMMIT"),seen.toString());
                assertFalse(Files.exists(scratch));assertEquals(baseline,f.source.client.usage());assertEquals(before,V53ReplayFilesTest.files(f.base));
                head.check();
                // Closing only the typed owner during an actual reply revokes the
                // acquisition; receiver cleanup cannot release retained head bytes.
                try(var revoked=MembershipLearnerSource.refresh(head,f.source.owner.activationIdentity(),f.config.bounds(),
                        (event,q,a)->{if(event.equals("AFTER_RESPONSE_READ"))typed.close();},System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(180))) {
                    assertThrows(Exception.class,()->revoked.fetch(f.base.resolve("revoked-receiving")));
                }
                assertThrows(IllegalArgumentException.class,head::check);assertEquals(baseline,f.source.client.usage());
                assertEquals(before,V53ReplayFilesTest.files(f.base));
            }
        }
    }
    @Test void onlyCurrentRetiredTypedHeadCanAcquireAndAllReservedPathsStayProtected()throws Exception {
        try(var f=helper().fixture(3,"ADD")) {
            MembershipLearnerSuccessor.View current;
            try(var old=f.prepare(e->{})) {
                assertThrows(IllegalArgumentException.class,old::currentHead);
                var candidate=helper().install(f,old.retainGeneration(),e->{});
                try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(candidate,1),f.captured,f.config,e->{})) {
                    assertEquals("learner refresh requires current typed head",assertThrows(IllegalArgumentException.class,typed::currentHead).getMessage());
                    current=typed.promoteSuccessor();
                }
            }
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(current,1),f.captured,f.config,e->{})) {
                assertEquals("learner refresh requires forced predecessor retirement",assertThrows(IllegalArgumentException.class,typed::currentHead).getMessage());
            }
            current.retirePredecessor();
            try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(current,1),f.captured,f.config,e->{})) {
                var head=typed.currentHead();var baseline=f.source.client.usage();var before=V53ReplayFilesTest.files(f.base);
                for(Path path:List.of(f.summary.request().operationDirectory(),f.summary.request().replicaDirectory(),
                        MembershipLearnerSuccessor.directory(f.summary),MembershipLearnerSuccessor.typedDirectory(f.summary),
                        f.typed(),f.config.materialization().directory())) {
                    try(var refresh=MembershipLearnerSource.refresh(head,f.source.owner.activationIdentity(),f.config.bounds(),MembershipTransport.Events.NONE,
                            System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(180))) {
                        assertEquals("overlapping authority/source paths",assertThrows(ReplicationException.class,()->refresh.fetch(path)).getMessage());
                    }
                }
                var clock=new AtomicLong();
                try(var expired=MembershipLearnerSource.refresh(head,f.source.owner.activationIdentity(),f.config.bounds(),MembershipTransport.Events.NONE,clock::get,0,10)) {
                    clock.set(10);assertEquals("learner source closed/original deadline",assertThrows(IllegalArgumentException.class,()->expired.fetch(f.base.resolve("expired"))).getMessage());
                }
                assertEquals(baseline,f.source.client.usage());assertEquals(before,V53ReplayFilesTest.files(f.base));
                f.store.close();assertThrows(IllegalArgumentException.class,head::check);assertEquals(0,f.source.client.usage().leases());
            }
        }
    }
}
