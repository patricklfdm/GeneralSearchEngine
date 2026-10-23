package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Certified next state and exact checkpoint request. Neither projection nor assembly forces an end or issues an ACK. */
final class MembershipCheckpointPlan {
    final Decoded catalog,statement;
    final MembershipApplicationReplay.Result application;
    private final MembershipCapsule before;
    private final Decoded root,certificate,entry;
    private final Map<String,byte[]> originals;
    private final Set<Owned> votes;
    private final List<Map<String,Object>> retained;
    private final String descriptor;
    private final List<MembershipCapsule.Anchor> additionalParents,requiredParents;
    Decoded originalCertificate(){return certificate;}
    MembershipCapsule.Anchor originalParent(){return before.terminal();}
    List<MembershipCapsule.Anchor> additionalParents(){return additionalParents;}
    /** Renew only authenticated original endpoints hidden inside the newly enlarged RANGE. */
    MembershipCheckpointPlan renewAncestors(Collection<MembershipCapsule.Anchor> required,byte[] originalAncestry) {
        var parents=renewalParents(before,(String)entry.value().get("kind"),required,originalAncestry);
        var all=new ArrayList<>(required);all.add(before.terminal());
        require(requiredBridges(before,(String)entry.value().get("kind"),all).size()<=6 && parents.size()<=5,"checkpoint renewed ancestry count");
        return new MembershipCheckpointPlan(this,parents,List.copyOf(all));
    }
    /** Pure admission projection; the actual new end/catalog and ACK still require certified replay. */
    static Map<String,Object> rangeStart(MembershipCapsule before,String kind) {
        var items=list(before.packet.capsule().value().get("items"));
        if(!Set.of("INTENT","FINAL").contains(kind) && !items.isEmpty()) {
            var last=object(items.getLast());
            if(last.get("kind").equals("RANGE"))return object(before.context.record((String)last.get("statement"),"CHECKPOINT").value().get("start"));
        }
        return before.context.cut;
    }
    static List<MembershipCapsule.Anchor> renewalParents(MembershipCapsule before,String kind,Collection<MembershipCapsule.Anchor> required,byte[] ancestry) {
        require(required.size()<=16,"checkpoint ancestor input count");before.verifyAncestry(ancestry,required);
        var start=rangeStart(before,kind);var unique=new TreeMap<Long,MembershipCapsule.Anchor>();
        for(var lower:required) {
            long index=number(lower.cut().get("index"));
            if(index>number(start.get("index")) && index<number(before.context.cut.get("index"))) {
                require(start.get("view").equals(lower.cut().get("view")),"checkpoint ancestor changed stable era");
                var prior=unique.putIfAbsent(index,lower);require(prior==null || prior.equals(lower),"checkpoint conflicting ancestor");
            }
        }
        return List.copyOf(unique.values());
    }
    /** Endpoints that will not be direct anchors of the next complete capsule. */
    static List<MembershipCapsule.Anchor> requiredBridges(MembershipCapsule before,String kind,Collection<MembershipCapsule.Anchor> required) {
        boolean hidden=!rangeStart(before,kind).equals(before.context.cut);var unique=new TreeMap<Long,MembershipCapsule.Anchor>();
        for(var lower:required) {
            long index=number(lower.cut().get("index"));var direct=before.anchor(index);
            require(direct==null || direct.equals(lower),"checkpoint conflicting required anchor");
            if(direct==null || hidden && lower.equals(before.terminal())) {
                var old=unique.putIfAbsent(index,lower);require(old==null || old.equals(lower),"checkpoint conflicting required bridge");
            }
        }
        return List.copyOf(unique.values());
    }
    private MembershipCheckpointPlan(MembershipCheckpointPlan original,List<MembershipCapsule.Anchor> parents,List<MembershipCapsule.Anchor> required) {
        before=original.before;root=original.root;certificate=original.certificate;entry=original.entry;catalog=original.catalog;
        statement=original.statement;application=original.application;votes=original.votes;originals=original.originals;
        retained=original.retained;descriptor=original.descriptor;additionalParents=List.copyOf(parents);requiredParents=List.copyOf(required);
    }
    static Decoded ancestorStatement(Decoded statement,MembershipCapsule.Anchor parent,MembershipCapsule.Anchor lower) {
        var value=statement.value();var start=object(value.get("start"));var view=object(start.get("view"));
        require(parentStatement(statement,parent).isPresent() && number(lower.cut().get("index"))>number(start.get("index"))
                && number(lower.cut().get("index"))<number(parent.cut().get("index")) && view.equals(lower.cut().get("view")),"checkpoint exact hidden earlier ancestor");
        var renewed=new TreeMap<>(value);renewed.put("start",lower.cut());renewed.put("catalogBefore",lower.catalog());renewed.put("applicationBefore",lower.application());
        return decode(encode("records","CHECKPOINT",renewed),"records","CHECKPOINT");
    }

    /** A compacted RANGE hides the actual certified parent. Its supplemental statement
     * is derived from that exact original state, never from a caller-supplied cut. */
    Optional<Decoded> parentStatement(){return parentStatement(statement,originalParent());}
    static Optional<Decoded> parentStatement(Decoded statement,MembershipCapsule.Anchor parent) {
        var value=statement.value();var start=object(value.get("start"));var end=object(value.get("end"));
        require(number(end.get("index"))==Math.addExact(number(parent.cut().get("index")),1),"checkpoint exact next parent index");
        if(start.equals(parent.cut())) {
            require(value.get("catalogBefore").equals(parent.catalog()) && value.get("applicationBefore").equals(parent.application()),"checkpoint exact direct parent");
            return Optional.empty();
        }
        var view=object(parent.cut().get("view"));
        require(value.get("scope").equals("RANGE") && view.get("operation")==null && view.equals(start.get("view")) && view.equals(end.get("view"))
                && number(start.get("index"))<number(parent.cut().get("index")),"checkpoint hidden parent in same stable range");
        var bridge=new TreeMap<>(value);bridge.put("start",parent.cut());bridge.put("catalogBefore",parent.catalog());bridge.put("applicationBefore",parent.application());
        return Optional.of(decode(encode("records","CHECKPOINT",bridge),"records","CHECKPOINT"));
    }

    static <K,T> MembershipCheckpointPlan replay(SearchEngineConfiguration<K,T> captured,DurableStorageConfig<K,T> storage,
            MembershipCapsule before,MembershipSourcePacket certified,Decoded certificate,Map<String,byte[]> images,Set<Owned> votes,Path scratch)throws IOException {
        require(votes.size()<=12 && Arrays.equals(certificate.bytes(),certified.objectBytes(certificate.digest())),"checkpoint original certificate/observation bound");
        var context=certifiedContext(before,certified,images);context.certificate(certificate,votes);
        var entry=context.record((String)certificate.value().get("entry"),"ENTRY");
        var root=root(before);byte[] payload=certified.objectBytes((String)entry.value().get("payload"));
        var result=MembershipApplicationReplay.replay(captured,storage,images.get(context.catalog.get("application")),
                (String)context.catalog.get("application"),UUID.fromString((String)root.value().get("historyId")),
                number(context.catalog.get("applicationSequence")),number(context.cut.get("index")),
                List.of(new MembershipApplicationReplay.Step(number(entry.value().get("index")),(String)entry.value().get("kind"),payload)),scratch);
        return project(before,certified,certificate,images,votes,result);
    }

    /** The storage owner may also supply an already semantically verified exact projection. */
    static MembershipCheckpointPlan project(MembershipCapsule before,MembershipSourcePacket certified,Decoded proposed,
            Map<String,byte[]> images,Set<Owned> votes,MembershipApplicationReplay.Result application) {
        var certificate=decode(proposed.bytes(),"records","CERTIFICATE");
        require(votes.size()<=12,"checkpoint phased observation count");
        require(Arrays.equals(certificate.bytes(),certified.objectBytes(certificate.digest())),"checkpoint original certificate bytes");
        var context=certifiedContext(before,certified,images);context.certificate(certificate,votes);
        var entry=context.record((String)certificate.value().get("entry"),"ENTRY");
        byte[] payload=certified.objectBytes((String)entry.value().get("payload"));
        var catalog=MembershipCatalog.project(context,entry,payload,application);
        var result=new MembershipCheckpointPlan(before,certified,certificate,entry,catalog,application,votes);
        new MembershipContext(result.root,catalog,object(catalog.value().get("cut")),result.originals,
                Map.of(hash(application.image()),application.image())).monotonicFrom(context);
        return result;
    }

    private static MembershipContext certifiedContext(MembershipCapsule before,MembershipSourcePacket certified,Map<String,byte[]> images) {
        for(String field:List.of("root","initial","cut","catalog","application","items"))
            require(before.packet.capsule().value().get(field).equals(certified.capsule().value().get(field)),"checkpoint changed certified base: "+field);
        require(before.packet.images().equals(certified.images()),"checkpoint changed base images");certified.verifyImages(images);
        for(String key:before.packet.objectNames())require(Arrays.equals(before.packet.objectBytes(key),certified.objectBytes(key)),"checkpoint changed original object");
        var objects=objects(certified);var catalog=decode(certified.objectBytes((String)certified.capsule().value().get("catalog")),"records","CATALOG");
        return new MembershipContext(root(before),catalog,before.context.cut,objects,images);
    }
    private static Decoded root(MembershipCapsule before) {
        return decode(before.packet.objectBytes(before.context.recordRootDigest()),"records","ROOT");
    }
    private static Map<String,byte[]> objects(MembershipSourcePacket packet) {
        var result=new TreeMap<String,byte[]>();for(String key:packet.objectNames())result.put(key,packet.objectBytes(key));return result;
    }
    private MembershipCheckpointPlan(MembershipCapsule before,MembershipSourcePacket certified,Decoded certificate,Decoded entry,
            Decoded catalog,MembershipApplicationReplay.Result application,Set<Owned> votes) {
        this.before=before;this.root=root(before);this.certificate=certificate;this.entry=entry;this.catalog=catalog;this.application=application;
        this.votes=Set.copyOf(votes);this.originals=objects(certified);originals.put(catalog.digest(),catalog.bytes());
        additionalParents=List.of();requiredParents=List.of(before.terminal());
        String kind=(String)entry.value().get("kind");boolean membership=Set.of("INTENT","FINAL").contains(kind);
        var items=new ArrayList<Map<String,Object>>();for(Object item:list(before.packet.capsule().value().get("items")))items.add(object(item));
        Map<String,Object> start=before.context.cut;String catalogBefore=(String)before.packet.capsule().value().get("catalog");
        String applicationBefore=(String)before.context.catalog.get("application");
        if(!membership && !items.isEmpty() && items.getLast().get("kind").equals("RANGE")) {
            var prior=decode(certified.objectBytes((String)items.removeLast().get("statement")),"records","CHECKPOINT").value();
            start=object(prior.get("start"));catalogBefore=(String)prior.get("catalogBefore");applicationBefore=(String)prior.get("applicationBefore");
        }
        if(membership) {
            var operation=list(before.context.catalog.get("results")).stream().map(MembershipFormat::object)
                    .filter(row->object(row.get("request")).get("number").equals(before.context.catalog.get("active"))).findFirst().orElseThrow();
            var sealed=new TreeMap<String,Object>();for(String field:List.of("request","prepared","receipt"))sealed.put(field,operation.get(field));
            byte[] bytes=canonical(sealed,8192);descriptor=hash(bytes);originals.put(descriptor,bytes);
        }else descriptor=null;
        require(start.equals(rangeStart(before,kind)),"checkpoint admission/materialization start mismatch");
        retained=List.copyOf(items);
        statement=decode(encode("records","CHECKPOINT",Map.of("root",before.context.root,"scope",membership?"MEMBERSHIP":"RANGE",
                "start",start,"end",catalog.value().get("cut"),"catalogBefore",catalogBefore,"catalogAfter",catalog.digest(),
                "applicationBefore",applicationBefore,"applicationAfter",catalog.value().get("application"))),"records","CHECKPOINT");
    }

    /** Only original, separately authenticated applied-end ACKs can complete the capsule. */
    MembershipCapsule complete(List<Decoded> acknowledgements,Set<Owned> checkpoints) {
        require(acknowledgements.size()>0 && acknowledgements.size()<=6 && checkpoints.size()<=6,"checkpoint endorsement count");
        var objects=new TreeMap<String,byte[]>();objects.put(root.digest(),root.bytes());copy(objects,(String)root.value().get("genesis"));
        objects.put(catalog.digest(),catalog.bytes());var items=new ArrayList<Map<String,Object>>();
        for(var item:retained){copyItem(objects,item);items.add(item);}
        objects.put(statement.digest(),statement.bytes());var acks=new ArrayList<String>();var voters=new ArrayList<String>();
        for(var proposed:acknowledgements) {
            var ack=decode(proposed.bytes(),"records","CHECKPOINT_ACK");var value=ack.value();
            require(value.get("root").equals(before.context.root) && value.get("cut").equals(statement.value().get("end"))
                    && value.get("statement").equals(statement.digest()),"checkpoint exact new endorsement");
            require(checkpoints.contains(new Owned((String)value.get("voter"),UUID.fromString((String)value.get("incarnation")),
                    ack.digest(),cutDigest(object(value.get("cut"))))),"checkpoint missing new applied-end observation");
            voters.add((String)value.get("voter"));acks.add(ack.digest());objects.put(ack.digest(),ack.bytes());
        }
        orderedNodes(voters);var item=new TreeMap<String,Object>();item.put("kind",statement.value().get("scope"));
        item.put("statement",statement.digest());item.put("endorsements",acks);item.put("certificate",descriptor==null?null:certificate.digest());item.put("descriptor",descriptor);
        if(descriptor!=null)copyMembership(objects,item);items.add(item);
        var images=Map.of(hash(application.image()),application.image());var sizes=Map.of(hash(application.image()),(long)application.image().length);
        var cap=new TreeMap<>(before.packet.capsule().value());cap.put("cut",catalog.value().get("cut"));cap.put("catalog",catalog.digest());
        cap.put("application",catalog.value().get("application"));cap.put("items",items);cap.put("inventory",hash(MembershipSourcePacket.index(objects,sizes)));
        var frame=decode(encode("records","CAPSULE",cap),"records","CAPSULE");
        var packet=MembershipSourcePacket.decode(MembershipSourcePacket.encode(frame,objects,sizes));
        var owned=new HashSet<>(votes);owned.addAll(checkpoints);
        return before.verifyExtension(packet,images,owned);
    }
    private void copy(Map<String,byte[]> objects,String digest) {
        byte[] bytes=originals.get(digest);require(bytes!=null,"checkpoint missing exact original");objects.put(digest,bytes.clone());
    }
    /** Retain one selected-slot proof and bounded, separately endorsed ancestry for local publication.
     * Normal source compaction remains unchanged; no receipt is inferred from witness hashes. */
    MembershipCapsule publication(List<Decoded> acknowledgements,Set<Owned> checkpoints,List<MembershipSelection.Bridge> bridges) {
        require(bridges.size()<=6,"publication ancestry count");
        var complete=complete(acknowledgements,checkpoints);var objects=objects(complete.packet);
        for(String digest:List.of(certificate.digest(),entry.digest(),(String)entry.value().get("payload")))copy(objects,digest);
        var accept=new TreeMap<>(certificate.value());accept.remove("accepts");accept.remove("proofs");copy(objects,hash(encode("records","ACCEPT",accept)));
        accept.put("accepts",certificate.value().get("accepts"));copy(objects,hash(encode("records","PROOF",accept)));
        var owned=new HashSet<>(votes);owned.addAll(checkpoints);
        for(var bridge:bridges) {
            objects.put(bridge.statement.digest(),bridge.statement.bytes());
            for(var ack:bridge.acknowledgements)objects.put(ack.digest(),ack.bytes());owned.addAll(bridge.owned);
        }
        var value=new TreeMap<>(complete.packet.capsule().value());value.put("inventory",hash(MembershipSourcePacket.index(objects,complete.packet.images())));
        var packet=MembershipSourcePacket.decode(MembershipSourcePacket.encode(decode(encode("records","CAPSULE",value),"records","CAPSULE"),objects,complete.packet.images()));
        var result=before.verifyExtension(packet,Map.of(hash(application.image()),application.image()),owned);
        byte[] ancestry=MembershipGenerationPlan.ancestry(bridges);result.verifyAncestry(ancestry,requiredParents);
        var expected=new HashSet<Map<String,Object>>();
        for(var parent:requiredParents)if(result.anchor(number(parent.cut().get("index")))==null)expected.add(parent.cut());
        require(result.ancestryAnchors(ancestry).keySet().equals(expected),"publication requires exact retained ancestry set");return result;
    }
    private void copyItem(Map<String,byte[]> objects,Map<String,Object> item) {
        copy(objects,(String)item.get("statement"));for(Object ack:list(item.get("endorsements")))copy(objects,(String)ack);
        if(item.get("certificate")!=null)copyMembership(objects,item);
    }
    private void copyMembership(Map<String,byte[]> objects,Map<String,Object> item) {
        copy(objects,(String)item.get("descriptor"));String hash=(String)item.get("certificate");copy(objects,hash);
        var certificate=decode(objects.get(hash),"records","CERTIFICATE");var value=certificate.value();copy(objects,(String)value.get("entry"));
        var entry=decode(objects.get(value.get("entry")),"records","ENTRY");copy(objects,(String)entry.value().get("payload"));
        var accept=new TreeMap<>(value);accept.remove("accepts");accept.remove("proofs");copy(objects,hash(encode("records","ACCEPT",accept)));
        accept.put("accepts",value.get("accepts"));copy(objects,hash(encode("records","PROOF",accept)));
    }
}
