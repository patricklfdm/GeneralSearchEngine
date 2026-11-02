package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53NodeProcessDiagnosticsTest {
    @Test void reportsCapturedScopeFailureWithoutReevaluatingClockOrInventingElapsedTime() {
        var ended=new MembershipActivationEndpoint.InactiveScope(MembershipActivationEndpoint.ScopeGuard.SCOPE_ENDED,
            MembershipActivationEndpoint.ScopeEnd.CONTROL_TIMEOUT,Map.of("counter",4L),100,180,null);
        var row=object(V53NodeProcessDiagnostics.causes(ended).getFirst().get("scopeFailure"));
        assertEquals("SCOPE_ENDED",row.get("guard"));assertEquals("CONTROL_TIMEOUT",row.get("firstEnd"));
        assertEquals(false,row.get("clockEvaluated"));assertFalse(row.containsKey("elapsedNanos"));
        var deadline=new MembershipActivationEndpoint.InactiveScope(MembershipActivationEndpoint.ScopeGuard.DEADLINE,
            MembershipActivationEndpoint.ScopeEnd.NONE,Map.of("counter",4L),100,180,181L);
        row=object(V53NodeProcessDiagnostics.causes(deadline).getFirst().get("scopeFailure"));
        assertEquals(true,row.get("clockEvaluated"));assertEquals(181L,row.get("elapsedNanos"));assertEquals(180L,row.get("limitNanos"));
    }
    @Test void serviceStartIntervalDoesNotPretendToKnowTheInnerClockSample() {
        assertEquals(Map.of("startReturned",false),V53NodeProcessDiagnostics.serviceInterval(false,0,0,0));
        assertEquals(Map.of("startReturned",true,"elapsedLowerBoundNanos",80L,"elapsedUpperBoundNanos",90L,"startCallNanos",10L),
            V53NodeProcessDiagnostics.serviceInterval(true,10,20,100));
    }
    @Test void measuresQueueAndWorkSeparatelyAndRetainsActiveAck() {
        var clock=new AtomicLong(100);var meter=new V53NodeProcessDiagnostics.Meter(clock::get);
        var span=meter.begin("snapshot");clock.set(110);span.acquired();span.phase("ack");clock.set(135);
        var active=list(meter.snapshot().get("active"));
        assertEquals(Map.of("action","snapshot","phase","ack","elapsedNanos",35L,"queueNanos",10L,"workNanos",25L),active.getFirst());
        clock.set(140);span.success();span.close();span.close();
        assertEquals(Map.of("snapshot",Map.of("completed",1L,"failed",0L,"queueNanos",10L,"maxQueueNanos",10L,"workNanos",30L,"maxWorkNanos",30L)),meter.snapshot().get("completed"));
        assertEquals(List.of(),meter.snapshot().get("active"));
        assertEquals(true,meter.snapshot().get("durationsMayOverlap"));
    }
    @Test void pipeStillRequiresExactAckAndPreservesCanonicalMessages()throws Exception {
        var bytes=new ByteArrayOutputStream();var meter=new V53NodeProcessDiagnostics.Meter();
        var pipe=new V53NodeProcessWorker.Pipe(new BufferedReader(new StringReader("ACK\nwrong\n")),new PrintStream(bytes,true,StandardCharsets.UTF_8),meter);
        pipe.accept("event",Map.of("event","test"));
        assertThrows(IOException.class,()->pipe.accept("snapshot","test"));
        assertEquals("{\"action\":\"event\",\"value\":{\"event\":\"test\"}}\n{\"action\":\"snapshot\",\"value\":\"test\"}\n",bytes.toString(StandardCharsets.UTF_8));
        var done=object(meter.snapshot().get("completed"));
        assertEquals(0L,object(done.get("event")).get("failed"));assertEquals(1L,object(done.get("snapshot")).get("failed"));
    }
    @Test void blockedAckCanBeObservedWithoutAcquiringPipeMonitor()throws Exception {
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);var meter=new V53NodeProcessDiagnostics.Meter();
        var input=new BufferedReader(new StringReader("")) {
            @Override public String readLine()throws IOException {
                entered.countDown();try{if(!release.await(5,TimeUnit.SECONDS))throw new IOException("test ACK timeout");return "ACK";}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException(error);}
            }
        };
        var pipe=new V53NodeProcessWorker.Pipe(input,new PrintStream(OutputStream.nullOutputStream()),meter);
        try(var pool=Executors.newSingleThreadExecutor()) {
            var task=pool.submit(()->{pipe.accept("installed",Map.of());return null;});
            try {
                assertTrue(entered.await(5,TimeUnit.SECONDS));
                assertEquals("ack",object(list(meter.snapshot().get("active")).getFirst()).get("phase"));
                assertFalse(task.isDone());
            }finally{release.countDown();}
            task.get(5,TimeUnit.SECONDS);
        }
    }
    @Test void pipeWriteFailureDoesNotConsumeAnAck() {
        var meter=new V53NodeProcessDiagnostics.Meter();
        var pipe=new V53NodeProcessWorker.Pipe(new BufferedReader(new StringReader("ACK\n")) {
            @Override public String readLine(){fail("ACK consumed after write failure");return "ACK";}
        },new PrintStream(new OutputStream(){@Override public void write(int value)throws IOException{throw new IOException("closed");}}),meter);
        var failure=assertThrows(IOException.class,()->pipe.accept("event",Map.of()));
        assertEquals("parent observation write failed",failure.getMessage());
    }
    @Test void boundsActiveSamplesAndUnknownLabels() {
        var meter=new V53NodeProcessDiagnostics.Meter();var spans=new ArrayList<V53NodeProcessDiagnostics.Meter.Span>();
        for(int i=0;i<100;i++)spans.add(meter.begin("untrusted-"+i));
        assertEquals(16,list(meter.snapshot().get("active")).size());assertEquals(84L,meter.snapshot().get("omittedActiveSamples"));
        spans.forEach(V53NodeProcessDiagnostics.Meter.Span::close);
        assertEquals(Set.of("other"),object(meter.snapshot().get("completed")).keySet());
        assertEquals(100L,object(object(meter.snapshot().get("completed")).get("other")).get("failed"));
    }
    @Test void reportsBeforeCloseAndPreservesPrimaryAndBothSecondaryFailures()throws Exception {
        var primary=new TimeoutException("original wait");var diagnostic=new IOException("diagnostic failed");var close=new IOException("drain failed");
        var order=new ArrayList<String>();
        V53NodeProcessDiagnostics.finish(primary,()->{order.add("diagnostic");throw diagnostic;},()->{order.add("close");throw close;});
        assertEquals(List.of("diagnostic","close"),order);assertArrayEquals(new Throwable[]{diagnostic,close},primary.getSuppressed());
    }
    @Test void successDoesNotReportAndCloseOnlyFailureRemainsFatal() {
        var close=new IOException("drain failed");
        assertSame(close,assertThrows(IOException.class,()->V53NodeProcessDiagnostics.finish(null,()->fail("success reported as failure"),()->{throw close;})));
    }
    @Test void unavailableStateDoesNotBlockDiagnosticOrInventServiceState()throws Exception {
        var release=new CountDownLatch(1);
        try {
            var result=V53NodeProcessDiagnostics.sample(()->{
                try{release.await();return Map.of("serviceState","READY");}
                catch(InterruptedException error){Thread.currentThread().interrupt();return Map.of();}
            },20);
            assertEquals(Map.of("status","UNAVAILABLE","reason","state sample timeout"),result);
        }finally{release.countDown();}
    }
    @Test void interruptedSamplingRestoresInterruptAndFailedSamplingRetainsCause() {
        Thread.currentThread().interrupt();
        try {
            var result=V53NodeProcessDiagnostics.sample(()->Map.of(),250);
            // The completed task is permitted to win the race with interruption.
            assertTrue(Set.of("SAMPLED","UNAVAILABLE").contains(result.get("status")));assertTrue(Thread.currentThread().isInterrupted());
        }finally{Thread.interrupted();}
        var result=V53NodeProcessDiagnostics.sample(()->{throw new IllegalStateException("original state getter");},5000);
        assertEquals("UNAVAILABLE",result.get("status"));assertEquals("original state getter",object(list(result.get("failure")).getFirst()).get("message"));
    }
    @Test void cyclicAndOversizedCausesStayBounded() {
        var first=new IOException("x".repeat(10000));var next=new IOException("next",first);first.initCause(next);
        var causes=V53NodeProcessDiagnostics.causes(first);
        assertEquals(3,causes.size());assertEquals(Map.of("truncated",true),causes.getLast());
        assertTrue(((String)causes.getFirst().get("message")).length()<400);
        Throwable deep=new IOException("leaf");for(int i=0;i<10;i++)deep=new IOException("wrapper",deep);
        assertEquals(5,V53NodeProcessDiagnostics.causes(deep).size());
    }
    @Test void reportIsBoundedNonAuthorityAndRetainsFailureWithoutProtocolMessages() {
        var bytes=new ByteArrayOutputStream();var meter=new V53NodeProcessDiagnostics.Meter();
        V53NodeProcessDiagnostics.report(new PrintStream(bytes,true,StandardCharsets.UTF_8),"worker","startup-await",2,System.nanoTime(),
            new TimeoutException("original startup wait"),meter,()->Map.of("nodeState","OPEN","serviceState","RESTARTING","rounds",2,"losses",List.of("CONTACT_UNAVAILABLE")));
        var line=bytes.toString(StandardCharsets.UTF_8);assertTrue(line.startsWith("v53NodeProcessDiagnostic="));
        var parsed=object(parse(line.substring(line.indexOf('=')+1).strip().getBytes(StandardCharsets.UTF_8),65536));
        assertEquals(false,parsed.get("authority"));assertEquals("startup-await",parsed.get("phase"));assertEquals(2L,parsed.get("life"));
        assertEquals("SAMPLED",object(parsed.get("state")).get("status"));
        assertEquals("java.util.concurrent.TimeoutException",object(list(parsed.get("failure")).getFirst()).get("type"));
        assertFalse(parsed.containsKey("action"));assertFalse(parsed.containsKey("accepted"));
    }
}
