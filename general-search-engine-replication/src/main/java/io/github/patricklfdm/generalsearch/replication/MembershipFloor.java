package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact durable-copy floor admission. A verified capsule or hash alone is not a copy observation. */
final class MembershipFloor {
    static final class Copy {
        final Decoded generation;
        final MembershipCapsule capsule;
        final MembershipIdentity owner;
        private final Map<String,byte[]> files;
        private Copy(Decoded generation,MembershipCapsule capsule,MembershipIdentity owner,Map<String,byte[]> files) {
            this.generation=generation;this.capsule=capsule;this.owner=owner;this.files=Map.copyOf(files);
        }
        /** Remote callers must provide authenticated force observations, not self-declared hashes. */
        static Copy verify(Decoded generation,MembershipCapsule capsule,MembershipIdentity owner,Set<Owned> forced,Map<String,byte[]> files) {
            require(generation.kind().equals("GENERATION"),"floor generation kind");var value=generation.value();
            require(value.get("root").equals(capsule.context.root) && value.get("node").equals(owner.nodeId().value())
                    && owner.equals(capsule.context.identities.get(owner.nodeId().value())),"floor copy identity");
            require(capsule.context.voters().contains(owner.nodeId().value()),"floor copy is not a governing voter");
            require(value.get("cut").equals(capsule.context.cut) && value.get("catalog").equals(capsule.terminal().catalog())
                    && value.get("application").equals(capsule.terminal().application()) && value.get("capsule").equals(capsule.packet.capsule().digest()),"floor copy materialization binding");
            require(forced.contains(new Owned(owner.nodeId().value(),owner.storageId(),generation.digest(),cutDigest(capsule.context.cut))),"floor copy has no exact forced generation");
            // Its force observation describes the whole validated generation, including all
            // manifest members/images. Local producers obtain it only after rechecking the owner.
            var copy=new Copy(generation,capsule,owner,files);copy.check();return copy;
        }
        void check() {validateMaterialization(generation,capsule,owner,files);}
        /** Pure original-byte validation; it creates no copy observation or deletion authority. */
        static void validateMaterialization(Decoded generation,MembershipCapsule capsule,MembershipIdentity owner,Map<String,byte[]> files) {
            require(generation.kind().equals("GENERATION"),"floor generation kind");var materialization=generation.value();
            require(materialization.get("root").equals(capsule.context.root) && materialization.get("node").equals(owner.nodeId().value())
                    && owner.equals(capsule.context.identities.get(owner.nodeId().value())),"floor copy identity");
            require(capsule.context.voters().contains(owner.nodeId().value()),"floor copy is not a governing voter");
            require(materialization.get("cut").equals(capsule.context.cut) && materialization.get("catalog").equals(capsule.terminal().catalog())
                    && materialization.get("application").equals(capsule.terminal().application())
                    && materialization.get("capsule").equals(capsule.packet.capsule().digest()),"floor copy materialization binding");
            var value=generation.value();var expected=new TreeSet<String>();expected.add("generation.gsr");long metadata=generation.bytes().length;String previous=null;
            require(Arrays.equals(files.get("generation.gsr"),generation.bytes()),"floor original generation bytes");
            for(Object row:list(value.get("files"))) {
                var file=object(row);String name=(String)file.get("path");
                require(name.equals("source.gscp") || name.equals("promise.gsr") || name.equals("basis.gsr") || name.equals("selected.gsr")
                        || name.equals("owned-tail.gsr") || name.equals("ancestry.gsr") || name.equals(MembershipGenerationPlan.ADOPTION) || name.equals(MembershipSelectionCoverage.FILE) || name.equals(MembershipSelectedSources.FILE)
                        || name.matches("[0-9a-f]{64}\\.image"),"floor source member path");
                require(previous==null || previous.compareTo(name)<0,"floor source inventory order");previous=name;expected.add(name);
                byte[] bytes=files.get(name);require(bytes!=null && bytes.length>0 && bytes.length<=MembershipGenerationFiles.limit(name) && bytes.length==number(file.get("size")) && hash(bytes).equals(file.get("sha256")),"floor source member bytes");
                if(name.endsWith(".image"))require(bytes.length>0 && bytes.length<=MembershipResources.Unit.APPLICATION.bytes && name.equals(hash(bytes)+".image"),"floor source image binding");
                else {metadata=Math.addExact(metadata,bytes.length);require(metadata<=MembershipResources.Unit.GENERATION.bytes,"floor source metadata capacity");}
            }
            require(expected.equals(files.keySet()) && expected.size()<=32 && Arrays.equals(files.get("source.gscp"),capsule.packet.bytes()),"floor complete source inventory");
            var images=new TreeMap<String,byte[]>();for(String hash:capsule.packet.images().keySet())images.put(hash,files.get(hash+".image"));capsule.packet.verifyImages(images);
            var names=new TreeSet<String>(Set.of("generation.gsr","source.gscp","promise.gsr"));
            capsule.packet.images().keySet().forEach(h->names.add(h+".image"));
            boolean adopted=files.containsKey(MembershipGenerationPlan.ADOPTION);
            boolean published=files.containsKey(MembershipSelectionCoverage.FILE);
            require(!published || !adopted && value.get("selection")!=null && value.get("ownedTail")==null,"floor publication selection binding");
            require((value.get("basis")==null)==(value.get("selection")==null),"floor incomplete selection binding");
            if(value.get("selection")!=null){names.add("basis.gsr");names.add("selected.gsr");}
            if(adopted)names.add(MembershipGenerationPlan.ADOPTION);
            if(published)names.add(MembershipSelectionCoverage.FILE);
            if(value.get("selection")!=null && files.containsKey(MembershipSelectedSources.FILE))names.add(MembershipSelectedSources.FILE);
            if((adopted || value.get("selection")!=null) && files.containsKey("ancestry.gsr"))names.add("ancestry.gsr");
            if(value.get("ownedTail")!=null)names.add("owned-tail.gsr");
            require(names.equals(files.keySet()),"floor materialization inventory");
            var promise=decode(files.get("promise.gsr"),"records","PROMISE");
            require(promise.digest().equals(value.get("promise")) && promise.value().get("root").equals(capsule.context.root),"floor source promise binding");
            if(adopted) {
                require(value.get("selection")==null && value.get("ownedTail")==null,"floor adoption is not a selected grant");
                var certificate=capsule.membershipCertificateFence().orElseThrow(()->new IllegalArgumentException("floor adoption certificate absent"));
                require(Arrays.equals(certificate.bytes(),files.get(MembershipGenerationPlan.ADOPTION))
                        && compareBallot(object(promise.value().get("ballot")),object(certificate.value().get("ballot")))>=0,"floor adopted promise below certificate");
            }else if(!published) {
                require(promise.value().get("view").equals(capsule.context.authority()),"floor source promise view");
                capsule.context.ballot(promise.value().get("ballot"),true);
            }
            if(value.get("selection")!=null) {
                var basis=decode(files.get("basis.gsr"),"records","BASIS");var selected=decode(files.get("selected.gsr"),"records","SELECTED");
                require(basis.digest().equals(value.get("basis")) && selected.digest().equals(value.get("selection")),"floor source frame binding");
                for(String field:List.of("root","view","ballot"))require(basis.value().get(field).equals(promise.value().get(field))
                        && selected.value().get(field).equals(promise.value().get(field)),"floor selected promise binding");
                require(basis.value().get("voter").equals(owner.nodeId().value()) && basis.value().get("basisId").equals(promise.value().get("basisId"))
                        && (published || selected.value().get("cut").equals(capsule.context.cut)),"floor selected original owner");
                if(files.containsKey(MembershipSelectedSources.FILE))MembershipSelectedSources.parents(files.get(MembershipSelectedSources.FILE),selected,capsule,files.getOrDefault("ancestry.gsr",new byte[0]));
                if(published)MembershipSelectionCoverage.verify(files.get(MembershipSelectionCoverage.FILE),capsule,promise,selected,files.getOrDefault("ancestry.gsr",new byte[0]));
                var voters=new ArrayList<String>();boolean own=false;
                for(Object row:list(selected.value().get("sources"))) {
                    var source=object(row);String voter=(String)source.get("voter");voters.add(voter);
                    if(voter.equals(owner.nodeId().value())) {
                        require(source.get("basisId").equals(basis.value().get("basisId")) && source.get("basisDigest").equals(basis.digest()),"floor selected local basis");own=true;
                    }
                }
                orderedNodes(voters);quorum(object(object(selected.value().get("cut")).get("view")),voters);
                require(own && voters.contains(object(promise.value().get("ballot")).get("proposer")),"floor selected quorum owner");
                if(value.get("ownedTail")==null)require(published || selected.value().get("nextEntry")==null,"floor selected tail missing");
                else require(selected.value().get("nextEntry").equals(decode(files.get("owned-tail.gsr"),"records","ACCEPT").value().get("entry")),"floor selected tail mismatch");
            }
            // Original ancestry evidence is retained and decoded even when no local old
            // generation is being retired by this admission operation.
            capsule.verifyAncestry(files.getOrDefault("ancestry.gsr",new byte[0]),List.of());
            if(value.get("ownedTail")!=null) {
                var tail=decode(files.get("owned-tail.gsr"),"records","ACCEPT");
                require(tail.digest().equals(value.get("ownedTail")) && Arrays.equals(tail.bytes(),capsule.packet.objectBytes(tail.digest())),"floor original tail binding");
                var basis=new TreeMap<>(promise.value());basis.put("voter",owner.nodeId().value());basis.put("cut",capsule.context.cut);
                basis.put("capsule",capsule.packet.capsule().digest());basis.put("inventory",capsule.packet.inventoryDigest());basis.put("accepted",tail.digest());
                capsule.packet.bind(decode(encode("records","BASIS",basis),"records","BASIS"));
                var entry=capsule.context.record((String)tail.value().get("entry"),"ENTRY");
                capsule.context.ballot(tail.value().get("ballot"),true);capsule.context.ballot(entry.value().get("origin"),true);
                capsule.context.control((String)entry.value().get("kind"),command((String)entry.value().get("kind"),capsule.packet.objectBytes((String)entry.value().get("payload"))));
            }
        }
        Set<String> fileNames(){return files.keySet();}
        byte[] fileBytes(String name){check();return Objects.requireNonNull(files.get(name)).clone();}
        Map<String,Object> reference() {
            return Map.of("voter",owner.nodeId().value(),"generation",generation.digest(),
                    "catalog",capsule.terminal().catalog(),"snapshot",capsule.terminal().application());
        }
    }
    static Decoded create(MembershipRoot root,Copy localCopy,List<Copy> offered) {
        localCopy.check();var local=localCopy.owner;var current=localCopy.capsule;
        require(current.context.root.equals(root.manifestDigest()) && local.equals(current.context.identities.get(local.nodeId().value())),"floor local root/identity");
        require(offered.size()>=2 && offered.size()<=6,"floor copy count");
        var copies=new TreeMap<String,Copy>();
        for(var copy:offered) {
            copy.check();String node=copy.owner.nodeId().value();
            require(copy.capsule.context.root.equals(root.manifestDigest()) && copy.capsule.terminal().equals(current.terminal())
                    && copy.owner.equals(current.context.identities.get(node)),"floor copy is not the exact current cut");
            require(copies.putIfAbsent(node,copy)==null,"duplicate floor voter");
        }
        require(copies.containsKey(local.nodeId().value()) && Arrays.equals(copies.get(local.nodeId().value()).generation.bytes(),localCopy.generation.bytes()),
                "floor lacks exact selected local generation");
        current.context.quorum(copies.keySet());
        var rows=copies.values().stream().map(Copy::reference).toList();
        return decode(encode("records","FLOOR",Map.of("root",root.manifestDigest(),"node",local.nodeId().value(),"cut",current.context.cut,"sources",rows)),"records","FLOOR");
    }
    static void verify(Decoded floor,MembershipRoot root,Copy local,List<Copy> offered) {
        require(Arrays.equals(floor.bytes(),create(root,local,offered).bytes()),"floor differs from exact original copies");
    }
}
