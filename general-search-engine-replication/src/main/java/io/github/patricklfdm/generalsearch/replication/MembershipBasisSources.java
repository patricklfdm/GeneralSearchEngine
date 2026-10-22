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
    private record FileIdentity(Object key,long bytes,String digest) {}

    MembershipBasisSources(Path parent,MembershipResources resources,MembershipBallotAllocator.Cut cut,
            Map<String,Decoded> promises,Map<String,Decoded> bases) throws IOException {
        directory=parent.resolve(DIRECTORY);this.resources=resources;this.cut=cut;
        root=AdmissionPaths.read(parent.resolve("root.gsr"),16384);directoryKey=key(directory);
        try {
            leases.add(resources.reserve(MembershipResources.Unit.JOURNAL,"membership-grants",MembershipGrantJournal.MAXIMUM));
            Set<String> ids=children(directory,6);
            require(promises.keySet().containsAll(ids) && ids.containsAll(bases.keySet()),"missing or unbound original source");
            for(String id:ids) {
                Path path=directory.resolve(id);var packet=load(path,promises.get(id),bases.get(id));
                leases.addAll(reserve(id,Files.size(path.resolve(PACKET)),packet.images()));
                retained.put(id,snapshot(path,packet));subdirectories.put(id,key(path));
            }
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
    private static Object key(Path path) throws IOException {
        AdmissionPaths.safe(path);Object value=Files.readAttributes(path,BasicFileAttributes.class,LinkOption.NOFOLLOW_LINKS).fileKey();
        require(value!=null,"basis source inode unavailable");return value;
    }
    private static Set<String> children(Path path,int maximum) throws IOException {
        AdmissionPaths.safe(path);require(Files.isDirectory(path,LinkOption.NOFOLLOW_LINKS),"basis source directory absent");
        var names=new TreeSet<String>();
        try(var stream=Files.newDirectoryStream(path)) {
            for(Path item:stream) {require(names.size()<maximum,"basis source inventory capacity");names.add(item.getFileName().toString());}
        }
        return names;
    }
    private MembershipSourcePacket load(Path path,Decoded promise,Decoded basis) throws IOException {
        var packet=MembershipSourcePacket.decode(AdmissionPaths.read(path.resolve(PACKET),MembershipSourcePacket.MAXIMUM));
        require(Arrays.equals(root,packet.objectBytes(hash(root))),"retained source original root");
        require(packet.capsule().value().get("root").equals(promise.value().get("root"))
                && MembershipContext.viewDigest((String)promise.value().get("root"),object(object(packet.capsule().value().get("cut")).get("view")))
                    .equals(promise.value().get("view")),"retained source promise view");
        if(basis!=null)packet.bind(basis);
        return packet;
    }
    private static FileIdentity inspect(Path path,long size,String digest) throws IOException {
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
        void capture() throws IOException {
            check();captured=true;leases.addAll(reserved);Path path=directory.resolve(id);
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
    private static void force(Path path) throws IOException {
        AdmissionPaths.regular(path);try(var channel=FileChannel.open(path,StandardOpenOption.WRITE,LinkOption.NOFOLLOW_LINKS)){channel.force(true);}
    }
    @Override public void close() {leases.forEach(MembershipResources.Lease::close);leases.clear();}
}
