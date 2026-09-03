package io.github.patricklfdm.generalsearch.engine;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.lang.management.ManagementFactory;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableBackupResult;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableRestoreResult;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Standalone V4.1 source-loss evidence probe packaged only in benchmarks.jar. */
public final class V41OperationalEvidenceProbe {
    private static final String SCHEMA = "gse-v41-operational-properties-v1";
    private static final String STORAGE_ID = "v41-operational-store-v1";
    private static final String SCHEMA_ID = "v41-operational-schema-v1";
    private static final long MAX_BUNDLE_BYTES = 8L * 1024 * 1024 * 1024;
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final DocumentCodec CODEC = new DocumentCodec();

    private V41OperationalEvidenceProbe() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length < 1) {
            usage();
        }
        switch (arguments[0]) {
            case "source" -> runSource(arguments);
            case "restore" -> runRestore(arguments);
            default -> usage();
        }
    }

    private static void runSource(String[] arguments) throws Exception {
        if (arguments.length != 6) {
            usage();
        }
        Profile profile = Profile.named(arguments[1]);
        Path store = absent(arguments[2], "source store");
        Path backup = absent(arguments[3], "backup target");
        Path output = absentFile(arguments[4], "source properties");
        long measurementSeconds = positiveLong(arguments[5], "measurement seconds");
        Map<String, String> result = base("source", profile, measurementSeconds);
        AtomicLong backupPeakBytes = new AtomicLong();
        AtomicReference<Throwable> monitorFailure = new AtomicReference<>();
        AtomicLong sourceReads = new AtomicLong();
        AtomicLong sourceReadNanos = new AtomicLong();

        long sourceStarted = System.nanoTime();
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(store, profile))) {
            long loadStarted = System.nanoTime();
            addInBatches(engine, documents(profile.documents(), 0), profile.batchSize());
            result.put("source.loadNanos", elapsed(loadStarted));

            long mutationStarted = System.nanoTime();
            updateRange(engine, profile.preBackupMutations(), 1, profile.batchSize());
            result.put("source.preBackupMutationNanos", elapsed(mutationStarted));
            String expectedCutChecksum = checksum(engine, profile.documents());
            long expectedCutSequence = engine.currentSequence();
            long bytesBeforeBackup = trackedBytes(store, backup);
            if (bytesBeforeBackup <= 0L) {
                throw new IllegalStateException("source bytes were not observable");
            }
            backupPeakBytes.set(bytesBeforeBackup);
            result.put("source.bytesBeforeBackup", Long.toString(bytesBeforeBackup));

            CompletableFuture<DurableBackupResult> backupFuture;
            long backupStarted = System.nanoTime();
            backupFuture = engine.backup(new DurableBackupRequest(
                    backup, MAX_BUNDLE_BYTES));

            Thread reader = new Thread(() -> {
                try {
                    long started = System.nanoTime();
                    do {
                        int id = (int) (sourceReads.get() % profile.documents());
                        if (engine.get(id) == null) {
                            throw new IllegalStateException("source-impact read lost a document");
                        }
                        sourceReads.incrementAndGet();
                    } while (!backupFuture.isDone() && sourceReads.get() < 100_000);
                    sourceReadNanos.set(Math.max(0L, System.nanoTime() - started));
                } catch (Throwable failure) {
                    monitorFailure.compareAndSet(null, failure);
                }
            }, "v41-backup-source-reader");
            Thread bytes = byteMonitor(store, backup, backupPeakBytes,
                    monitorFailure, backupFuture);
            reader.start();
            bytes.start();

            long afterCutStarted = System.nanoTime();
            engine.update(new Document(profile.documents() - 1,
                    body(profile.documents() - 1, 777))).join();
            result.put("source.afterCutMutationNanos", elapsed(afterCutStarted));
            DurableBackupResult completed = backupFuture.join();
            result.put("backup.elapsedNanos", elapsed(backupStarted));
            reader.join(TimeUnit.SECONDS.toMillis(30));
            bytes.join(TimeUnit.SECONDS.toMillis(30));
            if (reader.isAlive() || bytes.isAlive()) {
                reader.interrupt();
                bytes.interrupt();
                throw new IllegalStateException("backup monitor did not stop");
            }
            if (monitorFailure.get() != null) {
                throw new IllegalStateException("backup monitor failed", monitorFailure.get());
            }
            long peakObservedBytes = backupPeakBytes.get();
            if (peakObservedBytes < bytesBeforeBackup) {
                throw new IllegalStateException(
                        "backup peak bytes precede the synchronous baseline");
            }
            if (completed.sequence() != expectedCutSequence) {
                throw new IllegalStateException("backup cut sequence drifted");
            }

            DurableVerificationReport structural =
                    DurableStorageOperations.verifyBackup(backup);
            DurableSemanticVerificationReport semantic = builder().verifyDurableBackup(
                    backup, verification(profile));
            if (structural.status() != DurableVerificationStatus.VALID
                    || semantic.status()
                    != DurableSemanticVerificationStatus.SEMANTICALLY_VALID
                    || semantic.documentCount() != profile.documents()) {
                throw new IllegalStateException("completed backup did not verify");
            }
            result.put("backup.status", "PASS");
            result.put("backup.sequence", Long.toString(completed.sequence()));
            result.put("backup.contentIdentity", completed.contentIdentity());
            result.put("backup.sourceHistory", completed.sourceHistory().toString());
            result.put("backup.totalBytes", Long.toString(completed.totalBytes()));
            result.put("backup.peakObservedBytes", Long.toString(peakObservedBytes));
            result.put("backup.structuralStatus", structural.status().name());
            result.put("backup.semanticStatus", semantic.status().name());
            result.put("backup.semanticDocuments", Long.toString(semantic.documentCount()));
            result.put("oracle.cutChecksum", expectedCutChecksum);
            result.put("source.afterCutSequence", Long.toString(engine.currentSequence()));
            result.put("source.impactReads", Long.toString(sourceReads.get()));
            result.put("source.impactWrites", "1");
            result.put("source.impactReadNanos", Long.toString(sourceReadNanos.get()));
            result.put("source.retainedBytes",
                    Long.toString(engine.durabilityMetrics().retainedBytes()));
            result.put("source.heapUsedBytes", Long.toString(heapUsedBytes()));
        }
        result.put("source.totalNanos", elapsed(sourceStarted));
        result.put("status", "PASS");
        writeProperties(output, result);
        System.out.printf(
                "v41OperationalSource=PASS profile=%s documents=%d "
                        + "mutations=%d sequence=%s identity=%s%n",
                profile.name(), profile.documents(), profile.preBackupMutations(),
                result.get("backup.sequence"), result.get("backup.contentIdentity"));
    }

    private static void runRestore(String[] arguments) throws Exception {
        if (arguments.length != 7) {
            usage();
        }
        Profile profile = Profile.named(arguments[1]);
        Path backup = existingDirectory(arguments[2], "backup bundle");
        Path target = absent(arguments[3], "restore target");
        Path sourceProperties = existingFile(arguments[4], "source properties");
        Path output = absentFile(arguments[5], "restore properties");
        long measurementSeconds = positiveLong(arguments[6], "measurement seconds");
        Map<String, String> source = readProperties(sourceProperties);
        validateSourceProperties(source, profile, measurementSeconds);
        Map<String, String> result = base("restore", profile, measurementSeconds);

        long verifyStarted = System.nanoTime();
        DurableVerificationReport structural = DurableStorageOperations.verifyBackup(backup);
        DurableSemanticVerificationReport semantic = builder().verifyDurableBackup(
                backup, verification(profile));
        result.put("verification.elapsedNanos", elapsed(verifyStarted));
        if (structural.status() != DurableVerificationStatus.VALID
                || semantic.status()
                != DurableSemanticVerificationStatus.SEMANTICALLY_VALID
                || semantic.documentCount() != profile.documents()) {
            throw new IllegalStateException("replacement-host verification failed");
        }

        long restoreStarted = System.nanoTime();
        DurableRestoreResult restored = builder().restoreDurableBackup(
                backup, config(target, profile));
        result.put("restore.elapsedNanos", elapsed(restoreStarted));
        if (restored.restoredSequence()
                != Long.parseLong(source.get("backup.sequence"))
                || !restored.sourceContentIdentity().equals(
                source.get("backup.contentIdentity"))
                || !restored.sourceHistory().toString().equals(
                source.get("backup.sourceHistory"))) {
            throw new IllegalStateException("restore provenance differs from source evidence");
        }
        if (restored.newHistory().equals(restored.sourceHistory())) {
            throw new IllegalStateException("restore did not create a new history");
        }

        long initialOpenStarted = System.nanoTime();
        String cutChecksum;
        long finalSequence;
        String continuedChecksum;
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(target, profile))) {
            result.put("restore.firstOpenNanos", elapsed(initialOpenStarted));
            cutChecksum = checksum(engine, profile.documents());
            if (!cutChecksum.equals(source.get("oracle.cutChecksum"))) {
                throw new IllegalStateException("restored full-state oracle differs");
            }
            Document excluded = engine.get(profile.documents() - 1);
            if (!excluded.equals(new Document(
                    profile.documents() - 1, body(profile.documents() - 1, 0)))) {
                throw new IllegalStateException("post-cut source mutation entered backup");
            }
            assertRetrieval(engine, profile);

            long continuedStarted = System.nanoTime();
            updateRange(engine, profile.continuedMutations(), 2, profile.batchSize());
            result.put("restore.continuedMutationNanos", elapsed(continuedStarted));
            long checkpointStarted = System.nanoTime();
            engine.checkpoint().join();
            result.put("restore.checkpointNanos", elapsed(checkpointStarted));
            continuedChecksum = checksum(engine, profile.documents());
            finalSequence = engine.currentSequence();
            result.put("restore.retainedBytes",
                    Long.toString(engine.durabilityMetrics().retainedBytes()));
            result.put("restore.heapUsedBytes", Long.toString(heapUsedBytes()));
        }

        long reopenStarted = System.nanoTime();
        try (DurableSearchEngine<Integer, Document> reopened = builder()
                .buildDurable(config(target, profile))) {
            result.put("restore.secondOpenNanos", elapsed(reopenStarted));
            if (reopened.currentSequence() != finalSequence
                    || !checksum(reopened, profile.documents()).equals(continuedChecksum)) {
                throw new IllegalStateException("second reopen oracle differs");
            }
            assertRetrieval(reopened, profile);
            runReadMeasurement(reopened, profile, measurementSeconds, result);
        }

        result.put("verification.structuralStatus", structural.status().name());
        result.put("verification.semanticStatus", semantic.status().name());
        result.put("verification.semanticDocuments", Long.toString(semantic.documentCount()));
        result.put("restore.sourceHistory", restored.sourceHistory().toString());
        result.put("restore.newHistory", restored.newHistory().toString());
        result.put("restore.sequence", Long.toString(restored.restoredSequence()));
        result.put("restore.authoritativeBytes",
                Long.toString(restored.authoritativeBytes()));
        result.put("oracle.restoredChecksum", cutChecksum);
        result.put("oracle.continuedChecksum", continuedChecksum);
        result.put("restore.finalSequence", Long.toString(finalSequence));
        result.put("restore.finalDirectoryBytes", Long.toString(directoryBytes(target)));
        result.put("status", "PASS");
        writeProperties(output, result);
        System.out.printf(
                "v41OperationalRestore=PASS profile=%s documents=%d "
                        + "continuedMutations=%d sourceHistory=%s newHistory=%s%n",
                profile.name(), profile.documents(), profile.continuedMutations(),
                restored.sourceHistory(), restored.newHistory());
    }

    private static void runReadMeasurement(
            DurableSearchEngine<Integer, Document> engine,
            Profile profile,
            long seconds,
            Map<String, String> result
    ) throws InterruptedException {
        AtomicLong reads = new AtomicLong();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        long started = System.nanoTime();
        long deadline = started + TimeUnit.SECONDS.toNanos(seconds);
        List<Thread> workers = new ArrayList<>();
        for (int worker = 0; worker < profile.readers(); worker++) {
            int workerId = worker;
            Thread thread = new Thread(() -> {
                try {
                    while (System.nanoTime() < deadline && failure.get() == null) {
                        long operation = reads.getAndIncrement();
                        int id = (int) ((workerId + operation) % profile.documents());
                        if (engine.get(id) == null) {
                            throw new IllegalStateException("measurement read lost a document");
                        }
                    }
                } catch (Throwable caught) {
                    failure.compareAndSet(null, caught);
                }
            }, "v41-restored-reader-" + worker);
            workers.add(thread);
            thread.start();
        }
        for (Thread worker : workers) {
            worker.join(TimeUnit.SECONDS.toMillis(seconds + 30));
            if (worker.isAlive()) {
                worker.interrupt();
                throw new IllegalStateException("measurement worker did not stop");
            }
        }
        if (failure.get() != null) {
            throw new IllegalStateException("measurement worker failed", failure.get());
        }
        if (reads.get() == 0) {
            throw new IllegalStateException("measurement made no read progress");
        }
        long durationNanos = Math.max(1L, System.nanoTime() - started);
        result.put("measurement.reads", Long.toString(reads.get()));
        result.put("measurement.durationNanos", Long.toString(durationNanos));
        result.put("measurement.readsPerSecondMicros",
                Long.toString(Math.round(
                        reads.get() * 1_000_000_000_000_000.0 / durationNanos)));
    }

    private static Thread byteMonitor(
            Path store,
            Path backup,
            AtomicLong maximum,
            AtomicReference<Throwable> failure,
            CompletableFuture<?> completion
    ) {
        return new Thread(() -> {
            try {
                do {
                    maximum.accumulateAndGet(trackedBytes(store, backup), Math::max);
                    Thread.sleep(1L);
                } while (!completion.isDone());
                maximum.accumulateAndGet(trackedBytes(store, backup), Math::max);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                failure.compareAndSet(null, interrupted);
            } catch (IOException | UncheckedIOException caught) {
                failure.compareAndSet(null, caught);
            }
        }, "v41-backup-byte-monitor");
    }

    private static long trackedBytes(Path store, Path backup) throws IOException {
        return Math.addExact(directoryBytes(store), directoryBytes(backup));
    }

    private static Map<String, String> base(
            String stage,
            Profile profile,
            long measurementSeconds
    ) {
        Map<String, String> result = new TreeMap<>();
        result.put("schemaVersion", SCHEMA);
        result.put("status", "RUNNING");
        result.put("stage", stage);
        result.put("profile", profile.name());
        result.put("documents", Integer.toString(profile.documents()));
        result.put("tokensPerDocument", "16");
        result.put("preBackupMutations", Integer.toString(profile.preBackupMutations()));
        result.put("continuedMutations", Integer.toString(profile.continuedMutations()));
        result.put("measurementSeconds", Long.toString(measurementSeconds));
        result.put("codecId", CODEC.codecId());
        result.put("codecVersion", Integer.toString(CODEC.codecVersion()));
        result.put("storageIdentity", STORAGE_ID);
        result.put("schemaIdentity", SCHEMA_ID);
        result.put("processCpuNanosAtStart", Long.toString(processCpuNanos()));
        return result;
    }

    private static void validateSourceProperties(
            Map<String, String> source,
            Profile profile,
            long measurementSeconds
    ) {
        Map<String, String> expected = base("source", profile, measurementSeconds);
        for (String key : List.of("schemaVersion", "stage", "profile", "documents",
                "tokensPerDocument", "preBackupMutations", "continuedMutations",
                "measurementSeconds", "codecId", "codecVersion", "storageIdentity",
                "schemaIdentity")) {
            if (!expected.get(key).equals(source.get(key))) {
                throw new IllegalArgumentException("source property differs: " + key);
            }
        }
        if (!"PASS".equals(source.get("status"))
                || !"PASS".equals(source.get("backup.status"))) {
            throw new IllegalArgumentException("source stage did not pass");
        }
    }

    private static SearchEngineBuilder<Integer, Document> builder() {
        return SearchEngine.builder(Document.class, ID)
                .field(BODY)
                .index(IndexDefinition.equality(BODY));
    }

    private static DurableStorageConfig<Integer, Document> config(
            Path directory,
            Profile profile
    ) {
        return DurableStorageConfig.builder(directory, CODEC)
                .storageIdentity(STORAGE_ID)
                .schemaIdentity(SCHEMA_ID)
                .maxDocuments(profile.documents() * 2)
                .maxBulkElements(SnapshotEngineConfig.DEFAULT.maxBatchSize())
                .checkpointWalBytes(256L * 1024 * 1024)
                .maxRetainedBytes(8L * 1024 * 1024 * 1024)
                .build();
    }

    private static DurableVerificationConfig<Integer, Document> verification(
            Profile profile
    ) {
        return new DurableVerificationConfig<>(STORAGE_ID, SCHEMA_ID, CODEC,
                CODEC.codecVersion(),
                DurableStorageConfig.DEFAULT_MAX_ENCODED_KEY_BYTES,
                DurableStorageConfig.DEFAULT_MAX_ENCODED_DOCUMENT_BYTES,
                profile.documents() * 2);
    }

    private static List<Document> documents(int count, int revision) {
        List<Document> result = new ArrayList<>(count);
        for (int id = 0; id < count; id++) {
            result.add(new Document(id, body(id, revision)));
        }
        return result;
    }

    private static void addInBatches(
            SearchEngine<Integer, Document> engine,
            List<Document> documents,
            int batchSize
    ) {
        for (int start = 0; start < documents.size(); start += batchSize) {
            engine.addAll(documents.subList(
                    start, Math.min(start + batchSize, documents.size()))).join();
        }
    }

    private static void updateRange(
            SearchEngine<Integer, Document> engine,
            int count,
            int revision,
            int batchSize
    ) {
        for (int start = 0; start < count; start += batchSize) {
            List<Document> updates = new ArrayList<>();
            for (int offset = start; offset < Math.min(start + batchSize, count);
                    offset++) {
                updates.add(new Document(offset, body(offset, revision)));
            }
            engine.updateAll(updates).join();
        }
    }

    private static void assertRetrieval(
            SearchEngine<Integer, Document> engine,
            Profile profile
    ) {
        int untouched = profile.documents() - 1;
        Document document = engine.get(untouched);
        List<Document> matches = engine.search(Query.eq(BODY, document.body()));
        if (!matches.equals(List.of(document))) {
            throw new IllegalStateException("restored retrieval oracle differs");
        }
    }

    private static String checksum(SearchEngine<Integer, Document> engine, int count) {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 is unavailable", impossible);
        }
        for (int id = 0; id < count; id++) {
            Document document = engine.get(id);
            if (document == null) {
                throw new IllegalStateException("missing document " + id);
            }
            byte[] encoded = CODEC.encodeDocument(document);
            digest.update(ByteBuffer.allocate(Integer.BYTES * 2)
                    .putInt(id).putInt(encoded.length).array());
            digest.update(encoded);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static String body(int id, int revision) {
        return "durable operational backup document id" + id
                + " revision " + revision
                + " alpha beta gamma delta epsilon zeta eta theta iota";
    }

    private static long heapUsedBytes() {
        return ManagementFactory.getMemoryMXBean().getHeapMemoryUsage().getUsed();
    }

    private static long processCpuNanos() {
        var operatingSystem = ManagementFactory.getOperatingSystemMXBean();
        if (operatingSystem instanceof com.sun.management.OperatingSystemMXBean sun) {
            return Math.max(0L, sun.getProcessCpuTime());
        }
        return 0L;
    }

    private static String elapsed(long started) {
        return Long.toString(Math.max(0L, System.nanoTime() - started));
    }

    private static long directoryBytes(Path directory) throws IOException {
        if (directory == null || !Files.exists(directory)) {
            return 0L;
        }
        long[] total = {0L};
        Files.walkFileTree(directory, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult visitFile(
                    Path file,
                    BasicFileAttributes attributes
            ) {
                if (attributes.isRegularFile()) {
                    total[0] = Math.addExact(total[0], attributes.size());
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFileFailed(Path file, IOException failure)
                    throws IOException {
                if (failure instanceof NoSuchFileException) {
                    // Checkpoint staging and atomic publication may remove paths.
                    return FileVisitResult.CONTINUE;
                }
                throw failure;
            }

            @Override
            public FileVisitResult postVisitDirectory(Path directory, IOException failure)
                    throws IOException {
                return failure == null
                        ? FileVisitResult.CONTINUE
                        : visitFileFailed(directory, failure);
            }
        });
        return total[0];
    }

    private static Path absent(String value, String name) {
        Path path = Path.of(value).toAbsolutePath().normalize();
        if (Files.exists(path)) {
            throw new IllegalArgumentException(name + " already exists: " + path);
        }
        return path;
    }

    private static Path absentFile(String value, String name) {
        Path path = Path.of(value).toAbsolutePath().normalize();
        if (Files.exists(path)) {
            throw new IllegalArgumentException(name + " already exists: " + path);
        }
        if (path.getParent() == null || !Files.isDirectory(path.getParent())) {
            throw new IllegalArgumentException(name + " parent must exist: " + path);
        }
        return path;
    }

    private static Path existingDirectory(String value, String name) {
        Path path = Path.of(value).toAbsolutePath().normalize();
        if (!Files.isDirectory(path)) {
            throw new IllegalArgumentException(name + " must exist: " + path);
        }
        return path;
    }

    private static Path existingFile(String value, String name) {
        Path path = Path.of(value).toAbsolutePath().normalize();
        if (!Files.isRegularFile(path)) {
            throw new IllegalArgumentException(name + " must exist: " + path);
        }
        return path;
    }

    private static Map<String, String> readProperties(Path path) throws IOException {
        Map<String, String> result = new TreeMap<>();
        for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            int separator = line.indexOf('=');
            if (separator <= 0 || separator == line.length() - 1
                    || result.put(line.substring(0, separator),
                    line.substring(separator + 1)) != null) {
                throw new IllegalArgumentException("invalid source properties");
            }
        }
        return result;
    }

    private static void writeProperties(Path path, Map<String, String> properties)
            throws IOException {
        properties.put("processCpuNanosAtEnd", Long.toString(processCpuNanos()));
        StringBuilder content = new StringBuilder();
        for (Map.Entry<String, String> entry : properties.entrySet()) {
            if (!entry.getKey().matches("[A-Za-z0-9.]+")
                    || entry.getValue().isEmpty()
                    || entry.getValue().contains("\n")
                    || entry.getValue().contains("\r")
                    || entry.getValue().contains("=")) {
                throw new IllegalArgumentException("invalid evidence property");
            }
            content.append(entry.getKey()).append('=').append(entry.getValue())
                    .append('\n');
        }
        Files.writeString(path, content, StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW);
    }

    private static long positiveLong(String value, String name) {
        try {
            long parsed = Long.parseLong(value);
            if (parsed <= 0) {
                throw new NumberFormatException("not positive");
            }
            return parsed;
        } catch (NumberFormatException failure) {
            throw new IllegalArgumentException(name + " must be positive");
        }
    }

    private static void usage() {
        throw new IllegalArgumentException(
                "usage: V41OperationalEvidenceProbe source <smoke|production> "
                        + "<store> <backup> <properties> <measurement-seconds> | "
                        + "restore <smoke|production> <backup> <target> "
                        + "<source-properties> <properties> <measurement-seconds>");
    }

    private record Document(int id, String body) {
    }

    private record Profile(
            String name,
            int documents,
            int preBackupMutations,
            int continuedMutations,
            int batchSize,
            int readers
    ) {
        static Profile named(String name) {
            return switch (name) {
                case "smoke" -> new Profile(name, 1_000, 100, 20, 100, 2);
                case "production" ->
                        new Profile(name, 100_000, 10_000, 1_000, 1_000, 8);
                default -> throw new IllegalArgumentException(
                        "profile must be smoke or production");
            };
        }
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v41-operational-codec-v1";
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
                throw new IllegalArgumentException("invalid integer key");
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
                throw new UncheckedIOException(impossible);
            }
        }

        @Override
        public Document decodeDocument(byte[] bytes) {
            try (DataInputStream input = new DataInputStream(
                    new ByteArrayInputStream(bytes))) {
                Document document = new Document(input.readInt(), input.readUTF());
                if (input.read() != -1) {
                    throw new IllegalArgumentException("trailing document bytes");
                }
                return document;
            } catch (IOException failure) {
                throw new IllegalArgumentException("invalid document bytes", failure);
            }
        }
    }
}
