package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.ByteBuffer;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V40DurableStorageConfigTest {
    @Test
    void frozenDefaultsAndIdentitiesAreExposed(@TempDir Path directory) {
        DurableStorageConfig<Integer, Integer> config =
                DurableStorageConfig.builder(directory, codec())
                        .storageIdentity("orders-v1")
                        .schemaIdentity("order-schema-v1")
                        .build();

        assertEquals(directory, config.directory());
        assertEquals("orders-v1", config.storageIdentity());
        assertEquals("order-schema-v1", config.schemaIdentity());
        assertEquals(1024 * 1024, config.maxEncodedKeyBytes());
        assertEquals(64 * 1024 * 1024, config.maxEncodedDocumentBytes());
        assertEquals(100_000, config.maxBulkElements());
        assertEquals(10_000_000, config.maxDocuments());
        assertEquals(256L * 1024 * 1024, config.checkpointWalBytes());
        assertEquals(8L * 1024 * 1024 * 1024, config.maxRetainedBytes());
    }

    @Test
    void missingOrMalformedIdentityFailsClosed(@TempDir Path directory) {
        assertThrows(IllegalArgumentException.class, () ->
                DurableStorageConfig.builder(directory, codec())
                        .schemaIdentity("schema-v1")
                        .build());
        assertThrows(IllegalArgumentException.class, () ->
                DurableStorageConfig.builder(directory, codec())
                        .storageIdentity("Uppercase")
                        .schemaIdentity("schema-v1")
                        .build());
    }

    @Test
    void unsafeBoundsAndChangingCodecIdentityFailClosed(@TempDir Path directory) {
        assertThrows(IllegalArgumentException.class, () ->
                DurableStorageConfig.builder(directory, codec())
                        .storageIdentity("store-v1")
                        .schemaIdentity("schema-v1")
                        .checkpointWalBytes(10)
                        .maxRetainedBytes(10)
                        .build());
        DurableCodec<Integer, Integer> invalid = new DurableCodec<>() {
            @Override
            public String codecId() {
                return "INVALID";
            }

            @Override
            public int codecVersion() {
                return 0;
            }

            @Override
            public byte[] encodeKey(Integer key) {
                return new byte[0];
            }

            @Override
            public Integer decodeKey(byte[] bytes) {
                return 0;
            }

            @Override
            public byte[] encodeDocument(Integer document) {
                return new byte[0];
            }

            @Override
            public Integer decodeDocument(byte[] bytes) {
                return 0;
            }
        };
        assertThrows(IllegalArgumentException.class, () ->
                DurableStorageConfig.builder(directory, invalid)
                        .storageIdentity("store-v1")
                        .schemaIdentity("schema-v1")
                        .build());
    }

    private static DurableCodec<Integer, Integer> codec() {
        return new DurableCodec<>() {
            @Override
            public String codecId() {
                return "int-v1";
            }

            @Override
            public int codecVersion() {
                return 1;
            }

            @Override
            public byte[] encodeKey(Integer key) {
                return ByteBuffer.allocate(4).putInt(key).array();
            }

            @Override
            public Integer decodeKey(byte[] bytes) {
                return ByteBuffer.wrap(bytes).getInt();
            }

            @Override
            public byte[] encodeDocument(Integer document) {
                return encodeKey(document);
            }

            @Override
            public Integer decodeDocument(byte[] bytes) {
                return decodeKey(bytes);
            }
        };
    }
}
