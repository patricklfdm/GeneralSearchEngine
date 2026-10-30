package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One old-side PREPARE step before joining retention initialization. It never
 * selects, installs, votes for FINAL or exposes READY. Hints are not sources. */
final class MembershipJoiningRetentionCampaign implements AutoCloseable {
    record Hint(String root,String cut,MembershipIdentity joining,Map<String,Object> ballot,Map<String,String> sources) {
        Hint {ballot=Map.copyOf(ballot);sources=Map.copyOf(sources);}
        void check(MembershipContext context,MembershipIdentity target) {
            require(root.equals(context.root) && cut.equals(MembershipContext.cutDigest(context.cut)) && joining.equals(target)
                    && MembershipJoiningRetentionExport.reference(context,target,MembershipJoiningRetentionExport.reference(context,target)),
                    "joining preparation hint original cut/identity");context.ballot(ballot,true);
            var old=MembershipContext.nodes(context.view,"old");
            require(sources.size()>old.size()/2 && old.containsAll(sources.keySet()) && sources.containsKey(ballot.get("proposer"))
                    && sources.values().stream().allMatch(v->v.matches("[0-9a-f]{64}")),"joining preparation hint old majority");
        }
        void fragment(MembershipContext context,MembershipIdentity target,MembershipIdentity peer,Decoded basis) {
            check(context,target);require(peer.equals(context.identities.get(peer.nodeId().value()))
                    && basis.digest().equals(sources.get(peer.nodeId().value())) && basis.value().get("ballot").equals(ballot),
                    "joining preparation hint changed frozen source");
        }
    }
    private final MembershipGrantJournal owner;
    private final MembershipActivationEndpoint endpoint;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private final MembershipContext context;
    private final MembershipIdentity joining;
    private final Map<String,Object> initialFence;
    private final MembershipScratch scratch;
    private final CountDownLatch finished=new CountDownLatch(1);
    private volatile MembershipActivation campaign;
    private volatile MembershipGenerationMaintenance maintenance;
    private volatile boolean closed;
    private boolean used;
    private Thread runner;
    private volatile OldSide exchange;

    MembershipJoiningRetentionCampaign(MembershipGrantJournal owner,MembershipActivationEndpoint endpoint,MembershipResources resources,
            ReplicationBounds bounds,MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,Path scratch,
            LongSupplier clock,long started,long budget,MembershipIdentity joining)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"joining preparation budget");
        this.owner=Objects.requireNonNull(owner);this.endpoint=Objects.requireNonNull(endpoint);this.resources=Objects.requireNonNull(resources);
        this.bounds=Objects.requireNonNull(bounds);this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;this.joining=Objects.requireNonNull(joining);
        var original=owner.discoveryState(resources);context=original.context();initialFence=original.ballot();
        require(MembershipContext.nodes(context.view,"old").contains(owner.activationIdentity().nodeId().value())
                && MembershipJoiningRetentionExport.reference(context,joining,MembershipJoiningRetentionExport.reference(context,joining)),
                "joining preparation requires old proposer and actual new joint member");
        checkBase();this.scratch=owner.openScratch(scratch,MembershipScratch.Role.OUTGOING,resources,e->{});
    }
    private long checkBase()throws IOException {
        require(!closed && !Thread.currentThread().isInterrupted(),"joining preparation closed/interrupted");
        long elapsed=clock.getAsLong()-started;require(elapsed>=0 && elapsed<budget,"joining preparation original deadline");guard.check();
        synchronized(owner) {
            var current=owner.activationContext();require(context.root.equals(current.root) && context.cut.equals(current.cut),"joining preparation original cut changed");
            var active=campaign;if(active==null)owner.checkActivationBallot(context.authority(),initialFence);
            else owner.checkActivation(active.ownSource().basis,null,false);
        }
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining preparation original deadline");return budget-elapsed;
    }
    private long check()throws IOException {scratch.check();return checkBase();}
    Hint run()throws IOException {
        synchronized(this){require(!used && !closed,"joining preparation single use/closed");used=true;runner=Thread.currentThread();}
        try {
            check();if(owner.publishedMaintenanceRequired()) {
                var work=MembershipGenerationMaintenance.beforeGrant(owner,resources,bounds,link,()->check(),scratch.directory(),clock,started,budget);
                synchronized(this){if(closed){work.close();throw new IOException("joining preparation closed before maintenance");}maintenance=work;}
                try(work){work.run();check();}finally{maintenance=null;}
            }
            // Recheck while holding the writer before allocating the only ballot.
            synchronized(owner){check();campaign=new MembershipActivation(owner,resources,clock,started,budget);}
            check();require(campaign.ownSource().basis.value().get("accepted")==null,"joining preparation local unsettled tail");
            endpoint.serve(campaign);check();
            var step=new OldSide(campaign,owner,resources,bounds,link,()->check(),clock,started,budget,joining);
            synchronized(this){if(closed){step.close();throw new IOException("joining preparation closed before old-side exchange");}exchange=step;}
            try(step){return step.run();}finally{exchange=null;}
        }catch(IOException|RuntimeException|Error error) {
            var active=campaign;if(active!=null)try{endpoint.abandon(active.ballot());}catch(RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;
        }finally{finished.countDown();}
    }
    @Override public void close()throws IOException {
        boolean running;Thread worker;OldSide wait;
        synchronized(this){closed=true;running=used && finished.getCount()!=0;worker=runner;wait=exchange;}
        if(wait!=null)wait.close();if(running && worker!=Thread.currentThread())worker.interrupt();
        var work=maintenance;if(work!=null)work.close();
        if(running && worker!=Thread.currentThread())try{require(finished.await(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"joining preparation close timeout");}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("joining preparation close interrupted",error);}
        // A failed drain keeps ownership reachable by the unfinished worker.
        var active=campaign;if(active!=null){endpoint.abandon(active.ballot());active.close();}scratch.close();
    }
    /** Existing live grants and correlated PREPARE replies only. This pure
     * routing result is neither selected-source authority nor an initializer. */
    static final class OldSide implements AutoCloseable {
        private final MembershipActivation campaign;
        private final MembershipGrantJournal owner;
        private final MembershipResources resources;
        private final ReplicationBounds bounds;
        private final MembershipSourcePull.Link link;
        private final MembershipSourcePull.Guard guard;
        private final LongSupplier clock;
        private final long started,budget;
        private final MembershipIdentity joining;
        private final MembershipContext context;
        private CompletableFuture<Decoded> pending;
        private volatile boolean closed;
        private boolean used;
        OldSide(MembershipActivation campaign,MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
                MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget,
                MembershipIdentity joining)throws IOException {
            this.campaign=Objects.requireNonNull(campaign);this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);
            this.bounds=Objects.requireNonNull(bounds);this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);
            this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;this.joining=Objects.requireNonNull(joining);
            require(started==campaign.started() && budget==campaign.budget(),"joining preparation original campaign lifetime");
            context=campaign.ownSource().capsule.context;
            require(campaign.ownSource().owner.equals(owner.activationIdentity())
                    && owner.discoveryState(resources).context().cut.equals(context.cut)
                    && MembershipContext.nodes(context.view,"old").contains(owner.activationIdentity().nodeId().value())
                    && MembershipJoiningRetentionExport.reference(context,joining,MembershipJoiningRetentionExport.reference(context,joining))
                    && campaign.ownSource().basis.value().get("accepted")==null,"joining preparation original old grant");check();
        }
        private long check()throws IOException {
            require(!closed && !Thread.currentThread().isInterrupted(),"joining preparation exchange closed/interrupted");
            long elapsed=clock.getAsLong()-started;require(elapsed>=0 && elapsed<budget,"joining preparation original deadline");guard.check();
            owner.checkActivation(campaign.ownSource().basis,null,false);
            require(campaign.state()==MembershipActivation.State.PREPARING && owner.activationContext().cut.equals(context.cut),"joining preparation grant selected/changed");
            elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining preparation original deadline");return budget-elapsed;
        }
        Hint run()throws IOException {
            synchronized(this){require(!used && !closed,"joining preparation exchange single use/closed");used=true;}
            check();var sources=new TreeMap<String,String>();sources.put(owner.activationIdentity().nodeId().value(),campaign.ownSource().basis.digest());
            var old=new TreeSet<>(MembershipContext.nodes(context.view,"old"));
            for(String node:old) {
                if(sources.size()>old.size()/2)break;if(sources.containsKey(node))continue;check();
                var peer=context.identities.get(node);var request=campaign.prepare(peer);
                try{var reply=prepare(peer,request);sources.put(node,(String)object(reply.value().get("payload")).get("basis"));}
                catch(MembershipTransport.Failure error){
                    if(error.reason!=MembershipTransport.Reason.IO && error.reason!=MembershipTransport.Reason.DEADLINE)throw error;check();
                }
            }
            check();var hint=new Hint(context.root,MembershipContext.cutDigest(context.cut),joining,campaign.ballot(),sources);hint.check(context,joining);return hint;
        }
        private Decoded prepare(MembershipIdentity peer,Decoded request)throws IOException {
            int maximum=Math.min(FRAME,bounds.maxFrameBytes());require(request.size()<=maximum,"joining preparation request frame bound");
            try(var lease=resources.reserve(MembershipResources.Unit.CONTROL,"joining-prepare-"+UUID.randomUUID(),request.size())) {
                for(int attempt=1;attempt<=Math.min(3,bounds.maxRetryAttempts());attempt++) {
                    check();CompletableFuture<Decoded> future=Objects.requireNonNull(link.exchange(peer,request,"PROMISE",started+budget));
                    synchronized(this){pending=future;if(closed)future.cancel(true);}
                    try {
                        var reply=future.get(check(),TimeUnit.NANOSECONDS);check();require(reply.size()<=maximum,"joining preparation response frame bound");
                        MembershipWire.correlated(request,reply,"PROMISE");
                        context.wire(reply,peer,owner.activationIdentity(),campaign.ballot(),UUID.fromString((String)request.value().get("trace")),number(request.value().get("sequence")));
                        if(reply.kind().equals("REJECT")){campaign.rejected(peer,reply);throw new MembershipSourcePull.Rejected(reply);}
                        lease.reserveControl(request.size()+(long)reply.size());check();return reply;
                    }catch(InterruptedException error){future.cancel(true);Thread.currentThread().interrupt();throw new IOException("joining preparation interrupted",error);}
                    catch(CancellationException error){throw new IOException("joining preparation cancelled",error);}
                    catch(TimeoutException error){future.cancel(true);throw new IOException("joining preparation original deadline",error);}
                    catch(ExecutionException error) {
                        var cause=error.getCause();if(cause instanceof MembershipTransport.Failure f
                                && (f.reason==MembershipTransport.Reason.IO || f.reason==MembershipTransport.Reason.DEADLINE)
                                && attempt<Math.min(3,bounds.maxRetryAttempts()))continue;
                        if(cause instanceof IOException io)throw io;if(cause instanceof RuntimeException runtime)throw runtime;
                        if(cause instanceof Error fatal)throw fatal;throw new IOException("joining preparation response failed",cause);
                    }finally{synchronized(this){if(pending==future)pending=null;}}
                }
                throw new IOException("joining preparation attempt capacity exhausted");
            }
        }
        @Override public void close(){CompletableFuture<Decoded> wait;synchronized(this){closed=true;wait=pending;}if(wait!=null)wait.cancel(true);}
    }
}
