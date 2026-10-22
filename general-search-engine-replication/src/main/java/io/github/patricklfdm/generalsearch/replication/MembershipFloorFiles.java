package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One retained governing floor. Full copies precede its authority file; no deletion or rotation. */
final class MembershipFloorFiles implements AutoCloseable {
    static final String DIRECTORY="floor-copies", PROPOSAL="proposal.gsr", FLOOR="floor.gsr";
    private final Path parent,path;
    private final MembershipRoot root;
    private final MembershipIdentity local;
    private final MembershipResources resources;
    private final MembershipCurrentGeneration.Verifier verifier;
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private final Map<String,FileIdentity> files=new TreeMap<>();
    private final Map<String,Object> directories=new TreeMap<>();
    private Object pathKey;
    private boolean exists;
    private String reserved;

    MembershipFloorFiles(Path parent,MembershipRoot root,MembershipIdentity local,MembershipResources resources,
            MembershipCurrentGeneration.Verifier verifier) throws IOException {
        this.parent=parent;path=parent.resolve(DIRECTORY);this.root=root;this.local=local;this.resources=resources;this.verifier=verifier;
        try{capture();reserve(null);if(complete()) {
            read();
            for(String name:files.keySet())if(!name.equals(FLOOR))force(path.resolve(name));
            for(String name:directories.keySet())AdmissionPaths.forceDirectory(path.resolve(name));
            AdmissionPaths.forceDirectory(path);force(path.resolve(FLOOR));AdmissionPaths.forceDirectory(path);AdmissionPaths.forceDirectory(parent);check();
        }}catch(IOException | RuntimeException | Error error){close();throw error;}
    }
    boolean pending() throws IOException{return exists && !complete();}
    private static long limit(String name) {
        if(Set.of(PROPOSAL,FLOOR).contains(name))return 16384;
        String[] parts=name.split("/",-1);require(parts.length==2 && parts[0].matches("[0-9a-f]{64}"),"floor retained path");
        return MembershipGenerationFiles.limit(parts[1]);
    }
    private void capture() throws IOException {
        files.clear();directories.clear();exists=Files.exists(path,LinkOption.NOFOLLOW_LINKS);pathKey=exists?key(path):null;if(!exists)return;
        long total=0;
        for(String name:children(path,8)) {
            Path member=path.resolve(name);
            if(Set.of(PROPOSAL,FLOOR).contains(name))captureFile(name);
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
        var expected=new TreeSet<>(directories.keySet());for(String name:List.of(PROPOSAL,FLOOR))if(files.containsKey(name))expected.add(name);
        require(pathKey.equals(key(path)) && children(path,8).equals(expected),"floor inventory changed");
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
    Optional<Retained> retained() throws IOException {
        check();if(!complete())return Optional.empty();var floor=bound(AdmissionPaths.read(path.resolve(FLOOR),16384));
        var copies=new ArrayList<MembershipFloor.Copy>();var expected=new TreeSet<String>(Set.of(PROPOSAL,FLOOR));
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
        var floor=MembershipFloor.create(root,current,offered);require(current.owner.equals(local),"floor publication owner");
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
    private void completeFile(String name,byte[] bytes,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut,String event) throws IOException {
        check();owner.check();Path file=path.resolve(name);
        if(Files.exists(file,LinkOption.NOFOLLOW_LINKS))require(prefix(AdmissionPaths.read(file,bytes.length),bytes),"floor member changed from exact prefix");
        try(var channel=FileChannel.open(file,StandardOpenOption.CREATE,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            channel.position(channel.size());AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,Math.toIntExact(channel.size()),bytes.length));capture();
            cut.at(event+"_WRITTEN");check();owner.check();channel.force(true);cut.at(event+"_FORCED");check();owner.check();
        }
        AdmissionPaths.exact(file,bytes);capture();
    }
    private static boolean prefix(byte[] actual,byte[] expected){return actual.length<=expected.length && Arrays.equals(actual,Arrays.copyOf(expected,actual.length));}
    @Override public void close(){leases.forEach(MembershipResources.Lease::close);leases.clear();reserved=null;}
}
