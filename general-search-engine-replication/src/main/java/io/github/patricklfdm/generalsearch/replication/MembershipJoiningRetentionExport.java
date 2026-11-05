package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** The actual old voter's settled frozen retention input. This read cannot
 * grant, prepare a source, narrow uncertainty or initialize the joining owner. */
final class MembershipJoiningRetentionExport implements MembershipTransferExport {
    static String reference(MembershipContext context,MembershipIdentity joining) {
        return hash(canonical(Map.of("schema","gse-v53-joining-retention-reference/1.3","root",context.root,
                "joining",MembershipBootstrapSeed.identity(joining),"cut",context.cut),16384));
    }
    static boolean reference(MembershipContext context,MembershipIdentity joining,String digest) {
        return context.view.get("operation")!=null && joining.equals(context.identities.get(joining.nodeId().value()))
                && !MembershipContext.nodes(context.view,"old").contains(joining.nodeId().value())
                && MembershipContext.nodes(context.view,"new").contains(joining.nodeId().value())
                && reference(context,joining).equals(digest);
    }
    private final MembershipGrantJournal owner;
    private final MembershipContext context;
    private final MembershipIdentity reader;
    private final Decoded initial,basis;
    private final MembershipPrefixExport borrow;
    private final MembershipResources.Lease metadata;
    private final byte[] bytes;
    private final String digest;
    private final Map<String,MembershipSourceExport.Content> contents;
    private boolean closed;
    MembershipJoiningRetentionExport(MembershipGrantJournal owner,MembershipIdentity reader,Decoded request,
            MembershipResources resources,LongSupplier clock,long started,long budget)throws IOException {
        this.owner=owner;this.reader=reader;initial=request;
        synchronized(owner) {
            context=owner.discoveryState(resources).context();var payload=object(request.value().get("payload"));String alias=(String)payload.get("digest");
            require(MembershipContext.nodes(context.view,"old").contains(owner.activationIdentity().nodeId().value())
                    && reference(context,reader,alias),"joining retention original old voter/new identity");
            MembershipPrefixExport.envelope(context,owner.activationIdentity(),reader,request);
            require(request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1
                    && request.value().get("view").equals(context.authority()) && payload.get("action").equals("REQUEST")
                    && number(payload.get("offset"))==0 && payload.get("bytes").equals(""),"joining retention initial request");
            metadata=resources.reserve(MembershipResources.Unit.CONTROL,MembershipSourceResources.request("joining-retention-export",request),3L*MembershipJoiningRetentionSeed.FRAGMENT_MAXIMUM);
            MembershipPrefixExport acquired=null;
            try {
                acquired=owner.exportPrefix(MembershipContext.cutDigest(context.cut),object(request.value().get("ballot")),
                        context.authority(),resources,clock,started,budget);borrow=acquired;
                var source=owner.originalSource();basis=source.basis;owner.checkActivation(basis,null,false);
                require(source.owner.equals(owner.activationIdentity()) && source.capsule.context.cut.equals(context.cut)
                        && basis.value().get("accepted")==null,"joining retention settled current original required");
                bytes=MembershipJoiningRetentionSeed.fragment(source);digest=hash(bytes);
                var content=new MembershipSourceExport.Content(digest,bytes.length,MembershipTransfer.Kind.RECORD);
                require(!alias.equals(digest),"joining retention alias collision");contents=Map.of(alias,content,digest,content);check();
            }catch(IOException|RuntimeException|Error error){
                long rollback=metadata.observeExportRollbackBegin(acquired);
                if(acquired!=null)acquired.close();metadata.close();metadata.observeExportRollbackReturned(rollback);throw error;
            }
        }
    }
    private void check()throws IOException {require(!closed,"joining retention export closed");borrow.references();owner.checkActivation(basis,null,false);}
    @Override public List<MembershipResources.Lease> closeReservations(){return MembershipTransferExport.ownedWithBorrow(metadata,borrow);}
    @Override public MembershipContext context(){return context;}
    @Override public MembershipIdentity identity(){return owner.activationIdentity();}
    @Override public Map<String,Object> ballot(){return object(initial.value().get("ballot"));}
    @Override public void request(MembershipIdentity sender,Decoded request,UUID trace) {
        require(reader.equals(sender) && Set.of("CHUNK","TRANSFER_COMMIT").contains(request.kind()),"joining retention reader/kind");
        MembershipPrefixExport.envelope(context,identity(),reader,request);
        require(request.value().get("view").equals(initial.value().get("view")) && request.value().get("ballot").equals(ballot())
                && request.value().get("trace").equals(trace.toString()) && initial.value().get("trace").equals(trace.toString()),"joining retention original correlation");
    }
    @Override public Map<String,MembershipSourceExport.Content> references()throws IOException {synchronized(owner){check();return contents;}}
    @Override public byte[] read(String digest,long offset,int maximum)throws IOException {
        synchronized(owner){check();require(this.digest.equals(digest) && offset>=0 && offset<bytes.length && maximum>0 && maximum<=4*1024*1024,
                "joining retention exact extent");int from=Math.toIntExact(offset);byte[] result=Arrays.copyOfRange(bytes,from,from+(int)Math.min(maximum,bytes.length-offset));check();return result;}
    }
    @Override public void close(){synchronized(owner){if(!closed){closed=true;try{borrow.close();}finally{metadata.close();}}}}
}
