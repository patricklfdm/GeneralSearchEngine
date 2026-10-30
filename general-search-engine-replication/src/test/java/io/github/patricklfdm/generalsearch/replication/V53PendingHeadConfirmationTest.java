package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual pending owners, files and TCP; the old history in these focused
 * fixtures is conditional. The native majority test supplies the separate
 * continuous publication/confirmation/installation history. */
class V53PendingHeadConfirmationTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo info){System.out.println("v53PendingHeadCase="+info.getDisplayName());}
    V53LearnerCheckpointEndpointTest.Fixture fixture()throws Exception {
        var helper=new V53LearnerCheckpointEndpointTest();helper.temp=temp;return helper.new Fixture();
    }
    @Test void onlyForcedRetainedOriginalCanReportSealedEndpointWithoutAdvancingTypedHead()throws Exception {
        try(var f=fixture()) {
            var head=f.fixture.f.head;var pool=f.fixture.f.local.source.client;
            assertThrows(IllegalArgumentException.class,f.pending::retainSource);
            f.pending.endorse();var retained=f.pending.retainSource();var baseline=pool.usage();
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerHeadObservation.capture(head));
            var before=V53ReplayFilesTest.files(f.fixture.directory());
            try(var observed=MembershipLearnerHeadObservation.capture(retained)) {
                assertEquals(5L,number(observed.endpoint.cut().get("index")));
                assertEquals(3L,number(head.source().terminal().cut().get("index")));
                assertEquals(baseline.queued()+MembershipLearnerHeadObservation.BYTES,pool.usage().queued());
            }
            try(var endpoint=retained.listenHead(f.fixture.f.local.config.bounds(),MembershipTransport.Events.NONE);var contact=f.contact()) {
                var query=V53LearnerHeadProtocolTest.query(head,f.reader);
                var reply=contact.exchange(f.local,query,"LEARNER_HEAD_ACK",System.nanoTime()+TimeUnit.SECONDS.toNanos(30)).get(35,TimeUnit.SECONDS);
                MembershipWire.correlated(query,reply,"LEARNER_HEAD_ACK");
                assertEquals(MembershipRetentionIntent.anchor(f.source.terminal()),object(reply.value().get("payload")).get("endpoint"));
                assertArrayEquals(reply.bytes(),endpoint.answer(f.reader,query).bytes());
                assertThrows(IllegalArgumentException.class,()->retained.listenHead(f.fixture.f.local.config.bounds(),MembershipTransport.Events.NONE));
                assertThrows(IllegalArgumentException.class,()->f.listen(MembershipTransport.Events.NONE));
                for(var mutation:List.<Consumer<Map<String,Object>>>of(
                        v->v.put("root","ab".repeat(32)),v->v.put("view","ab".repeat(32)),v->v.put("sequence",2L),
                        v->object(v.get("ballot")).put("counter",2L),
                        v->object(v.get("sender")).put("storage",UUID.randomUUID().toString()),
                        v->object(object(v.get("payload")).get("request")).put("number",2L)))
                    assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,V53LearnerHeadProtocolTest.changed(query,mutation)));
                assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.local,V53LearnerHeadProtocolTest.query(head,f.local)));
                for(String name:List.of(MembershipLearnerDisposition.PENDING_ACK,MembershipLearnerDisposition.PENDING_SOURCE,"source/generation.gsr")) {
                    Path path=f.fixture.directory().resolve(name);byte[] original=Files.readAllBytes(path),bad=original.clone();bad[bad.length/2]^=1;
                    try {Files.write(path,bad);assertThrows(Exception.class,()->endpoint.answer(f.reader,query));}
                    finally{Files.write(path,original);}
                }
                var history=f.fixture.f.local.source.fixture.fixture.source;
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerProgressAccess.headRequest(f.source.context,f.local,f.reader));
                for(int through:List.of(6,7)) {
                    var published=V53CapsuleFixture.fromHistory(history,through).verify().context;
                    assertEquals(MembershipLearnerDiscovery.request(head.request().change()),MembershipLearnerProgressAccess.headRequest(published,f.local,f.reader));
                    assertThrows(IllegalArgumentException.class,()->MembershipLearnerDiscovery.reservation(published,f.local));
                    assertThrows(IllegalArgumentException.class,()->MembershipLearnerProgressAccess.headRequest(published,f.local,f.local));
                    var foreign=new MembershipIdentity(f.reader.nodeId(),UUID.randomUUID(),f.reader.endpoint());
                    assertThrows(IllegalArgumentException.class,()->MembershipLearnerProgressAccess.headRequest(published,f.local,foreign));
                }
                assertEquals(before,V53ReplayFilesTest.files(f.fixture.directory()));
                f.pending.close();assertTrue(endpoint.closed());assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,query));
            }
            assertEquals(f.baseline,pool.usage());
        }
    }
    @Test void changedOriginalAfterResponseHookCannotEmitAnAcknowledgement()throws Exception {
        try(var f=fixture()) {
            f.pending.endorse();var retained=f.pending.retainSource();Path ack=f.fixture.directory().resolve(MembershipLearnerDisposition.PENDING_ACK);
            byte[] original=Files.readAllBytes(ack);var reached=new AtomicBoolean();var baseline=f.fixture.f.local.source.client.usage();
            try(var endpoint=retained.listenHead(f.fixture.f.local.config.bounds(),(event,q,a)->{
                if(event.equals("BEFORE_RESPONSE_WRITE") && reached.compareAndSet(false,true))Files.writeString(ack,"changed-after-response");
            });var contact=f.contact()) {
                var query=V53LearnerHeadProtocolTest.query(f.fixture.f.head,f.reader);
                assertThrows(ExecutionException.class,()->contact.exchange(f.local,query,"LEARNER_HEAD_ACK",System.nanoTime()+TimeUnit.SECONDS.toNanos(30)).get(35,TimeUnit.SECONDS));
                assertTrue(reached.get());assertThrows(Exception.class,()->endpoint.answer(f.reader,query));
            }finally{Files.write(ack,original);}
            assertEquals(baseline,f.fixture.f.local.source.client.usage());retained.check();
        }
    }
    @Test void linkedIntentRevokesObservationAndVoterHandoffDrainsOwnedListener()throws Exception {
        var helper=new V53PendingPublishedProgressTest();helper.temp=temp;
        try(var f=helper.new Fixture(6);var endpoint=f.retained.listenHead(f.f.f.local.config.bounds(),MembershipTransport.Events.NONE);
                var progress=f.progress(MembershipTransport.Events.NONE)) {
            var query=V53LearnerHeadProtocolTest.query(f.f.f.head,f.f.f.peer.owner.activationIdentity());
            endpoint.answer(f.f.f.peer.owner.activationIdentity(),query);progress.fetch(f.scratch());
            try(var intent=progress.retainPublishedIntent(e->{})) {
                assertThrows(Exception.class,()->endpoint.answer(f.f.f.peer.owner.activationIdentity(),query));
                assertThrows(Exception.class,()->f.retained.listenHead(f.f.f.local.config.bounds(),MembershipTransport.Events.NONE));
                progress.close();
                try(var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                        var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
                    assertTrue(endpoint.closed());custody.check();
                }
            }
            assertEquals(0,f.f.f.local.source.client.usage().leases());
        }
    }
}
