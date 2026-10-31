package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One bounded concurrent liveness sample of a guarded, installed proposer.
 * A responding majority is diagnostic only: no vote, copied floor, read lease
 * or readiness is created. The serialized owner supplies the original installed
 * authority guard; its separate recovery/BARRIER path alone enables READY. */
final class MembershipHeartbeatRound implements AutoCloseable {
    record Contact(Set<String> responding,Map<String,Map<String,Object>> hints) {
        Contact {responding=Set.copyOf(responding);hints=Map.copyOf(hints);}
    }
    private record Reply(String peer,Decoded frame,Throwable failure) {}
    private static final int HEADER_LIMIT=65536;
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard authority;
    private final MembershipContext context;
    private final MembershipIdentity local;
    private final Map<String,Object> ballot;
    private final LongSupplier clock;
    private final long started,budget;
    private final int maximumAttempts,maximumFrame;
    private final UUID trace=UUID.randomUUID();
    private final ConcurrentMap<String,Attempt> attempts=new ConcurrentHashMap<>();
    private final BlockingQueue<Reply> replies=new ArrayBlockingQueue<>(16);
    private volatile boolean closed;
    private boolean used;

    MembershipHeartbeatRound(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipSourcePull.Guard authority,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"heartbeat round budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);
        this.link=Objects.requireNonNull(link);this.authority=Objects.requireNonNull(authority);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;maximumAttempts=Math.min(3,bounds.maxRetryAttempts());
        maximumFrame=Math.min(HEADER_LIMIT,bounds.maxFrameBytes());
        authority.check();var state=owner.discoveryState(resources);context=state.context();ballot=state.ballot();local=owner.activationIdentity();
        require(context.voters().contains(local.nodeId().value())
                && ballot.get("proposer").equals(local.nodeId().value()) && ballot.get("incarnation").equals(local.storageId().toString()),
                "heartbeat round requires current proposer");
        check();
    }
    private void check()throws IOException {
        waiting();
        authority.check();owner.checkActivationBallot(context.authority(),ballot);
        require(owner.activationContext().cut.equals(context.cut),"heartbeat round original cut changed");
        waiting();
    }
    /** Cancellation only; an idle sample must not scan disk or wait for the
     * writer before noticing a higher fence. All work boundaries use check(). */
    private void waiting()throws IOException {
        if(Thread.currentThread().isInterrupted())throw new IOException("heartbeat round interrupted");
        long elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"heartbeat round closed/original deadline");
        owner.checkCampaignWait(context.authority(),ballot);
    }
    private final class Attempt implements AutoCloseable {
        final MembershipIdentity peer;
        final Decoded request;
        final MembershipExchange retry;
        final MembershipResources.Lease reservation;
        CompletableFuture<Decoded> pending;
        boolean stopped,exhausted;
        Attempt(MembershipIdentity peer,long sequence) {
            this.peer=peer;
            // Reserve the bounded request and queued reply before either exists
            // in the transport callback. A joint view has at most five peers.
            // Construction precedes the caller's smaller-frame rejection, so
            // reserve the full private header bound even for a tiny caller cap.
            reservation=resources.reserve(MembershipResources.Unit.CONTROL,"heartbeat-"+UUID.randomUUID(),2L*HEADER_LIMIT);
            try {
                request=MembershipActivation.frame("HEARTBEAT",context,local,peer,ballot,trace,sequence,
                        Map.of("cut",context.cut,"activated",true));
                require(request.size()<=maximumFrame,"heartbeat request header capacity");
                retry=new MembershipExchange(request.digest(),started,budget);
            }catch(RuntimeException|Error error){reservation.close();throw error;}
        }
        void send()throws IOException {
            check();retry.attempt(request.digest(),clock.getAsLong());CompletableFuture<Decoded> future;
            try{future=Objects.requireNonNull(link.exchange(peer,request,"HEARTBEAT_ACK",started+budget));}
            catch(RuntimeException error){future=CompletableFuture.failedFuture(error);}
            synchronized(this){pending=future;if(stopped || closed)future.cancel(true);}
            future.whenComplete((response,failure)->{
                Throwable error=failure;
                if(error==null)try {
                    require(response!=null && response.size()<=maximumFrame,"heartbeat response header capacity");
                    MembershipWire.correlated(request,response,"HEARTBEAT_ACK");MembershipWire.envelope(response,context.root,peer,local);
                    if(response.kind().equals("REJECT")) {
                        var higher=object(object(response.value().get("payload")).get("promised"));context.ballot(higher,true);
                        // Validate correlation before the lock-free observation,
                        // even if a different peer's ACK is already queued.
                        if(compareBallot(higher,ballot)>0)owner.observe(context,higher);
                        throw new MembershipSourcePull.Rejected(response);
                    }
                }catch(Throwable rejected){error=rejected;}
                synchronized(this){pending=null;if(!closed && !stopped) {
                    // At most five outstanding callbacks, each of three finite
                    // attempts. The single runner consumes before any retry.
                    require(replies.offer(new Reply(peer.nodeId().value(),error==null?response:null,error)),"heartbeat reply capacity");
                }}
            });
        }
        @Override public synchronized void close(){stopped=true;if(pending!=null)pending.cancel(true);reservation.close();}
    }
    private boolean majority(Collection<String> names) {
        for(String side:List.of("old","new")) {
            var voters=nodes(context.view,side);
            if(names.stream().filter(voters::contains).count()<=voters.size()/2)return false;
        }
        return true;
    }
    Contact run()throws IOException {
        synchronized(this){require(!used && !closed,"heartbeat round single use");used=true;}
        var responding=new TreeSet<String>();responding.add(local.nodeId().value());var hints=new TreeMap<String,Map<String,Object>>();
        try {
            check();long sequence=0;
            for(String node:new TreeSet<>(context.voters()))if(!node.equals(local.nodeId().value())) {
                var attempt=new Attempt(context.identities.get(node),++sequence);attempts.put(node,attempt);
            }
            for(String node:new TreeSet<>(attempts.keySet()))attempts.get(node).send();
            while(!majority(responding)) {
                waiting();var possible=new HashSet<>(responding);
                attempts.forEach((node,attempt)->{if(!attempt.exhausted)possible.add(node);});
                if(!majority(possible))throw new MembershipCampaignLost(MembershipCampaignLost.Reason.CONTACT_UNAVAILABLE,"heartbeat majority unavailable");
                long remaining=budget-(clock.getAsLong()-started);require(remaining>0,"heartbeat round original deadline");
                Reply reply;
                try{reply=replies.poll(Math.min(remaining,TimeUnit.MILLISECONDS.toNanos(50)),TimeUnit.NANOSECONDS);}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("heartbeat round interrupted",error);}
                waiting();if(reply==null)continue;check();
                var attempt=attempts.get(reply.peer());
                require(attempt!=null && !attempt.exhausted && !responding.contains(reply.peer()),"heartbeat unsolicited completion");
                if(reply.failure()!=null) {
                    var failure=reply.failure();while(failure instanceof CompletionException || failure instanceof ExecutionException)failure=failure.getCause();
                    if(failure instanceof MembershipTransport.Failure transport) {
                        if((transport.reason==MembershipTransport.Reason.IO || transport.reason==MembershipTransport.Reason.DEADLINE)
                                && attempt.retry.attempts()<maximumAttempts){attempt.send();continue;}
                        if(transport.reason==MembershipTransport.Reason.IO || transport.reason==MembershipTransport.Reason.DEADLINE
                                || transport.reason==MembershipTransport.Reason.CAPACITY){attempt.exhausted=true;attempt.close();continue;}
                    }
                    if(failure instanceof IOException io)throw io;if(failure instanceof RuntimeException runtime)throw runtime;
                    throw new IOException("heartbeat exchange failed",failure);
                }
                var cut=object(object(reply.frame().value().get("payload")).get("cut"));
                checkView(object(cut.get("view")));MembershipValidation.position(number(cut.get("index")));
                require(viewDigest(context.root,object(cut.get("view"))).equals(context.authority()),"heartbeat reply requires original discovery");
                attempt.retry.complete(attempt.request.digest(),clock.getAsLong());responding.add(reply.peer());hints.put(reply.peer(),Map.copyOf(cut));attempt.close();
            }
            check();return new Contact(responding,hints);
        }finally{close();}
    }
    @Override public void close() {
        closed=true;attempts.values().forEach(Attempt::close);replies.clear();
        replies.offer(new Reply("",null,new IOException("heartbeat round closed")));
    }
}
