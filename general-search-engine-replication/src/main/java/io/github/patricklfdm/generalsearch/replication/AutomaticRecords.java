package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Base64;
import java.util.Collections;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/** Explicit automatic-only framing and the reviewed storage record catalog. */
final class AutomaticRecords {
    static final int HEADER = 48, META = 65536, IMAGE = 67108864;
    static final String ZERO = "00000000-0000-0000-0000-000000000000";
    static final Map<String, Object> CATALOG = catalog();
    private static Map<String,Object> catalog() {
        var result = new LinkedHashMap<>(object(ReplicaJson.decode(AutomaticRecordCatalog.JSON.strip().getBytes(StandardCharsets.US_ASCII),65536)));
        result.put("BOOTSTRAP_BINDING",Map.of("id",28L,"encoding","canonical-json","maximum",65536L,
                "schema",Map.of("object",Map.of("descriptor","blob"))));
        result.put("BOOTSTRAP_CLEANUP",Map.of("id",29L,"encoding","canonical-json","maximum",65536L,
                "schema",Map.of("object",Map.of("plan","frame:PLAN","binding","frame:BOOTSTRAP_BINDING","cleanup","frame:CLEANUP"))));
        return Collections.unmodifiableMap(result);
    }

    private AutomaticRecords() { }

    static AutomaticReplicationException failure(AutomaticReplicationException.Reason reason, String message, Throwable cause) {
        return new AutomaticReplicationException(reason, AutomaticReplicationException.Outcome.NOT_APPLICABLE,
                Optional.empty(), message, cause);
    }
    static void need(boolean condition, String message) {
        if (!condition) throw failure(INTEGRITY_FAILURE, message, null);
    }
    static void capacity(boolean condition, String message) {
        if (!condition) throw failure(CAPACITY_EXCEEDED, message, null);
    }
    @SuppressWarnings("unchecked")
    static Map<String, Object> object(Object value) {
        need(value instanceof Map<?, ?>, "object required"); return (Map<String, Object>) value;
    }
    @SuppressWarnings("unchecked")
    static List<Object> list(Object value) {
        need(value instanceof List<?>, "array required"); return (List<Object>) value;
    }
    static String text(Map<String, Object> value, String key) { return (String) value.get(key); }
    static long number(Map<String, Object> value, String key) { return ((Number) value.get(key)).longValue(); }
    static byte[] hash(byte[]... parts) {
        try { var digest = MessageDigest.getInstance("SHA-256"); for (byte[] part : parts) digest.update(part); return digest.digest(); }
        catch (java.security.NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
    }
    static String sha(byte[] bytes) { return HexFormat.of().formatHex(hash(bytes)); }
    static String digest(byte[] bytes) { need(bytes.length >= HEADER, "short frame"); return HexFormat.of().formatHex(bytes, 16, 48); }
    static String b64(byte[] bytes) { return Base64.getEncoder().encodeToString(bytes); }
    static byte[] unbase(Object text) { return Base64.getDecoder().decode((String) text); }
    static byte[] canonical(Object value) { return ReplicaJson.encode(value, IMAGE); }

    record Record(String name, Map<String, Object> value, byte[] bytes) {
        Record { value = object(freeze(value)); bytes = bytes.clone(); }
        @Override public byte[] bytes() { return bytes.clone(); }
        String digest() { return AutomaticRecords.digest(bytes); }
    }
    private static Object freeze(Object value) {
        if (value instanceof Map<?, ?>) {
            var copy = new LinkedHashMap<String, Object>(); object(value).forEach((k, v) -> copy.put(k, freeze(v)));
            return Collections.unmodifiableMap(copy);
        }
        if (value instanceof List<?>) return list(value).stream().map(AutomaticRecords::freeze).toList();
        return value;
    }

    static Record decode(byte[] bytes, String name) { return decode(bytes, name, 0); }
    private static Record decode(byte[] bytes, String name, int depth) {
        try {
            need(depth <= 16 && CATALOG.containsKey(name), "unsupported automatic record/depth");
            var spec = object(CATALOG.get(name));
            capacity(bytes.length > HEADER && bytes.length <= number(spec, "maximum"), "automatic record size");
            bytes = bytes.clone();
            var input = ByteBuffer.wrap(bytes);
            if (input.getInt() != 0x47534552 || input.getShort() != 1 || input.getShort() != 2)
                throw failure(PROTOCOL_MISMATCH, "automatic storage requires GSER 1.2", null);
            need(Short.toUnsignedInt(input.getShort()) == number(spec, "id") && input.getShort() == 0, "record kind/flags");
            need(input.getInt() == bytes.length - HEADER, "record length");
            byte[] body = Arrays.copyOfRange(bytes, HEADER, bytes.length);
            need(MessageDigest.isEqual(Arrays.copyOfRange(bytes, 16, HEADER),
                    hash(Arrays.copyOf(bytes, 16), body)), "record checksum");
            Map<String, Object> value;
            if (spec.get("encoding").equals("canonical-json")) value = object(ReplicaJson.decode(body, (int) number(spec, "maximum")));
            else {
                var reader = new Reader(body); value = new LinkedHashMap<>();
                for (Object row : list(spec.get("fields"))) {
                    var field = list(row); value.put((String) field.get(0), reader.read(field.get(1)));
                }
                need(!reader.input.hasRemaining(), "trailing binary fields");
            }
            schema(spec.get("schema"), value, depth);
            semantics(name, value);
            return new Record(name, value, bytes);
        } catch (ReplicationException error) {
            throw failure(error.reason() == ReplicationException.Reason.CAPACITY_EXCEEDED ? CAPACITY_EXCEEDED : INTEGRITY_FAILURE,
                    "invalid automatic JSON", error);
        } catch (IllegalArgumentException | java.nio.BufferUnderflowException error) {
            throw failure(INTEGRITY_FAILURE, "invalid automatic encoding", error);
        }
    }

    static byte[] encode(String name, Map<String, Object> value) {
        need(CATALOG.containsKey(name), "unsupported automatic record");
        var spec = object(CATALOG.get(name)); schema(spec.get("schema"), value, 0);
        byte[] body;
        if (spec.get("encoding").equals("canonical-json")) body = canonical(value);
        else {
            var output = new ByteArrayOutputStream();
            try (var stream = new DataOutputStream(output)) {
                for (Object row : list(spec.get("fields"))) {
                    var field = list(row); write(stream, field.get(1), value.get(field.get(0)));
                }
            } catch (IOException impossible) { throw new IllegalStateException(impossible); }
            body = output.toByteArray();
        }
        capacity((long) body.length + HEADER <= number(spec, "maximum"), "encoded record size");
        byte[] header = ByteBuffer.allocate(16).putInt(0x47534552).putShort((short) 1).putShort((short) 2)
                .putShort((short) number(spec, "id")).putShort((short) 0).putInt(body.length).array();
        return decode(ByteBuffer.allocate(HEADER + body.length).put(header).put(hash(header, body)).put(body).array(), name).bytes();
    }

    static void schema(Object type, Object value, int depth) {
        capacity(depth <= 16, "schema depth");
        if (type instanceof Map<?, ?>) {
            var spec = object(type);
            if (spec.containsKey("optional")) { if (value != null) schema(spec.get("optional"), value, depth + 1); }
            else if (spec.containsKey("object")) {
                var fields = object(spec.get("object")); var actual = object(value);
                need(actual.keySet().equals(fields.keySet()), "exact record fields");
                fields.forEach((key, child) -> schema(child, actual.get(key), depth + 1));
            } else if (spec.containsKey("array")) {
                var items = list(value); capacity(items.size() >= number(spec, "min") && items.size() <= number(spec, "max"), "array count");
                for (Object item : items) schema(spec.get("array"), item, depth + 1);
            } else if (spec.containsKey("enum")) need(list(spec.get("enum")).stream().anyMatch(x -> equalScalar(x, value)), "enum value");
            else if (spec.containsKey("integer")) {
                long n = integer(value); var range = list(spec.get("integer"));
                need(n >= ((Number) range.get(0)).longValue() && n <= ((Number) range.get(1)).longValue(), "integer range");
            } else throw failure(INTEGRITY_FAILURE, "unknown schema", null);
            return;
        }
        String name = (String) type;
        if (name.equals("bool")) { need(value instanceof Boolean, "boolean scalar"); return; }
        if (List.of("positive", "counter", "u8").contains(name)) {
            long n = integer(value); need(n >= (name.equals("positive") ? 1 : 0) && (!name.equals("u8") || n <= 255), "integer scalar"); return;
        }
        need(value instanceof String, "string scalar"); String s = (String) value;
        switch (name) {
            case "hash" -> need(hexHash(s), "hash");
            case "uuid" -> need(UUID.fromString(s).toString().equals(s), "canonical UUID");
            case "id", "node" -> need(identity(s, name.equals("node") ? 64 : 128), "identity");
            case "text", "relative" -> {
                need(!s.isEmpty() && s.getBytes(StandardCharsets.UTF_8).length <= 4096 && s.indexOf('\0') < 0, "text bound");
                need(StandardCharsets.UTF_8.newEncoder().canEncode(s), "invalid Unicode text");
                if (name.equals("relative")) need(!s.startsWith("/") && !s.contains("\\")
                        && Arrays.stream(s.split("/", -1)).noneMatch(v -> v.isEmpty() || v.equals(".") || v.equals("..")), "relative path");
            }
            default -> {
                need(name.equals("blob") || name.startsWith("frame:"), "binary scalar type");
                capacity(s.length() <= ((long) IMAGE + 2) / 3 * 4, "base64 size");
                byte[] raw = unbase(s); need(b64(raw).equals(s), "canonical base64"); capacity(raw.length <= IMAGE, "blob size");
                if (name.startsWith("frame:")) decode(raw, name.substring(6), depth + 1);
            }
        }
    }
    private static boolean hexHash(String value) {
        if (value.length() != 64) return false;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (!(c >= '0' && c <= '9' || c >= 'a' && c <= 'f')) return false;
        }
        return true;
    }
    private static boolean alphaNumeric(char c) { return c >= 'a' && c <= 'z' || c >= '0' && c <= '9'; }
    private static boolean identity(String value, int maximum) {
        if (value.isEmpty() || value.length() > maximum || !alphaNumeric(value.charAt(0))) return false;
        for (int i = 1; i < value.length(); i++) {
            char c = value.charAt(i);
            if (!alphaNumeric(c) && c != '.' && c != '_' && c != '-') return false;
        }
        return true;
    }
    private static long integer(Object value) { need(value instanceof Long || value instanceof Integer, "integer required"); return ((Number) value).longValue(); }
    private static boolean equalScalar(Object a, Object b) {
        return a instanceof Number && (b instanceof Long || b instanceof Integer) ? ((Number) a).longValue() == ((Number) b).longValue() : java.util.Objects.equals(a, b);
    }

    private static final class Reader {
        final ByteBuffer input;
        Reader(byte[] bytes) { input = ByteBuffer.wrap(bytes); }
        byte[] take(int size) { need(size >= 0 && size <= input.remaining(), "truncated field"); byte[] b = new byte[size]; input.get(b); return b; }
        Object read(Object type) {
            if (type instanceof Map<?, ?>) {
                var spec = object(type);
                if (spec.containsKey("optional")) { int tag = Byte.toUnsignedInt(input.get()); need(tag <= 1, "optional tag"); return tag == 0 ? null : read(spec.get("optional")); }
                if (spec.containsKey("array")) {
                    int count = input.getInt(); need(count >= number(spec, "min") && count <= number(spec, "max"), "binary array count");
                    var values = new ArrayList<>(); for (int i = 0; i < count; i++) values.add(read(spec.get("array"))); return values;
                }
                var result = new LinkedHashMap<String, Object>(); object(spec.get("object")).forEach((k, t) -> result.put(k, read(t))); return result;
            }
            String name = (String) type;
            return switch (name) {
                case "hash" -> HexFormat.of().formatHex(take(32));
                case "uuid" -> new UUID(input.getLong(), input.getLong()).toString();
                case "positive", "counter" -> input.getLong();
                case "u8" -> (long) Byte.toUnsignedInt(input.get());
                default -> {
                    byte[] bytes = take(input.getInt());
                    if (name.equals("blob") || name.startsWith("frame:")) yield b64(bytes);
                    try { yield StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                            .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString(); }
                    catch (java.nio.charset.CharacterCodingException error) { throw failure(INTEGRITY_FAILURE, "invalid UTF-8", error); }
                }
            };
        }
    }
    private static void write(DataOutputStream out, Object type, Object value) throws IOException {
        if (type instanceof Map<?, ?>) {
            var spec = object(type);
            if (spec.containsKey("optional")) { out.writeByte(value == null ? 0 : 1); if (value != null) write(out, spec.get("optional"), value); }
            else if (spec.containsKey("array")) { var items = list(value); out.writeInt(items.size()); for (Object item : items) write(out, spec.get("array"), item); }
            else for (var field : object(spec.get("object")).entrySet()) write(out, field.getValue(), object(value).get(field.getKey()));
            return;
        }
        String name = (String) type;
        switch (name) {
            case "hash" -> out.write(HexFormat.of().parseHex((String) value));
            case "uuid" -> { var uuid = UUID.fromString((String) value); out.writeLong(uuid.getMostSignificantBits()); out.writeLong(uuid.getLeastSignificantBits()); }
            case "positive", "counter" -> out.writeLong(integer(value));
            case "u8" -> out.writeByte((int) integer(value));
            default -> { byte[] bytes = name.equals("blob") || name.startsWith("frame:") ? unbase(value) : ((String) value).getBytes(StandardCharsets.UTF_8); out.writeInt(bytes.length); out.write(bytes); }
        }
    }

    static void ballot(Map<String, Object> value) {
        long epoch = number(value, "epoch"); Object proposer = value.get("proposer"); String incarnation = text(value, "incarnation");
        need(epoch == 1 ? proposer == null && ZERO.equals(incarnation) : epoch > 1 && proposer != null && !ZERO.equals(incarnation), "ballot identity");
    }
    static List<String> nodes(Map<String, Object> manifest) { return list(manifest.get("members")).stream().map(v -> text(object(v), "node")).toList(); }
    static void context(Record record, Record manifest) {
        var value = record.value(); var nodes = nodes(manifest.value());
        if (value.containsKey("manifestDigest")) need(manifest.digest().equals(value.get("manifestDigest")), "foreign manifest");
        if (value.containsKey("node")) need(nodes.contains(value.get("node")), "foreign node");
        if (List.of("PROMISE", "ACCEPT", "PROOF").contains(record.name()) && number(value, "epoch") > 1)
            need(nodes.get((int) ((number(value, "epoch") - 2) % 3)).equals(value.get("proposer")), "ranked ballot owner");
        if (record.name().equals("PROOF")) for (Object r : list(value.get("receipts"))) need(nodes.contains(object(r).get("voter")), "foreign receipt voter");
        if (record.name().equals("MANIFEST")) need(record.digest().equals(manifest.digest()), "nested manifest bytes");
        if (record.name().equals("GENESIS")) need(value.get("groupId").equals(manifest.value().get("groupId")), "genesis group");
        for (String key : List.of("ballot", "sourceBallot")) if (value.get(key) != null) {
            var b = object(value.get(key)); ballot(b);
            if (number(b, "epoch") > 1) need(nodes.get((int) ((number(b, "epoch") - 2) % 3)).equals(b.get("proposer")), "ranked nested ballot");
        }
        if (record.name().equals("SELECTED")) {
            var voters = list(value.get("bases")).stream().map(v -> object(v).get("node")).toList();
            need(nodes.containsAll(voters) && voters.contains(object(value.get("ballot")).get("proposer")), "selection quorum identity");
        }
        walkContext(object(CATALOG.get(record.name())).get("schema"), value, manifest);
    }
    static void walkContext(Object schema, Object value, Record manifest) {
        if (schema instanceof Map<?, ?>) {
            var s = object(schema);
            if (s.containsKey("optional")) { if (value != null) walkContext(s.get("optional"), value, manifest); }
            else if (s.containsKey("object")) object(s.get("object")).forEach((k, t) -> walkContext(t, object(value).get(k), manifest));
            else if (s.containsKey("array")) for (Object item : list(value)) walkContext(s.get("array"), item, manifest);
        } else if (((String) schema).startsWith("frame:")) context(decode(unbase(value), ((String) schema).substring(6)), manifest);
    }

    static String receipt(String domain, String manifest, String voter, Map<String, Object> ballot, long index, String digest) {
        var bytes = new ByteArrayOutputStream();
        try (var out = new DataOutputStream(bytes)) {
            write(out, "text", "gse-replication/1.2/" + domain); write(out, "hash", manifest); write(out, "node", voter);
            out.writeLong(number(ballot, "epoch")); write(out, "node", ballot.get("proposer")); write(out, "uuid", ballot.get("incarnation"));
            out.writeLong(index); write(out, "hash", digest);
        } catch (IOException impossible) { throw new IllegalStateException(impossible); }
        return sha(bytes.toByteArray());
    }
    private static void semantics(String name, Map<String, Object> v) {
        if (List.of("PROMISE", "ACCEPT", "PROOF").contains(name)) ballot(v);
        if (name.equals("MANIFEST")) {
            need(nodes(v).stream().distinct().count() == 3, "duplicate voters");
            need(list(v.get("members")).stream().map(x -> object(x).get("host") + ":" + object(x).get("port")).distinct().count() == 3, "duplicate endpoints");
        }
        if (name.equals("ENTRY")) {
            need(number(v, "originEpoch") >= 2 && !ZERO.equals(v.get("originIncarnation")), "entry origin");
            long op = number(v, "operation"); need(op >= 1 && op <= 10, "entry operation");
            need(number(v, "previousIndex") == number(v, "index") - 1 && number(v, "previousEpoch") <= number(v, "originEpoch"), "entry predecessor");
            byte[] payload = unbase(v.get("payload")); need(sha(payload).equals(v.get("payloadDigest")) && (op <= 8 || payload.length == 0), "entry payload");
        }
        if (name.equals("ACCEPT")) {
            var entry = decode(unbase(v.get("entry")), "ENTRY");
            need(v.get("manifestDigest").equals(entry.value().get("manifestDigest")) && entry.digest().equals(v.get("entryDigest"))
                    && number(v, "epoch") >= number(entry.value(), "originEpoch"), "acceptance origin/identity");
        }
        if (name.equals("PROOF")) {
            var voters = list(v.get("receipts")).stream().map(x -> text(object(x), "voter")).toList();
            need(voters.equals(voters.stream().distinct().sorted().toList()), "ordered distinct quorum");
            for (Object item : list(v.get("receipts"))) {
                var r = object(item); need(r.get("digest").equals(receipt("ACCEPT_ACK", text(v, "manifestDigest"), text(r, "voter"), v,
                        number(v, "index"), text(v, "entryDigest"))), "accept receipt digest/domain");
            }
        }
        if (name.equals("SNAPSHOT")) AutomaticRecovery.snapshotSemantics(v);
        if (name.equals("IMAGE")) AutomaticRecovery.imageSemantics(v);
        if (name.equals("BASIS") || name.equals("SELECTED") || name.equals("TRANSFER")) ballot(object(v.get("ballot")));
        if (name.equals("SELECTED")) {
            need(list(v.get("bases")).stream().map(x -> object(x).get("node")).distinct().count() == 2, "selection needs two voters");
            need((v.get("nextEntry") == null) == (v.get("sourceBallot") == null), "selected optional pair");
        }
        if (name.equals("FLOOR")) need(list(v.get("sources")).stream().map(x -> object(x).get("node")).distinct().count() == 2, "floor needs two sources");
        if (name.equals("TRANSFER")) need(number(v, "receivedBytes") <= number(v, "imageBytes"), "transfer progress");
        if (name.equals("CLEANUP")) {
            var files = list(v.get("files")).stream().map(x -> object(x).get("path")).toList(); var deletes = list(v.get("deletePaths"));
            need(files.stream().distinct().count() == files.size() && deletes.stream().distinct().count() == deletes.size() && files.containsAll(deletes), "cleanup inventory");
        }
        if (name.equals("PLAN")) AutomaticAdmission.checkPlan(v);
        if (name.equals("RECEIPT")) AutomaticAdmission.checkReceipt(v);
        if (name.equals("SEAL")) {
            var receipt = decode(unbase(v.get("receipt")), "RECEIPT");
            need(list(receipt.value().get("preparations")).stream().map(p -> decode(unbase(p), "PREPARED").value().get("node")).toList().contains(v.get("node")), "seal voter");
        }
    }
}
