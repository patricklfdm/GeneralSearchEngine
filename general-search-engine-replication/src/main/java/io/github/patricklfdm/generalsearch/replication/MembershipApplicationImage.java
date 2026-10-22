package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private exact backup-member image. No owner, WAL, selector, ACK or publication. */
final class MembershipApplicationImage {
    static final int MAXIMUM = (int) MembershipResources.Unit.APPLICATION.bytes;
    static final int HEADER = 12, OVERHEAD = HEADER + 3 * Integer.BYTES;
    static final List<String> MEMBERS = List.of("gse-backup-checkpoint", "gse-backup-manifest", "gse-backup-metadata");
    private static final int MAGIC = 0x47534149; // GSAI; private container, not a GSER record
    private MembershipApplicationImage() { }

    static <K,T> byte[] capture(SearchEngineConfiguration<K,T> captured,
            DurableStorageConfig<K,T> storage, DurableApplicationState<T> state, Path backup) throws IOException {
        AdmissionPaths.disjoint(List.of(storage.directory(), backup));
        AdmissionPaths.absent(backup);
        captured.newBuilder().writeDurableBackup(state, storage, new DurableBackupRequest(backup, MAXIMUM - OVERHEAD));
        return fromBackup(captured, storage, backup);
    }

    /** The source is only read; normalization affects a new byte array, never its files. */
    static <K,T> byte[] fromBackup(SearchEngineConfiguration<K,T> captured,
            DurableStorageConfig<K,T> storage, Path backup) throws IOException {
        var before = inventory(backup);
        require(DurableStorageOperations.verifyBackup(backup).status() == DurableVerificationStatus.VALID,
                "application backup structure");
        var members = new ArrayList<byte[]>();
        for (int i = 0; i < MEMBERS.size(); i++)
            members.add(AdmissionPaths.read(backup.resolve(MEMBERS.get(i)), Math.toIntExact(before.get(i).size())));
        var active = configuration(captured, members.get(2));
        active.newBuilder().readDurableBackup(backup, verification(storage), MAXIMUM - OVERHEAD);
        require(before.equals(inventory(backup)), "application backup changed");
        for (int i = 0; i < MEMBERS.size(); i++) {
            var member = before.get(i);
            require(member.name().equals(MEMBERS.get(i)) && member.size() == members.get(i).length
                    && member.digest().equals(MembershipFormat.hash(members.get(i))), "application original member changed");
        }
        members.set(1, manifest(members.get(1)));
        return pack(members);
    }

    /** Materializes into an absent, caller-reserved scratch directory and uses the core semantic reader. */
    static <K,T> DurableApplicationState<T> read(SearchEngineConfiguration<K,T> captured,
            DurableStorageConfig<K,T> storage, byte[] bytes, Path scratch) throws IOException {
        var members = unpack(bytes);
        require(Arrays.equals(members.get(1), manifest(members.get(1))), "noncanonical application manifest administration");
        var active = configuration(captured, members.get(2));
        AdmissionPaths.disjoint(List.of(storage.directory(), scratch));
        AdmissionPaths.absent(scratch);
        var parent = AdmissionPaths.binding(scratch);
        Files.createDirectory(scratch);
        for (int i = 0; i < MEMBERS.size(); i++) AdmissionPaths.write(scratch.resolve(MEMBERS.get(i)), members.get(i));
        AdmissionPaths.recheck(parent);
        var before = inventory(scratch);
        var state = active.newBuilder().readDurableBackup(scratch, verification(storage), MAXIMUM - OVERHEAD);
        require(before.equals(inventory(scratch)), "application scratch changed");
        for (int i = 0; i < MEMBERS.size(); i++)
            require(before.get(i).digest().equals(MembershipFormat.hash(members.get(i))), "application scratch identity");
        return state;
    }

    private static <K,T> DurableVerificationConfig<K,T> verification(DurableStorageConfig<K,T> storage) {
        return new DurableVerificationConfig<>(storage.storageIdentity(), storage.schemaIdentity(), storage.codec(),
                storage.codec().codecVersion(), storage.maxEncodedKeyBytes(), storage.maxEncodedDocumentBytes(), storage.maxDocuments());
    }

    private static List<AdmissionFormat.Member> inventory(Path backup) throws IOException {
        var members = AdmissionPaths.inventory(backup, MAXIMUM - OVERHEAD);
        require(members.size() == 3 && members.stream().allMatch(m -> m.kind() == 1 && m.size() > 0)
                && members.stream().map(AdmissionFormat.Member::name).toList().equals(MEMBERS), "application backup member inventory");
        return members;
    }

    static byte[] pack(List<byte[]> members) {
        require(members.size() == 3, "application member count");
        long length = OVERHEAD;
        for (byte[] member : members) { require(member.length > 0, "empty application member"); length += member.length; }
        require(length <= MAXIMUM, "application image capacity");
        var out = ByteBuffer.allocate((int) length).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt((int)length - HEADER);
        for (byte[] member : members) out.putInt(member.length).put(member);
        return out.array();
    }

    static List<byte[]> unpack(byte[] bytes) {
        require(bytes.length >= OVERHEAD && bytes.length <= MAXIMUM, "application image size");
        var in = ByteBuffer.wrap(bytes);
        require(in.getInt() == MAGIC && in.getShort() == 1 && in.getShort() == 3
                && in.getInt() == bytes.length - HEADER, "application image header");
        var members = new ArrayList<byte[]>();
        for (int i = 0; i < 3; i++) {
            require(in.remaining() >= 4, "application member length");
            int length = in.getInt();
            require(length > 0 && length <= in.remaining() - (2 - i) * 4, "application member length");
            byte[] member = new byte[length]; in.get(member); members.add(member);
        }
        require(!in.hasRemaining(), "application image trailer");
        return List.copyOf(members);
    }

    /** Only locates the existing administrative suffix; core verification remains mandatory. */
    private static byte[] manifest(byte[] original) throws IOException {
        var in = checked(original, 16 * 1024 * 1024);
        require(in.getLong() == 0x475345424b503130L && in.getShort() == 1, "application backup manifest format");
        int minor = in.getShort(); require(minor >= 0 && minor <= 2, "application backup manifest version");
        require(string(in,128,false).equals("gse-backup") && string(in,128,false).equals("gse-durable")
                && in.getShort() == 1 && in.getShort() == minor, "application backup manifest source");
        if (minor != 0) skip(in,32);
        skip(in,24); // history and sequence; retained byte-exact
        for (int i=0;i<3;i++) string(in,128,false);
        skip(in,4); require(in.getInt() == 2, "application backup payload count");
        for (int i=0;i<2;i++) { string(in,128,false); skip(in,40); }
        skip(in,32); int prefix = in.position();
        require(in.getLong() >= 0, "application backup creation time"); string(in,256,true);
        require(!in.hasRemaining(), "application backup manifest trailer");
        byte[] canonical = new byte[prefix + Long.BYTES + Integer.BYTES + Integer.BYTES];
        System.arraycopy(original,0,canonical,0,prefix); // zero time, empty request ID
        var crc = new CRC32C(); crc.update(canonical,0,canonical.length-4);
        ByteBuffer.wrap(canonical).putInt(canonical.length-4,(int)crc.getValue());
        return canonical;
    }

    /** Read existing core descriptor bytes, then delegate all typed semantics to the core reader. */
    private static <K,T> SearchEngineConfiguration<K,T> configuration(SearchEngineConfiguration<K,T> captured,
            byte[] metadata) throws IOException {
        var in = checked(metadata,MAXIMUM);
        require(in.getLong() == 0x4753454d45544131L && in.getShort() == 1, "application metadata format");
        int minor = in.getShort(); require(minor >= 0 && minor <= 2, "application metadata version");
        skip(in,16); require(string(in,128,false).equals("gse-durable"), "application metadata family");
        if(minor != 0) {int length = in.getInt(); require(length >= 12 && length <= 4096, "application metadata profile size"); skip(in,length+32);}
        for (int i=0;i<3;i++) string(in,128,false);
        skip(in,5*4+2*8+(minor==2?8:0));
        int count = in.getInt(); require(count >= 0 && count <= 10_000 && count <= in.remaining()/10, "application index count");
        var definitions = new ArrayList<IndexDefinition<T>>(); var fields = new HashSet<String>();
        for (int i=0;i<count;i++) {
            int kind = Byte.toUnsignedInt(in.get()); require(kind >= 1 && kind <= 4, "application index kind");
            String field = string(in,1024,false), analyzer = string(in,128,true);
            require(fields.add(field), "application duplicate index field");
            String descriptor = new String(ReplicaJson.encode(Map.of("kind",List.of("equality","range","prefix","text").get(kind-1),
                    "field",field,"analyzer",analyzer),8192),StandardCharsets.US_ASCII);
            definitions.add(ReplicaApplication.definition(captured.schema(),descriptor));
        }
        require(!in.hasRemaining(), "application metadata trailer");
        return new SearchEngineConfiguration<>(captured.schema(),definitions,captured.config(),captured.plannerConfig());
    }

    private static ByteBuffer checked(byte[] bytes,int maximum) {
        require(bytes.length >= 64 && bytes.length <= maximum, "application member size");
        var crc = new CRC32C(); crc.update(bytes,0,bytes.length-4);
        require((int)crc.getValue() == ByteBuffer.wrap(bytes).getInt(bytes.length-4), "application member CRC");
        return ByteBuffer.wrap(bytes,0,bytes.length-4).slice();
    }
    private static void skip(ByteBuffer in,int count) {
        require(count >= 0 && count <= in.remaining(), "application member truncation"); in.position(in.position()+count);
    }
    private static String string(ByteBuffer in,int maximum,boolean empty) throws IOException {
        require(in.remaining() >= 4, "application string length"); int length = in.getInt();
        require(length >= (empty?0:1) && length <= maximum && length <= in.remaining(), "application string bound");
        var slice = in.slice(); slice.limit(length); skip(in,length);
        return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(slice).toString();
    }
}
