package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.lang.management.MemoryUsage;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Properties;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.LongAdder;
import io.github.patricklfdm.generalsearch.engine.metrics.SearchEngineMetrics;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.search.SearchRequest;

/**
 * Opt-in V3 production soak that persists heap, GC, queue, throughput, and latency
 * evidence. It is intentionally not part of normal tests or CI.
 */
public final class V3ProductionSoak {
    private static final int RESERVOIR_SIZE = 20_000;

    private V3ProductionSoak() {
    }

    public static void main(String[] args) throws Exception {
        SoakConfig config = SoakConfig.parse(args);
        Files.createDirectories(config.output());
        writeConfig(config);

        long loadStarted = System.nanoTime();
        try (var fixture = V3ProductionBenchmarkSupport.createFixture(
                config.documentCount(),
                config.corpusProfile())) {
            double loadSeconds = elapsedSeconds(loadStarted);
            run(fixture, config, loadSeconds);
        } catch (Throwable failure) {
            Files.writeString(
                    config.output().resolve("failure.txt"),
                    stackTrace(failure),
                    StandardCharsets.UTF_8);
            rethrow(failure);
        }
    }

    private static void run(
            V3ProductionBenchmarkSupport.Fixture fixture,
            SoakConfig config,
            double loadSeconds
    ) throws Exception {
        List<SearchRequest<V3ProductionBenchmarkSupport.Document>> requests =
                V3ProductionBenchmarkSupport.requests(fixture, config.topK());
        AtomicBoolean stop = new AtomicBoolean();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        LongAdder readOperations = new LongAdder();
        LongAdder writeOperations = new LongAdder();
        LongAdder indexCycles = new LongAdder();
        LongAdder errors = new LongAdder();
        CountDownLatch start = new CountDownLatch(1);
        int taskCount = config.readerCount() + config.writerCount()
                + (config.indexCycles() ? 1 : 0);
        ExecutorService workers = Executors.newFixedThreadPool(taskCount);
        List<Future<WorkerResult>> readers = new ArrayList<>();
        List<Future<WorkerResult>> writers = new ArrayList<>();
        Future<?> lifecycle = null;
        try {
            for (int worker = 0; worker < config.readerCount(); worker++) {
                int workerId = worker;
                readers.add(workers.submit(guarded(failure, errors, () -> readLoop(
                        fixture,
                        requests,
                        workerId,
                        start,
                        stop,
                        readOperations))));
            }
            for (int worker = 0; worker < config.writerCount(); worker++) {
                int workerId = worker;
                writers.add(workers.submit(guarded(failure, errors, () -> writeLoop(
                        fixture,
                        config,
                        workerId,
                        start,
                        stop,
                        writeOperations))));
            }
            if (config.indexCycles()) {
                lifecycle = workers.submit(() -> lifecycleLoop(
                        fixture,
                        start,
                        stop,
                        failure,
                        errors,
                        indexCycles));
            }

            long runStarted = System.nanoTime();
            long deadline = runStarted + TimeUnit.SECONDS.toNanos(config.seconds());
            start.countDown();
            sampleUntilFinished(
                    fixture,
                    config,
                    runStarted,
                    deadline,
                    stop,
                    failure,
                    readOperations,
                    writeOperations,
                    indexCycles,
                    errors);
            stop.set(true);

            List<WorkerResult> readerResults = await(readers);
            List<WorkerResult> writerResults = await(writers);
            if (lifecycle != null) {
                lifecycle.get();
            }
            Throwable workerFailure = failure.get();
            if (workerFailure != null) {
                throw new IllegalStateException("soak worker failed", workerFailure);
            }
            writeSummary(
                    fixture,
                    config,
                    loadSeconds,
                    elapsedSeconds(runStarted),
                    readOperations.sum(),
                    writeOperations.sum(),
                    indexCycles.sum(),
                    errors.sum(),
                    readerResults,
                    writerResults);
        } finally {
            stop.set(true);
            start.countDown();
            workers.shutdownNow();
            workers.awaitTermination(30, TimeUnit.SECONDS);
        }
    }

    private static WorkerResult readLoop(
            V3ProductionBenchmarkSupport.Fixture fixture,
            List<SearchRequest<V3ProductionBenchmarkSupport.Document>> requests,
            int workerId,
            CountDownLatch start,
            AtomicBoolean stop,
            LongAdder operations
    ) throws InterruptedException {
        LatencyReservoir latency = new LatencyReservoir(RESERVOIR_SIZE, workerId + 1L);
        int cursor = workerId;
        start.await();
        while (!stop.get()) {
            SearchRequest<V3ProductionBenchmarkSupport.Document> request =
                    requests.get(Math.floorMod(cursor++, requests.size()));
            long started = System.nanoTime();
            int hitCount = fixture.engine().search(request).hits().size();
            latency.record(System.nanoTime() - started);
            if (hitCount > request.limit()) {
                throw new IllegalStateException("soak result exceeded request limit");
            }
            operations.increment();
        }
        return new WorkerResult(operations.sum(), latency);
    }

    private static WorkerResult writeLoop(
            V3ProductionBenchmarkSupport.Fixture fixture,
            SoakConfig config,
            int workerId,
            CountDownLatch start,
            AtomicBoolean stop,
            LongAdder operations
    ) throws InterruptedException {
        LatencyReservoir latency = new LatencyReservoir(
                RESERVOIR_SIZE,
                10_000L + workerId);
        long slot = workerId;
        start.await();
        while (!stop.get()) {
            int documentId = (int) Math.floorMod(slot, config.documentCount());
            int documentRevision = Math.toIntExact(
                    slot / config.documentCount() + 1L);
            var replacement = V3ProductionBenchmarkSupport.replacement(
                    documentId,
                    documentRevision,
                    fixture.profile());
            long started = System.nanoTime();
            fixture.engine().update(replacement).join();
            latency.record(System.nanoTime() - started);
            operations.increment();
            slot += config.writerCount();
        }
        return new WorkerResult(operations.sum(), latency);
    }

    private static void lifecycleLoop(
            V3ProductionBenchmarkSupport.Fixture fixture,
            CountDownLatch start,
            AtomicBoolean stop,
            AtomicReference<Throwable> failure,
            LongAdder errors,
            LongAdder cycles
    ) {
        try {
            start.await();
            while (!stop.get()) {
                fixture.engine().createIndex(IndexDefinition.range(
                        V3ProductionBenchmarkSupport.POPULARITY)).join();
                fixture.engine().dropIndex(
                        V3ProductionBenchmarkSupport.POPULARITY.name()).join();
                cycles.increment();
                if (!stop.get()) {
                    TimeUnit.SECONDS.sleep(1);
                }
            }
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        } catch (Throwable workerFailure) {
            errors.increment();
            failure.compareAndSet(null, workerFailure);
            stop.set(true);
        }
    }

    private static void sampleUntilFinished(
            V3ProductionBenchmarkSupport.Fixture fixture,
            SoakConfig config,
            long runStarted,
            long deadline,
            AtomicBoolean stop,
            AtomicReference<Throwable> failure,
            LongAdder reads,
            LongAdder writes,
            LongAdder indexCycles,
            LongAdder errors
    ) throws IOException, InterruptedException {
        Path output = config.output().resolve("soak-samples.csv");
        MemoryMXBean memory = ManagementFactory.getMemoryMXBean();
        try (PrintWriter csv = new PrintWriter(Files.newBufferedWriter(
                output,
                StandardCharsets.UTF_8))) {
            csv.println("timestamp,elapsed_s,used_heap_bytes,committed_heap_bytes,"
                    + "max_heap_bytes,read_ops,write_ops,index_cycles,errors,"
                    + "writer_queue_depth,writer_queue_capacity,snapshot_version,"
                    + "document_count,gc_count,gc_time_ms");
            while (System.nanoTime() < deadline && failure.get() == null) {
                writeSample(
                        csv,
                        fixture.engine().metrics(),
                        memory.getHeapMemoryUsage(),
                        runStarted,
                        reads.sum(),
                        writes.sum(),
                        indexCycles.sum(),
                        errors.sum());
                csv.flush();
                TimeUnit.SECONDS.sleep(config.sampleSeconds());
            }
            stop.set(true);
            writeSample(
                    csv,
                    fixture.engine().metrics(),
                    memory.getHeapMemoryUsage(),
                    runStarted,
                    reads.sum(),
                    writes.sum(),
                    indexCycles.sum(),
                    errors.sum());
        }
    }

    private static void writeSample(
            PrintWriter csv,
            SearchEngineMetrics metrics,
            MemoryUsage heap,
            long runStarted,
            long reads,
            long writes,
            long indexCycles,
            long errors
    ) {
        csv.printf(Locale.ROOT,
                "%s,%.3f,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d%n",
                Instant.now(),
                elapsedSeconds(runStarted),
                heap.getUsed(),
                heap.getCommitted(),
                heap.getMax(),
                reads,
                writes,
                indexCycles,
                errors,
                metrics.writerQueueDepth(),
                metrics.writerQueueCapacity(),
                metrics.snapshotVersion(),
                metrics.documentCount(),
                gcCount(),
                gcTimeMillis());
    }

    private static void writeConfig(SoakConfig config) throws IOException {
        Properties values = new Properties();
        values.setProperty("status", "CONFIGURED");
        values.setProperty("documents", Integer.toString(config.documentCount()));
        values.setProperty("readers", Integer.toString(config.readerCount()));
        values.setProperty("writers", Integer.toString(config.writerCount()));
        values.setProperty("seconds", Integer.toString(config.seconds()));
        values.setProperty("sample_seconds", Integer.toString(config.sampleSeconds()));
        values.setProperty("top_k", Integer.toString(config.topK()));
        values.setProperty("corpus_profile", config.corpusProfile());
        values.setProperty("index_cycles", Boolean.toString(config.indexCycles()));
        try (var output = Files.newOutputStream(
                config.output().resolve("soak-config.properties"))) {
            values.store(output, "V3 production soak configuration");
        }
    }

    private static void writeSummary(
            V3ProductionBenchmarkSupport.Fixture fixture,
            SoakConfig config,
            double loadSeconds,
            double runSeconds,
            long reads,
            long writes,
            long indexCycles,
            long errors,
            List<WorkerResult> readerResults,
            List<WorkerResult> writerResults
    ) throws IOException {
        long[] readLatency = samples(readerResults);
        long[] writeLatency = samples(writerResults);
        SearchEngineMetrics metrics = fixture.engine().metrics();
        Properties values = new Properties();
        values.setProperty("status", errors == 0 ? "PASS" : "FAIL");
        values.setProperty("load_seconds", decimal(loadSeconds));
        values.setProperty("run_seconds", decimal(runSeconds));
        values.setProperty("read_operations", Long.toString(reads));
        values.setProperty("write_operations", Long.toString(writes));
        values.setProperty("index_cycles", Long.toString(indexCycles));
        values.setProperty("errors", Long.toString(errors));
        values.setProperty("read_ops_per_second", decimal(reads / runSeconds));
        values.setProperty("write_ops_per_second", decimal(writes / runSeconds));
        addLatency(values, "read", readLatency, maxLatency(readerResults));
        addLatency(values, "write", writeLatency, maxLatency(writerResults));
        values.setProperty("final_snapshot_version",
                Long.toString(metrics.snapshotVersion()));
        values.setProperty("final_document_count",
                Integer.toString(metrics.documentCount()));
        values.setProperty("final_writer_queue_depth",
                Integer.toString(metrics.writerQueueDepth()));
        values.setProperty("gc_count", Long.toString(gcCount()));
        values.setProperty("gc_time_ms", Long.toString(gcTimeMillis()));
        try (var output = Files.newOutputStream(
                config.output().resolve("soak-summary.properties"))) {
            values.store(output, "V3 production soak result");
        }
    }

    private static void addLatency(
            Properties values,
            String prefix,
            long[] samples,
            long maxNanoseconds
    ) {
        values.setProperty(prefix + "_latency_samples",
                Integer.toString(samples.length));
        values.setProperty(prefix + "_latency_p50_us",
                decimal(percentile(samples, 0.50) / 1_000.0));
        values.setProperty(prefix + "_latency_p95_us",
                decimal(percentile(samples, 0.95) / 1_000.0));
        values.setProperty(prefix + "_latency_p99_us",
                decimal(percentile(samples, 0.99) / 1_000.0));
        values.setProperty(prefix + "_latency_max_us",
                decimal(maxNanoseconds / 1_000.0));
    }

    private static long maxLatency(List<WorkerResult> results) {
        return results.stream()
                .mapToLong(result -> result.latency().max())
                .max()
                .orElse(0L);
    }

    private static long[] samples(List<WorkerResult> results) {
        int size = results.stream()
                .mapToInt(result -> result.latency().size())
                .sum();
        long[] combined = new long[size];
        int offset = 0;
        for (WorkerResult result : results) {
            long[] workerSamples = result.latency().samples();
            System.arraycopy(workerSamples, 0, combined, offset, workerSamples.length);
            offset += workerSamples.length;
        }
        Arrays.sort(combined);
        return combined;
    }

    private static double percentile(long[] sorted, double percentile) {
        if (sorted.length == 0) {
            return 0.0;
        }
        int index = (int) Math.ceil(percentile * sorted.length) - 1;
        return sorted[Math.max(0, Math.min(index, sorted.length - 1))];
    }

    private static <T> Callable<T> guarded(
            AtomicReference<Throwable> failure,
            LongAdder errors,
            Callable<T> action
    ) {
        return () -> {
            try {
                return action.call();
            } catch (Throwable workerFailure) {
                errors.increment();
                failure.compareAndSet(null, workerFailure);
                rethrow(workerFailure);
                throw new AssertionError("unreachable");
            }
        };
    }

    private static void rethrow(Throwable failure) throws Exception {
        if (failure instanceof Exception exception) {
            throw exception;
        }
        if (failure instanceof Error error) {
            throw error;
        }
        throw new RuntimeException(failure);
    }

    private static List<WorkerResult> await(
            List<Future<WorkerResult>> futures
    ) throws Exception {
        List<WorkerResult> results = new ArrayList<>(futures.size());
        for (Future<WorkerResult> future : futures) {
            results.add(future.get());
        }
        return results;
    }

    private static long gcCount() {
        return ManagementFactory.getGarbageCollectorMXBeans().stream()
                .mapToLong(GarbageCollectorMXBean::getCollectionCount)
                .filter(value -> value >= 0)
                .sum();
    }

    private static long gcTimeMillis() {
        return ManagementFactory.getGarbageCollectorMXBeans().stream()
                .mapToLong(GarbageCollectorMXBean::getCollectionTime)
                .filter(value -> value >= 0)
                .sum();
    }

    private static double elapsedSeconds(long started) {
        return (System.nanoTime() - started) / 1_000_000_000.0;
    }

    private static String decimal(double value) {
        return String.format(Locale.ROOT, "%.3f", value);
    }

    private static String stackTrace(Throwable failure) {
        StringWriter output = new StringWriter();
        failure.printStackTrace(new PrintWriter(output));
        return output.toString();
    }

    private record WorkerResult(long operations, LatencyReservoir latency) {
    }

    private static final class LatencyReservoir {
        private final long[] samples;
        private int size;
        private long seen;
        private long randomState;
        private long max;

        private LatencyReservoir(int capacity, long seed) {
            samples = new long[capacity];
            randomState = seed;
        }

        private void record(long nanoseconds) {
            seen++;
            max = Math.max(max, nanoseconds);
            if (size < samples.length) {
                samples[size++] = nanoseconds;
                return;
            }
            randomState = randomState * 6_364_136_223_846_793_005L
                    + 1_442_695_040_888_963_407L;
            long selected = Math.floorMod(randomState, seen);
            if (selected < samples.length) {
                samples[(int) selected] = nanoseconds;
            }
        }

        private int size() {
            return size;
        }

        private long[] samples() {
            return Arrays.copyOf(samples, size);
        }

        private long max() {
            return max;
        }
    }

    private record SoakConfig(
            Path output,
            int documentCount,
            int readerCount,
            int writerCount,
            int seconds,
            int sampleSeconds,
            int topK,
            String corpusProfile,
            boolean indexCycles
    ) {
        private SoakConfig {
            if (documentCount <= 0 || readerCount <= 0 || writerCount <= 0
                    || seconds <= 0 || sampleSeconds <= 0 || topK <= 0) {
                throw new IllegalArgumentException(
                        "numeric soak arguments must be positive");
            }
        }

        private static SoakConfig parse(String[] args) {
            int readers = Math.max(2, Math.min(
                    16,
                    Runtime.getRuntime().availableProcessors() - 2));
            return new SoakConfig(
                    Path.of(stringArg(args, "--output", "benchmark-results/soak")),
                    intArg(args, "--documents", 100_000),
                    intArg(args, "--readers", readers),
                    intArg(args, "--writers", 1),
                    intArg(args, "--seconds", 1_800),
                    intArg(args, "--sample-seconds", 1),
                    intArg(args, "--top-k", 10),
                    stringArg(args, "--corpus-profile", "zipf-en-medium-4"),
                    booleanArg(args, "--index-cycles", true));
        }

        private static int intArg(String[] args, String name, int fallback) {
            return Integer.parseInt(stringArg(args, name, Integer.toString(fallback)));
        }

        private static boolean booleanArg(
                String[] args,
                String name,
                boolean fallback
        ) {
            return Boolean.parseBoolean(stringArg(
                    args,
                    name,
                    Boolean.toString(fallback)));
        }

        private static String stringArg(
                String[] args,
                String name,
                String fallback
        ) {
            String prefix = name + "=";
            for (String argument : args) {
                if (argument.startsWith(prefix)) {
                    return argument.substring(prefix.length());
                }
            }
            return fallback;
        }
    }
}
