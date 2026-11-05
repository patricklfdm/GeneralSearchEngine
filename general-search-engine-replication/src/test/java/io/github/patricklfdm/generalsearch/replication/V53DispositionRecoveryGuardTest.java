package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.concurrent.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;

/** A revoked retained owner still excludes recovery until its listener and
 * storage cleanup complete. Conditional history, actual TCP callback close. */
class V53DispositionRecoveryGuardTest {
    @TempDir Path temp;
    @ParameterizedTest @ValueSource(strings={"checkpoint","head"})
    void failedDrainCannotAdmitRecoveryUntilTheSameOwnerFinishesCleanup(String listener)throws Exception {
        var helper=new V53LearnerCheckpointEndpointTest();helper.temp=temp;
        try(var f=helper.new Fixture()) {
            var resources=f.fixture.f.local.source.client;var store=f.fixture.f.local.store;
            var capture=new V53PendingListenerDrainTest.Capture(resources,f.baselineObservation);
            try(var gate=new V53PendingListenerDrainTest.Gate(f.pending,capture,true)) {
                MembershipLearnerCheckpointEndpoint checkpoint=null;MembershipLearnerHeadEndpoint head=null;
                try {
                    if(listener.equals("checkpoint"))checkpoint=f.listen(gate);
                    else{f.pending.endorse();head=f.pending.retainSource().listenHead(f.fixture.f.local.config.bounds(),gate);}
                    try(var contact=f.contact()) {
                        var request=listener.equals("checkpoint")?f.first():V53LearnerHeadProtocolTest.query(f.fixture.f.head,f.reader);
                        var call=contact.exchange(f.local,request,listener.equals("checkpoint")?"SOURCE_OFFER":"LEARNER_HEAD_ACK",
                                System.nanoTime()+TimeUnit.SECONDS.toNanos(20));
                        try {
                            assertTrue(gate.entered.await(15,TimeUnit.SECONDS));
                            assertEquals("joining "+(listener.equals("checkpoint")?"checkpoint":"progress")+" listener not drained",
                                    assertInstanceOf(IOException.class,gate.failure.get()).getMessage());
                            var files=V53ReplayFilesTest.files(f.fixture.directory());var before=resources.usage();
                            for(int attempt=0;attempt<2;attempt++) {
                                var error=assertThrows(IllegalArgumentException.class,()->MembershipLearnerIntent.resumePublished(
                                        f.fixture.f.head,event->fail("recovery must not mutate an undrained original")));
                                assertEquals("linked recovery has a live original owner",error.getMessage());
                                assertEquals("linked recovery has a live original owner",assertThrows(IllegalArgumentException.class,
                                        ()->store.requirePublishedRecovery(null)).getMessage());
                            }
                            assertEquals(before,resources.usage());assertEquals(files,V53ReplayFilesTest.files(f.fixture.directory()));
                            assertThrows(IllegalArgumentException.class,f.pending::source);
                        }finally{gate.close();}
                        assertThrows(ExecutionException.class,()->call.get(10,TimeUnit.SECONDS));
                        f.pending.close();assertEquals(f.baseline,resources.usage());
                        // This is only the owner-exclusion guard, not authority
                        // to fabricate the absent linked INTENT history.
                        store.requirePublishedRecovery(null);
                        try(var restored=MembershipLearnerPendingIntent.resume(f.fixture.f.head,event->{})) {
                            restored.source();
                            assertEquals("linked recovery has a live original owner",assertThrows(IllegalArgumentException.class,
                                    ()->store.requirePublishedRecovery(null)).getMessage());
                        }
                        store.requirePublishedRecovery(null);assertEquals(f.baseline,resources.usage());
                    }
                }finally{gate.close();if(checkpoint!=null)checkpoint.close();if(head!=null)head.close();}
            }
        }
    }
}
