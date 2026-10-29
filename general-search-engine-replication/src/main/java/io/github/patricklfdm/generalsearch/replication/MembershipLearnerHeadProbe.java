package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One original, read-only head query. A received ACK is not yet a durable
 * discharge certificate: no ledger mutation accepts this result. */
final class MembershipLearnerHeadProbe implements AutoCloseable {
    static final int BYTES=128*1024;
    final class Received {
        private final MembershipCapsule.Anchor endpoint;
        private Received(Decoded reply)throws IOException {
            var value=object(object(reply.value().get("payload")).get("endpoint"));
            endpoint=new MembershipCapsule.Anchor(object(value.get("cut")),(String)value.get("catalog"),(String)value.get("application"));
            MembershipContext.checkView(object(endpoint.cut().get("view")));
            owner.checkLearnerHeadEndpoint(learner,resources,original,endpoint);
        }
        MembershipCapsule.Anchor endpoint()throws IOException {check();return endpoint;}
        void check()throws IOException {
            MembershipLearnerHeadProbe.this.check();require(complete,"learner head probe incomplete");
            owner.checkLearnerHeadEndpoint(learner,resources,original,endpoint);time();
        }
    }
    private final MembershipGrantJournal owner;
    private final MembershipIdentity learner;
    private final MembershipResources resources;
    private final MembershipResources.Lease lease;
    private final MembershipSourcePull.Link link;
    private final LongSupplier clock;
    private final long started,budget;
    private final int maximumAttempts,maximumFrame;
    private final Map<String,Object> original;
    private final Decoded request;
    private volatile boolean closed,complete;
    private boolean used,running;
    private CompletableFuture<Decoded> pending;

    MembershipLearnerHeadProbe(MembershipGrantJournal owner,MembershipIdentity learner,MembershipResources resources,
            ReplicationBounds bounds,MembershipSourcePull.Link link,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"learner head probe budget");
        this.owner=Objects.requireNonNull(owner);this.learner=Objects.requireNonNull(learner);this.resources=Objects.requireNonNull(resources);
        this.link=Objects.requireNonNull(link);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        maximumAttempts=Math.min(3,bounds.maxRetryAttempts());maximumFrame=Math.min(32768,bounds.maxFrameBytes());
        lease=resources.reserve(MembershipResources.Unit.CONTROL,"learner-head-query-"+UUID.randomUUID(),BYTES);
        try {
            original=owner.learnerHeadRequest(learner,resources);
            request=decode(encode("wire","LEARNER_HEAD_QUERY",Map.of("root",original.get("root"),"view",original.get("expected"),
                    "sender",MembershipPeerRetentionPlan.identity(owner.activationIdentity()),"recipient",MembershipPeerRetentionPlan.identity(learner),
                    "ballot",MembershipLearnerDiscovery.correlation(learner),"trace",UUID.randomUUID().toString(),"sequence",1L,
                    "payload",Map.of("request",original))),"wire","LEARNER_HEAD_QUERY");
            require(request.size()<=maximumFrame,"learner head query frame capacity");check();
        }catch(IOException|RuntimeException|Error error){lease.close();throw error;}
    }
    private void time() {
        long elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"learner head probe closed/original deadline");
    }
    private void check()throws IOException {
        time();require(original.equals(owner.learnerHeadRequest(learner,resources)),"learner head probe changed original");time();
    }
    Received run()throws IOException {
        synchronized(this){require(!used && !closed,"learner head probe single use");used=true;running=true;}
        var retry=new MembershipExchange(request.digest(),started,budget);
        try {
            for(;;) {
                check();retry.attempt(request.digest(),clock.getAsLong());CompletableFuture<Decoded> future;
                // No owner/lifecycle monitor is held during external submission.
                try{future=Objects.requireNonNull(link.exchange(learner,request,"LEARNER_HEAD_ACK",started+budget));}
                catch(RuntimeException failure){future=CompletableFuture.failedFuture(failure);}
                synchronized(this){pending=future;if(closed)future.cancel(true);}
                try {
                    check();long left=budget-(clock.getAsLong()-started);
                    if(left<=0)throw new TimeoutException("original head query deadline");
                    var reply=future.get(left,TimeUnit.NANOSECONDS);check();
                    require(reply.size()<=maximumFrame,"learner head reply frame capacity");
                    MembershipWire.envelope(reply,(String)original.get("root"),learner,owner.activationIdentity());
                    MembershipWire.correlated(request,reply,"LEARNER_HEAD_ACK");
                    require(reply.kind().equals("LEARNER_HEAD_ACK") && object(reply.value().get("payload")).get("request").equals(hash(canonical(original,8192))),
                            "learner head reply original request");
                    var received=new Received(reply);retry.complete(request.digest(),clock.getAsLong());check();complete=true;return received;
                }catch(InterruptedException failure){Thread.currentThread().interrupt();throw new IOException("learner head query interrupted",failure);}
                catch(CancellationException failure){throw new IOException("learner head query cancelled",failure);}
                catch(TimeoutException failure){throw new IOException("learner head query original deadline",failure);}
                catch(ExecutionException failure) {
                    var cause=failure.getCause();
                    while(cause instanceof CompletionException && cause.getCause()!=null)cause=cause.getCause();
                    if(cause instanceof MembershipTransport.Failure transport
                            && (transport.reason==MembershipTransport.Reason.IO || transport.reason==MembershipTransport.Reason.DEADLINE)
                            && retry.attempts()<maximumAttempts){check();continue;}
                    if(cause instanceof IOException io)throw io;
                    if(cause instanceof RuntimeException runtime)throw runtime;
                    throw new IOException("learner head query failed",cause);
                }finally {future.cancel(true);synchronized(this){if(pending==future)pending=null;}}
            }
        }finally {synchronized(this){running=false;if(closed)lease.close();}}
    }
    @Override public void close() {
        CompletableFuture<Decoded> active;
        synchronized(this){closed=true;active=pending;if(!running)lease.close();}
        if(active!=null)active.cancel(true);
    }
}
