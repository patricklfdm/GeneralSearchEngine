package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/** One validated snapshot and its committed contiguous tail, transferable in bounded chunks. */
record ReplicaRecoveryImage(ReplicaSnapshot snapshot, List<ReplicaEntry> entries, List<ReplicaProof> proofs) {
    static final int KIND = 9;
    ReplicaRecoveryImage { entries = List.copyOf(entries); proofs = List.copyOf(proofs); }
    long index() { return snapshot.index() + entries.size(); }
    String digestAt(long index) {
        require(index >= 0 && index <= index(), CONFLICTING_HISTORY, "recovery ancestor is unavailable");
        return index <= snapshot.index() ? snapshot.digestAt(index)
                : frameDigest(entries.get(Math.toIntExact(index - snapshot.index() - 1)).encode(ReplicationBounds.HARD_MAX_FRAME_BYTES));
    }
    List<ReplicaSnapshot.Anchor> anchors() {
        var result = new ArrayList<>(snapshot.anchors());
        for (var entry : entries) result.add(ReplicaSnapshot.Anchor.of(entry, ReplicationBounds.HARD_MAX_FRAME_BYTES));
        return result;
    }
    void validate(ReplicaManifest manifest, ReplicationBounds bounds) {
        snapshot.validate(manifest);
        require(index() <= MAX_ENTRIES, CAPACITY_EXCEEDED, "recovery ancestry capacity exceeded");
        long index = snapshot.index(), epoch = snapshot.epochAt(index);
        var incarnation = snapshot.anchors().isEmpty() ? NO_INCARNATION : snapshot.anchors().getLast().incarnation();
        String previous = snapshot.digestAt(index);
        for (var entry : entries) {
            require(entry.manifestDigest().equals(manifest.digest()) && entry.index() == index + 1
                    && entry.previousIndex() == index && entry.previousEpoch() == epoch
                    && entry.previousDigest().equals(previous) && entry.epoch() >= epoch
                    && (entry.epoch() > epoch || entry.incarnation().equals(incarnation)),
                    CONFLICTING_HISTORY, "recovery tail is not contiguous");
            index++; epoch = entry.epoch(); incarnation = entry.incarnation(); previous = frameDigest(entry.encode(bounds.maxFrameBytes()));
        }
        long committed = snapshot.index();
        for (var proof : proofs) {
            require(proof.index() > committed && proof.index() <= index, CONFLICTING_HISTORY, "recovery proof order mismatch");
            var entry = entries.get(Math.toIntExact(proof.index() - snapshot.index() - 1));
            ReplicaSnapshot.validateProof(manifest, proof, entry.index(), ReplicaSnapshot.Anchor.of(entry, bounds.maxFrameBytes()), entry.previousDigest());
            committed = proof.index();
        }
        require(committed == index, CONFLICTING_HISTORY, "recovery image contains uncommitted suffix");
    }
    byte[] encode(ReplicationBounds bounds) {
        int maximum = ReplicaSnapshot.maximum(bounds);
        return frame(KIND, body(out -> {
            ReplicaSnapshot.blob(out, snapshot.encode(maximum), maximum);
            out.writeInt(entries.size());
            for (var entry : entries) ReplicaSnapshot.blob(out, entry.encode(bounds.maxFrameBytes()), maximum);
            out.writeInt(proofs.size());
            for (var proof : proofs) ReplicaSnapshot.blob(out, proof.encode(), maximum);
        }), maximum);
    }
    static ReplicaRecoveryImage decode(byte[] bytes, ReplicaManifest manifest, ReplicationBounds bounds) {
        int maximum = ReplicaSnapshot.maximum(bounds);
        try {
            var in = input(decodeRecord(bytes, KIND, maximum));
            var snapshot = ReplicaSnapshot.decode(ReplicaSnapshot.blob(in, maximum), manifest, maximum);
            int count = in.readInt();
            require(count >= 0 && count <= MAX_ENTRIES && count <= in.available() / 4, CAPACITY_EXCEEDED, "recovery entry count exceeds bound");
            var entries = new ArrayList<ReplicaEntry>();
            for (int i = 0; i < count; i++) entries.add(ReplicaEntry.decode(decodeRecord(ReplicaSnapshot.blob(in, bounds.maxFrameBytes()), ENTRY, bounds.maxFrameBytes())));
            count = in.readInt();
            require(count >= 0 && count <= entries.size() && count <= in.available() / 4, CAPACITY_EXCEEDED, "recovery proof count exceeds bound");
            var proofs = new ArrayList<ReplicaProof>();
            for (int i = 0; i < count; i++) proofs.add(ReplicaProof.decode(decodeRecord(ReplicaSnapshot.blob(in, MAX_METADATA_BYTES), PROOF, MAX_METADATA_BYTES)));
            end(in);
            var result = new ReplicaRecoveryImage(snapshot, entries, proofs); result.validate(manifest, bounds); return result;
        } catch (IOException | IllegalArgumentException error) { throw failure(INTEGRITY_FAILURE, "invalid recovery image", error); }
    }
}
