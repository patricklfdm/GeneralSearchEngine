package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Native installed-round incoming ACCEPT/PROOF, with original payload and
 * original-voter receipt pulls. One bounded writer; reverse transfers never
 * wait on that writer. Optional typed application requires exact original phased
 * observations before certification. APPLY_ACK is not publication/public READY. */
final class MembershipVotingEndpoint implements MembershipTransport.Handler,AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipGrantJournal.Voting voting;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipTransferService transfers;
    private final LongSupplier clock;
    private final long started,budget;
    @FunctionalInterface private interface Application {MembershipGrantJournal.Applied apply()throws IOException;}
    @FunctionalInterface private interface Acceptance {MembershipContext.Owned accept(Decoded entry,byte[] payload)throws IOException;}
    private final Application application;
    private final Acceptance acceptance;
    private final ExecutorService writer=Executors.newSingleThreadExecutor(Thread.ofVirtual().name("gse-membership-voting").factory());
    private final Set<MembershipSourcePull> pulls=new HashSet<>();
    private CompletableFuture<Void> completion;
    private String control;
    private volatile boolean closed;
    MembershipVotingEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,
            LongSupplier clock,long started,long budget)throws IOException {
        this(owner,resources,bounds,link,clock,started,budget,null,owner::acceptCurrent);
    }
    <K,T> MembershipVotingEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,
            LongSupplier clock,long started,long budget,io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<K,T> configuration,
            io.github.patricklfdm.generalsearch.durability.DurableStorageConfig<K,T> storage)throws IOException {
        this(owner,resources,bounds,link,clock,started,budget,()->owner.applyCurrent(configuration,storage),
                (entry,payload)->owner.acceptCurrent(entry,payload,configuration,storage));
        Objects.requireNonNull(configuration);Objects.requireNonNull(storage);
    }
    private MembershipVotingEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,
            LongSupplier clock,long started,long budget,Application application,Acceptance acceptance)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"voting endpoint budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;this.application=application;this.acceptance=Objects.requireNonNull(acceptance);
        voting=owner.voting(resources);check();transfers=new MembershipTransferService(owner,voting.ballot,resources,bounds,this::check,clock,started,budget);
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"voting endpoint original deadline/closed");
        voting.check();elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"voting endpoint original deadline/closed");
    }
    @FunctionalInterface private interface Read<T>{T read(MembershipSourcePull pull)throws IOException;}
    private <T>T pull(MembershipIdentity peer,Read<T> action)throws IOException {
        MembershipSourcePull pull;
        synchronized(this){check();pull=new MembershipSourcePull(voting.before,owner.activationIdentity(),peer,voting.ballot,UUID.randomUUID(),resources,
                bounds,link,this::check,clock,started,budget);pulls.add(pull);}
        try(pull){T result=action.read(pull);check();return result;}
        catch(MembershipSourcePull.Rejected error){var promised=object(object(error.response.value().get("payload")).get("promised"));
            voting.before.context.ballot(promised,true);if(MembershipContext.compareBallot(promised,voting.ballot)>0)owner.observeCurrent(promised);throw error;}
        finally{synchronized(this){pulls.remove(pull);}}
    }
    private void statement(Decoded record) {
        var v=record.value();var context=voting.before.context;
        require(v.get("root").equals(context.root) && v.get("authority").equals(context.authority()) && v.get("ballot").equals(voting.ballot)
                && number(v.get("index"))==number(context.cut.get("index"))+1,"incoming vote statement context");
    }
    private void execute(MembershipIdentity sender,Decoded request)throws IOException {
        voting.request(sender,request);check();if(voting.acknowledge(sender,request).isPresent())return;
        var payload=object(request.value().get("payload"));
        if(request.kind().equals("ACCEPT")) {
            pull(sender,acceptPull->{
                var accepted=acceptPull.fetchRecord((String)payload.get("acceptance"),"ACCEPT",this::statement);
                // A generic copied ACCEPT alone is not the proposer's original
                // vote, even for the locally derivable empty BARRIER payload.
                pull(sender,p->p.fetchVoteObservation(accepted));
                return pull(sender,entryPull->{
                    var entry=entryPull.fetchRecord((String)accepted.value().get("entry"),"ENTRY",value->{
                        require(value.value().get("root").equals(accepted.value().get("root")) && value.value().get("authority").equals(accepted.value().get("authority"))
                                && value.value().get("index").equals(accepted.value().get("index")),"incoming ACCEPT entry context");});
                    // Every original buffer remains accounted through its durable use.
                    return pull(sender,p->{byte[] bytes=p.fetchPayload(entry);check();var own=acceptance.accept(entry,bytes);
                        require(own.record().equals(accepted.digest()),"incoming ACCEPT actual record");check();return own;});
                });
            });
        } else if(request.kind().equals("PROOF")) {
            var accepted=voting.record("ACCEPT").orElseThrow(()->new IllegalArgumentException("incoming PROOF requires original own ACCEPT"));
            pull(sender,proofPull->{
                var proof=proofPull.fetchRecord((String)payload.get("proof"),"PROOF",value->{statement(value);voting.before.context.persistedProof(value,accepted);});
                var observations=new HashSet<MembershipContext.Owned>();
                for(Object witness:list(proof.value().get("accepts"))) {
                    String node=(String)object(witness).get("voter");var peer=voting.before.context.identities.get(node);check();
                    observations.add(peer.equals(owner.activationIdentity())?voting.observation(accepted):pull(peer,p->p.fetchVoteObservation(accepted)));
                }
                check();var own=owner.proveCurrent(proof,observations);check();return own;
            });
        } else {
            require(application!=null,"typed application endpoint required");
            var accepted=voting.record("ACCEPT").orElseThrow(()->new IllegalArgumentException("incoming APPLY requires original own ACCEPT"));
            var proof=voting.record("PROOF").orElseThrow(()->new IllegalArgumentException("incoming APPLY requires original own PROOF"));
            String reference=(String)payload.get("certificate");var certificate=owner.currentCertificate();
            if(certificate.isPresent())require(certificate.get().digest().equals(reference),"incoming APPLY original certificate conflict");
            else pull(sender,p->{
                var proposed=p.fetchRecord(reference,"CERTIFICATE",value->{statement(value);voting.before.context.persistedCertificate(value,proof,accepted);});
                var observations=new HashSet<MembershipContext.Owned>();
                for(var phase:List.of(Map.entry("accepts",accepted),Map.entry("proofs",proof)))for(Object witness:list(proposed.value().get(phase.getKey()))) {
                    var peer=voting.before.context.identities.get((String)object(witness).get("voter"));check();
                    observations.add(peer.equals(owner.activationIdentity())?voting.observation(phase.getValue()):pull(peer,source->source.fetchVoteObservation(phase.getValue())));
                }
                check();owner.certifyCurrent(proposed,observations);check();return proposed;
            });
            // A recovered original certificate resumes typed replay without
            // acquiring fresh historical observations or manufacturing votes.
            check();application.apply();check();
        }
    }

    @Override public Decoded handle(MembershipIdentity sender,Decoded request)throws IOException {
        check();require(request.size()<=Math.min(FRAME,bounds.maxFrameBytes()),"voting endpoint frame capacity");
        if(request.kind().equals("CHUNK") || request.kind().equals("TRANSFER_COMMIT"))return transfers.handle(sender,request);
        voting.request(sender,request);var duplicate=voting.acknowledge(sender,request);if(duplicate.isPresent()){check();return duplicate.get();}
        try(var waiter=resources.reserve(MembershipResources.Unit.WAITER,MembershipSourceResources.request("voting-waiter",request),0)) {
        CompletableFuture<Void> work;
        synchronized(this){check();
            if(completion!=null && !completion.isDone() && !request.digest().equals(control))
                throw new MembershipTransport.Failure(MembershipTransport.Reason.CAPACITY,"voting control already in flight",null);
            if(completion==null || !request.digest().equals(control)) {
                var lease=resources.reserve(MembershipResources.Unit.CONTROL,MembershipSourceResources.request("voting-control",request),request.size());
                completion=new CompletableFuture<>();control=request.digest();var result=completion;
                try{writer.execute(()->{Throwable failure=null;try{execute(sender,request);}catch(Throwable error){failure=error;}finally{lease.close();}
                    if(failure==null)result.complete(null);else result.completeExceptionally(failure);});}
                catch(RuntimeException|Error error){lease.close();result.completeExceptionally(error);throw error;}
            }
            work=completion;
        }
        try{long left=budget-(clock.getAsLong()-started);require(left>0,"voting endpoint original deadline/closed");work.get(left,TimeUnit.NANOSECONDS);
            check();var reply=voting.acknowledge(sender,request).orElseThrow(()->new IllegalArgumentException("native voting completion absent"));check();return reply;}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("voting wait interrupted",error);}
        catch(TimeoutException|CancellationException error){throw new IOException("voting wait ended",error);}
        catch(ExecutionException error){var cause=error.getCause();
            if(cause instanceof MembershipSourcePull.Rejected rejected) {
                long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"voting rejection expired/closed");owner.activationCapsule();
                var response=new TreeMap<>(request.value());response.put("sender",request.value().get("recipient"));response.put("recipient",request.value().get("sender"));
                response.put("payload",rejected.response.value().get("payload"));return decode(encode("wire","REJECT",response),"wire","REJECT");
            }
            if(cause instanceof IOException io)throw io;if(cause instanceof RuntimeException runtime)throw runtime;if(cause instanceof Error fatal)throw fatal;
            throw new IOException("incoming voting failed",cause);}
        }
    }
    boolean poll(){long elapsed=clock.getAsLong()-started;if(elapsed<0 || elapsed>=budget)close();return !closed;}
    @Override public void close(){List<MembershipSourcePull> closing;
        synchronized(this){closed=true;closing=List.copyOf(pulls);if(completion!=null)completion.cancel(true);}
        IOException failure=null;for(var pull:closing)try{pull.close();}catch(IOException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
        transfers.close();writer.shutdown();try{require(writer.awaitTermination(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"voting writer close timeout");}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException("voting close interrupted",error);}
        if(failure!=null)throw new java.io.UncheckedIOException(failure);
    }
}
