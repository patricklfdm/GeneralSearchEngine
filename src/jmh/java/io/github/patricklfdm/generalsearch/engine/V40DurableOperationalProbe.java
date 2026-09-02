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
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurabilityMetrics;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;

/** Standalone operational evidence probe packaged only in the JMH artifact. */
public final class V40DurableOperationalProbe {
    private static final String SCHEMA = "gse-v40-performance-properties-v1";
    private static final String STORAGE_ID = "v40-performance-store-v1";
    private static final String SCHEMA_ID = "v40-performance-schema-v1";
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final DocumentCodec CODEC = new DocumentCodec();

    private V40DurableOperationalProbe() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 3) {
            throw new IllegalArgumentException(
                    "usage: V40DurableOperationalProbe "
                            + "<smoke|production> <workspace> <long-run-seconds>");
        }
        Profile profile = Profile.named(arguments[0]);
        Path workspace = Path.of(arguments[1]).toAbsolutePath().normalize();
        long longRunSeconds = positiveLong(arguments[2], "long-run-seconds");
        if (Files.exists(workspace)) {
            throw new IllegalArgumentException("workspace already exists: " + workspace);
        }
        Files.createDirectories(workspace);

        Map<String, String> result = new TreeMap<>();
        result.put("schemaVersion", SCHEMA);
        result.put("status", "RUNNING");
        result.put("profile", profile.name());
        result.put("documents", Integer.toString(profile.documents()));
        result.put("singleOperations", Integer.toString(profile.singleOperations()));
        result.put("bulkOperations", Integer.toString(profile.bulkOperations()));
        result.put("bulkSize", Integer.toString(profile.bulkSize()));
        result.put("producers", Integer.toString(profile.producers()));
        result.put("producerOperations", Integer.toString(profile.producerOperations()));
        result.put("longRunSeconds", Long.toString(longRunSeconds));
        result.put("codecId", CODEC.codecId());
        result.put("codecVersion", Integer.toString(CODEC.codecVersion()));
        result.put("storageIdentity", STORAGE_ID);
        result.put("schemaIdentity", SCHEMA_ID);

        runMutationCells(workspace.resolve("mutations"), profile, result);
        runGroupCommitCell(workspace.resolve("group-commit"), profile, result);
        runRecoveryCells(workspace.resolve("recovery"), profile, result);
        runLongRunCell(
                workspace.resolve("long-run"), profile, longRunSeconds, result);

        result.put("status", "PASS");
        writeProperties(workspace.resolve("performance.properties"), result);
        System.out.printf(
                "v40DurablePerformance=PASS profile=%s documents=%d "
                        + "singleOperations=%d bulkOperations=%d longRunSeconds=%d%n",
                profile.name(),
                profile.documents(),
                profile.singleOperations(),
                profile.bulkOperations(),
                longRunSeconds);
    }

    private static void runMutationCells(
            Path directory,
            Profile profile,
            Map<String, String> result
    ) throws Exception {
        Path durableDirectory = directory.resolve("durable");
        SearchEngine<Integer, Document> inMemory = builder().build();
        DurableSearchEngine<Integer, Document> durable = builder()
                .buildDurable(config(durableDirectory, profile));
        try {
            List<Document> initial = documents(profile.documents(), 0);
            inMemory.addAll(initial).join();
            durable.addAll(initial).join();

            List<Long> inMemorySingle = new ArrayList<>();
            List<Long> durableSingle = new ArrayList<>();
            for (int operation = 0; operation < profile.singleOperations(); operation++) {
                int id = operation % profile.documents();
                Document update = new Document(id, body(id, operation + 1));
                inMemorySingle.add(timed(() -> inMemory.update(update).join()));
                durableSingle.add(timed(() -> durable.update(update).join()));
            }

            List<Long> inMemoryBulk = new ArrayList<>();
            List<Long> durableBulk = new ArrayList<>();
            for (int operation = 0; operation < profile.bulkOperations(); operation++) {
                List<Document> batch = updateBatch(
                        operation * profile.bulkSize(),
                        profile.bulkSize(),
                        profile.documents(),
                        profile.singleOperations() + operation + 1);
                inMemoryBulk.add(timed(() -> inMemory.updateAll(batch).join()));
                durableBulk.add(timed(() -> durable.updateAll(batch).join()));
            }

            recordLatency(result, "mutation.inMemory.single", inMemorySingle);
            recordLatency(result, "mutation.durable.single", durableSingle);
            recordLatency(result, "mutation.inMemory.bulk", inMemoryBulk);
            recordLatency(result, "mutation.durable.bulk", durableBulk);
            result.put("mutation.bulkElements",
                    Integer.toString(profile.bulkSize()));

            long inMemoryChecksum = checksum(inMemory, profile.documents());
            long durableChecksum = checksum(durable, profile.documents());
            if (inMemoryChecksum != durableChecksum) {
                throw new IllegalStateException(
                        "in-memory and durable mutation checksums differ");
            }
            result.put("compatibility.inMemoryChecksum",
                    Long.toString(inMemoryChecksum));
            result.put("compatibility.durableChecksum",
                    Long.toString(durableChecksum));

            long encodedCorpusBytes = encodedBytes(
                    inMemory, profile.documents());
            DurabilityMetrics before = durable.durabilityMetrics();
            AtomicBoolean monitoring = new AtomicBoolean(true);
            AtomicLong temporaryPeak = new AtomicLong(directoryBytes(durableDirectory));
            AtomicReference<Throwable> monitorFailure = new AtomicReference<>();
            Thread monitor = new Thread(() -> {
                try {
                    while (monitoring.get()) {
                        temporaryPeak.accumulateAndGet(
                                directoryBytes(durableDirectory), Math::max);
                        Thread.sleep(1L);
                    }
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    monitorFailure.compareAndSet(null, interrupted);
                } catch (IOException failure) {
                    monitorFailure.compareAndSet(null, failure);
                }
            }, "v40-checkpoint-byte-monitor");
            monitor.start();
            long cpuBefore = processCpuNanos();
            long checkpointNanos;
            try {
                checkpointNanos = timed(() -> durable.checkpoint().join());
            } finally {
                monitoring.set(false);
                monitor.join(TimeUnit.SECONDS.toMillis(5));
            }
            if (monitor.isAlive()) {
                monitor.interrupt();
                throw new IllegalStateException("checkpoint byte monitor did not stop");
            }
            if (monitorFailure.get() != null) {
                throw new IllegalStateException(
                        "checkpoint byte monitor failed", monitorFailure.get());
            }
            long checkpointCpuNanos = nonNegativeDelta(
                    cpuBefore, processCpuNanos());
            DurabilityMetrics after = durable.durabilityMetrics();
            temporaryPeak.accumulateAndGet(
                    directoryBytes(durableDirectory), Math::max);
            result.put("checkpoint.elapsedNanos", Long.toString(checkpointNanos));
            result.put("checkpoint.processCpuNanos",
                    Long.toString(checkpointCpuNanos));
            result.put("checkpoint.retainedBeforeBytes",
                    Long.toString(before.retainedBytes()));
            result.put("checkpoint.temporaryPeakBytes",
                    Long.toString(temporaryPeak.get()));
            result.put("checkpoint.retainedAfterBytes",
                    Long.toString(after.retainedBytes()));
            result.put("checkpoint.encodedCorpusBytes",
                    Long.toString(encodedCorpusBytes));
            result.put("checkpoint.retainedAmplificationMicros",
                    Long.toString(ratioMicros(after.retainedBytes(), encodedCorpusBytes)));
            result.put("checkpoint.temporaryAmplificationMicros",
                    Long.toString(ratioMicros(temporaryPeak.get(), encodedCorpusBytes)));
        } finally {
            durable.close();
            inMemory.close();
        }
    }

    private static void runGroupCommitCell(
            Path directory,
            Profile profile,
            Map<String, String> result
    ) throws Exception {
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(directory, profile))) {
            engine.addAll(documents(profile.documents(), 0)).join();
            DurablePerformanceSnapshot before = performanceSnapshot(engine);
            CountDownLatch start = new CountDownLatch(1);
            ExecutorService producers = Executors.newFixedThreadPool(
                    profile.producers());
            ConcurrentLinkedQueue<Throwable> failures = new ConcurrentLinkedQueue<>();
            long started = System.nanoTime();
            try {
                List<CompletableFuture<Void>> workers = new ArrayList<>();
                for (int producer = 0; producer < profile.producers(); producer++) {
                    int producerId = producer;
                    workers.add(CompletableFuture.runAsync(() -> {
                        try {
                            start.await();
                            for (int operation = 0;
                                    operation < profile.producerOperations();
                                    operation++) {
                                int id = (producerId * profile.producerOperations()
                                        + operation) % profile.documents();
                                engine.update(new Document(
                                        id, body(id, operation + 10_000))).join();
                            }
                        } catch (Throwable failure) {
                            failures.add(failure);
                        }
                    }, producers));
                }
                start.countDown();
                CompletableFuture.allOf(
                        workers.toArray(CompletableFuture[]::new)).join();
            } finally {
                producers.shutdown();
                if (!producers.awaitTermination(30, TimeUnit.SECONDS)) {
                    producers.shutdownNow();
                    throw new IllegalStateException("group producers did not stop");
                }
            }
            if (!failures.isEmpty()) {
                throw new IllegalStateException(
                        "group commit producer failed", failures.peek());
            }
            long elapsed = Math.max(0L, System.nanoTime() - started);
            DurablePerformanceSnapshot after = performanceSnapshot(engine);
            long groups = after.forceGroups() - before.forceGroups();
            long units = after.forcedUnits() - before.forcedUnits();
            long expectedUnits = (long) profile.producers()
                    * profile.producerOperations();
            if (groups <= 0 || groups > units || units != expectedUnits) {
                throw new IllegalStateException(
                        "invalid force grouping: groups=" + groups + " units=" + units);
            }
            result.put("groupCommit.elapsedNanos", Long.toString(elapsed));
            result.put("groupCommit.forceGroups", Long.toString(groups));
            result.put("groupCommit.forcedUnits", Long.toString(units));
            result.put("groupCommit.averageGroupSizeMicros",
                    Long.toString(ratioMicros(units, groups)));
            result.put("groupCommit.maximumGroupSize",
                    Integer.toString(after.maximumForceGroupSize()));
            result.put("groupCommit.walAppendForceNanos",
                    Long.toString(after.walAppendForceNanos()
                            - before.walAppendForceNanos()));
        }
    }

    private static void runRecoveryCells(
            Path root,
            Profile profile,
            Map<String, String> result
    ) throws IOException {
        Files.createDirectories(root);
        recordRecovery(
                root.resolve("wal-only"), profile, false, 0,
                "recovery.walOnly", result);
        recordRecovery(
                root.resolve("checkpoint-only"), profile, true, 0,
                "recovery.checkpointOnly", result);
        recordRecovery(
                root.resolve("checkpoint-and-wal"), profile, true,
                profile.postCheckpointUnits(),
                "recovery.checkpointAndWal", result);
    }

    private static void recordRecovery(
            Path directory,
            Profile profile,
            boolean checkpoint,
            int postCheckpointUnits,
            String prefix,
            Map<String, String> result
    ) {
        DurableStorageConfig<Integer, Document> config = config(directory, profile);
        try (DurableSearchEngine<Integer, Document> writer = builder()
                .buildDurable(config)) {
            List<Document> corpus = documents(profile.recoveryDocuments(), 0);
            for (int start = 0; start < corpus.size(); start += profile.loadBatchSize()) {
                writer.addAll(corpus.subList(
                        start,
                        Math.min(start + profile.loadBatchSize(), corpus.size()))).join();
            }
            if (checkpoint) {
                writer.checkpoint().join();
            }
            for (int operation = 0; operation < postCheckpointUnits; operation++) {
                int id = operation % profile.recoveryDocuments();
                writer.update(new Document(id, body(id, operation + 50_000))).join();
            }
        }

        long started = System.nanoTime();
        try (DurableSearchEngine<Integer, Document> recovered = builder()
                .buildDurable(config)) {
            long totalOpenNanos = Math.max(0L, System.nanoTime() - started);
            DurabilityMetrics metrics = recovered.durabilityMetrics();
            DurablePerformanceSnapshot performance = performanceSnapshot(recovered);
            if (recovered.get(profile.recoveryDocuments() - 1) == null) {
                throw new IllegalStateException("recovery lost the final document");
            }
            result.put(prefix + ".source", metrics.recoverySource().name());
            result.put(prefix + ".documents",
                    Integer.toString(profile.recoveryDocuments()));
            result.put(prefix + ".replayedRecords",
                    Long.toString(metrics.replayedRecords()));
            result.put(prefix + ".totalOpenNanos", Long.toString(totalOpenNanos));
            result.put(prefix + ".reportedRecoveryNanos",
                    Long.toString(metrics.recoveryDuration().toNanos()));
            result.put(prefix + ".storageOpenNanos",
                    Long.toString(performance.storageOpenNanos()));
            result.put(prefix + ".checkpointLoadNanos",
                    Long.toString(performance.checkpointLoadNanos()));
            result.put(prefix + ".replayAndRebuildNanos",
                    Long.toString(performance.replayAndRebuildNanos()));
            result.put(prefix + ".indexRebuildNanos",
                    Long.toString(metrics.indexRebuildDuration().toNanos()));
            result.put(prefix + ".retainedBytes",
                    Long.toString(metrics.retainedBytes()));
            result.put(prefix + ".walBytes", Long.toString(metrics.walBytes()));
        }
    }

    private static void runLongRunCell(
            Path directory,
            Profile profile,
            long durationSeconds,
            Map<String, String> result
    ) throws Exception {
        try (DurableSearchEngine<Integer, Document> engine = builder()
                .buildDurable(config(directory, profile))) {
            engine.addAll(documents(profile.longRunDocuments(), 0)).join();
            AtomicBoolean stop = new AtomicBoolean();
            AtomicLong reads = new AtomicLong();
            AtomicLong writes = new AtomicLong();
            AtomicLong checkpoints = new AtomicLong();
            AtomicLong maximumRetained = new AtomicLong(
                    engine.durabilityMetrics().retainedBytes());
            AtomicReference<Throwable> failure = new AtomicReference<>();
            ExecutorService workers = Executors.newFixedThreadPool(
                    profile.longRunWriters() + profile.longRunReaders() + 1);
            CountDownLatch start = new CountDownLatch(1);
            for (int writer = 0; writer < profile.longRunWriters(); writer++) {
                int writerId = writer;
                workers.execute(() -> runWorker(start, stop, failure, () -> {
                    long operation = writes.getAndIncrement();
                    int id = (int) ((writerId + operation * profile.longRunWriters())
                            % profile.longRunDocuments());
                    engine.update(new Document(
                            id, body(id, Math.toIntExact(operation % 1_000_000)))).join();
                    maximumRetained.accumulateAndGet(
                            engine.durabilityMetrics().retainedBytes(), Math::max);
                }));
            }
            for (int reader = 0; reader < profile.longRunReaders(); reader++) {
                int readerId = reader;
                workers.execute(() -> runWorker(start, stop, failure, () -> {
                    long operation = reads.getAndIncrement();
                    int id = (int) ((readerId + operation) % profile.longRunDocuments());
                    Document document = engine.get(id);
                    if (document == null) {
                        throw new IllegalStateException("long-run read lost a document");
                    }
                }));
            }
            workers.execute(() -> runWorker(start, stop, failure, () -> {
                engine.checkpoint().join();
                checkpoints.incrementAndGet();
                maximumRetained.accumulateAndGet(
                        engine.durabilityMetrics().retainedBytes(), Math::max);
                Thread.sleep(profile.checkpointIntervalMillis());
            }));

            long started = System.nanoTime();
            start.countDown();
            try {
                Thread.sleep(TimeUnit.SECONDS.toMillis(durationSeconds));
            } finally {
                stop.set(true);
                workers.shutdown();
                if (!workers.awaitTermination(60, TimeUnit.SECONDS)) {
                    workers.shutdownNow();
                    throw new IllegalStateException("long-run workers did not stop");
                }
            }
            long elapsed = Math.max(0L, System.nanoTime() - started);
            if (failure.get() != null) {
                throw new IllegalStateException("long-run worker failed", failure.get());
            }
            engine.checkpoint().join();
            checkpoints.incrementAndGet();
            DurabilityMetrics metrics = engine.durabilityMetrics();
            result.put("longRun.elapsedNanos", Long.toString(elapsed));
            result.put("longRun.reads", Long.toString(reads.get()));
            result.put("longRun.writes", Long.toString(writes.get()));
            result.put("longRun.checkpoints", Long.toString(checkpoints.get()));
            result.put("longRun.maximumRetainedBytes",
                    Long.toString(maximumRetained.get()));
            result.put("longRun.finalRetainedBytes",
                    Long.toString(metrics.retainedBytes()));
            result.put("longRun.finalSequence",
                    Long.toString(engine.currentSequence()));
            result.put("longRun.status", metrics.status().name());
        }
    }

    private static void runWorker(
            CountDownLatch start,
            AtomicBoolean stop,
            AtomicReference<Throwable> failure,
            InterruptibleAction action
    ) {
        try {
            start.await();
            while (!stop.get() && failure.get() == null) {
                action.run();
            }
        } catch (Throwable caught) {
            failure.compareAndSet(null, caught);
            stop.set(true);
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
                .maxDocuments(Math.max(profile.documents(),
                        profile.recoveryDocuments()) * 2)
                .checkpointWalBytes(profile.checkpointWalBytes())
                .maxRetainedBytes(profile.maxRetainedBytes())
                .build();
    }

    private static DurablePerformanceSnapshot performanceSnapshot(
            DurableSearchEngine<Integer, Document> engine
    ) {
        return ((DurableSnapshotSearchEngine<Integer, Document>) engine)
                .performanceSnapshot();
    }

    private static List<Document> documents(int count, int revision) {
        List<Document> documents = new ArrayList<>(count);
        for (int id = 0; id < count; id++) {
            documents.add(new Document(id, body(id, revision)));
        }
        return documents;
    }

    private static List<Document> updateBatch(
            int start,
            int size,
            int documentCount,
            int revision
    ) {
        List<Document> documents = new ArrayList<>(size);
        int first = Math.floorMod(start, documentCount);
        for (int offset = 0; offset < size; offset++) {
            int id = (first + offset) % documentCount;
            documents.add(new Document(id, body(id, revision)));
        }
        return documents;
    }

    private static String body(int id, int revision) {
        return "durable operational document " + id + " revision " + revision;
    }

    private static long checksum(
            SearchEngine<Integer, Document> engine,
            int documents
    ) {
        long checksum = 1L;
        for (int id = 0; id < documents; id++) {
            Document document = engine.get(id);
            if (document == null) {
                throw new IllegalStateException("missing document " + id);
            }
            checksum = 31L * checksum + document.hashCode();
        }
        return checksum;
    }

    private static long encodedBytes(
            SearchEngine<Integer, Document> engine,
            int documents
    ) {
        long bytes = 0L;
        for (int id = 0; id < documents; id++) {
            bytes = Math.addExact(bytes, CODEC.encodeKey(id).length);
            bytes = Math.addExact(bytes,
                    CODEC.encodeDocument(engine.get(id)).length);
        }
        return bytes;
    }

    private static long timed(Runnable action) {
        long started = System.nanoTime();
        action.run();
        return Math.max(0L, System.nanoTime() - started);
    }

    private static void recordLatency(
            Map<String, String> result,
            String prefix,
            List<Long> samples
    ) {
        if (samples.isEmpty()) {
            throw new IllegalArgumentException("latency sample set must not be empty");
        }
        List<Long> ordered = new ArrayList<>(samples);
        Collections.sort(ordered);
        long total = 0L;
        for (long sample : ordered) {
            total = Math.addExact(total, sample);
        }
        result.put(prefix + ".count", Integer.toString(ordered.size()));
        result.put(prefix + ".meanNanos",
                Long.toString(total / ordered.size()));
        result.put(prefix + ".p50Nanos", Long.toString(percentile(ordered, 50)));
        result.put(prefix + ".p95Nanos", Long.toString(percentile(ordered, 95)));
        result.put(prefix + ".p99Nanos", Long.toString(percentile(ordered, 99)));
        result.put(prefix + ".maxNanos",
                Long.toString(ordered.getLast()));
    }

    private static long percentile(List<Long> ordered, int percentile) {
        int index = (int) Math.ceil(percentile / 100.0 * ordered.size()) - 1;
        return ordered.get(Math.max(0, Math.min(index, ordered.size() - 1)));
    }

    private static long directoryBytes(Path directory) throws IOException {
        if (!Files.exists(directory)) {
            return 0L;
        }
        long total = 0L;
        try (var members = Files.walk(directory)) {
            for (Path member : members.filter(Files::isRegularFile).toList()) {
                try {
                    total = Math.addExact(total, Files.size(member));
                } catch (NoSuchFileException disappearedDuringSample) {
                    // Checkpoint staging files are atomically renamed. A sampled
                    // directory member may legitimately disappear before size().
                }
            }
        }
        return total;
    }

    private static long processCpuNanos() {
        var operatingSystem = ManagementFactory.getOperatingSystemMXBean();
        if (operatingSystem instanceof com.sun.management.OperatingSystemMXBean sun) {
            return Math.max(0L, sun.getProcessCpuTime());
        }
        return 0L;
    }

    private static long nonNegativeDelta(long before, long after) {
        return after >= before ? after - before : 0L;
    }

    private static long ratioMicros(long numerator, long denominator) {
        if (denominator <= 0) {
            throw new IllegalArgumentException("ratio denominator must be positive");
        }
        if (numerator > Long.MAX_VALUE / 1_000_000L) {
            return Long.MAX_VALUE;
        }
        return numerator * 1_000_000L / denominator;
    }

    private static long positiveLong(String value, String name) {
        try {
            long parsed = Long.parseLong(value);
            if (parsed <= 0) {
                throw new NumberFormatException("not positive");
            }
            return parsed;
        } catch (NumberFormatException failure) {
            throw new IllegalArgumentException(name + " must be a positive integer");
        }
    }

    private static void writeProperties(
            Path path,
            Map<String, String> properties
    ) throws IOException {
        StringBuilder content = new StringBuilder();
        for (Map.Entry<String, String> entry : properties.entrySet()) {
            if (!entry.getKey().matches("[A-Za-z0-9.]+")
                    || entry.getValue().contains("\n")
                    || entry.getValue().contains("\r")
                    || entry.getValue().contains("=")) {
                throw new IllegalArgumentException("invalid evidence property");
            }
            content.append(entry.getKey()).append('=').append(entry.getValue())
                    .append('\n');
        }
        Files.writeString(
                path,
                content,
                StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW);
    }

    private record Document(int id, String body) {
    }

    private record Profile(
            String name,
            int documents,
            int singleOperations,
            int bulkOperations,
            int bulkSize,
            int producers,
            int producerOperations,
            int recoveryDocuments,
            int postCheckpointUnits,
            int loadBatchSize,
            int longRunDocuments,
            int longRunWriters,
            int longRunReaders,
            long checkpointIntervalMillis,
            long checkpointWalBytes,
            long maxRetainedBytes
    ) {
        static Profile named(String name) {
            return switch (name) {
                case "smoke" -> new Profile(
                        name, 1_000, 40, 10, 20, 4, 20,
                        1_000, 10, 500, 500, 1, 2, 250,
                        64L * 1024 * 1024, 512L * 1024 * 1024);
                case "production" -> new Profile(
                        name, 100_000, 1_000, 100, 100, 16, 200,
                        100_000, 1_000, 1_000, 10_000, 4, 8, 60_000,
                        256L * 1024 * 1024, 8L * 1024 * 1024 * 1024);
                default -> throw new IllegalArgumentException(
                        "profile must be smoke or production");
            };
        }
    }

    private static final class DocumentCodec
            implements DurableCodec<Integer, Document> {
        @Override
        public String codecId() {
            return "v40-performance-codec-v1";
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

    @FunctionalInterface
    private interface InterruptibleAction {
        void run() throws Exception;
    }
}
