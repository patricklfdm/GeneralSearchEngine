package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;

import java.io.IOException;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

/** Deterministic opaque payload; application codecs and apply belong to Phase 3. */
record ReplicaEntry(String manifestDigest, long epoch, UUID incarnation, long index,
                    String operation, long previousEpoch, long previousIndex,
                    String previousDigest, byte[] payload) {
    static final List<String> OPERATIONS = List.of("ADD", "UPDATE", "REMOVE", "ADD_ALL",
            "UPDATE_ALL", "REMOVE_ALL", "INDEX_CREATE", "INDEX_DROP", "NO_OP", "SNAPSHOT_MARKER");

    ReplicaEntry {
        validHash(manifestDigest);
        validHash(previousDigest);
        Objects.requireNonNull(incarnation, "incarnation");
        Objects.requireNonNull(payload, "payload");
        if (epoch < 2 || incarnation.equals(NO_INCARNATION) || index < 1 || previousEpoch < 1
                || previousEpoch > epoch || previousIndex != index - 1 || !OPERATIONS.contains(operation)) {
            throw new IllegalArgumentException("invalid replicated entry identity/type/predecessor");
        }
        if (payload.length > ReplicationBounds.HARD_MAX_FRAME_BYTES - 197) {
            throw new IllegalArgumentException("entry payload exceeds absolute frame bound");
        }
        payload = payload.clone();
    }

    @Override
    public byte[] payload() {
        return payload.clone();
    }

    byte[] encode(int maximum) {
        // Fixed envelope and entry fields occupy 197 bytes, including payload length/digest.
        require((long) payload.length + 197 <= maximum, ReplicationException.Reason.CAPACITY_EXCEEDED,
                "entry payload exceeds frame bound");
        return frame(ENTRY, body(output -> {
            hash(output, manifestDigest);
            output.writeLong(epoch);
            uuid(output, incarnation);
            output.writeLong(index);
            output.writeByte(OPERATIONS.indexOf(operation) + 1);
            output.writeLong(previousEpoch);
            output.writeLong(previousIndex);
            hash(output, previousDigest);
            output.writeInt(payload.length);
            hash(output, sha256(payload));
            output.write(payload);
        }), maximum);
    }

    static ReplicaEntry decode(byte[] body) throws IOException {
        var input = input(body);
        String manifest = hash(input);
        long epoch = input.readLong();
        UUID incarnation = uuid(input);
        long index = input.readLong();
        int type = input.readUnsignedByte();
        require(type >= 1 && type <= OPERATIONS.size(), ReplicationException.Reason.INTEGRITY_FAILURE,
                "unknown/reserved entry type");
        long previousEpoch = input.readLong(), previousIndex = input.readLong();
        String previousDigest = hash(input);
        int length = input.readInt();
        String payloadDigest = hash(input);
        require(length >= 0 && length == input.available(), ReplicationException.Reason.INTEGRITY_FAILURE,
                "invalid entry payload length");
        byte[] payload = input.readNBytes(length);
        require(sha256(payload).equals(payloadDigest), ReplicationException.Reason.INTEGRITY_FAILURE,
                "entry payload checksum mismatch");
        return new ReplicaEntry(manifest, epoch, incarnation, index, OPERATIONS.get(type - 1),
                previousEpoch, previousIndex, previousDigest, payload);
    }
}
