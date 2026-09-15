package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.UUID;

/** Exact public-admission 1.1 records. Legacy 1.0 readers remain separate. */
final class AdmissionFormat {
    static final int META = MAX_METADATA_BYTES, IMAGE = 64 * 1024 * 1024;
    static final String ZERO = "0".repeat(64);
    static final Comparator<String> UTF8 = (a, b) -> Arrays.compareUnsigned(
            a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8));

    private AdmissionFormat() { }

    static byte[] record(int kind, Encoder encoder) { return record(kind, body(encoder), META); }

    static byte[] record(int kind, byte[] payload, int maximum) {
        require(payload.length > 0 && (long) payload.length + HEADER_BYTES <= maximum,
                CAPACITY_EXCEEDED, "admission record exceeds bound");
        byte[] prefix = ByteBuffer.allocate(16).putInt(MAGIC).putShort((short) 1).putShort((short) 1)
                .putShort((short) kind).putShort((short) 0).putInt(payload.length).array();
        return join(prefix, HexFormat.of().parseHex(sha256(join(prefix, payload))), payload);
    }

    static DataInputStream decode(byte[] bytes, int kind, int maximum) {
        require(bytes.length >= HEADER_BYTES && bytes.length <= maximum, CAPACITY_EXCEEDED, "invalid record size");
        var header = ByteBuffer.wrap(bytes);
        require(header.getInt() == MAGIC && header.getShort() == 1 && header.getShort() == 1,
                PROTOCOL_MISMATCH, "public admission requires replicated 1.1");
        require(Short.toUnsignedInt(header.getShort()) == kind && header.getShort() == 0
                        && header.getInt() == bytes.length - HEADER_BYTES,
                INTEGRITY_FAILURE, "invalid record kind, flags or length");
        byte[] payload = Arrays.copyOfRange(bytes, HEADER_BYTES, bytes.length);
        require(Arrays.equals(bytes, record(kind, payload, maximum)), INTEGRITY_FAILURE, "admission checksum mismatch");
        return input(payload);
    }

    static byte[] join(byte[]... parts) {
        int size = 0;
        for (var part : parts) size = Math.addExact(size, part.length);
        var result = ByteBuffer.allocate(size);
        for (var part : parts) result.put(part);
        return result.array();
    }

    static byte[] blob(DataInputStream in, int maximum) throws IOException {
        int size = in.readInt();
        require(size >= 0 && size <= maximum && size <= in.available(), INTEGRITY_FAILURE, "invalid blob size");
        return in.readNBytes(size);
    }

    static void blob(DataOutputStream out, byte[] bytes) throws IOException {
        out.writeInt(bytes.length); out.write(bytes);
    }

    static UUID history(UUID group) {
        byte[] digest = HexFormat.of().parseHex(sha256(join(
                "gse-v50-application-history-v1\0".getBytes(StandardCharsets.US_ASCII),
                ByteBuffer.allocate(16).putLong(group.getMostSignificantBits()).putLong(group.getLeastSignificantBits()).array())));
        var input = ByteBuffer.wrap(digest);
        var history = new UUID(input.getLong(), input.getLong());
        require(!history.equals(NO_INCARNATION), CONFLICTING_HISTORY, "zero derived application history");
        return history;
    }

    record Member(String name, int kind, long size, String digest) {
        Member {
            require(name.getBytes(StandardCharsets.UTF_8).length <= 4096 && !name.contains("\\")
                            && !name.contains("\0") && Arrays.stream(name.split("/", -1))
                            .noneMatch(part -> part.isEmpty() || part.equals(".") || part.equals("..")),
                    INTEGRITY_FAILURE, "invalid inventory member name");
            validHash(digest);
            require((kind == 0 || kind == 1) && size >= 0 && size <= (1L << 40)
                            && (kind != 0 || size == 0 && digest.equals(ZERO)), INTEGRITY_FAILURE, "invalid inventory member");
        }
    }

    static List<Member> inventory(Map<String, byte[]> files) {
        return files.entrySet().stream().sorted(Map.Entry.comparingByKey(UTF8))
                .map(e -> new Member(e.getKey(), 1, e.getValue().length, sha256(e.getValue()))).toList();
    }

    static void inventory(DataOutputStream out, List<Member> members) throws IOException {
        require(members.size() <= 10_000, CAPACITY_EXCEEDED, "inventory count exceeds bound");
        out.writeInt(members.size());
        String previous = null;
        for (var member : members) {
            require(previous == null || UTF8.compare(previous, member.name()) < 0, INTEGRITY_FAILURE, "unsorted inventory");
            text(out, member.name()); out.writeByte(member.kind()); out.writeLong(member.size()); hash(out, member.digest());
            previous = member.name();
        }
    }

    static List<Member> inventory(DataInputStream in) throws IOException {
        int count = in.readInt();
        require(count >= 0 && count <= 10_000 && count <= in.available() / 46, CAPACITY_EXCEEDED, "invalid inventory count");
        var members = new ArrayList<Member>();
        String previous = null;
        for (int i = 0; i < count; i++) {
            var member = new Member(text(in, 4096), in.readUnsignedByte(), in.readLong(), hash(in));
            require(previous == null || UTF8.compare(previous, member.name()) < 0, INTEGRITY_FAILURE, "unsorted inventory");
            members.add(member); previous = member.name();
        }
        return List.copyOf(members);
    }

    static String inventoryDigest(List<Member> members) {
        return sha256(join("gse-v50-payload-inventory-v1\0".getBytes(StandardCharsets.US_ASCII),
                body(out -> inventory(out, members))));
    }

    record Source(int kind, int minor, UUID history, long sequence, List<Member> members) {
        Source {
            members = List.copyOf(members);
            require((kind == 0 || kind == 1) && sequence >= 0 && sequence < Long.MAX_VALUE,
                    INTEGRITY_FAILURE, "invalid source sequence/kind");
            require(kind == 0 ? minor == 0 && history.equals(NO_INCARNATION) && sequence == 0 && members.isEmpty()
                            : minor >= 0 && minor <= 2 && !history.equals(NO_INCARNATION)
                            && members.stream().map(Member::name).toList().equals(List.of(
                                    "gse-backup-checkpoint", "gse-backup-manifest", "gse-backup-metadata"))
                            && members.stream().allMatch(m -> m.kind() == 1 && m.size() > 0),
                    INTEGRITY_FAILURE, "invalid source provenance");
        }

        byte[] encode() {
            return body(out -> {
                out.writeByte(kind); text(out, kind == 0 ? "none" : "gse-backup");
                out.writeShort(kind == 0 ? 0 : 1); out.writeShort(minor);
                text(out, kind == 0 ? "none" : minor == 2 ? "canonical-only" : "full");
                uuid(out, history); out.writeLong(sequence); inventory(out, members);
            });
        }

        static Source decode(byte[] bytes) throws IOException {
            var in = input(bytes);
            int kind = in.readUnsignedByte(); String family = text(in, 32);
            int major = in.readUnsignedShort(), minor = in.readUnsignedShort(); String profile = text(in, 32);
            var result = new Source(kind, minor, uuid(in), in.readLong(), inventory(in)); end(in);
            require(Arrays.equals(bytes, result.encode()) && family.equals(kind == 0 ? "none" : "gse-backup")
                            && major == (kind == 0 ? 0 : 1) && profile.equals(kind == 0 ? "none" : minor == 2 ? "canonical-only" : "full"),
                    INTEGRITY_FAILURE, "noncanonical source descriptor");
            return result;
        }
    }

    record Manifest(ReplicaManifest group, String genesisDigest, UUID history, long base) {
        Manifest {
            validHash(genesisDigest);
            require(group.schemaVersion() == 1 && history.equals(AdmissionFormat.history(group.groupId().value()))
                    && base >= 0 && base < Long.MAX_VALUE, INTEGRITY_FAILURE, "invalid genesis manifest binding");
        }

        byte[] encode() {
            return record(1, out -> {
                text(out, "gse-replicated"); out.writeShort(1); out.writeShort(1);
                text(out, "gse-replication"); out.writeShort(1); out.writeShort(1);
                uuid(out, group.groupId().value()); text(out, group.configurationId()); out.writeLong(1);
                text(out, group.leader().value()); out.writeInt(3);
                for (var member : group.members()) {
                    text(out, member.nodeId().value()); text(out, member.endpoint().host());
                    out.writeInt(member.endpoint().port()); out.writeByte(1);
                }
                text(out, group.codecId()); out.writeInt(group.codecVersion());
                text(out, group.schemaId()); out.writeInt(group.schemaVersion()); hash(out, group.indexConfigurationDigest());
                hash(out, genesisDigest); uuid(out, history); out.writeLong(base);
            });
        }

        String digest() { return frameDigest(encode()); }

        static Manifest read(byte[] bytes) throws IOException {
            var in = decode(bytes, 1, META);
            require(text(in, 32).equals("gse-replicated") && in.readUnsignedShort() == 1 && in.readUnsignedShort() == 1
                            && text(in, 32).equals("gse-replication") && in.readUnsignedShort() == 1 && in.readUnsignedShort() == 1,
                    PROTOCOL_MISMATCH, "unsupported public manifest");
            var id = new ReplicationGroupId(uuid(in)); String config = text(in, 128);
            require(in.readLong() == 1, INTEGRITY_FAILURE, "invalid initial epoch");
            var leader = new ReplicationNodeId(text(in, 64));
            require(in.readInt() == 3, INTEGRITY_FAILURE, "invalid voter count");
            var members = new ArrayList<ReplicationMember>();
            for (int i = 0; i < 3; i++) {
                members.add(new ReplicationMember(new ReplicationNodeId(text(in, 64)),
                        new ReplicationEndpoint(text(in, 1012), in.readInt())));
                require(in.readUnsignedByte() == 1, INTEGRITY_FAILURE, "nonvoter in initial manifest");
            }
            var group = new ReplicaManifest(id, config, leader, members, text(in, 128), in.readInt(),
                    text(in, 128), in.readInt(), hash(in));
            var result = new Manifest(group, hash(in), uuid(in), in.readLong()); end(in);
            return result;
        }
    }

    record Genesis(UUID group, Source source, UUID history, long base, byte[] application) {
        Genesis {
            application = application.clone();
            require(history.equals(AdmissionFormat.history(group)) && !history.equals(source.history())
                            && base == source.sequence(), INTEGRITY_FAILURE, "invalid genesis history/base");
        }

        byte[] encode(int maximum) {
            return record(16, body(out -> {
                out.writeShort(1); uuid(out, group); blob(out, source.encode()); uuid(out, history);
                out.writeLong(base); blob(out, application);
            }), maximum);
        }

        static Genesis read(byte[] bytes, Manifest manifest) throws IOException {
            var in = decode(bytes, 16, IMAGE);
            require(in.readUnsignedShort() == 1, PROTOCOL_MISMATCH, "unsupported genesis projection");
            var result = new Genesis(uuid(in), Source.decode(blob(in, META)), uuid(in), in.readLong(), blob(in, IMAGE)); end(in);
            require(frameDigest(bytes).equals(manifest.genesisDigest()) && result.group().equals(manifest.group().groupId().value())
                            && result.history().equals(manifest.history()) && result.base() == manifest.base(),
                    INTEGRITY_FAILURE, "genesis differs from manifest");
            var indexes = validateApplication(result.application(), result.source().kind() == 0);
            require(sha256(ReplicaJson.encode(indexes.stream().sorted().toList(), META)).equals(manifest.group().indexConfigurationDigest()),
                    INTEGRITY_FAILURE, "genesis application index digest mismatch");
            return result;
        }
    }

    static List<String> validateApplication(byte[] bytes, boolean empty) throws IOException {
        var in = input(bytes); require(in.readUnsignedShort() == 1, PROTOCOL_MISMATCH, "unsupported application projection");
        int count = in.readInt(); require(count >= 0 && count <= 10_000 && count <= in.available() / 4,
                CAPACITY_EXCEEDED, "invalid application index count");
        var indexes = new ArrayList<String>(); String previous = null;
        for (int i = 0; i < count; i++) {
            String descriptor = text(in, 8192);
            var object = AdmissionConfiguration.object(ReplicaJson.decode(descriptor.getBytes(StandardCharsets.US_ASCII), 8192));
            AdmissionConfiguration.keys(object, "analyzer", "field", "kind");
            String field = AdmissionConfiguration.string(object, "field"), kind = AdmissionConfiguration.string(object, "kind");
            require((previous == null || previous.compareTo(field) < 0) && field.getBytes(StandardCharsets.UTF_8).length <= 1024
                            && java.util.Set.of("equality", "range", "prefix", "text").contains(kind)
                            && (kind.equals("text") ? "gse-simple-v1" : "").equals(object.get("analyzer")),
                    INTEGRITY_FAILURE, "noncanonical application index");
            previous = field; indexes.add(descriptor);
        }
        int documents = in.readInt();
        require(documents >= 0 && documents <= 100_000_000 && documents <= in.available() / 8 && (!empty || documents == 0),
                CAPACITY_EXCEEDED, "invalid genesis document count");
        var keys = new java.util.HashSet<ByteBuffer>();
        for (int i = 0; i < documents; i++) {
            require(keys.add(ByteBuffer.wrap(blob(in, IMAGE))), INTEGRITY_FAILURE, "duplicate canonical application key"); blob(in, IMAGE);
        }
        end(in); return List.copyOf(indexes);
    }

    static Map<String, byte[]> payloads(Manifest manifest, byte[] genesis, ReplicationNodeId node, boolean replacement) {
        var files = new TreeMap<String, byte[]>(UTF8);
        files.put("manifest.gsr", manifest.encode()); files.put("genesis.gsr", genesis); files.put("replica.lock", new byte[0]);
        files.put("node.gsr", record(2, out -> { hash(out, manifest.digest()); text(out, node.value()); out.writeByte(replacement ? 1 : 0); }));
        var headers = new ArrayList<byte[]>();
        for (int kind : List.of(4, 5, 6)) {
            headers.add(record(3, out -> { hash(out, manifest.digest()); text(out, node.value()); out.writeShort(kind); }));
        }
        byte[] promise = record(4, out -> {
            hash(out, manifest.digest()); text(out, manifest.group().leader().value()); out.writeLong(1); uuid(out, NO_INCARNATION);
        });
        files.put("promises.gsr", join(headers.get(0), promise)); files.put("entries.gsr", headers.get(1)); files.put("proofs.gsr", headers.get(2));
        files.put("storage-ready.gsr", record(7, out -> {
            hash(out, manifest.digest()); hash(out, frameDigest(files.get("node.gsr")));
            for (byte[] header : headers) hash(out, frameDigest(header));
        }));
        if (replacement) files.put("rebuilding.gsr", record(13, out -> { hash(out, manifest.digest()); text(out, node.value()); }));
        return files;
    }
}
