package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Selected, immutable local generation. Historical proof comes from explicit observations or its bound local owner.
 * The journal owns installation transactions; this reader never selects or retires a generation. */
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
    private final boolean installations;
    private final MembershipGrantJournal.HistoryRead historyOwner;
    private final MembershipRoot root;
    private boolean closed;
    final MembershipCapsule capsule;
    final String accepted;
    final boolean adopted;
    final String generation;
    final Decoded selector,manifest;

    MembershipCurrentGeneration(Path parent,MembershipRoot root,MembershipIdentity identity,MembershipResources resources,
            Collection<Decoded> promises,Collection<Decoded> bases,Verifier verifier,MembershipBallotAllocator.Cut cut) throws IOException {
        this(parent,root,identity,resources,promises,bases,List.of(),verifier,cut,false);
    }
    MembershipCurrentGeneration(Path parent,MembershipRoot root,MembershipIdentity identity,MembershipResources resources,
            Collection<Decoded> promises,Collection<Decoded> bases,Collection<Decoded> selections,Verifier verifier,MembershipBallotAllocator.Cut cut,boolean installations) throws IOException {
        this(parent,root,identity,resources,promises,bases,selections,Objects.requireNonNull(verifier),cut,installations,null);
    }
    /** Only the exclusive owner can recover a complete selected local copy without external historical observations.
     * This reader grants no vote and does not complete an adoption transaction or start a runtime. */
    static MembershipCurrentGeneration readOwned(MembershipGrantJournal.HistoryRead owner,MembershipResources resources,
            MembershipBallotAllocator.Cut cut)throws IOException {
        Objects.requireNonNull(owner).check();
        return new MembershipCurrentGeneration(owner.directory(),owner.root(),owner.identity(),resources,owner.promises(),owner.bases(),
                owner.selections(),null,cut,true,owner);
    }
    private MembershipCurrentGeneration(Path parent,MembershipRoot root,MembershipIdentity identity,MembershipResources resources,
            Collection<Decoded> promises,Collection<Decoded> bases,Collection<Decoded> selections,Verifier verifier,
            MembershipBallotAllocator.Cut cut,boolean installations,MembershipGrantJournal.HistoryRead historyOwner)throws IOException {
        this.parent=parent;this.root=root;this.identity=identity;this.historyOwner=historyOwner;this.installations=installations;
        if(historyOwner!=null)historyOwner.check();
        directory=parent.resolve(DIRECTORY);directoryKey=key(directory);
        byte[] selectorBytes=AdmissionPaths.read(parent.resolve(SELECTOR),4096);selector=decode(selectorBytes,"records","SELECTOR");
        bind(selector,root,identity);generation=(String)selector.value().get("generation");path=directory.resolve(generation);
        require(installations?Set.of("a","b").containsAll(children(directory,2)):children(directory,2).equals(Set.of(generation)),"current generation requires sole selected inventory");pathKey=key(path);
        byte[] manifestBytes=AdmissionPaths.read(path.resolve(MANIFEST),65536);manifest=decode(manifestBytes,"records","GENERATION");
        bind(manifest,root,identity);var value=manifest.value();
        require(selector.value().get("digest").equals(manifest.digest()) && value.get("generation").equals(generation),"current selector/manifest binding");
        require(value.get("basis")==null && value.get("selection")==null || installations && value.get("basis")!=null && value.get("selection")!=null,"selected installation records require Phase 2C");
        selectorIdentity=inspect(parent.resolve(SELECTOR),selectorBytes.length,selector.digest());
        manifestIdentity=inspect(path.resolve(MANIFEST),manifestBytes.length,manifest.digest());
        var inventory=new TreeMap<String,Map<String,Object>>();long metadata=manifestBytes.length;
        String previous=null;
        for(Object row:list(value.get("files"))) {
            var file=object(row);String name=(String)file.get("path");
            require(name.equals(PACKET) || name.equals("promise.gsr") || name.equals("owned-tail.gsr") || name.matches("[0-9a-f]{64}\\.image")
                    || installations && Set.of("basis.gsr","selected.gsr","ancestry.gsr",MembershipGenerationPlan.ADOPTION,MembershipSelectionCoverage.FILE,MembershipSelectedSources.FILE).contains(name),"current file path");
            require(previous==null || previous.compareTo(name)<0,"current file inventory order");previous=name;inventory.put(name,file);
            long size=number(file.get("size"));long maximum=name.endsWith(".image")?MembershipResources.Unit.APPLICATION.bytes:
                    name.equals(PACKET)?MembershipSourcePacket.MAXIMUM:name.equals("ancestry.gsr")?96*1024:name.equals("selected.gsr")?65536:
                    name.equals(MembershipSelectedSources.FILE)?MembershipSelectedSources.MAXIMUM:name.equals(MembershipSelectionCoverage.FILE)?MembershipSelectionCoverage.MAXIMUM:Set.of("basis.gsr",MembershipGenerationPlan.ADOPTION).contains(name)?16384:8192;
            require(size>0 && size<=maximum,"current file capacity");
            if(!name.endsWith(".image")){require(size<=MembershipResources.Unit.GENERATION.bytes-metadata,"complete generation metadata capacity");metadata+=size;}
        }
        adopted=inventory.containsKey(MembershipGenerationPlan.ADOPTION);
        boolean published=inventory.containsKey(MembershipSelectionCoverage.FILE);
        require(!published || installations && !adopted && value.get("selection")!=null && value.get("ownedTail")==null,"publication requires original selection without pending tail");
        require(!adopted || installations && value.get("selection")==null && value.get("basis")==null && value.get("ownedTail")==null,"adoption is not a selected grant");
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
            if(value.get("selection")!=null){names.add("basis.gsr");names.add("selected.gsr");}
            if(published)names.add(MembershipSelectionCoverage.FILE);
            if(value.get("selection")!=null && inventory.containsKey(MembershipSelectedSources.FILE))names.add(MembershipSelectedSources.FILE);
            if(adopted)names.add(MembershipGenerationPlan.ADOPTION);
            if((adopted || value.get("selection")!=null) && inventory.containsKey("ancestry.gsr"))names.add("ancestry.gsr");
            accepted=(String)value.get("ownedTail");if(accepted!=null)names.add("owned-tail.gsr");
            require(names.equals(inventory.keySet()),"current materialization inventory");
            for(var image:packet.images().entrySet()) {
                var file=files.get(image.getKey()+".image");require(file.bytes()==image.getValue() && file.digest().equals(image.getKey()),"current image binding");
            }
            var promise=decode(AdmissionPaths.read(path.resolve("promise.gsr"),8192),"records","PROMISE");
            require(promise.digest().equals(value.get("promise")) && promises.stream().anyMatch(p->Arrays.equals(p.bytes(),promise.bytes())),"current promise absent from journal");
            var materializations=materialize(packet);packet.verifyImages(materializations);
            if(historyOwner==null) capsule=Objects.requireNonNull(verifier.verify(localRoot,packet,materializations),"current capsule verifier");
            else {
                // The capability exists only during this exact validated inventory read. Its check
                // includes the actual owner, original selector, manifest and every retained byte.
                var copy=new RetainedCopy(this,packet,inventory.containsKey("ancestry.gsr")?
                        AdmissionPaths.read(path.resolve("ancestry.gsr"),96*1024):new byte[0]);
                try {capsule=MembershipCapsule.verifyStored(localRoot,packet,materializations,copy);}
                finally {copy.active=false;}
            }
            require(Arrays.equals(capsule.packet.bytes(),packet.bytes()),"current verifier substituted source");
            require(identity.equals(capsule.context.identities.get(identity.nodeId().value())) && (adopted || published || capsule.context.voters().contains(identity.nodeId().value())),"current local eligible identity");
            if(adopted) {
                var certificate=capsule.membershipCertificateFence().orElseThrow(()->new IllegalArgumentException("adopted certificate missing from capsule"));
                require(Arrays.equals(certificate.bytes(),AdmissionPaths.read(path.resolve(MembershipGenerationPlan.ADOPTION),16384)),"adopted certificate binding");
                require(compareBallot(object(promise.value().get("ballot")),object(certificate.value().get("ballot")))>=0,"adopted promise below certificate");
            }else if(!published) {
                require(promise.value().get("view").equals(capsule.context.authority()),"current promise view");
                capsule.context.ballot(promise.value().get("ballot"),true);
            }
            Decoded installed=null;
            if(value.get("selection")!=null) {
                var basis=decode(AdmissionPaths.read(path.resolve("basis.gsr"),16384),"records","BASIS");
                installed=decode(AdmissionPaths.read(path.resolve("selected.gsr"),65536),"records","SELECTED");var selectedBytes=installed.bytes();
                require(basis.digest().equals(value.get("basis")) && bases.stream().anyMatch(b->Arrays.equals(b.bytes(),basis.bytes())),"installed original basis absent from journal");
                require(installed.digest().equals(value.get("selection")) && selections.stream().anyMatch(s->Arrays.equals(s.bytes(),selectedBytes)),"installed selection absent from journal");
                for(String field:List.of("root","view","ballot"))require(installed.value().get(field).equals(promise.value().get(field)),"installed selection promise binding");
                require(basis.value().get("basisId").equals(promise.value().get("basisId")) && (published || installed.value().get("cut").equals(capsule.context.cut)),"installed selection parent");
                if(inventory.containsKey(MembershipSelectedSources.FILE))MembershipSelectedSources.parents(
                        AdmissionPaths.read(path.resolve(MembershipSelectedSources.FILE),MembershipSelectedSources.MAXIMUM),installed,capsule,
                        inventory.containsKey("ancestry.gsr")?AdmissionPaths.read(path.resolve("ancestry.gsr"),96*1024):new byte[0]);
                if(published) {
                    MembershipSelectionCoverage.verify(AdmissionPaths.read(path.resolve(MembershipSelectionCoverage.FILE),MembershipSelectionCoverage.MAXIMUM),
                            capsule,promise,installed,inventory.containsKey("ancestry.gsr")?AdmissionPaths.read(path.resolve("ancestry.gsr"),96*1024):new byte[0]);
                    if(!capsule.context.voters().contains(identity.nodeId().value()))MembershipSelectionCoverage.departingOwner(capsule,installed,identity);
                }
            }
            if(adopted || installed!=null) {
                var ancestors=new ArrayList<MembershipCapsule.Anchor>();
                for(var original:bases) {
                    var retained=MembershipSourcePacket.decode(AdmissionPaths.read(parent.resolve("sources").resolve((String)original.value().get("basisId")).resolve(PACKET),MembershipSourcePacket.MAXIMUM));
                    retained.bind(original);var cap=retained.capsule().value();ancestors.add(new MembershipCapsule.Anchor(object(cap.get("cut")),(String)cap.get("catalog"),(String)cap.get("application")));
                }
                capsule.verifyAncestry(inventory.containsKey("ancestry.gsr")?AdmissionPaths.read(path.resolve("ancestry.gsr"),96*1024):new byte[0],ancestors);
            }else for(var basis:bases)require(basis.value().get("cut").equals(capsule.context.cut),"current generation differs from retained grant cut");
            if(accepted!=null) {
                var tail=decode(AdmissionPaths.read(path.resolve("owned-tail.gsr"),8192),"records","ACCEPT");
                require(tail.digest().equals(accepted) && Arrays.equals(tail.bytes(),packet.objectBytes(accepted)),"current owned tail copy");
                var b=new TreeMap<>(promise.value());b.put("voter",identity.nodeId().value());b.put("cut",capsule.context.cut);
                b.put("capsule",packet.capsule().digest());b.put("inventory",packet.inventoryDigest());b.put("accepted",accepted);
                packet.bind(decode(encode("records","BASIS",b),"records","BASIS"));
                var entry=capsule.context.record((String)tail.value().get("entry"),"ENTRY");
                capsule.context.ballot(tail.value().get("ballot"),true);capsule.context.ballot(entry.value().get("origin"),true);
                capsule.context.control((String)entry.value().get("kind"),command((String)entry.value().get("kind"),packet.objectBytes((String)entry.value().get("payload"))));
                if(installed!=null)require(entry.digest().equals(installed.value().get("nextEntry")),"installed tail differs from selected choice");
            }
            if(installed!=null && accepted==null && !published)require(installed.value().get("nextEntry")==null,"installed selected tail missing");
            check();cut.at("CURRENT_VALIDATED");
            for(String name:files.keySet())force(path.resolve(name));cut.at("CURRENT_FILES_FORCED");
            force(path.resolve(MANIFEST));AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(directory);cut.at("CURRENT_GENERATION_FORCED");
            force(parent.resolve(SELECTOR));cut.at("CURRENT_SELECTOR_FORCED");
            AdmissionPaths.forceDirectory(parent);cut.at("CURRENT_DIRECTORY_FORCED");check();
        } catch(IOException | RuntimeException | Error error){close();throw error;}
    }
    /** Private construction prevents a bare packet or path from asserting local provenance. */
    static final class RetainedCopy implements MembershipCapsule.StoredCopy {
        private final MembershipCurrentGeneration source;
        private final MembershipSourcePacket packet;
        private final byte[] ancestry;
        private boolean active=true;
        private RetainedCopy(MembershipCurrentGeneration source,MembershipSourcePacket packet,byte[] ancestry) {
            this.source=source;this.packet=packet;this.ancestry=ancestry.clone();
        }
        public void check(Decoded root,MembershipSourcePacket packet)throws IOException {
            require(active && source.historyOwner!=null,"stored history read expired");source.check();
            require(root.rootDigest().equals(source.root.manifestDigest()) && Arrays.equals(this.packet.bytes(),packet.bytes())
                    && Arrays.equals(root.bytes(),packet.objectBytes(root.digest())),"stored history copy binding");
        }
        public byte[] ancestry(){require(active,"stored history read expired");return ancestry.clone();}
        public Optional<byte[]> coverage()throws IOException {
            require(active,"stored history read expired");return source.coverage();
        }
        public Decoded record(String name,String kind)throws IOException {
            require(active && Set.of("promise.gsr","selected.gsr").contains(name),"stored history record scope");source.check();
            require(source.files.containsKey(name),"stored history original record missing");
            return decode(AdmissionPaths.read(source.path.resolve(name),65536),"records",kind);
        }
    }
    private static void bind(Decoded frame,MembershipRoot root,MembershipIdentity identity) {
        require(frame.value().get("root").equals(root.manifestDigest()) && frame.value().get("node").equals(identity.nodeId().value()),"current root/node binding");
    }
    void check() throws IOException {
        require(!closed,"current generation closed");if(historyOwner!=null)historyOwner.check();
        require(directoryKey.equals(key(directory)) && pathKey.equals(key(path)) && (installations?Set.of("a","b").containsAll(children(directory,2)):children(directory,2).equals(Set.of(generation))),"current directory changed");
        var expected=new TreeSet<>(files.keySet());expected.add(MANIFEST);require(children(path,32).equals(expected),"current file inventory");
        checkFile(parent.resolve(SELECTOR),selectorIdentity);checkFile(path.resolve(MANIFEST),manifestIdentity);
        for(var file:files.entrySet())checkFile(path.resolve(file.getKey()),file.getValue());
    }
    private static void checkFile(Path path,FileIdentity expected) throws IOException {
        require(expected.equals(inspect(path,expected.bytes(),expected.digest())),"current inode changed");
    }
    /** Called only while the journal serializes owner validation and generation replacement.
     * Expose indexed packet/images, never a caller-supplied path or a voting record. */
    Map<String,MembershipSourceExport.Content> transferContents() {
        var result=new TreeMap<String,MembershipSourceExport.Content>();
        for(var item:files.entrySet())if(item.getKey().equals(PACKET) || item.getKey().endsWith(".image")) {
            var file=item.getValue();var kind=item.getKey().equals(PACKET)?MembershipTransfer.Kind.CAPSULE:MembershipTransfer.Kind.APPLICATION;
            require(result.put(file.digest(),new MembershipSourceExport.Content(file.digest(),file.bytes(),kind))==null,"current duplicate content");
        }
        return Map.copyOf(result);
    }
    /** Original selector-bound manifest and supplemental ancestry only. */
    Map<String,MembershipSourceExport.Content> ancestryContents() {
        var result=new TreeMap<String,MembershipSourceExport.Content>();
        result.put(manifest.digest(),new MembershipSourceExport.Content(manifest.digest(),manifest.size(),MembershipTransfer.Kind.RECORD));
        var ancestry=files.get("ancestry.gsr");
        if(ancestry!=null)require(result.put(ancestry.digest(),new MembershipSourceExport.Content(ancestry.digest(),ancestry.bytes(),MembershipTransfer.Kind.RECORD))==null,"ancestry content collision");
        return Map.copyOf(result);
    }
    /** Complete original generation for a governing-floor copy. Its records are
     * historical materialization bytes, not new voting observations. */
    Map<String,MembershipSourceExport.Content> generationContents() {
        var result=new TreeMap<String,MembershipSourceExport.Content>();
        result.put(manifest.digest(),new MembershipSourceExport.Content(manifest.digest(),manifest.size(),MembershipTransfer.Kind.RECORD));
        for(var entry:files.entrySet()) {
            var file=entry.getValue();var kind=entry.getKey().equals(PACKET)?MembershipTransfer.Kind.CAPSULE:
                    entry.getKey().endsWith(".image")?MembershipTransfer.Kind.APPLICATION:MembershipTransfer.Kind.RECORD;
            var content=new MembershipSourceExport.Content(file.digest(),file.bytes(),kind);
            var previous=result.putIfAbsent(file.digest(),content);
            require(previous==null || previous.equals(content),"generation content kind collision");
        }
        return Map.copyOf(result);
    }
    byte[] generationChunk(String digest,long offset,int maximum)throws IOException {
        if(digest.equals(manifest.digest()))return readChunk(path.resolve(MANIFEST),manifestIdentity,offset,maximum);
        var entry=files.entrySet().stream().filter(v->v.getValue().digest().equals(digest)).findFirst()
                .orElseThrow(()->new IllegalArgumentException("current generation content absent"));
        return readChunk(path.resolve(entry.getKey()),entry.getValue(),offset,maximum);
    }
    byte[] ancestryChunk(String digest,long offset,int maximum)throws IOException {
        FileIdentity file;Path source;
        if(digest.equals(manifest.digest())){file=manifestIdentity;source=path.resolve(MANIFEST);}
        else {file=files.get("ancestry.gsr");require(file!=null && file.digest().equals(digest),"current ancestry content absent");source=path.resolve("ancestry.gsr");}
        return readChunk(source,file,offset,maximum);
    }
    byte[] transferChunk(String digest,long offset,int maximum)throws IOException {
        var entry=files.entrySet().stream().filter(v->(v.getKey().equals(PACKET) || v.getKey().endsWith(".image"))
                && v.getValue().digest().equals(digest)).findFirst().orElseThrow(()->new IllegalArgumentException("current content absent"));
        return readChunk(path.resolve(entry.getKey()),entry.getValue(),offset,maximum);
    }
    private static byte[] readChunk(Path source,FileIdentity file,long offset,int maximum)throws IOException {
        require(maximum>0 && maximum<=4*1024*1024 && offset>=0 && offset<file.bytes(),"current chunk bounds");
        checkFile(source,file);var buffer=java.nio.ByteBuffer.allocate((int)Math.min(maximum,file.bytes()-offset));
        try(var channel=MembershipFileAccess.open(source,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)) {
            require(channel.size()==file.bytes(),"current content length");channel.position(offset);
            while(buffer.hasRemaining())require(channel.read(buffer)>0,"current incomplete read");
        }
        checkFile(source,file);return buffer.array();
    }
    private Map<String,byte[]> materialize(MembershipSourcePacket packet) throws IOException {
        var images=new TreeMap<String,byte[]>();
        for(var image:packet.images().entrySet())images.put(image.getKey(),AdmissionPaths.read(path.resolve(image.getKey()+".image"),Math.toIntExact(image.getValue())));
        return images;
    }
    void verifyParents(Collection<MembershipCapsule.Anchor> parents) throws IOException {
        check();capsule.verifyAncestry(ancestry(),parents);check();
    }
    byte[] ancestry()throws IOException {check();return files.containsKey("ancestry.gsr")?AdmissionPaths.read(path.resolve("ancestry.gsr"),96*1024):new byte[0];}
    Optional<byte[]> selectedSources()throws IOException {
        check();return files.containsKey(MembershipSelectedSources.FILE)?Optional.of(AdmissionPaths.read(path.resolve(MembershipSelectedSources.FILE),MembershipSelectedSources.MAXIMUM)):Optional.empty();
    }
    Optional<Decoded> selectedRecord()throws IOException {
        check();return files.containsKey("selected.gsr")?Optional.of(decode(AdmissionPaths.read(path.resolve("selected.gsr"),65536),"records","SELECTED")):Optional.empty();
    }
    Map<String,byte[]> copyFiles() throws IOException {
        check();var result=new TreeMap<String,byte[]>();
        for(var file:files.entrySet())result.put(file.getKey(),AdmissionPaths.read(path.resolve(file.getKey()),Math.toIntExact(file.getValue().bytes())));
        result.put(MANIFEST,manifest.bytes());check();return result;
    }
    Map<String,byte[]> images() throws IOException {check();var images=materialize(capsule.packet);capsule.packet.verifyImages(images);return images;}
    Optional<byte[]> coverage()throws IOException {
        check();return files.containsKey(MembershipSelectionCoverage.FILE)?Optional.of(AdmissionPaths.read(path.resolve(MembershipSelectionCoverage.FILE),MembershipSelectionCoverage.MAXIMUM)):Optional.empty();
    }
    Optional<String> publishedCertificate()throws IOException {
        check();if(!files.containsKey(MembershipSelectionCoverage.FILE))return Optional.empty();
        var coverage=object(parse(AdmissionPaths.read(path.resolve(MembershipSelectionCoverage.FILE),MembershipSelectionCoverage.MAXIMUM),MembershipSelectionCoverage.MAXIMUM));
        return Optional.of((String)coverage.get("certificate"));
    }
    MembershipCapsule.Anchor publishedParent()throws IOException {
        check();require(files.containsKey(MembershipSelectionCoverage.FILE),"published parent requires coverage");
        var coverage=object(parse(AdmissionPaths.read(path.resolve(MembershipSelectionCoverage.FILE),MembershipSelectionCoverage.MAXIMUM),MembershipSelectionCoverage.MAXIMUM));
        var p=object(coverage.get("parent"));return new MembershipCapsule.Anchor(object(p.get("cut")),(String)p.get("catalog"),(String)p.get("application"));
    }
    List<MembershipCapsule.Anchor> publishedAncestors()throws IOException {
        check();require(files.containsKey(MembershipSelectionCoverage.FILE),"published ancestors require coverage");
        return MembershipSelectionCoverage.additionalParents(AdmissionPaths.read(path.resolve(MembershipSelectionCoverage.FILE),MembershipSelectionCoverage.MAXIMUM));
    }
    Optional<Owned> ownedTail() throws IOException {
        check();return accepted==null?Optional.empty():Optional.of(new Owned(identity.nodeId().value(),identity.storageId(),accepted,cutDigest(capsule.context.cut)));
    }
    @Override public void close(){closed=true;leases.forEach(MembershipResources.Lease::close);leases.clear();}
}
