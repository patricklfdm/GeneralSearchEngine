package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One current-view outgoing activation, owned by a serialized runtime. Peer work is
 * concurrent but only the calling thread fixes sources or consumes installation ACKs.
 * Failed selected peers cause a fresh ballot and one bounded alternative opportunity;
 * all rounds retain the original deadline. This is not an election timer or READY.
 * The caller supplies actual historical provenance and owns journal/endpoint/transport. */
final class MembershipActivationDriver implements AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipActivationEndpoint endpoint;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipCurrentGeneration.Verifier verifier;
    private final boolean nativeHistory;
    private final List<MembershipSelection.Bridge> ancestry,retained;
    private final LongSupplier clock;
    private final long budget;
    private final int maximumCampaigns;
    private final Path scratch;
    private final MembershipScratch scratchOwner;
    private final CountDownLatch finished=new CountDownLatch(1);
    private final Object lifecycle=new Object();
    private final AtomicReference<Throwable> fatal=new AtomicReference<>();
    private volatile boolean closed;
    private volatile Round active;
    private Thread runner;
    private boolean used;
    private long started;
    private int campaigns;
    private Decoded selected,basis;
    private MembershipResources.Lease resultLease;

    MembershipActivationDriver(MembershipGrantJournal owner,MembershipActivationEndpoint endpoint,
            MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,
            List<MembershipSelection.Bridge> ancestry,List<MembershipSelection.Bridge> retained,
            Path scratch,LongSupplier clock,long budget,int maximumCampaigns)throws IOException {
        this(owner,endpoint,resources,bounds,link,null,ancestry,retained,scratch,clock,budget,maximumCampaigns,true);
    }
    MembershipActivationDriver(MembershipGrantJournal owner,MembershipActivationEndpoint endpoint,
            MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,
            MembershipCurrentGeneration.Verifier verifier,List<MembershipSelection.Bridge> ancestry,
            List<MembershipSelection.Bridge> retained,Path scratch,LongSupplier clock,long budget,int maximumCampaigns)throws IOException {
        this(owner,endpoint,resources,bounds,link,Objects.requireNonNull(verifier),ancestry,retained,scratch,clock,budget,maximumCampaigns,false);
    }
    private MembershipActivationDriver(MembershipGrantJournal owner,MembershipActivationEndpoint endpoint,
            MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,
            MembershipCurrentGeneration.Verifier verifier,List<MembershipSelection.Bridge> ancestry,
            List<MembershipSelection.Bridge> retained,Path scratch,LongSupplier clock,long budget,int maximumCampaigns,
            boolean nativeHistory)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"activation driver budget");
        // A bounded invocation may consume fewer slots than this if durable sources
        // already occupy capacity. Never retire a source merely to retry a campaign.
        require(maximumCampaigns>0 && maximumCampaigns<=MembershipResources.Unit.SOURCE.count,"activation driver campaign capacity");
        require(ancestry.size()<=6 && retained.size()<=6,"activation driver ancestry capacity");
        this.owner=Objects.requireNonNull(owner);this.endpoint=Objects.requireNonNull(endpoint);
        this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);this.link=Objects.requireNonNull(link);
        this.verifier=verifier;this.nativeHistory=nativeHistory;this.ancestry=List.copyOf(ancestry);this.retained=List.copyOf(retained);
        this.clock=Objects.requireNonNull(clock);this.budget=budget;this.maximumCampaigns=maximumCampaigns;
        scratchOwner=owner.openScratch(scratch,MembershipScratch.Role.OUTGOING,resources,event->{});this.scratch=scratchOwner.directory();
    }
    private long remaining()throws IOException {
        if(closed || Thread.currentThread().isInterrupted())throw new IOException("activation driver closed/interrupted");
        scratchOwner.check();
        Throwable failure=fatal.get();if(failure!=null)throw failure("activation driver fenced/failed",failure);
        long elapsed=clock.getAsLong()-started;require(elapsed>=0 && elapsed<budget,"original activation driver deadline");return budget-elapsed;
    }
    private static IOException failure(String message,Throwable cause) {
        if(cause instanceof Error error)throw error;
        return new IOException(message,cause);
    }
    /** The returned record is only an installed selection; voting must still check its live owner. */
    Decoded run()throws IOException {
        synchronized(lifecycle){require(!used && !closed,"activation driver single use/closed");used=true;runner=Thread.currentThread();started=clock.getAsLong();}
        String deferred=null;PeerUnavailable lastUnavailable=null;
        try {
            while(campaigns<maximumCampaigns) {
                remaining();Round round=new Round();active=round;campaigns++;
                try {
                    remaining();endpoint.serve(round.campaign);round.select(deferred);round.install();remaining();
                    Decoded installed=round.campaign.votingSelection(),original=round.campaign.ownSource().basis;
                    var lease=resources.reserve(MembershipResources.Unit.CONTROL,"activation-result-"+UUID.randomUUID(),installed.size()+(long)original.size());
                    synchronized(lifecycle){if(closed){lease.close();throw new IOException("activation driver closed");}selected=installed;basis=original;resultLease=lease;}
                    round.success=true;
                }catch(PeerUnavailable error) {
                    // No same-ballot replacement. No local generation has been installed.
                    remaining();deferred=error.peer.nodeId().value();lastUnavailable=error;
                }finally {round.close();active=null;}
                if(selected!=null)return selection();
            }
            throw new IOException("activation driver campaign capacity exhausted",lastUnavailable);
        }catch(IOException|RuntimeException|Error error) {
            synchronized(lifecycle){if(resultLease!=null){resultLease.close();resultLease=null;}selected=null;}
            if(basis!=null)endpoint.abandon(object(basis.value().get("ballot")));throw error;
        }finally {finished.countDown();}
    }
    Decoded selection()throws IOException {
        remaining();synchronized(lifecycle){require(selected!=null,"activation driver installation unavailable");owner.checkActivation(basis,selected,true);remaining();return selected;}
    }
    int campaigns(){return campaigns;}
    private static final class PeerUnavailable extends IOException {
        private static final long serialVersionUID=1L;
        final MembershipIdentity peer;
        PeerUnavailable(MembershipIdentity peer,Throwable cause){super("activation peer unavailable: "+peer.nodeId().value(),cause);this.peer=peer;}
    }
    private static boolean unavailable(Throwable error) {
        if(error instanceof MembershipTransport.Failure f)return f.reason==MembershipTransport.Reason.IO || f.reason==MembershipTransport.Reason.DEADLINE || f.reason==MembershipTransport.Reason.CAPACITY;
        if(error instanceof MembershipSourcePull.Rejected r)return Set.of("CAPACITY_EXCEEDED","NOT_READY").contains(object(r.response.value().get("payload")).get("reason"));
        return false;
    }
    /** Prefer an eligible quorum excluding the failed peer, then smallest/lexical.
     * Every completed verified source still participates in first-complete selection. */
    static List<MembershipIdentity> preferred(MembershipContext context,MembershipIdentity local,String deferred) {
        require(local.equals(context.identities.get(local.nodeId().value())) && context.voters().contains(local.nodeId().value()),"activation driver current proposer identity");
        var peers=context.voters().stream().filter(n->!n.equals(local.nodeId().value())).sorted().map(context.identities::get).toList();
        List<MembershipIdentity> best=null;int bestCost=Integer.MAX_VALUE;
        for(int mask=1;mask<(1<<peers.size());mask++) {
            var names=new HashSet<String>();names.add(local.nodeId().value());var chosen=new ArrayList<MembershipIdentity>();
            for(int i=0;i<peers.size();i++)if((mask&(1<<i))!=0){chosen.add(peers.get(i));names.add(peers.get(i).nodeId().value());}
            boolean valid=true;for(String side:List.of("old","new")){var voters=list(context.view.get(side));valid&=names.stream().filter(voters::contains).count()>voters.size()/2;}
            int cost=chosen.size()+(deferred!=null && names.contains(deferred)?16:0);
            if(valid && cost<bestCost){best=List.copyOf(chosen);bestCost=cost;}
        }
        require(best!=null,"activation driver eligible source quorum");return best;
    }
    private final class Round implements AutoCloseable {
        final MembershipActivation campaign;
        final MembershipSelection.Source own;
        final MembershipSourceExport localImages;
        final List<Task> tasks=new ArrayList<>();
        final BlockingQueue<Task> completions=new ArrayBlockingQueue<>(10);
        MembershipActivationAncestry history;
        volatile boolean ended;
        boolean success;
        Round()throws IOException {
            campaign=new MembershipActivation(owner,resources,clock,started,budget);own=campaign.ownSource();
            try {localImages=(MembershipSourceExport)owner.exportTransfer(own.basis.digest(),own.capsule.context.authority(),campaign.ballot(),clock,started,budget);}
            catch(IOException|RuntimeException error){campaign.close();throw error;}
        }
        void checkBase()throws IOException {remaining();require(!ended,"activation driver round ended");owner.checkActivation(own.basis,null,false);remaining();}
        void check()throws IOException {checkBase();if(history!=null)history.recheck();}
        MembershipActivationAncestry.Resolution history(List<MembershipSelection.Source> sources)throws IOException {
            require(history==null,"activation original source set already fixed");
            if(!ancestry.isEmpty())return new MembershipActivationAncestry.Resolution(sources,ancestry);
            var received=new TreeMap<String,MembershipSourceReceive>();
            for(var task:snapshot())if(!task.install && task.received!=null && sources.stream().anyMatch(s->s.owner.equals(task.peer)))
                received.put(task.peer.nodeId().value(),task.received);
            history=new MembershipActivationAncestry(owner,resources,bounds,(peer,request,kind,deadline)->snapshot().stream()
                    .filter(t->!t.install && t.peer.equals(peer)).findFirst().orElseThrow().exchange(peer,request,kind,deadline),
                    this::checkBase,clock,started,budget,scratch.resolve("source-"+UUID.randomUUID()),received);
            try{return history.resolve(sources);}
            catch(MembershipActivationAncestry.Failure error){if(unavailable(error.getCause()))throw new PeerUnavailable(error.source,error.getCause());throw error;}
        }
        Task start(MembershipIdentity peer,boolean install)throws IOException {
            check();Decoded request=install?campaign.installation(peer):campaign.prepare(peer);
            var task=new Task(peer,request,install);synchronized(tasks){tasks.add(task);}task.thread.start();return task;
        }
        Task next(long wait)throws IOException {
            check();try {var task=completions.poll(Math.min(remaining(),Math.min(wait,TimeUnit.MILLISECONDS.toNanos(50))),TimeUnit.NANOSECONDS);check();return task;}
            catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("activation driver interrupted",error);}
        }
        void select(String deferred)throws IOException {
            var initial=preferred(own.capsule.context,own.owner,deferred);var order=new ArrayList<>(initial);
            own.capsule.context.voters().stream().sorted().map(own.capsule.context.identities::get).filter(p->!p.equals(own.owner) && !order.contains(p))
                    .sorted(Comparator.comparing(p->p.nodeId().value().equals(deferred))).forEach(order::add);
            int launched=0,pending=0;for(var peer:initial){start(peer,false);launched++;pending++;}
            long opportunity=TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis()),lastLaunch=clock.getAsLong();
            Task lastFailure=null;
            while(campaign.state()==MembershipActivation.State.PREPARING) {
                check();long waited=clock.getAsLong()-lastLaunch;
                if(launched<order.size() && (pending==0 || waited>=opportunity)) {start(order.get(launched++),false);pending++;lastLaunch=clock.getAsLong();}
                if(pending==0){require(lastFailure!=null,"activation driver empty source set");throw new PeerUnavailable(lastFailure.peer,lastFailure.error);}
                var task=next(opportunity);if(task==null)continue;pending--;
                if(task.error!=null) {
                    if(!unavailable(task.error))throw failure("activation source failed",task.error);
                    lastFailure=task;
                    if(launched<order.size()){start(order.get(launched++),false);pending++;lastLaunch=clock.getAsLong();}
                    continue;
                }
                if(nativeHistory)campaign.promised(task.peer,task.reply,task.received,task.pull,this::history);
                else campaign.promised(task.peer,task.reply,task.received,verifier,ancestry);
            }
            var selected=campaign.sources().stream().map(s->s.owner).toList();
            for(var task:snapshot())if(!selected.contains(task.peer)){task.stop();task.drain();task.release();}
            completions.clear();check();
        }
        void install()throws IOException {
            var sources=campaign.sources();var longest=MembershipActivationAncestry.longest(sources);int pending=0;
            // A selected receiver may still need this exact current generation's
            // supplemental ancestry. Keep its owner unchanged until every other
            // remote installation ACKs; generation replacement must still revoke
            // prefix exports. Local installation remains last in every case.
            for(var source:sources)if(!source.owner.equals(own.owner) && !source.owner.equals(longest.owner)){start(source.owner,true);pending++;}
            installed(pending);
            if(!longest.owner.equals(own.owner)){start(longest.owner,true);installed(1);}
            check();var images=new TreeMap<String,byte[]>();
            for(var image:own.capsule.packet.images().entrySet())images.put(image.getKey(),localImages.image(image.getKey(),image.getValue()));
            for(var task:snapshot())if(task.received!=null && sources.stream().anyMatch(s->s.owner.equals(task.peer)))images.putAll(task.received.images());
            var materialization=longest.capsule.packet;
            images.keySet().retainAll(materialization.images().keySet());materialization.verifyImages(images);
            check();campaign.installLocal(retained,images);check();
        }
        void installed(int pending)throws IOException {
            while(pending>0) {
                var task=next(TimeUnit.MILLISECONDS.toNanos(50));if(task==null)continue;pending--;
                if(task.error!=null){if(unavailable(task.error))throw new PeerUnavailable(task.peer,task.error);throw failure("activation installation failed",task.error);}
                campaign.installed(task.peer,task.reply);
            }
        }
        List<Task> snapshot(){synchronized(tasks){return List.copyOf(tasks);}}
        void stop(){ended=true;for(var task:snapshot())task.stop();}
        @Override public void close()throws IOException {
            stop();IOException failure=null;
            try {
                if(history!=null)try{history.close();}catch(IOException|RuntimeException error){failure=new IOException("activation ancestry cleanup failed",error);}
                for(var task:snapshot())try{task.drain();task.release();}catch(IOException|RuntimeException error){if(failure==null)failure=new IOException("activation peer drain/cleanup failed",error);else failure.addSuppressed(error);}
            }finally {
                localImages.close();campaign.close();if(!success || failure!=null)endpoint.abandon(object(own.basis.value().get("ballot")));
            }
            if(failure!=null)throw failure;
        }
        private final class Task {
            final MembershipIdentity peer;
            final Decoded request;
            final boolean install;
            final Thread thread;
            final CountDownLatch done=new CountDownLatch(1);
            final Set<CompletableFuture<Decoded>> pending=ConcurrentHashMap.newKeySet();
            final MembershipResources.Lease lease;
            volatile boolean stopped;
            MembershipSourcePull pull;
            MembershipSourceReceive received;
            Decoded reply;
            Throwable error;
            Task(MembershipIdentity peer,Decoded request,boolean install) {
                this.peer=peer;this.request=request;this.install=install;
                lease=resources.reserve(MembershipResources.Unit.CONTROL,"activation-task-"+UUID.randomUUID(),request.size());
                thread=Thread.ofVirtual().name("gse-membership-activation-"+peer.nodeId().value()).unstarted(this::run);
            }
            void checkTask()throws IOException {check();require(!stopped,"activation task stopped");}
            CompletableFuture<Decoded> exchange(MembershipIdentity target,Decoded frame,String kind,long deadline) {
                try {
                    checkTask();require(deadline==started+budget,"activation driver changed deadline");
                    require(frame.size()<=Math.min(FRAME,bounds.maxFrameBytes()),"activation driver request frame bound");
                    var raw=Objects.requireNonNull(link.exchange(target,frame,kind,deadline));pending.add(raw);
                    var checked=raw.thenApply(response->{
                        require(response.size()<=Math.min(FRAME,bounds.maxFrameBytes()),"activation driver response frame bound");
                        MembershipWire.correlated(frame,response,kind);
                        own.capsule.context.wire(response,target,own.owner,campaign.ballot(),UUID.fromString((String)frame.value().get("trace")),number(frame.value().get("sequence")));
                        if(response.kind().equals("REJECT")) {
                            var higher=object(object(response.value().get("payload")).get("promised"));own.capsule.context.ballot(higher,true);
                            if(compareBallot(higher,campaign.ballot())>0){owner.observeCurrent(higher);fatal.compareAndSet(null,new IOException("higher activation promise"));}
                        }
                        return response;
                    });
                    raw.whenComplete((r,e)->pending.remove(raw));checked.whenComplete((r,e)->{if(checked.isCancelled())raw.cancel(true);});
                    if(closed || ended || stopped)raw.cancel(true);return checked;
                }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
            }
            Decoded control()throws IOException {
                for(int attempt=1;attempt<=Math.min(3,bounds.maxRetryAttempts());attempt++) {
                    checkTask();var future=exchange(peer,request,install?"INSTALL_ACK":"PROMISE",started+budget);
                    try {
                        var value=future.get(remaining(),TimeUnit.NANOSECONDS);checkTask();
                        if(value.kind().equals("REJECT"))throw new MembershipSourcePull.Rejected(value);
                        lease.reserveControl(request.size()+(long)value.size());return value;
                    }catch(InterruptedException error){future.cancel(true);Thread.currentThread().interrupt();throw new IOException("activation exchange interrupted",error);}
                    catch(TimeoutException error){future.cancel(true);throw new IOException("original activation driver deadline",error);}
                    catch(CancellationException error){throw new IOException("activation exchange cancelled",error);}
                    catch(ExecutionException error) {
                        Throwable cause=error.getCause();
                        if(cause instanceof MembershipTransport.Failure f && (f.reason==MembershipTransport.Reason.IO || f.reason==MembershipTransport.Reason.DEADLINE)
                                && attempt<Math.min(3,bounds.maxRetryAttempts()))continue;
                        throw cause instanceof IOException io?io:failure("activation response failed",cause);
                    }
                }
                throw new IOException("activation exact exchange attempts exhausted");
            }
            void run() {
                try {
                    reply=control();
                    if(!install) {
                        pull=new MembershipSourcePull(own.capsule,own.owner,peer,campaign.ballot(),UUID.randomUUID(),resources,bounds,this::exchange,this::checkTask,clock,started,budget);
                        received=pull.fetch(scratch.resolve("source-"+UUID.randomUUID()),(String)object(reply.value().get("payload")).get("basis"),localImages);
                    }
                    checkTask();
                }catch(Throwable failure){error=failure;}
                finally {completions.add(this);done.countDown();}
            }
            void stop(){stopped=true;for(var future:pending)future.cancel(true);thread.interrupt();}
            void drain()throws IOException {
                // Drain is cleanup only: it never grants protocol work more time.
                boolean interrupted=Thread.interrupted();
                try {require(done.await(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"activation task drain timeout");}
                catch(InterruptedException error){interrupted=true;throw new IOException("activation drain interrupted",error);}
                finally{if(interrupted)Thread.currentThread().interrupt();}
            }
            void release()throws IOException {if(pull!=null){pull.close();pull=null;received=null;}lease.close();}
        }
    }
    @Override public void close()throws IOException {
        boolean running;
        synchronized(lifecycle){closed=true;running=used && finished.getCount()!=0;}
        var round=active;if(round!=null)round.stop();
        if(running && Thread.currentThread()!=runner) {
            try{require(finished.await(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"activation driver close timeout");}
            catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("activation driver close interrupted",error);}
        }
        round=active;if(round!=null){round.close();active=null;}
        synchronized(lifecycle){if(resultLease!=null){resultLease.close();resultLease=null;}if(basis!=null)endpoint.abandon(object(basis.value().get("ballot")));}
        scratchOwner.close();
    }
}
