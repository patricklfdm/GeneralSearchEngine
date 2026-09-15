package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** Strict complete-row recovery: no torn tail can establish a publication or deletion decision. */
final class AdmissionJournal {
    record Row(String plan, long sequence, String previous, int phase, List<String> preparations, String receipt) {
        byte[] encode() {
            return record(21, out -> {
                hash(out, plan); out.writeLong(sequence); hash(out, previous); out.writeByte(phase);
                for (String preparation : preparations) hash(out, preparation); hash(out, receipt);
            });
        }
        String digest() { return frameDigest(encode()); }
        Row abort() { return new Row(plan, sequence + 1, digest(), 5, preparations, ZERO); }
    }
    private AdmissionJournal() { }

    static List<Row> read(Path path, AdmissionPlan plan) throws IOException {
        var rows = parse(AdmissionPaths.read(path, 5 * META));
        require(!rows.isEmpty(), INTEGRITY_FAILURE, "operation journal has no durable phase");
        for (int i = 0; i < rows.size(); i++) {
            var row = rows.get(i);
            if (row.phase() == 5) {
                require(i > 0 && i == rows.size() - 1 && rows.get(i - 1).phase() <= 2
                        && row.equals(rows.get(i - 1).abort()), INTEGRITY_FAILURE, "invalid abort transition");
            } else {
                require(row.phase() == i + 1 && row.phase() <= 4 && Arrays.equals(row.encode(),
                                plan.row(i + 1, i + 1, i == 0 ? ZERO : rows.get(i - 1).digest())),
                        INTEGRITY_FAILURE, "invalid bootstrap journal transition");
            }
        }
        return rows;
    }

    static List<Row> parse(byte[] bytes) throws IOException {
        var result = new ArrayList<Row>(); int offset = 0;
        while (offset < bytes.length) {
            require(bytes.length - offset >= HEADER_BYTES && result.size() < 5, INTEGRITY_FAILURE, "torn or overlong operation journal");
            int size = ByteBuffer.wrap(bytes, offset + 12, 4).getInt();
            require(size > 0 && size <= META - HEADER_BYTES && size <= bytes.length - offset - HEADER_BYTES,
                    INTEGRITY_FAILURE, "torn operation journal row");
            var in = decode(Arrays.copyOfRange(bytes, offset, offset + HEADER_BYTES + size), 21, META);
            var row = new Row(hash(in), in.readLong(), hash(in), in.readUnsignedByte(),
                    List.of(hash(in), hash(in), hash(in)), hash(in)); end(in); result.add(row); offset += HEADER_BYTES + size;
        }
        return List.copyOf(result);
    }
}
