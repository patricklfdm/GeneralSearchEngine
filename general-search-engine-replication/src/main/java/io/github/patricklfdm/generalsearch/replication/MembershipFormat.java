package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Bounded 1.3 byte syntax. Contextual authority validation is a separate required step. */
final class MembershipFormat {
    static final int HEADER = 48;
    static final int FRAME = 8 * 1024 * 1024;
    static final Map<String, Object> CATALOG = loadCatalog();
    private MembershipFormat() {}

    record Decoded(String family, String kind, Map<String, Object> value, byte[] bytes) {
        Decoded { bytes = bytes.clone(); value = object(freeze(value)); }
        @Override public byte[] bytes() { return bytes.clone(); }
        String digest() { return hash(bytes); }
        String rootDigest() {
            require(family.equals("records") && kind.equals("ROOT"), "not a ROOT record");
            return HexFormat.of().formatHex(bytes, 16, HEADER);
        }
    }

    static Map<String, Object> object(Object value) {
        require(value instanceof Map<?, ?>, "expected object");
        @SuppressWarnings("unchecked") var result = (Map<String, Object>) value;
        return result;
    }
    static long number(Object value) {
        require(value instanceof Long || value instanceof Integer, "expected integer");
        return ((Number) value).longValue();
    }
    static List<?> list(Object value) { require(value instanceof List<?>, "expected array"); return (List<?>) value; }
    static String hash(byte[] bytes) { return HexFormat.of().formatHex(sha(bytes)); }
    static byte[] sha(byte[]... parts) {
        try {
            var digest = MessageDigest.getInstance("SHA-256");
            for (var part : parts) digest.update(part);
            return digest.digest();
        } catch (NoSuchAlgorithmException error) { throw new AssertionError(error); }
    }
    private static Map<String, Object> loadCatalog() {
        try (var stream = MembershipFormat.class.getResourceAsStream("/replication/membership-format-v13.json")) {
            if (stream == null) throw new IllegalStateException("missing membership schema");
            byte[] bytes = stream.readNBytes(262145);
            require(bytes.length <= 262144, "schema size");
            var result = object(freeze(ReplicaJson.decode(bytes, 262144)));
            require(object(result.get("records")).size() == 24 && object(result.get("wire")).size() == 21, "schema inventory");
            return result;
        } catch (IOException error) { throw new ExceptionInInitializerError(error); }
    }
    private static Map<String, Object> spec(String family, String name) {
        require(family.equals("records") || family.equals("wire"), "unknown format family");
        var result = object(CATALOG.get(family)).get(name);
        require(result != null, "unknown format kind"); return object(result);
    }
    private static int magic(String family) { return family.equals("records") ? 0x47534552 : 0x47535250; }

    /** Checks untrusted length/version before any payload allocation or read. */
    static int header(byte[] bytes, String family, String kind) {
        var shape = spec(family, kind); require(bytes.length >= HEADER, "truncated header");
        var input = ByteBuffer.wrap(bytes);
        require(input.getInt() == magic(family) && input.getShort() == 1 && input.getShort() == 3, "protocol mismatch");
        require(Short.toUnsignedInt(input.getShort()) == number(shape.get("id")) && input.getShort() == 0, "kind/flags mismatch");
        long length = Integer.toUnsignedLong(input.getInt());
        require(length > 0 && length <= number(shape.get("maximum")) - HEADER, "frame capacity");
        return Math.toIntExact(length);
    }
    static Decoded read(InputStream stream, String family, String kind) throws IOException {
        Objects.requireNonNull(stream, "stream");
        byte[] prefix = stream.readNBytes(HEADER); int length = header(prefix, family, kind);
        byte[] bytes = Arrays.copyOf(prefix, HEADER + length);
        int offset = HEADER;
        while (offset < bytes.length) {
            int count = stream.read(bytes, offset, bytes.length - offset);
            if (count < 0) throw new EOFException("truncated membership frame");
            if (count == 0) { int one = stream.read(); if (one < 0) throw new EOFException("truncated membership frame"); bytes[offset++] = (byte) one; }
            else offset += count;
        }
        return decode(bytes, family, kind);
    }
    static byte[] encode(String family, String name, Map<String, Object> value) {
        var shape = spec(family, name);
        checkType(value, shape.get("schema"));
        byte[] body = canonical(value, Math.toIntExact(number(shape.get("maximum"))) - HEADER);
        var output = ByteBuffer.allocate(HEADER + body.length);
        output.putInt(magic(family)).putShort((short) 1).putShort((short) 3)
                .putShort((short) number(shape.get("id"))).putShort((short) 0).putInt(body.length);
        byte[] prefix = Arrays.copyOf(output.array(), 16);
        output.put(sha(prefix, body)).put(body); return output.array();
    }
    static Decoded decode(byte[] bytes, String family, String name) {
        Objects.requireNonNull(bytes, "bytes");
        int length = header(bytes, family, name); require(length == bytes.length - HEADER, "frame length");
        byte[] body = Arrays.copyOfRange(bytes, HEADER, bytes.length);
        require(MessageDigest.isEqual(Arrays.copyOfRange(bytes, 16, HEADER), sha(Arrays.copyOf(bytes, 16), body)), "frame checksum");
        parserBudget(body);
        var value = object(ReplicaJson.decode(body, length)); checkType(value, spec(family, name).get("schema"));
        return new Decoded(family, name, value, bytes);
    }
    static byte[] canonical(Object value, int maximum) {
        byte[] result = ReplicaJson.encode(value, maximum); parserBudget(result); return result;
    }
    static Object parse(byte[] bytes, int maximum) {
        require(bytes.length <= maximum, "JSON capacity"); parserBudget(bytes); return freeze(ReplicaJson.decode(bytes, maximum));
    }

    /** Counts keys as tokens and checks depth before the JSON object graph is allocated. */
    static void parserBudget(byte[] bytes) {
        int depth = 0, tokens = 0;
        for (int i = 0; i < bytes.length;) {
            int c = bytes[i++] & 255; require(c < 128, "non-ASCII JSON");
            if (c == ' ' || c == '\n' || c == '\r' || c == '\t' || c == ',' || c == ':') continue;
            if (c == '}' || c == ']') { require(--depth >= 0, "unbalanced JSON"); continue; }
            require(++tokens <= 65536, "JSON token budget");
            if (c == '{' || c == '[') { require(++depth <= 16, "JSON depth budget"); continue; }
            if (c == '"') {
                boolean ended = false;
                while (i < bytes.length) {
                    c = bytes[i++] & 255; require(c < 128, "non-ASCII JSON string");
                    if (c == '"') { ended = true; break; }
                    if (c == '\\') { require(i < bytes.length && bytes[i] >= 0, "truncated/non-ASCII escape"); i++; }
                }
                require(ended, "unterminated JSON string");
            } else while (i < bytes.length && bytes[i] != ',' && bytes[i] != '}' && bytes[i] != ']'
                    && bytes[i] != ':' && bytes[i] != ' ' && bytes[i] != '\n' && bytes[i] != '\r' && bytes[i] != '\t') {
                require(bytes[i++] >= 0, "non-ASCII JSON scalar");
            }
        }
        require(depth == 0, "unbalanced JSON");
    }

    static void checkType(Object value, Object type) {
        var types = object(CATALOG.get("types"));
        if (type instanceof String name && types.containsKey(name)) { checkType(value, types.get(name)); return; }
        if (type instanceof Map<?, ?>) {
            var shape = object(type);
            if (shape.containsKey("object")) {
                var fields = object(shape.get("object")); var actual = object(value);
                require(actual.keySet().equals(fields.keySet()), "exact fields");
                for (var field : fields.entrySet()) checkType(actual.get(field.getKey()), field.getValue());
            } else if (shape.containsKey("array")) {
                var values = list(value);
                require(values.size() >= number(shape.get("min")) && values.size() <= number(shape.get("max")), "array bound");
                for (var item : values) checkType(item, shape.get("array"));
            } else if (shape.containsKey("nullable")) {
                if (value != null) checkType(value, shape.get("nullable"));
            } else if (shape.containsKey("enum")) require(list(shape.get("enum")).contains(value), "enum value");
            else throw new IllegalArgumentException("unknown schema");
            return;
        }
        String name = (String) type;
        switch (name) {
            case "counter", "positive", "port" -> {
                long n = number(value); require(n >= (name.equals("counter") ? 0 : 1)
                        && n <= (name.equals("port") ? 65535 : Long.MAX_VALUE), "integer range");
            }
            case "bool" -> require(value instanceof Boolean, "boolean");
            default -> {
                require(value instanceof String, "string"); String s = (String) value;
                require(s.chars().allMatch(c -> c < 128), "ASCII scalar");
                switch (name) {
                    case "hash" -> MembershipValidation.digest(s);
                    case "uuid" -> { UUID id = UUID.fromString(s); MembershipValidation.uuid(id); require(id.toString().equals(s), "canonical UUID"); }
                    case "node", "id" -> require(s.matches("[a-z0-9][a-z0-9._-]{0," + (name.equals("node") ? 63 : 127) + "}"), "identifier");
                    case "host" -> { require(!s.isEmpty(), "empty host"); MembershipValidation.host(s); }
                    case "relative" -> {
                        require(!s.isEmpty() && s.length() <= 256 && !s.startsWith("/"), "relative path bound");
                        for (String part : s.split("/", -1)) require(part.matches("[A-Za-z0-9][A-Za-z0-9._-]*"), "relative path component");
                    }
                    case "blob" -> {
                        require(s.length() <= ((4194304 + 2) / 3) * 4, "base64 capacity");
                        byte[] decoded = Base64.getDecoder().decode(s);
                        require(decoded.length <= 4194304 && Base64.getEncoder().encodeToString(decoded).equals(s), "canonical base64");
                    }
                    default -> throw new IllegalArgumentException("unknown scalar");
                }
            }
        }
    }
    private static Object freeze(Object value) {
        if (value instanceof Map<?, ?> values) {
            var result = new TreeMap<String, Object>();
            for (var row : values.entrySet()) result.put((String) row.getKey(), freeze(row.getValue()));
            return Collections.unmodifiableMap(result);
        }
        if (value instanceof List<?> values) {
            var result = new ArrayList<Object>(); for (var item : values) result.add(freeze(item));
            return Collections.unmodifiableList(result);
        }
        return value;
    }
    static byte[] command(String name, Object value) {
        var shape = object(CATALOG.get("commands")); require(shape.containsKey(name), "unknown command");
        if (name.equals("BARRIER")) { require(value == null, "barrier payload"); return new byte[0]; }
        if (name.equals("DATA")) { require(value instanceof byte[] && ((byte[]) value).length <= FRAME, "application payload bound"); return ((byte[]) value).clone(); }
        checkType(value, Map.of("object", shape.get(name))); return canonical(value, 8192);
    }
    static Object command(String name, byte[] bytes) {
        if (name.equals("BARRIER")) { require(bytes.length == 0, "barrier payload"); return null; }
        if (name.equals("DATA")) return command(name, (Object) bytes);
        Object value = parse(bytes, 8192);
        require(Arrays.equals(command(name, value), bytes), "noncanonical command"); return value;
    }
}
