package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.LongBinaryOperator;
import java.util.function.LongSupplier;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Serialized, bounded native round lifetime. Activation, carried recovery and
 * the fresh barrier are one invocation; subsequent slots retain its deadline.
 * READY is an internal guarded state, not a public read lease or an election
 * timer. A changed authority requires fresh activation within the original
 * lifetime, never a reused old grant or a restarted deadline. */
final class MembershipRoundDriver<K,T> implements AutoCloseable {
    enum State { NEW, WAITING, DISCOVERING, ACTIVATING, RECOVERING, READY, FAILED, CLOSED }
    interface Events {
        Events NONE=(event,record)->{};
        void at(String event,Decoded record)throws IOException;
    }
    private final MembershipGrantJournal owner;
    private final MembershipActivationEndpoint endpoint;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipTransport transport;
    private final SearchEngineConfiguration<K,T> configuration;
    private final DurableStorageConfig<K,T> storage;
    private final Path scratch;
    private final LongSupplier clock;
    private final long budget;
    private final int maximumCampaigns;
    private final Events events;
    private final MembershipSlotDriver.Events slotEvents;
    private final MembershipResources.Lease ownership;
    private volatile boolean closed;
    private State state=State.NEW;
    private Thread runner;
    private long started;
    private MembershipActivationDriver activation;
    private MembershipPrefixRecovery discovery;
    private MembershipHeartbeatRound heartbeat;
    private MembershipWorkPulse workPulse;
    private MembershipElectionWait electionWait;
    private MembershipSlotDriver slot;
    private Decoded selection,barrier;
    private Map<String,Object> ballot,expectedCut;
    private String authority;
    private boolean carriedPending;

    MembershipRoundDriver(MembershipGrantJournal owner,MembershipActivationEndpoint endpoint,MembershipResources resources,
            ReplicationBounds bounds,MembershipTransport transport,Path scratch,LongSupplier clock,long budget,int maximumCampaigns,
            SearchEngineConfiguration<K,T> configuration,DurableStorageConfig<K,T> storage,Events events,
            MembershipSlotDriver.Events slotEvents) {
        require(budget>0 && budget<Long.MAX_VALUE/2,"native round budget");
        require(maximumCampaigns>0 && maximumCampaigns<=MembershipResources.Unit.SOURCE.count,"native round campaign capacity");
        this.owner=Objects.requireNonNull(owner);this.endpoint=Objects.requireNonNull(endpoint);this.resources=Objects.requireNonNull(resources);
        this.bounds=Objects.requireNonNull(bounds);this.transport=Objects.requireNonNull(transport);this.scratch=Objects.requireNonNull(scratch);
        this.clock=Objects.requireNonNull(clock);this.budget=budget;this.maximumCampaigns=maximumCampaigns;
        this.configuration=Objects.requireNonNull(configuration);this.storage=Objects.requireNonNull(storage);
        this.events=Objects.requireNonNull(events);this.slotEvents=Objects.requireNonNull(slotEvents);
        // Selection, current input, barrier/last response and context bookkeeping.
        // Payload copies have a separate reservation before materialization.
        ownership=resources.reserve(MembershipResources.Unit.CONTROL,"native-round-owner",4L*65536);
    }
    synchronized State state(){return state;}
    private void enter(State required){enter(required,null);}
    private synchronized void enter(State required,Long originalStarted) {
        require(!closed && state==required && runner==null,"native round state/busy");
        if(required==State.NEW){started=originalStarted==null?clock.getAsLong():originalStarted;state=State.ACTIVATING;}
        runner=Thread.currentThread();
    }
    private synchronized void leave(){runner=null;notifyAll();}
    private void time()throws IOException {
        if(closed || Thread.currentThread().isInterrupted())throw new IOException("native round closed/interrupted");
        long elapsed=clock.getAsLong()-started;require(elapsed>=0 && elapsed<budget,"native round original deadline");
    }
    private void current()throws IOException {
        time();owner.checkCampaignWait(authority,ballot);var voting=owner.voting(resources);
        require(selection!=null && owner.originalSelection().orElseThrow().digest().equals(selection.digest())
                && voting.ballot.equals(ballot) && voting.before.context.authority().equals(authority),"native round selection/authority changed");
        require(voting.before.context.cut.equals(expectedCut),"native round external publication");voting.check();endpoint.checkInstalled();time();
    }
    private void transition(State next)throws IOException {
        time();synchronized(this){require(!closed,"native round closed");state=next;}
    }
    private Decoded entry(String kind,byte[] payload)throws IOException {
        current();var context=owner.activationContext();
        return decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),
                "index",Math.addExact(number(context.cut.get("index")),1),"previous",context.cut.get("entry"),
                "origin",ballot,"kind",kind,"payload",hash(payload))),"records","ENTRY");
    }
    private Decoded publish(Decoded entry,byte[] payload)throws IOException {
        current();events.at("SLOT_BEGIN",entry);current();
        var child=new MembershipSlotDriver(owner,endpoint,resources,bounds,transport,clock,started,budget,configuration,storage,slotEvents,this::pulseWhileWorking);
        boolean registered=false;
        try {
            synchronized(this){require(!closed,"native round closed before slot");slot=child;registered=true;}
            var done=child.run(entry,payload);time();
            // A child returns only after real publication and draining its tasks.
            // Derive the new cut from the owned journal, then recheck the ballot.
            var context=owner.activationContext();require(context.cut.get("entry").equals(entry.digest())
                    && context.cut.get("index").equals(entry.value().get("index")),"native round published exact entry");
            expectedCut=context.cut;
            if(!context.authority().equals(authority)) {
                require(Set.of("INTENT","FINAL").contains(entry.value().get("kind")),"native round unexpected authority change");
                synchronized(this){barrier=null;}
                transition(State.ACTIVATING);completedFence();events.at("SLOT_COMPLETE",done);completedFence();
            } else {current();events.at("SLOT_COMPLETE",done);current();}
            return done;
        }finally{
            child.close(); // A failed drain retains the child and parent ownership.
            synchronized(this){if(registered && slot==child)slot=null;}
        }
    }
    /** Fence only work the child has already durably completed. This does not
     * revive the old endpoint scope or grant service under the new authority. */
    private void completedFence()throws IOException {
        time();var context=owner.activationContext();
        require(context.cut.equals(expectedCut) && owner.originalSelection().orElseThrow().digest().equals(selection.digest()),
                "native round completed publication changed");
        owner.checkActivationBallot(context.authority(),ballot);time();
    }
    private void activate()throws IOException {
        time();transition(State.ACTIVATING);
        MembershipActivationDriver previous;
        synchronized(this){barrier=null;previous=activation;}
        if(previous!=null)previous.close();
        synchronized(this){if(activation==previous)activation=null;}
        require(owner.activationContext().voters().contains(owner.activationIdentity().nodeId().value()),
                "native round local member not eligible for activation");
        time();var child=new MembershipActivationDriver(owner,endpoint,resources,bounds,transport::exchange,List.of(),List.of(),
                scratch,clock,budget,maximumCampaigns);
        boolean registered=false;
        try {
            synchronized(this){require(!closed,"native round closed before activation");activation=child;registered=true;}
            selection=child.run(started);
        }finally{if(!registered)child.close();}
        ballot=Map.copyOf(object(selection.value().get("ballot")));var context=owner.activationContext();
        authority=context.authority();expectedCut=context.cut;carriedPending=selection.value().get("nextEntry")!=null;
        current();events.at("INSTALLED",selection);current();
        // Installed activation is live before recovery/BARRIER grants READY.
        // Notify even unselected current voters, then keep servicing liveness
        // at unlocked recovery work boundaries under this same original cut.
        if(workPulse!=null)sampleHeartbeat();
    }
    private Map<String,Object> activeOperation()throws IOException {
        var catalog=owner.activationContext().catalog;Object active=catalog.get("active");
        if(active==null)return null;
        for(Object row:list(catalog.get("results"))) {
            var operation=object(row);
            if(object(operation.get("request")).get("number").equals(active))return operation;
        }
        throw new IllegalArgumentException("native round active operation absent");
    }
    private Decoded recoverAndReady()throws IOException {
        // A serialized operation has at most old -> joint -> new authority.
        // Each activation retains its existing bounded attempt count, and all
        // handoffs share the parent's original start and budget.
        int handoffs=0;
        for(;;) {
            transition(State.RECOVERING);current();
            if(carriedPending) {
                String next=(String)selection.value().get("nextEntry");var packet=owner.activationCapsule().packet;
                try(var entryLease=resources.reserve(MembershipResources.Unit.CONTROL,"round-carried-entry",packet.objectSize(next))) {
                    var carried=decode(packet.objectBytes(next),"records","ENTRY");String digest=(String)carried.value().get("payload");
                    try(var payloadLease=resources.reserve(MembershipResources.Unit.CONTROL,"round-carried-payload",Math.max(1,packet.objectSize(digest)))) {
                        publish(carried,packet.objectBytes(digest));carriedPending=false;
                    }
                }
            }
            if(!owner.activationContext().authority().equals(authority)) {
                require(++handoffs<=2,"native round authority handoff bound");activate();continue;
            }
            current();var operation=activeOperation();String phase=operation==null?null:(String)operation.get("phase");
            if("SEALED".equals(phase) || "JOINT".equals(phase)) {
                String kind="SEALED".equals(phase)?"INTENT":"FINAL";Map<String,Object> command;
                if(kind.equals("INTENT")) {
                    var sealed=new TreeMap<String,Object>();for(String key:List.of("request","prepared","receipt"))sealed.put(key,operation.get(key));
                    command=Map.of("sealed",sealed);
                } else command=Map.of("binding",operation.get("binding"));
                try(var held=resources.reserve(MembershipResources.Unit.CONTROL,"round-transition-input",8192)) {
                    byte[] payload=canonical(command,8192);
                    publish(entry(kind,payload),payload);
                }
                require(!owner.activationContext().authority().equals(authority),"native round transition did not change authority");
                require(++handoffs<=2,"native round authority handoff bound");activate();continue;
            }
            require(owner.activationContext().view.get("operation")==null,"native round readiness requires stable authority");
            var fresh=entry("BARRIER",new byte[0]);var done=publish(fresh,new byte[0]);current();
            require(fresh.value().get("origin").equals(ballot),"native round fresh barrier ballot");
            events.at("BEFORE_READY",done);current();
            synchronized(this){require(!closed,"native round closed before readiness");barrier=done;state=State.READY;}
            if(workPulse!=null)workPulse.completed();
            return done;
        }
    }
    Decoded start()throws IOException {
        return start(clock.getAsLong());
    }
    /** Preserve the enclosing preparation/wait lifetime across fresh activation. */
    Decoded start(long originalStarted)throws IOException {
        return start(originalStarted,false);
    }
    /** Discover/adopt a newer certified authority before allocating this round's
     * own grant. The whole pass, fresh activation and barrier share one lifetime.
     * The returned value still requires readiness(); STATUS never enables it. */
    Decoded startDiscovered()throws IOException {return start(clock.getAsLong(),true);}
    Decoded startDiscovered(long originalStarted)throws IOException {return start(originalStarted,true);}
    Decoded startAutomatic(AutomaticLeadershipPolicy policy)throws IOException {
        return startAutomatic(policy,(minimum,maximum)->ThreadLocalRandom.current().nextLong(minimum,maximum+1));
    }
    Decoded startAutomatic(AutomaticLeadershipPolicy policy,LongBinaryOperator jitter)throws IOException {
        return startAutomatic(clock.getAsLong(),policy,jitter);
    }
    private Decoded startAutomatic(long originalStarted,AutomaticLeadershipPolicy policy,LongBinaryOperator jitter)throws IOException {
        return start(originalStarted,true,Objects.requireNonNull(policy),Objects.requireNonNull(jitter));
    }
    /** Transfer serial invocation ownership to one private automatic control
     * loop. The caller must no longer invoke this driver directly. */
    synchronized MembershipAutomaticOwner automaticOwner(AutomaticLeadershipPolicy policy) {
        return new MembershipAutomaticOwner(automaticSession(policy),()->{
            var fresh=new MembershipRoundDriver<>(owner,endpoint,resources,bounds,transport,
                scratch.resolveSibling(scratch.getFileName()+"-retry-"+UUID.randomUUID()),clock,budget,maximumCampaigns,
                configuration,storage,events,slotEvents);
            try{return fresh.automaticSession(policy,true);}
            catch(RuntimeException|Error error){try{fresh.close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
        },Math.min(3,bounds.maxRetryAttempts()),resources,bounds,policy,clock,budget);
    }
    @FunctionalInterface interface CampaignCall<R> { R run()throws IOException; }
    static <R> R campaignCall(CampaignCall<R> call)throws IOException {
        try{return call.run();}
        catch(MembershipGrantJournal.HigherBallot fenced) {
            // Never erase a failed drain or reinterpret a wrapped integrity error.
            if(fenced.getSuppressed().length!=0)throw fenced;
            var lost=new MembershipCampaignLost(MembershipCampaignLost.Reason.HIGHER_BALLOT,fenced.getMessage());
            lost.initCause(fenced);throw lost;
        }
        catch(MembershipTransport.Failure unavailable) {
            // A peer can stop replying before its newer promise is forced and
            // reportable. Only direct, exhausted transport availability permits
            // fresh recovery; malformed frames, capacity, closure and wrapped
            // application errors do not. The owner never replays the client call.
            if(unavailable.getSuppressed().length!=0 || !(unavailable.reason==MembershipTransport.Reason.IO
                    || unavailable.reason==MembershipTransport.Reason.DEADLINE))throw unavailable;
            var lost=new MembershipCampaignLost(MembershipCampaignLost.Reason.CONTACT_UNAVAILABLE,"native campaign peer unavailable");
            lost.initCause(unavailable);throw lost;
        }
        catch(MembershipGenerationMaintenance.Unavailable unavailable) {
            // Serving a just-forced grant performs the same published-copy
            // maintenance as the pre-grant check. Neither absence can skip the
            // floor; both leave the original durable grant for fresh discovery.
            if(unavailable.getSuppressed().length!=0)throw unavailable;
            var lost=new MembershipCampaignLost(MembershipCampaignLost.Reason.CONTACT_UNAVAILABLE,"published original copies unavailable");
            lost.initCause(unavailable);throw lost;
        }
    }
    /** The same native adapter can be instrumented by whole-history tests;
     * its returned heartbeat is diagnostic and never reused as readiness. */
    synchronized MembershipAutomaticOwner.Session automaticSession(AutomaticLeadershipPolicy policy) {
        return automaticSession(policy,false);
    }
    private synchronized MembershipAutomaticOwner.Session automaticSession(AutomaticLeadershipPolicy policy,boolean freshRetry) {
        Objects.requireNonNull(policy);
        require(!closed && state==State.NEW && runner==null,"automatic owner requires unused round");
        return new MembershipAutomaticOwner.Session() {
            public Decoded start(long began)throws IOException {
                return campaignCall(()->MembershipRoundDriver.this.start(began,true,policy,(minimum,maximum)->ThreadLocalRandom.current().nextLong(minimum,maximum+1),freshRetry));
            }
            public void idle()throws IOException {
                time();synchronized(MembershipRoundDriver.this) {
                    require(!closed && state==State.READY && runner==null,"automatic owner idle state");
                    owner.checkCampaignWait(authority,ballot);
                }
            }
            public MembershipHeartbeatRound.Contact heartbeat()throws IOException {return campaignCall(()->MembershipRoundDriver.this.heartbeat());}
            public Decoded readiness()throws IOException {return campaignCall(()->MembershipRoundDriver.this.readiness());}
            public Decoded submit(String kind,byte[] payload)throws IOException {return campaignCall(()->MembershipRoundDriver.this.submit(kind,payload));}
            public void close()throws IOException {MembershipRoundDriver.this.close();}
        };
    }
    private Decoded start(long originalStarted,boolean discover)throws IOException {
        return start(originalStarted,discover,null,null);
    }
    private Decoded start(long originalStarted,boolean discover,AutomaticLeadershipPolicy policy,LongBinaryOperator jitter)throws IOException {
        return start(originalStarted,discover,policy,jitter,false);
    }
    private void discoverPrefix(boolean election)throws IOException {
        transition(State.DISCOVERING);
        MembershipPrefixRecovery child;
        try{child=new MembershipPrefixRecovery(owner,resources,bounds,transport::exchange,this::time,scratch,clock,started,budget);}
        catch(MembershipGrantJournal.HigherBallot changed) {
            if(!election || changed.getSuppressed().length!=0)throw changed;
            throw new MembershipPrefixRecovery.Superseded(changed);
        }
        boolean registered=false;Throwable failure=null;
        try {
            synchronized(this){require(!closed,"native round closed before discovery");discovery=child;registered=true;}
            var adopted=election?child.runForElection():child.run();time();
            if(adopted.isPresent()){events.at("ADOPTED",adopted.orElseThrow());time();}
        }catch(IOException|RuntimeException|Error error){failure=error;throw error;}
        finally {
            try {
                child.close();
                synchronized(this){if(registered && discovery==child)discovery=null;}
            }catch(IOException|RuntimeException cleanup){if(failure!=null)failure.addSuppressed(cleanup);else throw cleanup;}
        }
    }
    private Decoded start(long originalStarted,boolean discover,AutomaticLeadershipPolicy policy,LongBinaryOperator jitter,boolean freshRetry)throws IOException {
        enter(State.NEW,originalStarted);
        try {
            if(policy!=null) {
                workPulse=new MembershipWorkPulse(clock,TimeUnit.MILLISECONDS.toNanos(policy.heartbeatIntervalMillis()));
                boolean retryWait=freshRetry;
                for(;;) {
                    transition(State.WAITING);
                    var child=new MembershipElectionWait(owner,endpoint,resources,policy,clock,jitter,started,budget,retryWait);
                    MembershipElectionWait.Decision decision;boolean registered=false;
                    try {
                        synchronized(this){require(!closed,"native round closed before election wait");electionWait=child;registered=true;}
                        decision=child.awaitDecision();time();
                    }finally{child.close();synchronized(this){if(registered && electionWait==child)electionWait=null;}}
                    retryWait=false;
                    try{if(discover)discoverPrefix(true);}
                    catch(MembershipPrefixRecovery.Superseded changed) {
                        // Still a follower: no local grant or client operation
                        // has been attempted. Drain first, then resume the same
                        // deadline's election wait; do not consume a failed
                        // campaign round for incoming, authenticated progress.
                        if(changed.getSuppressed().length!=0)throw changed;
                        time();continue;
                    }
                    time();boolean current=decision.current(owner,endpoint,resources);time();
                    if(current)break;
                    // Discovery/adoption can outlive the expired timer. Observe
                    // the new original fence/cut/contact before campaigning.
                    // Completed heartbeats/milestones keep their arrival time.
                }
            }else if(discover)discoverPrefix(false);
            activate();return recoverAndReady();
        }catch(IOException|RuntimeException|Error error){fail(error);throw error;}
        finally{leave();}
    }
    /** The producer supplies only an operation payload; parent, ballot and index
     * are allocated here. No automatic replay of an indeterminate client call. */
    Decoded submit(String kind,byte[] bytes)throws IOException {
        validateInput(kind,bytes,bounds);
        enter(State.READY);
        try(var payloadLease=resources.reserve(MembershipResources.Unit.CONTROL,"round-input",Math.max(1,bytes.length))) {
            current();byte[] payload=bytes.clone();maintainReadyRetention();
            if(kind.equals("SEAL")){transition(State.RECOVERING);synchronized(this){barrier=null;}}
            var done=publish(entry(kind,payload),payload);
            if(kind.equals("SEAL"))recoverAndReady();
            return done;
        }catch(IOException|RuntimeException|Error error){fail(error);throw error;}
        finally{leave();}
    }
    /** Before accepting a new command, settle current copies and, at most once,
     * reconcile full renewal debt through a real fresh campaign and BARRIER.
     * The old deadline and activation attempt bound apply to the entire call.
     * No business entry exists yet, so this never replays a client mutation. */
    private void maintainReadyRetention()throws IOException {
        current();endpoint.maintainInstalled(this::pulseWhileWorking);current();
        if(owner.peerObservationReconciliationRequired()) {
            activate();recoverAndReady();current();
            require(!owner.peerObservationReconciliationRequired(),"native round retention reconciliation incomplete");
        }
    }
    /** Same serialized pre-command boundary for a private lifecycle coordinator.
     * Returned readiness still requires the normal current() check on use. */
    Decoded maintainReady()throws IOException {
        enter(State.READY);
        try{maintainReadyRetention();current();return barrier;}
        catch(IOException|RuntimeException|Error error){fail(error);throw error;}
        finally{leave();}
    }
    static void validateInput(String kind,byte[] bytes,ReplicationBounds bounds) {
        Objects.requireNonNull(bytes);require(Set.of("DATA","BARRIER","RESERVE","PREPARE","READY","SEAL","CANCEL","RETIRE").contains(kind),"native stable slot kind");
        require(bytes.length<=Math.min(FRAME,bounds.maxFrameBytes()),"native round payload bound");
        if(kind.equals("BARRIER"))require(bytes.length==0,"native barrier empty payload");
    }
    /** This guard is mandatory; state() alone is diagnostic and grants nothing. */
    Decoded readiness()throws IOException {
        enter(State.READY);
        try{current();return barrier;}
        catch(IOException|RuntimeException|Error error){fail(error);throw error;}
        finally{leave();}
    }
    /** A liveness sample of this already-ready round. Its majority grants no
     * service lease; every later operation still performs current() and votes. */
    MembershipHeartbeatRound.Contact heartbeat()throws IOException {
        enter(State.READY);
        try{return sampleHeartbeat();}
        catch(IOException|RuntimeException|Error error){fail(error);throw error;}
        finally{leave();}
    }
    /** Cooperatively service installed-campaign liveness on the single slot
     * coordinator, including carried recovery and the initial fresh BARRIER.
     * Never sample from peer workers or under the writer monitor. No heartbeat
     * enables READY: current() still requires the exact installed original cut. */
    private void pulseWhileWorking()throws IOException {
        if(Thread.holdsLock(owner))return;
        synchronized(this){if(runner!=Thread.currentThread() || workPulse==null
                || !(state==State.RECOVERING || state==State.READY && barrier!=null))return;}
        time();workPulse.due(()->{sampleHeartbeat();});time();
    }
    private MembershipHeartbeatRound.Contact sampleHeartbeat()throws IOException {
        current();long began=clock.getAsLong(),remaining=budget-(began-started);
        long limit=Math.min(remaining,TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis())*Math.min(3,bounds.maxRetryAttempts()));
        var child=new MembershipHeartbeatRound(owner,resources,bounds,transport::exchange,this::current,clock,began,limit);
        boolean registered=false;
        try {
            synchronized(this){require(!closed && heartbeat==null,"native round closed/overlapping heartbeat");heartbeat=child;registered=true;}
            var result=child.run();current();if(workPulse!=null)workPulse.completed();return result;
        }finally {child.close();synchronized(this){if(registered && heartbeat==child)heartbeat=null;}}
    }
    private void fail(Throwable original) {
        synchronized(this){if(!closed)state=State.FAILED;barrier=null;}
        try{release();}catch(IOException|RuntimeException error){original.addSuppressed(error);}
    }
    private void release()throws IOException {
        MembershipSlotDriver activeSlot;MembershipActivationDriver activeActivation;MembershipPrefixRecovery activeDiscovery;MembershipHeartbeatRound activeHeartbeat;MembershipElectionWait activeWait;
        synchronized(this){activeSlot=slot;activeActivation=activation;activeDiscovery=discovery;activeHeartbeat=heartbeat;activeWait=electionWait;}
        // Do not release the activation/parent reservation before child drain.
        if(activeSlot!=null)activeSlot.close();
        if(activeActivation!=null)activeActivation.close();
        if(activeDiscovery!=null)activeDiscovery.close();
        if(activeHeartbeat!=null)activeHeartbeat.close();
        if(activeWait!=null)activeWait.close();
        synchronized(this){selection=null;barrier=null;ballot=null;expectedCut=null;authority=null;carriedPending=false;}
        ownership.close();
    }
    @Override public void close()throws IOException {
        Thread active;MembershipPrefixRecovery activeDiscovery;MembershipHeartbeatRound activeHeartbeat;MembershipElectionWait activeWait;
        synchronized(this){closed=true;state=State.CLOSED;barrier=null;active=runner;activeDiscovery=discovery;activeHeartbeat=heartbeat;activeWait=electionWait;}
        if(active!=null && active!=Thread.currentThread() && activeDiscovery==null)active.interrupt();
        // The runner owns cleanup while executing. Child close cancels blocked
        // network work; an expired cleanup wait keeps the parent reservation.
        MembershipSlotDriver activeSlot;MembershipActivationDriver activeActivation;
        synchronized(this){activeSlot=slot;activeActivation=activation;}
        if(activeHeartbeat!=null)activeHeartbeat.close();
        if(activeWait!=null)activeWait.close();
        if(activeDiscovery!=null)activeDiscovery.close();
        else if(activeSlot!=null)activeSlot.close();
        else if(activeActivation!=null)activeActivation.close();
        if(active!=Thread.currentThread()) {
            long end=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
            try{synchronized(this){while(runner!=null){long left=end-System.nanoTime();require(left>0,"native round close timeout");
                TimeUnit.NANOSECONDS.timedWait(this,left);}}}
            catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("native round close interrupted",error);}
            release();
        }
    }
}
