package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Wait for routing publication without campaigning, observing a ballot, or
 * replaying an exhausted transport route. The result is never source authority. */
final class MembershipJoiningPreparationRendezvous implements AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private final MembershipContext context;
    private final Map<String,Object> fence;
    private final MembershipResources.Lease metadata;
    private final MembershipCompletionWait waiting;
    private Set<String> routes;
    private MembershipJoiningPreparationDiscovery pending;
    private MembershipJoiningRetentionCampaign.Hint hint;
    private volatile boolean closed;
    MembershipJoiningPreparationRendezvous(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget)throws IOException {
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        var original=owner.discoveryState(resources);context=original.context();fence=original.ballot();
        require(MembershipJoiningPreparation.reference(context,owner.activationIdentity(),MembershipJoiningPreparation.reference(context,owner.activationIdentity())),
                "joining rendezvous actual new identity");
        routes=new TreeSet<>(MembershipContext.nodes(context.view,"old"));
        waiting=new MembershipCompletionWait(new MembershipCompletionWait.Probe(){
            @Override public boolean initialized()throws IOException{return pass();}
            @Override public void close()throws IOException{cancelPass();}
        },this::check,clock,started,budget,bounds.requestTimeoutMillis(),bounds.requestTimeoutMillis());
        check();metadata=resources.reserve(MembershipResources.Unit.CONTROL,"joining-rendezvous-"+UUID.randomUUID(),4L*MembershipJoiningPreparation.MAXIMUM);
        try{check();}catch(IOException|RuntimeException|Error error){metadata.close();throw error;}
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining rendezvous closed/original deadline");guard.check();
        owner.checkReadOnlyBallot(context.authority(),fence);require(owner.readOnlyCapsule().context.cut.equals(context.cut),"joining rendezvous original cut changed");
    }
    private boolean pass()throws IOException {
        check();var search=new MembershipJoiningPreparationDiscovery(owner,resources,bounds,link,this::check,clock,started,budget);
        synchronized(this){if(closed){search.close();throw new IOException("joining rendezvous closed before pass");}pending=search;}
        try {
            var result=search.scan(routes);check();hint=result.hint();routes=result.absent();
            require(hint!=null || !routes.isEmpty(),"joining rendezvous has no absent route");return hint!=null;
        }finally{search.close();synchronized(this){if(pending==search)pending=null;}}
    }
    MembershipJoiningRetentionCampaign.Hint await()throws IOException {
        waiting.run();check();return Objects.requireNonNull(hint);
    }
    private void cancelPass()throws IOException {
        MembershipJoiningPreparationDiscovery search;synchronized(this){search=pending;}if(search!=null)search.close();
    }
    @Override public void close()throws IOException {closed=true;waiting.close();metadata.close();}
}
