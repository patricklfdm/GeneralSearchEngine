package io.github.patricklfdm.generalsearch.admission;

import io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.*;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Deterministic consumer shutdown checks against both unchanged public APIs. */
public final class V52MeasurementCloseProbe {
    private static void need(boolean value,String message){if(!value)throw new AssertionError(message);}
    private static AutomaticReplicationException timeout(){return new AutomaticReplicationException(DEADLINE_EXCEEDED,NOT_APPLICABLE,Optional.empty(),"runtime close pending",new TimeoutException());}
    private static final class World {
        final AtomicLong now=new AtomicLong();final AtomicInteger calls=new AtomicInteger();
        final List<Map<String,Object>> events=new ArrayList<>();
        World(){V52MeasurementConsumer.observer=(event,row)->{var value=new LinkedHashMap<String,Object>(row);value.put("event",event);events.add(value);};}
        V52MeasurementConsumer.Close close(Runnable action){return new V52MeasurementConsumer.Close(()->{calls.incrementAndGet();action.run();},now::get,ms->now.addAndGet(ms*1_000_000));}
        long count(String event){return events.stream().filter(v->v.get("event").equals(event)).count();}
        void stopped(int attempts,int failures,boolean closed){need(calls.get()==attempts && count("CLIENT_CLOSE_ATTEMPT")==attempts && count("CLIENT_CLOSE_FAILURE")==failures && count("CLOSED")== (closed?1:0),"close accounting");}
    }
    public static void main(String[] args) throws Exception {
        var checks=new ArrayList<String>();
        {
            var w=new World();try(var close=w.close(()->{})){close.close();close.close();}w.stopped(1,0,true);checks.add("single-success-and-no-implicit-repeat");
        }
        {
            var w=new World();try(var close=w.close(()->{if(w.calls.get()<3)throw timeout();})){close.close();}
            w.stopped(3,2,true);need(w.now.get()==200_000_000 && w.events.get(w.events.size()-1).get("closeAttempts").equals(3),"timeout retry accounting");
            checks.add("timeouts-then-success");
        }
        {
            var w=new World();AutomaticReplicationException caught=null;
            try(var close=w.close(()->{throw timeout();})){close.close();}catch(AutomaticReplicationException e){caught=e;}
            w.stopped(8,8,false);need(caught!=null && caught.getSuppressed().length==7,"retain exhausted close failures");checks.add("attempt-exhaustion-no-ninth-close");
        }
        for(boolean afterPause:List.of(false,true)) {
            var w=new World();var failure=timeout();Throwable caught=null;
            try(var close=w.close(()->{w.now.set((20_000L-(afterPause?50:0))*1_000_000);throw failure;})){close.close();}catch(Throwable e){caught=e;}
            w.stopped(1,1,false);need(caught==failure,"retry window failure identity");checks.add(afterPause?"window-expired-during-backoff":"window-exhaustion");
        }
        for(RuntimeException failure:List.of(
                new AutomaticReplicationException(STORAGE_FAILURE,NOT_APPLICABLE,Optional.empty(),"storage"),
                new AutomaticReplicationException(INTEGRITY_FAILURE,NOT_APPLICABLE,Optional.empty(),"integrity"),
                new AutomaticReplicationException(DEADLINE_EXCEEDED,INDETERMINATE,Optional.empty(),"wrong outcome"),
                new AutomaticReplicationException(DEADLINE_EXCEEDED,NOT_APPLICABLE,Optional.empty(),"wrapped storage",new ExecutionException(new IOException("storage"))),
                new IllegalStateException("observer failure"),new CancellationException("cancelled"))) {
            var w=new World();Throwable caught=null;
            try(var close=w.close(()->{throw failure;})){close.close();}catch(Throwable e){caught=e;}
            w.stopped(1,failure instanceof AutomaticReplicationException?1:0,false);need(caught==failure,"nonretryable identity");
        }
        checks.add("non-timeout-outcome-and-cause-fail-fast");
        {
            var w=new World();var failure=timeout();Throwable caught=null;Thread.currentThread().interrupt();
            try(var close=w.close(()->{throw failure;})){close.close();}catch(Throwable e){caught=e;}
            need(Thread.currentThread().isInterrupted(),"lost interrupt");Thread.interrupted();w.stopped(1,1,false);need(caught==failure,"interrupted retry");checks.add("interrupted-close-no-retry");
        }
        {
            var w=new World();Throwable caught=null;var failure=timeout();
            try(var close=new V52MeasurementConsumer.Close(()->{w.calls.incrementAndGet();throw failure;},w.now::get,ms->{throw new InterruptedException("pause");})){close.close();}
            catch(Throwable e){caught=e;}
            need(caught instanceof InterruptedException && Thread.currentThread().isInterrupted() && caught.getSuppressed()[0]==failure,"interrupted backoff");
            Thread.interrupted();w.stopped(1,1,false);checks.add("interrupted-backoff-retains-timeout");
        }
        for(boolean cleanupFails:List.of(false,true)) {
            var w=new World();var original=new IllegalStateException("original workload failure");Throwable caught=null;
            try(var close=w.close(()->{if(cleanupFails)throw timeout();})){throw original;}catch(Throwable e){caught=e;}
            need(caught==original && caught.getSuppressed().length==(cleanupFails?1:0),"original failure replaced");
            w.stopped(cleanupFails?8:1,cleanupFails?8:0,!cleanupFails);checks.add(cleanupFails?"original-failure-with-exhausted-cleanup":"original-failure-with-clean-cleanup");
        }
        {
            var w=new World();var repeated=timeout();Throwable caught=null;
            try(var close=w.close(()->{throw repeated;})){close.close();}catch(Throwable e){caught=e;}
            need(caught==repeated && caught.getSuppressed().length==0,"self suppression");w.stopped(8,8,false);checks.add("same-timeout-object-no-self-suppression");
        }
        V52MeasurementConsumer.observer=(event,row)->{};
        System.out.println(AdmissionJson.canonical(Map.of("status","PASS","execution","consumer-close-policy-only","checks",checks,
                "policy",Map.of("attempts",V52MeasurementConsumer.Close.ATTEMPTS,"retryWindowMillis",V52MeasurementConsumer.Close.WINDOW_MILLIS,
                "backoffMillis",V52MeasurementConsumer.Close.BACKOFF_MILLIS,"retryReason","DEADLINE_EXCEEDED","retryOutcome","NOT_APPLICABLE"))));
    }
}
