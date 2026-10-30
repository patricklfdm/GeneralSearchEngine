package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One original-deadline discovery/adoption pass before a fresh campaign. Only
 * complete original history can change authority; hints never grant votes or
 * READY. Transport exhaustion may move to another known identity, but a failed
 * durable adoption is never retried or hidden by another source. */
final class MembershipPrefixRecovery implements AutoCloseable {
    /** Only a drained, read-only discovery pass may return to election wait.
     * A fencing error after durable adoption starts is never converted. */
    static final class Superseded extends IOException {
        private static final long serialVersionUID=1L;
        Superseded(MembershipGrantJournal.HigherBallot cause){super("election discovery superseded before adoption",cause);}
        Superseded(){super("original prefix changed before election adoption");}
    }
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard guard;
    private final MembershipGrantJournal.DiscoveryState original;
    private final Path scratch;
    private final LongSupplier clock;
    private final long started,budget;
    private final MembershipResources.Lease ownership;
    private final Set<CompletableFuture<Decoded>> pending=new HashSet<>();
    private MembershipScratch scratchOwner;
    private MembershipSourcePull source,ancestry;
    private Thread runner;
    private boolean used;
    private boolean adoptionAttempted;
    private boolean election;
    private volatile boolean closed;

    MembershipPrefixRecovery(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,Path scratch,
            LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"prefix recovery budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);this.scratch=Objects.requireNonNull(scratch);
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        original=owner.discoveryState(resources);check();
        // The existing catalog permits 512 permanently reserved identities. Do
        // not accumulate hints, source bytes or a second dynamically learned list.
        ownership=resources.reserve(MembershipResources.Unit.CONTROL,"prefix-recovery-owner",4L*65536);
    }
    private void time()throws IOException {
        if(closed || Thread.currentThread().isInterrupted())throw new IOException("prefix recovery closed/interrupted");
        long elapsed=clock.getAsLong()-started;
        require(elapsed>=0 && elapsed<budget,"prefix recovery original deadline");guard.check();
        elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"prefix recovery original deadline");
    }
    private void check()throws IOException {
        time();
        if(election && !adoptionAttempted)synchronized(owner) {
            // Incoming, already verified publication/adoption is also follower
            // progress. Read physical storage before recognizing the change;
            // never classify an arbitrary validation error by its message.
            var current=owner.discoveryState(resources);
            require(current.context().root.equals(original.context().root),"prefix recovery root changed");
            if(!current.context().authority().equals(original.context().authority())
                    || !current.context().cut.equals(original.context().cut))throw new Superseded();
            owner.checkActivationBallot(original.context().authority(),original.ballot());
        }else {
            owner.checkActivationBallot(original.context().authority(),original.ballot());
            require(owner.activationContext().cut.equals(original.context().cut),"prefix recovery original cut changed");
        }
        time();
    }
    private CompletableFuture<Decoded> exchange(MembershipIdentity peer,Decoded request,String kind,long deadline) {
        CompletableFuture<Decoded> future;
        synchronized(this) {
            if(closed)return CompletableFuture.failedFuture(new IOException("prefix recovery closed"));
            future=Objects.requireNonNull(link.exchange(peer,request,kind,deadline));pending.add(future);
        }
        future.whenComplete((reply,error)->{synchronized(this){pending.remove(future);}});return future;
    }
    private MembershipSourcePull pull(MembershipDiscovery.Hint hint)throws IOException {
        return MembershipSourcePull.prefix(owner,hint,resources,bounds,this::exchange,this::check,clock,started,budget);
    }
    private void releasePulls()throws IOException {
        if(ancestry!=null){ancestry.close();ancestry=null;}
        if(source!=null){source.close();source=null;}
    }
    private void release()throws IOException {
        releasePulls();if(scratchOwner!=null){scratchOwner.close();scratchOwner=null;}ownership.close();
    }
    Optional<Decoded> runForElection()throws IOException {
        try{return run(true);}
        catch(MembershipGrantJournal.HigherBallot changed) {
            if(adoptionAttempted || changed.getSuppressed().length!=0)throw changed;
            throw new Superseded(changed);
        }
    }
    Optional<Decoded> run()throws IOException {
        return run(false);
    }
    private Optional<Decoded> run(boolean election)throws IOException {
        synchronized(this){require(!used && !closed,"prefix recovery single use/closed");used=true;this.election=election;runner=Thread.currentThread();}
        Throwable failure=null;
        try {
            check();var context=original.context();var local=owner.activationIdentity();
            for(var peer:context.identities.values().stream().filter(p->!p.equals(local))
                    .sorted(Comparator.comparing(p->p.nodeId().value())).toList()) {
                check();MembershipCapsule verified;Map<String,byte[]> images;List<MembershipSelection.Bridge> bridges;
                try {
                    MembershipDiscovery.Hint hint;
                    try(var query=new MembershipDiscovery(owner,resources,bounds,this::exchange,this::check,clock,started,budget)) {
                        hint=query.query(peer);
                    }
                    check();long index=number(hint.cut().get("index")),own=number(context.cut.get("index"));
                    if(index==own)require(hint.cut().equals(context.cut),"prefix recovery conflicting same-index hint");
                    if(index<=own || object(hint.cut().get("view")).equals(context.view))continue;
                    if(scratchOwner==null)scratchOwner=owner.openScratch(scratch,MembershipScratch.Role.OUTGOING,resources,event->{});
                    source=pull(hint);var received=source.fetchPrefix(scratchOwner.directory().resolve("source-"+UUID.randomUUID()));
                    ancestry=pull(hint);verified=ancestry.fetchAncestry(source.verifiedPrefix());
                    received.recheck();images=received.images();bridges=ancestry.ancestry();check();
                }catch(MembershipTransport.Failure error) {
                    releasePulls();check();
                    if(error.reason==MembershipTransport.Reason.IO || error.reason==MembershipTransport.Reason.DEADLINE)continue;
                    throw error;
                }
                // No transport fallback around this durable transaction. Keep
                // both receiving owners live; close cancels reads and waits for
                // this runner, never interrupting a force already admitted here.
                synchronized(owner) {
                    check();source.verifiedPrefix();ancestry.ancestry();
                    adoptionAttempted=true;
                    return Optional.of(owner.adoptCurrent(verified,images,bridges));
                }
            }
            check();return Optional.empty();
        }catch(IOException|RuntimeException|Error error){failure=error;throw error;}
        finally {
            try{release();}catch(IOException|RuntimeException error){if(failure!=null)failure.addSuppressed(error);else throw error;}
            finally{synchronized(this){runner=null;notifyAll();}}
        }
    }
    @Override public void close()throws IOException {
        Thread active;List<CompletableFuture<Decoded>> requests;
        synchronized(this){closed=true;active=runner;requests=List.copyOf(pending);}
        for(var request:requests)request.cancel(true);
        if(active==Thread.currentThread())return;
        long end=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
        try{synchronized(this){while(runner!=null){long left=end-System.nanoTime();require(left>0,"prefix recovery close timeout");
            TimeUnit.NANOSECONDS.timedWait(this,left);}}}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("prefix recovery close interrupted",error);}
        release();
    }
}
