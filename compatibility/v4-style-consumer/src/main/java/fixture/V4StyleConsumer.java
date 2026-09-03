package fixture;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.schema.Field;

/** A framework-independent consumer of only the published V4 durable API. */
public final class V4StyleConsumer {
    public static final String STORAGE_IDENTITY = "v40-consumer-store-v1";
    public static final String SCHEMA_IDENTITY = "v40-consumer-schema-v1";
    public static final String CODEC_IDENTITY = "v40-consumer-codec-v1";

    public static final Field<DurableDocument, Integer> ID =
            Field.of("id", Integer.class, DurableDocument::id);
    public static final Field<DurableDocument, String> BODY =
            Field.of("body", String.class, DurableDocument::body);

    private V4StyleConsumer() {
    }

    public static DurableSearchEngine<Integer, DurableDocument> open(Path directory) {
        return builder()
                .buildDurable(config(directory, SCHEMA_IDENTITY));
    }

    public static SearchEngineBuilder<Integer, DurableDocument> builder() {
        return SearchEngine.builder(DurableDocument.class, ID).field(BODY);
    }

    public static DurableVerificationConfig<Integer, DurableDocument>
            verificationConfig() {
        DocumentCodec codec = new DocumentCodec();
        return new DurableVerificationConfig<>(
                STORAGE_IDENTITY,
                SCHEMA_IDENTITY,
                codec,
                codec.codecVersion(),
                64,
                4096,
                10_000);
    }

    public static DurableStorageConfig<Integer, DurableDocument> config(
            Path directory,
            String schemaIdentity
    ) {
        return DurableStorageConfig.builder(directory, new DocumentCodec())
                .storageIdentity(STORAGE_IDENTITY)
                .schemaIdentity(schemaIdentity)
                .maxEncodedKeyBytes(64)
                .maxEncodedDocumentBytes(4096)
                .maxBulkElements(1000)
                .maxDocuments(10_000)
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, DurableDocument> {
        @Override
        public String codecId() {
            return CODEC_IDENTITY;
        }

        @Override
        public int codecVersion() {
            return 1;
        }

        @Override
        public byte[] encodeKey(Integer key) {
            return ByteBuffer.allocate(Integer.BYTES).putInt(key).array();
        }

        @Override
        public Integer decodeKey(byte[] bytes) {
            if (bytes.length != Integer.BYTES) {
                throw new IllegalArgumentException("invalid integer key length");
            }
            return ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(DurableDocument document) {
            byte[] body = document.body().getBytes(StandardCharsets.UTF_8);
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    output.writeInt(document.id());
                    output.writeInt(body.length);
                    output.write(body);
                }
                return bytes.toByteArray();
            } catch (IOException impossible) {
                throw new AssertionError(impossible);
            }
        }

        @Override
        public DurableDocument decodeDocument(byte[] bytes) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(bytes))) {
                int id = input.readInt();
                int length = input.readInt();
                if (length < 0 || length != input.available()) {
                    throw new IllegalArgumentException("invalid document length");
                }
                byte[] body = input.readNBytes(length);
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return new DurableDocument(
                        id, new String(body, StandardCharsets.UTF_8));
            } catch (EOFException failure) {
                throw new IllegalArgumentException("truncated document", failure);
            } catch (IOException impossible) {
                throw new AssertionError(impossible);
            }
        }
    }
}
