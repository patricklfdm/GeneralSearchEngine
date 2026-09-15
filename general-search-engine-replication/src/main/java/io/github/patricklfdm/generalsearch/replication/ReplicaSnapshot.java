package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** Immutable application cut plus bounded ancestry; original payloads are not retained. */
record ReplicaSnapshot(String manifestDigest, List<Anchor> anchors, ReplicaProof proof, byte[] application,
                       long baseSequence, int formatMinor) {
    ReplicaSnapshot(String manifestDigest, List<Anchor> anchors, ReplicaProof proof, byte[] application) {
        this(manifestDigest, anchors, proof, application, 0, 0);
    }
    static final int KIND = 8, MAX_BYTES = 64 * 1024 * 1024;
    record Anchor(long epoch, UUID incarnation, String operation, String digest, String payloadDigest) {
        Anchor {
            validHash(digest); validHash(payloadDigest);
            require(epoch >= 2 && incarnation != null && !incarnation.equals(NO_INCARNATION)
                    && ReplicaEntry.OPERATIONS.contains(operation), INTEGRITY_FAILURE, "invalid snapshot ancestor");
        }
        static Anchor of(ReplicaEntry entry, int maximum) {
            return new Anchor(entry.epoch(), entry.incarnation(), entry.operation(),
                    frameDigest(entry.encode(maximum)), sha256(entry.payload()));
        }
    }
    ReplicaSnapshot {
        validHash(manifestDigest);
        require((formatMinor == 0 || formatMinor == 1) && baseSequence >= 0 && baseSequence < Long.MAX_VALUE
                        && (formatMinor != 0 || baseSequence == 0), INTEGRITY_FAILURE, "invalid snapshot base/version");
        anchors = List.copyOf(anchors); application = application.clone();
        require(anchors.size() <= MAX_ENTRIES && application.length <= MAX_BYTES, CAPACITY_EXCEEDED, "snapshot capacity exceeded");
        require(anchors.isEmpty() == (proof == null), INTEGRITY_FAILURE, "snapshot requires its terminal proof");
        long epoch = 1;
        UUID incarnation = NO_INCARNATION;
        for (var anchor : anchors) {
            require(anchor.epoch() >= epoch && (anchor.epoch() > epoch || anchor.incarnation().equals(incarnation)), CONFLICTING_HISTORY, "snapshot ancestry epoch/incarnation conflicts");
            epoch = anchor.epoch(); incarnation = anchor.incarnation();
        }
    }
    @Override public byte[] application() { return application.clone(); }
    long index() { return anchors.size(); }
    long sequence() { return Math.addExact(baseSequence, anchors.stream().filter(a -> !List.of("NO_OP", "SNAPSHOT_MARKER").contains(a.operation())).count()); }
    String digestAt(long index) { return index == 0 ? manifestDigest : anchors.get(Math.toIntExact(index - 1)).digest(); }
    long epochAt(long index) { return index == 0 ? 1 : anchors.get(Math.toIntExact(index - 1)).epoch(); }
    void validate(ReplicaManifest manifest) {
        require(manifest.digest().equals(manifestDigest) && manifest.formatMinor() == formatMinor
                && manifest.baseSequence() == baseSequence, PROTOCOL_MISMATCH, "snapshot manifest/base mismatch");
        if (proof != null) validateProof(manifest, proof, index(), anchors.getLast(), digestAt(index() - 1));
    }
    static void validateProof(ReplicaManifest manifest, ReplicaProof proof, long index, Anchor anchor, String previous) {
        require(proof.manifestDigest().equals(manifest.digest()) && proof.formatMinor() == manifest.formatMinor() && proof.index() == index
                && proof.epoch() == anchor.epoch() && proof.incarnation().equals(anchor.incarnation())
                && proof.entryDigest().equals(anchor.digest()) && proof.previousDigest().equals(previous),
                CONFLICTING_HISTORY, "proof disagrees with recovery ancestry");
        for (var receipt : proof.receipts()) {
            require(manifest.contains(receipt.voter()), PROTOCOL_MISMATCH, "unknown proof voter");
            String expected = sha256(body(out -> {
                text(out, manifest.protocol() + "/DURABLE_ACK"); hash(out, manifest.digest()); text(out, receipt.voter().value());
                out.writeLong(anchor.epoch()); uuid(out, anchor.incarnation()); out.writeLong(index); hash(out, anchor.digest());
            }));
            require(receipt.digest().equals(expected), INTEGRITY_FAILURE, "invalid recovery receipt");
        }
    }
    byte[] encode(int maximum) {
        return frame(KIND, body(out -> {
            hash(out, manifestDigest);
            if (formatMinor == 1) { out.writeLong(baseSequence); out.writeLong(sequence()); }
            out.writeInt(anchors.size());
            for (var anchor : anchors) {
                out.writeLong(anchor.epoch()); uuid(out, anchor.incarnation());
                out.writeByte(ReplicaEntry.OPERATIONS.indexOf(anchor.operation()) + 1);
                hash(out, anchor.digest()); hash(out, anchor.payloadDigest());
                require(out.size() <= maximum - HEADER_BYTES, CAPACITY_EXCEEDED, "snapshot ancestry exceeds bound");
            }
            blob(out, proof == null ? new byte[0] : proof.encode(), maximum);
            blob(out, application, maximum);
        }), maximum, formatMinor);
    }
    static ReplicaSnapshot decode(byte[] encoded, ReplicaManifest manifest, int maximum) {
        try {
            int minor = manifest.formatMinor();
            var in = input(decodeRecord(encoded, KIND, maximum, minor));
            String digest = hash(in);
            long base = minor == 1 ? in.readLong() : 0, claimed = minor == 1 ? in.readLong() : 0;
            int count = in.readInt();
            require(count >= 0 && count <= MAX_ENTRIES && count <= in.available() / 89, CAPACITY_EXCEEDED, "snapshot ancestry count exceeds bound");
            var anchors = new ArrayList<Anchor>();
            for (int i = 0; i < count; i++) {
                long epoch = in.readLong(); UUID incarnation = uuid(in); int operation = in.readUnsignedByte();
                require(operation >= 1 && operation <= ReplicaEntry.OPERATIONS.size(), INTEGRITY_FAILURE, "unknown snapshot operation");
                anchors.add(new Anchor(epoch, incarnation, ReplicaEntry.OPERATIONS.get(operation - 1), hash(in), hash(in)));
            }
            byte[] proof = blob(in, MAX_METADATA_BYTES), application = blob(in, maximum); end(in);
            var result = new ReplicaSnapshot(digest, anchors, proof.length == 0 ? null
                    : ReplicaProof.decode(decodeRecord(proof, PROOF, MAX_METADATA_BYTES, minor), minor), application, base, minor);
            require(minor == 0 || result.sequence() == claimed, INTEGRITY_FAILURE, "snapshot application sequence mismatch");
            result.validate(manifest); return result;
        } catch (IOException | IllegalArgumentException error) { throw failure(INTEGRITY_FAILURE, "invalid snapshot", error); }
    }
    static int maximum(ReplicationBounds bounds) { return (int) Math.min(MAX_BYTES, bounds.maxSnapshotStagingBytes()); }
    static void blob(java.io.DataOutputStream out, byte[] bytes, int maximum) throws IOException {
        require((long) out.size() + 4 + bytes.length + HEADER_BYTES <= maximum, CAPACITY_EXCEEDED, "recovery image exceeds bound");
        out.writeInt(bytes.length); out.write(bytes);
    }
    static byte[] blob(java.io.DataInputStream in, int maximum) throws IOException {
        int length = in.readInt();
        require(length >= 0 && length <= maximum && length <= in.available(), INTEGRITY_FAILURE, "invalid recovery blob length");
        return in.readNBytes(length);
    }
}
