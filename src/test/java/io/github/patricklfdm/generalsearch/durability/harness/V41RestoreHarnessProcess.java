package io.github.patricklfdm.generalsearch.durability.harness;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableRestoreResult;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Separate-JVM restore producer and continuation oracle for Phase 4 crash evidence. */
public final class V41RestoreHarnessProcess {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);

    private V41RestoreHarnessProcess() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 2) {
            throw new IllegalArgumentException("expected mode and workspace");
        }
        Path workspace = Path.of(arguments[1]).toAbsolutePath().normalize();
        Files.createDirectories(workspace);
        switch (arguments[0]) {
            case "produce" -> produce(workspace, false);
            case "crash" -> produce(workspace, true);
            case "recover" -> recover(workspace);
            default -> throw new IllegalArgumentException(
                    "unknown mode: " + arguments[0]);
        }
    }

    private static void produce(Path workspace, boolean crash) throws Exception {
        Path source = workspace.resolve("source");
        Path backup = workspace.resolve("backup");
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(source))) {
            engine.add(new Document(1, "phase4-restored-document")).join();
            engine.add(new Document(2, "second-document")).join();
            engine.backup(new DurableBackupRequest(
                    backup, 64L * 1024 * 1024)).join();
        }
        if (crash) {
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                try {
                    Files.writeString(workspace.resolve("graceful-close.marker"),
                            "shutdown-hook-ran\n", StandardCharsets.UTF_8,
                            StandardOpenOption.CREATE_NEW);
                } catch (Exception ignored) {
                    // Presence is the only parent-consumed signal.
                }
            }, "v41-restore-shutdown-marker"));
        }
        DurableRestoreResult result = builder().restoreDurableBackup(
                backup, config(workspace.resolve("restored")));
        if (crash) {
            throw new IllegalStateException("configured crash barrier was not hit");
        }
        System.out.println("GSE_V41_RESTORE_RESULT={\"status\":\"PASS\","
                + "\"sequence\":" + result.restoredSequence() + ","
                + "\"newHistory\":\"" + result.newHistory() + "\"}");
    }

    private static void recover(Path workspace) {
        Path restored = workspace.resolve("restored");
        if (!Files.exists(restored)) {
            restored = workspace.resolve("retry-restored");
            builder().restoreDurableBackup(workspace.resolve("backup"),
                    config(restored));
        }
        if (DurableStorageOperations.verifyStore(restored).status()
                != DurableVerificationStatus.VALID) {
            throw new IllegalStateException("restored store is not structurally valid");
        }
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(restored))) {
            if (engine.currentSequence() != 2
                    || !new Document(1, "phase4-restored-document")
                            .equals(engine.get(1))
                    || !new Document(2, "second-document").equals(engine.get(2))) {
                throw new IllegalStateException("restore recovery oracle mismatch");
            }
            engine.add(new Document(3, "continued-after-restore-crash")).join();
            engine.checkpoint().join();
            if (engine.currentSequence() != 3) {
                throw new IllegalStateException("restore continuation failed");
            }
        }
        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(restored))) {
            if (reopened.currentSequence() != 3
                    || reopened.get(3) == null) {
                throw new IllegalStateException("second restore reopen failed");
            }
        }
        System.out.println("GSE_V41_RESTORE_RECOVERY={\"status\":\"PASS\","
                + "\"recoveredSequence\":2,\"continuedSequence\":3}");
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID);
    }

    private static DurableStorageConfig<Integer, Document> config(Path directory) {
        return DurableStorageConfig.builder(directory, new DocumentCodec())
                .storageIdentity("v41-phase4-harness-store")
                .schemaIdentity("v41-phase4-harness-schema")
                .checkpointWalBytes(1024 * 1024)
                .maxRetainedBytes(64L * 1024 * 1024)
                .build();
    }

    private record Document(int id, String body) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v41-phase4-harness-codec";
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
                throw new IllegalArgumentException("invalid key bytes");
            }
            return ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            try {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                try (DataOutputStream output = new DataOutputStream(bytes)) {
                    output.writeInt(document.id());
                    output.writeUTF(document.body());
                }
                return bytes.toByteArray();
            } catch (IOException impossible) {
                throw new AssertionError(impossible);
            }
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(bytes))) {
                Document result = new Document(input.readInt(), input.readUTF());
                if (input.available() != 0) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return result;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document bytes", failure);
            }
        }
    }
}
