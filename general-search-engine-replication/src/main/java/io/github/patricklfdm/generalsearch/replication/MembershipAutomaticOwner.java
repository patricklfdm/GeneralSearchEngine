package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.Decoded;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One bounded automatic service lifetime. All protocol calls are serialized;
 * typed campaign loss may start a fresh round, never replay a client mutation.
 * This private owner exposes no public read/leadership lease or user callbacks. */
final class MembershipAutomaticOwner implements AutoCloseable {
    enum State { NEW, STARTING, READY, RESTARTING, FAILED, CLOSED }
    interface Session extends AutoCloseable {
        Decoded start(long originalStarted)throws IOException;
        void idle()throws IOException;
        MembershipHeartbeatRound.Contact heartbeat()throws IOException;
        Decoded readiness()throws IOException;
        Decoded submit(String kind,byte[] bytes)throws IOException;
        @Override void close()throws IOException;
    }
    @FunctionalInterface interface Factory {Session open()throws IOException;}
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
    private Session session;
    private final Factory next;
    private final int maximumRounds;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final LongSupplier clock;
    private final long budget,interval;
    private final MembershipResources.Lease ownership;
    private final ArrayDeque<Work> queue=new ArrayDeque<>();
    private final List<MembershipCampaignLost.Reason> losses=new ArrayList<>();
    private final Call started=new Call();
    private Thread worker;
    private State state=State.NEW;
    private boolean closed,terminated;
    private Throwable failure;
    private int pending,rounds;
    private long began;

    MembershipAutomaticOwner(Session session,MembershipResources resources,ReplicationBounds bounds,AutomaticLeadershipPolicy policy,
            LongSupplier clock,long budget) {
        this(session,()->{throw new IOException("automatic owner has no next round");},1,resources,bounds,policy,clock,budget);
    }
    MembershipAutomaticOwner(Session session,Factory next,int maximumRounds,MembershipResources resources,ReplicationBounds bounds,
            AutomaticLeadershipPolicy policy,LongSupplier clock,long budget) {
        require(budget>0 && budget<Long.MAX_VALUE/2,"automatic owner budget");
        this.session=Objects.requireNonNull(session);this.next=Objects.requireNonNull(next);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        require(maximumRounds>0 && maximumRounds<=Math.min(MembershipResources.Unit.SOURCE.count,bounds.maxRetryAttempts()),"automatic owner round count");
        this.maximumRounds=maximumRounds;
        this.clock=Objects.requireNonNull(clock);this.budget=budget;interval=TimeUnit.MILLISECONDS.toNanos(policy.heartbeatIntervalMillis());
        ownership=resources.reserve(MembershipResources.Unit.CONTROL,"automatic-loop-owner",65536);
    }
    synchronized State state(){return state;}
    synchronized Optional<Throwable> failure(){return Optional.ofNullable(failure);}
    synchronized int pending(){return pending;}
    synchronized int rounds(){return rounds;}
    synchronized List<MembershipCampaignLost.Reason> losses(){return List.copyOf(losses);}
    synchronized boolean drained(){return closed && session==null && pending==0 && (worker==null || !worker.isAlive());}
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
    private void serve(Session current)throws IOException,InterruptedException {
            time();var barrier=current.start(began);long lastHeartbeat=time();
            synchronized(this){require(!closed,"automatic owner closed before ready");state=State.READY;}
            // Arm before exposing startup completion: a caller waking and
            // advancing the clock must not postpone the first due heartbeat.
            started.result.complete(barrier);
            for(;;) {
                long now=time();current.idle();now=time();
                // Due heartbeats precede queued commands, but a slow sample is
                // not followed by a burst of missed ticks. It grants no lease.
                if(now-lastHeartbeat>=interval){current.heartbeat();lastHeartbeat=time();continue;}
                Work work;
                synchronized(this) {
                    time();work=queue.pollFirst();
                    if(work==null) {
                        long remaining=Math.min(budget-(now-began),interval-(now-lastHeartbeat));
                        TimeUnit.NANOSECONDS.timedWait(this,Math.min(remaining,TimeUnit.MILLISECONDS.toNanos(50)));continue;
                    }
                }
                try {
                    time();var result=work.kind==null?current.readiness():current.submit(work.kind,work.bytes);time();
                    work.call.result.complete(result);
                }catch(IOException|RuntimeException|Error error){work.call.result.completeExceptionally(error);throw error;}
                finally{work.close();synchronized(this){pending--;}}
            }
    }
    private void closeSession()throws IOException {
        Session current;synchronized(this){current=session;}
        if(current!=null) {
            current.close(); // A failed drain retains the exact child reference.
            synchronized(this){if(session==current)session=null;}
        }
    }
    private void loop() {
        Throwable stopped=null;
        try {
            for(;;) {
                Session current;synchronized(this){current=session;rounds++;}
                try{serve(current);}
                catch(MembershipCampaignLost lost) {
                    // Do not infer retryability from message text or a nested
                    // cause. Cleanup/integrity failures remain terminal.
                    synchronized(this) {
                        losses.add(lost.reason);
                        if(closed || rounds>=maximumRounds || lost.getSuppressed().length!=0)throw lost;
                        state=State.RESTARTING;
                    }
                    rejectQueued(lost);
                    try{closeSession();}catch(IOException|RuntimeException|Error cleanup){lost.addSuppressed(cleanup);throw lost;}
                    time();var fresh=Objects.requireNonNull(next.open());
                    synchronized(this){session=fresh;}
                    require(fresh!=current,"automatic owner must open a fresh session");time();
                    // The next start receives began, not the retry's clock.
                }
            }
        }catch(InterruptedException error){Thread.currentThread().interrupt();stopped=new IOException("automatic owner interrupted",error);}
        catch(IOException|RuntimeException|Error error){stopped=error;}
        finally {
            if(stopped==null)stopped=new IOException("automatic owner stopped");
            synchronized(this){if(!closed){state=State.FAILED;failure=stopped;}}
            started.result.completeExceptionally(stopped);rejectQueued(stopped);
            boolean drained=false;
            try{closeSession();drained=true;}
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
        closeSession();
        if(active==Thread.currentThread())return;
        if(active!=null) {
            long end=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
            try{synchronized(this){while(!terminated){long left=end-System.nanoTime();
                if(left<=0)throw new IOException("automatic owner close drain deadline");TimeUnit.NANOSECONDS.timedWait(this,left);}}}
            catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new IOException("automatic owner close interrupted",interrupted);}
            try {
                long left=end-System.nanoTime();if(active.isAlive() && left>0)TimeUnit.NANOSECONDS.timedJoin(active,left);
                if(active.isAlive())throw new IOException("automatic owner thread drain deadline");
            }catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new IOException("automatic owner close interrupted",interrupted);}
        }
        ownership.close();
    }
}
