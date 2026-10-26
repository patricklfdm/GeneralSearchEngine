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
    /** An exact already-verified historical statement, not a new voter observation. */
    private record Historical(String kind,String record,String binding) {}
    private final Set<Historical> history;
    private static Historical certificate(Decoded certificate,Map<String,Object> parent) {
        return new Historical("CERTIFICATE",certificate.digest(),cutDigest(parent));
    }
    private static Historical checkpoint(Decoded statement,List<?> endorsements) {
        return new Historical("CHECKPOINT",statement.digest(),hash(canonical(endorsements,8192)));
    }
    private final Decoded highestMembershipCertificate;
    private MembershipCapsule(MembershipContext context,MembershipSourcePacket packet,Map<Long,Map<String,Object>> anchors,Map<Long,Anchor> states,Set<Owned> observations,Set<Historical> history,Decoded highestMembershipCertificate) {
        this.context=context;this.packet=packet;this.anchors=Map.copyOf(anchors);this.states=Map.copyOf(states);this.observations=Set.copyOf(observations);
        this.highestMembershipCertificate=highestMembershipCertificate;this.history=Set.copyOf(history);
    }
    boolean containsCut(Map<String,Object> cut) {return cut.equals(anchors.get(number(cut.get("index"))));}
    Map<Long,Map<String,Object>> anchors() {return anchors;}
    Anchor anchor(long index) {return states.get(index);}
    Anchor terminal() {return states.get(number(context.cut.get("index")));}
    /** Reuse only this already authenticated prefix's observations; extension evidence stays explicit. */
    MembershipCapsule verifyExtension(MembershipSourcePacket packet,Map<String,byte[]> images,Set<Owned> additional) {
        // Do not accumulate observations for replaced ranges or unrelated future records.
        var owned=new HashSet<Owned>();for(var observation:observations)
            if(packet.objectNames().contains(observation.record()))owned.add(observation);
        for(var observation:additional)if(packet.objectNames().contains(observation.record()))owned.add(observation);
        var root=decode(this.packet.objectBytes(this.context.recordRootDigest()),"records","ROOT");
        return verify(root,packet,images,owned,history,false);
    }
    boolean sameProvenPrefix(MembershipSourcePacket candidate) {
        var a=new TreeMap<>(packet.capsule().value());var b=new TreeMap<>(candidate.capsule().value());
        a.remove("inventory");b.remove("inventory");return a.equals(b) && packet.images().equals(candidate.images());
    }
    /** Materialization may attach exact original tail records, not change the proven prefix.
     * Every supplemental bridge is verified before its historical key is retained. */
    MembershipCapsule materialization(MembershipSourcePacket candidate,Map<String,byte[]> images,List<MembershipSelection.Bridge> bridges) {
        require(sameProvenPrefix(candidate),"materialization changed proven prefix");
        byte[] ancestry=checkedAncestry(bridges);
        return verifyExtension(candidate,images,Set.of()).retainingCompleteAncestry(ancestry);
    }
    /** Preserve the exact independently authenticated bridges when a caller later
     * validates their serialized form. Bare statements never acquire authority. */
    MembershipCapsule retainingVerifiedAncestry(List<MembershipSelection.Bridge> bridges) {
        return retainingCompleteAncestry(checkedAncestry(bridges));
    }
    private byte[] checkedAncestry(List<MembershipSelection.Bridge> bridges) {
        byte[] bytes=MembershipGenerationPlan.ancestry(bridges);
        for(var bridge:bridges) {
            var v=bridge.statement.value();bridge.verify(this,new Anchor(object(v.get("start")),(String)v.get("catalogBefore"),(String)v.get("applicationBefore")));
        }
        return bytes;
    }
    /** Only certificates actually authenticated while walking membership edges, never inventory extras. */
    Optional<Decoded> membershipCertificateFence(){return Optional.ofNullable(highestMembershipCertificate);}
    /** A publication must retain the exact phases and independently owned observations, including for DATA. */
    Decoded publicationCertificate(Decoded certificate,Map<String,Object> parent) {
        return history.contains(certificate(certificate,parent))?context.certificateStructure(certificate,parent):
                context.certificateAt(certificate,observations,parent);
    }

    /** Retain one already authenticated original proof through a compacted range.
     * Does not create observations or import unrelated history. The source packet caps still apply. */
    MembershipCapsule retainingCertificate(MembershipCapsule original,Decoded certificate,Map<String,Object> parent,Map<String,byte[]> images) {
        require(context.root.equals(original.context.root),"retained proof changed root");
        var entry=original.publicationCertificate(certificate,parent);var names=new HashSet<String>();
        names.add(certificate.digest());names.add(entry.digest());names.add((String)entry.value().get("payload"));
        var accept=new TreeMap<>(certificate.value());accept.remove("accepts");accept.remove("proofs");names.add(hash(encode("records","ACCEPT",accept)));
        accept.put("accepts",certificate.value().get("accepts"));names.add(hash(encode("records","PROOF",accept)));
        var objects=new TreeMap<String,byte[]>();for(String h:packet.objectNames())objects.put(h,packet.objectBytes(h));
        for(String h:names)objects.put(h,original.packet.objectBytes(h));
        var value=new TreeMap<>(packet.capsule().value());value.put("inventory",hash(MembershipSourcePacket.index(objects,packet.images())));
        var retained=MembershipSourcePacket.decode(MembershipSourcePacket.encode(decode(encode("records","CAPSULE",value),"records","CAPSULE"),objects,packet.images()));
        var owned=new HashSet<Owned>();for(var observation:original.observations)if(names.contains(observation.record()))owned.add(observation);
        var retainedHistory=new HashSet<>(history);retainedHistory.add(certificate(certificate,parent));
        for(var observation:observations)if(retained.objectNames().contains(observation.record()))owned.add(observation);
        var root=decode(packet.objectBytes(context.recordRootDigest()),"records","ROOT");
        var result=verify(root,retained,images,owned,retainedHistory,false);result.publicationCertificate(certificate,parent);return result;
    }

    static MembershipCapsule verify(Decoded root,MembershipSourcePacket packet,Map<String,byte[]> images,Set<Owned> owned) {
        return verify(root,packet,images,owned,Set.of(),false);
    }
    /** The only whole-copy admission is a complete authenticated owner's source exchange.
     * A bare packet, witness tuple, content hash or generic record cannot mint this token. */
    static MembershipCapsule verifyRetained(Decoded root,MembershipSourcePacket packet,Map<String,byte[]> images,
            MembershipSourcePull.RetainedCopy copy)throws java.io.IOException {
        Objects.requireNonNull(copy).check(root,packet);
        var result=verify(root,packet,images,Set.of(),Set.of(),true);copy.check(root,packet);return result;
    }
    /** Only complete original storage readers can issue this short-lived local-copy capability. */
    sealed interface StoredCopy permits MembershipCurrentGeneration.RetainedCopy,MembershipBasisSources.RetainedCopy,MembershipFloorFiles.RetainedCopy,MembershipGenerationFiles.RetainedCopy,MembershipRetirementFiles.RetainedCopy,MembershipPendingContextFiles.RetainedCopy {
        void check(Decoded root,MembershipSourcePacket packet)throws java.io.IOException;
        byte[] ancestry();
        Optional<byte[]> coverage()throws java.io.IOException;
        Decoded record(String name,String kind)throws java.io.IOException;
    }
    /** Complete original selected storage, checked under the exact exclusive local owner.
     * The history token never supplies fresh ACCEPT/PROOF observations. */
    static MembershipCapsule verifyStored(Decoded root,MembershipSourcePacket packet,Map<String,byte[]> images,
            StoredCopy copy)throws java.io.IOException {
        Objects.requireNonNull(copy).check(root,packet);
        byte[] ancestry=copy.ancestry();
        var result=verify(root,packet,images,Set.of(),Set.of(),true).retainingCompleteAncestry(ancestry);
        var coverage=copy.coverage();
        if(coverage.isPresent()) {
            var value=object(parse(coverage.get(),MembershipSelectionCoverage.MAXIMUM));
            boolean round="gse-v53-round-coverage/1.3".equals(value.get("schema"));
            require(round || "gse-v53-selected-coverage/1.3".equals(value.get("schema")),"stored history coverage schema");
            var proofs=new HashSet<>(result.history);result.retainCoverageCertificate(value,proofs);
            if(round)result.retainCoverageCertificate(object(value.get("first")),proofs);
            result=new MembershipCapsule(result.context,result.packet,result.anchors,result.states,Set.of(),proofs,result.highestMembershipCertificate);
            MembershipSelectionCoverage.verify(coverage.get(),result,copy.record("promise.gsr","PROMISE"),copy.record("selected.gsr","SELECTED"),ancestry);
        }
        copy.check(root,packet);return result;
    }
    private void retainCoverageCertificate(Map<String,Object> coverage,Set<Historical> proofs) {
        var parent=object(object(coverage.get("parent")).get("cut"));
        var certificate=context.record((String)coverage.get("certificate"),"CERTIFICATE");
        context.certificateStructure(certificate,parent);proofs.add(certificate(certificate,parent));
    }
    private static MembershipCapsule verify(Decoded root,MembershipSourcePacket packet,Map<String,byte[]> images,
            Set<Owned> owned,Set<Historical> inherited,boolean retainedCopy) {
        var history=new HashSet<Historical>();
        for(var item:inherited)if(packet.objectNames().contains(item.record()))history.add(item);
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
                var proof=certificate(cert,at);
                var entry=retainedCopy || history.contains(proof)?context.certificateStructure(cert,at):context.certificateAt(cert,owned,at);
                history.add(proof);var entryValue=entry.value();
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
            var endorsements=list(item.get("endorsements"));var proof=checkpoint(statement,endorsements);
            checkpoint(context,packet,statement,endorsements,owned,bytes,retainedCopy || history.contains(proof));history.add(proof);
            long size=0;for(String hash:bytes)size+=packet.objectBytes(hash).length;
            require(size<=(item.get("kind").equals("RANGE")?16:48)*1024,"complete capsule item byte capacity");
            at=end;catalog=(String)s.get("catalogAfter");application=(String)s.get("applicationAfter");anchors.put(number(at.get("index")),at);states.put(number(at.get("index")),new Anchor(at,catalog,application));
        }
        require(list(capsule.get("items")).size()<=3*changes+1,"capsule logical item bound");
        require(at.equals(currentCut) && catalog.equals(capsule.get("catalog")) && application.equals(capsule.get("application")),"capsule terminal state");
        return new MembershipCapsule(context,packet,anchors,states,owned,history,highestMembershipCertificate);
    }
    void verifyAncestry(byte[] bytes,Collection<Anchor> required) {
        var lower=ancestryAnchors(bytes);
        for(var anchor:required) {
            var direct=anchor(number(anchor.cut().get("index")));
            require(direct==null?anchor.equals(lower.get(anchor.cut())):anchor.equals(direct),"generation did not preserve original proven parent");
        }
    }
    /** Return only fully authenticated lower endpoints; packed inventory extras are not ancestry. */
    Map<Map<String,Object>,Anchor> ancestryAnchors(byte[] bytes) {
        var lower=new HashMap<Map<String,Object>,Anchor>();
        for(var bridge:verifiedAncestry(bytes)) {
            var value=bridge.statement.value();var anchor=new Anchor(object(value.get("start")),(String)value.get("catalogBefore"),(String)value.get("applicationBefore"));
            lower.put(anchor.cut(),anchor);
        }
        return Map.copyOf(lower);
    }
    /** Original statements/endorsements only after the whole retained ancestry verifies. */
    List<MembershipSelection.Bridge> verifiedAncestry(byte[] bytes) {
        var bridges=ancestryFrames(bytes);var lower=new HashMap<Map<String,Object>,Anchor>();
        for(var bridge:bridges) {
            var value=bridge.statement.value();var anchor=new Anchor(object(value.get("start")),(String)value.get("catalogBefore"),(String)value.get("applicationBefore"));
            require(lower.putIfAbsent(anchor.cut(),anchor)==null,"duplicate generation ancestry");bridge.verify(this,anchor);
        }
        return bridges;
    }
    /** Extend only exact historical authority from an authenticated complete manifest/ancestry copy. */
    MembershipCapsule retainingAncestry(byte[] bytes,MembershipSourcePull.RetainedAncestry copy)throws java.io.IOException {
        Objects.requireNonNull(copy).check(this,bytes);var result=retainingCompleteAncestry(bytes);
        copy.check(this,bytes);return result;
    }
    private MembershipCapsule retainingCompleteAncestry(byte[] bytes) {
        var retained=new HashSet<Historical>();
        for(var item:history)if(packet.objectNames().contains(item.record()))retained.add(item);
        for(var bridge:ancestryFrames(bytes))retained.add(checkpoint(bridge.statement,bridge.acknowledgements.stream().map(Decoded::digest).toList()));
        var result=new MembershipCapsule(context,packet,anchors,states,observations,retained,highestMembershipCertificate);
        result.verifiedAncestry(bytes);return result;
    }
    boolean historicalCheckpoint(Decoded statement,List<Decoded> acknowledgements) {
        return history.contains(checkpoint(statement,acknowledgements.stream().map(Decoded::digest).toList()));
    }
    private List<MembershipSelection.Bridge> ancestryFrames(byte[] bytes) {
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
        return List.copyOf(bridges);
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
                                   Set<Owned> owned,Set<String> bytes,boolean historical) {
        var cut=object(statement.value().get("end"));var voters=new ArrayList<String>();
        for(Object hash:endorsements) {
            var ack=context.record((String)hash,"CHECKPOINT_ACK");var value=ack.value();String voter=(String)value.get("voter");
            var id=context.identities.get(voter);
            require(id!=null && id.storageId().toString().equals(value.get("incarnation")) && value.get("cut").equals(cut)
                    && value.get("statement").equals(statement.digest()),"checkpoint exact statement/end identity");
            require(historical || owned.contains(new Owned(voter,id.storageId(),ack.digest(),cutDigest(cut))),"checkpoint before owned applied end");
            voters.add(voter);bytes.add(ack.digest());
        }
        orderedNodes(voters);quorum(object(cut.get("view")),voters);
    }
}
