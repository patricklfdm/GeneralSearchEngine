package io.github.patricklfdm.generalsearch.replication;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.UUID;

/** Bounded outer framing shared by replica metadata and journals. */
final class ReplicaFormat {
    static final int MAGIC = 0x47534552; // GSER; deliberately distinct from V4 and wire frames
    static final int HEADER_BYTES = 48;
    static final int MAX_METADATA_BYTES = 64 * 1024;
    static final int MAX_ENTRIES = 1_000_000;
    static final int MAX_PROMISES = 10_000;
    static final int MANIFEST = 1, NODE = 2, JOURNAL = 3, PROMISE = 4, ENTRY = 5, PROOF = 6, READY = 7;
    static final UUID NO_INCARNATION = new UUID(0, 0);

    private ReplicaFormat() { }

    record Frame(int kind, byte[] body, String digest, long nextOffset) { }

    @FunctionalInterface
    interface Encoder {
        void write(DataOutputStream output) throws IOException;
    }

    static byte[] body(Encoder encoder) {
        try {
            var bytes = new ByteArrayOutputStream();
            try (var output = new DataOutputStream(bytes)) {
                encoder.write(output);
            }
            return bytes.toByteArray();
        } catch (IOException error) {
            throw failure(ReplicationException.Reason.STORAGE_FAILURE, "cannot encode replica record", error);
        }
    }

    static byte[] frame(int kind, byte[] body, int maximum) {
        return frame(kind, body, maximum, 0);
    }

    static byte[] frame(int kind, byte[] body, int maximum, int minor) {
        require(minor == 0 || minor == 1, ReplicationException.Reason.PROTOCOL_MISMATCH, "unsupported storage version");
        require(body.length > 0 && (long) body.length + HEADER_BYTES <= maximum,
                ReplicationException.Reason.CAPACITY_EXCEEDED, "replica frame exceeds bound");
        byte[] prefix = ByteBuffer.allocate(16).putInt(MAGIC).putShort((short) 1).putShort((short) minor)
                .putShort((short) kind).putShort((short) 0).putInt(body.length).array();
        byte[] digest = digest(prefix, body);
        return ByteBuffer.allocate(HEADER_BYTES + body.length).put(prefix).put(digest).put(body).array();
    }

    static String frameDigest(byte[] frame) {
        return HexFormat.of().formatHex(frame, 16, HEADER_BYTES);
    }

    static byte[] decodeRecord(byte[] encoded, int kind, int maximum) {
        return decodeRecord(encoded, kind, maximum, 0);
    }

    static byte[] decodeRecord(byte[] encoded, int kind, int maximum, int minor) {
        require(encoded.length >= HEADER_BYTES && encoded.length <= maximum,
                ReplicationException.Reason.CAPACITY_EXCEEDED, "record size exceeds bound");
        var header = ByteBuffer.wrap(encoded);
        require(header.getInt() == MAGIC && header.getShort() == 1 && header.getShort() == minor,
                ReplicationException.Reason.PROTOCOL_MISMATCH, "unsupported storage family/version");
        require(Short.toUnsignedInt(header.getShort()) == kind && header.getShort() == 0,
                ReplicationException.Reason.INTEGRITY_FAILURE, "wrong record kind/flags");
        int length = header.getInt();
        require(length > 0 && length == encoded.length - HEADER_BYTES,
                ReplicationException.Reason.INTEGRITY_FAILURE, "incomplete/trailing record bytes");
        byte[] body = java.util.Arrays.copyOfRange(encoded, HEADER_BYTES, encoded.length);
        require(java.util.Arrays.equals(encoded, frame(kind, body, maximum, minor)),
                ReplicationException.Reason.INTEGRITY_FAILURE, "record checksum mismatch");
        return body;
    }

    static Frame read(FileChannel channel, long offset, int kind, int maximum) throws IOException {
        return read(channel, offset, kind, maximum, 0);
    }

    static Frame read(FileChannel channel, long offset, int kind, int maximum, int minor) throws IOException {
        long remaining = channel.size() - offset;
        if (remaining == 0) {
            return null;
        }
        require(remaining >= HEADER_BYTES, ReplicationException.Reason.INTEGRITY_FAILURE,
                "incomplete replica frame header");
        ByteBuffer header = ByteBuffer.allocate(HEADER_BYTES);
        readFully(channel, header, offset);
        byte[] prefix = java.util.Arrays.copyOf(header.array(), 16);
        header.flip();
        require(header.getInt() == MAGIC && header.getShort() == 1 && header.getShort() == minor,
                ReplicationException.Reason.PROTOCOL_MISMATCH, "unsupported replicated storage family/version");
        require(Short.toUnsignedInt(header.getShort()) == kind && header.getShort() == 0,
                ReplicationException.Reason.INTEGRITY_FAILURE, "invalid replica record kind/flags");
        int length = header.getInt();
        require(length > 0, ReplicationException.Reason.INTEGRITY_FAILURE, "invalid replica body length");
        require((long) length + HEADER_BYTES <= maximum,
                ReplicationException.Reason.CAPACITY_EXCEEDED, "replica frame exceeds bound");
        require((long) length + HEADER_BYTES <= remaining, ReplicationException.Reason.INTEGRITY_FAILURE,
                "incomplete replica frame body");
        byte[] expected = new byte[32];
        header.get(expected);
        byte[] body = new byte[length];
        readFully(channel, ByteBuffer.wrap(body), offset + HEADER_BYTES);
        require(MessageDigest.isEqual(expected, digest(prefix, body)),
                ReplicationException.Reason.INTEGRITY_FAILURE, "replica record checksum mismatch");
        return new Frame(kind, body, HexFormat.of().formatHex(expected), offset + HEADER_BYTES + length);
    }

    private static void readFully(FileChannel channel, ByteBuffer buffer, long offset) throws IOException {
        int stalls = 0;
        while (buffer.hasRemaining()) {
            int read = channel.read(buffer, offset + buffer.position());
            if (read < 0) {
                throw new EOFException("replica record changed during inspection");
            }
            if (read == 0 && ++stalls > 16) {
                throw new IOException("replica read made no progress");
            }
            if (read > 0) {
                stalls = 0;
            }
        }
    }

    static DataInputStream input(byte[] body) {
        return new DataInputStream(new ByteArrayInputStream(body));
    }

    static void end(DataInputStream input) throws IOException {
        require(input.available() == 0, ReplicationException.Reason.INTEGRITY_FAILURE,
                "trailing replica record fields");
    }

    static void text(DataOutputStream output, String value) throws IOException {
        ByteBuffer encoded = StandardCharsets.UTF_8.newEncoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).encode(java.nio.CharBuffer.wrap(value));
        byte[] bytes = new byte[encoded.remaining()];
        encoded.get(bytes);
        output.writeInt(bytes.length);
        output.write(bytes);
    }

    static String text(DataInputStream input, int maximum) throws IOException {
        int length = input.readInt();
        require(length > 0 && length <= maximum && length <= input.available(),
                ReplicationException.Reason.INTEGRITY_FAILURE, "invalid replica string length");
        byte[] bytes = input.readNBytes(length);
        return StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();
    }

    static void uuid(DataOutputStream output, UUID value) throws IOException {
        output.writeLong(value.getMostSignificantBits());
        output.writeLong(value.getLeastSignificantBits());
    }

    static UUID uuid(DataInputStream input) throws IOException {
        return new UUID(input.readLong(), input.readLong());
    }

    static void hash(DataOutputStream output, String value) throws IOException {
        validHash(value);
        output.write(HexFormat.of().parseHex(value));
    }

    static String hash(DataInputStream input) throws IOException {
        byte[] bytes = input.readNBytes(32);
        if (bytes.length != 32) {
            throw new EOFException("incomplete replica digest");
        }
        return HexFormat.of().formatHex(bytes);
    }

    static String sha256(byte[] value) {
        return HexFormat.of().formatHex(digest(value));
    }

    private static byte[] digest(byte[]... parts) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (byte[] part : parts) {
                digest.update(part);
            }
            return digest.digest();
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    static void validHash(String value) {
        if (value == null || !value.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("digest must be lowercase SHA-256");
        }
    }

    static void require(boolean condition, ReplicationException.Reason reason, String message) {
        if (!condition) {
            throw new ReplicationException(reason, message);
        }
    }

    static ReplicationException failure(ReplicationException.Reason reason, String message, Throwable cause) {
        return new ReplicationException(reason, message, cause);
    }
}
