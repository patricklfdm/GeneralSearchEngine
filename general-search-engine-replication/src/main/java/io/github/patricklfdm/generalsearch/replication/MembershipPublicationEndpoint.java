package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One native applied certificate, with independent original-owner checkpoint
 * pulls before selector publication. The runtime owns this bounded scope; it
 * cannot be constructed from received hashes or a caller's expected ACK set.
 * Transfer handling stays independent of the writer, including reverse pulls. */
final class MembershipPublicationEndpoint implements MembershipTransport.Handler,AutoCloseable {
    // Current statement plus at most six renewed ancestors, each with at most
    // six original owners. Completed asynchronous results remain owned by the
    // publication writer until publication finishes, even after a pull closes.
    static final long RECEIPT_CAPACITY=7L*6*(HEADER+number(object(object(CATALOG.get("records")).get("CHECKPOINT_ACK")).get("maximum")));
    private final MembershipGrantJournal owner;
    private final MembershipGrantJournal.Publication publication;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipTransferService transfers;
    private final MembershipTransport.Events events;
    private final LongSupplier clock;
    private final long started,budget;
    private final ExecutorService writer=Executors.newSingleThreadExecutor(Thread.ofVirtual().name("gse-membership-publication").factory());
    private final ExecutorService receivers=Executors.newThreadPerTaskExecutor(Thread.ofVirtual().name("gse-membership-checkpoint-",0).factory());
    private final Set<MembershipSourcePull> pulls=new HashSet<>();
    private CompletableFuture<Void> completion;
    private volatile boolean closed;

    MembershipPublicationEndpoint(MembershipGrantJournal owner,MembershipGrantJournal.Applied applied,MembershipResources resources,
            ReplicationBounds bounds,MembershipSourcePull.Link link,LongSupplier clock,long started,long budget,MembershipTransport.Events events)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"publication endpoint budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;this.events=Objects.requireNonNull(events);
        owner.checkRetentionResources(resources);publication=owner.publication(applied);
        transfers=MembershipTransferService.publication(owner,publication,resources,bounds,this::check,clock,started,budget);
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"publication endpoint original deadline/closed");
        publication.check();elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"publication endpoint original deadline/closed");
    }
    private boolean quorum(Decoded statement,Collection<String> voters) {
        var view=object(object(statement.value().get("end")).get("view"));
        for(String side:List.of("old","new")) {var members=MembershipContext.nodes(view,side);
            if(voters.stream().filter(members::contains).count()<=members.size()/2)return false;}return true;
    }
    private MembershipSourcePull.CheckpointReceipt checkpoint(Decoded statement,String node)throws IOException {
        check();var peer=publication.before.context.identities.get(node);require(peer!=null,"publication checkpoint owner absent");
        var expected=decode(encode("records","CHECKPOINT_ACK",Map.of("root",statement.value().get("root"),"voter",node,
                "incarnation",peer.storageId().toString(),"cut",statement.value().get("end"),"statement",statement.digest())),"records","CHECKPOINT_ACK");
        MembershipSourcePull pull;
        synchronized(this) {
            check();pull=new MembershipSourcePull(publication.before,owner.activationIdentity(),peer,publication.ballot,UUID.randomUUID(),resources,bounds,
                    link,this::check,clock,started,budget);pulls.add(pull);
        }
        try(pull){var actual=pull.fetchCheckpointAcknowledgement(statement,expected);check();return actual;}
        catch(MembershipSourcePull.Rejected error) {
            var promised=object(object(error.response.value().get("payload")).get("promised"));publication.before.context.ballot(promised,true);
            if(MembershipContext.compareBallot(promised,publication.ballot)>0)owner.observeCurrent(promised);
            throw error;
        }finally{synchronized(this){pulls.remove(pull);}}
    }
    private MembershipSourcePull.CheckpointReceipt await(Future<MembershipSourcePull.CheckpointReceipt> work)throws IOException {
        try {
            long left=budget-(clock.getAsLong()-started);require(left>0,"publication endpoint original deadline/closed");
            return work.get(left,TimeUnit.NANOSECONDS);
        }catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("checkpoint wait interrupted",error);}
        catch(TimeoutException|CancellationException error){throw new IOException("checkpoint original deadline/closed",error);}
        catch(ExecutionException error) {
            var cause=error.getCause();if(cause instanceof IOException io)throw io;
            if(cause instanceof RuntimeException runtime)throw runtime;if(cause instanceof Error fatal)throw fatal;
            throw new IOException("checkpoint collection failed",cause);
        }
    }
    private MembershipSelection.Bridge collect(Decoded statement,Decoded own,MembershipContext.Owned observed)throws IOException {
        var acks=new ArrayList<Decoded>();var observations=new HashSet<MembershipContext.Owned>();var received=new TreeSet<String>();
        var view=object(object(statement.value().get("end")).get("view"));var eligible=new TreeSet<>(MembershipContext.nodes(view,"old"));eligible.addAll(MembershipContext.nodes(view,"new"));
        String local=owner.activationIdentity().nodeId().value();
        require((own!=null)==eligible.contains(local) && (own!=null)==(observed!=null),"publication own completion eligibility");
        if(own!=null){acks.add(own);observations.add(observed);received.add(local);}
        eligible.removeAll(received);
        // Launch only the next possible old/new quorum, never the whole identity
        // directory. Each original owner's transfer has its own bounded lease,
        // identical retries and the same original publication deadline. Receipt
        // order remains canonical; a failed owner is never counted as a voter.
        while(!quorum(statement,received) && !eligible.isEmpty()) {
            var planned=new TreeSet<>(received);var batch=new LinkedHashMap<String,Future<MembershipSourcePull.CheckpointReceipt>>();
            try {
                while(!quorum(statement,planned) && !eligible.isEmpty()) {
                    String node=eligible.pollFirst();planned.add(node);check();
                    batch.put(node,receivers.submit(()->{
                        try(var lease=resources.reserve(MembershipResources.Unit.CONTROL,"checkpoint-task-"+UUID.randomUUID(),1024)) {
                            return checkpoint(statement,node);
                        }
                    }));
                }
                for(var task:batch.entrySet()) {
                    try {
                        var actual=await(task.getValue());check();acks.add(actual.acknowledgement());observations.add(actual.owned());received.add(task.getKey());
                        events.at("PUBLICATION_CHECKPOINT_RECEIVED",statement,actual.acknowledgement());
                    }catch(MembershipTransport.Failure error) {
                        if(error.reason!=MembershipTransport.Reason.IO && error.reason!=MembershipTransport.Reason.DEADLINE)throw error;
                        check();
                    }
                }
            }finally{for(var task:batch.values())if(!task.isDone())task.cancel(true);}
        }
        require(quorum(statement,received),"publication checkpoint quorum unavailable");
        acks.sort(Comparator.comparing(a->(String)a.value().get("voter")));return new MembershipSelection.Bridge(statement,acks,observations);
    }
    private void publish()throws IOException {
        check();if(publication.published())return;
        var applied=publication.applied;var end=applied.votingEnd();
        var original=collect(applied.plan().statement,end.map(MembershipAppliedEndFiles.Endorsement::acknowledgement).orElse(null),
                end.map(MembershipAppliedEndFiles.Endorsement::owned).orElse(null));
        var bridges=new ArrayList<>(publication.retainedBridges());
        var parents=new ArrayList<MembershipAppliedEndFiles.ParentEndorsement>();
        end.ifPresent(owned->{parents.addAll(owned.ancestors());owned.parent().ifPresent(parents::add);});
        for(var parent:parents)bridges.add(collect(parent.statement(),parent.acknowledgement(),parent.owned()));
        check();owner.publishCurrent(applied,original.acknowledgements,original.owned,bridges);check();
    }
    @Override public Decoded handle(MembershipIdentity sender,Decoded request)throws IOException {
        check();
        if(request.kind().equals("FUTURE_RETENTION_INTENT"))return owner.recordFutureRetention(sender,request);
        if(request.kind().equals("CHUNK") || request.kind().equals("TRANSFER_COMMIT"))return transfers.handle(sender,request);
        publication.request(sender,request);CompletableFuture<Void> work;
        synchronized(this) {
            check();
            if(completion==null) {
                var lease=resources.reserve(MembershipResources.Unit.CONTROL,"publication-control-"+UUID.randomUUID(),request.size()+RECEIPT_CAPACITY);
                completion=new CompletableFuture<>();var result=completion;
                try {writer.execute(()->{Throwable failure=null;try{publish();}catch(Throwable error){failure=error;}finally{lease.close();}
                    if(failure==null)result.complete(null);else result.completeExceptionally(failure);});}
                catch(RuntimeException|Error error){lease.close();result.completeExceptionally(error);throw error;}
            }
            work=completion;
        }
        try {
            long left=budget-(clock.getAsLong()-started);require(left>0,"publication endpoint original deadline/closed");work.get(left,TimeUnit.NANOSECONDS);
            check();var response=publication.acknowledge(sender,request);check();return response;
        }catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("publication wait interrupted",error);}
        catch(TimeoutException|CancellationException error){throw new IOException("publication wait ended",error);}
        catch(ExecutionException error){var cause=error.getCause();
            if(cause instanceof MembershipSourcePull.Rejected rejected) {
                long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"publication rejection expired/closed");
                owner.activationCapsule(); // Recheck the live storage owner, without undoing a higher-ballot fence.
                var response=new TreeMap<>(request.value());response.put("sender",request.value().get("recipient"));response.put("recipient",request.value().get("sender"));
                response.put("payload",rejected.response.value().get("payload"));return decode(encode("wire","REJECT",response),"wire","REJECT");
            }
            if(cause instanceof IOException io)throw io;
            if(cause instanceof RuntimeException runtime)throw runtime;if(cause instanceof Error fatal)throw fatal;throw new IOException("publication failed",cause);}
    }
    boolean poll(){long elapsed=clock.getAsLong()-started;if(elapsed<0 || elapsed>=budget)close();return !closed;}
    @Override public void close() {
        List<MembershipSourcePull> closing;
        synchronized(this){closed=true;closing=List.copyOf(pulls);if(completion!=null)completion.cancel(true);}
        IOException failure=null;
        for(var pull:closing)try{pull.close();}catch(IOException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
        transfers.close();receivers.shutdownNow();writer.shutdown();
        try{long end=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
            require(writer.awaitTermination(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"publication writer close timeout");
            require(receivers.awaitTermination(Math.max(0,end-System.nanoTime()),TimeUnit.NANOSECONDS),"publication receivers close timeout");}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException("publication close interrupted",error);}
        if(failure!=null)throw new java.io.UncheckedIOException(failure);
    }
}
