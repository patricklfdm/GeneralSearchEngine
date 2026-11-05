package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Files;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Pause an actual cancelled I/O worker after close returns on that worker.
 * No sleep/race is needed to distinguish cancellation from completed drain. */
class V53LearnerEndpointDrainTest {
    @TempDir Path temp;
    static final class Gate implements MembershipTransport.Events,AutoCloseable {
        final AtomicReference<AutoCloseable> endpoint=new AtomicReference<>();
        final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        @Override public void at(String event,MembershipFormat.Decoded request,MembershipFormat.Decoded response)throws IOException {
            if(!event.equals("BEFORE_RESPONSE_WRITE"))return;
            try{endpoint.get().close();}catch(Exception error){throw new IOException(error);}
            entered.countDown();boolean interrupted=Thread.interrupted();long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
            try {
                while(release.getCount()!=0) {
                    long left=until-System.nanoTime();if(left<=0)throw new IOException("test drain gate expired");
                    try{release.await(left,TimeUnit.NANOSECONDS);}catch(InterruptedException error){interrupted=true;}
                }
            }finally{if(interrupted)Thread.currentThread().interrupt();}
        }
        void reached()throws Exception{assertTrue(entered.await(15,TimeUnit.SECONDS),"callback did not reach close");}
        @Override public void close(){release.countDown();}
    }
    @Test void checkpointCancellationCannotAuthorizeAReplacementBeforeWorkerDrain()throws Exception {
        var helper=new V53LearnerCheckpointEndpointTest();helper.temp=temp;
        MembershipResources budget;
        try(var f=helper.new Fixture();var gate=new Gate()) {
            budget=f.fixture.f.local.source.client;
            try(var endpoint=f.listen(gate);var contact=f.contact()) {
                gate.endpoint.set(endpoint);var request=f.first();
                var pending=contact.exchange(f.local,request,"SOURCE_OFFER",System.nanoTime()+TimeUnit.SECONDS.toNanos(20));
                try {
                    gate.reached();assertTrue(endpoint.usage().closed());
                    assertFalse(endpoint.closed(),"cancelled worker is still inside the reply callback");
                    assertThrows(IllegalArgumentException.class,()->f.listen(MembershipTransport.Events.NONE));
                }finally{gate.close();}
                assertThrows(ExecutionException.class,()->pending.get(10,TimeUnit.SECONDS));
                endpoint.close();assertTrue(endpoint.closed());
                try(var replacement=f.listen(MembershipTransport.Events.NONE)) {
                    assertEquals("SOURCE_OFFER",replacement.answer(f.reader,f.first()).kind());
                }
            }
        }
        if(Boolean.getBoolean("v53.resource.learner.control.close")) {
            assertEquals(0,budget.usage().leases());var closes=budget.controlCloseObservations();assertFalse(closes.failed());assertFalse(closes.truncated());
            assertEquals(12,closes.rows().size());
            Path raw=Files.createDirectories(Path.of("target/v53-joining-close/run-"+UUID.randomUUID()));
            V53ResourceTraceFiles.write(raw.resolve("resources.json"),budget.observations());
            V53ResourceTraceFiles.writeCloses(raw.resolve("closes.json"),closes);
            System.out.println("v53JoiningCleanupObservations="+raw.toAbsolutePath());
        }
    }
    @Test void headCancellationIsNotACompletedListenerDrain()throws Exception {
        var helper=new V53LearnerMaterializationTest();helper.temp=temp;
        try(var f=helper.new Fixture();var typed=f.prepare(e->{});var gate=new Gate()) {
            var head=typed.retainGeneration();var voter=f.source.owner.activationIdentity();
            try(var endpoint=new MembershipLearnerHeadEndpoint(head,V53SourceExchangeTest.bounds(),gate);
                var contact=new MembershipTransport(head.source(),voter,V53SourceExchangeTest.bounds(),f.source.server,
                        (p,q)->{throw new IOException("read-only test contact");},MembershipTransport.Events.NONE)) {
                gate.endpoint.set(endpoint);var request=V53LearnerHeadProtocolTest.query(head,voter);
                var pending=contact.exchange(head.request().identity(),request,"LEARNER_HEAD_ACK",System.nanoTime()+TimeUnit.SECONDS.toNanos(20));
                try{gate.reached();assertFalse(endpoint.closed(),"cancelled head worker is still in its callback");}
                finally{gate.close();}
                assertThrows(ExecutionException.class,()->pending.get(10,TimeUnit.SECONDS));endpoint.close();assertTrue(endpoint.closed());
            }
        }
    }
}
