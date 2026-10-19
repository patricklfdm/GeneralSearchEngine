package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.V51PublicRuntimeTest.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationState.*;
import java.nio.file.Path;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.List;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.api.io.TempDir;

/** Original public writes; observation hooks delay publication, never forge authority. */
class V52MutationDeadlineTest {
    @TempDir Path root;

    @ParameterizedTest @ValueSource(booleans={true,false})
    void queuedClientDeadlineDoesNotCancelProvenWriteOrLegacyReadBarrier(boolean mutation) throws Exception {
        var fixture=new V51PublicRuntimeTest();fixture.root=root;
        var owner=new AtomicReference<String>();var publishes=new AtomicInteger();var chosen=new AtomicInteger();var readInvoked=new CountDownLatch(1);
        var firstEntered=new CountDownLatch(1);var firstRelease=new CountDownLatch(1);
        var secondEntered=new CountDownLatch(1);var secondRelease=new CountDownLatch(1);
        try(var group=fixture.new Group(rich(),null,false)) {
            try {
                for(var engine:group.engines) {
                    String node=engine.leadershipStatus().localNodeId().value();
                    AutomaticRuntimeHooks.CURRENT.set(new AutomaticRuntimeHooks.Hooks(AutomaticStore.Faults.NONE,
                        AutomaticTransport.Events.NONE,(event,value)->{
                            if(!node.equals(owner.get()))return;
                            if(event.equals("PUBLIC_READ_INVOKE"))readInvoked.countDown();
                            if(!event.equals("BEFORE_PUBLISH"))return;
                            long sequence=publishes.incrementAndGet();
                            if(sequence==1){firstEntered.countDown();latch(firstRelease);}
                            if(sequence==2){chosen.set(((List<?>)decode(unbase(value.get("snapshot")),"SNAPSHOT").value().get("anchors")).size());secondEntered.countDown();latch(secondRelease);}
                        }));
                    engine.start().get(15,TimeUnit.SECONDS);
                }
                AutomaticRuntimeHooks.CURRENT.remove();
                var leader=group.leader();owner.set(leader.leadershipStatus().localNodeId().value());
                long epoch=leader.leadershipStatus().promisedEpoch();
                var first=leader.add(new Doc(1,"first"));assertTrue(firstEntered.await(5,TimeUnit.SECONDS));
                CompletableFuture<?> second=mutation?leader.add(new Doc(2,"queued then proven")):
                        CompletableFuture.supplyAsync(()->leader.get(1));
                if(!mutation)assertTrue(readInvoked.await(3,TimeUnit.SECONDS));
                // Spend part of the second call's 9.6s public deadline in the
                // ordered queue. Its later protocol submission has its own deadline.
                Thread.sleep(5000);firstRelease.countDown();first.get(5,TimeUnit.SECONDS);
                assertTrue(secondEntered.await(3,TimeUnit.SECONDS));
                rejected(DEADLINE_EXCEEDED,mutation?INDETERMINATE:NOT_APPLICABLE,()->second.orTimeout(12,TimeUnit.SECONDS).join());
                secondRelease.countDown();
                long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(3);
                while(leader.leadershipStatus().appliedIndex()<chosen.get()&&System.nanoTime()<until)Thread.sleep(5);
                assertEquals(LEADER_READY,leader.leadershipStatus().state(),"client timeout cannot cancel the chosen protocol operation");
                assertEquals(epoch,leader.leadershipStatus().promisedEpoch());
                assertEquals(chosen.get(),leader.leadershipStatus().appliedIndex(),"chosen operation still publishes");
                assertEquals(mutation?2:1,leader.leadershipStatus().applicationSequence());
                assertEquals(mutation?new Doc(2,"queued then proven"):new Doc(1,"first"),leader.get(mutation?2:1));
                leader.add(new Doc(3,"following write")).get(5,TimeUnit.SECONDS);
                assertEquals(epoch,leader.leadershipStatus().promisedEpoch());
            } finally {firstRelease.countDown();secondRelease.countDown();AutomaticRuntimeHooks.CURRENT.remove();}
        }
    }
}
