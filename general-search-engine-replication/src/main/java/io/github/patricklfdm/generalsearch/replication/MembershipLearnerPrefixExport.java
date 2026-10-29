package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Complete native source borrow scoped to one exact current learner reservation.
 * Shares original prefix ownership; it grants neither admission nor a new vote. */
final class MembershipLearnerPrefixExport implements MembershipTransferExport {
    static final Set<String> SCOPES=Set.of("prefix","ancestry","generation");
    static String reference(MembershipLearnerRequest learner,Map<String,Object> cut,String scope) {
        return reference(learner.root().manifestDigest(),learner.identity(),MembershipLearnerDiscovery.request(learner.change()),cut,scope);
    }
    private static String reference(String root,MembershipIdentity learner,Map<String,Object> request,Map<String,Object> cut,String scope) {
        require(SCOPES.contains(scope),"learner prefix scope");
        return hash(canonical(Map.of("schema","gse-v53-learner-source-reference/1.3","root",root,
                "learner",MembershipBootstrapSeed.identity(learner),"request",request,"cut",cut,"scope",scope),16384));
    }
    static String scope(MembershipContext context,MembershipIdentity learner,String reference) {
        if(context.voters().contains(learner.nodeId().value()) || !learner.equals(context.identities.get(learner.nodeId().value()))
                || context.catalog.get("active")==null || context.view.get("operation")!=null)return null;
        var operation=list(context.catalog.get("results")).stream().map(MembershipFormat::object)
                .filter(row->object(row.get("request")).get("number").equals(context.catalog.get("active"))).findFirst().orElseThrow();
        for(String scope:SCOPES)if(reference.equals(reference(context.root,learner,object(operation.get("request")),context.cut,scope)))return scope;
        return null;
    }
    static void originalReservation(MembershipContext context,MembershipLearnerRequest request,MembershipIdentity source) {
        var original=MembershipLearnerDiscovery.reservation(context,request.identity());
        require(context.root.equals(request.root().manifestDigest()) && original.equals(MembershipLearnerDiscovery.request(request.change()))
                && context.authority().equals(request.change().expectedConfigurationDigest())
                && source.equals(context.identities.get(source.nodeId().value())) && context.voters().contains(source.nodeId().value()),
                "learner prefix exact original reservation/source");
    }
    private final MembershipGrantJournal owner;
    private final MembershipCapsule original;
    private final MembershipIdentity reader;
    private final boolean progress;
    private final MembershipLearnerRetentionQuorum.Recording recording;
    private final MembershipResources resources;
    private final MembershipPrefixExport borrow;
    private final Map<String,MembershipSourceExport.Content> references;
    private boolean closed;
    MembershipLearnerPrefixExport(MembershipGrantJournal owner,MembershipIdentity reader,Decoded request,
            MembershipResources resources,LongSupplier clock,long started,long budget)throws IOException {
        this(owner,reader,request,resources,clock,started,budget,false);
    }
    MembershipLearnerPrefixExport(MembershipGrantJournal owner,MembershipIdentity reader,Decoded request,
            MembershipResources resources,LongSupplier clock,long started,long budget,boolean progress)throws IOException {
        this(owner,reader,request,resources,clock,started,budget,progress,null);
    }
    MembershipLearnerPrefixExport(MembershipGrantJournal owner,MembershipIdentity reader,Decoded request,
            MembershipResources resources,LongSupplier clock,long started,long budget,boolean progress,
            MembershipLearnerRetentionQuorum.Recording recording)throws IOException {
        this.owner=Objects.requireNonNull(owner);this.reader=Objects.requireNonNull(reader);this.progress=progress;
        this.recording=recording;this.resources=resources;
        synchronized(owner) {
            retention();original=owner.activationCapsule();
            require(owner.discoveryState(resources).context()==original.context,"learner prefix shared exclusive owner");
            String scope=checkRequest(original.context,reader,owner.activationIdentity(),request,progress);
            String alias=(String)object(request.value().get("payload")).get("digest");
            String reference=switch(scope) {
                case "prefix"->cutDigest(original.context.cut);
                case "ancestry"->MembershipPrefixExport.ancestryReference(original.context);
                default->MembershipPrefixExport.generationReference(original.context);
            };
            borrow=owner.exportPrefix(reference,object(request.value().get("ballot")),(String)request.value().get("view"),resources,clock,started,budget);
            try {
                var refs=new TreeMap<>(borrow.references());var first=refs.remove(reference);
                require(first!=null && refs.putIfAbsent(alias,first)==null,"learner prefix alias collision");references=Map.copyOf(refs);check();
            }catch(IOException|RuntimeException|Error error){borrow.close();throw error;}
        }
    }
    static String checkRequest(MembershipContext context,MembershipIdentity reader,MembershipIdentity source,Decoded request,boolean progress) {
        MembershipWire.envelope(request,context.root,reader,source);
        var reservation=progress?object(MembershipLearnerProgressAccess.operation(context,reader).get("request")):
                MembershipLearnerDiscovery.reservation(context,reader);
        var payload=object(request.value().get("payload"));String alias=(String)payload.get("digest");
        String scope=progress?MembershipLearnerProgressAccess.scope(context,reader,alias):scope(context,reader,alias);
        require(scope!=null && request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1
                && request.value().get("view").equals(reservation.get("expected"))
                && request.value().get("ballot").equals(MembershipLearnerDiscovery.correlation(reader))
                && payload.get("action").equals("REQUEST") && number(payload.get("offset"))==0 && payload.get("bytes").equals(""),
                "learner prefix original request");
        return scope;
    }
    private void retention()throws IOException {
        if(recording==null)owner.checkLearnerRetentionExport();else recording.checkExport(owner,reader,resources);
    }
    private void check()throws IOException {
        require(!closed && owner.activationCapsule()==original,"learner prefix original generation replaced/closed");
        retention();
        if(progress)MembershipLearnerProgressAccess.operation(original.context,reader);
        else MembershipLearnerDiscovery.reservation(original.context,reader);
        borrow.references();
    }
    @Override public MembershipContext context(){return original.context;}
    @Override public MembershipIdentity identity(){return borrow.identity();}
    @Override public Map<String,Object> ballot(){return borrow.ballot();}
    @Override public void request(MembershipIdentity sender,Decoded request,UUID session) {
        require(reader.equals(sender),"learner prefix reader");borrow.request(sender,request,session);
    }
    @Override public Map<String,MembershipSourceExport.Content> references()throws IOException {
        synchronized(owner){check();return references;}
    }
    @Override public byte[] read(String digest,long offset,int maximum)throws IOException {
        synchronized(owner){check();byte[] bytes=borrow.read(digest,offset,maximum);check();return bytes;}
    }
    @Override public void close(){synchronized(owner){if(!closed){closed=true;borrow.close();}}}
}
