package io.github.patricklfdm.generalsearch.durability.harness;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.regex.Pattern;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupPlan;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupScope;
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
import io.github.patricklfdm.generalsearch.schema.Field;

/** Separate-process producer, migrator and verifier for Phase 3 authority barriers. */
public final class V42ProductionMigrationHarnessProcess {
    private static final Pattern MIGRATION_REMNANT = Pattern.compile(
            "\\.gse-v42-migration-[0-9a-f]{32}\\.staging(?:\\.operation)?");
    private static final Set<String> PUBLISHED_BARRIERS = Set.of(
            "v42-migration-after-final-rename-v1",
            "v42-migration-before-parent-force-v1",
            "v42-migration-after-parent-force-v1",
            "v42-migration-before-final-verification-v1",
            "v42-migration-after-final-verification-v1",
            "v42-migration-before-final-source-compare-v1",
            "v42-migration-after-final-source-compare-v1",
            "v42-migration-before-marker-delete-v1",
            "v42-migration-after-marker-delete-v1",
            "v42-migration-after-marker-parent-force-v1",
            "v42-migration-before-return-v1");
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);

    private V42ProductionMigrationHarnessProcess() {
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
            case "produce-v11" -> produceV11(source, target);
            case "apply-halt" -> apply(source, target, barrier);
            case "verify" -> verify(source, target, barrier);
            case "cleanup" -> cleanup(source, target, barrier);
            default -> throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void produceV11(Path source, Path backup) {
        if (Files.exists(source) || Files.exists(backup)) {
            throw new IllegalStateException("harness paths must be absent");
        }
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source, DurableStorageFormat.V1_1))) {
            engine.add(new Document(1, 11)).join();
            engine.add(new Document(2, 22)).join();
            engine.checkpoint().join();
            engine.add(new Document(3, 33)).join();
            engine.backup(new DurableBackupRequest(
                    backup, 64L * 1024 * 1024)).join();
            engine.add(new Document(4, 44)).join();
        }
        System.out.println("GSE_V42_V11_RESULT=PASS");
    }

    private static void prepare(Path source, Path target) {
        if (Files.exists(source) || Files.exists(target)) {
            throw new IllegalStateException("harness paths must be absent");
        }
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source, DurableStorageFormat.V1_0))) {
            engine.add(new Document(1, 11)).join();
            engine.add(new Document(2, 22)).join();
            engine.remove(1).join();
            engine.checkpoint().join();
        }
        System.out.println("GSE_V42_PREPARE_RESULT=PASS");
    }

    private static void apply(Path source, Path target, String barrier) {
        SearchEngineBuilder<Integer, Document> sourceBuilder = builder();
        SearchEngineBuilder<Integer, Document> targetBuilder = builder();
        DurableMigrationRequest<Integer, Document, Integer, Document> request =
                request(source, target);
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
        boolean published = PUBLISHED_BARRIERS.contains(barrier);
        if (published) {
            if (DurableStorageOperations.verifyStore(target).status()
                    != DurableVerificationStatus.VALID
                    || !DurableStorageOperations.inspectStoreFormat(target)
                            .declaredFormat().orElseThrow()
                            .equals(DurableStorageFormat.V1_1)) {
                throw new IllegalStateException("published target is invalid");
            }
            try (DurableSearchEngine<Integer, Document> engine = builder()
                    .buildDurable(config(target, DurableStorageFormat.V1_1))) {
                if (!new Document(2, 22).equals(engine.get(2))
                        || engine.currentSequence() != 3) {
                    throw new IllegalStateException("target state is invalid");
                }
            }
        } else if (Files.exists(target)) {
            throw new IllegalStateException("prepublication target must be absent");
        }
        System.out.println("GSE_V42_VERIFY_RESULT={\"status\":\"PASS\","
                + "\"sourceValid\":true,\"targetPublished\":" + published + "}");
    }

    private static void cleanup(Path source, Path target, String barrier)
            throws IOException {
        List<Path> remnants;
        try (var paths = Files.list(target.getParent())) {
            remnants = paths.filter(path -> MIGRATION_REMNANT.matcher(
                            path.getFileName().toString()).matches())
                    .sorted().toList();
        }
        if (!remnants.isEmpty()) {
            Path named = remnants.stream().filter(Files::isDirectory)
                    .findFirst().orElse(remnants.getFirst());
            DurableCleanupPlan plan = DurableStorageOperations.planCleanup(
                    new DurableCleanupRequest(
                            named, DurableCleanupScope.OPERATION_REMNANT));
            if (plan.deleteSet().stream().anyMatch(entry ->
                    entry.member().equals(source)
                            || entry.member().equals(target))) {
                throw new IllegalStateException("unsafe migration cleanup plan");
            }
            DurableStorageOperations.applyCleanup(plan);
        }
        try (var paths = Files.list(target.getParent())) {
            if (paths.anyMatch(path -> MIGRATION_REMNANT.matcher(
                    path.getFileName().toString()).matches())) {
                throw new IllegalStateException("migration remnant survived cleanup");
            }
        }
        if (PUBLISHED_BARRIERS.contains(barrier)
                && DurableStorageOperations.verifyStore(target).status()
                        != DurableVerificationStatus.VALID) {
            throw new IllegalStateException("cleanup changed target authority");
        }
        System.out.println("GSE_V42_CLEANUP_RESULT=PASS");
    }

    private static DurableMigrationRequest<Integer, Document, Integer, Document>
            request(Path source, Path target) {
        return new DurableMigrationRequest<>(source,
                new DurableVerificationConfig<>(
                        "v42-harness-store", "v42-harness-schema",
                        new DocumentCodec(), 1,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                        DurableStorageConfig.DEFAULT_MAX_DOCUMENTS),
                config(target, DurableStorageFormat.V1_1),
                new DurableMigrationTransformDescriptor("identity-format-v1", 1),
                (key, document) -> new DurableMigrationRecord<>(key, document),
                64L * 1024 * 1024, 64L * 1024 * 1024,
                1024 * 1024, 1000, 1000, 64 * 1024);
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID);
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory, DurableStorageFormat format) {
        return DurableStorageConfig.builder(directory, new DocumentCodec())
                .format(format)
                .storageIdentity("v42-harness-store")
                .schemaIdentity("v42-harness-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private record Document(int id, int value) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v42-harness-codec";
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
                throw new IllegalArgumentException("invalid key");
            }
            return ByteBuffer.wrap(encoded).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            return ByteBuffer.allocate(8).putInt(document.id())
                    .putInt(document.value()).array();
        }

        @Override
        public Document decodeDocument(byte[] encoded) {
            if (encoded.length != 8) {
                throw new IllegalArgumentException("invalid document");
            }
            ByteBuffer bytes = ByteBuffer.wrap(encoded);
            return new Document(bytes.getInt(), bytes.getInt());
        }
    }
}
