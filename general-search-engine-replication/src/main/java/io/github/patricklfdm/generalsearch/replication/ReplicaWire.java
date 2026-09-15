package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.UUID;

final class ReplicaWire {
    // Historical internal nodes keep 1.0; sealed public nodes use only 1.1.
    private static final String PROTOCOL = "gse-replication/1.0";
    static final List<String> TYPES = List.of("HANDSHAKE", "ACTIVATION_PROMISE", "APPEND", "DURABLE_ACK",
            "COMMIT_PROOF", "COMMIT_PROOF_ACK", "COMMIT_ADVANCE", "CONFLICT", "AUTHORITY_STATUS_PROBE",
            "SNAPSHOT_OFFER", "SNAPSHOT_CHUNK", "SNAPSHOT_INSTALL", "ACTIVATE_EPOCH", "AUTHORITY_STATUS", "SNAPSHOT_ABORT", "REJECT");
    private static final Set<String> FIELDS = Set.of("protocol", "groupId", "configurationId", "sender", "recipient",
            "epoch", "incarnationId", "traceId", "eventSequence", "type", "payload");
    private ReplicaWire() { }

    static byte[] encode(Map<String, Object> message, int maximum) {
        validate(message);
        byte[] body = ReplicaJson.encode(message, maximum - HEADER_BYTES);
        byte[] prefix = ByteBuffer.allocate(16).putInt(0x47535250).putShort((short) 1).putShort((short) minor(message))
                .putShort((short) (TYPES.indexOf(string(message, "type")) + 1)).putShort((short) 0).putInt(body.length).array();
        byte[] checked = new byte[16 + body.length];
        System.arraycopy(prefix, 0, checked, 0, 16);
        System.arraycopy(body, 0, checked, 16, body.length);
        return ByteBuffer.allocate(HEADER_BYTES + body.length).put(prefix)
                .put(HexFormat.of().parseHex(sha256(checked))).put(body).array();
    }

    static int bodyLength(byte[] header, int maximum) {
        require(header.length == HEADER_BYTES, INTEGRITY_FAILURE, "incomplete wire header");
        var input = ByteBuffer.wrap(header);
        require(input.getInt() == 0x47535250 && input.getShort() == 1,
                PROTOCOL_MISMATCH, "unsupported wire family/version");
        int minor = Short.toUnsignedInt(input.getShort());
        require(minor <= 1, PROTOCOL_MISMATCH, "unsupported wire minor version");
        int type = Short.toUnsignedInt(input.getShort());
        require(type >= 1 && type <= TYPES.size() && input.getShort() == 0, PROTOCOL_MISMATCH, "unknown wire type/flags");
        int length = input.getInt();
        require(length > 0 && (long) length + HEADER_BYTES <= maximum, CAPACITY_EXCEEDED, "wire frame exceeds bound");
        return length;
    }

    static Map<String, Object> decode(byte[] frame, int maximum) {
        require(frame.length >= HEADER_BYTES && frame.length <= maximum, CAPACITY_EXCEEDED, "wire frame exceeds bound");
        int length = bodyLength(Arrays.copyOf(frame, HEADER_BYTES), maximum);
        require(length == frame.length - HEADER_BYTES, INTEGRITY_FAILURE, "incomplete/trailing wire bytes");
        byte[] checked = new byte[length + 16];
        System.arraycopy(frame, 0, checked, 0, 16);
        System.arraycopy(frame, HEADER_BYTES, checked, 16, length);
        require(MessageDigest.isEqual(Arrays.copyOfRange(frame, 16, HEADER_BYTES), HexFormat.of().parseHex(sha256(checked))),
                INTEGRITY_FAILURE, "wire checksum mismatch");
        var message = object(ReplicaJson.decode(Arrays.copyOfRange(frame, HEADER_BYTES, frame.length), maximum - HEADER_BYTES));
        validate(message);
        require(ByteBuffer.wrap(frame).getShort(6) == minor(message), PROTOCOL_MISMATCH, "wire header/protocol mismatch");
        require(TYPES.indexOf(string(message, "type")) + 1 == Short.toUnsignedInt(ByteBuffer.wrap(frame).getShort(8)),
                PROTOCOL_MISMATCH, "wire type mismatch");
        return message;
    }

    static Map<String, Object> message(ReplicaManifest manifest, ReplicationNodeId sender, ReplicationNodeId recipient,
                                       long epoch, UUID incarnation, String type, Map<String, Object> payload,
                                       UUID trace, long sequence) {
        var value = new TreeMap<String, Object>();
        value.put("protocol", manifest.protocol());
        if (manifest.formatMinor() == 1) value.put("manifestDigest", manifest.digest());
        value.put("groupId", manifest.groupId().value().toString());
        value.put("configurationId", manifest.configurationId());
        value.put("sender", sender.value()); value.put("recipient", recipient.value());
        value.put("epoch", epoch); value.put("incarnationId", incarnation.toString());
        value.put("traceId", trace.toString()); value.put("eventSequence", sequence);
        value.put("type", type); value.put("payload", payload);
        return value;
    }

    static void identity(Map<String, Object> message, ReplicaManifest manifest, ReplicationNodeId local) {
        require(string(message, "protocol").equals(manifest.protocol()) && !string(message, "sender").equals(local.value())
                        && string(message, "groupId").equals(manifest.groupId().value().toString())
                        && string(message, "configurationId").equals(manifest.configurationId())
                        && string(message, "recipient").equals(local.value())
                        && manifest.members().stream().anyMatch(member -> member.nodeId().value().equals(string(message, "sender")))
                        && string(manifest.formatMinor() == 1 ? message : object(message.get("payload")), "manifestDigest").equals(manifest.digest()),
                PROTOCOL_MISMATCH, "wire group/member/manifest mismatch");
    }

    private static void validate(Map<String, Object> value) {
        int minor = minor(value);
        var expected = new java.util.HashSet<>(FIELDS);
        if (minor == 1) expected.add("manifestDigest");
        require(value.keySet().equals(expected)
                && TYPES.contains(string(value, "type")), PROTOCOL_MISMATCH, "invalid wire envelope");
        for (String field : List.of("groupId", "incarnationId", "traceId")) {
            try { require(UUID.fromString(string(value, field)).toString().equals(string(value, field)), PROTOCOL_MISMATCH, "noncanonical UUID"); }
            catch (IllegalArgumentException error) { throw failure(PROTOCOL_MISMATCH, "invalid wire UUID", error); }
        }
        for (String field : List.of("configurationId", "sender", "recipient"))
            require(string(value, field).matches("[a-z0-9][a-z0-9._-]{0,127}"), PROTOCOL_MISMATCH, "invalid wire identity");
        require(number(value, "epoch") >= 0 && number(value, "eventSequence") >= 0, PROTOCOL_MISMATCH, "negative wire counter");
        require(number(value, "epoch") > 0 || Set.of("HANDSHAKE", "REJECT").contains(string(value, "type")),
                PROTOCOL_MISMATCH, "invalid zero epoch");
        var payload = object(value.get("payload"));
        if (minor == 1) {
            validHash(string(value, "manifestDigest"));
            require(!payload.containsKey("manifestDigest"), PROTOCOL_MISMATCH, "duplicate payload identity");
        }
    }

    private static int minor(Map<String, Object> message) {
        String protocol = string(message, "protocol");
        require(protocol.equals(PROTOCOL) || protocol.equals("gse-replication/1.1"), PROTOCOL_MISMATCH, "unsupported wire protocol");
        return protocol.equals(PROTOCOL) ? 0 : 1;
    }

    static String string(Map<String, Object> value, String key) {
        require(value.get(key) instanceof String, PROTOCOL_MISMATCH, "missing string: " + key);
        return (String) value.get(key);
    }
    static long number(Map<String, Object> value, String key) {
        Object number = value.get(key);
        require(number instanceof Long || number instanceof Integer, PROTOCOL_MISMATCH, "missing integer: " + key);
        return ((Number) number).longValue();
    }
    @SuppressWarnings("unchecked")
    static Map<String, Object> object(Object value) {
        require(value instanceof Map<?, ?>, PROTOCOL_MISMATCH, "expected wire object");
        return (Map<String, Object>) value;
    }
    static void fields(Map<String, Object> payload, String... names) {
        var expected = new java.util.HashSet<>(List.of(names)); expected.add("manifestDigest");
        require(payload.keySet().equals(expected), PROTOCOL_MISMATCH, "unexpected payload fields");
    }
}
