package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Immutable local bytes for original grants, under the journal's exclusive owner.
 * Does not establish remote owned observations or authorize a public vote. */
final class MembershipBasisSources implements AutoCloseable {
    static final String DIRECTORY="sources", PACKET="source.gscp";
    private final Path directory;
    private final Object directoryKey;
    private final byte[] root;
    private final MembershipResources resources;
    private final MembershipBallotAllocator.Cut cut;
    private final Map<String,Map<String,FileIdentity>> retained=new TreeMap<>();
    private final Map<String,Object> subdirectories=new TreeMap<>();
    private final List<MembershipResources.Lease> leases=new ArrayList<>();
    private final Map<String,List<MembershipResources.Lease>> sourceLeases=new TreeMap<>();
    record FileIdentity(Object key,long bytes,String digest) {}

    MembershipBasisSources(Path parent,MembershipResources resources,MembershipBallotAllocator.Cut cut,
            Map<String,Decoded> promises,Map<String,Decoded> bases) throws IOException {
        this(parent,resources,cut,promises,bases,null);
    }
    MembershipBasisSources(Path parent,MembershipResources resources,MembershipBallotAllocator.Cut cut,
            Map<String,Decoded> promises,Map<String,Decoded> bases,MembershipSourceRetirementFiles.Decision retiring) throws IOException {
        this(parent,resources,cut,promises,bases,retiring,null);
    }
    MembershipBasisSources(Path parent,MembershipResources resources,MembershipBallotAllocator.Cut cut,
            Map<String,Decoded> promises,Map<String,Decoded> bases,MembershipSourceRetirementFiles.Decision retiring,
            MembershipCaptureFiles.Plan capture)throws IOException {
        directory=parent.resolve(DIRECTORY);this.resources=resources;this.cut=cut;
        root=AdmissionPaths.read(parent.resolve("root.gsr"),16384);directoryKey=key(directory);
        try {
            leases.add(resources.reserve(MembershipResources.Unit.JOURNAL,"membership-grants",MembershipGrantJournal.MAXIMUM));
            Set<String> ids=children(directory,6);
            var allowed=new HashSet<>(promises.keySet());if(retiring!=null)allowed.add(retiring.id());
            require(allowed.containsAll(ids) && ids.containsAll(bases.keySet())
                    && (retiring==null || !promises.containsKey(retiring.id()) || ids.contains(retiring.id())),"missing or unbound original source");
            for(String id:ids) {
                Path path=directory.resolve(id);
                if(retiring!=null && id.equals(retiring.id()) && !promises.containsKey(id)) {
                    var expected=retirementInventory(retiring);var actual=new TreeMap<String,FileIdentity>();
                    require(expected.keySet().containsAll(children(path,8)),"source retirement unlisted member");
                    for(String name:children(path,8)){var item=expected.get(name);actual.put(name,inspect(path.resolve(name),number(item.get("size")),(String)item.get("sha256")));}
                    var images=new TreeMap<String,Long>();for(var file:expected.entrySet())if(file.getKey().endsWith(".image"))images.put((String)file.getValue().get("sha256"),number(file.getValue().get("size")));
                    retainLeases(id,reserve(id,number(expected.get(PACKET).get("size")),images));retained.put(id,Map.copyOf(actual));subdirectories.put(id,key(path));continue;
                }
                if(capture!=null && id.equals(capture.id()) && !bases.containsKey(id)) {
                    require(retiring==null,"capture conflicts with source retirement");
                    retained.put(id,prefixSnapshot(path,capture.packet(),capture.images()));subdirectories.put(id,key(path));
                    retainLeases(id,reserve(id,capture.packet().bytes().length,capture.packet().images()));continue;
                }
                var packet=load(path,promises.get(id),bases.get(id));
                retainLeases(id,reserve(id,Files.size(path.resolve(PACKET)),packet.images()));
                retained.put(id,snapshot(path,packet));subdirectories.put(id,key(path));
            }
            if(capture!=null && !bases.containsKey(capture.id()) && !sourceLeases.containsKey(capture.id()))
                retainLeases(capture.id(),reserve(capture.id(),capture.packet().bytes().length,capture.packet().images()));
            // Validate the entire inventory before sealing bytes made visible by an interrupted process.
            check();
            for(String id:retained.keySet()) {
                Path path=directory.resolve(id);
                for(String name:retained.get(id).keySet())force(path.resolve(name));
                AdmissionPaths.forceDirectory(path);
            }
            AdmissionPaths.forceDirectory(directory);
        } catch(IOException | RuntimeException | Error error) {close();throw error;}
    }
    static Object key(Path path) throws IOException {
        AdmissionPaths.safe(path);Object value=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS).fileKey();
        require(value!=null,"basis source inode unavailable");return value;
    }
    static Set<String> children(Path path,int maximum) throws IOException {
        AdmissionPaths.safe(path);require(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"basis source directory absent");
        var names=new TreeSet<String>();
        try(var stream=Files.newDirectoryStream(path)) {
            for(Path item:stream) {require(names.size()<maximum,"basis source inventory capacity");names.add(item.getFileName().toString());}
        }
        return names;
    }
    private MembershipSourcePacket load(Path path,Decoded promise,Decoded basis) throws IOException {
        require(promise!=null && promise.value().get("basisId")!=null
                && path.getFileName().toString().equals(promise.value().get("basisId")),"retained source requires original basis identity");
        var packet=MembershipSourcePacket.decode(AdmissionPaths.read(path.resolve(PACKET),MembershipSourcePacket.MAXIMUM));
        require(Arrays.equals(root,packet.objectBytes(hash(root))),"retained source original root");
        require(packet.capsule().value().get("root").equals(promise.value().get("root"))
                && MembershipContext.viewDigest((String)promise.value().get("root"),object(object(packet.capsule().value().get("cut")).get("view")))
                    .equals(promise.value().get("view")),"retained source promise view");
        if(basis!=null)packet.bind(basis);
        return packet;
    }
    static FileIdentity inspect(Path path,long size,String digest) throws IOException {
        AdmissionPaths.regular(path);require(Files.size(path)==size,"retained source file length");Object before=key(path);
        MessageDigest sha;
        try {sha=MessageDigest.getInstance("SHA-256");}catch(NoSuchAlgorithmException error){throw new AssertionError(error);}
        try(var channel=FileChannel.open(path,StandardOpenOption.READ,LinkOption.NOFOLLOW_LINKS)) {
            var buffer=ByteBuffer.allocate(65536);long count=0;
            while(channel.read(buffer)!=-1) {buffer.flip();count+=buffer.remaining();require(count<=size,"retained source grew");sha.update(buffer);buffer.clear();}
            require(count==size,"retained source file length");
        }
        String actual=HexFormat.of().formatHex(sha.digest());
        require(actual.equals(digest) && before.equals(key(path)),"retained source file integrity");
        return new FileIdentity(before,size,digest);
    }
    private static Map<String,FileIdentity> snapshot(Path path,MembershipSourcePacket packet) throws IOException {
        var names=new TreeSet<String>();names.add(PACKET);for(String hash:packet.images().keySet())names.add(hash+".image");
        require(children(path,8).equals(names),"retained source file inventory");
        var result=new TreeMap<String,FileIdentity>();byte[] bytes=packet.bytes();
        result.put(PACKET,inspect(path.resolve(PACKET),bytes.length,hash(bytes)));
        for(var image:packet.images().entrySet())result.put(image.getKey()+".image",inspect(path.resolve(image.getKey()+".image"),image.getValue(),image.getKey()));
        return Map.copyOf(result);
    }
    private static Map<String,byte[]> expectedFiles(MembershipSourcePacket packet,Map<String,byte[]> images) {
        packet.verifyImages(images);var result=new TreeMap<String,byte[]>();result.put(PACKET,packet.bytes());
        images.forEach((hash,bytes)->result.put(hash+".image",bytes));return result;
    }
    private static Map<String,FileIdentity> prefixSnapshot(Path path,MembershipSourcePacket packet,Map<String,byte[]> images)throws IOException {
        var expected=expectedFiles(packet,images);var names=children(path,8);require(expected.keySet().containsAll(names),"capture unlisted source member");
        var result=new TreeMap<String,FileIdentity>();
        for(String name:names) {
            byte[] original=expected.get(name),prefix=AdmissionPaths.read(path.resolve(name),original.length);
            require(Arrays.equals(prefix,Arrays.copyOf(original,prefix.length)),"capture source prefix changed");
            result.put(name,inspect(path.resolve(name),prefix.length,hash(prefix)));
        }
        return Map.copyOf(result);
    }
    void resumeCapture(MembershipCaptureFiles.Plan plan,MembershipGenerationFiles.Guard owner)throws IOException {
        require(sourceLeases.containsKey(plan.id()),"capture reservation absent");
        completeCapture(plan.id(),plan.packet(),plan.images(),owner);
    }
    private void completeCapture(String id,MembershipSourcePacket packet,Map<String,byte[]> images,MembershipGenerationFiles.Guard owner)throws IOException {
        check();owner.check();Path path=directory.resolve(id);
        if(!retained.containsKey(id)) {
            cut.at("SOURCE_BEFORE_CREATE");check();owner.check();Files.createDirectory(path);
            retained.put(id,Map.of());subdirectories.put(id,key(path));cut.at("SOURCE_CREATED");check();owner.check();
        }
        var expected=expectedFiles(packet,images);
        // Packet first, then every image. Existing bytes must be the exact original prefix.
        var names=new ArrayList<String>();names.add(PACKET);for(String name:expected.keySet())if(!name.equals(PACKET))names.add(name);
        for(String name:names) {
            check();owner.check();byte[] bytes=expected.get(name);var old=retained.get(id).get(name);
            var options=new HashSet<OpenOption>(Set.of(StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS));if(old==null)options.add(StandardOpenOption.CREATE_NEW);
            String event=name.equals(PACKET)?"SOURCE_PACKET":"SOURCE_IMAGE";
            try(var channel=FileChannel.open(path.resolve(name),options)) {
                Object original=old==null?key(path.resolve(name)):old.key();
                if(old==null){rememberPrefix(id,name,bytes,0,original);cut.at(event+"_CREATED");check();owner.check();}
                int offset=Math.toIntExact(channel.size());require(offset<=bytes.length,"capture file exceeds original");channel.position(offset);
                int middle=offset+(bytes.length-offset)/2;AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,offset,middle));rememberPrefix(id,name,bytes,middle,original);
                cut.at(event+"_PREFIX_WRITTEN");check();owner.check();
                AdmissionPaths.write(channel,Arrays.copyOfRange(bytes,middle,bytes.length));rememberPrefix(id,name,bytes,bytes.length,original);
                cut.at(event+"_WRITTEN");check();owner.check();channel.force(true);cut.at(event+"_FORCED");check();owner.check();
            }
        }
        AdmissionPaths.forceDirectory(path);cut.at("SOURCE_FILES_DIRECTORY_FORCED");check();owner.check();
        AdmissionPaths.forceDirectory(directory);cut.at("SOURCE_DIRECTORY_FORCED");check();owner.check();
        require(retained.get(id).equals(snapshot(path,packet)),"capture complete source changed");
    }
    private void rememberPrefix(String id,String name,byte[] bytes,int length,Object original)throws IOException {
        var info=inspect(directory.resolve(id).resolve(name),length,hash(Arrays.copyOf(bytes,length)));
        require(original.equals(info.key()),"capture source inode changed");var files=new TreeMap<>(retained.get(id));files.put(name,info);retained.put(id,Map.copyOf(files));
    }
    void check() throws IOException {
        require(directoryKey.equals(key(directory)) && children(directory,6).equals(retained.keySet()),"retained source directory changed");
        for(var source:retained.entrySet()) {
            Path path=directory.resolve(source.getKey());require(subdirectories.get(source.getKey()).equals(key(path)),"retained source inode changed");
            require(children(path,8).equals(source.getValue().keySet()),"retained source file inventory");
            for(var file:source.getValue().entrySet()) {
                FileIdentity old=file.getValue();require(old.equals(inspect(path.resolve(file.getKey()),old.bytes(),old.digest())),"retained source inode changed");
            }
        }
    }
    private static Map<String,Map<String,Object>> retirementInventory(MembershipSourceRetirementFiles.Decision decision) {
        var result=new TreeMap<String,Map<String,Object>>();String prefix="sources/"+decision.id()+"/";
        for(Object row:list(decision.record().value().get("files"))){var file=object(row);String full=(String)file.get("path");require(full.startsWith(prefix),"source retirement foreign path");result.put(full.substring(prefix.length()),file);}
        return result;
    }
    void deleteRetired(MembershipSourceRetirementFiles.Decision decision,MembershipGenerationFiles.Guard owner,MembershipBallotAllocator.Cut cut)throws IOException {
        String id=decision.id();var expected=retirementInventory(decision);check();owner.check();
        if(!retained.containsKey(id)){require(!Files.exists(directory.resolve(id),LinkOption.NOFOLLOW_LINKS),"source retirement untracked directory");return;}
        Path path=directory.resolve(id);
        for(String name:new TreeSet<>(retained.get(id).keySet())) {
            check();owner.check();var actual=retained.get(id).get(name);var wanted=expected.get(name);
            require(wanted!=null && actual.bytes()==number(wanted.get("size")) && actual.digest().equals(wanted.get("sha256")),"source retirement remaining original changed");
            Files.delete(path.resolve(name));var remaining=new TreeMap<>(retained.get(id));remaining.remove(name);retained.put(id,Map.copyOf(remaining));
            AdmissionPaths.forceDirectory(path);cut.at("SOURCE_RETIREMENT_FILE_DELETED");check();owner.check();
        }
        check();owner.check();require(children(path,8).isEmpty(),"source retirement directory not empty");Files.delete(path);retained.remove(id);subdirectories.remove(id);
        AdmissionPaths.forceDirectory(directory);cut.at("SOURCE_RETIREMENT_DIRECTORY_DELETED");check();owner.check();
    }
    private void retainLeases(String id,List<MembershipResources.Lease> reserved) {
        require(!sourceLeases.containsKey(id),"source leases already retained");leases.addAll(reserved);sourceLeases.put(id,List.copyOf(reserved));
    }
    void releaseRetiredLeases(String id)throws IOException {
        check();require(!retained.containsKey(id) && !Files.exists(directory.resolve(id),LinkOption.NOFOLLOW_LINKS),"source files still own reservations");
        var obsolete=sourceLeases.remove(id);if(obsolete!=null){obsolete.forEach(MembershipResources.Lease::close);leases.removeAll(obsolete);}
    }
    Set<String> retainedIdentities(){return Set.copyOf(retained.keySet());}
    record Original(MembershipSourcePacket packet,Map<String,byte[]> images) {}
    Original original(Decoded basis) throws IOException {
        return original((String)basis.value().get("basisId"),null,basis);
    }
    Original original(String id,Decoded promise,Decoded basis)throws IOException {
        check();require(retained.containsKey(id),"original basis source absent");
        Path path=directory.resolve(id);var packet=MembershipSourcePacket.decode(AdmissionPaths.read(path.resolve(PACKET),MembershipSourcePacket.MAXIMUM));
        if(basis!=null)packet.bind(basis);else require(promise!=null && id.equals(promise.value().get("basisId"))
                && packet.capsule().value().get("root").equals(promise.value().get("root"))
                && MembershipContext.viewDigest((String)promise.value().get("root"),object(object(packet.capsule().value().get("cut")).get("view"))).equals(promise.value().get("view")),"captured source original promise");
        var images=new TreeMap<String,byte[]>();
        for(var image:packet.images().entrySet())images.put(image.getKey(),AdmissionPaths.read(path.resolve(image.getKey()+".image"),Math.toIntExact(image.getValue())));
        packet.verifyImages(images);check();return new Original(packet,Map.copyOf(images));
    }
    private List<MembershipResources.Lease> reserve(String id,long size,Map<String,Long> images) {
        var result=new ArrayList<MembershipResources.Lease>();
        try {
            result.add(resources.reserve(MembershipResources.Unit.SOURCE,id,size));
            for(var image:images.entrySet())result.add(resources.reserve(MembershipResources.Unit.APPLICATION,id+":"+image.getKey(),image.getValue()));
            return result;
        } catch(RuntimeException | Error error) {result.forEach(MembershipResources.Lease::close);throw error;}
    }
    Prepared prepare(Decoded basis,MembershipCapsule source,Map<String,byte[]> images) throws IOException {
        check();String id=(String)basis.value().get("basisId");require(!retained.containsKey(id),"source identity reused");
        source.packet.bind(basis);source.packet.verifyImages(images);
        byte[] packet=source.packet.bytes();List<MembershipResources.Lease> reserved;
        try {reserved=reserve(id,packet.length,source.packet.images());}
        catch(IllegalArgumentException error) {throw new MembershipOperationException(MembershipOperationException.Reason.CAPACITY_EXCEEDED,
                AutomaticReplicationException.Outcome.NOT_SUBMITTED,Optional.empty(),"original source retention capacity",error);}
        try {
            var copies=new TreeMap<String,byte[]>();images.forEach((hash,bytes)->copies.put(hash,bytes.clone()));source.packet.verifyImages(copies);
            return new Prepared(id,source.packet,packet,copies,reserved);
        }catch(RuntimeException | Error error){reserved.forEach(MembershipResources.Lease::close);throw error;}
    }
    final class Prepared implements AutoCloseable {
        final String id;final MembershipSourcePacket source;final byte[] packet;final Map<String,byte[]> images;
        final List<MembershipResources.Lease> reserved;boolean captured;
        Prepared(String id,MembershipSourcePacket source,byte[] packet,Map<String,byte[]> images,List<MembershipResources.Lease> reserved) {
            this.id=id;this.source=source;this.packet=packet;this.images=images;this.reserved=reserved;
        }
        void captureRecovering(MembershipGenerationFiles.Guard owner)throws IOException {
            check();owner.check();captured=true;retainLeases(id,reserved);completeCapture(id,source,images,owner);
        }
        void capture() throws IOException {
            check();captured=true;retainLeases(id,reserved);Path path=directory.resolve(id);
            cut.at("SOURCE_BEFORE_CREATE");Files.createDirectory(path);cut.at("SOURCE_CREATED");
            write(path.resolve(PACKET),packet,"SOURCE_PACKET");
            for(var image:images.entrySet())write(path.resolve(image.getKey()+".image"),image.getValue(),"SOURCE_IMAGE");
            AdmissionPaths.forceDirectory(path);cut.at("SOURCE_FILES_DIRECTORY_FORCED");
            AdmissionPaths.forceDirectory(directory);cut.at("SOURCE_DIRECTORY_FORCED");
            retained.put(id,snapshot(path,source));subdirectories.put(id,key(path));check();
        }
        @Override public void close() {if(!captured)reserved.forEach(MembershipResources.Lease::close);}
    }
    private void write(Path path,byte[] bytes,String event) throws IOException {
        try(var channel=FileChannel.open(path,StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)) {
            AdmissionPaths.write(channel,bytes);cut.at(event+"_WRITTEN");channel.force(true);cut.at(event+"_FORCED");
        }
    }
    static void force(Path path) throws IOException {
        AdmissionPaths.regular(path);try(var channel=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
    }
    @Override public void close() {leases.forEach(MembershipResources.Lease::close);leases.clear();sourceLeases.clear();}
}
