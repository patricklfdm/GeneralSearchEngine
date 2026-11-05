package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.LongSupplier;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private native node lifetime. Construct before open so a failed open/drain
 * always leaves the caller an exact closeable owner. A fresh object must reopen
 * original storage; it cannot reuse READY, queued commands or a failed journal.
 * The caller supplies existing scratch parents, never paths inside authority. */
final class MembershipNodeOwner<K,T> implements AutoCloseable {
    enum State { NEW, OPENING, OPEN, FAILED, CLOSING, CLOSED }
    record Hooks(MembershipBallotAllocator.Cut storage,MembershipTransport.Events network,
                 MembershipRoundDriver.Events round,MembershipSlotDriver.Events slot,MembershipAutomaticOwner.Events automatic) {
        Hooks(MembershipBallotAllocator.Cut storage,MembershipTransport.Events network,
                 MembershipRoundDriver.Events round,MembershipSlotDriver.Events slot) {
            this(storage,network,round,slot,MembershipAutomaticOwner.Events.NONE);
        }
        static final Hooks NONE=new Hooks(event->{},MembershipTransport.Events.NONE,MembershipRoundDriver.Events.NONE,MembershipSlotDriver.Events.NONE);
        Hooks {Objects.requireNonNull(storage);Objects.requireNonNull(network);Objects.requireNonNull(round);Objects.requireNonNull(slot);Objects.requireNonNull(automatic);}
    }
    private final MembershipReplicaConfig<K,T> config;
    private final SearchEngineConfiguration<K,T> application;
    private final Path incoming,outgoing;
    private final LongSupplier clock;
    private final long budget;
    private final Hooks hooks;
    private final MembershipResources resources;
    private final ReentrantLock drain=new ReentrantLock();
    private volatile State state=State.NEW;
    private Thread opener;
    private volatile MembershipGrantJournal journal;
    private volatile MembershipActivationEndpoint endpoint;
    private volatile MembershipTransport transport;
    private volatile MembershipRoundDriver<K,T> unownedRound;
    private volatile MembershipAutomaticOwner automatic;
    private volatile IOException observationFailure;

    MembershipNodeOwner(MembershipReplicaConfig<K,T> config,SearchEngineConfiguration<K,T> application,
            Path incoming,Path outgoing,LongSupplier clock,long budget,Hooks hooks) {
        this.config=Objects.requireNonNull(config);this.application=Objects.requireNonNull(application);
        this.incoming=MembershipValidation.path(incoming);this.outgoing=MembershipValidation.path(outgoing);
        MembershipValidation.disjoint(List.of(config.replicaDirectory(),config.materialization().directory(),this.incoming,this.outgoing));
        this.clock=Objects.requireNonNull(clock);require(budget>0 && budget<Long.MAX_VALUE/2,"node owner budget");this.budget=budget;
        this.hooks=Objects.requireNonNull(hooks);resources=new MembershipResources(config.bounds().maxSnapshotStagingBytes());
    }
    State state(){return state;}
    MembershipResources.Usage usage(){return resources.usage();}
    synchronized Optional<MembershipAutomaticOwner.State> serviceState(){return automatic==null?Optional.empty():Optional.of(automatic.state());}
    synchronized Optional<Throwable> failure(){return automatic==null?Optional.empty():automatic.failure();}
    synchronized Optional<IOException> observationFailure() {
        var current=automatic;
        return current==null?Optional.ofNullable(observationFailure):current.observationFailure();
    }
    record Recovery(int rounds,List<MembershipCampaignLost.Reason> losses) {}
    synchronized Optional<Recovery> recovery() {
        if(automatic==null)return Optional.empty();
        synchronized(automatic){return Optional.of(new Recovery(automatic.rounds(),automatic.losses()));}
    }
    private void opening()throws IOException {if(state!=State.OPENING)throw new IOException("node open cancelled");}
    /** A bound listener refuses work until every owner has been published.
     * open does not campaign; start enters the existing bounded automatic loop. */
    void open()throws IOException {
        synchronized(this){require(state==State.NEW,"node owner single open");state=State.OPENING;opener=Thread.currentThread();}
        try {
            journal=MembershipGrantJournal.openRetainingFuturePeers(config.replicaDirectory(),config.materialization().directory(),
                    config.root(),config.localIdentity(),resources,MembershipGrantJournal.MAXIMUM,hooks.storage());opening();
            var context=journal.activationContext();
            for(var seed:config.seedPeers())require(seed.equals(context.identities.get(seed.nodeId().value())),"node seed differs from original identity");
            journal.recoverCarriedAcceptance(application,config.materialization());opening();
            endpoint=new MembershipActivationEndpoint(journal,resources,config.bounds(),(peer,request,kind,deadline)->{
                var current=transport;
                if(state!=State.OPEN || current==null)return CompletableFuture.failedFuture(new IOException("node transport not serving"));
                return current.exchange(peer,request,kind,deadline);
            },List.of(),List.of(),incoming,clock,budget,application,config.materialization());opening();
            var receiver=endpoint;
            transport=new MembershipTransport(journal,config.bounds(),resources,(peer,request)->{
                if(state!=State.OPEN)throw new IOException("node endpoint not serving");return receiver.handle(peer,request);
            },hooks.network());opening();
            unownedRound=new MembershipRoundDriver<>(journal,endpoint,resources,config.bounds(),transport,outgoing,clock,budget,
                    Math.min(3,config.bounds().maxRetryAttempts()),application,config.materialization(),hooks.round(),hooks.slot());opening();
            automatic=unownedRound.automaticOwner(config.leadershipPolicy(),hooks.automatic());unownedRound=null;
            synchronized(this){opening();state=State.OPEN;}
        }catch(IOException|RuntimeException|Error error){synchronized(this){if(state==State.OPENING)state=State.FAILED;}throw error;}
        finally{synchronized(this){opener=null;notifyAll();}}
    }
    synchronized MembershipAutomaticOwner.Call start(){require(state==State.OPEN,"node owner not open");return automatic.start();}
    synchronized MembershipAutomaticOwner.Call submit(String kind,byte[] bytes){require(state==State.OPEN,"node owner not open");return automatic.submit(kind,bytes);}
    synchronized MembershipAutomaticOwner.Call readiness(){require(state==State.OPEN,"node owner not open");return automatic.readiness();}

    private static IOException failed(IOException prior,String component,Exception error) {
        var next=new IOException("node "+component+" drain failed",error);if(prior==null)return next;prior.addSuppressed(next);return prior;
    }
    /** Cancel admission first, drain all work before storage. Any failed drain
     * retains the journal and exact child for a later external close attempt. */
    @Override public void close()throws IOException {
        long timeout=TimeUnit.MILLISECONDS.toNanos(config.bounds().requestTimeoutMillis()),end=System.nanoTime()+timeout;
        synchronized(this){if(state==State.CLOSED)return;state=State.CLOSING;notifyAll();}
        if(drain.isHeldByCurrentThread())throw new IOException("recursive node close cannot prove drain");
        try {if(!drain.tryLock(timeout,TimeUnit.NANOSECONDS))throw new IOException("node concurrent close deadline");}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("node close interrupted",error);}
        try {
            synchronized(this) {
                if(opener==Thread.currentThread())throw new IOException("opening thread cannot drain itself");
                while(opener!=null) {
                    long left=end-System.nanoTime();if(left<=0)throw new IOException("node open drain deadline");
                    try{TimeUnit.NANOSECONDS.timedWait(this,left);}
                    catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("node close interrupted",error);}
                }
            }
            IOException failure=null;
            if(automatic!=null)try {
                automatic.close();if(!automatic.drained())throw new IOException("automatic callback has not drained");
                observationFailure=automatic.observationFailure().orElse(null);automatic=null;
            }catch(IOException|RuntimeException error){failure=failed(failure,"automatic",error);}
            if(unownedRound!=null)try{unownedRound.close();unownedRound=null;}
            catch(IOException|RuntimeException error){failure=failed(failure,"unowned round",error);}
            if(endpoint!=null)try{endpoint.close();endpoint=null;}
            catch(IOException|RuntimeException error){failure=failed(failure,"endpoint",error);}
            if(transport!=null)try {
                transport.close();if(!transport.drained())throw new IOException("transport callback has not drained");transport=null;
            }catch(RuntimeException|IOException error){failure=failed(failure,"transport",error);}
            if(failure!=null)throw failure;
            if(journal!=null){journal.close();journal=null;}
            require(resources.usage().leases()==0,"node resources remain after drain");
            synchronized(this){state=State.CLOSED;notifyAll();}
        }finally{drain.unlock();}
    }
}
