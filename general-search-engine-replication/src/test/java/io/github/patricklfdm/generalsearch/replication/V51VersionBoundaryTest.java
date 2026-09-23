package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.junit.jupiter.api.Test;

/** Explicit bidirectional format refusal, independently of the public endpoint probes. */
class V51VersionBoundaryTest {
    private static byte[] version(byte[] original, int minor) {
        byte[] bytes=original.clone();ByteBuffer.wrap(bytes).putShort(6,(short)minor);
        System.arraycopy(hash(Arrays.copyOf(bytes,16),Arrays.copyOfRange(bytes,48,bytes.length)),0,bytes,16,32);
        return bytes;
    }
    @Test void automaticStorageRejectsBothOlderMinorsWithValidChecksums() throws Exception {
        byte[] current=unbase(V51StorageFixture.samples().get("MANIFEST"));
        assertEquals("MANIFEST",decode(current,"MANIFEST").name());
        for(int minor:new int[]{0,1}) {
            var failure=assertThrows(AutomaticReplicationException.class,()->decode(version(current,minor),"MANIFEST"));
            assertEquals(AutomaticReplicationException.Reason.PROTOCOL_MISMATCH,failure.reason());
        }
    }
    @Test void legacyAndConfiguredDiskReadersRejectAutomaticRecords() throws Exception {
        byte[] current=unbase(V51StorageFixture.samples().get("MANIFEST"));
        int kind=Short.toUnsignedInt(ByteBuffer.wrap(current).getShort(8));
        for(int minor:new int[]{0,1}) {
            var failure=assertThrows(ReplicationException.class,()->ReplicaFormat.decodeRecord(current,kind,IMAGE,minor));
            assertEquals(ReplicationException.Reason.PROTOCOL_MISMATCH,failure.reason());
        }
        assertEquals(ReplicationException.Reason.PROTOCOL_MISMATCH,
                assertThrows(ReplicationException.class,()->AdmissionFormat.decode(current,kind,IMAGE)).reason());
    }
    @Test void wireReadersRejectForeignMinorsInBothDirections() throws Exception {
        try(var input=getClass().getResourceAsStream("/replication/v51/format-fixtures.json")) {
            var fixtures=object(io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(new String(input.readAllBytes(),StandardCharsets.UTF_8)));
            var manifest=decode(unbase(object(fixtures.get("storage")).get("MANIFEST")),"MANIFEST");
            for(var row:object(fixtures.get("wire")).entrySet()) {
                byte[] current=unbase(row.getValue());AutomaticWire.decode(current,manifest,IMAGE);
                assertEquals(ReplicationException.Reason.PROTOCOL_MISMATCH,
                        assertThrows(ReplicationException.class,()->ReplicaWire.decode(current,IMAGE)).reason(),row.getKey());
                for(int minor:new int[]{0,1}) {
                    var failure=assertThrows(AutomaticReplicationException.class,()->AutomaticWire.decode(version(current,minor),manifest,IMAGE));
                    assertEquals(AutomaticReplicationException.Reason.PROTOCOL_MISMATCH,failure.reason(),row.getKey());
                }
            }
        }
    }
}
