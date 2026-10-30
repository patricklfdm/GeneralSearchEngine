package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Current-view incoming activation owner. One bounded control task runs separately
 * from reverse source requests. A higher verified PREPARE fences before admission;
 * duplicate controls share the original task and deadline. No election timer, newer
 * view adoption, historical witness discovery or public service READY is implied.
 * The caller closes this endpoint and its transport before closing the journal. */
final class MembershipActivationEndpoint implements MembershipTransport.Handler,AutoCloseable {
    record Usage(int waiters,int pendingExchanges,boolean controlRunning,boolean scopeEnded,boolean closed) {}
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipCurrentGeneration.Verifier verifier;
    private final boolean nativeHistory;
    @FunctionalInterface private interface Slots {MembershipSlotEndpoint open(long started,long limit)throws IOException;}
    private final Slots slots;
    private final List<MembershipSelection.Bridge> ancestry,retained;
    private final LongSupplier clock;
    private final long budget;
    private final Path scratch;
    private final MembershipScratch scratchOwner;
    private final ExecutorService controls;
    private final ScheduledExecutorService expiry;
    private final Object registry=new Object();
    private volatile Scope scope;
    private final Object prefixRegistry=new Object();
    private volatile MembershipTransferService prefixService;
    private volatile boolean closed;
    private Control control;
    private int waiters;

    MembershipActivationEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,List<MembershipSelection.Bridge> ancestry,List<MembershipSelection.Bridge> retained,
            Path scratch,LongSupplier clock,long budget)throws IOException {
        this(owner,resources,bounds,link,null,ancestry,retained,scratch,clock,budget,true,null);
    }
    /** Typed native service: installation automatically admits slot controls on
     * this same handler. Every slot inherits the grant's original deadline and
     * uses the grant's existing source registry, including failed trace markers. */
    <K,T> MembershipActivationEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,List<MembershipSelection.Bridge> ancestry,List<MembershipSelection.Bridge> retained,
            Path scratch,LongSupplier clock,long budget,
            io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage)throws IOException {
        this(owner,resources,bounds,link,null,ancestry,retained,scratch,clock,budget,true,
                slots(owner,resources,bounds,link,clock,configuration,storage));
    }
    private static <K,T> Slots slots(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,LongSupplier clock,
            io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage) {
        Objects.requireNonNull(configuration);Objects.requireNonNull(storage);
        return (started,limit)->new MembershipSlotEndpoint(owner,resources,bounds,link,clock,started,limit,
                configuration,storage,MembershipTransport.Events.NONE);
    }
    MembershipActivationEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipCurrentGeneration.Verifier verifier,
            List<MembershipSelection.Bridge> ancestry,List<MembershipSelection.Bridge> retained,
            Path scratch,LongSupplier clock,long budget)throws IOException {
        this(owner,resources,bounds,link,Objects.requireNonNull(verifier),ancestry,retained,scratch,clock,budget,false,null);
    }
    private MembershipActivationEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipCurrentGeneration.Verifier verifier,
            List<MembershipSelection.Bridge> ancestry,List<MembershipSelection.Bridge> retained,
            Path scratch,LongSupplier clock,long budget,boolean nativeHistory,Slots slots)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"activation endpoint budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.verifier=verifier;this.nativeHistory=nativeHistory;this.slots=slots;
        this.ancestry=List.copyOf(ancestry);this.retained=List.copyOf(retained);
        require(ancestry.size()<=6 && retained.size()<=6,"activation endpoint ancestry capacity");
        this.clock=Objects.requireNonNull(clock);this.budget=budget;
        scratchOwner=owner.openScratch(scratch,MembershipScratch.Role.INCOMING,resources,event->{});this.scratch=scratchOwner.directory();
        controls=Executors.newSingleThreadExecutor(Thread.ofVirtual().name("gse-membership-control-"+owner.activationIdentity().nodeId().value()).factory());
        expiry=Executors.newSingleThreadScheduledExecutor(Thread.ofPlatform().daemon().name("gse-membership-expiry-"+owner.activationIdentity().nodeId().value()).factory());
        expiry.scheduleWithFixedDelay(this::expire,100,100,TimeUnit.MILLISECONDS);
    }
    private final class Scope implements AutoCloseable {
        final MembershipCapsule capsule;
        final Map<String,Object> ballot;
        final long started,limit;
        final Set<CompletableFuture<Decoded>> pending=ConcurrentHashMap.newKeySet();
        volatile boolean ended;
        private MembershipTransferService service;
        private MembershipGenerationMaintenance maintenance;
        private final Object slotRegistry=new Object();
        private MembershipSlotEndpoint slot;
        private Map<String,Object> slotCut;
        private int slotCalls;
        private boolean slotChanging;
        Scope(MembershipCapsule capsule,Map<String,Object> ballot,long started,long limit) {
            this.capsule=capsule;this.ballot=Map.copyOf(ballot);this.started=started;this.limit=limit;
        }
        boolean expired(){long elapsed=clock.getAsLong()-started;return elapsed<0 || elapsed>=limit;}
        void check()throws IOException {
            require(!closed && !ended && !expired(),"original activation endpoint deadline/closed");
            scratchOwner.check();
            owner.checkActivationBallot(capsule.context.authority(),ballot);
            require(!closed && !ended && !expired(),"original activation endpoint deadline/closed");
        }
        void completed(MembershipIdentity sender,Decoded request,Decoded response)throws IOException {
            if(!request.kind().equals("PUBLISH") || !response.kind().equals("PUBLISH_ACK")){check();return;}
            // A forced INTENT/FINAL changes the current view. Only the exact
            // completed publication may finish under its original authority;
            // ordinary controls still use check() and cannot revive that view.
            require(!closed && !ended && !expired(),"original activation endpoint deadline/closed");scratchOwner.check();
            require(nativeHistory && request.value().get("ballot").equals(ballot)
                    && request.value().get("view").equals(capsule.context.authority()),"completed activation publication original authority");
            require(Arrays.equals(response.bytes(),owner.acknowledgePublished(sender,request).bytes()),"completed activation publication exact acknowledgement");
            require(!closed && !ended && !expired(),"original activation endpoint deadline/closed");
        }
        CompletableFuture<Decoded> exchange(MembershipIdentity peer,Decoded request,String kind,long deadline) {
            try {
                check();require(deadline==started+limit,"activation endpoint changed deadline");
                var result=Objects.requireNonNull(link.exchange(peer,request,kind,deadline));pending.add(result);
                result.whenComplete((reply,error)->pending.remove(result));
                if(closed || ended || expired())result.cancel(true);
                return result;
            }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
        }
        void granted()throws IOException {
            check();var original=owner.originalBasis().orElseThrow();owner.checkActivation(original,null,false);
            synchronized(this){if(service!=null)return;}
            var made=new MembershipTransferService(owner,ballot,resources,bounds,()->{check();owner.checkActivation(original,null,false);},clock,started,limit);
            boolean accepted=false;
            try {synchronized(this){if(!ended && !closed && service==null){service=made;accepted=true;}}}
            finally {if(!accepted)made.close();}
            check();
        }
        Decoded transfer(MembershipIdentity sender,Decoded request)throws IOException {
            require(!closed && !ended && !expired(),"original activation endpoint deadline/closed");scratchOwner.check();
            MembershipTransferService active;synchronized(this){active=service;}
            if(!owner.activationContext().authority().equals(capsule.context.authority())
                    && (active==null || !active.contains(sender,request))) {
                // Fresh checkpoint reads can finish peers' publication after a
                // view change. Existing grant traces never migrate registries.
                MembershipSlotEndpoint published;synchronized(slotRegistry){published=slot;}
                require(published!=null,"completed checkpoint slot unavailable");
                var reply=published.completedCheckpoint(sender,request);
                require(!closed && !ended && !expired(),"original activation endpoint deadline/closed");return reply;
            }
            check();require(active!=null,"activation endpoint grant not available");return active.handle(sender,request);
        }
        void maintain()throws IOException {
            maintain(false);
        }
        void maintain(boolean beforeGrant)throws IOException {
            check();if(!(beforeGrant?owner.publishedMaintenanceRequired():owner.nativeGenerationMaintenanceRequired()))return;
            var work=beforeGrant?MembershipGenerationMaintenance.beforeGrant(owner,resources,bounds,this::exchange,this::check,scratch,clock,started,limit):
                    new MembershipGenerationMaintenance(owner,resources,bounds,this::exchange,this::check,scratch,clock,started,limit);
            synchronized(this){if(ended || closed){work.close();throw new IOException("native maintenance scope ended");}
                require(maintenance==null,"native maintenance already active");maintenance=work;}
            try(work){work.run();}finally{synchronized(this){if(maintenance==work)maintenance=null;}}
        }
        Decoded nativeControl(MembershipIdentity sender,Decoded request)throws IOException {
            check();var installed=owner.voting(resources);
            require(installed.ballot.equals(ballot),"native dispatch installed ballot changed");
            installed.before.context.wire(request,sender,owner.activationIdentity(),ballot,
                    UUID.fromString((String)request.value().get("trace")),number(request.value().get("sequence")));
            MembershipSlotEndpoint chosen,old=null;boolean replace;
            synchronized(slotRegistry) {
                require(!ended && !closed,"native dispatch scope ended");
                if(slotChanging)throw new MembershipTransport.Failure(MembershipTransport.Reason.CAPACITY,"native slot handoff in progress",null);
                replace=slot==null || !installed.before.context.cut.equals(slotCut);
                if(replace) {
                    if(slotCalls!=0)throw new MembershipTransport.Failure(MembershipTransport.Reason.CAPACITY,"previous native slot still in flight",null);
                    slotChanging=true;old=slot;slot=null;slotCut=null;chosen=null;
                }else{chosen=slot;slotCalls++;}
            }
            if(replace) {
                MembershipSlotEndpoint made=null;
                try {
                    if(old!=null)old.close();check();installed.check();
                    if(!installed.carriedSlot())maintain();made=slots.open(started,limit);check();
                    synchronized(slotRegistry){require(!ended && !closed,"native dispatch replaced/closed");
                        slot=chosen=made;slotCut=installed.before.context.cut;slotCalls++;made=null;}
                }finally {
                    try{if(made!=null)made.close();}
                    finally{synchronized(slotRegistry){slotChanging=false;slotRegistry.notifyAll();}}
                }
            }
            try{
                check();
                if(request.kind().equals("PROOF") && installed.carriedSlot()) {
                    require(installed.record("ACCEPT").isPresent(),"carried maintenance requires actual new ACCEPT");
                    maintain();check();
                }
                var reply=chosen.handle(sender,request);completed(sender,request,reply);return reply;
            }
            finally{synchronized(slotRegistry){slotCalls--;slotRegistry.notifyAll();}}
        }
        @Override public void close() {
            MembershipTransferService old;MembershipSlotEndpoint oldSlot;MembershipGenerationMaintenance cleanup;
            synchronized(this){ended=true;old=service;service=null;cleanup=maintenance;}
            synchronized(slotRegistry){oldSlot=slot;slot=null;}
            for(var future:pending)future.cancel(true);
            // Never hold registry, scope or journal monitors while releasing exports.
            RuntimeException failure=null;
            for(Runnable action:List.<Runnable>of(
                    ()->{if(cleanup!=null)try{cleanup.close();}catch(IOException error){throw new UncheckedIOException(error);}},
                    ()->{if(oldSlot!=null)oldSlot.close();},()->{if(old!=null)old.close();})) {
                try{action.run();}catch(RuntimeException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
            }
            long end=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
            try{synchronized(slotRegistry){while(slotChanging || slotCalls!=0){long left=end-System.nanoTime();
                require(left>0,"native dispatch close timeout");TimeUnit.NANOSECONDS.timedWait(slotRegistry,left);}}}
            catch(InterruptedException error){Thread.currentThread().interrupt();var interrupted=new IllegalStateException("native dispatch close interrupted",error);
                if(failure==null)failure=interrupted;else failure.addSuppressed(interrupted);}
            catch(RuntimeException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
            if(failure!=null)throw failure;
        }
    }
    private Scope enter(MembershipCapsule capsule,Map<String,Object> ballot,long started,long limit)throws IOException {
        Scope old,next;
        synchronized(registry) {
            require(!closed,"activation endpoint closed");old=scope;
            if(old!=null) {
                int compared=compareBallot(ballot,old.ballot);
                require(compared>=0 && old.capsule.context.root.equals(capsule.context.root),"activation endpoint stale ballot/root");
                if(compared==0){require(old.capsule.context.authority().equals(capsule.context.authority()),"activation endpoint changed view");return old;}
            }
            scope=next=new Scope(capsule,ballot,started,limit);
        }
        if(old!=null)old.close();releaseEndedControl();next.check();return next;
    }
    /** Register the actual local campaign before any peer may fetch its PROMISE.
     * The original local start/deadline is inherited, never reset by registration. */
    void serve(MembershipActivation campaign)throws IOException {
        owner.checkActivation(campaign.ownSource().basis,null,false);
        require(campaign.ownSource().owner.equals(owner.activationIdentity()),"activation endpoint foreign campaign");
        var active=enter(campaign.ownSource().capsule,campaign.ballot(),campaign.started(),Math.min(budget,campaign.budget()));
        active.granted();
        // The newly forced promise may make an intermediate source obsolete.
        // Reclaim it while only the current generation occupies image capacity.
        if(nativeHistory)active.maintain(true);
    }
    /** Revoke only the outgoing owner's failed round, never an intervening peer scope. */
    void abandon(Map<String,Object> ballot) {
        var active=scope;if(active!=null && active.ballot.equals(ballot))active.close();releaseEndedControl();
    }
    /** Durable selection alone cannot revive an abandoned/expired serving scope. */
    void checkInstalled()throws IOException {
        require(slots!=null,"typed native endpoint required");var active=scope;
        require(active!=null,"native round requires active campaign");active.check();
        require(owner.voting(resources).ballot.equals(active.ballot),"native round endpoint ballot changed");active.check();
    }
    /** The serialized outgoing owner uses the same actual maintenance path before
     * creating its own vote. Incoming native slots invoke it automatically. */
    void maintainInstalled()throws IOException {
        require(slots!=null,"typed native endpoint required");var active=scope;
        require(active!=null,"native maintenance requires active campaign");active.check();
        synchronized(active.slotRegistry){require(!active.slotChanging && active.slotCalls==0,"native slot busy before maintenance");active.slotChanging=true;}
        try{active.maintain();}finally{synchronized(active.slotRegistry){active.slotChanging=false;active.slotRegistry.notifyAll();}}
    }
    private void releaseEndedControl() {
        synchronized(registry){if(control!=null && control.finished && control.active.ended){control.close();control=null;}}
    }
    private void expire(){var active=scope;if(active!=null && active.expired())active.close();var prefix=prefixService;if(prefix!=null)prefix.poll();releaseEndedControl();}
    private Decoded prefix(MembershipIdentity sender,Decoded request,long received)throws IOException {
        var active=prefixService;
        if(active!=null && active.contains(sender,request))return active.handle(sender,request);
        if(!request.kind().equals("CHUNK") || number(request.value().get("sequence"))!=1)return null;
        var current=owner.activationContext();
        String reference=(String)object(request.value().get("payload")).get("digest");
        if(!MembershipPrefixExport.reference(current,reference) && !MembershipLearnerDiscovery.rootReference(current,sender,reference)
                && !MembershipJoiningIntentExport.reference(current,sender,reference)
                && MembershipLearnerPrefixExport.scope(current,sender,reference)==null
                && MembershipLearnerProgressAccess.scope(current,sender,reference)==null)return null;
        synchronized(prefixRegistry) {
            require(!closed,"prefix endpoint closed");active=prefixService;
            if(active==null || !active.poll() || !active.sameCut(current.cut)) {
                if(active!=null)active.close();
                prefixService=active=MembershipTransferService.prefix(owner,resources,bounds,
                        ()->{require(!closed,"prefix endpoint closed");scratchOwner.check();},clock,received,budget,link);
            }
        }
        return active.handle(sender,request);
    }
    Usage usage(){synchronized(registry){var active=scope;return new Usage(waiters,active==null?0:active.pending.size(),control!=null && !control.finished,active==null || active.ended,closed);}}
    private final class Control implements AutoCloseable {
        final Scope active;
        final MembershipIdentity sender;
        final Decoded request;
        final CompletableFuture<Decoded> result=new CompletableFuture<>();
        final MembershipResources.Lease lease;
        boolean finished;
        Control(Scope active,MembershipIdentity sender,Decoded request) {
            this.active=active;this.sender=sender;this.request=request;
            lease=resources.reserve(MembershipResources.Unit.CONTROL,"activation-control-"+UUID.randomUUID(),request.size());
        }
        void run() {
            try {
                active.check();Decoded response;
                if(request.kind().equals("PREPARE")) {
                    try(var pull=new MembershipSourcePull(active.capsule,owner.activationIdentity(),sender,active.ballot,UUID.randomUUID(),resources,bounds,
                            active::exchange,active::check,clock,active.started,active.limit)) {
                        String digest=(String)object(request.value().get("payload")).get("promise");
                        var promise=pull.fetchRecord(digest,"PROMISE",value->{
                            require(value.value().get("view").equals(active.capsule.context.authority())
                                    && value.value().get("ballot").equals(active.ballot) && value.value().get("basisId")!=null,"activation endpoint original promise");
                        });
                        active.check();if(nativeHistory)active.maintain(true);
                        active.check();response=MembershipActivation.prepare(owner,sender,request,promise).response();active.granted();
                        // Complete same-cut retirement before advertising this
                        // grant. All selected receivers must finish PREPARE
                        // before any installation can replace a source generation.
                        if(nativeHistory)active.maintain(true);
                    }
                } else if(request.kind().equals("SELECTED")) {
                    Path destination=scratch.resolve("selected-"+UUID.randomUUID());
                    try(var incoming=nativeHistory?
                            new MembershipSelectedPull(owner,sender,request,resources,bounds,active::exchange,ancestry,retained,
                                    destination,active::check,clock,active.started,active.limit):
                            new MembershipSelectedPull(owner,sender,request,resources,bounds,active::exchange,verifier,ancestry,retained,
                                    destination,active::check,clock,active.started,active.limit)) {response=incoming.install();}
                }else response=active.nativeControl(sender,request);
                active.completed(sender,request,response);lease.reserveControl(request.size()+(long)response.size());active.completed(sender,request,response);
                synchronized(registry){finished=true;result.complete(response);}
            }catch(Throwable error){
                // SourcePull has already checked exact sender/recipient/root/view,
                // request sequence and trace before exposing this rejection.
                if(error instanceof MembershipSourcePull.Rejected rejected)try {
                    var higher=object(object(rejected.response.value().get("payload")).get("promised"));
                    active.capsule.context.ballot(higher,true);
                    if(compareBallot(higher,active.ballot)>0){owner.observeCurrent(higher);active.close();}
                }catch(RuntimeException fencing){error.addSuppressed(fencing);}
                synchronized(registry){finished=true;result.completeExceptionally(error);}
            }
            finally {synchronized(registry){finished=true;if(closed || active.ended || control!=this)close();}}
        }
        @Override public void close(){lease.close();}
    }
    @Override public Decoded handle(MembershipIdentity sender,Decoded request)throws IOException {
        long received=clock.getAsLong();require(!closed,"activation endpoint closed");String kind=request.kind();Scope active;
        boolean nativeSlot=slots!=null && (Set.of("ACCEPT","PROOF","APPLY").contains(kind)
                || (kind.equals("PUBLISH") && owner.currentCertificate().isPresent()));
        if(kind.equals("PUBLISH") && !nativeSlot) {
            // Completed publication survives the old in-memory campaign scope.
            // This path neither applies a pending certificate nor enters a round.
            require(nativeHistory,"published acknowledgement requires native endpoint");scratchOwner.check();
            var reply=owner.acknowledgePublished(sender,request);long elapsed=clock.getAsLong()-received;
            require(!closed && elapsed>=0 && elapsed<budget,"published endpoint closed/original deadline");return reply;
        }
        if(Set.of("RETENTION_INTENT","FUTURE_RETENTION_INTENT","LEARNER_RETENTION_INTENT").contains(kind)) {
            scratchOwner.check();var reply=switch(kind) {
                case "RETENTION_INTENT" -> owner.recordPeerRetention(sender,request);
                case "FUTURE_RETENTION_INTENT" -> owner.recordFutureRetention(sender,request);
                default -> owner.recordLearnerRetention(sender,request);
            };
            long elapsed=clock.getAsLong()-received;
            require(!closed && elapsed>=0 && elapsed<budget,"retention endpoint closed/original deadline");return reply;
        }
        if(kind.equals("STATUS_PROBE")) {
            // Discovery must work before a grant and after an obsolete campaign
            // ends. It neither enters/revives that scope nor observes a promise.
            scratchOwner.check();var reply=owner.discoveryStatus(sender,request);
            long elapsed=clock.getAsLong()-received;
            require(!closed && elapsed>=0 && elapsed<budget,"discovery endpoint closed/original deadline");return reply;
        }
        if(kind.equals("CHUNK") || kind.equals("TRANSFER_COMMIT")) {
            var response=prefix(sender,request,received);if(response!=null)return response;
        }
        if(kind.equals("PREPARE")) {
            // No control queue or writer monitor before the higher-ballot fence.
            owner.observeActivation(sender,request);
            active=enter(owner.activationCapsule(),object(request.value().get("ballot")),received,budget);
        } else {
            active=scope;require(active!=null,"activation endpoint scope unavailable");
            active.capsule.context.wire(request,sender,owner.activationIdentity(),active.ballot,
                    UUID.fromString((String)request.value().get("trace")),number(request.value().get("sequence")));
        }
        if(kind.equals("CHUNK") || kind.equals("TRANSFER_COMMIT"))return active.transfer(sender,request);
        active.check();
        require(kind.equals("PREPARE") || kind.equals("SELECTED") || nativeSlot,"activation endpoint control kind");
        MembershipActivation.incoming(owner,sender,request,kind);Control task;
        synchronized(registry) {
            require(!closed && active==scope && !active.ended,"activation endpoint replaced/closed");task=control;
            if(task==null || task.active!=active || !Arrays.equals(task.request.bytes(),request.bytes())) {
                if(task!=null && !task.finished) {
                    var values=new TreeMap<>(request.value());values.put("sender",request.value().get("recipient"));values.put("recipient",request.value().get("sender"));
                    values.put("payload",Map.of("promised",active.ballot,"reason","CAPACITY_EXCEEDED"));return decode(encode("wire","REJECT",values),"wire","REJECT");
                }
                if(task!=null)task.close();control=task=new Control(active,sender,request);
                try{controls.execute(task::run);}catch(RuntimeException error){task.close();control=null;throw error;}
            }
            waiters++;
        }
        try {
            long left=active.limit-(clock.getAsLong()-active.started);require(left>0,"original activation endpoint deadline");
            var response=task.result.get(left,TimeUnit.NANOSECONDS);active.completed(sender,request,response);return response;
        }catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("activation endpoint interrupted",error);}
        catch(TimeoutException error){active.close();throw new IOException("activation endpoint deadline",error);}
        catch(ExecutionException error){if(error.getCause() instanceof IOException io)throw io;if(error.getCause() instanceof RuntimeException r)throw r;throw new IOException("activation endpoint control failed",error.getCause());}
        finally {synchronized(registry){waiters--;}}
    }
    @Override public void close()throws IOException {
        synchronized(registry){closed=true;if(control!=null)control.result.completeExceptionally(new IOException("activation endpoint closed"));}
        expiry.shutdownNow();IOException failure=null;
        try{synchronized(prefixRegistry){if(prefixService!=null)prefixService.close();}}
        catch(RuntimeException error){failure=new IOException("activation prefix close failed",error);}
        try{var active=scope;if(active!=null)active.close();}
        catch(RuntimeException error){var closing=new IOException("activation scope close failed",error);if(failure==null)failure=closing;else failure.addSuppressed(closing);}
        controls.shutdownNow();
        try {boolean controlStopped=controls.awaitTermination(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS);
            boolean expiryStopped=expiry.awaitTermination(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS);
            require(controlStopped && expiryStopped,"activation endpoint close timeout");}
        catch(InterruptedException error){Thread.currentThread().interrupt();var interrupted=new IOException("activation endpoint close interrupted",error);
            if(failure==null)failure=interrupted;else failure.addSuppressed(interrupted);}
        catch(RuntimeException error){var timeout=new IOException("activation endpoint close failed",error);if(failure==null)failure=timeout;else failure.addSuppressed(timeout);}
        // A failed drain must retain ownership of storage still reachable by a
        // worker. A later close can finish it once both executors have stopped.
        if(controls.isTerminated() && expiry.isTerminated()) {
            synchronized(registry){if(control!=null){control.close();control=null;}}
            try{scratchOwner.close();}catch(IOException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
        }
        if(failure!=null)throw failure;
    }
}
