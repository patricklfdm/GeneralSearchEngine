package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.*;

/** Complete capsule walk under authenticated owned-record observations, never a file-deletion permit. */
final class MembershipCapsule {
    final MembershipContext context;
    final MembershipSourcePacket packet;
    record Anchor(Map<String,Object> cut,String catalog,String application) {}
    private final Map<Long,Map<String,Object>> anchors;
    private final Map<Long,Anchor> states;
    private final Set<Owned> observations;
    private final Decoded highestMembershipCertificate;
    private MembershipCapsule(MembershipContext context,MembershipSourcePacket packet,Map<Long,Map<String,Object>> anchors,Map<Long,Anchor> states,Set<Owned> observations,Decoded highestMembershipCertificate) {
        this.context=context;this.packet=packet;this.anchors=Map.copyOf(anchors);this.states=Map.copyOf(states);this.observations=Set.copyOf(observations);
        this.highestMembershipCertificate=highestMembershipCertificate;
    }
    boolean containsCut(Map<String,Object> cut) {return cut.equals(anchors.get(number(cut.get("index"))));}
    Map<Long,Map<String,Object>> anchors() {return anchors;}
    Anchor anchor(long index) {return states.get(index);}
    Anchor terminal() {return states.get(number(context.cut.get("index")));}
    /** Only certificates actually authenticated while walking membership edges, never inventory extras. */
    Optional<Decoded> membershipCertificateFence(){return Optional.ofNullable(highestMembershipCertificate);}

    static MembershipCapsule verify(Decoded root,MembershipSourcePacket packet,Map<String,byte[]> images,Set<Owned> owned) {
        require(root.family().equals("records") && root.kind().equals("ROOT"),"capsule ROOT kind");packet.verifyImages(images);
        require(Arrays.equals(root.bytes(),packet.objectBytes(root.digest())),"capsule original ROOT bytes");
        var capsule=packet.capsule().value();var currentCut=object(capsule.get("cut"));
        var inventory=new HashMap<String,byte[]>();for(String key:packet.objectNames())inventory.put(key,packet.objectBytes(key));
        var terminal=decode(packet.objectBytes((String)capsule.get("catalog")),"records","CATALOG");
        var context=new MembershipContext(root,terminal,currentCut,inventory,images);
        require(capsule.get("root").equals(context.root) && capsule.get("initial").equals(root.value().get("genesis")),"capsule root/genesis identity");
        var genesis=decode(packet.objectBytes((String)capsule.get("initial")),"records","GENESIS").value();
        var initialCatalog=initialCatalog(root,genesis);String catalog=hash(encode("records","CATALOG",initialCatalog));
        String application=(String)genesis.get("application");Map<String,Object> at=object(initialCatalog.get("cut"));
        var anchors=new TreeMap<Long,Map<String,Object>>();anchors.put(0L,at);
        var states=new TreeMap<Long,Anchor>();states.put(0L,new Anchor(at,catalog,application));
        int changes=0;long operation=0;boolean priorRange=false;Decoded highestMembershipCertificate=null;
        for(Object itemValue:list(capsule.get("items"))) {
            var item=object(itemValue);var statement=context.record((String)item.get("statement"),"CHECKPOINT");var s=statement.value();
            var end=object(s.get("end"));var beforeView=object(at.get("view"));var afterView=object(end.get("view"));
            checkView(afterView);position(number(end.get("index")));
            require(s.get("start").equals(at) && s.get("catalogBefore").equals(catalog) && s.get("applicationBefore").equals(application)
                    && number(end.get("index"))>number(at.get("index")) && item.get("kind").equals(s.get("scope")),"capsule checkpoint continuity");
            var bytes=new HashSet<String>();bytes.add(statement.digest());
            if(item.get("kind").equals("RANGE")) {
                require(!priorRange && item.get("certificate")==null && item.get("descriptor")==null
                        && beforeView.get("operation")==null && afterView.equals(beforeView),"range hides boundary or splits stable era");
                priorRange=true;
            } else {
                require(item.get("kind").equals("MEMBERSHIP") && item.get("certificate")!=null && item.get("descriptor")!=null
                        && number(at.get("index"))<MAX && number(end.get("index"))==number(at.get("index"))+1,"membership edge shape");
                priorRange=false;
                var cert=context.record((String)item.get("certificate"),"CERTIFICATE");
                var entry=context.certificateAt(cert,owned,at);var entryValue=entry.value();
                if(highestMembershipCertificate==null || compareBallot(object(cert.value().get("ballot")),object(highestMembershipCertificate.value().get("ballot")))>=0)
                    highestMembershipCertificate=cert;
                String kind=(String)entryValue.get("kind");String descriptorHash=(String)item.get("descriptor");
                var descriptor=object(parse(packet.objectBytes(descriptorHash),8192));checkType(descriptor,"sealed");
                var expected=successor(context,at,descriptor,descriptorHash,application,kind);
                require(afterView.equals(expected) && end.get("entry").equals(entry.digest())
                        && s.get("applicationAfter").equals(application),"membership successor/application");
                Object payload=command(kind,packet.objectBytes((String)entryValue.get("payload")));
                require(kind.equals("INTENT") ? object(payload).get("sealed").equals(descriptor) : object(payload).get("binding").equals(descriptorHash),"original membership descriptor payload");
                long number=number(object(descriptor.get("request")).get("number"));
                if(kind.equals("INTENT")) {require(++changes<=256 && number>operation,"membership lifetime/order");operation=number;}
                else require(number==operation,"FINAL changed operation number");
                require(number<number(context.catalog.get("nextOperation")),"catalog forgot historical operation allocator");
                bytes.add(cert.digest());bytes.add(entry.digest());bytes.add((String)entryValue.get("payload"));bytes.add(descriptorHash);
                var accept=new TreeMap<>(cert.value());accept.remove("accepts");accept.remove("proofs");bytes.add(hash(encode("records","ACCEPT",accept)));
                accept.put("accepts",cert.value().get("accepts"));bytes.add(hash(encode("records","PROOF",accept)));
            }
            checkpoint(context,packet,statement,list(item.get("endorsements")),owned,bytes);
            long size=0;for(String hash:bytes)size+=packet.objectBytes(hash).length;
            require(size<=(item.get("kind").equals("RANGE")?16:48)*1024,"complete capsule item byte capacity");
            at=end;catalog=(String)s.get("catalogAfter");application=(String)s.get("applicationAfter");anchors.put(number(at.get("index")),at);states.put(number(at.get("index")),new Anchor(at,catalog,application));
        }
        require(list(capsule.get("items")).size()<=3*changes+1,"capsule logical item bound");
        require(at.equals(currentCut) && catalog.equals(capsule.get("catalog")) && application.equals(capsule.get("application")),"capsule terminal state");
        return new MembershipCapsule(context,packet,anchors,states,owned,highestMembershipCertificate);
    }
    void verifyAncestry(byte[] bytes,Collection<Anchor> required) {
        require(bytes.length<=96*1024,"generation ancestry capacity");var bridges=new ArrayList<MembershipSelection.Bridge>();
        Decoded statement=null;var acks=new ArrayList<Decoded>();int offset=0;
        while(offset<bytes.length) {
            require(bytes.length-offset>=HEADER,"torn generation ancestry");var header=Arrays.copyOfRange(bytes,offset,offset+HEADER);
            int kind=java.nio.ByteBuffer.wrap(header).getShort(8);require(kind==12 || kind==13,"generation ancestry record kind");
            String name=kind==12?"CHECKPOINT":"CHECKPOINT_ACK";int length=HEADER+header(header,"records",name);
            require(length<=bytes.length-offset,"torn generation ancestry");var frame=decode(Arrays.copyOfRange(bytes,offset,offset+length),"records",name);offset+=length;
            if(kind==12) {
                if(statement!=null)bridges.add(ancestryBridge(statement,acks));
                statement=frame;acks=new ArrayList<>();require(bridges.size()<6,"generation ancestry count");
            }else {require(statement!=null && acks.size()<6,"orphan/excess ancestry ACK");acks.add(frame);}
        }
        if(statement!=null)bridges.add(ancestryBridge(statement,acks));
        var lower=new HashMap<Map<String,Object>,Anchor>();
        for(var bridge:bridges) {
            var value=bridge.statement.value();var anchor=new Anchor(object(value.get("start")),(String)value.get("catalogBefore"),(String)value.get("applicationBefore"));
            require(lower.putIfAbsent(anchor.cut(),anchor)==null,"duplicate generation ancestry");bridge.verify(this,anchor);
        }
        for(var anchor:required) {
            var direct=anchor(number(anchor.cut().get("index")));
            require(direct==null?anchor.equals(lower.get(anchor.cut())):anchor.equals(direct),"generation did not preserve original proven parent");
        }
    }
    private MembershipSelection.Bridge ancestryBridge(Decoded statement,List<Decoded> acknowledgements) {
        var digests=new HashSet<String>();acknowledgements.forEach(ack->digests.add(ack.digest()));
        var owned=new HashSet<Owned>();for(var observation:observations)if(digests.contains(observation.record()))owned.add(observation);
        return new MembershipSelection.Bridge(statement,acknowledgements,owned);
    }
    static Map<String,Object> initialCatalog(Decoded root,Map<String,Object> genesis) {
        var names=list(root.value().get("initial")).stream().map(MembershipFormat::object).map(v->(String)v.get("node")).toList();
        var view=new TreeMap<String,Object>();view.put("generation",0L);view.put("old",names);view.put("new",names);view.put("operation",null);
        var catalog=new TreeMap<String,Object>();catalog.put("root",root.rootDigest());catalog.put("active",null);
        catalog.put("application",genesis.get("application"));catalog.put("applicationSequence",genesis.get("baseSequence"));
        catalog.put("cut",Map.of("index",0L,"entry",root.value().get("genesis"),"view",view));catalog.put("identities",root.value().get("initial"));
        catalog.put("lastDataIndex",0L);catalog.put("nextOperation",1L);catalog.put("results",List.of());catalog.put("retiredThrough",0L);
        // Reuse the codec's immutable representation; no caller can rewrite an ancestry anchor.
        return decode(encode("records","CATALOG",catalog),"records","CATALOG").value();
    }
    private static Map<String,Object> successor(MembershipContext context,Map<String,Object> at,Map<String,Object> descriptor,
                                                 String binding,String application,String kind) {
        require(kind.equals("INTENT") || kind.equals("FINAL"),"nonmembership entry in edge");
        var view=object(at.get("view"));var stable=new TreeMap<>(view);stable.put("new",view.get("old"));stable.put("operation",null);
        var request=object(descriptor.get("request"));var prepared=object(descriptor.get("prepared"));Object receipt=descriptor.get("receipt");
        require(request.get("root").equals(context.root) && request.get("expected").equals(viewDigest(context.root,stable))
                && number(request.get("number"))<=MAX && number(prepared.get("revision"))<=64
                && object(prepared.get("cut")).get("view").equals(stable) && number(object(prepared.get("cut")).get("index"))<=number(at.get("index"))
                && prepared.get("application").equals(application),"membership descriptor preparation");
        var target=new ArrayList<MembershipIdentity>();for(Object value:list(request.get("target")))target.add(identity(object(value)));
        MembershipValidation.identities(target,3,5);
        for(var id:target)require(id.equals(context.identities.get(id.nodeId().value())),"descriptor permanent identity");
        var old=new HashSet<>(nodes(view,"old"));var next=target.stream().map(v->v.nodeId().value()).toList();
        var added=new HashSet<>(next);added.removeAll(old);var removed=new HashSet<>(old);removed.removeAll(next);
        require(switch((String)request.get("kind")){case "ADD"->added.size()==1 && removed.isEmpty();case "REMOVE"->added.isEmpty() && removed.size()==1;
            case "REPLACE"->added.size()==1 && removed.size()==1;default->false;},"descriptor one-member change");
        require(added.isEmpty()?receipt==null:receipt!=null,"descriptor learner receipt");
        if(receipt!=null) {
            var r=object(receipt);var id=identity(object(r.get("identity")));
            require(added.contains(id.nodeId().value()) && target.contains(id) && r.get("root").equals(context.root)
                    && r.get("number").equals(request.get("number")) && r.get("request").equals(hash(canonical(request,8192)))
                    && r.get("prepared").equals(prepared) && r.get("image").equals(application),"descriptor exact learner image");
        }
        var result=new TreeMap<>(view);
        if(kind.equals("INTENT")) {
            require(view.get("operation")==null && number(view.get("generation"))<256,"INTENT stable generation");
            result.put("new",next);result.put("operation",binding);
        } else {
            require(binding.equals(view.get("operation")) && next.equals(view.get("new")),"FINAL joint binding");
            result.put("old",next);result.put("new",next);result.put("operation",null);result.put("generation",number(view.get("generation"))+1);
        }
        return result;
    }
    private static void checkpoint(MembershipContext context,MembershipSourcePacket packet,Decoded statement,List<?> endorsements,
                                   Set<Owned> owned,Set<String> bytes) {
        var cut=object(statement.value().get("end"));var voters=new ArrayList<String>();
        for(Object hash:endorsements) {
            var ack=context.record((String)hash,"CHECKPOINT_ACK");var value=ack.value();String voter=(String)value.get("voter");
            var id=context.identities.get(voter);
            require(id!=null && id.storageId().toString().equals(value.get("incarnation")) && value.get("cut").equals(cut)
                    && value.get("statement").equals(statement.digest()),"checkpoint exact statement/end identity");
            require(owned.contains(new Owned(voter,id.storageId(),ack.digest(),cutDigest(cut))),"checkpoint before owned applied end");
            voters.add(voter);bytes.add(ack.digest());
        }
        orderedNodes(voters);quorum(object(cut.get("view")),voters);
    }
}
