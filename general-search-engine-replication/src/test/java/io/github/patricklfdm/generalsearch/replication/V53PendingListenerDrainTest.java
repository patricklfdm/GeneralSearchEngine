package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Original retained storage must outlive a cancelled callback and an
 * interrupted external closer. Historical authority is a conditional fixture. */
class V53PendingListenerDrainTest {
    @TempDir Path temp;
    static Map<String,Object> storage(MembershipResources.Usage usage) {
        var counts=new TreeMap<String,Integer>();usage.counts().forEach((unit,count)->{if(unit!=MembershipResources.Unit.CONTROL && unit!=MembershipResources.Unit.WAITER)counts.put(unit.name(),count);});
        return Map.of("metadata",usage.metadata(),"staging",usage.staging(),"counts",counts);
    }
    static List<Map<String,String>> inventory(Path root)throws IOException {
        return V53ReplayFilesTest.files(root).entrySet().stream().map(v->Map.of("path",v.getKey(),"sha256",v.getValue())).toList();
    }
    static final class Capture {
        final MembershipResources budget;final boolean enabled;final List<Map<String,Object>> rows=new ArrayList<>();
        Capture(MembershipResources budget,MembershipResourceObservations.Checkpoint initial) {
            this.budget=budget;enabled=initial!=null;if(enabled)point("BASELINE",initial,null,false);
        }
        synchronized void point(String event,MembershipResourceObservations.Checkpoint point,Throwable error,boolean interrupted) {
            assertTrue(point.complete());rows.add(Map.of("event",event,"sequence",point.sequence(),"usage",V53ResourceTraceFiles.usage(point.usage()),
                    "error",error==null?"":error.getClass().getName()+": "+error.getMessage(),"interrupted",interrupted));
        }
        void mark(String event,Throwable error,boolean interrupted){if(enabled)point(event,budget.observationCheckpoint(),error,interrupted);}
    }
    static final class Gate implements MembershipTransport.Events,AutoCloseable {
        final CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);
        final AtomicReference<Throwable> failure=new AtomicReference<>();final AtomicReference<Map<String,Object>> held=new AtomicReference<>();
        final AutoCloseable owner;final Capture capture;final boolean callback;
        Gate(AutoCloseable owner,Capture capture,boolean callback){this.owner=owner;this.capture=capture;this.callback=callback;}
        void attemptClose() {
            capture.mark("OWNER_CLOSE_BEGIN",null,Thread.currentThread().isInterrupted());
            try{owner.close();}catch(Throwable error){failure.set(error);}
            capture.mark("OWNER_CLOSE_FAILED",failure.get(),Thread.currentThread().isInterrupted());
        }
        @Override public void at(String event,Decoded request,Decoded response)throws IOException {
            if(!event.equals("BEFORE_RESPONSE_WRITE"))return;
            held.set(storage(capture.budget.usage()));capture.mark("REQUEST_HELD",null,false);
            if(callback)attemptClose();entered.countDown();
            boolean interrupted=Thread.interrupted();long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
            try {
                while(release.getCount()!=0) {
                    long left=until-System.nanoTime();if(left<=0)throw new IOException("pending drain gate expired");
                    try{release.await(left,TimeUnit.NANOSECONDS);}catch(InterruptedException e){interrupted=true;}
                }
            }finally{if(interrupted)Thread.currentThread().interrupt();}
        }
        @Override public void close(){release.countDown();}
    }
    @ParameterizedTest @ValueSource(strings={"checkpoint","head"})
    void callbackCloseRetainsStorageUntilAnExternalCloserDrains(String listener)throws Exception {run(listener,true);}
    @ParameterizedTest @ValueSource(strings={"checkpoint","head"})
    void interruptedExternalCloseRetainsStorageForTheSameOwnerRetry(String listener)throws Exception {run(listener,false);}
    private void run(String listener,boolean callback)throws Exception {
        var helper=new V53LearnerCheckpointEndpointTest();helper.temp=temp;Capture capture=null;
        var inventories=new TreeMap<String,Object>();Throwable failure=null;
        Path raw=Boolean.getBoolean("v53.resource.learner.control.close")?
                Files.createDirectories(Path.of("target/v53-pending-drain/run-"+UUID.randomUUID())):null;
        if(raw!=null)System.out.println("v53PendingDrainEvidence="+raw.toAbsolutePath()+" listener="+listener+" callback="+callback);
        try(var f=helper.new Fixture()) {
            capture=new Capture(f.fixture.f.local.source.client,f.baselineObservation);
            try(var gate=new Gate(f.pending,capture,callback)) {
                MembershipLearnerCheckpointEndpoint checkpoint=null;MembershipLearnerHeadEndpoint head=null;
                try {
                    if(listener.equals("checkpoint"))checkpoint=f.listen(gate);
                    else{f.pending.endorse();head=f.pending.retainSource().listenHead(f.fixture.f.local.config.bounds(),gate);}
                    inventories.put("before",inventory(f.fixture.directory()));
                    try(var contact=f.contact()) {
                        var request=listener.equals("checkpoint")?f.first():V53LearnerHeadProtocolTest.query(f.fixture.f.head,f.reader);
                        var pending=contact.exchange(f.local,request,listener.equals("checkpoint")?"SOURCE_OFFER":"LEARNER_HEAD_ACK",System.nanoTime()+TimeUnit.SECONDS.toNanos(20));
                        try {
                            assertTrue(gate.entered.await(15,TimeUnit.SECONDS));
                            if(!callback) {
                                var interruptPreserved=new AtomicBoolean();
                                Thread closer=Thread.ofPlatform().start(()->{
                                    Thread.currentThread().interrupt();gate.attemptClose();interruptPreserved.set(Thread.currentThread().isInterrupted());Thread.interrupted();
                                });closer.join(10000);assertFalse(closer.isAlive());assertTrue(interruptPreserved.get());
                            }
                            var error=gate.failure.get();
                            if(callback)assertEquals("joining "+(listener.equals("checkpoint")?"checkpoint":"progress")+" listener not drained",assertInstanceOf(IOException.class,error).getMessage());
                            else assertEquals("membership transport close interrupted",assertInstanceOf(IllegalStateException.class,error).getMessage());
                            assertEquals(gate.held.get(),storage(capture.budget.usage()),"retained storage released before listener drain");
                            inventories.put("afterFailure",inventory(f.fixture.directory()));
                            assertEquals(inventories.get("before"),inventories.get("afterFailure"));
                            assertThrows(IllegalArgumentException.class,f.pending::source);
                        }finally{gate.close();}
                        assertThrows(ExecutionException.class,()->pending.get(10,TimeUnit.SECONDS));
                        capture.mark("RETRY_CLOSE_BEGIN",null,false);f.pending.close();capture.mark("OWNER_CLOSE_RETURNED",null,false);
                        assertEquals(f.baseline,capture.budget.usage());
                        inventories.put("afterSuccess",inventory(f.fixture.directory()));assertEquals(inventories.get("before"),inventories.get("afterSuccess"));
                    }
                }finally{gate.close();if(checkpoint!=null)checkpoint.close();if(head!=null)head.close();}
            }
        }catch(Throwable error){failure=error;throw error;}
        finally {
            if(raw!=null && capture!=null) {
                capture.mark("FIXTURE_CLOSED",null,false);assertEquals(0,capture.budget.usage().leases());
                V53ResourceTraceFiles.write(raw.resolve("resources.json"),capture.budget.observations());
                Files.write(raw.resolve("history.json"),canonical(Map.of("schema","gse-v53-pending-drain-v1","listener",listener,"mode",callback?"callback":"interrupt",
                        "status",failure==null?"PASS":"FAIL","rows",capture.rows,"inventories",inventories,"completeMembershipHistory",false),4*1024*1024));
            }
        }
    }
}
