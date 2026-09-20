package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.ByteBuffer;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;

class V51AutomaticRecordsTest {
    @Test void everySupportedRecordAgreesWithFrozenIndependentBytesAndSchemas() throws Exception {
        var samples = V51StorageFixture.samples();
        try (var in = getClass().getResourceAsStream("/replication/v51/format-catalog.json")) {
            var schemas = object(object(io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8))).get("records"));
            assertEquals(13, CATALOG.size());
            for (String name : CATALOG.keySet()) {
                var expected = V51StorageFixture.copy(object(schemas.get(name))); expected.remove("path");
                assertEquals(expected, CATALOG.get(name), name);
                byte[] bytes = unbase(samples.get(name)); var actual = decode(bytes, name);
                assertArrayEquals(bytes, encode(name, actual.value()), name);
                byte[] copy = actual.bytes(); copy[0] = 0; assertArrayEquals(bytes, actual.bytes());
                assertThrows(UnsupportedOperationException.class, () -> actual.value().put("changed", true));
            }
        }
    }
    @Test void rejectsForeignVersionsFlagsKindsLengthsAndChecksums() throws Exception {
        byte[] original = unbase(V51StorageFixture.samples().get("ACCEPT"));
        for (int offset : List.of(0, 4, 6, 8, 10, 12, 16, original.length - 1)) {
            byte[] bad = original.clone(); bad[offset] ^= 1;
            assertThrows(AutomaticReplicationException.class, () -> decode(bad, "ACCEPT"), "offset " + offset);
        }
        for (int size : List.of(0, 1, 47, 48, original.length - 1, original.length + 1))
            assertThrows(AutomaticReplicationException.class, () -> decode(Arrays.copyOf(original, size), "ACCEPT"));
        assertThrows(AutomaticReplicationException.class, () -> decode(original, "SELECTED"));
    }
    @Test void validChecksumCannotHideWrongPayloadReceiptsOrRankedProposer() throws Exception {
        var samples = V51StorageFixture.samples(); byte[] manifest = unbase(samples.get("MANIFEST"));
        var entry = V51StorageFixture.copy(decode(unbase(samples.get("ENTRY")), "ENTRY").value());
        entry.put("payloadDigest", "00".repeat(32)); assertThrows(AutomaticReplicationException.class, () -> encode("ENTRY", entry));
        var proof = V51StorageFixture.copy(decode(unbase(samples.get("PROOF")), "PROOF").value());
        object(list(proof.get("receipts")).get(1)).put("voter", "node-1");
        assertThrows(AutomaticReplicationException.class, () -> encode("PROOF", proof));
        var promise = V51StorageFixture.copy(decode(V51StorageFixture.promise(manifest, 2), "PROMISE").value());
        promise.put("proposer", "node-2"); byte[] wrong = encode("PROMISE", promise);
        assertThrows(AutomaticReplicationException.class, () -> context(decode(wrong, "PROMISE"), decode(manifest, "MANIFEST")));
    }
    @Test void binaryOptionalAndCanonicalJsonRejectRechecksummedCorruption() throws Exception {
        byte[] promise = unbase(V51StorageFixture.samples().get("PROMISE")); promise[48 + 32 + 8] = 2;
        resign(promise); assertThrows(AutomaticReplicationException.class, () -> decode(promise, "PROMISE"));
        byte[] manifest = unbase(V51StorageFixture.samples().get("MANIFEST"));
        byte[] spaced = new byte[manifest.length + 1]; System.arraycopy(manifest, 0, spaced, 0, 48);
        spaced[48] = ' '; System.arraycopy(manifest, 48, spaced, 49, manifest.length - 48);
        ByteBuffer.wrap(spaced).putInt(12, spaced.length - 48); resign(spaced);
        assertThrows(AutomaticReplicationException.class, () -> decode(spaced, "MANIFEST"));
    }
    private static void resign(byte[] bytes) {
        byte[] hash = AutomaticRecords.hash(Arrays.copyOf(bytes, 16), Arrays.copyOfRange(bytes, 48, bytes.length));
        System.arraycopy(hash, 0, bytes, 16, 32);
    }
}
