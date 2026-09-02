package io.github.patricklfdm.generalsearch.durability.harness;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.concurrent.CompletableFuture;
import java.util.regex.Pattern;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Separate-JVM Phase 1 process used by the local crash-harness scaffold. */
public final class V40CrashHarnessProcess {
    private static final Pattern ID = Pattern.compile("[a-z0-9][a-z0-9-]{0,127}");

    private V40CrashHarnessProcess() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 3) {
            throw new IllegalArgumentException("expected mode, workspace and barrier ID");
        }
        String mode = arguments[0];
        Path workspace = Path.of(arguments[1]).toAbsolutePath().normalize();
        String barrier = arguments[2];
        if (!ID.matcher(barrier).matches()) {
            throw new IllegalArgumentException("invalid barrier ID");
        }
        Files.createDirectories(workspace);
        if (mode.equals("child-halt") || mode.equals("child-wait")) {
            runChild(workspace, barrier, mode.equals("child-halt"));
            return;
        }
        if (mode.equals("recover")) {
            recover(workspace, barrier);
            return;
        }
        if (mode.equals("phase2-write")) {
            runPhase2Writer(workspace);
            return;
        }
        if (mode.equals("phase2-verify")) {
            verifyPhase2Storage(workspace, barrier);
            return;
        }
        if (mode.equals("phase3-recover")) {
            verifyPhase3Recovery(workspace, barrier);
            return;
        }
        if (mode.equals("phase3-open-crash")) {
            crashDuringPhase3Recovery(workspace, barrier);
            return;
        }
        throw new IllegalArgumentException("unknown mode: " + mode);
    }

    private static void runChild(Path workspace, String barrier, boolean halt)
            throws Exception {
        Path gracefulMarker = workspace.resolve("graceful-close.marker");
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                Files.writeString(
                        gracefulMarker,
                        "shutdown-hook-ran\n",
                        StandardCharsets.UTF_8,
                        StandardOpenOption.CREATE_NEW);
            } catch (Exception ignored) {
                // The parent treats any marker presence as an invalid abrupt-crash case.
            }
        }, "v40-harness-shutdown-marker"));
        Files.writeString(
                workspace.resolve("phase1-scaffold.properties"),
                "schemaVersion=1\nbarrierId=" + barrier
                        + "\nproductionStorage=false\n",
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW);
        System.out.println("GSE_BARRIER_READY={\"schemaVersion\":1,\"barrierId\":\""
                + barrier + "\",\"pid\":" + ProcessHandle.current().pid() + "}");
        System.out.flush();
        if (halt) {
            Runtime.getRuntime().halt(86);
        }
        while (true) {
            Thread.sleep(1_000L);
        }
    }

    private static void recover(Path workspace, String barrier) throws Exception {
        String state = Files.readString(
                workspace.resolve("phase1-scaffold.properties"),
                StandardCharsets.UTF_8);
        if (!state.contains("barrierId=" + barrier + "\n")
                || !state.contains("productionStorage=false\n")) {
            throw new IllegalStateException("scaffold state mismatch");
        }
        if (Files.exists(workspace.resolve("graceful-close.marker"))) {
            throw new IllegalStateException("graceful shutdown path ran");
        }
        System.out.println("GSE_RECOVERY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"PASS\",\"productionStorage\":false,"
                + "\"barrierId\":\"" + barrier + "\"}");
    }

    private static void runPhase2Writer(Path workspace) {
        installShutdownMarker(workspace.resolve("graceful-close.marker"));
        DurableStorageConfig<String, Phase2Document> storage =
                DurableStorageConfig.builder(workspace, new Phase2Codec())
                        .storageIdentity("phase2-crash-store-v1")
                        .schemaIdentity("phase2-crash-schema-v1")
                        .build();
        Field<Phase2Document, String> id = Field.of(
                "id", String.class, Phase2Document::id);
        try (DurableSearchEngine<String, Phase2Document> engine =
                     SearchEngine.builder(Phase2Document.class, id)
                             .buildDurable(storage)) {
            CompletableFuture<Void> completion = engine.add(
                    new Phase2Document("doc-1", "phase2 durable payload"));
            completion.join();
            throw new IllegalStateException("configured crash barrier was not reached");
        }
    }

    private static void verifyPhase2Storage(Path workspace, String barrier)
            throws Exception {
        if (!Files.isRegularFile(workspace.resolve("gse-metadata"))
                || !Files.isRegularFile(workspace.resolve(
                        "gse-wal-00000000000000000001.log"))) {
            throw new IllegalStateException("Phase 2 storage files are missing");
        }
        if (Files.exists(workspace.resolve("graceful-close.marker"))) {
            throw new IllegalStateException("graceful shutdown path ran");
        }
        System.out.println("GSE_RECOVERY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"DEFERRED_PHASE3\","
                + "\"productionStorage\":true,"
                + "\"barrierId\":\"" + barrier + "\"}");
    }

    private static void verifyPhase3Recovery(Path workspace, String barrier)
            throws Exception {
        if (Files.exists(workspace.resolve("graceful-close.marker"))) {
            throw new IllegalStateException("graceful shutdown path ran");
        }
        long expectedSequence = expectedSequence(barrier);
        Path wal = workspace.resolve("gse-wal-00000000000000000001.log");
        long beforeOpenBytes = Files.size(wal);
        long recoveredSequence;
        long replayedRecords;
        long afterOpenBytes;
        try (DurableSearchEngine<String, Phase2Document> engine = openEngine(workspace)) {
            recoveredSequence = engine.currentSequence();
            replayedRecords = engine.durabilityMetrics().replayedRecords();
            afterOpenBytes = Files.size(wal);
            if (recoveredSequence != expectedSequence
                    || replayedRecords != expectedSequence
                    || engine.metrics().snapshotVersion() != 0) {
                throw new IllegalStateException("recovered durable prefix mismatch");
            }
            Phase2Document first = engine.get("doc-1");
            if ((expectedSequence == 1) != (first != null)) {
                throw new IllegalStateException("recovered document mismatch");
            }
            engine.add(new Phase2Document(
                    "doc-2", "continued after recovery")).join();
            if (engine.currentSequence() != expectedSequence + 1) {
                throw new IllegalStateException("continued sequence mismatch");
            }
        }
        try (DurableSearchEngine<String, Phase2Document> reopened = openEngine(workspace)) {
            if (reopened.currentSequence() != expectedSequence + 1
                    || reopened.get("doc-2") == null
                    || reopened.metrics().snapshotVersion() != 0) {
                throw new IllegalStateException("repeated reopen mismatch");
            }
        }
        System.out.println("GSE_RECOVERY_RESULT={\"schemaVersion\":1,"
                + "\"status\":\"PASS\",\"productionStorage\":true,"
                + "\"barrierId\":\"" + barrier + "\","
                + "\"recoveredSequence\":" + recoveredSequence + ","
                + "\"continuedSequence\":" + (expectedSequence + 1) + ","
                + "\"replayedRecords\":" + replayedRecords + ","
                + "\"tailTruncatedBytes\":"
                + Math.max(0, beforeOpenBytes - afterOpenBytes) + "}");
    }

    private static void crashDuringPhase3Recovery(Path workspace, String barrier)
            throws Exception {
        installShutdownMarker(workspace.resolve("graceful-close.marker"));
        String configuredBarrier = System.getProperty("gse.v4.crashBarrier");
        String configuredAction = System.getProperty("gse.v4.crashAction", "halt");
        System.clearProperty("gse.v4.crashBarrier");
        try (DurableSearchEngine<String, Phase2Document> engine = openEngine(workspace)) {
            engine.add(new Phase2Document(
                    "doc-1", "phase3 recovery crash payload")).join();
        }
        if (barrier.equals("v4-recovery-after-tail-truncate-v1")) {
            Files.write(
                    workspace.resolve("gse-wal-00000000000000000001.log"),
                    java.nio.ByteBuffer.allocate(8)
                            .putInt(0x47534546)
                            .putShort((short) 1)
                            .putShort((short) 0)
                            .array(),
                    StandardOpenOption.APPEND);
        }
        System.setProperty("gse.v4.crashBarrier", configuredBarrier);
        System.setProperty("gse.v4.crashAction", configuredAction);
        try (DurableSearchEngine<String, Phase2Document> ignored =
                     openEngine(workspace)) {
            throw new IllegalStateException(
                    "configured recovery crash barrier was not reached");
        }
    }

    private static DurableSearchEngine<String, Phase2Document> openEngine(
            Path workspace
    ) {
        DurableStorageConfig<String, Phase2Document> storage =
                DurableStorageConfig.builder(workspace, new Phase2Codec())
                        .storageIdentity("phase2-crash-store-v1")
                        .schemaIdentity("phase2-crash-schema-v1")
                        .build();
        Field<Phase2Document, String> id = Field.of(
                "id", String.class, Phase2Document::id);
        return SearchEngine.builder(Phase2Document.class, id)
                .buildDurable(storage);
    }

    private static long expectedSequence(String barrier) {
        return switch (barrier) {
            case "v4-wal-before-sequence-v1",
                    "v4-wal-after-sequence-v1",
                    "v4-wal-partial-header-v1",
                    "v4-wal-partial-payload-v1",
                    "v4-wal-partial-trailer-v1" -> 0;
            case "v4-wal-complete-before-force-v1",
                    "v4-wal-after-force-v1",
                    "v4-wal-before-publication-v1",
                    "v4-wal-after-publication-v1",
                    "v4-wal-before-future-completion-v1",
                    "v4-recovery-after-tail-truncate-v1",
                    "v4-recovery-after-replay-v1",
                    "v4-recovery-before-ready-publication-v1" -> 1;
            default -> throw new IllegalArgumentException(
                    "unsupported Phase 3 recovery barrier: " + barrier);
        };
    }

    private static void installShutdownMarker(Path marker) {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                Files.writeString(
                        marker,
                        "shutdown-hook-ran\n",
                        StandardCharsets.UTF_8,
                        StandardOpenOption.CREATE_NEW);
            } catch (Exception ignored) {
                // The parent treats any marker presence as an invalid abrupt-crash case.
            }
        }, "v40-phase2-shutdown-marker"));
    }

    private record Phase2Document(String id, String body) {
    }

    private static final class Phase2Codec
            implements DurableCodec<String, Phase2Document> {
        @Override
        public String codecId() {
            return "phase2-crash-codec-v1";
        }

        @Override
        public int codecVersion() {
            return 1;
        }

        @Override
        public byte[] encodeKey(String key) {
            return key.getBytes(StandardCharsets.UTF_8);
        }

        @Override
        public String decodeKey(byte[] bytes) {
            return new String(bytes, StandardCharsets.UTF_8);
        }

        @Override
        public byte[] encodeDocument(Phase2Document document) {
            return (document.id() + "\n" + document.body())
                    .getBytes(StandardCharsets.UTF_8);
        }

        @Override
        public Phase2Document decodeDocument(byte[] bytes) {
            String encoded = new String(bytes, StandardCharsets.UTF_8);
            int separator = encoded.indexOf('\n');
            if (separator < 0) {
                throw new IllegalArgumentException("invalid Phase 2 document");
            }
            return new Phase2Document(
                    encoded.substring(0, separator),
                    encoded.substring(separator + 1));
        }
    }
}
