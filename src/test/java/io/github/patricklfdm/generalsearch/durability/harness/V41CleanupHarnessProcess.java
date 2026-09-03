package io.github.patricklfdm.generalsearch.durability.harness;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.UUID;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupPlan;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCleanupScope;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Separate-JVM driver for the V4.1 safe-cleanup abrupt-halt matrix. */
public final class V41CleanupHarnessProcess {
    private static final long OPERATION_MAGIC = 0x4753454f50313030L;
    private static final UUID CLEANUP_OPERATION = UUID.fromString(
            "33333333-3333-3333-3333-333333333333");
    private static final String CLEANUP_STAGING =
            ".gse-v41-backup-33333333333333333333333333333333.staging";
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    private V41CleanupHarnessProcess() {
    }

    /** Runs one crash or replacement-process recovery scenario. */
    public static void main(String[] arguments) throws Exception {
        if (arguments.length < 3) {
            throw new IllegalArgumentException("mode and workspace are required");
        }
        Path workspace = Path.of(arguments[1]).toAbsolutePath().normalize();
        String scope = arguments.length == 4 ? arguments[3] : "live";
        switch (arguments[0]) {
            case "crash" -> crash(workspace, arguments[2], scope);
            case "recover" -> recover(workspace, scope);
            default -> throw new IllegalArgumentException("unsupported mode");
        }
    }

    private static void crash(
            Path workspace,
            String barrier,
            String scope
    ) throws Exception {
        switch (scope) {
            case "live" -> crashLive(workspace, barrier);
            case "operation" -> crashOperation(workspace, barrier);
            default -> throw new IllegalArgumentException("unsupported scope");
        }
    }

    private static void crashLive(Path workspace, String barrier) throws Exception {
        Files.createDirectories(workspace);
        Path store = workspace.resolve("store");
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).field(BODY)
                .buildDurable(config(store))) {
            engine.add(new Document(1, "alpha")).join();
            engine.add(new Document(2, "beta")).join();
            engine.checkpoint().join();
        }
        writeProtectedManifest(store, workspace.resolve("protected.sha256"));
        Path checkpoint;
        try (var paths = Files.list(store)) {
            checkpoint = paths.filter(path -> path.getFileName().toString()
                            .endsWith(".chk"))
                    .findFirst().orElseThrow();
        }
        Files.copy(checkpoint, store.resolve(
                "gse-checkpoint-00000000000000000000-"
                        + "22222222222222222222222222222222.chk"));
        Files.writeString(store.resolve("gse-metadata.staging"),
                "phase5-safe-remnant", StandardCharsets.UTF_8);
        DurableCleanupPlan plan = DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(store, DurableCleanupScope.LIVE_STORE));
        System.setProperty("gse.v4.crashBarrier", barrier);
        System.setProperty("gse.v4.crashAction", "halt");
        DurableStorageOperations.applyCleanup(plan);
        throw new IllegalStateException("cleanup barrier was not reached");
    }

    private static void crashOperation(Path workspace, String barrier)
            throws Exception {
        Files.createDirectories(workspace);
        Path source = createStore(workspace.resolve("source"));
        writeProtectedManifest(source, workspace.resolve("protected.sha256"));
        Path staging = Files.createDirectory(workspace.resolve(CLEANUP_STAGING));
        Files.writeString(staging.resolve("gse-backup-metadata"), "partial");
        Files.writeString(staging.resolve("gse-backup-manifest.staging"),
                "partial-manifest");
        Path marker = workspace.resolve(CLEANUP_STAGING + ".operation");
        Files.write(marker, marker(CLEANUP_OPERATION, CLEANUP_STAGING, "backup"));
        DurableCleanupPlan plan = DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(staging,
                        DurableCleanupScope.OPERATION_REMNANT));
        System.setProperty("gse.v4.crashBarrier", barrier);
        System.setProperty("gse.v4.crashAction", "halt");
        DurableStorageOperations.applyCleanup(plan);
        throw new IllegalStateException("cleanup barrier was not reached");
    }

    private static void recover(Path workspace, String scope) throws Exception {
        switch (scope) {
            case "live" -> recoverLive(workspace);
            case "operation" -> recoverOperation(workspace);
            default -> throw new IllegalArgumentException("unsupported scope");
        }
    }

    private static void recoverLive(Path workspace) throws Exception {
        Path store = workspace.resolve("store");
        DurableCleanupPlan plan = DurableStorageOperations.planCleanup(
                new DurableCleanupRequest(store, DurableCleanupScope.LIVE_STORE));
        DurableStorageOperations.applyCleanup(plan);
        if (DurableStorageOperations.verifyStore(store).status()
                != DurableVerificationStatus.VALID) {
            throw new IllegalStateException("post-cleanup store is not valid");
        }
        continueStore(store);
    }

    private static void recoverOperation(Path workspace) throws Exception {
        Path staging = workspace.resolve(CLEANUP_STAGING);
        Path marker = workspace.resolve(CLEANUP_STAGING + ".operation");
        Path named = Files.exists(staging) ? staging
                : Files.exists(marker) ? marker : null;
        if (named != null) {
            DurableCleanupPlan plan = DurableStorageOperations.planCleanup(
                    new DurableCleanupRequest(named,
                            DurableCleanupScope.OPERATION_REMNANT));
            DurableStorageOperations.applyCleanup(plan);
        }
        if (Files.exists(staging) || Files.exists(marker)
                || Files.exists(workspace.resolve("backup"))) {
            throw new IllegalStateException("operation cleanup is incomplete");
        }
        Path source = workspace.resolve("source");
        if (DurableStorageOperations.verifyStore(source).status()
                != DurableVerificationStatus.VALID) {
            throw new IllegalStateException("source store is not valid");
        }
        continueStore(source);
    }

    private static Path createStore(Path store) throws Exception {
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).field(BODY)
                .buildDurable(config(store))) {
            engine.add(new Document(1, "alpha")).join();
            engine.add(new Document(2, "beta")).join();
            engine.checkpoint().join();
        }
        return store;
    }

    private static void continueStore(Path store) throws Exception {
        long continued;
        try (DurableSearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID).field(BODY)
                .buildDurable(config(store))) {
            engine.add(new Document(3, "continued")).join();
            continued = engine.currentSequence();
            engine.checkpoint().join();
        }
        try (DurableSearchEngine<Integer, Document> reopened = SearchEngine
                .builder(Document.class, ID).field(BODY)
                .buildDurable(config(store))) {
            if (!new Document(3, "continued").equals(reopened.get(3))
                    || reopened.currentSequence() != continued) {
                throw new IllegalStateException("second reopen diverged");
            }
        }
        System.out.println("GSE_V41_CLEANUP_RECOVERY={\"status\":\"PASS\","
                + "\"continuedSequence\":" + continued + "}");
    }

    private static byte[] marker(
            UUID operation,
            String staging,
            String target
    ) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        CRC32C checksum = new CRC32C();
        try (DataOutputStream output = new DataOutputStream(bytes)) {
            output.writeLong(OPERATION_MAGIC);
            output.writeShort(1);
            output.writeShort(0);
            output.writeByte(1);
            output.writeLong(operation.getMostSignificantBits());
            output.writeLong(operation.getLeastSignificantBits());
            writeString(output, staging);
            writeString(output, target);
            output.flush();
            checksum.update(bytes.toByteArray());
            output.writeInt((int) checksum.getValue());
        }
        return bytes.toByteArray();
    }

    private static void writeString(DataOutputStream output, String value)
            throws IOException {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        output.writeInt(bytes.length);
        output.write(bytes);
    }

    private static void writeProtectedManifest(Path store, Path output)
            throws IOException {
        StringBuilder manifest = new StringBuilder();
        try (var paths = Files.list(store)) {
            for (Path path : paths.sorted(Comparator.comparing(candidate ->
                    candidate.getFileName().toString())).toList()) {
                manifest.append(sha256(path)).append("  ")
                        .append(path.getFileName()).append('\n');
            }
        }
        Files.writeString(output, manifest, StandardCharsets.US_ASCII);
    }

    private static String sha256(Path path) throws IOException {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
        try (var input = Files.newInputStream(path)) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = input.read(buffer)) >= 0) {
                digest.update(buffer, 0, read);
            }
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static DurableStorageConfig<Integer, Document> config(Path store) {
        return DurableStorageConfig.builder(store, new DocumentCodec())
                .storageIdentity("phase5-crash-store")
                .schemaIdentity("phase5-crash-schema")
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
            return "phase5-crash-codec";
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
            return ByteBuffer.wrap(bytes).getInt();
        }

        @Override
        public byte[] encodeDocument(Document document) {
            return (document.id() + "\0" + document.body())
                    .getBytes(StandardCharsets.UTF_8);
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            String encoded = new String(bytes, StandardCharsets.UTF_8);
            int separator = encoded.indexOf('\0');
            return new Document(Integer.parseInt(
                    encoded.substring(0, separator)),
                    encoded.substring(separator + 1));
        }
    }
}
