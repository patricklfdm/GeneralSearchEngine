package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.NOT_APPLICABLE;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;

/** Bounded request ownership. The supplied lock is the runtime's protocol capture monitor. */
final class AutomaticReadQueue<K,T> {
    interface Access<K,T> {
        void check(ReplicaReadOptions options);
        long publishedIndex(); // eligibility hint only; capture must inspect the actual application
        AutomaticReadCut capture(ReplicaReadOptions options, long epoch, long barrierIndex);
        <R> R read(AutomaticReadCut cut, Function<ReplicaReadView<K,T>,R> action);
    }
    interface Alarm { void cancel(); }
    interface Timer { Alarm schedule(long deadlineNanos, Runnable task); }
    record Counts(int owned, int waiting, int captured, int settling, int alarms, int marker, int highWater) { }
    private enum Phase { QUEUED, CAPTURED, SETTLING }

    private final Object lock;
    private final AutomaticReadCut identity;
    private final Access<K,T> access;
    private final Semaphore admission;
    private final int limit;
    private final LongSupplier clock;
    private final Timer timer;
    private final Executor dispatch, completions; // both must dispatch asynchronously
    private final LinkedHashSet<Request<?>> owned = new LinkedHashSet<>();
    private boolean marker, closed;
    private int highWater;

    AutomaticReadQueue(Object lock, AutomaticReadCut identity, Access<K,T> access,
                       Semaphore admission, int pendingBound, LongSupplier clock,
                       Timer timer, Executor dispatch, Executor completions) {
        if (pendingBound < 1) throw new IllegalArgumentException("pending bound");
        this.lock=lock; this.identity=identity; this.access=access; this.admission=admission;
        limit=Math.min(64,pendingBound-1); this.clock=clock; this.timer=timer;
        this.dispatch=dispatch; this.completions=completions;
    }

    private static AutomaticReplicationException failure(AutomaticReplicationException.Reason reason) {
        return new AutomaticReplicationException(reason,NOT_APPLICABLE,Optional.empty(),"replica read "+reason);
    }

    final class Request<R> {
        final ReplicaReadOptions options;
        final long deadline;
        Function<ReplicaReadView<K,T>,R> action;
        Phase phase=Phase.QUEUED;
        Alarm alarm;
        long epoch, barrierIndex;
        boolean barrierReady, preparing, cancelled, completionReturned;
        int cancelling;
        final CompletableFuture<ReplicaReadResult<R>> result=new CompletableFuture<>() {
            @Override public boolean cancel(boolean mayInterruptIfRunning) {
                synchronized(lock) {
                    if(isDone())return isCancelled();
                    cancelled=true; cancelling++;
                }
                // Future handlers can execute here; never call them under the protocol monitor.
                try {return super.cancel(false);}
                finally {synchronized(lock) {
                    cancelling--;
                    if(owned.contains(Request.this)&&phase==Phase.QUEUED)
                        settle(Request.this,null,new CancellationException());
                    releaseIfComplete(Request.this);
                }}
            }
        };

        Request(ReplicaReadOptions options,Function<ReplicaReadView<K,T>,R> action,long deadline) {
            this.options=options; this.action=action; this.deadline=deadline;
            preparing=options.policy()==ReplicaReadPolicy.LEADER_STRONG;
        }
        CompletableFuture<ReplicaReadResult<R>> future() {return result;}
        /** Only the existing fresh NO_OP barrier may supply these values. */
        void barrier(long epoch,long index) {
            synchronized(lock) {
                preparing=false;
                if(!owned.contains(this)||phase!=Phase.QUEUED){releaseIfComplete(this);return;}
                if(options.policy()!=ReplicaReadPolicy.LEADER_STRONG||barrierReady)
                    throw new IllegalStateException("unexpected replica read barrier");
                this.epoch=epoch; barrierIndex=index; barrierReady=true;
                changedLocked();
            }
        }
        void fail(Throwable error) {
            synchronized(lock) {
                preparing=false;
                if(owned.contains(this)&&phase==Phase.QUEUED)settle(this,null,error);
                releaseIfComplete(this);
            }
        }
    }

    <R> Request<R> submit(ReplicaReadOptions options,Function<ReplicaReadView<K,T>,R> action,long deadline) {
        Objects.requireNonNull(options); Objects.requireNonNull(action);
        var request=new Request<>(options,action,deadline);
        Throwable rejected=null;
        synchronized(lock) {
            try {
                check(request); // identity and state precede both capacity checks
                if(owned.size()>=limit||!admission.tryAcquire())throw failure(CAPACITY_EXCEEDED);
                owned.add(request); highWater=Math.max(highWater,owned.size());
                try {
                    request.alarm=timer.schedule(deadline,()->expire(request));
                    changedLocked(); // register/recheck under the same publication/capture boundary
                } catch(Throwable error) {settle(request,null,infrastructureFailure(error));}
            } catch(Throwable error) {rejected=error; request.action=null;}
        }
        if(rejected!=null)request.result.completeExceptionally(rejected);
        return request;
    }

    private void check(Request<?> request) {
        if(closed)throw failure(CLOSED);
        access.check(request.options);
        request.options.minimum().ifPresent(identity::compatible);
        if(clock.getAsLong()>=request.deadline)throw failure(DEADLINE_EXCEEDED);
    }

    private Throwable infrastructureFailure(Throwable error) {
        return error instanceof RejectedExecutionException ? failure(closed?CLOSED:CAPACITY_EXCEEDED) : error;
    }

    private boolean ready(Request<?> request) {
        return request.options.policy()==ReplicaReadPolicy.LEADER_STRONG ? request.barrierReady :
                request.options.policy()==ReplicaReadPolicy.STALE_ALLOWED || request.options.waitTimeoutMillis()==0 ||
                access.publishedIndex()>=request.options.minimum().orElseThrow().index();
    }

    void changed() {synchronized(lock) {changedLocked();}}
    private void changedLocked() {
        boolean eligible=false;
        for(var request:List.copyOf(owned))if(request.phase==Phase.QUEUED) {
            try {
                check(request);
                if(request.cancelled)settle(request,null,new CancellationException());
                else eligible|=ready(request);
            } catch(Throwable error) {settle(request,null,error);}
        }
        if(eligible&&!marker) {
            marker=true;
            try {dispatch.execute(this::turn);}
            catch(Throwable error) {
                marker=false;
                for(var request:List.copyOf(owned))if(request.phase==Phase.QUEUED)settle(request,null,infrastructureFailure(error));
            }
        }
    }

    private void expire(Request<?> request) {
        synchronized(lock) {
            if(owned.contains(request)&&request.phase==Phase.QUEUED&&clock.getAsLong()>=request.deadline)
                settle(request,null,failure(DEADLINE_EXCEEDED));
        }
    }

    private void turn() {
        Request<?> selected=null; AutomaticReadCut cut=null;
        synchronized(lock) {
            marker=false;
            for(var request:List.copyOf(owned))if(request.phase==Phase.QUEUED) {
                try {
                    check(request);
                    if(request.cancelled){settle(request,null,new CancellationException());continue;}
                    if(!ready(request))continue;
                    var captured=access.capture(request.options,request.epoch,request.barrierIndex);
                    check(request); // capture observation itself may have consumed the remaining deadline
                    if(request.options.policy()==ReplicaReadPolicy.AT_LEAST_INDEX) {
                        var minimum=request.options.minimum().orElseThrow(); captured.compatible(minimum);
                        if(captured.index()<minimum.index()) {
                            if(request.options.waitTimeoutMillis()>0)continue;
                            throw new ReplicaReadException(ReplicaReadException.Reason.PROGRESS_NOT_REACHED,"published read index is below the requested minimum");
                        }
                    }
                    request.phase=Phase.CAPTURED; cancelAlarm(request); selected=request; cut=captured; break;
                } catch(Throwable error) {settle(request,null,error);}
            }
        }
        if(selected!=null)invoke(selected,cut);
        synchronized(lock) {changedLocked();}
    }

    private <R> void invoke(Request<R> request,AutomaticReadCut cut) {
        ReplicaReadResult<R> value=null; Throwable failed=null;
        try {value=new ReplicaReadResult<>(access.read(cut,request.action),request.options.policy(),cut.token(),cut.sequence());}
        catch(Throwable error) {failed=error;}
        synchronized(lock) {settle(request,value,failed);}
    }

    private void cancelAlarm(Request<?> request) {
        if(request.alarm!=null){request.alarm.cancel();request.alarm=null;}
    }
    private <R> void settle(Request<R> request,ReplicaReadResult<R> value,Throwable error) {
        if(request.phase==Phase.SETTLING)return;
        request.phase=Phase.SETTLING; request.action=null; cancelAlarm(request);
        completions.execute(()->{
            try {if(error==null)request.result.complete(value);else request.result.completeExceptionally(error);}
            finally {synchronized(lock) {request.completionReturned=true;releaseIfComplete(request);}}
        });
    }
    private void releaseIfComplete(Request<?> request) {
        if(request.completionReturned&&request.cancelling==0&&!request.preparing&&owned.remove(request))admission.release();
    }
    void close() {synchronized(lock) {closed=true;changedLocked();}}
    Counts counts() {
        synchronized(lock) {
            int waiting=0,captured=0,settling=0,alarms=0;
            for(var request:owned) {
                switch(request.phase){case QUEUED->waiting++;case CAPTURED->captured++;case SETTLING->settling++;}
                if(request.alarm!=null)alarms++;
            }
            return new Counts(owned.size(),waiting,captured,settling,alarms,marker?1:0,highWater);
        }
    }
}
