package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Acquires a settled same-ballot old majority through actual source exports,
 * then invokes the existing original-owner initialization transaction. No new
 * promise, source, counter, election, empty-ledger fallback or public READY. */
final class MembershipJoiningRetentionAcquisition implements AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipGrantJournal.JoiningRetentionPreparation original;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private final MembershipJoiningRetentionCampaign.Hint prepared;
    private final List<MembershipResources.Lease> held=new ArrayList<>();
    private MembershipSourcePull pending;
    private volatile boolean closed;
    private boolean used;
    private int active;
    private MembershipJoiningRetentionSeed seed;

    MembershipJoiningRetentionAcquisition(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget)throws IOException {
        this(owner,resources,bounds,link,guard,clock,started,budget,null);
    }
    MembershipJoiningRetentionAcquisition(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget,
            MembershipJoiningRetentionCampaign.Hint prepared)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"joining retention acquisition budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;this.prepared=prepared;original=owner.joiningRetentionPreparation(resources);
        if(prepared!=null)prepared.check(original.capsule.context,owner.activationIdentity());check();
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining retention acquisition closed/original deadline");
        guard.check();original.check();elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"joining retention acquisition closed/original deadline");
    }
    private MembershipResources.Lease reserve(long bytes) {
        synchronized(this){require(!closed,"joining retention acquisition closed");
            var lease=resources.reserve(MembershipResources.Unit.CONTROL,"joining-retention-acquisition-"+UUID.randomUUID(),bytes);held.add(lease);return lease;}
    }
    private void release(MembershipResources.Lease lease){synchronized(this){held.remove(lease);lease.close();}}
    MembershipJoiningRetentionSeed fetch()throws IOException {
        synchronized(this){require(!used && !closed,"joining retention acquisition single use");used=true;active++;}
        try {
            check();var context=original.capsule.context;var fragments=new ArrayList<byte[]>();Object ballot=null;
            var old=new TreeSet<>(MembershipContext.nodes(context.view,"old"));long size=16384;
            require(MembershipJoiningRetentionExport.reference(context,owner.activationIdentity(),
                    MembershipJoiningRetentionExport.reference(context,owner.activationIdentity())),"joining retention new joint owner required");
            for(String node:prepared==null?old:new TreeSet<>(prepared.sources().keySet())) {
                if(fragments.size()>old.size()/2)break;check();var peer=context.identities.get(node);
                var lease=reserve(3L*MembershipJoiningRetentionSeed.FRAGMENT_MAXIMUM);boolean retained=false;
                try(var pull=MembershipSourcePull.prefix(owner,new MembershipDiscovery.Hint(peer,context.cut,false),resources,bounds,link,this::check,clock,started,budget)) {
                    synchronized(this){require(!closed,"joining retention acquisition closed");pending=pull;}
                    byte[] fragment=pull.fetchPrefixMetadata(MembershipJoiningRetentionExport.reference(context,owner.activationIdentity()),MembershipJoiningRetentionSeed.FRAGMENT_MAXIMUM);
                    check();var basis=MembershipJoiningRetentionSeed.fragmentBasis(fragment);
                    require(basis.value().get("voter").equals(node) && basis.value().get("root").equals(context.root)
                            && basis.value().get("cut").equals(context.cut) && basis.value().get("view").equals(context.authority())
                            && basis.value().get("accepted")==null,"joining retention received owner/cut/tail");
                    context.ballot(basis.value().get("ballot"),true);
                    if(prepared!=null)prepared.fragment(context,owner.activationIdentity(),peer,basis);
                    require(ballot==null || ballot.equals(basis.value().get("ballot")),"joining retention mixed received ballots");
                    ballot=basis.value().get("ballot");fragments.add(fragment);size=Math.addExact(size,fragment.length);retained=true;
                }catch(MembershipTransport.Failure error) {
                    if(error.reason!=MembershipTransport.Reason.IO && error.reason!=MembershipTransport.Reason.DEADLINE)throw error;
                    check(); // Only unavailable transport may move to another old identity.
                }finally{synchronized(this){pending=null;}if(!retained)release(lease);}
            }
            check();require(fragments.size()>old.size()/2,"joining retention old majority unavailable");
            require(size<=MembershipJoiningRetentionSeed.MAXIMUM,"joining retention combined source capacity");
            // Retained fragments, parsed envelopes and immutable final descriptor
            // remain separately charged until initialization or close.
            for(int i=0;i<3;i++)reserve(size);
            var result=MembershipJoiningRetentionSeed.assemble(original.capsule,original.ancestry,owner.activationIdentity(),fragments);check();
            synchronized(this){require(!closed,"joining retention acquisition closed");seed=result;return result;}
        }catch(IOException|RuntimeException|Error error){try{close();}catch(RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
        finally{finish();}
    }
    final class Use implements AutoCloseable {
        final MembershipJoiningRetentionSeed seed;
        private boolean released;
        private Use(MembershipJoiningRetentionSeed seed){this.seed=seed;}
        @Override public void close(){synchronized(this){if(released)return;released=true;}finish();}
    }
    Use useFor(MembershipGrantJournal target,MembershipResources pool)throws IOException {
        check();require(target==owner && pool==resources,"joining retention acquisition foreign owner");
        synchronized(this){require(!closed && seed!=null && active==0,"joining retention acquisition incomplete/busy/closed");active++;return new Use(seed);}
    }
    void initialize()throws IOException {fetch();try{owner.initializeJoinedRetention(this);}finally{close();}}
    private List<MembershipResources.Lease> releaseIdle() {
        if(!closed || active!=0)return List.of();var leases=List.copyOf(held);held.clear();return leases;
    }
    private void finish(){List<MembershipResources.Lease> leases;synchronized(this){require(active>0,"joining retention active ownership");active--;leases=releaseIdle();}leases.forEach(MembershipResources.Lease::close);}
    @Override public void close() {
        MembershipSourcePull pull;List<MembershipResources.Lease> leases;
        // Revoke new uses immediately. An admitted force transaction keeps its
        // original control charges until exit, even if close races with it.
        synchronized(this){closed=true;seed=null;pull=pending;pending=null;leases=releaseIdle();}
        try{if(pull!=null)try{pull.close();}catch(IOException error){throw new java.io.UncheckedIOException(error);}}
        finally{leases.forEach(MembershipResources.Lease::close);}
    }
}
