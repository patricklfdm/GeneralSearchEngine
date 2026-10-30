package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.function.LongSupplier;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One old-owner JOINT continuation. Prepare old sources, retain their publication
 * while the independently running joining owner initializes, then use ordinary
 * fresh activation, FINAL and BARRIER. No election timer or public factory. */
final class MembershipJointContinuation<K,T> implements AutoCloseable {
    enum State { NEW, PREPARING, WAITING, ACTIVATING, READY, FAILED, CLOSED }
    private final MembershipGrantJournal owner;
    private final MembershipActivationEndpoint endpoint;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipTransport transport;
    private final Path scratch;
    private final LongSupplier clock;
    private final long budget;
    private final int maximumCampaigns;
    private final SearchEngineConfiguration<K,T> configuration;
    private final DurableStorageConfig<K,T> storage;
    private final MembershipRoundDriver.Events events;
    private final MembershipSlotDriver.Events slotEvents;
    private final MembershipResources.Lease metadata;
    private State state=State.NEW;
    private Thread runner;
    private volatile boolean closed;
    private long started;
    private MembershipContext original;
    private MembershipJoiningRetentionCampaign preparation;
    private MembershipCompletionWait waiting;
    private MembershipRoundDriver<K,T> round;
    MembershipJointContinuation(MembershipGrantJournal owner,MembershipActivationEndpoint endpoint,MembershipResources resources,
            ReplicationBounds bounds,MembershipTransport transport,Path scratch,LongSupplier clock,long budget,int maximumCampaigns,
            SearchEngineConfiguration<K,T> configuration,DurableStorageConfig<K,T> storage,MembershipRoundDriver.Events events,
            MembershipSlotDriver.Events slotEvents) {
        require(budget>0 && budget<Long.MAX_VALUE/2 && maximumCampaigns>0 && maximumCampaigns<=MembershipResources.Unit.SOURCE.count,"joint continuation bounds");
        this.owner=Objects.requireNonNull(owner);this.endpoint=Objects.requireNonNull(endpoint);this.resources=Objects.requireNonNull(resources);
        this.bounds=Objects.requireNonNull(bounds);this.transport=Objects.requireNonNull(transport);this.scratch=Objects.requireNonNull(scratch);
        this.clock=Objects.requireNonNull(clock);this.budget=budget;this.maximumCampaigns=maximumCampaigns;
        this.configuration=Objects.requireNonNull(configuration);this.storage=Objects.requireNonNull(storage);this.events=Objects.requireNonNull(events);this.slotEvents=Objects.requireNonNull(slotEvents);
        metadata=resources.reserve(MembershipResources.Unit.CONTROL,"joint-continuation-owner",4096);
    }
    static Optional<MembershipIdentity> joining(MembershipContext context,MembershipIdentity local) {
        var old=MembershipContext.nodes(context.view,"old");
        require(context.view.get("operation")!=null && old.contains(local.nodeId().value()) && local.equals(context.identities.get(local.nodeId().value())),
                "joint continuation requires actual old voter at JOINT cut");
        var added=new TreeSet<>(MembershipContext.nodes(context.view,"new"));added.removeAll(old);
        require(added.size()<=1,"joint continuation joining identity bound");return added.stream().map(context.identities::get).findFirst();
    }
    synchronized State state(){return state;}
    private synchronized void enter(State expected) {
        require(!closed && state==expected && runner==null,"joint continuation state/busy");
        runner=Thread.currentThread();if(expected==State.NEW){started=clock.getAsLong();state=State.PREPARING;}
    }
    private synchronized void leave(){runner=null;notifyAll();}
    private void time()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joint continuation closed/original deadline");
        if(Thread.currentThread().isInterrupted())throw new IOException("joint continuation interrupted");
    }
    private void original()throws IOException {time();require(owner.activationContext().cut.equals(original.cut),"joint continuation original cut changed");time();}
    private void transition(State next)throws IOException {time();synchronized(this){require(!closed,"joint continuation closed");state=next;}}
    Decoded start()throws IOException {
        enter(State.NEW);
        try {
            time();original=owner.discoveryState(resources).context();var joining=joining(original,owner.activationIdentity());
            if(joining.isPresent()) {
                var prepared=new MembershipJoiningRetentionCampaign(owner,endpoint,resources,bounds,transport::exchange,this::original,
                        scratch.resolve("preparation"),clock,started,budget,joining.get());
                synchronized(this){if(closed){prepared.close();throw new IOException("joint continuation closed before preparation");}preparation=prepared;}
                prepared.run();original();transition(State.WAITING);
                var wait=new MembershipCompletionWait(new MembershipCompletionWait.Probe(){
                    @Override public boolean initialized()throws IOException{return prepared.probeInitialized();}
                    @Override public void close()throws IOException{prepared.close();}
                },this::original,clock,started,budget,bounds.requestTimeoutMillis(),bounds.requestTimeoutMillis());
                synchronized(this){if(closed){wait.close();throw new IOException("joint continuation closed before wait");}waiting=wait;}
                wait.run();original();wait.close();prepared.close();
                synchronized(this){waiting=null;preparation=null;}
            }
            original();transition(State.ACTIVATING);
            var active=new MembershipRoundDriver<>(owner,endpoint,resources,bounds,transport,scratch.resolve("round"),clock,budget,maximumCampaigns,configuration,storage,events,slotEvents);
            synchronized(this){if(closed){active.close();throw new IOException("joint continuation closed before round");}round=active;}
            var barrier=active.start(started);time();active.readiness();transition(State.READY);return barrier;
        }catch(IOException|RuntimeException|Error error){fail(error);throw error;}
        finally{leave();}
    }
    Decoded readiness()throws IOException {
        enter(State.READY);try{time();var result=round.readiness();time();return result;}
        catch(IOException|RuntimeException|Error error){fail(error);throw error;}finally{leave();}
    }
    Decoded submit(String kind,byte[] bytes)throws IOException {
        enter(State.READY);try{time();var result=round.submit(kind,bytes);time();return result;}
        catch(IOException|RuntimeException|Error error){fail(error);throw error;}finally{leave();}
    }
    private void fail(Throwable error) {
        synchronized(this){if(!closed)state=State.FAILED;}
        try{release();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}
    }
    private void release()throws IOException {
        MembershipCompletionWait wait;MembershipJoiningRetentionCampaign prepared;MembershipRoundDriver<K,T> active;
        synchronized(this){wait=waiting;prepared=preparation;active=round;}
        if(wait!=null)wait.close();if(prepared!=null)prepared.close();if(active!=null)active.close();metadata.close();
    }
    @Override public void close()throws IOException {
        Thread worker;synchronized(this){closed=true;state=State.CLOSED;worker=runner;}
        if(worker!=null && worker!=Thread.currentThread())worker.interrupt();
        // Cancel children before waiting, but keep the parent charge until the
        // owning call exits. Failed child/drain cleanup remains reachable.
        MembershipCompletionWait wait;MembershipJoiningRetentionCampaign prepared;MembershipRoundDriver<K,T> active;
        synchronized(this){wait=waiting;prepared=preparation;active=round;}
        if(wait!=null)wait.close();if(prepared!=null)prepared.close();if(active!=null)active.close();
        if(worker!=Thread.currentThread()) {
            long began=System.nanoTime(),limit=TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
            try{synchronized(this){while(runner!=null){long left=limit-(System.nanoTime()-began);require(left>0,"joint continuation close drain timeout");TimeUnit.NANOSECONDS.timedWait(this,left);}}}
            catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("joint continuation close interrupted",error);}
            release();
        }
    }
}
