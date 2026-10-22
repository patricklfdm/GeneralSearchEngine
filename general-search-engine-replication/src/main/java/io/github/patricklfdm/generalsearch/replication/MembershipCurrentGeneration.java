package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Selected, immutable local generation. Historical remote force evidence remains a separate verifier input.
 * Installation/retirement is deliberately unavailable until the selected-source transaction exists. */
final class MembershipCurrentGeneration implements AutoCloseable {
    static final String DIRECTORY="generations", SELECTOR="selector.gsr", MANIFEST="generation.gsr";
    @FunctionalInterface interface Verifier {
        MembershipCapsule verify(Decoded root,MembershipSourcePacket packet,Map<String,byte[]> images);
    }
    private final Path parent,directory,path;
    private final Object directoryKey,pathKey;
    private final Map<String,FileIdentity> files=new TreeMap<>();
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private final FileIdentity selectorIdentity,manifestIdentity;
    private final MembershipIdentity identity;
    final MembershipCapsule capsule;
    final String accepted;
    final String generation;

    MembershipCurrentGeneration(Path parent,MembershipRoot root,MembershipIdentity identity,MembershipResources resources,
            Collection<Decoded> promises,Collection<Decoded> bases,Verifier verifier,MembershipBallotAllocator.Cut cut) throws IOException {
        this.parent=parent;this.identity=identity;directory=parent.resolve(DIRECTORY);directoryKey=key(directory);
        byte[] selectorBytes=AdmissionPaths.read(parent.resolve(SELECTOR),4096);var selector=decode(selectorBytes,"records","SELECTOR");
        bind(selector,root,identity);generation=(String)selector.value().get("generation");path=directory.resolve(generation);
        require(children(directory,2).equals(Set.of(generation)),"current generation requires sole selected inventory");pathKey=key(path);
        byte[] manifestBytes=AdmissionPaths.read(path.resolve(MANIFEST),65536);var manifest=decode(manifestBytes,"records","GENERATION");
        bind(manifest,root,identity);var value=manifest.value();
        require(selector.value().get("digest").equals(manifest.digest()) && value.get("generation").equals(generation),"current selector/manifest binding");
        require(value.get("basis")==null && value.get("selection")==null,"selected installation records require Phase 2C");
        selectorIdentity=inspect(parent.resolve(SELECTOR),selectorBytes.length,selector.digest());
        manifestIdentity=inspect(path.resolve(MANIFEST),manifestBytes.length,manifest.digest());
        var inventory=new TreeMap<String,Map<String,Object>>();long metadata=manifestBytes.length;
        String previous=null;
        for(Object row:list(value.get("files"))) {
            var file=object(row);String name=(String)file.get("path");
            require(name.equals(PACKET) || name.equals("promise.gsr") || name.equals("owned-tail.gsr") || name.matches("[0-9a-f]{64}\\.image"),"current file path");
            require(previous==null || previous.compareTo(name)<0,"current file inventory order");previous=name;inventory.put(name,file);
            long size=number(file.get("size"));long maximum=name.endsWith(".image")?MembershipResources.Unit.APPLICATION.bytes:
                    name.equals(PACKET)?MembershipSourcePacket.MAXIMUM:8192;
            require(size>0 && size<=maximum,"current file capacity");
            if(!name.endsWith(".image")){require(size<=MembershipResources.Unit.GENERATION.bytes-metadata,"complete generation metadata capacity");metadata+=size;}
        }
        var expected=new TreeSet<>(inventory.keySet());expected.add(MANIFEST);
        require(children(path,32).equals(expected) && inventory.containsKey(PACKET) && inventory.containsKey("promise.gsr"),"current file inventory");
        try {
            leases.add(resources.reserve(MembershipResources.Unit.MISC,"current-authority",MembershipResources.Unit.MISC.bytes));
            leases.add(resources.reserve(MembershipResources.Unit.GENERATION,generation,metadata));
            for(var file:inventory.values()) {
                String name=(String)file.get("path");long size=number(file.get("size"));
                if(name.endsWith(".image"))leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"generation-"+generation+":"+name,size));
                files.put(name,inspect(path.resolve(name),size,(String)file.get("sha256")));
            }
            var packet=MembershipSourcePacket.decode(AdmissionPaths.read(path.resolve(PACKET),MembershipSourcePacket.MAXIMUM));
            var localRoot=decode(AdmissionPaths.read(parent.resolve("root.gsr"),16384),"records","ROOT");
            require(Arrays.equals(localRoot.bytes(),packet.objectBytes(localRoot.digest())),"current original root");
            for(String field:List.of("root","cut","catalog","application"))require(value.get(field).equals(packet.capsule().value().get(field)),"current capsule binding: "+field);
            require(value.get("capsule").equals(packet.capsule().digest()),"current capsule digest");
            var names=new TreeSet<>(Set.of(PACKET,"promise.gsr"));packet.images().keySet().forEach(h->names.add(h+".image"));
            accepted=(String)value.get("ownedTail");if(accepted!=null)names.add("owned-tail.gsr");
            require(names.equals(inventory.keySet()),"current materialization inventory");
            for(var image:packet.images().entrySet()) {
                var file=files.get(image.getKey()+".image");require(file.bytes()==image.getValue() && file.digest().equals(image.getKey()),"current image binding");
            }
            var promise=decode(AdmissionPaths.read(path.resolve("promise.gsr"),8192),"records","PROMISE");
            require(promise.digest().equals(value.get("promise")) && promises.stream().anyMatch(p->Arrays.equals(p.bytes(),promise.bytes())),"current promise absent from journal");
            var materializations=materialize(packet);packet.verifyImages(materializations);
            capsule=Objects.requireNonNull(verifier.verify(localRoot,packet,materializations),"current capsule verifier");
            require(Arrays.equals(capsule.packet.bytes(),packet.bytes()),"current verifier substituted source");
            require(identity.equals(capsule.context.identities.get(identity.nodeId().value())) && capsule.context.voters().contains(identity.nodeId().value()),"current local eligible identity");
            require(promise.value().get("view").equals(capsule.context.authority()),"current promise view");
            capsule.context.ballot(promise.value().get("ballot"),true);
            // This entry cannot install another prefix. A later transaction must validate ancestry/adoption before switching.
            for(var basis:bases)require(basis.value().get("cut").equals(capsule.context.cut),"current generation differs from retained grant cut");
            if(accepted!=null) {
                var tail=decode(AdmissionPaths.read(path.resolve("owned-tail.gsr"),8192),"records","ACCEPT");
                require(tail.digest().equals(accepted) && Arrays.equals(tail.bytes(),packet.objectBytes(accepted)),"current owned tail copy");
                var b=new TreeMap<>(promise.value());b.put("voter",identity.nodeId().value());b.put("cut",capsule.context.cut);
                b.put("capsule",packet.capsule().digest());b.put("inventory",packet.inventoryDigest());b.put("accepted",accepted);
                packet.bind(decode(encode("records","BASIS",b),"records","BASIS"));
                var entry=capsule.context.record((String)tail.value().get("entry"),"ENTRY");
                capsule.context.ballot(tail.value().get("ballot"),true);capsule.context.ballot(entry.value().get("origin"),true);
                capsule.context.control((String)entry.value().get("kind"),command((String)entry.value().get("kind"),packet.objectBytes((String)entry.value().get("payload"))));
            }
            check();cut.at("CURRENT_VALIDATED");
            for(String name:files.keySet())force(path.resolve(name));cut.at("CURRENT_FILES_FORCED");
            force(path.resolve(MANIFEST));AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(directory);cut.at("CURRENT_GENERATION_FORCED");
            force(parent.resolve(SELECTOR));cut.at("CURRENT_SELECTOR_FORCED");
            AdmissionPaths.forceDirectory(parent);cut.at("CURRENT_DIRECTORY_FORCED");check();
        } catch(IOException | RuntimeException | Error error){close();throw error;}
    }
    private static void bind(Decoded frame,MembershipRoot root,MembershipIdentity identity) {
        require(frame.value().get("root").equals(root.manifestDigest()) && frame.value().get("node").equals(identity.nodeId().value()),"current root/node binding");
    }
    void check() throws IOException {
        require(directoryKey.equals(key(directory)) && pathKey.equals(key(path)) && children(directory,2).equals(Set.of(generation)),"current directory changed");
        var expected=new TreeSet<>(files.keySet());expected.add(MANIFEST);require(children(path,32).equals(expected),"current file inventory");
        checkFile(parent.resolve(SELECTOR),selectorIdentity);checkFile(path.resolve(MANIFEST),manifestIdentity);
        for(var file:files.entrySet())checkFile(path.resolve(file.getKey()),file.getValue());
    }
    private static void checkFile(Path path,FileIdentity expected) throws IOException {
        require(expected.equals(inspect(path,expected.bytes(),expected.digest())),"current inode changed");
    }
    private Map<String,byte[]> materialize(MembershipSourcePacket packet) throws IOException {
        var images=new TreeMap<String,byte[]>();
        for(var image:packet.images().entrySet())images.put(image.getKey(),AdmissionPaths.read(path.resolve(image.getKey()+".image"),Math.toIntExact(image.getValue())));
        return images;
    }
    Map<String,byte[]> images() throws IOException {check();var images=materialize(capsule.packet);capsule.packet.verifyImages(images);return images;}
    Optional<Owned> ownedTail() throws IOException {
        check();return accepted==null?Optional.empty():Optional.of(new Owned(identity.nodeId().value(),identity.storageId(),accepted,cutDigest(capsule.context.cut)));
    }
    @Override public void close(){leases.forEach(MembershipResources.Lease::close);leases.clear();}
}
