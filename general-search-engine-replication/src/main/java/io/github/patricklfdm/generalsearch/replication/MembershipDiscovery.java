package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Read-only discovery across configuration eras. A hint is neither an authenticated
 * prefix nor a vote, read barrier, promise, installation or permission to learn peers.
 * The runtime must separately acquire and verify the complete newer source before
 * adoption. One query has one deadline and at most three identical transport attempts. */
final class MembershipDiscovery implements AutoCloseable {
    record Hint(MembershipIdentity peer,Map<String,Object> cut,boolean ready) {}
    private final MembershipGrantJournal owner;
    private final MembershipContext context;
    private final MembershipIdentity local;
    private final Map<String,Object> ballot;
    private final MembershipResources resources;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private final int maximumAttempts,maximumFrame;
    private volatile boolean closed;
    private boolean used;
    private CompletableFuture<Decoded> pending;

    MembershipDiscovery(MembershipGrantJournal owner,MembershipResources resources,
            ReplicationBounds bounds,MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,
            LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"discovery time budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);
        var original=owner.discoveryState(resources);context=original.context();local=owner.activationIdentity();
        ballot=original.ballot();context.ballot(ballot,false);
        this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;maximumAttempts=Math.min(3,bounds.maxRetryAttempts());maximumFrame=Math.min(FRAME,bounds.maxFrameBytes());
        require(maximumFrame>=4096,"discovery frame limit");check();
    }
    private void check()throws IOException {
        if(closed)guard.check(); // Preserve a positively revoked parent on drain.
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"discovery closed/original deadline");
        guard.check();owner.checkActivationBallot(context.authority(),ballot);
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"discovery closed/original deadline");
    }
    /** Authenticate the directory identities, not current-voter eligibility. A removed
     * historical identity may discover a newer cut. The request view/ballot are echoed
     * correlation, not an election proposal; this path never calls observe or prepare. */
    static Decoded answer(MembershipContext current,MembershipIdentity local,MembershipIdentity sender,Decoded request) {
        require(request.kind().equals("STATUS_PROBE"),"discovery probe kind");MembershipWire.envelope(request,current.root,sender,local);
        require(!sender.equals(local) && sender.equals(current.identities.get(sender.nodeId().value()))
                && local.equals(current.identities.get(local.nodeId().value())),"discovery permanent identities");
        current.ballot(request.value().get("ballot"),false);
        var value=new TreeMap<>(request.value());value.put("sender",request.value().get("recipient"));value.put("recipient",request.value().get("sender"));
        value.put("payload",Map.of("nonce",object(request.value().get("payload")).get("nonce"),"cut",current.cut,"ready",false));
        return decode(encode("wire","STATUS",value),"wire","STATUS");
    }
    Hint query(MembershipIdentity peer)throws IOException {
        synchronized(this){require(!used && !closed,"discovery single use");used=true;}
        try {
            check();require(!local.equals(peer) && peer.equals(context.identities.get(peer.nodeId().value())),"discovery known peer required");
            String nonce=UUID.randomUUID().toString();
            var request=decode(encode("wire","STATUS_PROBE",Map.of("root",context.root,"view",context.authority(),"ballot",ballot,
                    "sender",MembershipBootstrapSeed.identity(local),"recipient",MembershipBootstrapSeed.identity(peer),
                    "trace",UUID.randomUUID().toString(),"sequence",1L,"payload",Map.of("nonce",nonce))),"wire","STATUS_PROBE");
            require(request.size()<=maximumFrame,"discovery request frame limit");var retry=new MembershipExchange(request.digest(),started,budget);
            try(var held=resources.reserve(MembershipResources.Unit.CONTROL,"discovery-"+UUID.randomUUID(),request.size())) {
                for(;;) {
                    check();retry.attempt(request.digest(),clock.getAsLong());CompletableFuture<Decoded> future;
                    synchronized(this){check();future=Objects.requireNonNull(link.exchange(peer,request,"STATUS",started+budget));pending=future;}
                    try {
                        long left=budget-(clock.getAsLong()-started);
                        if(left<=0){future.cancel(true);throw new IOException("discovery original deadline");}
                        var reply=future.get(left,TimeUnit.NANOSECONDS);check();require(reply.size()<=maximumFrame,"discovery response frame limit");
                        MembershipWire.correlated(request,reply,"STATUS");MembershipWire.envelope(reply,context.root,peer,local);
                        if(reply.kind().equals("REJECT"))throw new MembershipSourcePull.Rejected(reply);
                        var payload=object(reply.value().get("payload"));require(nonce.equals(payload.get("nonce")),"discovery nonce");
                        var cut=object(payload.get("cut"));checkView(object(cut.get("view")));MembershipValidation.position(number(cut.get("index")));
                        // The hint may mention previously unknown identities. Do not add them
                        // to the trusted directory or derive an authority from this reply.
                        retry.complete(request.digest(),clock.getAsLong());check();return new Hint(peer,cut,(boolean)payload.get("ready"));
                    }catch(InterruptedException error){future.cancel(true);Thread.currentThread().interrupt();throw new IOException("discovery interrupted",error);}
                    catch(CancellationException error){if(error instanceof MembershipCampaignLost.Cancelled revoked)throw revoked.loss;
                        throw new IOException("discovery cancelled",error);}
                    catch(TimeoutException error){future.cancel(true);throw new IOException("discovery original deadline",error);}
                    catch(ExecutionException error) {
                        var cause=error.getCause();
                        if(cause instanceof MembershipTransport.Failure failure
                                && (failure.reason==MembershipTransport.Reason.IO || failure.reason==MembershipTransport.Reason.DEADLINE)) {
                            check();if(retry.attempts()>=maximumAttempts)throw failure;
                        }else {
                            if(cause instanceof IOException io)throw io;if(cause instanceof RuntimeException runtime)throw runtime;
                            throw new IOException("discovery failed",cause);
                        }
                    }finally{synchronized(this){if(pending==future)pending=null;}}
                }
            }
        }finally{close();}
    }
    @Override public synchronized void close(){closed=true;if(pending!=null)pending.cancel(true);}
}
