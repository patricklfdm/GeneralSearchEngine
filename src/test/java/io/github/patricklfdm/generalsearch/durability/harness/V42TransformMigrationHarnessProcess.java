package io.github.patricklfdm.generalsearch.durability.harness;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationPlan;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRecord;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationRequest;
import io.github.patricklfdm.generalsearch.durability.DurableMigrationTransformDescriptor;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Separate-process changed-codec/schema/key migration authority harness. */
public final class V42TransformMigrationHarnessProcess {
    private static final Field<LegacyDocument, Integer> LEGACY_ID =
            Field.of("id", Integer.class, LegacyDocument::id);
    private static final Field<LegacyDocument, Integer> LEGACY_VALUE =
            Field.of("value", Integer.class, LegacyDocument::value);
    private static final Field<CatalogDocument, String> CATALOG_ID =
            Field.of("sku", String.class, CatalogDocument::sku);
    private static final Field<CatalogDocument, Long> CATALOG_VALUE =
            Field.of("value", Long.class, CatalogDocument::value);
    private static final Field<CatalogDocument, String> CATALOG_CATEGORY =
            Field.of("category", String.class, CatalogDocument::category);

    private V42TransformMigrationHarnessProcess() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 4) {
            throw new IllegalArgumentException("expected mode, source, target, barrier");
        }
        String mode = arguments[0];
        Path source = Path.of(arguments[1]).toAbsolutePath().normalize();
        Path target = Path.of(arguments[2]).toAbsolutePath().normalize();
        String barrier = arguments[3];
        switch (mode) {
            case "prepare" -> prepare(source, target);
            case "apply-halt" -> apply(source, target, barrier);
            case "verify" -> verify(source, target, barrier);
            default -> throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void prepare(Path source, Path target) {
        if (Files.exists(source) || Files.exists(target)) {
            throw new IllegalStateException("harness paths must be absent");
        }
        try (DurableSearchEngine<Integer, LegacyDocument> engine = sourceBuilder()
                .buildDurable(sourceConfig(source))) {
            engine.add(new LegacyDocument(1, 11)).join();
            engine.add(new LegacyDocument(2, 22)).join();
            engine.remove(1).join();
            engine.checkpoint().join();
        }
        System.out.println("GSE_V42_PREPARE_RESULT=PASS");
    }

    private static void apply(Path source, Path target, String barrier) {
        SearchEngineBuilder<Integer, LegacyDocument> sourceBuilder = sourceBuilder();
        SearchEngineBuilder<String, CatalogDocument> targetBuilder = targetBuilder();
        DurableMigrationRequest<Integer, LegacyDocument,
                String, CatalogDocument> request = request(source, target);
        DurableMigrationPlan plan = targetBuilder.planDurableMigration(
                sourceBuilder, request);
        System.setProperty("gse.v4.crashBarrier", barrier);
        System.setProperty("gse.v4.crashAction", "halt");
        targetBuilder.applyDurableMigration(sourceBuilder, request, plan);
        throw new IllegalStateException("migration returned before crash barrier");
    }

    private static void verify(Path source, Path target, String barrier) {
        if (DurableStorageOperations.verifyStore(source).status()
                != DurableVerificationStatus.VALID
                || !DurableStorageOperations.inspectStoreFormat(source)
                        .declaredFormat().orElseThrow()
                        .equals(DurableStorageFormat.V1_0)) {
            throw new IllegalStateException("source authority is invalid");
        }
        try (DurableSearchEngine<Integer, LegacyDocument> engine = sourceBuilder()
                .buildDurable(sourceConfig(source))) {
            if (!new LegacyDocument(2, 22).equals(engine.get(2))
                    || engine.currentSequence() != 3) {
                throw new IllegalStateException("source typed state is invalid");
            }
        }
        boolean published = barrier.equals("v42-migration-after-parent-force-v1");
        if (published) {
            if (DurableStorageOperations.verifyStore(target).status()
                    != DurableVerificationStatus.VALID
                    || !DurableStorageOperations.inspectStoreFormat(target)
                            .declaredFormat().orElseThrow()
                            .equals(DurableStorageFormat.V1_1)) {
                throw new IllegalStateException("published target is invalid");
            }
            try (DurableSearchEngine<String, CatalogDocument> engine = targetBuilder()
                    .buildDurable(targetConfig(target))) {
                CatalogDocument expected = new CatalogDocument(
                        "sku-0002", 220L, "migrated");
                if (!expected.equals(engine.get("sku-0002"))
                        || engine.currentSequence() != 3
                        || !engine.search(Query.between(
                                CATALOG_VALUE, 200L, 300L)).equals(List.of(expected))
                        || !engine.search(Query.prefix(
                                CATALOG_CATEGORY, "mig")).equals(List.of(expected))) {
                    throw new IllegalStateException("target typed state is invalid");
                }
            }
        } else if (Files.exists(target)) {
            throw new IllegalStateException("prepublication target must be absent");
        }
        System.out.println("GSE_V42_VERIFY_RESULT={\"status\":\"PASS\","
                + "\"sourceValid\":true,\"targetPublished\":" + published
                + ",\"transformed\":true}");
    }

    private static DurableMigrationRequest<Integer, LegacyDocument,
            String, CatalogDocument> request(Path source, Path target) {
        return new DurableMigrationRequest<>(source,
                new DurableVerificationConfig<>(
                        "v42-transform-source", "v42-legacy-schema",
                        new LegacyCodec(), 1,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_DOCUMENTS),
                targetConfig(target),
                new DurableMigrationTransformDescriptor(
                        "catalog-schema-key-v1", 1),
                (key, document) -> {
                    String targetKey = "sku-%04d".formatted(key);
                    return new DurableMigrationRecord<>(targetKey,
                            new CatalogDocument(targetKey,
                                    document.value() * 10L, "migrated"));
                },
                64L * 1024 * 1024, 64L * 1024 * 1024,
                1024 * 1024, 1000, 1000, 64 * 1024);
    }

    private static SearchEngineBuilder<Integer, LegacyDocument> sourceBuilder() {
        return SearchEngine.builder(LegacyDocument.class, LEGACY_ID)
                .field(LEGACY_VALUE)
                .index(IndexDefinition.equality(LEGACY_VALUE));
    }

    private static SearchEngineBuilder<String, CatalogDocument> targetBuilder() {
        return SearchEngine.builder(CatalogDocument.class, CATALOG_ID)
                .field(CATALOG_VALUE)
                .field(CATALOG_CATEGORY)
                .index(IndexDefinition.range(CATALOG_VALUE))
                .index(IndexDefinition.prefix(CATALOG_CATEGORY));
    }

    private static DurableStorageConfig<Integer, LegacyDocument> sourceConfig(
            Path directory) {
        return DurableStorageConfig.builder(directory, new LegacyCodec())
                .format(DurableStorageFormat.V1_0)
                .storageIdentity("v42-transform-source")
                .schemaIdentity("v42-legacy-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private static DurableStorageConfig<String, CatalogDocument> targetConfig(
            Path directory) {
        return DurableStorageConfig.builder(directory, new CatalogCodec())
                .format(DurableStorageFormat.V1_1)
                .storageIdentity("v42-transform-target")
                .schemaIdentity("v42-catalog-schema")
                .checkpointWalBytes(2L * 1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private record LegacyDocument(int id, int value) {
    }

    private record CatalogDocument(String sku, long value, String category) {
    }

    private static final class LegacyCodec
            implements DurableCodec<Integer, LegacyDocument> {
        @Override
        public String codecId() {
            return "v42-legacy-binary";
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
        public Integer decodeKey(byte[] encoded) {
            if (encoded.length != 4) {
                throw new IllegalArgumentException("invalid legacy key");
            }
            return ByteBuffer.wrap(encoded).getInt();
        }

        @Override
        public byte[] encodeDocument(LegacyDocument document) {
            return ByteBuffer.allocate(8).putInt(document.id())
                    .putInt(document.value()).array();
        }

        @Override
        public LegacyDocument decodeDocument(byte[] encoded) {
            if (encoded.length != 8) {
                throw new IllegalArgumentException("invalid legacy document");
            }
            ByteBuffer bytes = ByteBuffer.wrap(encoded);
            return new LegacyDocument(bytes.getInt(), bytes.getInt());
        }
    }

    private static final class CatalogCodec
            implements DurableCodec<String, CatalogDocument> {
        @Override
        public String codecId() {
            return "v42-catalog-binary";
        }

        @Override
        public int codecVersion() {
            return 2;
        }

        @Override
        public byte[] encodeKey(String key) {
            return write(output -> output.writeUTF(key));
        }

        @Override
        public String decodeKey(byte[] encoded) {
            return read(encoded, input -> input.readUTF());
        }

        @Override
        public byte[] encodeDocument(CatalogDocument document) {
            return write(output -> {
                output.writeUTF(document.sku());
                output.writeLong(document.value());
                output.writeUTF(document.category());
            });
        }

        @Override
        public CatalogDocument decodeDocument(byte[] encoded) {
            return read(encoded, input -> new CatalogDocument(
                    input.readUTF(), input.readLong(), input.readUTF()));
        }

        private static byte[] write(Writer writer) {
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    writer.write(output);
                }
                return bytes.toByteArray();
            } catch (IOException impossible) {
                throw new AssertionError(impossible);
            }
        }

        private static <T> T read(byte[] encoded, Reader<T> reader) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(encoded))) {
                T result = reader.read(input);
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing catalog bytes");
                }
                return result;
            } catch (IOException problem) {
                throw new IllegalArgumentException("invalid catalog bytes", problem);
            }
        }

        @FunctionalInterface
        private interface Writer {
            void write(DataOutputStream output) throws IOException;
        }

        @FunctionalInterface
        private interface Reader<T> {
            T read(DataInputStream input) throws IOException;
        }
    }
}
