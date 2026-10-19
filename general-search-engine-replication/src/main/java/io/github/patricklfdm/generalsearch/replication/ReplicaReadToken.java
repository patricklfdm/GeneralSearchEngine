package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Objects;
import java.util.UUID;
import static io.github.patricklfdm.generalsearch.replication.ReplicaReadException.Reason.*;

/**
 * Immutable history-bound lower bound, not an authenticated commit certificate.
 * The manifest digest is the verified GSER manifest's embedded record digest.
 * Log position and application sequence are distinct. No retained snapshot or
 * wall-clock expiry is attached to this value.
 */
public record ReplicaReadToken(int version, ReplicationGroupId groupId,
        UUID historyId, String manifestDigest, long index) {
    private static final int SIZE = 112;
    private static final int MAGIC = 0x47535254;
    private static final byte[] DOMAIN = "gse-replica-read-token/1\0".getBytes(StandardCharsets.US_ASCII);

    public ReplicaReadToken {
        if (version != 1) throw new ReplicaReadException(UNSUPPORTED_TOKEN_VERSION, "unsupported read token version");
        if (groupId == null || historyId == null || manifestDigest == null
                || !manifestDigest.matches("[0-9a-f]{64}") || index < 0)
            throw new ReplicaReadException(INVALID_TOKEN, "invalid read token components");
    }

    /** Returns a new fixed-length, big-endian client-token encoding. */
    public byte[] encode() {
        var output = ByteBuffer.allocate(SIZE);
        output.putInt(MAGIC).put((byte) version).put(new byte[3]);
        output.putLong(groupId.value().getMostSignificantBits()).putLong(groupId.value().getLeastSignificantBits());
        output.putLong(historyId.getMostSignificantBits()).putLong(historyId.getLeastSignificantBits());
        output.put(HexFormat.of().parseHex(manifestDigest)).putLong(index);
        output.put(checksum(output.array()));
        return output.array();
    }

    /** Decodes exactly 112 bytes without IO; never accepts an unknown version. */
    public static ReplicaReadToken decode(byte[] encoded) {
        Objects.requireNonNull(encoded, "encoded");
        if (encoded.length != SIZE) throw new ReplicaReadException(INVALID_TOKEN, "read token length");
        byte[] bytes = encoded.clone();
        var input = ByteBuffer.wrap(bytes);
        if (input.getInt() != MAGIC) throw new ReplicaReadException(INVALID_TOKEN, "read token magic");
        int version = Byte.toUnsignedInt(input.get());
        if (version != 1) throw new ReplicaReadException(UNSUPPORTED_TOKEN_VERSION, "unsupported read token version");
        if (input.get() != 0 || input.get() != 0 || input.get() != 0
                || !MessageDigest.isEqual(Arrays.copyOfRange(bytes, 80, SIZE), checksum(bytes)))
            throw new ReplicaReadException(INVALID_TOKEN, "read token flags or checksum");
        var group = new ReplicationGroupId(new UUID(input.getLong(), input.getLong()));
        var history = new UUID(input.getLong(), input.getLong());
        byte[] digest = new byte[32]; input.get(digest);
        return new ReplicaReadToken(version, group, history, HexFormat.of().formatHex(digest), input.getLong());
    }

    private static byte[] checksum(byte[] bytes) {
        try {
            var digest = MessageDigest.getInstance("SHA-256");
            digest.update(DOMAIN); digest.update(bytes, 0, 80); return digest.digest();
        } catch (NoSuchAlgorithmException impossible) { throw new AssertionError(impossible); }
    }
}
