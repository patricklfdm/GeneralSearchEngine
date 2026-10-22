package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One retained governing floor; explicit release relinquishes authority before bounded cleanup. */
final class MembershipFloorFiles implements AutoCloseable {
    static final String DIRECTORY="floor-copies", PROPOSAL="proposal.gsr", FLOOR="floor.gsr", RELEASE="release.gsr";
    private final Path parent,path;
    private final MembershipRoot root;
    private final MembershipIdentity local;
    private final MembershipResources resources;
    private final MembershipCurrentGeneration.Verifier verifier;
    private final boolean releaseEnabled;
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private final Map<String,FileIdentity> files=new TreeMap<>();
    private final Map<String,Object> directories=new TreeMap<>();
    private Object pathKey;
    private boolean exists;
    private String reserved;

    MembershipFloorFiles(Path parent,MembershipRoot root,MembershipIdentity local,MembershipResources resources,
            MembershipCurrentGeneration.Verifier verifier) throws IOException {
        this(parent,root,local,resources,verifier,false);
    }
    MembershipFloorFiles(Path parent,MembershipRoot root,MembershipIdentity local,MembershipResources resources,
            MembershipCurrentGeneration.Verifier verifier,boolean releaseEnabled) throws IOException {
        this.parent=parent;path=parent.resolve(DIRECTORY);this.root=root;this.local=local;this.resources=resources;this.verifier=verifier;this.releaseEnabled=releaseEnabled;
        try{capture();reserve(null);if(!releasing() && complete()) {
            read();
            for(String name:files.keySet())if(!name.equals(FLOOR))force(path.resolve(name));
            for(String name:directories.keySet())AdmissionPaths.forceDirectory(path.resolve(name));
            AdmissionPaths.forceDirectory(path);force(path.resolve(FLOOR));AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(parent);check();
        }}catch(IOException | RuntimeException | Error error){close();throw error;}
    }
    boolean pending() throws IOException{return exists && (releasing() || !complete());}
    boolean releasing(){return files.containsKey(RELEASE);}
    boolean exists(){return exists;}
    private static long limit(String name) {
        if(name.equals(RELEASE))return 65536;
        if(Set.of(PROPOSAL,FLOOR).contains(name))return 16384;
        String[] parts=name.split("/",-1);require(parts.length==2 && parts[0].matches("[0-9a-f]{64}"),"floor retained path");
        return MembershipGenerationFiles.limit(parts[1]);
    }
    private void capture() throws IOException {
        files.clear();directories.clear();exists=Files.exists(path,LinkOption.NOFOLLOW_LINKS);pathKey=exists?key(path):null;if(!exists)return;
        long total=0;
        for(String name:children(path,9)) {
            Path member=path.resolve(name);
            if(Set.of(PROPOSAL,FLOOR).contains(name) || releaseEnabled && name.equals(RELEASE))captureFile(name);
            else {
                require(name.matches("[0-9a-f]{64}") && directories.size()<6,"floor copy directory count/name");directories.put(name,key(member));long metadata=0;
                for(String file:children(member,32)) {
                    var captured=captureFile(name+"/"+file);
                    if(!file.endsWith(".image")){metadata=Math.addExact(metadata,captured.bytes());require(metadata<=MembershipResources.Unit.SOURCE.bytes,"floor retained metadata capacity");}
                }
                total=Math.addExact(total,metadata);
            }
        }
        require(total<=6*MembershipResources.Unit.SOURCE.bytes,"floor retained total capacity");
    }
    private FileIdentity captureFile(String name) throws IOException {
        byte[] bytes=AdmissionPaths.read(path.resolve(name),Math.toIntExact(limit(name)));var identity=inspect(path.resolve(name),bytes.length,hash(bytes));files.put(name,identity);return identity;
    }
    void check() throws IOException {
        require(exists==Files.exists(path,LinkOption.NOFOLLOW_LINKS),"floor directory changed");if(!exists)return;
        var expected=new TreeSet<>(directories.keySet());for(String name:List.of(PROPOSAL,FLOOR,RELEASE))if(files.containsKey(name))expected.add(name);
        require(pathKey.equals(key(path)) && children(path,9).equals(expected),"floor inventory changed");
        for(var directory:directories.entrySet()) {
            String prefix=directory.getKey()+"/";var names=new TreeSet<String>();for(String name:files.keySet())if(name.startsWith(prefix))names.add(name.substring(prefix.length()));
            require(directory.getValue().equals(key(path.resolve(directory.getKey()))) && children(path.resolve(directory.getKey()),32).equals(names),"floor source directory changed");
        }
        for(var file:files.entrySet())require(file.getValue().equals(inspect(path.resolve(file.getKey()),file.getValue().bytes(),file.getValue().digest())),"floor file inode changed");
    }
    private void reserve(SortedMap<String,byte[]> plan) {
        close();if(!exists && plan==null)return;
        try {
            Set<String> ids=new TreeSet<>();if(plan==null)ids.addAll(directories.keySet());else for(String name:plan.keySet())if(name.contains("/"))ids.add(name.substring(0,name.indexOf('/')));
            for(String id:ids) {
                long metadata=0;var images=new TreeMap<String,Long>();String prefix=id+"/";
                if(plan==null)for(var file:files.entrySet())if(file.getKey().startsWith(prefix)) {
                    if(file.getKey().endsWith(".image"))images.put(file.getKey(),file.getValue().bytes());else metadata=Math.addExact(metadata,file.getValue().bytes());
                }
                if(plan!=null)for(var file:plan.entrySet())if(file.getKey().startsWith(prefix)) {
                    if(file.getKey().endsWith(".image"))images.put(file.getKey(),(long)file.getValue().length);else metadata=Math.addExact(metadata,file.getValue().length);
                }
                leases.add(resources.reserve(MembershipResources.Unit.SOURCE,"floor:"+id,Math.max(1,metadata)));
                // The digest identifies the copy as well as the image; duplicates on disk
                // still consume separate reservations. Never alias original BASIS leases.
                int ordinal=0;for(var image:images.entrySet())leases.add(resources.reserve(MembershipResources.Unit.APPLICATION,"floor:"+id+":"+(ordinal++),Math.max(1,image.getValue())));
            }
            reserved=plan==null?null:hash(plan.get(PROPOSAL));
        }catch(RuntimeException | Error error){close();throw error;}
    }
    private boolean complete() throws IOException {
        if(!files.containsKey(FLOOR))return false;
        require(files.containsKey(PROPOSAL),"floor has no original proposal");
        byte[] proposed=AdmissionPaths.read(path.resolve(PROPOSAL),16384),actual=AdmissionPaths.read(path.resolve(FLOOR),16384);
        require(prefix(actual,proposed),"floor differs from original proposal");
        return actual.length==proposed.length && actual.length>0;
    }
    private Decoded bound(byte[] bytes) {
        var floor=decode(bytes,"records","FLOOR");require(floor.value().get("root").equals(root.manifestDigest()) && floor.value().get("node").equals(local.nodeId().value()),"retained floor root/owner");return floor;
    }
    record Retained(Decoded floor,List<MembershipFloor.Copy> copies) {}
    Optional<Decoded> read() throws IOException {return retained().map(Retained::floor);}
    Optional<Retained> retained() throws IOException {check();return releasing()?Optional.empty():retainedOriginal();}
    private Optional<Retained> retainedOriginal() throws IOException {
        check();if(!complete())return Optional.empty();var floor=bound(AdmissionPaths.read(path.resolve(FLOOR),16384));
        var copies=new ArrayList<MembershipFloor.Copy>();var expected=new TreeSet<String>(Set.of(PROPOSAL,FLOOR));if(releasing())expected.add(RELEASE);
        var rootBytes=decode(AdmissionPaths.read(parent.resolve("root.gsr"),16384),"records","ROOT");MembershipFloor.Copy own=null;
        for(Object row:list(floor.value().get("sources"))) {
            var ref=object(row);String id=(String)ref.get("generation");String prefix=id+"/";var members=new TreeMap<String,byte[]>();
            for(String name:files.keySet())if(name.startsWith(prefix)){expected.add(name);members.put(name.substring(prefix.length()),AdmissionPaths.read(path.resolve(name),Math.toIntExact(limit(name))));}
            require(members.containsKey("generation.gsr") && members.containsKey(PACKET),"retained floor copy absent");
            var generation=decode(members.get("generation.gsr"),"records","GENERATION");require(generation.digest().equals(id),"retained floor generation digest");
            var packet=MembershipSourcePacket.decode(members.get(PACKET));var images=new TreeMap<String,byte[]>();packet.images().keySet().forEach(h->images.put(h,members.get(h+".image")));
            var capsule=Objects.requireNonNull(verifier.verify(rootBytes,packet,images));require(Arrays.equals(capsule.packet.bytes(),packet.bytes()),"floor verifier substituted source");
            String voter=(String)ref.get("voter");var owner=capsule.context.identities.get(voter);require(owner!=null,"retained floor unknown identity");
            // The forced FLOOR remembers the admitted copy observation. Reopen checks its
            // original full bytes, never invents a new remote ACK or eligible vote.
            var remembered=new Owned(voter,owner.storageId(),id,cutDigest(capsule.context.cut));
            var copy=MembershipFloor.Copy.verify(generation,capsule,owner,Set.of(remembered),members);
            require(copy.reference().equals(ref),"retained floor source binding");copies.add(copy);if(voter.equals(local.nodeId().value()))own=copy;
        }
        require(expected.equals(files.keySet()) && directories.size()==copies.size() && own!=null,"retained floor inventory/owner");
        MembershipFloor.verify(floor,root,own,copies);check();return Optional.of(new Retained(floor,List.copyOf(copies)));
    }
    Decoded establish(MembershipFloor.Copy current,List<MembershipFloor.Copy> offered,
            MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut) throws IOException {
        require(!releasing(),"pending floor release must finish before new floor");var floor=MembershipFloor.create(root,current,offered);require(current.owner.equals(local),"floor publication owner");
        var plan=new TreeMap<String,byte[]>();plan.put(PROPOSAL,floor.bytes());plan.put(FLOOR,floor.bytes());
        for(var copy:offered)for(String name:copy.fileNames())plan.put(copy.generation.digest()+"/"+name,copy.fileBytes(name));
        check();owner.check();require(plan.keySet().containsAll(files.keySet()),"unrelated retained floor files");
        for(var file:files.entrySet())require(prefix(AdmissionPaths.read(path.resolve(file.getKey()),Math.toIntExact(limit(file.getKey()))),plan.get(file.getKey())),"floor requires exact original proposal");
        var ids=new TreeSet<String>();for(var copy:offered)ids.add(copy.generation.digest());require(ids.containsAll(directories.keySet()),"unrelated retained floor directory");
        if(!floor.digest().equals(reserved))reserve(plan);cut.at("FLOOR_RESERVED");check();owner.check();
        if(!exists){Files.createDirectory(path);capture();}cut.at("FLOOR_DIRECTORY_CREATED");check();owner.check();
        completeFile(PROPOSAL,plan.get(PROPOSAL),owner,cut,"FLOOR_PROPOSAL");
        for(String id:ids) {
            if(!directories.containsKey(id)){Files.createDirectory(path.resolve(id));capture();}cut.at("FLOOR_COPY_CREATED");check();owner.check();
            completeFile(id+"/generation.gsr",plan.get(id+"/generation.gsr"),owner,cut,"FLOOR_MANIFEST");
            for(var file:plan.entrySet())if(file.getKey().startsWith(id+"/") && !file.getKey().endsWith("/generation.gsr"))
                completeFile(file.getKey(),file.getValue(),owner,cut,file.getKey().endsWith(".image")?"FLOOR_IMAGE":"FLOOR_MEMBER");
            AdmissionPaths.forceDirectory(path.resolve(id));cut.at("FLOOR_COPY_DIRECTORY_FORCED");check();owner.check();
        }
        AdmissionPaths.forceDirectory(path);cut.at("FLOOR_COPIES_FORCED");check();owner.check();
        completeFile(FLOOR,plan.get(FLOOR),owner,cut,"FLOOR_AUTHORITY");
        AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(parent);cut.at("FLOOR_PARENT_FORCED");check();owner.check();
        var retained=read().orElseThrow();require(Arrays.equals(retained.bytes(),floor.bytes()),"floor publication bytes changed");cut.at("FLOOR_BEFORE_RETURN");check();owner.check();return floor;
    }
    /** Exact cleanup authority; never reconstruct a floor from partially deleted copies. */
    private Decoded releasePlan(MembershipCurrentGeneration current,Retained retained) throws IOException {
        current.check();var own=retained.copies().stream().filter(c->c.owner.equals(local)).findFirst().orElseThrow();
        current.verifyParents(List.of(own.capsule.terminal()));
        if(own.generation.value().get("ownedTail")!=null) {
            var accept=decode(own.fileBytes("owned-tail.gsr"),"records","ACCEPT");
            if(number(accept.value().get("index"))>number(object(retained.floor().value().get("cut")).get("index"))) {
                var entry=decode(own.capsule.packet.objectBytes((String)accept.value().get("entry")),"records","ENTRY");
                for(String digest:List.of(accept.digest(),entry.digest(),(String)entry.value().get("payload")))
                    require(Arrays.equals(own.capsule.packet.objectBytes(digest),current.capsule.packet.objectBytes(digest)),"floor release loses original above-floor bytes");
                if(number(accept.value().get("index"))>number(current.capsule.context.cut.get("index")))
                    require(accept.digest().equals(current.manifest.value().get("ownedTail")),"floor release loses unresolved ownership");
            }
        }
        var inventory=new ArrayList<Map<String,Object>>();
        for(var file:files.entrySet())if(!file.getKey().equals(RELEASE))inventory.add(Map.of("path",DIRECTORY+"/"+file.getKey(),"size",file.getValue().bytes(),"sha256",file.getValue().digest()));
        return decode(encode("records","RETIREMENT",Map.of("root",root.manifestDigest(),"node",local.nodeId().value(),
                "floor",retained.floor().digest(),"selector",current.selector.digest(),"files",inventory)),"records","RETIREMENT");
    }
    private void validateRelease(Decoded record,MembershipCurrentGeneration current) throws IOException {
        check();current.check();var value=record.value();
        require(value.get("root").equals(root.manifestDigest()) && value.get("node").equals(local.nodeId().value())
                && value.get("selector").equals(current.selector.digest()),"floor release authority context changed");
        var expected=new TreeMap<String,Map<String,Object>>();var ids=new TreeSet<String>();String previous=null;long metadata=0;int images=0;
        for(Object row:list(value.get("files"))) {
            var file=object(row);String full=(String)file.get("path");
            require(full.startsWith(DIRECTORY+"/") && (previous==null || previous.compareTo(full)<0),"floor release inventory path/order");previous=full;
            String name=full.substring(DIRECTORY.length()+1);require(!name.equals(RELEASE),"floor release cannot list itself");
            long size=number(file.get("size"));require(size>0 && size<=limit(name),"floor release inventory capacity");expected.put(name,file);
            if(name.contains("/"))ids.add(name.substring(0,name.indexOf('/')));
            if(name.endsWith(".image")){images++;require(name.endsWith("/"+file.get("sha256")+".image"),"floor release image binding");}
            else metadata=Math.addExact(metadata,size);
        }
        require(expected.containsKey(FLOOR) && expected.containsKey(PROPOSAL) && ids.size()>=2 && ids.size()<=6
                && images<=7 && metadata<=6*MembershipResources.Unit.SOURCE.bytes+32768,"floor release complete inventory");
        require(expected.get(FLOOR).get("sha256").equals(value.get("floor")) && expected.get(PROPOSAL).equals(Map.of("path",DIRECTORY+"/"+PROPOSAL,
                "size",expected.get(FLOOR).get("size"),"sha256",value.get("floor"))),"floor release original authority binding");
        for(String id:ids)require(expected.containsKey(id+"/generation.gsr") && expected.containsKey(id+"/source.gscp") && expected.containsKey(id+"/promise.gsr"),"floor release complete source inventory");
        require(ids.containsAll(directories.keySet()),"floor release unlisted directory");
        for(var file:files.entrySet())if(!file.getKey().equals(RELEASE)) {
            var wanted=expected.get(file.getKey());require(wanted!=null && number(wanted.get("size"))==file.getValue().bytes()
                    && wanted.get("sha256").equals(file.getValue().digest()),"floor release remaining bytes changed");
        }
        if(releasing())require(prefix(AdmissionPaths.read(path.resolve(RELEASE),65536),record.bytes()),"floor release requires exact original decision");
    }
    void release(MembershipCurrentGeneration current,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut) throws IOException {
        require(releaseEnabled,"floor release owner required");check();owner.check();if(!exists)return;
        if(files.isEmpty() && directories.isEmpty()){clearReleased(owner,cut);return;}
        Decoded record;
        if(files.containsKey(FLOOR)) {
            var retained=retainedOriginal().orElseThrow(()->new IllegalArgumentException("complete floor required before release"));record=releasePlan(current,retained);
        }else {
            require(releasing(),"incomplete floor cannot be released");record=decode(AdmissionPaths.read(path.resolve(RELEASE),65536),"records","RETIREMENT");
        }
        validateRelease(record,current);owner.check();
        // Also reseal an existing complete authority before resuming any deletion.
        completeFile(RELEASE,record.bytes(),owner,cut,"FLOOR_RELEASE_AUTHORITY");
        AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(parent);cut.at("FLOOR_RELEASE_PARENT_FORCED");validateRelease(record,current);owner.check();
        if(files.containsKey(FLOOR))deleteReleased(FLOOR,record,current,owner,cut,"FLOOR_RELEASE_RELINQUISHED");
        for(String name:new TreeSet<>(files.keySet()))if(name.contains("/"))deleteReleased(name,record,current,owner,cut,"FLOOR_RELEASE_FILE_DELETED");
        for(String name:new TreeSet<>(directories.keySet())) {
            validateRelease(record,current);owner.check();require(children(path.resolve(name),32).isEmpty(),"floor release source not empty");
            Files.delete(path.resolve(name));capture();AdmissionPaths.forceDirectory(path);cut.at("FLOOR_RELEASE_COPY_DELETED");validateRelease(record,current);owner.check();
        }
        if(files.containsKey(PROPOSAL))deleteReleased(PROPOSAL,record,current,owner,cut,"FLOOR_RELEASE_PROPOSAL_CLEARED");
        require(files.keySet().equals(Set.of(RELEASE)) && directories.isEmpty(),"floor release authority must clear last");
        validateRelease(record,current);owner.check();Files.delete(path.resolve(RELEASE));capture();AdmissionPaths.forceDirectory(path);
        cut.at("FLOOR_RELEASE_AUTHORITY_CLEARED");check();owner.check();clearReleased(owner,cut);
    }
    private void deleteReleased(String name,Decoded record,MembershipCurrentGeneration current,MembershipGenerationFiles.Guard owner,
            MembershipBallotAllocator.Cut cut,String event)throws IOException {
        validateRelease(record,current);owner.check();Files.delete(path.resolve(name));capture();AdmissionPaths.forceDirectory(path.resolve(name).getParent());
        cut.at(event);validateRelease(record,current);owner.check();
    }
    private void clearReleased(MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        check();owner.check();require(files.isEmpty() && directories.isEmpty(),"floor release still owns bytes");
        Files.delete(path);capture();AdmissionPaths.forceDirectory(parent);cut.at("FLOOR_RELEASE_CLEARED");check();owner.check();close();
    }

    private void completeFile(String name,byte[] bytes,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut,String event) throws IOException {
        check();owner.check();Path file=path.resolve(name);
        if(Files.exists(file,LinkOption.NOFOLLOW_LINKS))require(prefix(AdmissionPaths.read(file,bytes.length),bytes),"floor member changed from exact prefix");
        boolean creating=name.equals(RELEASE) && !Files.exists(file,LinkOption.NOFOLLOW_LINKS);
        try(var channel=FileChannel.open(file,StandardOpenOption.CREATE,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            if(creating){capture();cut.at("FLOOR_RELEASE_AUTHORITY_CREATED");check();owner.check();}
            channel.position(channel.size());AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,Math.toIntExact(channel.size()),bytes.length));capture();
            cut.at(event+"_WRITTEN");check();owner.check();channel.force(true);cut.at(event+"_FORCED");check();owner.check();
        }
        AdmissionPaths.exact(file,bytes);capture();
    }
    private static boolean prefix(byte[] actual,byte[] expected){return actual.length<=expected.length && Arrays.equals(actual,Arrays.copyOf(expected,actual.length));}
    @Override public void close(){leases.forEach(MembershipResources.Lease::close);leases.clear();reserved=null;}
}
