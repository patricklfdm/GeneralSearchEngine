package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Context checks against an already verified applied cut and owned inventory, never a source of authority by itself. */
final class MembershipContext {
    record Owned(String voter,UUID storage,String record,String parent) {
        Owned { Objects.requireNonNull(voter);uuid(storage);digest(record);digest(parent); }
    }
    final String root;
    private final String rootRecordDigest;
    final Map<String,Object> cut, view, catalog;
    final Map<String,MembershipIdentity> identities;
    private final Map<String,byte[]> inventory;
    private final Set<String> images;

    MembershipContext(MembershipFormat.Decoded rootRecord,MembershipFormat.Decoded catalogRecord,
                      Map<String,Object> verifiedCut,Map<String,byte[]> inventory,Map<String,byte[]> images) {
        require(rootRecord.family().equals("records") && rootRecord.kind().equals("ROOT"),"context ROOT kind");
        require(catalogRecord.family().equals("records") && catalogRecord.kind().equals("CATALOG"),"context CATALOG kind");
        root=rootRecord.rootDigest();rootRecordDigest=rootRecord.digest();catalog=catalogRecord.value();cut=object(catalog.get("cut"));view=object(cut.get("view"));
        require(rootRecord.value().get("limits").equals(hash(canonical(MembershipFormat.CATALOG.get("resources"),16384))),"root resource contract");
        require(catalog.get("root").equals(root) && cut.equals(verifiedCut),"catalog applied cut/root");
        checkView(view);position(number(cut.get("index")));
        long sequence=number(catalog.get("applicationSequence")),dataIndex=number(catalog.get("lastDataIndex"));
        position(sequence);require(sequence>=number(rootRecord.value().get("baseSequence")) && dataIndex<=number(cut.get("index")),"catalog progress");
        var registry=new TreeMap<String,MembershipIdentity>();
        var ordered=new ArrayList<MembershipIdentity>();
        for(var row:list(catalog.get("identities"))) {
            var id=identity(object(row));ordered.add(id);registry.put(id.nodeId().value(),id);
        }
        MembershipValidation.identities(ordered,3,512);identities=Collections.unmodifiableMap(registry);
        var initial=new ArrayList<MembershipIdentity>();
        for(var row:list(rootRecord.value().get("initial"))) {
            var id=identity(object(row));initial.add(id);require(id.equals(identities.get(id.nodeId().value())),"missing/recycled initial identity");
        }
        MembershipValidation.identities(initial,3,5);
        for(String voter:voters())require(identities.containsKey(voter),"unreserved voter");
        validateCatalog();
        Objects.requireNonNull(inventory,"inventory");require(inventory.size()<=65536,"object inventory count");
        long total=0;var copy=new HashMap<String,byte[]>();
        for(var row:inventory.entrySet()) {
            digest(row.getKey());Objects.requireNonNull(row.getValue(),"object bytes");
            require(row.getValue().length<=32*MembershipResources.MIB-total,"complete inventory capacity");
            total+=row.getValue().length;
            require(hash(row.getValue()).equals(row.getKey()),"object inventory hash");
        }
        // Images are independent materializations, not capsule metadata. Retain their verified
        // identities, not another in-memory copy; the caller owns staging and its shared budget.
        Objects.requireNonNull(images,"images");require(images.size()<=MembershipResources.Unit.APPLICATION.count,"application inventory count");
        for(var row:images.entrySet()) {
            digest(row.getKey());Objects.requireNonNull(row.getValue(),"application bytes");
            require(row.getValue().length>0 && row.getValue().length<=MembershipResources.Unit.APPLICATION.bytes,"application image capacity");
        }
        for(var row:images.entrySet())require(hash(row.getValue()).equals(row.getKey()),"application image hash");
        this.images=Set.copyOf(images.keySet());
        for(var row:inventory.entrySet())copy.put(row.getKey(),row.getValue().clone());
        this.inventory=Collections.unmodifiableMap(copy);
        byte[] genesisBytes=this.inventory.get((String)rootRecord.value().get("genesis"));require(genesisBytes!=null,"missing original genesis");
        var genesis=decode(genesisBytes,"records","GENESIS").value();
        for(String key:List.of("groupId","historyId","baseSequence","schema","indexes"))
            require(genesis.get(key).equals(rootRecord.value().get(key)),"root/genesis "+key);
        require(genesis.get("source").equals("EMPTY")== (genesis.get("sourceDigest")==null),"genesis source binding");
        require(this.images.contains((String)catalog.get("application")),"missing separate application image");
        if(number(cut.get("index"))==0)require(nodes(view,"old").equals(initial.stream().map(i->i.nodeId().value()).toList())
                && view.get("old").equals(view.get("new")) && number(view.get("generation"))==0
                && number(catalog.get("nextOperation"))==1 && catalog.get("active")==null && sequence==number(genesis.get("baseSequence"))
                && catalog.get("application").equals(genesis.get("application")) && cut.get("entry").equals(rootRecord.value().get("genesis")),"initial catalog provenance");
    }
    static MembershipIdentity identity(Map<String,Object> value) {
        return new MembershipIdentity(new ReplicationNodeId((String)value.get("node")),UUID.fromString((String)value.get("storage")),
                new ReplicationEndpoint((String)value.get("host"),Math.toIntExact(number(value.get("port")))));
    }
    static void checkView(Map<String,Object> view) {
        checkType(view,"view");require(number(view.get("generation"))<=256,"membership generation bound");
        orderedNodes(list(view.get("old")));orderedNodes(list(view.get("new")));
        var old=new TreeSet<>(nodes(view,"old"));var next=new TreeSet<>(nodes(view,"new"));
        var union=new TreeSet<>(old);union.addAll(next);require(union.size()<=6,"membership union bound");
        require(old.equals(next)==(view.get("operation")==null),"stable/joint binding");
        if(!old.equals(next)) {
            var added=new TreeSet<>(next);added.removeAll(old);var removed=new TreeSet<>(old);removed.removeAll(next);
            require(added.size()<=1 && removed.size()<=1,"multi-member transition");
        }
    }
    static List<String> nodes(Map<String,Object> view,String name) { return list(view.get(name)).stream().map(String.class::cast).toList(); }
    static void orderedNodes(List<?> values) {
        String previous=null;
        for(Object item:values) {
            require(item instanceof String,"node value");String node=(String)item;
            require(previous==null || previous.compareTo(node)<0,"duplicate/unordered voters");previous=node;
        }
    }
    Set<String> voters() { var result=new TreeSet<>(nodes(view,"old"));result.addAll(nodes(view,"new"));return result; }
    static String viewDigest(String root,Map<String,Object> view) {
        var value=new TreeMap<>(view);value.put("root",root);return hash(canonical(value,16384));
    }
    static String cutDigest(Map<String,Object> cut) { return hash(canonical(cut,16384)); }
    String authority() { return viewDigest(root,view); }
    void quorum(Collection<String> voters) {quorum(view,voters);}
    static void quorum(Map<String,Object> view,Collection<String> voters) {
        var eligible=new HashSet<>(nodes(view,"old"));eligible.addAll(nodes(view,"new"));
        var unique=new HashSet<>(voters);require(unique.size()==voters.size() && eligible.containsAll(unique),"duplicate/foreign quorum voter");
        for(String side:List.of("old","new")) {
            var members=nodes(view,side);
            require(unique.stream().filter(members::contains).count()>members.size()/2,"both governing majorities required");
        }
    }
    private void validateCatalog() {
        long next=number(catalog.get("nextOperation")),retired=number(catalog.get("retiredThrough"));
        require(next>0 && retired<next,"catalog allocator ordering");
        var rows=list(catalog.get("results"));require(next-retired-1==rows.size(),"missing retained operation detail");
        Long active=catalog.get("active")==null?null:number(catalog.get("active"));long number=retired;int activeCount=0;
        require(active==null || number(view.get("generation"))<256,"active change beyond lifetime bound");
        for(Object item:rows) {
            var operation=object(item);var request=object(operation.get("request"));
            require(number(request.get("number"))==++number && number<=MAX && request.get("root").equals(root),"operation history/number");
            var targets=new ArrayList<MembershipIdentity>();
            for(var target:list(request.get("target"))) {
                var id=identity(object(target));targets.add(id);
                require(id.equals(identities.get(id.nodeId().value())),"operation target not permanently reserved");
            }
            MembershipValidation.identities(targets,3,5);
            String phase=(String)operation.get("phase");boolean terminal=phase.equals("COMPLETED") || phase.equals("CANCELLED");
            long revision=number(operation.get("revision"));Object prepared=operation.get("prepared"),receipt=operation.get("receipt"),binding=operation.get("binding");
            require(revision<=64 && (revision==0)==(prepared==null),"operation preparation revision");
            require((operation.get("terminalIndex")!=null)==terminal,"operation terminal evidence");
            if(terminal)require(number(operation.get("terminalIndex"))<=number(cut.get("index")),"terminal beyond applied cut");
            else { activeCount++;require(active!=null && active==number,"active catalog operation"); }
            boolean sealed=Set.of("SEALED","JOINT","COMPLETED").contains(phase);
            require((binding!=null)==sealed,"sealed operation binding");
            require(!phase.equals("RESERVED") || revision==0,"reserved operation prepared");
            require(!Set.of("PREPARING","READY","SEALED","JOINT","COMPLETED").contains(phase) || revision>0,"missing prepared cut");
            if(prepared!=null) {
                var p=object(prepared);var preparedCut=object(p.get("cut"));checkView(object(preparedCut.get("view")));
                require(number(p.get("revision"))==revision && number(preparedCut.get("index"))<=number(cut.get("index")),"prepared cut/revision");
                if(terminal)require(number(preparedCut.get("index"))<=number(operation.get("terminalIndex")),"terminal before prepared cut");
            }
            if(receipt!=null) {
                var r=object(receipt);
                require(prepared!=null && r.get("root").equals(root) && number(r.get("number"))==number
                        && r.get("prepared").equals(prepared) && r.get("request").equals(hash(canonical(request,8192)))
                        && targets.contains(identity(object(r.get("identity")))),"learner receipt context");
            }
            require(!phase.equals("RESERVED") && !phase.equals("PREPARING") || receipt==null,"premature learner receipt");
            if(sealed) {
                var descriptor=new TreeMap<String,Object>();descriptor.put("request",request);descriptor.put("prepared",prepared);descriptor.put("receipt",receipt);
                require(binding.equals(hash(canonical(descriptor,8192))),"sealed descriptor hash");
            }
            if(!terminal) {
                var stable=new TreeMap<>(view);stable.put("new",view.get("old"));stable.put("operation",null);
                require(request.get("expected").equals(viewDigest(root,stable)),"active request expected configuration");
                var old=new HashSet<>(nodes(view,"old"));var targetNodes=new HashSet<String>();targets.forEach(i->targetNodes.add(i.nodeId().value()));
                var added=new HashSet<>(targetNodes);added.removeAll(old);var removed=new HashSet<>(old);removed.removeAll(targetNodes);
                String kind=(String)request.get("kind");
                require(switch(kind) { case "ADD" -> added.size()==1 && removed.isEmpty(); case "REMOVE" -> added.isEmpty() && removed.size()==1;
                    case "REPLACE" -> added.size()==1 && removed.size()==1; default -> false; },"operation change shape");
                if(Set.of("READY","SEALED","JOINT").contains(phase)) {
                    require(added.isEmpty() ? receipt==null : receipt!=null,"learner readiness missing/unneeded");
                    if(receipt!=null)require(added.contains(object(object(receipt).get("identity")).get("node")),"readiness from retained voter");
                }
                if(phase.equals("JOINT"))require(Objects.equals(binding,view.get("operation")) && new HashSet<>(nodes(view,"new")).equals(targetNodes),"joint operation view");
                else require(view.get("operation")==null,"joint view before INTENT");
            }
        }
        require(activeCount==(active==null?0:1) && (view.get("operation")==null || activeCount==1),"active operation cardinality");
    }
    void monotonicFrom(MembershipContext prior) {
        require(number(cut.get("index"))!=number(prior.cut.get("index")) || catalog.equals(prior.catalog),"catalog rewrite at same cut");
        require(root.equals(prior.root) && number(cut.get("index"))>=number(prior.cut.get("index"))
                && number(view.get("generation"))>=number(prior.view.get("generation"))
                && number(catalog.get("applicationSequence"))>=number(prior.catalog.get("applicationSequence"))
                && number(catalog.get("nextOperation"))>=number(prior.catalog.get("nextOperation"))
                && number(catalog.get("retiredThrough"))>=number(prior.catalog.get("retiredThrough")),"catalog regression");
        for(var priorIdentity:prior.identities.entrySet()) require(priorIdentity.getValue().equals(identities.get(priorIdentity.getKey())),"forgotten/recycled permanent identity");
    }
    MembershipFormat.Decoded record(String digest,String kind) {
        byte[] bytes=inventory.get(digest);require(bytes!=null,"missing content-addressed object");
        var record=decode(bytes,"records",kind);require(root.equals(record.value().get("root")),"foreign record root");return record;
    }
    Map<String,Object> ballot(Object value,boolean currentVoter) {return ballot(value,view,currentVoter);}
    private Map<String,Object> ballot(Object value,Map<String,Object> view,boolean currentVoter) {
        var ballot=object(value);checkType(ballot,"ballot");position(number(ballot.get("counter")));
        String proposer=(String)ballot.get("proposer");var id=identities.get(proposer);
        require(id!=null && id.storageId().toString().equals(ballot.get("incarnation")),"ballot durable identity");
        require(!currentVoter || nodes(view,"old").contains(proposer) || nodes(view,"new").contains(proposer),"ballot proposer outside view");return ballot;
    }
    static int compareBallot(Map<String,Object> a,Map<String,Object> b) {
        int result=Long.compare(number(a.get("counter")),number(b.get("counter")));
        if(result==0)result=((String)a.get("proposer")).compareTo((String)b.get("proposer"));
        if(result==0)result=((String)a.get("incarnation")).compareTo((String)b.get("incarnation"));return result;
    }
    void certificate(MembershipFormat.Decoded certificate,Set<Owned> owned) {
        var entry=certificateAt(certificate,owned,cut).value();
        control((String)entry.get("kind"),command((String)entry.get("kind"),inventory.get((String)entry.get("payload"))));
    }
    /** Historical proof verification; the caller must separately establish this parent cut. */
    Decoded certificateAt(Decoded certificate,Set<Owned> owned,Map<String,Object> parent) {
        checkType(parent,"cut");var governing=object(parent.get("view"));checkView(governing);
        String authority=viewDigest(root,governing);
        require(certificate.family().equals("records") && certificate.kind().equals("CERTIFICATE"),"certificate kind");
        var cert=certificate.value();require(root.equals(cert.get("root")) && authority.equals(cert.get("authority")),"certificate context");
        require(number(parent.get("index"))<MAX && number(cert.get("index"))==number(parent.get("index"))+1,"certificate parent index");
        var current=ballot(cert.get("ballot"),governing,true);var entry=record((String)cert.get("entry"),"ENTRY");var value=entry.value();
        require(value.get("authority").equals(authority) && value.get("index").equals(cert.get("index"))
                && value.get("previous").equals(parent.get("entry")),"entry governing parent");
        require(compareBallot(ballot(value.get("origin"),governing,true),current)<=0,"entry origin beyond proof ballot");
        byte[] payload=inventory.get((String)value.get("payload"));require(payload!=null,"missing original entry payload");
        command((String)value.get("kind"),payload);
        var accept=new TreeMap<>(cert);accept.remove("accepts");accept.remove("proofs");
        byte[] acceptance=encode("records","ACCEPT",accept);var proof=new TreeMap<>(accept);proof.put("accepts",cert.get("accepts"));
        byte[] proofBytes=encode("records","PROOF",proof);
        require(Arrays.equals(inventory.get(hash(acceptance)),acceptance) && Arrays.equals(inventory.get(hash(proofBytes)),proofBytes),"missing exact phased record");
        witnesses(list(cert.get("accepts")),"ACCEPT",hash(acceptance),owned,parent);
        witnesses(list(cert.get("proofs")),"PROOF",hash(proofBytes),owned,parent);
        return entry;
    }
    private Map<String,Object> activeOperation() {
        if(catalog.get("active")==null)return null;
        for(Object item:list(catalog.get("results"))) {
            var row=object(item);
            if(number(object(row.get("request")).get("number"))==number(catalog.get("active")))return row;
        }
        throw new IllegalArgumentException("missing active detail");
    }
    void control(String kind,Object payload) {
        var active=activeOperation();String phase=active==null?null:(String)active.get("phase");
        require(view.get("operation")==null || kind.equals("FINAL"),"joint era only admits FINAL");
        if(kind.equals("DATA")) { require(!"SEALED".equals(phase),"DATA after SEAL");return; }
        if(kind.equals("BARRIER"))return;
        var value=object(payload);
        if(kind.equals("RESERVE")) {
            require(active==null && number(view.get("generation"))<256 && list(catalog.get("results")).size()<64,"reservation capacity/busy");
            var request=object(value.get("request"));
            require(root.equals(request.get("root")) && number(request.get("number"))==number(catalog.get("nextOperation"))
                    && number(request.get("number"))<=MAX && request.get("expected").equals(authority()),"reservation history/allocator/configuration");
            var targets=new ArrayList<MembershipIdentity>();for(Object row:list(request.get("target")))targets.add(identity(object(row)));
            MembershipValidation.identities(targets,3,5);var old=new HashSet<>(nodes(view,"old"));int added=0;
            for(var id:targets) {
                if(old.remove(id.nodeId().value()))require(id.equals(identities.get(id.nodeId().value())),"recycled retained identity");
                else { added++;for(var used:identities.values())require(!id.nodeId().equals(used.nodeId()) && !id.storageId().equals(used.storageId())
                        && !id.endpoint().equals(used.endpoint()),"permanent identity reuse"); }
            }
            require(identities.size()+added<=512,"identity reservation capacity");
            int removed=old.size();String change=(String)request.get("kind");
            require(switch(change) { case "ADD" -> added==1 && removed==0;case "REMOVE" -> added==0 && removed==1;
                case "REPLACE" -> added==1 && removed==1;default -> false; },"reservation change shape");return;
        }
        if(kind.equals("RETIRE")) {
            long through=number(value.get("through"));require(through>number(catalog.get("retiredThrough")) && through<number(catalog.get("nextOperation")),"retirement range");
            for(Object row:list(catalog.get("results")))if(number(object(object(row).get("request")).get("number"))<=through)
                require(Set.of("COMPLETED","CANCELLED").contains(object(row).get("phase")),"retirement before terminal result");return;
        }
        require(active!=null,"control without active operation");
        if(value.containsKey("number"))require(number(value.get("number"))==number(catalog.get("active")),"control operation number");
        switch(kind) {
            case "PREPARE" -> require(Set.of("RESERVED","PREPARING","READY").contains(phase)
                    && number(value.get("revision"))==number(active.get("revision"))+1 && number(value.get("revision"))<=64,"preparation phase/revision");
            case "READY" -> {
                require(phase.equals("PREPARING"),"ready phase");Object receipt=value.get("receipt");
                var target=list(object(active.get("request")).get("target"));
                var joining=target.stream().map(MembershipFormat::object).map(MembershipContext::identity).filter(id->!voters().contains(id.nodeId().value())).toList();
                require(joining.isEmpty()?receipt==null:receipt!=null,"ready learner receipt presence");
                if(receipt!=null) {
                    var r=object(receipt);require(joining.size()==1 && joining.contains(identity(object(r.get("identity"))))
                            && root.equals(r.get("root")) && number(r.get("number"))==number(catalog.get("active"))
                            && r.get("prepared").equals(active.get("prepared"))
                            && r.get("request").equals(hash(canonical(active.get("request"),8192))),"ready exact prepared identity");
                    require(images.contains((String)r.get("image")),"missing learner materialization bytes");
                }
            }
            case "SEAL" -> require(phase.equals("READY") && object(active.get("prepared")).get("application").equals(catalog.get("application"))
                    && number(object(object(active.get("prepared")).get("cut")).get("index"))>=number(catalog.get("lastDataIndex")),"stale/unready seal");
            case "CANCEL" -> require(Set.of("RESERVED","PREPARING","READY").contains(phase),"irreversible cancellation");
            case "INTENT" -> {
                var descriptor=new TreeMap<String,Object>();for(String key:List.of("request","prepared","receipt"))descriptor.put(key,active.get(key));
                require(phase.equals("SEALED") && descriptor.equals(value.get("sealed")) && hash(canonical(descriptor,8192)).equals(active.get("binding")),"INTENT original sealed descriptor");
            }
            case "FINAL" -> require(phase.equals("JOINT") && value.get("binding").equals(view.get("operation")),"FINAL original joint binding");
            default -> throw new IllegalArgumentException("unexpected control");
        }
    }
    /** First PROOF admission requires real exact ACCEPT observations, not receipt hashes alone. */
    void proof(Decoded proof,Decoded accept,Set<Owned> owned) {
        Objects.requireNonNull(owned,"owned ACCEPT observations");require(owned.size()<=6,"ACCEPT observation count");owned=Set.copyOf(owned);persistedProof(proof,accept);
        witnesses(list(proof.value().get("accepts")),"ACCEPT",accept.digest(),owned,cut);
    }
    /** Reopen of this exclusive owner's original forced PROOF. This validates the retained
     * attestation's structure; it is not a fresh observation of remote durable ownership. */
    void persistedProof(Decoded proof,Decoded accept) {
        require(proof.family().equals("records") && proof.kind().equals("PROOF")
                && accept.family().equals("records") && accept.kind().equals("ACCEPT"),"pending PROOF/ACCEPT kind");
        var value=new TreeMap<>(proof.value());var receipts=list(value.remove("accepts"));
        require(value.equals(accept.value()) && root.equals(value.get("root")) && authority().equals(value.get("authority"))
                && number(cut.get("index"))<MAX && number(value.get("index"))==number(cut.get("index"))+1,"pending PROOF exact ACCEPT/parent");
        ballot(value.get("ballot"),true);witnessShape(receipts,"ACCEPT",accept.digest(),cut);
    }
    /** Authentic original local certificate attestation, never fresh remote observations. */
    void persistedCertificate(Decoded certificate,Decoded proof,Decoded accept) {
        require(proof!=null,"certificate requires original PROOF");persistedProof(proof,accept);
        require(certificate.family().equals("records") && certificate.kind().equals("CERTIFICATE"),"pending certificate kind");
        var value=new TreeMap<>(certificate.value());var receipts=list(value.remove("proofs"));
        require(value.equals(proof.value()),"pending certificate differs from original PROOF");
        witnessShape(receipts,"PROOF",proof.digest(),cut);
    }
    private void witnesses(List<?> witnesses,String phase,String record,Set<Owned> owned,Map<String,Object> parent) {
        Objects.requireNonNull(owned,"owned phased observations");
        witnessShape(witnesses,phase,record,parent);
        for(Object value:witnesses) {
            String voter=(String)object(value).get("voter");var id=identities.get(voter);
            require(owned.contains(new Owned(voter,id.storageId(),record,cutDigest(parent))),"missing owned phased record/applied parent");
        }
    }
    private void witnessShape(List<?> witnesses,String phase,String record,Map<String,Object> parent) {
        var nodes=new ArrayList<String>();
        for(Object value:witnesses) {
            var witness=object(value);String voter=(String)witness.get("voter");var id=identities.get(voter);
            require(id!=null && id.storageId().toString().equals(witness.get("incarnation")),"witness disk identity");nodes.add(voter);
            var receipt=Map.of("root",root,"voter",voter,"incarnation",witness.get("incarnation"),"phase",phase,"record",record);
            require(witness.get("receipt").equals(hash(canonical(receipt,2048))),"witness phased record binding");
        }
        orderedNodes(nodes);quorum(object(parent.get("view")),nodes);
    }
    void wire(MembershipFormat.Decoded frame,MembershipIdentity authenticatedSender,MembershipIdentity recipient,
              Map<String,Object> expectedBallot,UUID trace,long sequence) {
        require(frame.family().equals("wire"),"wire family");var value=frame.value();
        require(identity(object(value.get("sender"))).equals(authenticatedSender) && identity(object(value.get("recipient"))).equals(recipient),"authenticated wire identities");
        require(root.equals(value.get("root")) && authority().equals(value.get("view")) && value.get("ballot").equals(expectedBallot)
                && value.get("trace").equals(trace.toString()) && number(value.get("sequence"))==sequence,"wire root/view/ballot/correlation");
        ballot(expectedBallot,true);
        require(authenticatedSender.equals(identities.get(authenticatedSender.nodeId().value())) && recipient.equals(identities.get(recipient.nodeId().value())),"unreserved wire identity");
        String name=frame.kind();var payload=object(value.get("payload"));
        for(var participant:List.of(authenticatedSender,recipient))if(!voters().contains(participant.nodeId().value())) {
            var operation=activeOperation();
            require(operation!=null && list(object(operation.get("request")).get("target")).stream().map(MembershipFormat::object)
                    .map(MembershipContext::identity).anyMatch(participant::equals),"endpoint outside learner reservation");
            require(Set.of("HELLO","SOURCE_OFFER","CHUNK","TRANSFER_COMMIT","LEARNER_READY").contains(name),"learner cannot vote/read");
            require(name.equals("HELLO") || operation.get("prepared")!=null,"learner transfer before preparation");
        }
        if(name.equals("HELLO"))require(rootRecordDigest.equals(payload.get("rootRecord"))
                && payload.get("mode").equals(voters().contains(authenticatedSender.nodeId().value())?"VOTER":"LEARNER"),"HELLO root/role");
        if(name.equals("SOURCE_OFFER")) {
            long maximum=switch((String)payload.get("kind")) {case "RECORD" -> MembershipFormat.FRAME;case "CAPSULE" -> 32*MembershipResources.MIB;
                case "APPLICATION" -> 64*MembershipResources.MIB;default -> throw new IllegalArgumentException("unknown transfer kind");};
            require(number(payload.get("bytes"))<=maximum,"source offer capacity");
        }
        if(name.equals("LEARNER_READY")) {
            var active=activeOperation();require(active!=null && active.get("prepared")!=null,"ready without preparation");
            var receipt=object(record((String)payload.get("receipt"),"LEARNER").value().get("receipt"));
            require(identity(object(receipt.get("identity"))).equals(authenticatedSender),"ready authenticated learner");
            control("READY",Map.of("number",catalog.get("active"),"receipt",receipt));
        }
        if(name.equals("CHUNK")) {
            byte[] bytes=Base64.getDecoder().decode((String)payload.get("bytes"));boolean data=payload.get("action").equals("DATA");
            require(data ? bytes.length>0 && hash(bytes).equals(payload.get("digest")) : bytes.length==0,"CHUNK action/hash");
        }
    }
}
