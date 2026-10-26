package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
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
    private final List<MembershipSelection.Bridge> ancestry,retained;
    private final LongSupplier clock;
    private final long budget;
    private final Path scratch;
    private final Object directoryKey;
    private final ExecutorService controls;
    private final ScheduledExecutorService expiry;
    private final Object registry=new Object();
    private volatile Scope scope;
    private volatile boolean closed;
    private Control control;
    private int waiters;
    private boolean removed;

    MembershipActivationEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipCurrentGeneration.Verifier verifier,
            List<MembershipSelection.Bridge> ancestry,List<MembershipSelection.Bridge> retained,
            Path scratch,LongSupplier clock,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"activation endpoint budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.verifier=Objects.requireNonNull(verifier);
        this.ancestry=List.copyOf(ancestry);this.retained=List.copyOf(retained);
        require(ancestry.size()<=6 && retained.size()<=6,"activation endpoint ancestry capacity");
        this.clock=Objects.requireNonNull(clock);this.budget=budget;
        this.scratch=scratch.toAbsolutePath().normalize();AdmissionPaths.safe(this.scratch.getParent());Files.createDirectory(this.scratch);
        directoryKey=MembershipBasisSources.key(this.scratch);
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
        Scope(MembershipCapsule capsule,Map<String,Object> ballot,long started,long limit) {
            this.capsule=capsule;this.ballot=Map.copyOf(ballot);this.started=started;this.limit=limit;
        }
        boolean expired(){long elapsed=clock.getAsLong()-started;return elapsed<0 || elapsed>=limit;}
        void check()throws IOException {
            require(!closed && !ended && !expired(),"original activation endpoint deadline/closed");
            owner.checkActivationBallot(capsule.context.authority(),ballot);
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
            check();MembershipTransferService active;synchronized(this){active=service;}
            require(active!=null,"activation endpoint grant not available");return active.handle(sender,request);
        }
        @Override public void close() {
            MembershipTransferService old;
            synchronized(this){ended=true;old=service;service=null;}
            for(var future:pending)future.cancel(true);
            // Never hold registry, scope or journal monitors while releasing exports.
            if(old!=null)old.close();
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
    }
    /** Revoke only the outgoing owner's failed round, never an intervening peer scope. */
    void abandon(Map<String,Object> ballot) {
        var active=scope;if(active!=null && active.ballot.equals(ballot))active.close();releaseEndedControl();
    }
    private void releaseEndedControl() {
        synchronized(registry){if(control!=null && control.finished && control.active.ended){control.close();control=null;}}
    }
    private void expire(){var active=scope;if(active!=null && active.expired())active.close();releaseEndedControl();}
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
                        active.check();response=MembershipActivation.prepare(owner,sender,request,promise).response();active.granted();
                    }
                } else {
                    try(var incoming=new MembershipSelectedPull(owner,sender,request,resources,bounds,active::exchange,verifier,ancestry,retained,
                            scratch.resolve("selected-"+UUID.randomUUID()),active::check,clock,active.started,active.limit)) {response=incoming.install();}
                }
                active.check();lease.reserveControl(request.size()+(long)response.size());active.check();
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
        if(kind.equals("PREPARE")) {
            // No control queue or writer monitor before the higher-ballot fence.
            owner.observeActivation(sender,request);
            active=enter(owner.activationCapsule(),object(request.value().get("ballot")),received,budget);
        } else {
            active=scope;require(active!=null,"activation endpoint scope unavailable");
            active.capsule.context.wire(request,sender,owner.activationIdentity(),active.ballot,
                    UUID.fromString((String)request.value().get("trace")),number(request.value().get("sequence")));
        }
        active.check();
        if(kind.equals("CHUNK") || kind.equals("TRANSFER_COMMIT"))return active.transfer(sender,request);
        require(kind.equals("PREPARE") || kind.equals("SELECTED"),"activation endpoint control kind");
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
            var response=task.result.get(left,TimeUnit.NANOSECONDS);active.check();return response;
        }catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("activation endpoint interrupted",error);}
        catch(TimeoutException error){active.close();throw new IOException("activation endpoint deadline",error);}
        catch(ExecutionException error){if(error.getCause() instanceof IOException io)throw io;if(error.getCause() instanceof RuntimeException r)throw r;throw new IOException("activation endpoint control failed",error.getCause());}
        finally {synchronized(registry){waiters--;}}
    }
    @Override public void close()throws IOException {
        synchronized(registry){closed=true;if(control!=null)control.result.completeExceptionally(new IOException("activation endpoint closed"));}
        expiry.shutdownNow();var active=scope;if(active!=null)active.close();controls.shutdownNow();
        try {require(controls.awaitTermination(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS)
                && expiry.awaitTermination(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"activation endpoint close timeout");}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("activation endpoint close interrupted",error);}
        synchronized(registry){if(control!=null){control.close();control=null;}}
        if(!removed) {AdmissionPaths.safe(scratch);require(directoryKey.equals(MembershipBasisSources.key(scratch)),"activation endpoint scratch replaced");Files.delete(scratch);removed=true;}
    }
}
