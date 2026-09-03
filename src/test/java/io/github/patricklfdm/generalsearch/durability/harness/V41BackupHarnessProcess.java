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
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableBackupResult;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Separate JVM producer/reopener for Phase 3 backup crash evidence. */
public final class V41BackupHarnessProcess {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);

    private V41BackupHarnessProcess() {
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
            case "recover-source" -> recoverSource(workspace);
            default -> throw new IllegalArgumentException(
                    "unknown mode: " + arguments[0]);
        }
    }

    private static void produce(Path workspace, boolean crash) throws Exception {
        if (crash) {
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                try {
                    Files.writeString(workspace.resolve("graceful-close.marker"),
                            "shutdown-hook-ran\n", StandardCharsets.UTF_8,
                            StandardOpenOption.CREATE_NEW);
                } catch (Exception ignored) {
                    // Presence is the only parent-consumed signal.
                }
            }, "v41-backup-shutdown-marker"));
        }
        try (DurableSearchEngine<Integer, Document> engine = engine(
                workspace.resolve("source"))) {
            engine.add(new Document(1, "phase3-backup-document")).join();
            DurableBackupResult result = engine.backup(new DurableBackupRequest(
                    workspace.resolve("backup"), 64L * 1024 * 1024))
                    .get(20, TimeUnit.SECONDS);
            if (crash) {
                throw new IllegalStateException("configured crash barrier was not hit");
            }
            System.out.println("GSE_V41_BACKUP_RESULT={\"status\":\"PASS\","
                    + "\"sequence\":" + result.sequence() + ","
                    + "\"contentIdentity\":\"" + result.contentIdentity()
                    + "\"}");
        }
    }

    private static void recoverSource(Path workspace) {
        try (DurableSearchEngine<Integer, Document> engine = engine(
                workspace.resolve("source"))) {
            if (engine.currentSequence() != 1
                    || !new Document(1, "phase3-backup-document")
                            .equals(engine.get(1))) {
                throw new IllegalStateException("source recovery oracle mismatch");
            }
            engine.add(new Document(2, "continued-after-backup-crash")).join();
            if (engine.currentSequence() != 2) {
                throw new IllegalStateException("source continuation failed");
            }
            System.out.println("GSE_V41_SOURCE_RECOVERY={\"status\":\"PASS\","
                    + "\"recoveredSequence\":1,\"continuedSequence\":2}");
        }
    }

    private static DurableSearchEngine<Integer, Document> engine(Path source) {
        DurableStorageConfig<Integer, Document> storage =
                DurableStorageConfig.builder(source, new DocumentCodec())
                        .storageIdentity("v41-phase3-harness-store")
                        .schemaIdentity("v41-phase3-harness-schema")
                        .checkpointWalBytes(1024 * 1024)
                        .maxRetainedBytes(64L * 1024 * 1024)
                        .build();
        return SearchEngine.builder(Document.class, ID).buildDurable(storage);
    }

    private record Document(int id, String body) {
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v41-phase3-harness-codec";
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
