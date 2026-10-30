package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One bounded election wait, never a grant or a lease. Only work boundaries
 * read original storage; idle polls use the existing volatile cancellation fence.
 * The subsequent campaign must rediscover/revalidate before allocating a ballot. */
final class MembershipElectionWait implements AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipActivationEndpoint endpoint;
    private final MembershipResources resources;
    private final LongSupplier clock;
    private final LongBinaryOperator jitter;
    private final long started,budget,minimum,maximum;
    private final boolean freshRetry;
    private final BlockingQueue<Boolean> wake=new ArrayBlockingQueue<>(1);
    private volatile boolean closed;
    private boolean used;
    MembershipElectionWait(MembershipGrantJournal owner,MembershipActivationEndpoint endpoint,MembershipResources resources,
            AutomaticLeadershipPolicy policy,LongSupplier clock,LongBinaryOperator jitter,long started,long budget) {
        this(owner,endpoint,resources,policy,clock,jitter,started,budget,false);
    }
    MembershipElectionWait(MembershipGrantJournal owner,MembershipActivationEndpoint endpoint,MembershipResources resources,
            AutomaticLeadershipPolicy policy,LongSupplier clock,LongBinaryOperator jitter,long started,long budget,boolean freshRetry) {
        require(budget>0 && budget<Long.MAX_VALUE/2,"election wait budget");
        this.owner=Objects.requireNonNull(owner);this.endpoint=Objects.requireNonNull(endpoint);this.resources=Objects.requireNonNull(resources);
        this.clock=Objects.requireNonNull(clock);this.jitter=Objects.requireNonNull(jitter);this.started=started;this.budget=budget;this.freshRetry=freshRetry;
        minimum=TimeUnit.MILLISECONDS.toNanos(policy.minElectionTimeoutMillis());maximum=TimeUnit.MILLISECONDS.toNanos(policy.maxElectionTimeoutMillis());
    }
    private long time()throws IOException {
        if(Thread.currentThread().isInterrupted())throw new IOException("election wait interrupted");
        long now=clock.getAsLong(),elapsed=now-started;
        require(!closed && !endpoint.usage().closed() && elapsed>=0 && elapsed<budget,"election wait closed/original deadline");return now;
    }
    private long delay() {
        long result=jitter.applyAsLong(minimum,maximum);require(result>=minimum && result<=maximum,"election jitter outside policy");return result;
    }
    private MembershipGrantJournal.DiscoveryState snapshot()throws IOException {
        time();var state=owner.discoveryState(resources);
        require(state.context().voters().contains(owner.activationIdentity().nodeId().value()),"election requires current voter");time();return state;
    }
    MembershipGrantJournal.DiscoveryState await()throws IOException {
        synchronized(this){require(!used && !closed,"election wait single use");used=true;}
        try {
            var state=snapshot();long armed=time(),retryEntered=armed,delay=delay();
            MembershipActivationEndpoint.HeartbeatContact seen=null;
            MembershipActivationEndpoint.ActivationProgress seenProgress=null;
            boolean activityArmed=false;
            for(;;) {
                long now=time();
                try{owner.checkActivationWait(state.context().authority(),state.ballot());}
                catch(IllegalArgumentException changed) {
                    // A new observed campaign/view is real progress, but it does
                    // not extend the enclosing invocation or create authority.
                    state=snapshot();armed=time();delay=delay();seen=null;seenProgress=null;activityArmed=false;now=armed;
                }
                var contact=endpoint.heartbeatContact().orElse(null);
                var progress=endpoint.activationProgress().orElse(null);
                boolean newContact=contact!=null && !contact.equals(seen),newProgress=progress!=null && !progress.equals(seenProgress);
                if(newContact || newProgress) {
                    require(!newContact || contact.root().equals(state.context().root),"election contact foreign root");
                    require(!newProgress || progress.root().equals(state.context().root),"election progress foreign root");
                    if(newContact && (!contact.view().equals(state.context().authority()) || !contact.ballot().equals(state.ballot()))
                            || newProgress && (!progress.view().equals(state.context().authority()) || !progress.ballot().equals(state.ballot()))) {
                        state=snapshot();armed=time();delay=delay();seen=null;seenProgress=null;activityArmed=false;continue;
                    }
                    now=time();long at=newContact?contact.receivedNanos():progress.completedNanos();
                    if(newContact)require(now-contact.receivedNanos()>=0,"election contact from future clock");
                    if(newProgress) {
                        require(now-progress.completedNanos()>=0,"election progress from future clock");
                        if(progress.completedNanos()-at>0)at=progress.completedNanos();
                    }
                    // Use original arrival/completion, never poll time. Delayed
                    // heartbeats cannot move a newer progress arm backwards.
                    // A failed campaign gets one ordinary election interval.
                    // An already expired cached milestone cannot spend all new
                    // rounds immediately. New contacts retain their actual time;
                    // this never renews the original enclosing deadline.
                    if((!freshRetry || at-retryEntered>=0) && (!activityArmed || at-armed>0)){
                        armed=at;delay=delay();activityArmed=true;
                    }
                    if(newContact)seen=contact;if(newProgress)seenProgress=progress;
                }
                if(now-armed>=delay) {
                    var current=snapshot();
                    if(!current.context().authority().equals(state.context().authority()) || !current.ballot().equals(state.ballot())) {
                        state=current;armed=time();delay=delay();seen=null;seenProgress=null;activityArmed=false;continue;
                    }
                    var latest=endpoint.heartbeatContact().orElse(null);
                    if(latest!=null && !latest.equals(seen))continue;
                    var latestProgress=endpoint.activationProgress().orElse(null);
                    if(latestProgress!=null && !latestProgress.equals(seenProgress))continue;
                    owner.checkActivationWait(current.context().authority(),current.ballot());time();return current;
                }
                long left=Math.min(budget-(now-started),delay-(now-armed));require(left>0,"election wait original deadline");
                try{wake.poll(Math.min(left,TimeUnit.MILLISECONDS.toNanos(50)),TimeUnit.NANOSECONDS);}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("election wait interrupted",error);}
            }
        }finally{close();}
    }
    @Override public void close(){closed=true;wake.offer(Boolean.TRUE);}
}
