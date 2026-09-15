package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

/** Received commit proof; never creates a quorum or completes an application operation. */
record ReplicaProof(String manifestDigest, long epoch, UUID incarnation, long index,
                    String entryDigest, String previousDigest, List<Receipt> receipts) {
    record Receipt(ReplicationNodeId voter, String digest) {
        Receipt {
            Objects.requireNonNull(voter, "voter");
            validHash(digest);
        }
    }

    ReplicaProof {
        validHash(manifestDigest);
        validHash(entryDigest);
        validHash(previousDigest);
        Objects.requireNonNull(incarnation, "incarnation");
        receipts = List.copyOf(receipts);
        if (epoch < 2 || index < 1 || incarnation.equals(NO_INCARNATION)
                || receipts.size() < 2 || receipts.size() > 3) {
            throw new IllegalArgumentException("invalid commit proof identity/quorum");
        }
        for (int i = 1; i < receipts.size(); i++) {
            if (receipts.get(i - 1).voter().compareTo(receipts.get(i).voter()) >= 0) {
                throw new IllegalArgumentException("receipt voters must be distinct and sorted");
            }
        }
    }

    byte[] encode() {
        return frame(PROOF, body(output -> {
            hash(output, manifestDigest);
            output.writeLong(epoch);
            uuid(output, incarnation);
            output.writeLong(index);
            hash(output, entryDigest);
            hash(output, previousDigest);
            output.writeInt(receipts.size());
            for (Receipt receipt : receipts) {
                text(output, receipt.voter().value());
                hash(output, receipt.digest());
            }
        }), MAX_METADATA_BYTES);
    }

    static ReplicaProof decode(byte[] body) throws IOException {
        var input = input(body);
        String manifest = hash(input);
        long epoch = input.readLong();
        UUID incarnation = uuid(input);
        long index = input.readLong();
        String entry = hash(input), previous = hash(input);
        int count = input.readInt();
        require(count >= 2 && count <= 3, ReplicationException.Reason.INTEGRITY_FAILURE,
                "invalid commit-proof voter count");
        var receipts = new ArrayList<Receipt>();
        for (int i = 0; i < count; i++) {
            receipts.add(new Receipt(new ReplicationNodeId(text(input, 64)), hash(input)));
        }
        end(input);
        return new ReplicaProof(manifest, epoch, incarnation, index, entry, previous, receipts);
    }

    static Receipt acknowledgement(ReplicationNodeId voter, ReplicaEntry entry, String entryDigest) {
        String digest = sha256(body(output -> {
            text(output, "gse-replication/1.0/DURABLE_ACK");
            hash(output, entry.manifestDigest());
            text(output, voter.value());
            output.writeLong(entry.epoch());
            uuid(output, entry.incarnation());
            output.writeLong(entry.index());
            hash(output, entryDigest);
        }));
        return new Receipt(voter, digest);
    }
}
