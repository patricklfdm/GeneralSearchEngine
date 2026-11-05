package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Read-only initialization observation. Neither these bytes nor a successful
 * probe is a vote, installed selection, read barrier or public READY. */
final class MembershipJoiningCompletion implements MembershipTransferExport {
    static final int MAXIMUM=16384;
    static String reference(MembershipContext context,MembershipIdentity joining) {
        return hash(canonical(Map.of("schema","gse-v53-joining-completion-reference/1.3","root",context.root,
                "cut",context.cut,"joining",MembershipBootstrapSeed.identity(joining)),MAXIMUM));
    }
    static boolean reference(MembershipContext context,MembershipIdentity joining,String digest) {
        return MembershipJoiningRetentionExport.reference(context,joining,MembershipJoiningRetentionExport.reference(context,joining))
                && reference(context,joining).equals(digest);
    }
    static byte[] bytes(MembershipContext context,MembershipIdentity joining) {
        require(reference(context,joining,reference(context,joining)),"joining completion exact new joint identity");
        return canonical(Map.of("schema","gse-v53-joining-completion/1.3","root",context.root,
                "cut",context.cut,"joining",MembershipBootstrapSeed.identity(joining)),MAXIMUM);
    }
    static void read(byte[] bytes,MembershipContext context,MembershipIdentity joining) {
        require(bytes.length<=MAXIMUM && Arrays.equals(bytes,bytes(context,joining)),"joining completion exact canonical observation");
    }
    private static void initial(MembershipContext context,MembershipIdentity local,MembershipIdentity reader,Decoded request) {
        var payload=object(request.value().get("payload"));
        require(reference(context,local,(String)payload.get("digest")) && MembershipContext.nodes(context.view,"old").contains(reader.nodeId().value()),
                "joining completion original joining owner/old reader");
        MembershipPrefixExport.envelope(context,local,reader,request);
        require(request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1
                && request.value().get("view").equals(context.authority()) && payload.get("action").equals("REQUEST")
                && number(payload.get("offset"))==0 && payload.get("bytes").equals(""),"joining completion initial request");
    }
    static Decoded unavailable(MembershipGrantJournal owner,MembershipResources resources,MembershipIdentity reader,Decoded request)throws IOException {
        synchronized(owner){var current=owner.discoveryState(resources);initial(current.context(),owner.activationIdentity(),reader,request);
            var values=new TreeMap<>(request.value());values.put("sender",request.value().get("recipient"));values.put("recipient",request.value().get("sender"));
            values.put("payload",Map.of("promised",current.ballot(),"reason","NOT_READY"));return decode(encode("wire","REJECT",values),"wire","REJECT");}
    }
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final MembershipContext context;
    private final MembershipIdentity reader;
    private final Map<String,Object> fence;
    private final Decoded first;
    private final LongSupplier clock;
    private final long started,budget;
    private final MembershipResources.Lease metadata;
    private final byte[] bytes;
    private final String digest,alias;
    private volatile boolean closed;
    MembershipJoiningCompletion(MembershipGrantJournal owner,MembershipIdentity reader,Decoded request,MembershipResources resources,
            LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"joining completion original budget");
        this.owner=Objects.requireNonNull(owner);this.reader=Objects.requireNonNull(reader);first=request;this.resources=Objects.requireNonNull(resources);
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        synchronized(owner){owner.joiningEndpointReady(resources);var current=owner.discoveryState(resources);context=current.context();fence=current.ballot();
            initial(context,owner.activationIdentity(),reader,request);check();}
        metadata=resources.reserve(MembershipResources.Unit.CONTROL,"joining-completion-export-"+UUID.randomUUID(),2L*MAXIMUM);
        try{bytes=bytes(context,owner.activationIdentity());digest=hash(bytes);alias=reference(context,owner.activationIdentity());
            require(!digest.equals(alias),"joining completion alias collision");check();}
        catch(IOException|RuntimeException|Error error){metadata.close();throw error;}
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining completion closed/original deadline");
        synchronized(owner){owner.joiningEndpointReady(resources);owner.checkActivationBallot(context.authority(),fence);
            require(owner.activationContext().cut.equals(context.cut),"joining completion original cut changed");}
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining completion closed/original deadline");
    }
    @Override public List<MembershipResources.Lease> closeReservations(){return List.of(metadata);}
    @Override public MembershipContext context(){return context;}
    @Override public MembershipIdentity identity(){return owner.activationIdentity();}
    @Override public Map<String,Object> ballot(){return object(first.value().get("ballot"));}
    @Override public void request(MembershipIdentity sender,Decoded request,UUID trace) {
        require(reader.equals(sender) && Set.of("CHUNK","TRANSFER_COMMIT").contains(request.kind()),"joining completion reader/kind");
        MembershipPrefixExport.envelope(context,identity(),reader,request);
        require(request.value().get("view").equals(first.value().get("view")) && request.value().get("ballot").equals(ballot())
                && request.value().get("trace").equals(trace.toString()) && first.value().get("trace").equals(trace.toString()),"joining completion original correlation");
    }
    @Override public Map<String,MembershipSourceExport.Content> references()throws IOException {
        check();var content=new MembershipSourceExport.Content(digest,bytes.length,MembershipTransfer.Kind.RECORD);return Map.of(alias,content,digest,content);
    }
    @Override public byte[] read(String requested,long offset,int maximum)throws IOException {
        check();require(digest.equals(requested) && offset>=0 && offset<bytes.length && maximum>0 && maximum<=4*1024*1024,"joining completion exact extent");
        int from=Math.toIntExact(offset);byte[] result=Arrays.copyOfRange(bytes,from,from+(int)Math.min(maximum,bytes.length-offset));check();return result;
    }
    @Override public void close(){closed=true;metadata.close();}

    /** One probe under the original old preparation. An explicit initial absence
     * returns false; failures never become success or a new preparation ballot. */
    static final class Probe implements AutoCloseable {
        private final MembershipGrantJournal owner;
        private final MembershipResources resources;
        private final MembershipSourcePull.Guard guard;
        private final MembershipContext context;
        private final MembershipJoiningRetentionCampaign.Hint hint;
        private final LongSupplier clock;
        private final long started,budget;
        private final MembershipInitializationTask task;
        private final MembershipSourcePull pull;
        private boolean found;
        private volatile boolean closed;
        Probe(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,
                MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget,MembershipJoiningRetentionCampaign.Hint hint)throws IOException {
            require(budget>0 && budget<Long.MAX_VALUE/2,"joining completion probe original budget");
            this.owner=owner;this.resources=resources;this.guard=guard;this.hint=hint;this.clock=clock;this.started=started;this.budget=budget;
            context=owner.discoveryState(resources).context();
            hint.check(context,hint.joining());require(owner.activationIdentity().nodeId().value().equals(hint.ballot().get("proposer")),"joining completion original proposer");
            task=new MembershipInitializationTask(bounds.requestTimeoutMillis());check();
            pull=MembershipSourcePull.prefix(owner,new MembershipDiscovery.Hint(hint.joining(),context.cut,false),resources,bounds,link,this::check,clock,started,budget);
        }
        private void check()throws IOException {
            long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining completion probe closed/original deadline");
            guard.check();var basis=owner.originalSource().basis;
            hint.fragment(context,hint.joining(),owner.activationIdentity(),basis);owner.checkActivation(basis,null,false);
            require(owner.activationContext().cut.equals(context.cut) && owner.originalSelection().isEmpty(),"joining completion preparation changed/selected");
            elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining completion probe closed/original deadline");
        }
        boolean run()throws IOException {
            task.execute(()->new MembershipInitializationTask.Action(){
                @Override public void run()throws IOException {
                    try(var metadata=resources.reserve(MembershipResources.Unit.CONTROL,"joining-completion-probe-"+UUID.randomUUID(),4L*MAXIMUM)) {
                        check();try {byte[] bytes=pull.fetchPrefixMetadata(reference(context,hint.joining()),MAXIMUM);check();read(bytes,context,hint.joining());check();found=true;}
                        catch(MembershipSourcePull.Rejected rejection){check();var payload=object(rejection.response.value().get("payload"));context.ballot(payload.get("promised"),true);
                            if(!payload.get("reason").equals("NOT_READY") || number(rejection.response.value().get("sequence"))!=1)throw rejection;}
                    }
                }
                @Override public void close()throws IOException{pull.close();}
            });check();return found;
        }
        @Override public void close()throws IOException{closed=true;pull.close();task.close();}
    }
}
