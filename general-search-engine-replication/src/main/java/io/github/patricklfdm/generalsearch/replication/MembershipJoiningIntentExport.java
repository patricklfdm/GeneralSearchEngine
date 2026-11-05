package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Original pending INTENT metadata only. No image, prefix, generation, receipt
 * of installation or CHECKPOINT_ACK is exported. The learner must independently
 * acquire and retain its complete original source before using these bytes. */
final class MembershipJoiningIntentExport implements MembershipTransferExport {
    static String reference(MembershipLearnerRequest learner,Map<String,Object> cut) {
        return reference(learner.root().manifestDigest(),learner.identity(),MembershipLearnerDiscovery.request(learner.change()),cut);
    }
    private static String reference(String root,MembershipIdentity learner,Map<String,Object> request,Map<String,Object> cut) {
        return hash(canonical(Map.of("schema","gse-v53-joining-intent-reference/1.3","root",root,
                "learner",MembershipBootstrapSeed.identity(learner),"request",request,"cut",cut),16384));
    }
    /** Routing predicate only; creating an exporter still requires the live
     * native original certificate and completed application. */
    static boolean reference(MembershipContext context,MembershipIdentity reader,String digest) {
        if(context.view.get("operation")!=null || context.voters().contains(reader.nodeId().value())
                || !reader.equals(context.identities.get(reader.nodeId().value())))return false;
        for(var value:list(context.catalog.get("results"))) {
            var row=object(value);var request=object(row.get("request"));
            if(request.get("number").equals(context.catalog.get("active")) && row.get("phase").equals("SEALED"))
                return digest.equals(reference(context.root,reader,request,context.cut));
        }
        return false;
    }
    private final MembershipGrantJournal owner;
    private final MembershipGrantJournal.JoiningIntent original;
    private final MembershipIdentity reader,local;
    private final Decoded initial;
    private final MembershipResources.Lease metadata;
    private final MembershipPrefixExport borrow;
    private final byte[] bytes;
    private final String digest;
    private final Map<String,MembershipSourceExport.Content> contents;
    private boolean closed;

    MembershipJoiningIntentExport(MembershipGrantJournal owner,MembershipIdentity reader,Decoded request,
            MembershipResources resources,LongSupplier clock,long started,long budget)throws IOException {
        this.owner=Objects.requireNonNull(owner);this.reader=Objects.requireNonNull(reader);initial=request;local=owner.activationIdentity();
        synchronized(owner) {
            original=owner.joiningIntent(reader);var context=original.context();
            require(owner.discoveryState(resources).context()==context,"joining metadata actual resource owner");
            MembershipWire.envelope(request,context.root,reader,local);var payload=object(request.value().get("payload"));
            String alias=(String)payload.get("digest");
            require(request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1
                    && request.value().get("view").equals(original.request.get("expected"))
                    && request.value().get("ballot").equals(MembershipLearnerDiscovery.correlation(reader))
                    && payload.get("action").equals("REQUEST") && number(payload.get("offset"))==0 && payload.get("bytes").equals("")
                    && reference(context,reader,alias),"joining metadata original request");
            metadata=resources.reserve(MembershipResources.Unit.CONTROL,"joining-intent-"+UUID.randomUUID(),original.reservationBytes());
            MembershipPrefixExport acquired=null;
            try {
                // Share the six-borrow registry and its replacement/deadline
                // checks, without exposing the underlying prefix or images.
                acquired=owner.exportPrefix(MembershipContext.cutDigest(context.cut),object(request.value().get("ballot")),
                        (String)request.value().get("view"),resources,clock,started,budget);borrow=acquired;
                bytes=original.metadata();digest=hash(bytes);
                var content=new MembershipSourceExport.Content(digest,bytes.length,MembershipTransfer.Kind.RECORD);
                require(!alias.equals(digest),"joining metadata alias collision");contents=Map.of(alias,content,digest,content);check();
            }catch(IOException|RuntimeException|Error error){if(acquired!=null)acquired.close();metadata.close();throw error;}
        }
    }
    private void check()throws IOException {require(!closed,"joining metadata closed");original.check();borrow.references();}
    @Override public List<MembershipResources.Lease> closeReservations(){return MembershipTransferExport.ownedWithBorrow(metadata,borrow);}
    @Override public MembershipContext context(){return original.context();}
    @Override public MembershipIdentity identity(){return local;}
    @Override public Map<String,Object> ballot(){return object(initial.value().get("ballot"));}
    @Override public void request(MembershipIdentity sender,Decoded request,UUID trace) {
        require(reader.equals(sender) && Set.of("CHUNK","TRANSFER_COMMIT").contains(request.kind()),"joining metadata reader/kind");
        MembershipWire.envelope(request,context().root,reader,local);
        require(request.value().get("view").equals(initial.value().get("view")) && request.value().get("ballot").equals(ballot())
                && request.value().get("trace").equals(trace.toString()) && initial.value().get("trace").equals(trace.toString()),
                "joining metadata original correlation");
    }
    @Override public Map<String,MembershipSourceExport.Content> references()throws IOException {
        synchronized(owner){check();return contents;}
    }
    @Override public byte[] read(String digest,long offset,int maximum)throws IOException {
        synchronized(owner) {
            check();require(this.digest.equals(digest) && offset>=0 && offset<bytes.length && maximum>0 && maximum<=4*1024*1024,
                    "joining metadata exact extent");
            int from=Math.toIntExact(offset);byte[] result=Arrays.copyOfRange(bytes,from,from+(int)Math.min(maximum,bytes.length-offset));check();return result;
        }
    }
    @Override public void close(){synchronized(owner){if(!closed){closed=true;try{borrow.close();}finally{metadata.close();}}}}
}
