package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One installed native slot through voting, application and publication, without
 * rebinding the socket or replacing a handler between phases. A single transfer
 * registry retains original sessions across the handoff. The owner loop must
 * close this scope before the next slot/selection; this is not an election loop. */
final class MembershipSlotEndpoint implements MembershipTransport.Handler,AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipGrantJournal.Voting original;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final LongSupplier clock;
    private final long started,budget;
    private final MembershipTransport.Events events;
    private final MembershipVotingEndpoint voting;
    private final MembershipTransferService transfers;
    private volatile MembershipGrantJournal.Publication publishedScope;
    private MembershipPublicationEndpoint publication;
    private final Object registry=new Object();
    private String control;
    private int calls;
    private volatile boolean closed;

    <K,T> MembershipSlotEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,LongSupplier clock,long started,long budget,
            io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,
            MembershipTransport.Events events)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"slot endpoint budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;this.events=Objects.requireNonNull(events);
        Objects.requireNonNull(configuration);Objects.requireNonNull(storage);owner.checkRetentionResources(resources);
        original=owner.voting(resources);check();
        voting=new MembershipVotingEndpoint(owner,resources,bounds,link,clock,started,budget,configuration,storage);
        try{transfers=new MembershipTransferService(owner,original.ballot,resources,bounds,this::check,clock,started,budget);}
        catch(IOException|RuntimeException|Error error){voting.close();throw error;}
    }
    private void time(){long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"slot endpoint original deadline/closed");}
    private void check()throws IOException {
        time();var active=publishedScope;if(active==null)original.check();else active.check();time();
    }
    private MembershipPublicationEndpoint publication()throws IOException {
        synchronized(registry) {
            time();if(publication!=null)return publication;
            // Only this owner's actual typed end can advance the receiver stage.
            var applied=original.application().orElseThrow(()->new IllegalArgumentException("slot publication requires own native application"));
            var next=owner.publication(applied);
            var endpoint=new MembershipPublicationEndpoint(owner,applied,resources,bounds,link,clock,started,budget,events);
            publishedScope=next;publication=endpoint;return endpoint;
        }
    }
    @Override public Decoded handle(MembershipIdentity sender,Decoded request)throws IOException {
        time();require(request.size()<=Math.min(FRAME,bounds.maxFrameBytes()),"slot endpoint frame capacity");
        String kind=request.kind();
        // Reverse receipt pulls remain independent of a control waiting on them.
        // Do not try another registry on failure: an old trace must stay failed.
        if(kind.equals("CHUNK") || kind.equals("TRANSFER_COMMIT"))return transfers.handle(sender,request);
        require(Set.of("ACCEPT","PROOF","APPLY","PUBLISH","FUTURE_RETENTION_INTENT","RETENTION_INTENT").contains(kind),"slot endpoint control kind");
        try(var waiter=resources.reserve(MembershipResources.Unit.WAITER,"slot-waiter-"+UUID.randomUUID(),0)) {
            synchronized(registry) {
                time();if(calls!=0 && !request.digest().equals(control))
                    throw new MembershipTransport.Failure(MembershipTransport.Reason.CAPACITY,"slot control already in flight",null);
                control=request.digest();calls++;
            }
            try {
                Decoded result=switch(kind) {
                    case "PUBLISH" -> publication().handle(sender,request);
                    case "FUTURE_RETENTION_INTENT" -> {check();var reply=owner.recordFutureRetention(sender,request);check();yield reply;}
                    case "RETENTION_INTENT" -> {check();var reply=owner.recordPeerRetention(sender,request);check();yield reply;}
                    default -> voting.handle(sender,request);
                };
                // Voting/publication own their durable scope checks. Transfers
                // invoke this scope's guard at their original read boundaries.
                // The dispatcher adds cancellation/time checks, not another
                // complete disk traversal around each already-checked child.
                time();return result;
            }finally{synchronized(registry){calls--;registry.notifyAll();}}
        }
    }
    boolean poll(){long elapsed=clock.getAsLong()-started;if(elapsed<0 || elapsed>=budget)close();return !closed;}
    @Override public void close() {
        MembershipPublicationEndpoint old;
        synchronized(registry){if(closed)return;closed=true;old=publication;}
        // Never wait for a writer or transfer while holding a journal/registry monitor.
        RuntimeException failure=null;
        try{voting.close();}catch(RuntimeException error){failure=error;}
        try{if(old!=null)old.close();}catch(RuntimeException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
        try{transfers.close();}catch(RuntimeException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
        long end=System.nanoTime()+java.util.concurrent.TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
        try{synchronized(registry){while(calls!=0){long left=end-System.nanoTime();require(left>0,"slot control close timeout");
                    java.util.concurrent.TimeUnit.NANOSECONDS.timedWait(registry,left);}}}
        catch(InterruptedException error){Thread.currentThread().interrupt();var interrupted=new IllegalStateException("slot close interrupted",error);
            if(failure==null)failure=interrupted;else failure.addSuppressed(interrupted);}
        catch(RuntimeException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
        if(failure!=null)throw failure;
    }
}
