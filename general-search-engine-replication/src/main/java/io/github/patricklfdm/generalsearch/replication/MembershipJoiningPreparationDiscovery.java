package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One bounded pass over known old identities. Only routing data is discovered;
 * no ballot is allocated, observed or selected and no owner is initialized. */
final class MembershipJoiningPreparationDiscovery implements AutoCloseable {
    record Scan(MembershipJoiningRetentionCampaign.Hint hint,Set<String> absent) {
        Scan {absent=Set.copyOf(absent);}
    }
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
    private MembershipSourcePull pending;
    private volatile boolean closed;
    private boolean used;
    private int active;
    MembershipJoiningPreparationDiscovery(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"joining discovery original budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        var original=owner.discoveryState(resources);context=original.context();fence=original.ballot();
        require(MembershipJoiningPreparation.reference(context,owner.activationIdentity(),MembershipJoiningPreparation.reference(context,owner.activationIdentity())),
                "joining discovery actual new joint identity");check();
        metadata=resources.reserve(MembershipResources.Unit.CONTROL,"joining-preparation-discovery-"+UUID.randomUUID(),4L*MembershipJoiningPreparation.MAXIMUM);
        try{check();}catch(IOException|RuntimeException|Error error){metadata.close();throw error;}
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining discovery closed/original deadline");guard.check();
        owner.checkReadOnlyBallot(context.authority(),fence);require(owner.readOnlyCapsule().context.cut.equals(context.cut),"joining discovery original cut changed");
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining discovery closed/original deadline");
    }
    MembershipJoiningRetentionCampaign.Hint find()throws IOException {
        var observed=scan(new TreeSet<>(MembershipContext.nodes(context.view,"old")));
        if(observed.hint()!=null)return observed.hint();
        throw new IOException("joining preparation unavailable from every known old identity");
    }
    /** Only exact initial absence permits a later pass. Unreachable routes are
     * excluded from that pass instead of renewing their finite transport tries. */
    Scan scan(Set<String> peers)throws IOException {
        require(!peers.isEmpty() && MembershipContext.nodes(context.view,"old").containsAll(peers),"joining discovery old routes");
        var routes=new TreeSet<>(peers);
        synchronized(this){require(!closed && !used,"joining discovery single use/closed");used=true;active++;}
        try {
            var absent=new TreeSet<String>();MembershipTransport.Failure unavailable=null;
            for(String node:routes) {
                check();var peer=context.identities.get(node);
                try(var read=MembershipSourcePull.prefix(owner,new MembershipDiscovery.Hint(peer,context.cut,false),resources,bounds,link,this::check,clock,started,budget)) {
                    synchronized(this){require(!closed,"joining discovery closed before read");pending=read;}
                    byte[] raw=read.fetchPrefixMetadata(MembershipJoiningPreparation.reference(context,owner.activationIdentity()),MembershipJoiningPreparation.MAXIMUM);
                    check();var hint=MembershipJoiningPreparation.read(raw,context,owner.activationIdentity(),peer);check();return new Scan(hint,Set.of());
                }catch(MembershipSourcePull.Rejected rejection) {
                    check();var payload=object(rejection.response.value().get("payload"));
                    context.ballot(payload.get("promised"),true);
                    if(!payload.get("reason").equals("NOT_READY") || number(rejection.response.value().get("sequence"))!=1)throw rejection;
                    // The pull already checked root, identity, view, ballot,
                    // trace and sequence. Only initial absence may try another
                    // route; never replace a partially received hint. Do not
                    // observe the remote promise.
                    absent.add(node);
                }catch(MembershipTransport.Failure failure) {
                    check();if(failure.reason!=MembershipTransport.Reason.IO && failure.reason!=MembershipTransport.Reason.DEADLINE)throw failure;
                    unavailable=failure;
                }finally{synchronized(this){pending=null;}}
            }
            check();if(absent.isEmpty() && unavailable!=null)throw unavailable;return new Scan(null,absent);
        }finally{synchronized(this){active--;if(closed && active==0)metadata.close();}}
    }
    @Override public void close()throws IOException {
        MembershipSourcePull read;synchronized(this){closed=true;read=pending;}
        try{if(read!=null)read.close();}finally{synchronized(this){if(active==0)metadata.close();}}
    }
}
