package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;

class V50LogicalFixtureTest {
    @Test
    void freezesLogicalMessageAndRejectionFamilies() throws IOException {
        try (var input = getClass().getResourceAsStream(
                "/replication/v50-logical-protocol-fixtures.json")) {
            String fixture = new String(input.readAllBytes(), StandardCharsets.UTF_8);
            for (String required : new String[]{
                    "gse-replication/1.0", "HANDSHAKE", "ACTIVATION_PROMISE",
                    "APPEND", "DURABLE_ACK", "COMMIT_PROOF", "COMMIT_PROOF_ACK",
                    "COMMIT_ADVANCE", "CONFLICT", "AUTHORITY_STATUS_PROBE",
                    "SNAPSHOT_OFFER", "SNAPSHOT_CHUNK", "SNAPSHOT_INSTALL",
                    "BEFORE_ENTRY_FORCE", "AFTER_ENTRY_QUORUM_ACK",
                    "BEFORE_PROOF_FORCE", "AFTER_PROOF_QUORUM_ACK",
                    "BEFORE_APPLY", "AFTER_APPLY", "BEFORE_PUBLICATION",
                    "AFTER_PUBLICATION", "BEFORE_RESPONSE", "AFTER_RESPONSE",
                    "UNKNOWN_MAJOR",
                    "STALE_EPOCH", "INTEGRITY_FAILURE", "CAPACITY_EXCEEDED"}) {
                assertTrue(fixture.contains("\"" + required + "\""), required);
            }
        }
    }
}
