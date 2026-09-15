package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V50PublicApiContractTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);

    @TempDir
    Path temporary;

    @Test
    void freezesExactThreeVoterConfigurationAndDeclarationOnlyBuild() {
        ReplicationGroupConfig<Integer, Document> config = configuration();
        assertEquals(3, config.members().size());
        assertEquals("gse-replication/1.0", ReplicatedSearchEngines.PROTOCOL);
        ReplicationBounds bounds = config.bounds();
        assertEquals(8 * 1024 * 1024, bounds.maxFrameBytes());
        assertEquals(1000, bounds.maxEntriesPerAppend());
        assertEquals(256, bounds.maxInFlightPerPeer());
        assertEquals(10_000, bounds.maxPendingClientOperations());
        assertEquals(12, bounds.maxRetryAttempts());
        assertEquals(5000, bounds.requestTimeoutMillis());
        assertEquals(250, bounds.retryBackoffMillis());
        assertEquals(4 * 1024 * 1024, bounds.snapshotChunkBytes());
        assertEquals(8L * 1024 * 1024 * 1024, bounds.maxRetainedLogBytes());
        assertEquals(16L * 1024 * 1024 * 1024, bounds.maxSnapshotStagingBytes());
        try {
            assertEquals(CompletableFuture.class,
                    ReplicatedSearchEngine.class.getMethod("start").getReturnType());
        } catch (NoSuchMethodException exception) {
            throw new AssertionError(exception);
        }
        assertThrows(UnsupportedOperationException.class, () ->
                ReplicatedSearchEngines.builder(
                        SearchEngine.builder(Document.class, ID), config).build());
    }

    @Test
    void rejectsAmbiguousOrUnboundedConfiguration() {
        ReplicationGroupConfig<Integer, Document> valid = configuration();
        assertThrows(IllegalArgumentException.class, () ->
                new ReplicationGroupConfig<>(
                        valid.groupId(), valid.configurationId(), valid.localNodeId(),
                        valid.configuredLeaderId(), valid.members().subList(0, 2),
                        valid.replicaDirectory(), valid.materialization(), valid.bounds()));
        assertThrows(IllegalArgumentException.class, () ->
                new ReplicationBounds(
                        ReplicationBounds.HARD_MAX_FRAME_BYTES + 1,
                        1, 1, 1, 1, 1, 1, 1, 1, 1));
        assertThrows(IllegalArgumentException.class, () ->
                new ReplicationBounds(1, 0, 1, 1, 1, 1, 1, 1, 1, 1));
        assertThrows(IllegalArgumentException.class, () ->
                new ReplicationStatus(
                        valid.localNodeId(), ReplicaRole.FOLLOWER,
                        ReplicaState.READY, false,
                        2, 2, 3, 2, 3, 1, 0, 0));
    }

    @Test
    void everyResourceDimensionRejectsZeroAndValuesAboveItsAbsoluteMaximum() {
        long[] maximums = {
                ReplicationBounds.HARD_MAX_FRAME_BYTES,
                ReplicationBounds.HARD_MAX_ENTRIES_PER_APPEND,
                ReplicationBounds.HARD_MAX_IN_FLIGHT_PER_PEER,
                ReplicationBounds.HARD_MAX_PENDING_CLIENT_OPERATIONS,
                ReplicationBounds.HARD_MAX_RETRY_ATTEMPTS,
                ReplicationBounds.HARD_MAX_REQUEST_TIMEOUT_MILLIS,
                ReplicationBounds.HARD_MAX_RETRY_BACKOFF_MILLIS,
                ReplicationBounds.HARD_MAX_SNAPSHOT_CHUNK_BYTES,
                ReplicationBounds.HARD_MAX_RETAINED_LOG_BYTES,
                ReplicationBounds.HARD_MAX_SNAPSHOT_STAGING_BYTES};
        for (int dimension = 0; dimension < maximums.length; dimension++) {
            for (long invalid : new long[]{0, -1, maximums[dimension] + 1}) {
                long[] values = maximums.clone();
                values[dimension] = invalid;
                assertThrows(IllegalArgumentException.class, () -> bounds(values),
                        "dimension=" + dimension + " invalid=" + invalid);
            }
        }
        assertEquals(maximums[9], bounds(maximums).maxSnapshotStagingBytes());
    }

    private ReplicationBounds bounds(long[] values) {
        return new ReplicationBounds((int) values[0], (int) values[1], (int) values[2],
                (int) values[3], (int) values[4], (int) values[5], (int) values[6],
                (int) values[7], values[8], values[9]);
    }

    @Test
    void freezesOfflineBootstrapShape() {
        ReplicationBootstrapPlan plan = new ReplicationBootstrapPlan(
                new ReplicationGroupId(UUID.fromString(
                        "11111111-1111-1111-1111-111111111111")),
                "config-v1", ReplicationBootstrapSource.EMPTY, null,
                List.of(temporary.resolve("a"), temporary.resolve("b"),
                        temporary.resolve("c")), "sha256:fixture");
        assertEquals(3, plan.absentReplicaTargets().size());
        assertThrows(UnsupportedOperationException.class,
                () -> ReplicationStorageOperations.applyBootstrap(plan));
        assertTrue(plan.absentReplicaTargets().stream().noneMatch(java.nio.file.Files::exists));
    }

    private ReplicationGroupConfig<Integer, Document> configuration() {
        ReplicationNodeId one = new ReplicationNodeId("node-1");
        ReplicationNodeId two = new ReplicationNodeId("node-2");
        ReplicationNodeId three = new ReplicationNodeId("node-3");
        var materialization = DurableStorageConfig.builder(
                        temporary.resolve("materialized"), new Codec())
                .storageIdentity("v50-fixture-store")
                .schemaIdentity("v50-fixture-schema")
                .build();
        return new ReplicationGroupConfig<>(
                new ReplicationGroupId(UUID.fromString(
                        "11111111-1111-1111-1111-111111111111")),
                "config-v1", one, one,
                List.of(
                        new ReplicationMember(one, new ReplicationEndpoint("127.0.0.1", 19101)),
                        new ReplicationMember(two, new ReplicationEndpoint("127.0.0.1", 19102)),
                        new ReplicationMember(three, new ReplicationEndpoint("127.0.0.1", 19103))),
                temporary.resolve("replica"), materialization,
                ReplicationBounds.defaults());
    }

    private record Document(int id, String value) {
    }

    private static final class Codec implements DurableCodec<Integer, Document> {
        public String codecId() { return "v50-fixture-codec"; }
        public int codecVersion() { return 1; }
        public byte[] encodeKey(Integer value) {
            return ByteBuffer.allocate(4).putInt(value).array();
        }
        public Integer decodeKey(byte[] value) { return ByteBuffer.wrap(value).getInt(); }
        public byte[] encodeDocument(Document value) {
            return encodeKey(value.id());
        }
        public Document decodeDocument(byte[] value) {
            return new Document(decodeKey(value), "fixture");
        }
    }
}
