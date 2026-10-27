package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One whole native slot under an already installed original selection. The
 * serialized runtime owns activation and supplies its original deadline. This
 * driver owns peer tasks/receipts through publication, not elections or READY. */
final class MembershipSlotDriver implements AutoCloseable {
    interface Events {
        Events NONE=(event,record,voters)->{};
        void at(String event,Decoded record,Set<String> voters)throws IOException;
    }
    @FunctionalInterface private interface Application {MembershipGrantJournal.Applied apply()throws IOException;}
    @FunctionalInterface private interface PeerWork {void run(MembershipIdentity peer)throws IOException;}
    // Completed receipts remain accounted after a SourcePull has released its
    // transfer buffers, through construction/forcing of proof and certificate.
    static final long RECORD_CAPACITY=65536+16384+8192+2L*16384+12L*2048+6L*4096;
    private final MembershipGrantJournal owner;
    private final MembershipActivationEndpoint endpoint;
    private final MembershipGrantJournal.Voting voting;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipTransport transport;
    private final LongSupplier clock;
    private final long started,budget;
    private final Application application;
    private final Events events;
    private final List<MembershipIdentity> peers;
    private final Set<String> selected;
    private final Decoded selection;
    private final MembershipResources.Lease ownership;
    private MembershipResources.Lease payloadLease;
    private final ExecutorService workers;
    private final Set<Future<?>> pending=new HashSet<>();
    private final Set<MembershipResources.Lease> taskLeases=new HashSet<>();
    private final Set<MembershipSourcePull> pulls=new HashSet<>();
    private final CountDownLatch finished=new CountDownLatch(1);
    private MembershipFutureRetentionQuorum future;
    private Thread runner;
    private volatile boolean closed;
    private boolean used;
    private Decoded published;
    <K,T> MembershipSlotDriver(MembershipGrantJournal owner,MembershipActivationEndpoint endpoint,MembershipResources resources,
            ReplicationBounds bounds,MembershipTransport transport,LongSupplier clock,long started,long budget,
            io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage,Events events)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"slot driver budget");this.owner=Objects.requireNonNull(owner);
        this.endpoint=Objects.requireNonNull(endpoint);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.transport=Objects.requireNonNull(transport);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        Objects.requireNonNull(configuration);Objects.requireNonNull(storage);application=()->owner.applyCurrent(configuration,storage);
        this.events=Objects.requireNonNull(events);voting=owner.voting(resources);selection=owner.originalSelection().orElseThrow();
        var local=owner.activationIdentity();require(local.nodeId().value().equals(voting.ballot.get("proposer")),"slot driver original proposer");
        var names=new TreeSet<String>();for(var row:list(selection.value().get("sources")))require(names.add((String)object(row).get("voter")),"slot driver distinct selected voter");
        require(names.contains(local.nodeId().value()) && names.size()<=6,"slot driver selected proposer/count");
        for(String side:List.of("old","new")){var voters=MembershipContext.nodes(voting.before.context.view,side);
            require(names.stream().filter(voters::contains).count()>voters.size()/2,"slot driver governing selected quorum");}
        selected=Set.copyOf(names);peers=names.stream().filter(n->!n.equals(local.nodeId().value())).map(voting.before.context.identities::get).toList();
        time();ownership=resources.reserve(MembershipResources.Unit.CONTROL,"native-slot-owner",1);
        try{workers=Executors.newFixedThreadPool(peers.size(),Thread.ofVirtual().name("gse-membership-slot-peer-",0).factory());}
        catch(RuntimeException|Error error){ownership.close();throw error;}
    }
    private void time()throws IOException {
        if(closed || Thread.currentThread().isInterrupted())throw new IOException("slot driver closed/interrupted");
        long elapsed=clock.getAsLong()-started;require(elapsed>=0 && elapsed<budget,"slot driver original deadline");
    }
    private void check()throws IOException {time();voting.check();time();}
    private void fanout(PeerWork work)throws IOException {
        check();var completions=new ExecutorCompletionService<Void>(workers);var phase=new ArrayList<Future<Void>>();
        try {
            for(var peer:peers) {
                check();var lease=resources.reserve(MembershipResources.Unit.CONTROL,"slot-peer-"+UUID.randomUUID(),1);
                synchronized(this){
                    if(closed){lease.close();throw new IOException("slot driver closed");}
                    try {taskLeases.add(lease);var task=completions.submit(()->{try(lease){check();work.run(peer);check();return null;}finally{synchronized(this){taskLeases.remove(lease);}}});phase.add(task);pending.add(task);}
                    catch(RuntimeException|Error error){taskLeases.remove(lease);lease.close();throw error;}
                }
            }
            for(int i=0;i<peers.size();i++) {
                check();var task=completions.poll(budget-(clock.getAsLong()-started),TimeUnit.NANOSECONDS);
                require(task!=null,"slot driver original deadline");task.get();check();
            }
        }catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("slot peer phase interrupted",error);}
        catch(ExecutionException error){throw failure(error.getCause());}
        catch(CancellationException error){throw new IOException("slot peer phase cancelled",error);}
        finally{synchronized(this){for(var task:phase){task.cancel(true);pending.remove(task);}}}
    }
    private static IOException failure(Throwable error) {
        if(error instanceof IOException io)return io;if(error instanceof RuntimeException runtime)throw runtime;if(error instanceof Error fatal)throw fatal;
        return new IOException("slot driver failed",error);
    }
    private Decoded request(MembershipIdentity peer,String kind,Map<String,Object> payload) {
        return MembershipActivation.frame(kind,voting.before.context,owner.activationIdentity(),peer,voting.ballot,UUID.randomUUID(),1,payload);
    }
    private void deliver(String kind,Decoded record)throws IOException {
        fanout(peer->{var payload=kind.equals("APPLY")?Map.<String,Object>of("certificate",record.digest(),"selection",selection.digest()):
                Map.<String,Object>of(kind.equals("ACCEPT")?"acceptance":"proof",record.digest());
            MembershipSlotDelivery.deliver(owner,peer,request(peer,kind,payload),resources,transport,clock,started,budget,this::check);});
    }
    private Set<MembershipContext.Owned> observations(Decoded record)throws IOException {
        var result=ConcurrentHashMap.<MembershipContext.Owned>newKeySet();result.add(voting.observation(record));
        fanout(peer->{
            var pull=new MembershipSourcePull(voting.before,owner.activationIdentity(),peer,voting.ballot,UUID.randomUUID(),resources,
                    bounds,transport::exchange,this::check,clock,started,budget);
            synchronized(this){if(closed){pull.close();throw new IOException("slot receipt closed");}pulls.add(pull);}
            try(pull){var observed=pull.fetchVoteObservation(record);check();require(result.add(observed),"slot duplicate original observation");}
            catch(MembershipSourcePull.Rejected error){var higher=object(object(error.response.value().get("payload")).get("promised"));
                voting.before.context.ballot(higher,true);if(MembershipContext.compareBallot(higher,voting.ballot)>0)owner.observeCurrent(higher);throw error;}
            finally{synchronized(this){pulls.remove(pull);}}
        });
        require(result.stream().map(MembershipContext.Owned::voter).collect(java.util.stream.Collectors.toSet()).equals(selected),"slot actual original observation set");
        return Set.copyOf(result);
    }
    private List<Map<String,Object>> witnesses(Decoded record,Set<MembershipContext.Owned> observations) {
        return observations.stream().sorted(Comparator.comparing(MembershipContext.Owned::voter)).map(observed->{
            var peer=voting.before.context.identities.get(observed.voter());
            require(peer.storageId().equals(observed.storage()) && observed.record().equals(record.digest())
                    && observed.parent().equals(MembershipContext.cutDigest(voting.before.context.cut)),"slot exact original receipt");
            return Map.<String,Object>of("voter",observed.voter(),"incarnation",observed.storage().toString(),
                    "receipt",hash(MembershipVoteReceipt.bytes(voting.before.context,peer,record)));
        }).toList();
    }
    private Decoded execute(Decoded entry,byte[] payload)throws IOException {
        check();endpoint.maintainInstalled();check();owner.acceptCurrent(entry,payload);check();
        var accept=voting.record("ACCEPT").orElseThrow();deliver("ACCEPT",accept);var accepts=observations(accept);
        var values=new TreeMap<>(accept.value());values.put("accepts",witnesses(accept,accepts));var proof=decode(encode("records","PROOF",values),"records","PROOF");
        check();owner.proveCurrent(proof,accepts);check();deliver("PROOF",proof);var proofs=observations(proof);
        values=new TreeMap<>(proof.value());values.put("proofs",witnesses(proof,proofs));var certificate=decode(encode("records","CERTIFICATE",values),"records","CERTIFICATE");
        var original=new HashSet<>(accepts);original.addAll(proofs);check();owner.certifyCurrent(certificate,original);check();
        var applied=application.apply();check();deliver("APPLY",certificate);events.at("APPLIED",certificate,selected);check();
        for(var peer:peers) {
            check();var recording=new MembershipFutureRetentionQuorum(owner,peer,voting.ballot,owner.pendingPublication(applied),resources,
                    transport::exchange,clock,started,budget);
            synchronized(this){if(closed){recording.close();throw new IOException("slot future quorum closed");}future=recording;}
            try(recording){var recorded=recording.record();check();events.at("FUTURE_QUORUM_COMPLETE",certificate,recorded.voters());check();recorded.dispatch(transport);check();}
            finally{synchronized(this){if(future==recording)future=null;}}
        }
        check();var publish=request(owner.activationIdentity(),"PUBLISH",Map.of("certificate",certificate.digest()));
        var response=endpoint.handle(owner.activationIdentity(),publish);time();
        require(response.kind().equals("PUBLISH_ACK"),"slot local publication acknowledgement");
        require(Arrays.equals(response.bytes(),owner.acknowledgePublished(owner.activationIdentity(),publish).bytes()),"slot actual completed publication");
        events.at("PUBLISHED",certificate,selected);time();return publish;
    }
    /** A failed invocation cannot be reused. The outer owner reconciles durable
     * partial work/new ballots; no client success is inferred from partial ACKs. */
    Decoded run(Decoded proposed,byte[] bytes)throws IOException {
        synchronized(this){require(!used && !closed,"slot driver single use/closed");used=true;runner=Thread.currentThread();}
        Throwable problem=null;Decoded publish=null,completed=null;boolean entered=false;
        try {
            try {
                check();Objects.requireNonNull(proposed);Objects.requireNonNull(bytes);
                require(proposed.family().equals("records") && proposed.kind().equals("ENTRY") && bytes.length<=Math.min(FRAME,bounds.maxFrameBytes()),"slot entry/payload bound");
                ownership.reserveControl(RECORD_CAPACITY);payloadLease=resources.reserve(MembershipResources.Unit.CONTROL,"slot-payload",Math.max(1,bytes.length));
                byte[] payload=bytes.clone();var entry=decode(proposed.bytes(),"records","ENTRY");
                require(entry.value().get("payload").equals(hash(payload)),"slot original payload digest");check();entered=true;publish=execute(entry,payload);
            }catch(Throwable error){problem=error;}
            try{drain();}catch(Throwable error){if(problem==null)problem=error;else problem.addSuppressed(error);}
            if(problem==null)try {
                time();completed=owner.acknowledgePublished(owner.activationIdentity(),publish);time();
                synchronized(this){require(!closed,"slot closed before completion");published=completed;}
            }catch(Throwable error){problem=error;}
            if(problem!=null) {
                if(entered)try{endpoint.abandon(voting.ballot);}catch(Throwable error){problem.addSuppressed(error);}
                throw failure(problem);
            }
            return completed;
        }finally{synchronized(this){runner=null;finished.countDown();}if(closed)release();}
    }
    synchronized Optional<Decoded> published(){return Optional.ofNullable(published);}
    private void stop()throws IOException {
        List<MembershipSourcePull> closing;MembershipFutureRetentionQuorum recording;
        synchronized(this){for(var task:pending)task.cancel(true);closing=List.copyOf(pulls);recording=future;}
        IOException problem=null;
        try{if(recording!=null)recording.close();}catch(RuntimeException error){problem=new IOException("slot recording close failed",error);}
        for(var pull:closing)try{pull.close();}catch(IOException|RuntimeException error){var failure=error instanceof IOException io?io:new IOException("slot receipt close failed",error);
            if(problem==null)problem=failure;else problem.addSuppressed(failure);}
        workers.shutdownNow();if(problem!=null)throw problem;
    }
    private void drain()throws IOException {
        IOException problem=null;try{stop();}catch(IOException error){problem=error;}
        boolean interrupted=Thread.interrupted();
        try{require(workers.awaitTermination(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"slot workers close timeout");}
        catch(InterruptedException error){interrupted=true;var failure=new IOException("slot workers close interrupted",error);if(problem==null)problem=failure;else problem.addSuppressed(failure);}
        finally{if(interrupted)Thread.currentThread().interrupt();}
        if(workers.isTerminated())synchronized(this){for(var lease:taskLeases)lease.close();taskLeases.clear();}
        if(problem!=null)throw problem;
    }
    private synchronized void release(){if(workers.isTerminated()){if(payloadLease!=null)payloadLease.close();ownership.close();}}
    @Override public void close()throws IOException {
        Thread active;boolean wait;
        synchronized(this){closed=true;active=runner;wait=used && active!=Thread.currentThread();
            if(active!=null && active!=Thread.currentThread())active.interrupt();}
        IOException problem=null;try{stop();}catch(IOException error){problem=error;}
        if(wait)try{require(finished.await(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"slot driver close timeout");}
        catch(InterruptedException error){Thread.currentThread().interrupt();var failure=new IOException("slot driver close interrupted",error);if(problem==null)problem=failure;else problem.addSuppressed(failure);}
        if(!used || finished.getCount()==0) {
            try{drain();}catch(IOException error){if(problem==null)problem=error;else problem.addSuppressed(error);}
            release();
        }
        if(problem!=null)throw problem;
    }
}
