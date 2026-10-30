package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Ephemeral old-proposer routing data, never majority, initialization or vote
 * authority. Readers must acquire and authenticate every advertised original. */
final class MembershipJoiningPreparation implements AutoCloseable {
    static final int MAXIMUM=16384;
    private static final String SCHEMA="gse-v53-joining-preparation-hint/1.3";
    static String reference(MembershipContext context,MembershipIdentity joining) {
        return hash(canonical(Map.of("schema","gse-v53-joining-preparation-reference/1.3","root",context.root,
                "cut",context.cut,"joining",MembershipBootstrapSeed.identity(joining)),MAXIMUM));
    }
    static boolean reference(MembershipContext context,MembershipIdentity joining,String digest) {
        return MembershipJoiningRetentionExport.reference(context,joining,MembershipJoiningRetentionExport.reference(context,joining))
                && reference(context,joining).equals(digest);
    }
    static byte[] bytes(MembershipJoiningRetentionCampaign.Hint hint) {
        var sources=new TreeMap<>(hint.sources()).entrySet().stream().map(v->Map.of("node",v.getKey(),"basis",v.getValue())).toList();
        return canonical(Map.of("schema",SCHEMA,"root",hint.root(),"cut",hint.cut(),"joining",MembershipBootstrapSeed.identity(hint.joining()),
                "ballot",hint.ballot(),"sources",sources),MAXIMUM);
    }
    static MembershipJoiningRetentionCampaign.Hint read(byte[] bytes,MembershipContext context,MembershipIdentity joining,MembershipIdentity proposer) {
        require(bytes.length<=MAXIMUM,"joining preparation hint capacity");var value=object(parse(bytes,MAXIMUM));
        require(value.keySet().equals(Set.of("schema","root","cut","joining","ballot","sources")) && SCHEMA.equals(value.get("schema")),"joining preparation hint fields");
        var sources=new TreeMap<String,String>();
        for(Object raw:list(value.get("sources"))) {var row=object(raw);require(row.keySet().equals(Set.of("node","basis")),"joining preparation source fields");
            require(sources.put((String)row.get("node"),(String)row.get("basis"))==null,"joining preparation duplicate source");}
        var hint=new MembershipJoiningRetentionCampaign.Hint((String)value.get("root"),(String)value.get("cut"),
                MembershipContext.identity(object(value.get("joining"))),object(value.get("ballot")),sources);
        hint.check(context,joining);require(proposer.equals(context.identities.get(proposer.nodeId().value()))
                && proposer.nodeId().value().equals(hint.ballot().get("proposer")),"joining preparation exact proposer");
        require(Arrays.equals(bytes,bytes(hint)),"joining preparation canonical hint");return hint;
    }
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final MembershipContext context;
    private final MembershipIdentity joining;
    private final Decoded basis;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private final byte[] bytes;
    private final String alias,digest;
    private final MembershipResources.Lease metadata;
    private volatile boolean closed;
    MembershipJoiningPreparation(MembershipGrantJournal owner,MembershipResources resources,MembershipJoiningRetentionCampaign.Hint hint,
            MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"joining preparation publication budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.guard=Objects.requireNonNull(guard);
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
        synchronized(owner){context=owner.discoveryState(resources).context();joining=hint.joining();hint.check(context,joining);
            require(owner.activationIdentity().nodeId().value().equals(hint.ballot().get("proposer")),"joining preparation original proposer");
            basis=owner.originalSource().basis;hint.fragment(context,joining,owner.activationIdentity(),basis);check();
            bytes=bytes(hint);alias=reference(context,joining);digest=hash(bytes);require(!alias.equals(digest),"joining preparation alias collision");}
        metadata=resources.reserve(MembershipResources.Unit.CONTROL,"joining-preparation-publication-"+UUID.randomUUID(),2L*MAXIMUM);
        try{check();}catch(IOException|RuntimeException|Error error){metadata.close();throw error;}
    }
    void belongsTo(MembershipGrantJournal owner,MembershipResources pool)throws IOException {
        require(this.owner==owner && resources==pool,"joining preparation actual endpoint owner");check();
    }
    boolean poll(){long elapsed=clock.getAsLong()-started;if(elapsed<0 || elapsed>=budget)close();return !closed;}
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining preparation publication closed/original deadline");guard.check();
        synchronized(owner){owner.checkActivation(basis,null,false);require(owner.activationContext().cut.equals(context.cut)
                && owner.originalSelection().isEmpty(),"joining preparation publication changed/selected");}
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"joining preparation publication closed/original deadline");
    }
    MembershipTransferExport open(MembershipIdentity reader,Decoded request)throws IOException {
        check();require(joining.equals(reader) && reference(context,reader,(String)object(request.value().get("payload")).get("digest")),"joining preparation exact joining reader/reference");
        MembershipPrefixExport.envelope(context,owner.activationIdentity(),reader,request);
        var payload=object(request.value().get("payload"));require(request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1
                && request.value().get("view").equals(context.authority()) && payload.get("action").equals("REQUEST")
                && number(payload.get("offset"))==0 && payload.get("bytes").equals(""),"joining preparation initial request");
        var charge=resources.reserve(MembershipResources.Unit.CONTROL,"joining-preparation-export-"+UUID.randomUUID(),2L*MAXIMUM);
        try{check();return new Export(reader,request,charge);}catch(IOException|RuntimeException|Error error){charge.close();throw error;}
    }
    private final class Export implements MembershipTransferExport {
        private final MembershipIdentity reader;
        private final Decoded initial;
        private final MembershipResources.Lease charge;
        private volatile boolean ended;
        Export(MembershipIdentity reader,Decoded initial,MembershipResources.Lease charge){this.reader=reader;this.initial=initial;this.charge=charge;}
        private void live()throws IOException{require(!ended,"joining preparation export closed");check();}
        @Override public MembershipContext context(){return context;}
        @Override public MembershipIdentity identity(){return owner.activationIdentity();}
        @Override public Map<String,Object> ballot(){return object(initial.value().get("ballot"));}
        @Override public void request(MembershipIdentity sender,Decoded request,UUID trace) {
            require(reader.equals(sender) && Set.of("CHUNK","TRANSFER_COMMIT").contains(request.kind()),"joining preparation reader/kind");
            MembershipPrefixExport.envelope(context,identity(),reader,request);
            require(request.value().get("view").equals(initial.value().get("view")) && request.value().get("ballot").equals(ballot())
                    && request.value().get("trace").equals(trace.toString()) && initial.value().get("trace").equals(trace.toString()),"joining preparation original correlation");
        }
        @Override public Map<String,MembershipSourceExport.Content> references()throws IOException {
            live();var content=new MembershipSourceExport.Content(digest,bytes.length,MembershipTransfer.Kind.RECORD);return Map.of(alias,content,digest,content);
        }
        @Override public byte[] read(String requested,long offset,int maximum)throws IOException {
            live();require(digest.equals(requested) && offset>=0 && offset<bytes.length && maximum>0 && maximum<=4*1024*1024,"joining preparation exact extent");
            int from=Math.toIntExact(offset);byte[] result=Arrays.copyOfRange(bytes,from,from+(int)Math.min(maximum,bytes.length-offset));live();return result;
        }
        @Override public void close(){ended=true;charge.close();}
    }
    @Override public void close(){closed=true;metadata.close();}
}
