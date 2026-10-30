package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.Decoded;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One bounded automatic campaign/service lifetime. All protocol calls are
 * serialized; an error ends the lifetime, never replays a client mutation.
 * This private owner exposes no public read/leadership lease or user callbacks. */
final class MembershipAutomaticOwner implements AutoCloseable {
    enum State { NEW, STARTING, READY, FAILED, CLOSED }
    interface Session extends AutoCloseable {
        Decoded start(long originalStarted)throws IOException;
        void idle()throws IOException;
        void heartbeat()throws IOException;
        Decoded readiness()throws IOException;
        Decoded submit(String kind,byte[] bytes)throws IOException;
        @Override void close()throws IOException;
    }
    /** Waiting timeout does not cancel the admitted operation or change its
     * deadline. No externally executable completion callback runs on the owner. */
    static final class Call {
        private final CompletableFuture<Decoded> result=new CompletableFuture<>();
        Decoded await(long timeout,TimeUnit unit)throws InterruptedException,ExecutionException,TimeoutException {
            return result.get(timeout,unit);
        }
        boolean isDone(){return result.isDone();}
    }
    private final class Work implements AutoCloseable {
        final String kind;
        final byte[] bytes;
        final Call call=new Call();
        final MembershipResources.Lease waiter,input;
        Work(String kind,byte[] value) {
            this.kind=kind;String key="automatic-call-"+UUID.randomUUID();
            waiter=resources.reserve(MembershipResources.Unit.WAITER,key,0);
            MembershipResources.Lease held=null;
            try {
                // The fixed owner reservation covers at most 64 global waiter
                // headers; this lease covers the immutable body, even at FRAME.
                held=resources.reserve(MembershipResources.Unit.CONTROL,key,Math.max(1,value==null?0:value.length));
                bytes=value==null?null:value.clone();input=held;
            }catch(RuntimeException|Error error){if(held!=null)held.close();waiter.close();throw error;}
        }
        @Override public void close(){input.close();waiter.close();}
    }
    private final Session session;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final LongSupplier clock;
    private final long budget,interval;
    private final MembershipResources.Lease ownership;
    private final ArrayDeque<Work> queue=new ArrayDeque<>();
    private final Call started=new Call();
    private Thread worker;
    private State state=State.NEW;
    private boolean closed,terminated;
    private Throwable failure;
    private int pending;
    private long began;

    MembershipAutomaticOwner(Session session,MembershipResources resources,ReplicationBounds bounds,AutomaticLeadershipPolicy policy,
            LongSupplier clock,long budget) {
        require(budget>0 && budget<Long.MAX_VALUE/2,"automatic owner budget");
        this.session=Objects.requireNonNull(session);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.clock=Objects.requireNonNull(clock);this.budget=budget;interval=TimeUnit.MILLISECONDS.toNanos(policy.heartbeatIntervalMillis());
        ownership=resources.reserve(MembershipResources.Unit.CONTROL,"automatic-loop-owner",65536);
    }
    synchronized State state(){return state;}
    synchronized Optional<Throwable> failure(){return Optional.ofNullable(failure);}
    synchronized int pending(){return pending;}
    synchronized Call start() {
        require(!closed && state==State.NEW,"automatic owner single start");
        began=clock.getAsLong();state=State.STARTING;
        worker=Thread.ofPlatform().daemon().name("gse-membership-automatic-owner").unstarted(this::loop);
        try{worker.start();}catch(RuntimeException|Error error){worker=null;state=State.FAILED;failure=error;started.result.completeExceptionally(error);throw error;}
        return started;
    }
    Call submit(String kind,byte[] value){MembershipRoundDriver.validateInput(kind,value,bounds);return enqueue(kind,value);}
    Call readiness(){return enqueue(null,null);}
    private synchronized Call enqueue(String kind,byte[] bytes) {
        require(!closed && state==State.READY,"automatic owner not ready");
        require(pending<bounds.maxPendingClientOperations(),"automatic owner pending capacity");
        var work=new Work(kind,bytes);
        try{queue.addLast(work);pending++;notifyAll();return work.call;}
        catch(RuntimeException|Error error){work.close();throw error;}
    }
    private synchronized long time()throws IOException {
        if(closed || Thread.currentThread().isInterrupted())throw new IOException("automatic owner closed/interrupted");
        long now=clock.getAsLong(),elapsed=now-began;
        require(elapsed>=0 && elapsed<budget,"automatic owner original deadline");return now;
    }
    private void loop() {
        Throwable stopped=null;
        try {
            time();var barrier=session.start(began);long lastHeartbeat=time();
            synchronized(this){require(!closed,"automatic owner closed before ready");state=State.READY;}
            // Arm before exposing startup completion: a caller waking and
            // advancing the clock must not postpone the first due heartbeat.
            started.result.complete(barrier);
            for(;;) {
                long now=time();session.idle();now=time();
                // Due heartbeats precede queued commands, but a slow sample is
                // not followed by a burst of missed ticks. It grants no lease.
                if(now-lastHeartbeat>=interval){session.heartbeat();lastHeartbeat=time();continue;}
                Work work;
                synchronized(this) {
                    time();work=queue.pollFirst();
                    if(work==null) {
                        long remaining=Math.min(budget-(now-began),interval-(now-lastHeartbeat));
                        TimeUnit.NANOSECONDS.timedWait(this,Math.min(remaining,TimeUnit.MILLISECONDS.toNanos(50)));continue;
                    }
                }
                try {
                    time();var result=work.kind==null?session.readiness():session.submit(work.kind,work.bytes);time();
                    work.call.result.complete(result);
                }catch(IOException|RuntimeException|Error error){work.call.result.completeExceptionally(error);throw error;}
                finally{work.close();synchronized(this){pending--;}}
            }
        }catch(InterruptedException error){Thread.currentThread().interrupt();stopped=new IOException("automatic owner interrupted",error);}
        catch(IOException|RuntimeException|Error error){stopped=error;}
        finally {
            if(stopped==null)stopped=new IOException("automatic owner stopped");
            synchronized(this){if(!closed){state=State.FAILED;failure=stopped;}}
            started.result.completeExceptionally(stopped);rejectQueued(stopped);
            boolean drained=false;
            try{session.close();drained=true;}
            catch(IOException|RuntimeException|Error error){stopped.addSuppressed(error);synchronized(this){failure=stopped;}}
            if(drained)ownership.close();
            synchronized(this){terminated=true;notifyAll();}
        }
    }
    private void rejectQueued(Throwable error) {
        List<Work> rejected;
        synchronized(this){rejected=new ArrayList<>(queue);queue.clear();pending-=rejected.size();}
        for(var work:rejected){work.close();work.call.result.completeExceptionally(error);}
    }
    @Override public void close()throws IOException {
        Thread active;
        synchronized(this){closed=true;state=State.CLOSED;active=worker;notifyAll();}
        var error=new IOException("automatic owner closed");started.result.completeExceptionally(error);rejectQueued(error);
        // Native close owns cancellation and drain, including discovery's
        // special handling. Do not blindly interrupt that child from here.
        session.close();
        if(active==Thread.currentThread())return;
        if(active!=null) {
            long end=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
            try{synchronized(this){while(!terminated){long left=end-System.nanoTime();
                if(left<=0)throw new IOException("automatic owner close drain deadline");TimeUnit.NANOSECONDS.timedWait(this,left);}}}
            catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new IOException("automatic owner close interrupted",interrupted);}
        }
        ownership.close();
    }
}
