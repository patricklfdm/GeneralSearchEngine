package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.function.LongSupplier;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Original joined-owner dispatch: read-only before durable retention, then a
 * drained handoff to the ordinary typed activation endpoint. No public READY. */
final class MembershipJoiningEndpoint<K,T> implements MembershipTransport.Handler,AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final Path scratch;
    private final LongSupplier clock;
    private final long started,budget;
    private final SearchEngineConfiguration<K,T> configuration;
    private final DurableStorageConfig<K,T> storage;
    private final MembershipEndpointHandoff handoff;
    private final MembershipInitializationTask initialization;
    private volatile MembershipActivationEndpoint voting;
    private volatile boolean closed;
    MembershipJoiningEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,Path scratch,LongSupplier clock,long started,long budget,
            SearchEngineConfiguration<K,T> configuration,DurableStorageConfig<K,T> storage)throws IOException {
        this(owner,resources,bounds,link,scratch,clock,started,budget,configuration,storage,false);
    }
    static <K,T> MembershipJoiningEndpoint<K,T> resume(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,Path scratch,LongSupplier clock,long budget,
            SearchEngineConfiguration<K,T> configuration,DurableStorageConfig<K,T> storage)throws IOException {
        return new MembershipJoiningEndpoint<>(owner,resources,bounds,link,scratch,clock,clock.getAsLong(),budget,configuration,storage,true);
    }
    private MembershipJoiningEndpoint(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,Path scratch,LongSupplier clock,long started,long budget,
            SearchEngineConfiguration<K,T> configuration,DurableStorageConfig<K,T> storage,boolean resume)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"joining endpoint initialization budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.scratch=Objects.requireNonNull(scratch);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;this.configuration=Objects.requireNonNull(configuration);this.storage=Objects.requireNonNull(storage);
        initialization=new MembershipInitializationTask(bounds.requestTimeoutMillis());initialTime();
        MembershipEndpointHandoff.Endpoint first;
        if(resume)first=openVoting();
        else {var original=owner.joiningRetentionPreparation(resources);first=new ReadOnly(owner,resources,bounds,original::check,clock,started,budget);}
        try{handoff=new MembershipEndpointHandoff(first,resume,resources,bounds.requestTimeoutMillis());}
        catch(RuntimeException|Error error){try{first.close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    private void initialTime() {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining endpoint original initialization deadline/closed");
    }
    private MembershipEndpointHandoff.Endpoint openVoting()throws IOException {
        initialTime();owner.joiningEndpointReady(resources);
        var made=new MembershipActivationEndpoint(owner,resources,bounds,link,List.of(),List.of(),scratch,clock,budget,configuration,storage);
        try{owner.joiningEndpointReady(resources);initialTime();voting=made;}
        catch(IOException|RuntimeException|Error error){try{made.close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
        return new MembershipEndpointHandoff.Endpoint(){
            @Override public Decoded handle(MembershipIdentity peer,Decoded request)throws IOException {owner.joiningEndpointReady(resources);return made.handle(peer,request);}
            @Override public void close()throws IOException{made.close();}
        };
    }
    /** The original forced completion and all three live ledgers are mandatory.
     * New voting campaigns retain the normal endpoint's per-campaign deadlines. */
    private void activate()throws IOException {
        initialTime();owner.joiningEndpointReady(resources);handoff.replace(this::openVoting);
    }
    /** Own acquisition through force completion and dispatch handoff. The hint
     * is routing data; only the acquisition's original owner may initialize. */
    void initialize(MembershipJoiningRetentionCampaign.Hint prepared)throws IOException {
        Objects.requireNonNull(prepared);initialTime();
        require(handoff.state()==MembershipEndpointHandoff.State.READ_ONLY,"joining initialization requires read-only endpoint");
        var admitted=new java.util.concurrent.atomic.AtomicBoolean();
        try {
            initialization.execute(()->{
                admitted.set(true);initialTime();var acquisition=new MembershipJoiningRetentionAcquisition(owner,resources,bounds,link,
                        this::initialTime,clock,started,budget,prepared);
                return new MembershipInitializationTask.Action(){
                    @Override public void run()throws IOException {
                        acquisition.fetch();initialTime();owner.initializeJoinedRetention(acquisition);initialTime();activate();
                    }
                    @Override public void close(){acquisition.close();}
                };
            });
        }catch(IOException|RuntimeException|Error error){
            if(admitted.get())try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;
        }
    }
    MembershipActivationEndpoint votingEndpoint()throws IOException {
        require(!closed && handoff.state()==MembershipEndpointHandoff.State.ACTIVE,"joining voting endpoint unavailable");
        owner.joiningEndpointReady(resources);return Objects.requireNonNull(voting);
    }
    MembershipEndpointHandoff.State state(){return handoff.state();}
    @Override public Decoded handle(MembershipIdentity sender,Decoded request)throws IOException {
        require(!closed,"joining endpoint closed");return handoff.handle(sender,request);
    }
    @Override public void close()throws IOException{closed=true;initialization.close();handoff.close();}

    /** Nonvoting read component. It can serve conditional data in tests; only the
     * enclosing original-owner constructor may promote to a voting endpoint. */
    static final class ReadOnly implements MembershipEndpointHandoff.Endpoint {
        private final MembershipGrantJournal owner;
        private final MembershipContext context;
        private final MembershipResources resources;
        private final MembershipTransferService transfers;
        private final MembershipSourcePull.Guard guard;
        private final LongSupplier clock;
        private final long started,budget;
        private final int maximum;
        private volatile boolean closed;
        ReadOnly(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Guard guard,
                LongSupplier clock,long started,long budget)throws IOException {
            this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.guard=Objects.requireNonNull(guard);
            this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;require(budget>0 && budget<Long.MAX_VALUE/2,"joining read budget");
            context=owner.discoveryState(resources).context();var joining=owner.activationIdentity();
            require(MembershipJoiningRetentionExport.reference(context,joining,MembershipJoiningRetentionExport.reference(context,joining)),"joining read exact new joint owner");
            maximum=Math.min(FRAME,bounds.maxFrameBytes());check();transfers=MembershipTransferService.prefix(owner,resources,bounds,this::check,clock,started,budget);
        }
        private void check()throws IOException {
            long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining read original deadline/closed");guard.check();
            require(owner.discoveryState(resources).context().cut.equals(context.cut),"joining read current cut changed");
            elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining read original deadline/closed");
        }
        @Override public Decoded handle(MembershipIdentity sender,Decoded request)throws IOException {
            check();require(request.size()<=maximum && Set.of("STATUS_PROBE","CHUNK","TRANSFER_COMMIT").contains(request.kind())
                    && MembershipContext.nodes(context.view,"old").contains(sender.nodeId().value()),"joining read refuses voting or non-old reader");
            Decoded reply;
            if(request.kind().equals("STATUS_PROBE"))reply=owner.discoveryStatus(sender,request);
            else {
                if(!transfers.contains(sender,request))require(request.kind().equals("CHUNK")
                        && MembershipPrefixExport.reference(context,(String)object(request.value().get("payload")).get("digest")),"joining read prefix/generation only");
                reply=transfers.handle(sender,request);
            }
            check();return reply;
        }
        @Override public void close(){closed=true;transfers.close();}
    }
}
