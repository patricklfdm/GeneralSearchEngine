package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Retained original packet and deletion authority. The journal validates semantics before deletion. */
final class MembershipRetirementFiles implements AutoCloseable {
    static final String DIRECTORY="retirement", PROPOSAL="proposal.gsr", AUTHORITY="retirement.gsr", SOURCE="source";
    private final Path parent,path,source;
    private final MembershipResources resources;
    private final MembershipFloorFiles floorFiles;
    private final MembershipBasisSources basisSources;
    private final Map<String,FileIdentity> files=new TreeMap<>();
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private final Map<String,MembershipResources.Lease> parts=new HashMap<>();
    private Object pathKey,sourceKey;
    private boolean exists,sourceExists;
    private String reserved;

    MembershipRetirementFiles(Path parent,MembershipResources resources)throws IOException {
        this(parent,resources,null);
    }
    MembershipRetirementFiles(Path parent,MembershipResources resources,MembershipFloorFiles floorFiles)throws IOException {
        this(parent,resources,floorFiles,null);
    }
    MembershipRetirementFiles(Path parent,MembershipResources resources,MembershipFloorFiles floorFiles,MembershipBasisSources basisSources)throws IOException {
        this.basisSources=basisSources;this.floorFiles=floorFiles;this.parent=parent;this.path=parent.resolve(DIRECTORY);this.source=path.resolve(SOURCE);this.resources=resources;
        try{capture();reserve(null);}catch(IOException | RuntimeException | Error error){close();throw error;}
    }
    boolean pending(){return exists;}
    private static long limit(String name) {
        if(Set.of(PROPOSAL,AUTHORITY,MembershipRetirementImages.FILE).contains(name))return 65536;
        require(name.startsWith("source/"),"retirement retained path");return MembershipGenerationFiles.limit(name.substring(7));
    }
    private FileIdentity captureFile(String name)throws IOException {
        byte[] bytes=AdmissionPaths.read(path.resolve(name),Math.toIntExact(limit(name)));var identity=inspect(path.resolve(name),bytes.length,hash(bytes));files.put(name,identity);return identity;
    }
    private void capture()throws IOException {
        files.clear();exists=Files.exists(path,LinkOption.NOFOLLOW_LINKS);pathKey=exists?key(path):null;sourceExists=false;sourceKey=null;if(!exists)return;
        for(String name:children(path,4)) {
            if(name.equals(SOURCE)) {
                sourceExists=true;sourceKey=key(source);long metadata=0;
                for(String member:children(source,32)) {
                    var file=captureFile(SOURCE+"/"+member);
                    if(!member.endsWith(".image")){metadata=Math.addExact(metadata,file.bytes());require(metadata<=MembershipResources.Unit.SOURCE.bytes,"retirement source metadata capacity");}
                }
            }else{require(Set.of(PROPOSAL,AUTHORITY,MembershipRetirementImages.FILE).contains(name),"retirement unknown authority member");captureFile(name);}
        }
        long saved=0;for(var file:files.entrySet())if(file.getKey().startsWith(SOURCE+"/") && !file.getKey().endsWith(".image") || file.getKey().equals(MembershipRetirementImages.FILE))saved=Math.addExact(saved,file.getValue().bytes());
        require(saved<=MembershipResources.Unit.SOURCE.bytes,"retirement saved metadata capacity");
        require(!files.containsKey(MembershipRetirementImages.FILE) || floorFiles!=null,"borrowed retirement requires floor owner");
    }
    void check()throws IOException {
        require(exists==Files.exists(path,LinkOption.NOFOLLOW_LINKS),"retirement directory changed");if(!exists)return;
        var expected=new TreeSet<String>();for(String name:List.of(PROPOSAL,AUTHORITY,MembershipRetirementImages.FILE))if(files.containsKey(name))expected.add(name);if(sourceExists)expected.add(SOURCE);
        require(pathKey.equals(key(path)) && children(path,4).equals(expected),"retirement inventory changed");
        if(sourceExists) {
            var names=new TreeSet<String>();for(String name:files.keySet())if(name.startsWith(SOURCE+"/"))names.add(name.substring(7));
            require(sourceKey.equals(key(source)) && children(source,32).equals(names),"retirement source directory changed");
        }
        for(var file:files.entrySet())require(file.getValue().equals(inspect(path.resolve(file.getKey()),file.getValue().bytes(),file.getValue().digest())),"retirement file inode changed");
    }
    private void reserve(SortedMap<String,byte[]> plan) {
        if(plan==null && !sourceExists && !files.containsKey(MembershipRetirementImages.FILE))return;
        long metadata=0;var images=new TreeMap<String,Long>();
        if(plan==null)for(var file:files.entrySet())if(file.getKey().startsWith(SOURCE+"/") || file.getKey().equals(MembershipRetirementImages.FILE)) {
            if(file.getKey().endsWith(".image"))images.put(file.getKey(),file.getValue().bytes());else metadata=Math.addExact(metadata,file.getValue().bytes());
        }
        if(plan!=null)for(var file:plan.entrySet())if(file.getKey().startsWith(SOURCE+"/") || file.getKey().equals(MembershipRetirementImages.FILE)) {
            if(file.getKey().endsWith(".image"))images.put(file.getKey(),(long)file.getValue().length);else metadata=Math.addExact(metadata,file.getValue().length);
        }
        var required=new LinkedHashMap<String,MembershipResources.StorageReservation>();
        required.put("metadata",new MembershipResources.StorageReservation(MembershipResources.Unit.SOURCE,"retirement",Math.max(1,metadata)));
        int ordinal=0;for(var image:images.entrySet())required.put(image.getKey(),new MembershipResources.StorageReservation(
                MembershipResources.Unit.APPLICATION,"retirement:"+(ordinal++),Math.max(1,image.getValue())));
        require(required.keySet().containsAll(parts.keySet()),"retirement reservation cannot drop original parts");
        var growth=new LinkedHashMap<MembershipResources.Lease,Long>();var additions=new ArrayList<MembershipResources.StorageReservation>();
        var names=new ArrayList<String>();
        required.forEach((name,row)->{var lease=parts.get(name);
            if(lease==null){names.add(name);additions.add(row);}else growth.put(lease,row.bytes());});
        var acquired=resources.extendSources(growth,additions);
        for(int n=0;n<names.size();n++){var lease=acquired.get(n);parts.put(names.get(n),lease);leases.add(lease);}
        reserved=plan==null?null:hash(plan.get(PROPOSAL));
    }
    Optional<Decoded> authority()throws IOException {
        check();if(!files.containsKey(AUTHORITY))return Optional.empty();byte[] raw=AdmissionPaths.read(path.resolve(AUTHORITY),65536);
        if(files.containsKey(PROPOSAL)) {
            byte[] proposal=AdmissionPaths.read(path.resolve(PROPOSAL),65536);require(prefix(raw,proposal),"retirement differs from original proposal");
            if(raw.length!=proposal.length || raw.length==0)return Optional.empty();
        }
        return Optional.of(decode(raw,"records","RETIREMENT"));
    }
    Map<String,byte[]> original()throws IOException {
        check();require(sourceExists,"retirement original source missing");var result=new TreeMap<String,byte[]>();
        for(String name:files.keySet())if(name.startsWith(SOURCE+"/"))result.put(name.substring(7),AdmissionPaths.read(path.resolve(name),Math.toIntExact(limit(name))));
        if(files.containsKey(MembershipRetirementImages.FILE)) {
            var record=authority().orElseThrow(()->new IllegalArgumentException("retirement borrowed original requires complete authority"));
            result.putAll(borrowed(record));
        }
        check();return result;
    }
    /** The complete retirement decision preserves the original after inactive deletion starts. */
    MembershipCapsule verifiedOriginal(MembershipGrantJournal.HistoryRead owner)throws IOException {
        var record=authority().orElseThrow(()->new IllegalArgumentException("complete retirement authority required for history"));
        var members=original();require(members.containsKey("generation.gsr") && members.containsKey("source.gscp"),"complete retirement history required");
        var manifest=decode(members.get("generation.gsr"),"records","GENERATION");var packet=MembershipSourcePacket.decode(members.get("source.gscp"));
        var images=new TreeMap<String,byte[]>();packet.images().keySet().forEach(h->images.put(h,members.get(h+".image")));
        var copy=new RetainedCopy(this,owner,record,manifest,packet,members);
        try {
            var root=decode(AdmissionPaths.read(parent.resolve("root.gsr"),16384),"records","ROOT");
            var capsule=MembershipCapsule.verifyStored(root,packet,images,copy);
            MembershipFloor.Copy.validateMaterialization(manifest,capsule,owner.identity(),members);copy.check(root,packet);return capsule;
        }finally {copy.active=false;}
    }
    static final class RetainedCopy implements MembershipCapsule.StoredCopy {
        private final MembershipRetirementFiles source;
        private final MembershipGrantJournal.HistoryRead owner;
        private final Decoded authority,manifest;
        private final MembershipSourcePacket packet;
        private final Map<String,byte[]> members;
        private boolean active=true;
        private RetainedCopy(MembershipRetirementFiles source,MembershipGrantJournal.HistoryRead owner,Decoded authority,Decoded manifest,MembershipSourcePacket packet,Map<String,byte[]> members) {
            this.source=source;this.owner=owner;this.authority=authority;this.manifest=manifest;this.packet=packet;this.members=members;
        }
        public void check(Decoded root,MembershipSourcePacket packet)throws IOException {
            require(active,"retirement history expired");owner.generation(manifest);source.check();source.checkSaved(authority);
            require(source.parent.equals(owner.directory()) && root.rootDigest().equals(owner.root().manifestDigest())
                    && authority.value().get("root").equals(root.rootDigest()) && authority.value().get("node").equals(owner.identity().nodeId().value())
                    && Arrays.equals(source.authority().orElseThrow().bytes(),authority.bytes()) && Arrays.equals(this.packet.bytes(),packet.bytes()),"retirement history binding");
        }
        public byte[] ancestry(){require(active,"retirement history expired");return members.getOrDefault("ancestry.gsr",new byte[0]).clone();}
        public Optional<byte[]> coverage(){require(active,"retirement history expired");return Optional.ofNullable(members.get(MembershipSelectionCoverage.FILE)).map(byte[]::clone);}
        public Decoded record(String name,String kind) {
            require(active && Set.of("promise.gsr","selected.gsr").contains(name) && members.containsKey(name),"retirement history record scope");return decode(members.get(name),"records",kind);
        }
    }
    private Map<String,byte[]> borrowed(Decoded record)throws IOException {
        require(floorFiles!=null,"retirement borrowed floor owner absent");
        var floor=floorFiles.retained().orElseThrow(()->new IllegalArgumentException("retirement borrowed floor unavailable"));
        byte[] binding=AdmissionPaths.read(path.resolve(MembershipRetirementImages.FILE),MembershipRetirementImages.MAXIMUM);
        return sourceBinding(binding)?MembershipRetirementSourceImages.resolve(binding,record,floor,basisSources):MembershipRetirementImages.resolve(binding,record,floor);
    }
    private static boolean sourceBinding(byte[] binding) {
        return MembershipRetirementSourceImages.SCHEMA.equals(object(parse(binding,MembershipRetirementImages.MAXIMUM)).get("schema"));
    }
    private void resealBacking(Decoded record,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        borrowed(record);var floor=floorFiles.retained().orElseThrow();
        if(sourceBinding(AdmissionPaths.read(path.resolve(MembershipRetirementImages.FILE),MembershipRetirementImages.MAXIMUM))) {
            basisSources.resealOriginal(MembershipRetirementSourceImages.basis(record,floor),owner);
            cut.at("RETIREMENT_BORROWED_SOURCE_FORCED");check();owner.check();borrowed(record);
        }
        floorFiles.resealForRetirement(owner,cut);
    }
    /** Check every remaining saved byte against the already-bound retirement inventory. */
    void checkSaved(Decoded record)throws IOException {
        check();var expected=new TreeMap<String,Map<String,Object>>();
        for(Object row:list(record.value().get("files"))){var file=object(row);String name=(String)file.get("path");expected.put(SOURCE+"/"+name.substring(name.lastIndexOf('/')+1),file);}
        for(var file:files.entrySet())if(file.getKey().startsWith(SOURCE+"/")) {
            var original=expected.get(file.getKey());require(original!=null && file.getValue().bytes()==number(original.get("size")) && file.getValue().digest().equals(original.get("sha256")),"retirement saved bytes changed");
        }
        if(files.containsKey(MembershipRetirementImages.FILE)) {
            require(files.keySet().stream().noneMatch(n->n.startsWith(SOURCE+"/") && n.endsWith(".image")),"borrowed retirement cannot mix physical backup images");borrowed(record);
        }
        if(files.containsKey(PROPOSAL))require(Arrays.equals(AdmissionPaths.read(path.resolve(PROPOSAL),65536),record.bytes()),"retirement proposal binding");
    }
    void sealAuthority(Decoded record,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        checkSaved(record);owner.check();if(files.containsKey(MembershipRetirementImages.FILE))resealBacking(record,owner,cut);force(path.resolve(AUTHORITY));AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(parent);
        cut.at("RETIREMENT_AUTHORITY_RESEALED");check();owner.check();
    }
    void prepare(MembershipRetirementPlan retirement,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        var plan=new TreeMap<String,byte[]>();plan.put(PROPOSAL,retirement.record.bytes());plan.put(AUTHORITY,retirement.record.bytes());
        long imageCount=retirement.original.fileNames().stream().filter(n->n.endsWith(".image")).count();
        boolean borrow=files.containsKey(MembershipRetirementImages.FILE) || files.isEmpty() && !sourceExists
                && resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)+imageCount>MembershipResources.Unit.APPLICATION.count;
        if(borrow) {
            require(floorFiles!=null,"retirement image capacity requires retained floor owner");
            var floor=floorFiles.retained().orElseThrow(()->new IllegalArgumentException("retirement image capacity requires complete floor"));
            var local=MembershipRetirementImages.local(retirement.record,floor);local.check();
            boolean localImages=retirement.original.fileNames().stream().filter(n->n.endsWith(".image")).allMatch(local.fileNames()::contains);
            plan.put(MembershipRetirementImages.FILE,!localImages && basisSources!=null
                    ?MembershipRetirementSourceImages.create(retirement.record,floor,basisSources):MembershipRetirementImages.create(retirement.record,floor));
        }
        for(String name:retirement.original.fileNames())if(!borrow || !name.endsWith(".image"))plan.put(SOURCE+"/"+name,retirement.original.fileBytes(name));
        check();owner.check();require(plan.keySet().containsAll(files.keySet()),"unrelated retained retirement files");
        for(String name:files.keySet())require(prefix(AdmissionPaths.read(path.resolve(name),Math.toIntExact(limit(name))),plan.get(name)),"retirement requires exact original proposal");
        if(!retirement.record.digest().equals(reserved))reserve(plan);cut.at("RETIREMENT_RESERVED");check();owner.check();
        if(!exists){Files.createDirectory(path);capture();}cut.at("RETIREMENT_CREATED");check();owner.check();
        if(borrow)complete(MembershipRetirementImages.FILE,plan.get(MembershipRetirementImages.FILE),owner,cut,"RETIREMENT_BORROW");
        complete(PROPOSAL,plan.get(PROPOSAL),owner,cut,"RETIREMENT_PROPOSAL");
        if(!sourceExists){Files.createDirectory(source);capture();}cut.at("RETIREMENT_SOURCE_CREATED");check();owner.check();
        complete(SOURCE+"/generation.gsr",plan.get(SOURCE+"/generation.gsr"),owner,cut,"RETIREMENT_MANIFEST");
        for(var file:plan.entrySet())if(file.getKey().startsWith(SOURCE+"/") && !file.getKey().equals(SOURCE+"/generation.gsr"))
            complete(file.getKey(),file.getValue(),owner,cut,file.getKey().endsWith(".image")?"RETIREMENT_IMAGE":"RETIREMENT_MEMBER");
        AdmissionPaths.forceDirectory(source);AdmissionPaths.forceDirectory(path);cut.at("RETIREMENT_SOURCE_FORCED");check();owner.check();
        if(borrow)resealBacking(retirement.record,owner,cut);
        complete(AUTHORITY,plan.get(AUTHORITY),owner,cut,"RETIREMENT_AUTHORITY");
        AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(parent);cut.at("RETIREMENT_PARENT_FORCED");check();owner.check();
    }
    void clearAfterDeletion(Decoded record,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        checkSaved(record);owner.check();
        for(String name:new TreeSet<>(files.keySet()))if(name.startsWith(SOURCE+"/")) {
            check();owner.check();Files.delete(path.resolve(name));capture();AdmissionPaths.forceDirectory(source);cut.at("RETIREMENT_SAVED_FILE_DELETED");check();owner.check();
        }
        if(sourceExists){Files.delete(source);capture();AdmissionPaths.forceDirectory(path);cut.at("RETIREMENT_SAVED_DIRECTORY_DELETED");check();owner.check();}
        if(files.containsKey(PROPOSAL)){Files.delete(path.resolve(PROPOSAL));capture();AdmissionPaths.forceDirectory(path);cut.at("RETIREMENT_PROPOSAL_CLEARED");check();owner.check();}
        if(files.containsKey(MembershipRetirementImages.FILE)){Files.delete(path.resolve(MembershipRetirementImages.FILE));capture();AdmissionPaths.forceDirectory(path);cut.at("RETIREMENT_BORROW_CLEARED");check();owner.check();}
        require(files.keySet().equals(Set.of(AUTHORITY)),"retirement authority must clear last");
        Files.delete(path.resolve(AUTHORITY));capture();AdmissionPaths.forceDirectory(path);cut.at("RETIREMENT_AUTHORITY_CLEARED");check();owner.check();
        clearEmpty(owner,cut);
    }
    void clearEmpty(MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        check();require(exists && !sourceExists && files.isEmpty(),"retirement still owns files");owner.check();
        Files.delete(path);capture();AdmissionPaths.forceDirectory(parent);cut.at("RETIREMENT_CLEARED");owner.check();check();close();
    }
    boolean empty(){return exists && !sourceExists && files.isEmpty();}
    private void complete(String name,byte[] bytes,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut,String event)throws IOException {
        check();owner.check();Path file=path.resolve(name);
        if(Files.exists(file,LinkOption.NOFOLLOW_LINKS))require(prefix(AdmissionPaths.read(file,bytes.length),bytes),"retirement member changed from exact prefix");
        try(var channel=MembershipFileAccess.open(file,StandardOpenOption.CREATE,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            channel.position(channel.size());
            if(name.equals(MembershipRetirementImages.FILE)) {
                int offset=Math.toIntExact(channel.size()),middle=offset+(bytes.length-offset)/2;
                AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,offset,middle));capture();cut.at("RETIREMENT_BORROW_PREFIX_WRITTEN");check();owner.check();
            }
            AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,Math.toIntExact(channel.size()),bytes.length));capture();
            cut.at(event+"_WRITTEN");check();owner.check();channel.force(true);cut.at(event+"_FORCED");check();owner.check();
        }
        AdmissionPaths.exact(file,bytes);capture();
    }
    private static boolean prefix(byte[] actual,byte[] expected){return actual.length<=expected.length && Arrays.equals(actual,Arrays.copyOf(expected,actual.length));}
    @Override public void close(){leases.forEach(MembershipResources.Lease::close);leases.clear();parts.clear();reserved=null;}
}
