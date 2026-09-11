package io.github.patricklfdm.generalsearch.engine;

import java.io.IOException;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.stream.Stream;
import io.github.patricklfdm.generalsearch.analysis.SimpleAnalyzer;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableCodec;
import io.github.patricklfdm.generalsearch.durability.DurableSearchEngine;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageFormat;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Benchmark-only bounded V4.4 dense scale, concurrency and resource probe. */
final class V44FinalDurableLocalProbe {
    private static final int DOCUMENTS = 20_000;
    private static final int MUTATIONS = 2_000;
    private static final int READERS = 4;
    private static final int CHECKPOINT_EVERY = 500;
    private static final int VALUE_BYTES = 256;
    private static final long SEED = 440_001L;
    private static final Field<Document, Long> ID =
            Field.of("id", Long.class, Document::id);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final Field<Document, Integer> PRICE =
            Field.of("price", Integer.class, Document::price);
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, SimpleAnalyzer.INSTANCE);
    private static final Codec CODEC = new Codec();

    private V44FinalDurableLocalProbe() {
    }

    public static void main(String[] arguments) throws Exception {
        if (arguments.length != 2) {
            throw new IllegalArgumentException(
                    "usage: V44FinalDurableLocalProbe <workspace> <duration-seconds>");
        }
        Path workspace = Path.of(arguments[0]).toAbsolutePath().normalize();
        int durationSeconds = Integer.parseInt(arguments[1]);
        if (Files.exists(workspace) || durationSeconds < 1 || durationSeconds > 180) {
            throw new IllegalArgumentException("probe input is outside frozen bounds");
        }
        Files.createDirectories(workspace);
        run(workspace, durationSeconds);
    }

    private static void run(Path workspace, int durationSeconds) throws Exception {
        Path store = workspace.resolve("store");
        Map<String, String> result = base(durationSeconds);
        long cpuStart = processCpuNanos();
        long gcCountStart = gcCount();
        long gcTimeStart = gcTimeMillis();
        long started = System.nanoTime();
        AtomicBoolean monitorStop = new AtomicBoolean();
        AtomicLong peakBytes = new AtomicLong();
        AtomicReference<Throwable> monitorFailure = new AtomicReference<>();
        Thread monitor = new Thread(() -> monitorBytes(
                workspace, monitorStop, peakBytes, monitorFailure),
                "v44-local-byte-monitor");
        monitor.setDaemon(true);
        monitor.start();

        AtomicLong reads = new AtomicLong();
        AtomicLong searches = new AtomicLong();
        AtomicReference<Throwable> workerFailure = new AtomicReference<>();
        AtomicBoolean readersStop = new AtomicBoolean();
        ExecutorService readers = Executors.newFixedThreadPool(READERS);
        CountDownLatch readerStart = new CountDownLatch(1);
        long sequence;
        String beforeClose;
        long retainedBytes;
        long walBytes;
        try (DurableSearchEngine<Long, Document> engine = builder()
                .buildDurable(config(store))) {
            addInitial(engine);
            engine.checkpoint().join();
            for (int reader = 0; reader < READERS; reader++) {
                int readerId = reader;
                readers.execute(() -> readLoop(
                        engine, readerId, readerStart, readersStop,
                        reads, searches, workerFailure));
            }
            long concurrentStarted = System.nanoTime();
            readerStart.countDown();
            int checkpoints = 0;
            int backups = 0;
            for (int mutation = 0; mutation < MUTATIONS; mutation++) {
                engine.update(document(mutation, 1)).join();
                if ((mutation + 1) % CHECKPOINT_EVERY == 0) {
                    engine.checkpoint().join();
                    checkpoints++;
                    if (checkpoints % 2 == 0) {
                        backups++;
                        Path backup = workspace.resolve("backup-" + backups);
                        engine.backup(new DurableBackupRequest(
                                backup, 8L * 1024 * 1024 * 1024)).join();
                        if (DurableStorageOperations.verifyBackup(backup).status()
                                != DurableVerificationStatus.VALID) {
                            throw new IllegalStateException("backup did not verify");
                        }
                    }
                }
            }
            long minimumEnd = concurrentStarted
                    + TimeUnit.SECONDS.toNanos(durationSeconds);
            while (System.nanoTime() < minimumEnd && workerFailure.get() == null) {
                Thread.sleep(10L);
            }
            readersStop.set(true);
            readers.shutdown();
            if (!readers.awaitTermination(30, TimeUnit.SECONDS)) {
                readers.shutdownNow();
                throw new IllegalStateException("reader workers did not stop");
            }
            if (workerFailure.get() != null) {
                throw new IllegalStateException(
                        "concurrent reader failed", workerFailure.get());
            }
            if (checkpoints != 4 || backups != 2) {
                throw new IllegalStateException("checkpoint/backup cadence drifted");
            }
            beforeClose = semanticDigest(engine, false);
            sequence = engine.currentSequence();
            retainedBytes = engine.durabilityMetrics().retainedBytes();
            walBytes = engine.durabilityMetrics().walBytes();
            result.put("measurement.concurrentNanos",
                    Long.toString(System.nanoTime() - concurrentStarted));
            result.put("measurement.reads", Long.toString(reads.get()));
            result.put("measurement.searches", Long.toString(searches.get()));
            result.put("measurement.writes", Integer.toString(MUTATIONS));
            result.put("measurement.checkpoints", Integer.toString(checkpoints));
            result.put("measurement.backups", Integer.toString(backups));
            result.put("measurement.sequence", Long.toString(sequence));
            result.put("measurement.retainedBytes", Long.toString(retainedBytes));
            result.put("measurement.walBytes", Long.toString(walBytes));
            result.put("oracle.beforeClose", beforeClose);
        } finally {
            readersStop.set(true);
            readers.shutdownNow();
        }

        if (sequence != 2_020L || reads.get() == 0 || searches.get() == 0) {
            throw new IllegalStateException("dense workload did not make exact progress");
        }
        long[] reopen = new long[3];
        for (int sample = 0; sample < reopen.length; sample++) {
            long reopenStarted = System.nanoTime();
            try (DurableSearchEngine<Long, Document> engine = builder()
                    .buildDurable(config(store))) {
                reopen[sample] = System.nanoTime() - reopenStarted;
                if (!beforeClose.equals(semanticDigest(engine, false))) {
                    throw new IllegalStateException("reopen semantic digest differs");
                }
            }
        }
        java.util.Arrays.sort(reopen);
        result.put("reopen.samplesNanos", "%d,%d,%d".formatted(
                reopen[0], reopen[1], reopen[2]));
        result.put("reopen.medianNanos", Long.toString(reopen[1]));
        result.put("reopen.maximumNanos", Long.toString(reopen[2]));

        String afterContinuation;
        try (DurableSearchEngine<Long, Document> engine = builder()
                .buildDurable(config(store))) {
            engine.update(document(DOCUMENTS - 1L, 2)).join();
            engine.checkpoint().join();
            if (engine.currentSequence() != 2_021L) {
                throw new IllegalStateException("continuation sequence differs");
            }
            afterContinuation = semanticDigest(engine, true);
        }
        try (DurableSearchEngine<Long, Document> engine = builder()
                .buildDurable(config(store))) {
            if (!afterContinuation.equals(semanticDigest(engine, true))) {
                throw new IllegalStateException("second reopen digest differs");
            }
        }

        monitorStop.set(true);
        monitor.join(30_000L);
        if (monitor.isAlive()) {
            monitor.interrupt();
            throw new IllegalStateException("byte monitor did not stop");
        }
        if (monitorFailure.get() != null) {
            throw new IllegalStateException("byte monitor failed", monitorFailure.get());
        }
        long finalBytes = directoryBytes(workspace);
        peakBytes.accumulateAndGet(finalBytes, Math::max);
        result.put("resource.finalDirectoryBytes", Long.toString(finalBytes));
        result.put("resource.peakDirectoryBytes", Long.toString(peakBytes.get()));
        result.put("resource.heapUsedBytes", Long.toString(heapUsedBytes()));
        result.put("resource.heapMaximumBytes",
                Long.toString(Runtime.getRuntime().maxMemory()));
        result.put("resource.processCpuNanos",
                Long.toString(Math.max(0L, processCpuNanos() - cpuStart)));
        result.put("resource.gcCount",
                Long.toString(Math.max(0L, gcCount() - gcCountStart)));
        result.put("resource.gcTimeMillis",
                Long.toString(Math.max(0L, gcTimeMillis() - gcTimeStart)));
        result.put("measurement.totalNanos",
                Long.toString(System.nanoTime() - started));
        result.put("oracle.afterContinuation", afterContinuation);
        result.put("status", "PASS");
        writeProperties(workspace.resolve("performance.properties"), result);
        System.out.printf(
                "v44LocalHardening=PASS documents=%d mutations=%d readers=%d "
                        + "reads=%d searches=%d checkpoints=4 backups=2 "
                        + "sequence=2021 peakBytes=%d%n",
                DOCUMENTS, MUTATIONS, READERS, reads.get(), searches.get(),
                peakBytes.get());
    }

    private static void addInitial(DurableSearchEngine<Long, Document> engine) {
        for (int start = 0; start < DOCUMENTS; start += 1_000) {
            List<Document> batch = new ArrayList<>(1_000);
            for (int id = start; id < Math.min(DOCUMENTS, start + 1_000); id++) {
                batch.add(document(id, 0));
            }
            engine.addAll(batch).join();
        }
    }

    private static void readLoop(
            DurableSearchEngine<Long, Document> engine,
            int readerId,
            CountDownLatch start,
            AtomicBoolean stop,
            AtomicLong reads,
            AtomicLong searches,
            AtomicReference<Throwable> failure
    ) {
        try {
            start.await();
            long operation = readerId;
            while (!stop.get() && failure.get() == null) {
                long id = Math.floorMod(operation * 31L + SEED, DOCUMENTS);
                if (engine.get(id) == null) {
                    throw new IllegalStateException("reader lost document " + id);
                }
                reads.incrementAndGet();
                if ((operation & 4095L) == 0L) {
                    if (engine.search(Query.eq(CATEGORY, "category-7")).isEmpty()) {
                        throw new IllegalStateException("indexed query lost candidates");
                    }
                    searches.incrementAndGet();
                }
                if ((operation & 255L) == 0L) {
                    Thread.sleep(1L);
                }
                operation++;
            }
        } catch (Throwable caught) {
            failure.compareAndSet(null, caught);
            stop.set(true);
        }
    }

    private static String semanticDigest(
            DurableSearchEngine<Long, Document> engine,
            boolean continued
    ) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        List<Long> equality = new ArrayList<>();
        List<Long> range = new ArrayList<>();
        List<Long> prefix = new ArrayList<>();
        for (long id = 0; id < DOCUMENTS; id++) {
            int revision = id < MUTATIONS ? 1 : 0;
            if (continued && id == DOCUMENTS - 1L) {
                revision = 2;
            }
            Document expected = document(id, revision);
            Document observed = engine.get(id);
            if (!expected.equals(observed)) {
                throw new IllegalStateException("document differs: " + id);
            }
            digest.update(CODEC.encodeDocument(observed));
            if (expected.category().equals("category-7")) {
                equality.add(id);
            }
            if (100 <= expected.price() && expected.price() <= 200) {
                range.add(id);
            }
            if (expected.title().startsWith("title-10")) {
                prefix.add(id);
            }
        }
        requireIds(equality, engine.search(Query.eq(CATEGORY, "category-7")));
        requireIds(range, engine.search(Query.between(PRICE, 100, 200)));
        requireIds(prefix, engine.search(Query.prefix(TITLE, "title-10")));
        if (engine.search(Query.allTerms(TEXT, "java durable")).size() != DOCUMENTS) {
            throw new IllegalStateException("text result count differs");
        }
        digest.update(Long.toString(engine.currentSequence())
                .getBytes(StandardCharsets.US_ASCII));
        return HexFormat.of().formatHex(digest.digest());
    }

    private static void requireIds(List<Long> expected, List<Document> observed) {
        List<Long> actual = observed.stream().map(Document::id).sorted().toList();
        if (!expected.equals(actual)) {
            throw new IllegalStateException("structured query result differs");
        }
    }

    private static SearchEngineBuilder<Long, Document> builder() {
        return SearchEngine.builder(Document.class, ID)
                .field(CATEGORY).field(PRICE).field(TITLE).textField(TEXT)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.range(PRICE))
                .index(IndexDefinition.prefix(TITLE))
                .index(IndexDefinition.text(TEXT));
    }

    private static DurableStorageConfig<Long, Document> config(Path directory) {
        return DurableStorageConfig.builder(directory, CODEC)
                .format(DurableStorageFormat.V1_2)
                .storageIdentity("v44-final-durable-local-v1")
                .schemaIdentity("v44-final-durable-schema-v1")
                .maxDocuments(40_000)
                .maxBulkElements(1_000)
                .checkpointWalBytes(256L * 1024 * 1024)
                .maxRetainedBytes(8L * 1024 * 1024 * 1024)
                .maxDerivedStateBytes(2L * 1024 * 1024 * 1024)
                .build();
    }

    private static Document document(long id, int revision) {
        return new Document(id, "category-" + (id % 32),
                (int) (id % 10_000), "title-" + (id % 2_048),
                "java search durable final hardening local scale concurrent "
                        + "checkpoint backup restore migration reopen resource token "
                        + "token" + (id % 97), revision);
    }

    private static Map<String, String> base(int durationSeconds) {
        Map<String, String> result = new TreeMap<>();
        result.put("schemaVersion", "gse-v44-local-hardening-properties-v1");
        result.put("status", "RUNNING");
        result.put("profile", "dense");
        result.put("seed", Long.toString(SEED));
        result.put("documents", Integer.toString(DOCUMENTS));
        result.put("tokensPerDocument", "16");
        result.put("keyBytes", "8");
        result.put("valueBytes", Integer.toString(VALUE_BYTES));
        result.put("indexes", "4");
        result.put("mutations", Integer.toString(MUTATIONS));
        result.put("readers", Integer.toString(READERS));
        result.put("writers", "1");
        result.put("checkpointEveryMutations", Integer.toString(CHECKPOINT_EVERY));
        result.put("backupEveryCheckpoints", "2");
        result.put("migrationCount", "4");
        result.put("durationSeconds", Integer.toString(durationSeconds));
        result.put("pageCacheTreatment", "uncontrolled-local-page-cache");
        result.put("filesystem", System.getProperty("os.name") + "-local-filesystem");
        result.put("gc", "G1");
        return result;
    }

    private static void monitorBytes(
            Path workspace,
            AtomicBoolean stop,
            AtomicLong peak,
            AtomicReference<Throwable> failure
    ) {
        try {
            while (!stop.get()) {
                peak.accumulateAndGet(directoryBytes(workspace), Math::max);
                Thread.sleep(2L);
            }
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            failure.compareAndSet(null, interrupted);
        } catch (IOException caught) {
            failure.compareAndSet(null, caught);
        }
    }

    private static long directoryBytes(Path directory) throws IOException {
        if (!Files.exists(directory)) {
            return 0L;
        }
        long total = 0L;
        try (Stream<Path> paths = Files.walk(directory)) {
            for (Path path : paths.sorted(Comparator.naturalOrder()).toList()) {
                try {
                    if (Files.isRegularFile(path) && !Files.isSymbolicLink(path)) {
                        total = Math.addExact(total, Files.size(path));
                    }
                } catch (NoSuchFileException ignored) {
                    // A checkpoint may retire a member between inventory and size.
                }
            }
        }
        return total;
    }

    private static long heapUsedBytes() {
        return ManagementFactory.getMemoryMXBean().getHeapMemoryUsage().getUsed();
    }

    private static long processCpuNanos() {
        var bean = ManagementFactory.getOperatingSystemMXBean();
        if (bean instanceof com.sun.management.OperatingSystemMXBean sun) {
            return Math.max(0L, sun.getProcessCpuTime());
        }
        return 0L;
    }

    private static long gcCount() {
        return ManagementFactory.getGarbageCollectorMXBeans().stream()
                .mapToLong(GarbageCollectorMXBean::getCollectionCount)
                .filter(value -> value >= 0L).sum();
    }

    private static long gcTimeMillis() {
        return ManagementFactory.getGarbageCollectorMXBeans().stream()
                .mapToLong(GarbageCollectorMXBean::getCollectionTime)
                .filter(value -> value >= 0L).sum();
    }

    private static void writeProperties(Path path, Map<String, String> values)
            throws IOException {
        StringBuilder content = new StringBuilder();
        for (Map.Entry<String, String> entry : values.entrySet()) {
            if (!entry.getKey().matches("[A-Za-z0-9.]+")
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

    private record Document(long id, String category, int price, String title,
                            String body, int revision) {
    }

    private static final class Codec implements DurableCodec<Long, Document> {
        @Override
        public String codecId() {
            return "v44-final-durable-codec-v1";
        }

        @Override
        public int codecVersion() {
            return 1;
        }

        @Override
        public byte[] encodeKey(Long key) {
            return ByteBuffer.allocate(Long.BYTES).putLong(key).array();
        }

        @Override
        public Long decodeKey(byte[] encoded) {
            if (encoded.length != Long.BYTES) {
                throw new IllegalArgumentException("invalid long key");
            }
            return ByteBuffer.wrap(encoded).getLong();
        }

        @Override
        public byte[] encodeDocument(Document value) {
            if (!value.equals(document(value.id(), value.revision()))) {
                throw new IllegalArgumentException("document fields are inconsistent");
            }
            return ByteBuffer.allocate(VALUE_BYTES)
                    .putLong(value.id()).putInt(value.revision()).array();
        }

        @Override
        public Document decodeDocument(byte[] encoded) {
            if (encoded.length != VALUE_BYTES) {
                throw new IllegalArgumentException("invalid fixed document bytes");
            }
            ByteBuffer input = ByteBuffer.wrap(encoded);
            long id = input.getLong();
            int revision = input.getInt();
            while (input.hasRemaining()) {
                if (input.get() != 0) {
                    throw new IllegalArgumentException("invalid document padding");
                }
            }
            return document(id, revision);
        }
    }
}
