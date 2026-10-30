package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.Objects;
import java.util.concurrent.TimeUnit;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Poll only explicit absence. Failures propagate; neither a delay nor a probe
 * renews the parent lifetime. This owns cancellation, not protocol authority. */
final class MembershipCompletionWait implements AutoCloseable {
    interface Probe extends AutoCloseable {boolean initialized()throws IOException;void close()throws IOException;}
    private final Probe probe;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget,interval;
    private final MembershipInitializationTask task;
    private volatile boolean closed;
    MembershipCompletionWait(Probe probe,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget,long intervalMillis,long drainMillis) {
        require(budget>0 && budget<Long.MAX_VALUE/2 && intervalMillis>0 && intervalMillis<=ReplicationBounds.HARD_MAX_REQUEST_TIMEOUT_MILLIS,
                "joining completion wait bounds");
        this.probe=Objects.requireNonNull(probe);this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;interval=TimeUnit.MILLISECONDS.toNanos(intervalMillis);task=new MembershipInitializationTask(drainMillis);
    }
    private long remaining()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining completion wait closed/original deadline");
        if(Thread.currentThread().isInterrupted())throw new IOException("joining completion wait interrupted");return budget-elapsed;
    }
    private void check()throws IOException {remaining();guard.check();remaining();}
    void run()throws IOException {
        task.execute(()->new MembershipInitializationTask.Action(){
            @Override public void run()throws IOException {
                for(;;) {
                    check();boolean found=probe.initialized();check();if(found)return;
                    long began=clock.getAsLong();
                    for(;;) {
                        check();long elapsed=clock.getAsLong()-began;require(elapsed>=0,"joining completion wait clock reversed");
                        long delay=Math.min(interval-elapsed,remaining());if(delay<=0)break;
                        try{synchronized(MembershipCompletionWait.this){if(!closed)TimeUnit.NANOSECONDS.timedWait(MembershipCompletionWait.this,delay);}}
                        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("joining completion wait interrupted",error);}
                    }
                }
            }
            @Override public void close()throws IOException{probe.close();}
        });remaining();
    }
    @Override public void close()throws IOException {
        synchronized(this){closed=true;notifyAll();}task.close();probe.close();
    }
}
