package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.EnumMap;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Properties;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.LongAdder;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.exception.DocumentNotFoundException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchPageRequest;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.TotalHitsMode;

/**
 * Bounded calibration for the V3.4 long-run sampler and mixed workload. Local runs
 * remain capped at 30 minutes. The separately identified final-v34 cloud lane may
 * select the frozen 30-minute or two-hour duration.
 */
public final class V34LongRunCalibration {
    private static final int MAX_SECONDS = 1_800;
    private static final int MAX_FINAL_CLOUD_SECONDS = 7_200;
    private static final int MAX_DOCUMENTS = 1_000_000;
    private static final int RESERVOIR_SIZE = 8_192;

    private V34LongRunCalibration() {
    }

    public static void main(String[] arguments) throws Exception {
        Config config = Config.parse(arguments);
        Files.createDirectories(config.output());
        writeConfig(config);
        try {
            Result result = run(config);
            writeSummary(config, result);
            writeManifest(config.output());
            System.out.printf(Locale.ROOT,
                    "longRun=SUCCESS seconds=%d warmupSeconds=%d windows=%d "
                            + "documents=%d readers=%d readOperations=%d "
                            + "writeBatches=%d writeMutations=%d bursts=%d "
                            + "lifecycleCycles=%d expectedFailures=%d "
                            + "unexpectedFailures=%d unresolvedFutures=%d "
                            + "queueMaximum=%d snapshotDelta=%d gcCount=%d "
                            + "gcTimeMillis=%d checksum=%d corpusDigest=%s "
                            + "output=%s%n",
                    config.seconds(),
                    config.warmupSeconds(),
                    result.windows().size(),
                    config.documentCount(),
                    config.readerCount(),
                    result.readOperations(),
                    result.writeBatches(),
                    result.writeMutations(),
                    result.bursts(),
                    result.lifecycleCycles(),
                    result.expectedFailures(),
                    result.unexpectedFailures(),
                    result.unresolvedFutures(),
                    result.queueMaximum(),
                    result.snapshotDelta(),
                    result.gcCount(),
                    result.gcTimeMillis(),
                    result.checksum(),
                    result.corpusDigest(),
                    config.output());
        } catch (Throwable failure) {
            Files.writeString(
                    config.output().resolve("failure.txt"),
                    stackTrace(failure),
                    StandardCharsets.UTF_8);
            if (failure instanceof Exception exception) {
                throw exception;
            }
            if (failure instanceof Error error) {
                throw error;
            }
            throw new RuntimeException(failure);
        }
    }

    static Result run(Config config) throws Exception {
        try (var fixture = V34Phase3Support.createFixture(
                config.documentCount(), config.queueCapacity())) {
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine =
                    fixture.engine();
            Requests requests = Requests.create(engine, config.topK());
            String initialDigest = V34Phase3Support.corpusDigest(
                    engine, config.documentCount());
            long initialChecksum = V34Phase3Support.corpusChecksum(
                    engine, config.documentCount());
            long initialSnapshot = engine.metrics().snapshotVersion();
            long initialSuccessful = engine.metrics().successfulMutations();
            long gcStarted = V34Phase3Support.gcCount();
            long gcTimeStarted = V34Phase3Support.gcTimeMillis();

            long warmupStarted = System.nanoTime();
            long measurementStarted = warmupStarted
                    + TimeUnit.SECONDS.toNanos(config.warmupSeconds());
            long measurementEnded = measurementStarted
                    + TimeUnit.SECONDS.toNanos(config.seconds());
            WindowAccumulator[] windows = new WindowAccumulator[
                    config.seconds() / config.windowSeconds()];
            Arrays.setAll(windows, index -> new WindowAccumulator(index));
            RunCounters counters = new RunCounters(windows);
            AtomicBoolean stop = new AtomicBoolean();
            AtomicReference<Throwable> failure = new AtomicReference<>();
            Set<CompletableFuture<Void>> unresolved =
                    ConcurrentHashMap.newKeySet();
            int taskCount = config.readerCount() + 3;
            CountDownLatch ready = new CountDownLatch(taskCount);
            CountDownLatch start = new CountDownLatch(1);
            ExecutorService workers = Executors.newFixedThreadPool(taskCount);
            ExecutorService burstWorkers = Executors.newFixedThreadPool(
                    config.burstProducers());
            List<Future<Void>> tasks = new ArrayList<>();
            try {
                for (int reader = 0; reader < config.readerCount(); reader++) {
                    int readerId = reader;
                    tasks.add(workers.submit(guarded(
                            failure,
                            stop,
                            () -> readerLoop(
                                    engine,
                                    requests,
                                    config,
                                    readerId,
                                    measurementStarted,
                                    measurementEnded,
                                    counters,
                                    ready,
                                    start,
                                    stop))));
                }
                tasks.add(workers.submit(guarded(
                        failure,
                        stop,
                        () -> steadyWriterLoop(
                                engine,
                                config,
                                measurementStarted,
                                measurementEnded,
                                counters,
                                unresolved,
                                ready,
                                start,
                                stop))));
                tasks.add(workers.submit(guarded(
                        failure,
                        stop,
                        () -> burstLoop(
                                engine,
                                config,
                                measurementStarted,
                                measurementEnded,
                                counters,
                                unresolved,
                                burstWorkers,
                                ready,
                                start,
                                stop))));
                tasks.add(workers.submit(guarded(
                        failure,
                        stop,
                        () -> lifecycleLoop(
                                engine,
                                config,
                                measurementStarted,
                                measurementEnded,
                                counters,
                                unresolved,
                                ready,
                                start,
                                stop))));

                if (!ready.await(10, TimeUnit.SECONDS)) {
                    throw new IllegalStateException(
                            "long-run workers did not reach the start barrier");
                }
                Path samplesPath = config.output().resolve("samples.csv");
                MemoryMXBean memory = ManagementFactory.getMemoryMXBean();
                start.countDown();
                try (PrintWriter samples = new PrintWriter(Files.newBufferedWriter(
                        samplesPath, StandardCharsets.UTF_8))) {
                    samples.println("timestamp,phase,elapsed_s,used_heap_bytes,"
                            + "committed_heap_bytes,max_heap_bytes,read_ops,"
                            + "write_batches,write_mutations,bursts,lifecycle_cycles,"
                            + "expected_failures,unexpected_failures,queue_depth,"
                            + "queue_capacity,snapshot_version,successful_mutations,"
                            + "failed_mutations,pending_index_builds,mutation_journal,"
                            + "gc_count,gc_time_ms");
                    sampleUntilFinished(
                            engine,
                            config,
                            memory,
                            warmupStarted,
                            measurementStarted,
                            measurementEnded,
                            counters,
                            failure,
                            stop,
                            samples);
                }
                stop.set(true);
                for (Future<Void> task : tasks) {
                    task.get(30, TimeUnit.SECONDS);
                }
                burstWorkers.shutdown();
                if (!burstWorkers.awaitTermination(30, TimeUnit.SECONDS)) {
                    throw new IllegalStateException("burst producers did not terminate");
                }
                Throwable workerFailure = failure.get();
                if (workerFailure != null) {
                    throw new IllegalStateException(
                            "long-run worker failed", workerFailure);
                }
                V34Phase3Support.awaitDrain(engine, java.time.Duration.ofSeconds(30));
                return validate(
                        engine,
                        config,
                        requests,
                        counters,
                        unresolved.size(),
                        initialDigest,
                        initialChecksum,
                        initialSnapshot,
                        initialSuccessful,
                        V34Phase3Support.gcCount() - gcStarted,
                        V34Phase3Support.gcTimeMillis() - gcTimeStarted);
            } finally {
                stop.set(true);
                start.countDown();
                workers.shutdownNow();
                burstWorkers.shutdownNow();
                workers.awaitTermination(30, TimeUnit.SECONDS);
                burstWorkers.awaitTermination(30, TimeUnit.SECONDS);
            }
        }
    }

    private static Void readerLoop(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            Requests requests,
            Config config,
            int readerId,
            long measurementStarted,
            long measurementEnded,
            RunCounters counters,
            CountDownLatch ready,
            CountDownLatch start,
            AtomicBoolean stop
    ) throws Exception {
        int cursor = readerId;
        ready.countDown();
        start.await();
        while (!stop.get() && System.nanoTime() < measurementEnded) {
            WorkloadKind kind = WorkloadKind.values()[Math.floorMod(
                    cursor++, WorkloadKind.values().length)];
            long started = System.nanoTime();
            long checksum = executeRead(engine, requests, kind);
            long completed = System.nanoTime();
            if (checksum == 0L) {
                throw new IllegalStateException("zero read checksum for " + kind);
            }
            counters.recordRead(
                    kind,
                    completed - started,
                    checksum,
                    completed,
                    measurementStarted,
                    config.windowSeconds(),
                    measurementEnded);
        }
        return null;
    }

    private static long executeRead(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            Requests requests,
            WorkloadKind kind
    ) {
        return switch (kind) {
            case STRUCTURED -> {
                List<V3ProductionBenchmarkSupport.Document> documents = engine.search(
                        Query.eq(V3ProductionBenchmarkSupport.CATEGORY, "travel"));
                if (documents.size() != requests.structuredCount()) {
                    throw new IllegalStateException("structured truth changed");
                }
                long checksum = documents.size();
                for (V3ProductionBenchmarkSupport.Document document : documents) {
                    checksum = 31L * checksum + document.id();
                }
                yield checksum;
            }
            case RANKED_TEXT -> {
                var hits = engine.search(requests.text()).hits();
                requireRanked(hits.size(), requests.textHits());
                yield V34Phase3Support.hitChecksum(hits);
            }
            case RANKED_PHRASE -> {
                var hits = engine.search(requests.phrase()).hits();
                requireRanked(hits.size(), requests.phraseHits());
                yield V34Phase3Support.hitChecksum(hits);
            }
            case HIGHLIGHT -> {
                var result = engine.search(requests.highlight());
                if (result.hits().size() != requests.textHits()) {
                    throw new IllegalStateException("highlight truth changed");
                }
                long checksum = result.hits().size();
                for (var hit : result.hits()) {
                    if (hit.highlights().isEmpty()) {
                        throw new IllegalStateException("highlight evidence is empty");
                    }
                    checksum = 31L * checksum + hit.hit().document().id();
                    checksum = 31L * checksum
                            + Double.doubleToRawLongBits(hit.hit().score());
                    checksum = 31L * checksum
                            + hit.highlights().getFirst().fragments()
                            .getFirst().startOffset();
                }
                yield checksum;
            }
            case PAGE_EXACT -> {
                var page = engine.search(requests.page());
                if (page.hits().size() != requests.textHits()
                        || page.totalHits().orElseThrow()
                        != requests.exactTextTotal()) {
                    throw new IllegalStateException("page/exact-total truth changed");
                }
                yield 31L * V34Phase3Support.hitChecksum(page.hits())
                        + page.totalHits().orElseThrow();
            }
            case EXPLAIN -> {
                var explanation = engine.explain(
                        requests.text(), requests.explainId()).orElseThrow();
                if (!explanation.matched()
                        || Double.doubleToRawLongBits(explanation.score())
                        != requests.explainScoreBits()) {
                    throw new IllegalStateException("Explain truth changed");
                }
                yield 31L * requests.explainId()
                        + Double.doubleToRawLongBits(explanation.score());
            }
        };
    }

    private static void requireRanked(int actual, int expected) {
        if (actual != expected || actual <= 0) {
            throw new IllegalStateException(
                    "ranked truth changed: expected=" + expected + ",actual=" + actual);
        }
    }

    private static Void steadyWriterLoop(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            Config config,
            long measurementStarted,
            long measurementEnded,
            RunCounters counters,
            Set<CompletableFuture<Void>> unresolved,
            CountDownLatch ready,
            CountDownLatch start,
            AtomicBoolean stop
    ) throws Exception {
        long cursor = 0L;
        boolean injected = false;
        long injectAt = measurementStarted
                + (measurementEnded - measurementStarted) / 2L;
        ready.countDown();
        start.await();
        if (!awaitNano(measurementStarted, stop)) {
            return null;
        }
        while (!stop.get() && System.nanoTime() < measurementEnded) {
            long now = System.nanoTime();
            if (!injected && now >= injectAt) {
                injectExpectedFailure(
                        engine,
                        config,
                        counters,
                        measurementStarted,
                        measurementEnded);
                injected = true;
            }
            long id = Math.floorMod(cursor++, config.documentCount());
            submitAndRecord(
                    engine,
                    List.of(V34Phase3Support.initialDocument(id)),
                    counters,
                    unresolved,
                    measurementStarted,
                    measurementEnded,
                    config.windowSeconds());
            sleepBounded(config.steadyMillis(), stop);
        }
        if (!injected) {
            throw new IllegalStateException("expected failure injection did not run");
        }
        return null;
    }

    private static Void burstLoop(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            Config config,
            long measurementStarted,
            long measurementEnded,
            RunCounters counters,
            Set<CompletableFuture<Void>> unresolved,
            ExecutorService burstWorkers,
            CountDownLatch ready,
            CountDownLatch start,
            AtomicBoolean stop
    ) throws Exception {
        ready.countDown();
        start.await();
        long nextBurst = measurementStarted;
        int sequence = 0;
        while (!stop.get() && nextBurst < measurementEnded) {
            if (!awaitNano(nextBurst, stop)) {
                break;
            }
            int burstSequence = sequence++;
            List<Future<?>> producerTasks = new ArrayList<>();
            for (int producer = 0; producer < config.burstProducers(); producer++) {
                int producerId = producer;
                producerTasks.add(burstWorkers.submit(() -> {
                    List<V3ProductionBenchmarkSupport.Document> batch =
                            new ArrayList<>(config.burstBatchSize());
                    long base = ((long) burstSequence * config.burstProducers()
                            + producerId) * config.burstBatchSize();
                    for (int item = 0; item < config.burstBatchSize(); item++) {
                        long id = Math.floorMod(base + item, config.documentCount());
                        batch.add(V34Phase3Support.initialDocument(id));
                    }
                    submitAndRecord(
                            engine,
                            batch,
                            counters,
                            unresolved,
                            measurementStarted,
                            measurementEnded,
                            config.windowSeconds());
                }));
            }
            for (Future<?> producer : producerTasks) {
                producer.get(30, TimeUnit.SECONDS);
            }
            counters.bursts.increment();
            nextBurst += TimeUnit.SECONDS.toNanos(config.burstEverySeconds());
        }
        return null;
    }

    private static Void lifecycleLoop(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            Config config,
            long measurementStarted,
            long measurementEnded,
            RunCounters counters,
            Set<CompletableFuture<Void>> unresolved,
            CountDownLatch ready,
            CountDownLatch start,
            AtomicBoolean stop
    ) throws Exception {
        ready.countDown();
        start.await();
        long nextCycle = measurementStarted;
        while (!stop.get() && nextCycle < measurementEnded) {
            if (!awaitNano(nextCycle, stop)) {
                break;
            }
            awaitLifecycle(unresolved, engine.createIndex(IndexDefinition.range(
                    V3ProductionBenchmarkSupport.POPULARITY)));
            awaitLifecycle(unresolved, engine.createIndex(IndexDefinition.text(
                    V3ProductionBenchmarkSupport.TITLE_TEXT)));
            awaitLifecycle(unresolved, engine.dropIndex(
                    V3ProductionBenchmarkSupport.POPULARITY.name()));
            awaitLifecycle(unresolved, engine.dropIndex(
                    V3ProductionBenchmarkSupport.TITLE.name()));
            counters.lifecycleCycles.increment();
            nextCycle += TimeUnit.SECONDS.toNanos(config.lifecycleEverySeconds());
        }
        return null;
    }

    private static void awaitLifecycle(
            Set<CompletableFuture<Void>> unresolved,
            CompletableFuture<Void> future
    ) {
        unresolved.add(future);
        try {
            future.join();
        } finally {
            unresolved.remove(future);
        }
    }

    private static void submitAndRecord(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            List<V3ProductionBenchmarkSupport.Document> documents,
            RunCounters counters,
            Set<CompletableFuture<Void>> unresolved,
            long measurementStarted,
            long measurementEnded,
            int windowSeconds
    ) {
        long started = System.nanoTime();
        CompletableFuture<Void> future = engine.updateAll(documents);
        unresolved.add(future);
        try {
            future.join();
            long completed = System.nanoTime();
            counters.recordWrite(
                    documents.size(),
                    completed - started,
                    completed,
                    measurementStarted,
                    windowSeconds,
                    measurementEnded);
        } finally {
            unresolved.remove(future);
        }
    }

    private static void injectExpectedFailure(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            Config config,
            RunCounters counters,
            long measurementStarted,
            long measurementEnded
    ) {
        long missingId = config.documentCount() + 1L;
        try {
            engine.update(V34Phase3Support.initialDocument(missingId)).join();
            throw new IllegalStateException(
                    "missing-document failure was reported as success");
        } catch (RuntimeException failed) {
            Throwable cause = V34Phase3Support.rootCause(failed);
            if (!(cause instanceof DocumentNotFoundException)) {
                throw new IllegalStateException(
                        "wrong injected failure: " + cause, cause);
            }
            long completed = System.nanoTime();
            counters.recordExpectedFailure(
                    completed,
                    measurementStarted,
                    config.windowSeconds(),
                    measurementEnded);
            if (engine.get(missingId) != null
                    || engine.metrics().documentCount() != config.documentCount()) {
                throw new IllegalStateException("injected failure changed engine state");
            }
        }
    }

    private static void sampleUntilFinished(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            Config config,
            MemoryMXBean memory,
            long warmupStarted,
            long measurementStarted,
            long measurementEnded,
            RunCounters counters,
            AtomicReference<Throwable> failure,
            AtomicBoolean stop,
            PrintWriter output
    ) throws Exception {
        long nextSample = warmupStarted;
        while (System.nanoTime() < measurementEnded && failure.get() == null) {
            long now = System.nanoTime();
            if (now < nextSample) {
                TimeUnit.NANOSECONDS.sleep(Math.min(
                        nextSample - now, TimeUnit.MILLISECONDS.toNanos(50)));
                continue;
            }
            writeSample(
                    engine,
                    config,
                    memory,
                    warmupStarted,
                    measurementStarted,
                    measurementEnded,
                    counters,
                    output,
                    now);
            output.flush();
            nextSample += TimeUnit.MILLISECONDS.toNanos(config.sampleMillis());
        }
        stop.set(true);
        writeSample(
                engine,
                config,
                memory,
                warmupStarted,
                measurementStarted,
                measurementEnded,
                counters,
                output,
                System.nanoTime());
        output.flush();
        Throwable workerFailure = failure.get();
        if (workerFailure != null) {
            throw new IllegalStateException("worker failed during sampling",
                    workerFailure);
        }
    }

    private static void writeSample(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            Config config,
            MemoryMXBean memory,
            long warmupStarted,
            long measurementStarted,
            long measurementEnded,
            RunCounters counters,
            PrintWriter output,
            long now
    ) {
        var metrics = engine.metrics();
        var heap = memory.getHeapMemoryUsage();
        if (metrics.writerQueueDepth() < 0
                || metrics.writerQueueDepth() > metrics.writerQueueCapacity()
                || metrics.writerQueueCapacity() != config.queueCapacity()) {
            throw new IllegalStateException("invalid queue telemetry sample");
        }
        String phase = now < measurementStarted ? "warmup" : "measurement";
        double elapsed = (now - warmupStarted) / 1_000_000_000.0;
        output.printf(Locale.ROOT,
                "%s,%s,%.6f,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d%n",
                Instant.now(),
                phase,
                elapsed,
                heap.getUsed(),
                heap.getCommitted(),
                heap.getMax(),
                counters.readOperations.sum(),
                counters.writeBatches.sum(),
                counters.writeMutations.sum(),
                counters.bursts.sum(),
                counters.lifecycleCycles.sum(),
                counters.expectedFailures.sum(),
                counters.unexpectedFailures.sum(),
                metrics.writerQueueDepth(),
                metrics.writerQueueCapacity(),
                metrics.snapshotVersion(),
                metrics.successfulMutations(),
                metrics.failedMutations(),
                metrics.pendingIndexBuildCount(),
                metrics.mutationJournalLength(),
                V34Phase3Support.gcCount(),
                V34Phase3Support.gcTimeMillis());
        counters.queueMaximum.accumulateAndGet(
                metrics.writerQueueDepth(), Math::max);
        int window = windowIndex(
                now, measurementStarted, config.windowSeconds(), measurementEnded);
        if (window >= 0) {
            counters.windows[window].sample(
                    heap.getUsed(),
                    metrics.writerQueueDepth(),
                    metrics.writerQueueCapacity(),
                    metrics.snapshotVersion(),
                    V34Phase3Support.gcCount(),
                    V34Phase3Support.gcTimeMillis());
        }
    }

    private static Result validate(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            Config config,
            Requests requests,
            RunCounters counters,
            int unresolvedFutures,
            String initialDigest,
            long initialChecksum,
            long initialSnapshot,
            long initialSuccessful,
            long gcCount,
            long gcTimeMillis
    ) throws Exception {
        List<WindowResult> windows = Arrays.stream(counters.windows)
                .map(WindowAccumulator::result).toList();
        long expectedSamples = Math.max(1L,
                TimeUnit.SECONDS.toMillis(config.windowSeconds())
                        / config.sampleMillis());
        long minimumSamples = Math.max(1L, (long) Math.floor(
                expectedSamples * 0.80));
        if (windows.stream().anyMatch(window ->
                window.sampleCount() < minimumSamples)) {
            throw new IllegalStateException(
                    "long-run sampling coverage is incomplete: minimum="
                            + minimumSamples);
        }
        CalibrationDecision decision = evaluateWindows(windows);
        if (!decision.passed()) {
            throw new IllegalStateException(
                    "long-run window gate failed: " + decision.reasons());
        }
        var metrics = engine.metrics();
        long writeMutations = counters.writeMutations.sum();
        if (unresolvedFutures != 0
                || metrics.writerQueueDepth() != 0
                || metrics.pendingIndexBuildCount() != 0
                || metrics.mutationJournalLength() != 0
                || metrics.registeredIndexCount() != 2
                || counters.expectedFailures.sum() != 1L
                || counters.unexpectedFailures.sum() != 0L
                || counters.bursts.sum() <= 0L
                || counters.lifecycleCycles.sum() <= 0L
                || metrics.successfulMutations() - initialSuccessful
                != writeMutations) {
            throw new IllegalStateException("long-run completion gate failed");
        }
        String finalDigest = V34Phase3Support.corpusDigest(
                engine, config.documentCount());
        long finalChecksum = V34Phase3Support.corpusChecksum(
                engine, config.documentCount());
        if (!initialDigest.equals(finalDigest)
                || initialChecksum != finalChecksum) {
            throw new IllegalStateException("stable long-run corpus changed");
        }
        for (WorkloadKind kind : WorkloadKind.values()) {
            executeRead(engine, requests, kind);
        }
        long snapshotDelta = metrics.snapshotVersion() - initialSnapshot;
        long checksum = 31L * finalChecksum + counters.checksum.sum();
        checksum = 31L * checksum + snapshotDelta;
        if (snapshotDelta <= 0L || checksum == 0L) {
            throw new IllegalStateException("long-run identity is invalid");
        }
        writeWindows(config, windows, decision);
        return new Result(
                windows,
                counters.readOperations.sum(),
                counters.writeBatches.sum(),
                writeMutations,
                counters.bursts.sum(),
                counters.lifecycleCycles.sum(),
                counters.expectedFailures.sum(),
                counters.unexpectedFailures.sum(),
                unresolvedFutures,
                counters.queueMaximum.get(),
                snapshotDelta,
                gcCount,
                gcTimeMillis,
                checksum,
                finalDigest,
                decision);
    }

    static CalibrationDecision evaluateWindows(List<WindowResult> windows) {
        List<String> reasons = new ArrayList<>();
        long previousSnapshot = -1L;
        for (WindowResult window : windows) {
            if (window.sampleCount() <= 0L) {
                reasons.add("window-" + window.index() + "-has-no-samples");
            }
            if (window.readOperations() <= 0L
                    || window.writeBatches() <= 0L
                    || window.writeMutations() <= 0L
                    || window.publications() <= 0L) {
                reasons.add("window-" + window.index() + "-has-no-progress");
            }
            if (window.unexpectedFailures() != 0L) {
                reasons.add("window-" + window.index() + "-has-errors");
            }
            if (window.queueMaximum() < 0
                    || window.queueMaximum() > window.queueCapacity()) {
                reasons.add("window-" + window.index() + "-queue-invalid");
            }
            if (window.snapshotMaximum() < previousSnapshot
                    || window.snapshotMaximum() < window.snapshotMinimum()) {
                reasons.add("window-" + window.index() + "-snapshot-invalid");
            }
            previousSnapshot = window.snapshotMaximum();
            for (WorkloadKind kind : WorkloadKind.values()) {
                if (window.kindOperations().getOrDefault(kind, 0L) <= 0L) {
                    reasons.add("window-" + window.index()
                            + "-missing-" + kind.id());
                }
            }
        }
        long[] readRates = windows.stream()
                .mapToLong(WindowResult::readOperations).sorted().toArray();
        long[] p99 = windows.stream()
                .mapToLong(WindowResult::readP99Nanos).sorted().toArray();
        long medianRead = median(readRates);
        long medianP99 = median(p99);
        return new CalibrationDecision(
                reasons.isEmpty(),
                List.copyOf(reasons),
                medianRead,
                Math.max(1L, Math.round(medianRead * 0.75)),
                medianP99,
                Math.max(1L, Math.round(medianP99 * 2.0)));
    }

    private static void writeWindows(
            Config config,
            List<WindowResult> windows,
            CalibrationDecision decision
    ) throws Exception {
        try (PrintWriter output = new PrintWriter(Files.newBufferedWriter(
                config.output().resolve("windows.csv"), StandardCharsets.UTF_8))) {
            output.println("window,read_ops,write_batches,write_mutations,"
                    + "publications,expected_failures,unexpected_failures,"
                    + "read_p50_ns,read_p95_ns,read_p99_ns,write_p50_ns,"
                    + "write_p95_ns,write_p99_ns,queue_max,queue_capacity,"
                    + "heap_max_bytes,snapshot_min,snapshot_max,gc_count_delta,"
                    + "gc_time_ms_delta,samples,structured_ops,ranked_text_ops,"
                    + "ranked_phrase_ops,highlight_ops,page_exact_ops,explain_ops");
            for (WindowResult window : windows) {
                output.printf(Locale.ROOT,
                        "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d%n",
                        window.index(),
                        window.readOperations(),
                        window.writeBatches(),
                        window.writeMutations(),
                        window.publications(),
                        window.expectedFailures(),
                        window.unexpectedFailures(),
                        window.readP50Nanos(),
                        window.readP95Nanos(),
                        window.readP99Nanos(),
                        window.writeP50Nanos(),
                        window.writeP95Nanos(),
                        window.writeP99Nanos(),
                        window.queueMaximum(),
                        window.queueCapacity(),
                        window.heapMaximumBytes(),
                        window.snapshotMinimum(),
                        window.snapshotMaximum(),
                        window.gcCountDelta(),
                        window.gcTimeMillisDelta(),
                        window.sampleCount(),
                        window.kindOperations().get(WorkloadKind.STRUCTURED),
                        window.kindOperations().get(WorkloadKind.RANKED_TEXT),
                        window.kindOperations().get(WorkloadKind.RANKED_PHRASE),
                        window.kindOperations().get(WorkloadKind.HIGHLIGHT),
                        window.kindOperations().get(WorkloadKind.PAGE_EXACT),
                        window.kindOperations().get(WorkloadKind.EXPLAIN));
            }
        }
    }

    private static void writeConfig(Config config) throws Exception {
        Properties values = new Properties();
        values.setProperty("schema", config.runKind().equals("final-v34-cloud")
                ? "v34-final-long-run-v1"
                : "v34-local-long-run-v1");
        values.setProperty("run_kind", config.runKind());
        values.setProperty("source_commit", config.sourceCommit());
        values.setProperty("tree_state", config.treeState());
        values.setProperty("version", "3.4.0");
        values.setProperty("documents", Integer.toString(config.documentCount()));
        values.setProperty("readers", Integer.toString(config.readerCount()));
        values.setProperty("seconds", Integer.toString(config.seconds()));
        values.setProperty("warmup_seconds",
                Integer.toString(config.warmupSeconds()));
        values.setProperty("window_seconds",
                Integer.toString(config.windowSeconds()));
        values.setProperty("sample_millis", Integer.toString(config.sampleMillis()));
        values.setProperty("top_k", Integer.toString(config.topK()));
        values.setProperty("steady_millis", Integer.toString(config.steadyMillis()));
        values.setProperty("burst_every_seconds",
                Integer.toString(config.burstEverySeconds()));
        values.setProperty("burst_producers",
                Integer.toString(config.burstProducers()));
        values.setProperty("burst_batch_size",
                Integer.toString(config.burstBatchSize()));
        values.setProperty("lifecycle_every_seconds",
                Integer.toString(config.lifecycleEverySeconds()));
        values.setProperty("queue_capacity",
                Integer.toString(config.queueCapacity()));
        values.setProperty("java_version", System.getProperty("java.version"));
        values.setProperty("java_vendor", System.getProperty("java.vendor"));
        values.setProperty("vm_name", System.getProperty("java.vm.name"));
        values.setProperty("jvm_arguments", String.join("|",
                ManagementFactory.getRuntimeMXBean().getInputArguments()));
        values.setProperty("os_name", System.getProperty("os.name"));
        values.setProperty("os_version", System.getProperty("os.version"));
        values.setProperty("os_arch", System.getProperty("os.arch"));
        values.setProperty("processors", Integer.toString(
                Runtime.getRuntime().availableProcessors()));
        try (var output = Files.newOutputStream(
                config.output().resolve("config.properties"))) {
            values.store(output, "V3.4 local long-run calibration identity");
        }
    }

    private static void writeSummary(Config config, Result result) throws Exception {
        Properties values = new Properties();
        values.setProperty("status", "SUCCESS");
        values.setProperty("read_operations",
                Long.toString(result.readOperations()));
        values.setProperty("write_batches", Long.toString(result.writeBatches()));
        values.setProperty("write_mutations",
                Long.toString(result.writeMutations()));
        values.setProperty("bursts", Long.toString(result.bursts()));
        values.setProperty("lifecycle_cycles",
                Long.toString(result.lifecycleCycles()));
        values.setProperty("expected_failures",
                Long.toString(result.expectedFailures()));
        values.setProperty("unexpected_failures",
                Long.toString(result.unexpectedFailures()));
        values.setProperty("unresolved_futures",
                Integer.toString(result.unresolvedFutures()));
        values.setProperty("queue_maximum",
                Integer.toString(result.queueMaximum()));
        values.setProperty("snapshot_delta", Long.toString(result.snapshotDelta()));
        values.setProperty("gc_count", Long.toString(result.gcCount()));
        values.setProperty("gc_time_millis", Long.toString(result.gcTimeMillis()));
        values.setProperty("checksum", Long.toString(result.checksum()));
        values.setProperty("corpus_digest", result.corpusDigest());
        values.setProperty("review_read_window_median",
                Long.toString(result.decision().medianReadOperations()));
        values.setProperty("review_read_window_lower",
                Long.toString(result.decision().readOperationsLowerReviewBand()));
        values.setProperty("review_read_p99_median_ns",
                Long.toString(result.decision().medianReadP99Nanos()));
        values.setProperty("review_read_p99_upper_ns",
                Long.toString(result.decision().readP99UpperReviewBandNanos()));
        values.setProperty("review_bands_are_release_gates", "false");
        try (var output = Files.newOutputStream(
                config.output().resolve("summary.properties"))) {
            values.store(output, "V3.4 local long-run calibration result");
        }
    }

    private static void writeManifest(Path output) throws Exception {
        List<String> names = List.of(
                "config.properties", "samples.csv", "windows.csv",
                "summary.properties");
        try (PrintWriter manifest = new PrintWriter(Files.newBufferedWriter(
                output.resolve("manifest.sha256"), StandardCharsets.UTF_8))) {
            for (String name : names) {
                Path file = output.resolve(name);
                manifest.println(sha256(Files.readAllBytes(file)) + "  " + name);
            }
        }
    }

    private static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    private static <T> java.util.concurrent.Callable<T> guarded(
            AtomicReference<Throwable> failure,
            AtomicBoolean stop,
            java.util.concurrent.Callable<T> action
    ) {
        return () -> {
            try {
                return action.call();
            } catch (Throwable workerFailure) {
                failure.compareAndSet(null, workerFailure);
                stop.set(true);
                if (workerFailure instanceof Exception exception) {
                    throw exception;
                }
                if (workerFailure instanceof Error error) {
                    throw error;
                }
                throw new RuntimeException(workerFailure);
            }
        };
    }

    private static boolean awaitNano(long target, AtomicBoolean stop)
            throws InterruptedException {
        while (!stop.get()) {
            long remaining = target - System.nanoTime();
            if (remaining <= 0L) {
                return true;
            }
            TimeUnit.NANOSECONDS.sleep(Math.min(
                    remaining, TimeUnit.MILLISECONDS.toNanos(50)));
        }
        return false;
    }

    private static void sleepBounded(int millis, AtomicBoolean stop)
            throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(millis);
        awaitNano(deadline, stop);
    }

    private static int windowIndex(
            long completed,
            long measurementStarted,
            int windowSeconds,
            long measurementEnded
    ) {
        if (completed < measurementStarted || completed >= measurementEnded) {
            return -1;
        }
        return (int) ((completed - measurementStarted)
                / TimeUnit.SECONDS.toNanos(windowSeconds));
    }

    private static long median(long[] sorted) {
        return sorted.length == 0 ? 0L : sorted[(sorted.length - 1) / 2];
    }

    private static String stackTrace(Throwable failure) {
        StringWriter output = new StringWriter();
        failure.printStackTrace(new PrintWriter(output));
        return output.toString();
    }

    enum WorkloadKind {
        STRUCTURED("structured"),
        RANKED_TEXT("ranked-text"),
        RANKED_PHRASE("ranked-phrase"),
        HIGHLIGHT("highlight"),
        PAGE_EXACT("page-exact"),
        EXPLAIN("explain");

        private final String id;

        WorkloadKind(String id) {
            this.id = id;
        }

        String id() {
            return id;
        }
    }

    private record Requests(
            SearchRequest<V3ProductionBenchmarkSupport.Document> text,
            SearchRequest<V3ProductionBenchmarkSupport.Document> phrase,
            HighlightedSearchRequest<V3ProductionBenchmarkSupport.Document> highlight,
            SearchPageRequest<V3ProductionBenchmarkSupport.Document> page,
            int structuredCount,
            int textHits,
            int phraseHits,
            long exactTextTotal,
            long explainId,
            long explainScoreBits
    ) {
        static Requests create(
                SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
                int topK
        ) {
            SearchRequest<V3ProductionBenchmarkSupport.Document> text =
                    SearchRequest.<V3ProductionBenchmarkSupport.Document>builder()
                            .query(SearchQueries.text(
                                    V3ProductionBenchmarkSupport.BODY_TEXT, "search"))
                            .limit(topK)
                            .build();
            SearchRequest<V3ProductionBenchmarkSupport.Document> phrase =
                    SearchRequest.<V3ProductionBenchmarkSupport.Document>builder()
                            .query(SearchQueries.phrase(
                                    V3ProductionBenchmarkSupport.BODY_TEXT,
                                    "search engine"))
                            .limit(topK)
                            .build();
            var highlight = HighlightedSearchRequest
                    .<V3ProductionBenchmarkSupport.Document>builder(text)
                    .field(V3ProductionBenchmarkSupport.BODY_TEXT)
                    .contextCharacters(20)
                    .maxFragmentsPerField(2)
                    .build();
            var page = SearchPageRequest
                    .<V3ProductionBenchmarkSupport.Document>builder(text)
                    .totalHits(TotalHitsMode.EXACT)
                    .build();
            int structured = engine.search(Query.eq(
                    V3ProductionBenchmarkSupport.CATEGORY, "travel")).size();
            var textResult = engine.search(text);
            var phraseResult = engine.search(phrase);
            var pageResult = engine.search(page);
            if (structured <= 0 || textResult.hits().isEmpty()
                    || phraseResult.hits().isEmpty()
                    || pageResult.hits().size() != textResult.hits().size()
                    || pageResult.totalHits().orElseThrow() <= 0) {
                throw new IllegalStateException("invalid long-run control requests");
            }
            var explainHit = textResult.hits().getFirst();
            var explanation = engine.explain(
                    text, explainHit.document().id()).orElseThrow();
            if (!explanation.matched()
                    || Double.doubleToRawLongBits(explanation.score())
                    != Double.doubleToRawLongBits(explainHit.score())) {
                throw new IllegalStateException("invalid Explain control");
            }
            return new Requests(
                    text,
                    phrase,
                    highlight,
                    page,
                    structured,
                    textResult.hits().size(),
                    phraseResult.hits().size(),
                    pageResult.totalHits().orElseThrow(),
                    explainHit.document().id(),
                    Double.doubleToRawLongBits(explainHit.score()));
        }
    }

    private static final class RunCounters {
        private final WindowAccumulator[] windows;
        private final LongAdder readOperations = new LongAdder();
        private final LongAdder writeBatches = new LongAdder();
        private final LongAdder writeMutations = new LongAdder();
        private final LongAdder bursts = new LongAdder();
        private final LongAdder lifecycleCycles = new LongAdder();
        private final LongAdder expectedFailures = new LongAdder();
        private final LongAdder unexpectedFailures = new LongAdder();
        private final LongAdder checksum = new LongAdder();
        private final AtomicInteger queueMaximum = new AtomicInteger();

        private RunCounters(WindowAccumulator[] windows) {
            this.windows = windows;
        }

        private void recordRead(
                WorkloadKind kind,
                long latency,
                long value,
                long completed,
                long measurementStarted,
                int windowSeconds,
                long measurementEnded
        ) {
            int index = windowIndex(
                    completed, measurementStarted, windowSeconds, measurementEnded);
            if (index < 0) {
                return;
            }
            windows[index].read(kind, latency);
            readOperations.increment();
            checksum.add(value);
        }

        private void recordWrite(
                int mutations,
                long latency,
                long completed,
                long measurementStarted,
                int windowSeconds,
                long measurementEnded
        ) {
            writeBatches.increment();
            writeMutations.add(mutations);
            int index = windowIndex(
                    completed, measurementStarted, windowSeconds, measurementEnded);
            if (index < 0) {
                return;
            }
            windows[index].write(mutations, latency);
        }

        private void recordExpectedFailure(
                long completed,
                long measurementStarted,
                int windowSeconds,
                long measurementEnded
        ) {
            int index = windowIndex(
                    completed, measurementStarted, windowSeconds, measurementEnded);
            if (index < 0) {
                throw new IllegalStateException(
                        "expected failure occurred outside measurement");
            }
            windows[index].expectedFailures.increment();
            expectedFailures.increment();
        }
    }

    private static final class WindowAccumulator {
        private final int index;
        private final LongAdder readOperations = new LongAdder();
        private final LongAdder writeBatches = new LongAdder();
        private final LongAdder writeMutations = new LongAdder();
        private final LongAdder publications = new LongAdder();
        private final LongAdder expectedFailures = new LongAdder();
        private final LongAdder unexpectedFailures = new LongAdder();
        private final LongAdder sampleCount = new LongAdder();
        private final EnumMap<WorkloadKind, LongAdder> kinds =
                new EnumMap<>(WorkloadKind.class);
        private final V3ProductionSoak.LatencyReservoir readLatency;
        private final V3ProductionSoak.LatencyReservoir writeLatency;
        private final AtomicInteger queueMaximum = new AtomicInteger();
        private final AtomicLong heapMaximum = new AtomicLong();
        private final AtomicLong snapshotMinimum = new AtomicLong(Long.MAX_VALUE);
        private final AtomicLong snapshotMaximum = new AtomicLong();
        private final AtomicLong gcCountMinimum = new AtomicLong(Long.MAX_VALUE);
        private final AtomicLong gcCountMaximum = new AtomicLong();
        private final AtomicLong gcTimeMinimum = new AtomicLong(Long.MAX_VALUE);
        private final AtomicLong gcTimeMaximum = new AtomicLong();
        private final AtomicInteger queueCapacity = new AtomicInteger();

        private WindowAccumulator(int index) {
            this.index = index;
            readLatency = new V3ProductionSoak.LatencyReservoir(
                    RESERVOIR_SIZE, 34_100L + index);
            writeLatency = new V3ProductionSoak.LatencyReservoir(
                    RESERVOIR_SIZE, 34_200L + index);
            for (WorkloadKind kind : WorkloadKind.values()) {
                kinds.put(kind, new LongAdder());
            }
        }

        private void read(WorkloadKind kind, long latency) {
            readOperations.increment();
            kinds.get(kind).increment();
            synchronized (readLatency) {
                readLatency.record(latency);
            }
        }

        private void write(int mutations, long latency) {
            writeBatches.increment();
            writeMutations.add(mutations);
            publications.increment();
            synchronized (writeLatency) {
                writeLatency.record(latency);
            }
        }

        private void sample(
                long heapUsed,
                int queueDepth,
                int observedQueueCapacity,
                long snapshot,
                long gcCount,
                long gcTime
        ) {
            sampleCount.increment();
            heapMaximum.accumulateAndGet(heapUsed, Math::max);
            queueMaximum.accumulateAndGet(queueDepth, Math::max);
            int previousCapacity = queueCapacity.get();
            if (previousCapacity != 0 && previousCapacity != observedQueueCapacity) {
                throw new IllegalStateException(
                        "queue capacity changed within a measurement window");
            }
            queueCapacity.compareAndSet(0, observedQueueCapacity);
            snapshotMinimum.accumulateAndGet(snapshot, Math::min);
            snapshotMaximum.accumulateAndGet(snapshot, Math::max);
            gcCountMinimum.accumulateAndGet(gcCount, Math::min);
            gcCountMaximum.accumulateAndGet(gcCount, Math::max);
            gcTimeMinimum.accumulateAndGet(gcTime, Math::min);
            gcTimeMaximum.accumulateAndGet(gcTime, Math::max);
        }

        private WindowResult result() {
            Map<WorkloadKind, Long> kindValues = new EnumMap<>(WorkloadKind.class);
            kinds.forEach((kind, count) -> kindValues.put(kind, count.sum()));
            List<Long> reads;
            List<Long> writes;
            synchronized (readLatency) {
                reads = Arrays.stream(readLatency.samples()).boxed().toList();
            }
            synchronized (writeLatency) {
                writes = Arrays.stream(writeLatency.samples()).boxed().toList();
            }
            long samples = sampleCount.sum();
            return new WindowResult(
                    index,
                    readOperations.sum(),
                    writeBatches.sum(),
                    writeMutations.sum(),
                    publications.sum(),
                    expectedFailures.sum(),
                    unexpectedFailures.sum(),
                    V34Phase3Support.percentile(reads, 0.50),
                    V34Phase3Support.percentile(reads, 0.95),
                    V34Phase3Support.percentile(reads, 0.99),
                    V34Phase3Support.percentile(writes, 0.50),
                    V34Phase3Support.percentile(writes, 0.95),
                    V34Phase3Support.percentile(writes, 0.99),
                    queueMaximum.get(),
                    queueCapacity.get(),
                    heapMaximum.get(),
                    samples == 0 ? 0L : snapshotMinimum.get(),
                    snapshotMaximum.get(),
                    samples == 0 ? 0L : gcCountMaximum.get() - gcCountMinimum.get(),
                    samples == 0 ? 0L : gcTimeMaximum.get() - gcTimeMinimum.get(),
                    samples,
                    Map.copyOf(kindValues));
        }
    }

    record WindowResult(
            int index,
            long readOperations,
            long writeBatches,
            long writeMutations,
            long publications,
            long expectedFailures,
            long unexpectedFailures,
            long readP50Nanos,
            long readP95Nanos,
            long readP99Nanos,
            long writeP50Nanos,
            long writeP95Nanos,
            long writeP99Nanos,
            int queueMaximum,
            int queueCapacity,
            long heapMaximumBytes,
            long snapshotMinimum,
            long snapshotMaximum,
            long gcCountDelta,
            long gcTimeMillisDelta,
            long sampleCount,
            Map<WorkloadKind, Long> kindOperations
    ) {
        WindowResult {
            kindOperations = Map.copyOf(kindOperations);
        }
    }

    record CalibrationDecision(
            boolean passed,
            List<String> reasons,
            long medianReadOperations,
            long readOperationsLowerReviewBand,
            long medianReadP99Nanos,
            long readP99UpperReviewBandNanos
    ) {
        CalibrationDecision {
            reasons = List.copyOf(reasons);
        }
    }

    record Result(
            List<WindowResult> windows,
            long readOperations,
            long writeBatches,
            long writeMutations,
            long bursts,
            long lifecycleCycles,
            long expectedFailures,
            long unexpectedFailures,
            int unresolvedFutures,
            int queueMaximum,
            long snapshotDelta,
            long gcCount,
            long gcTimeMillis,
            long checksum,
            String corpusDigest,
            CalibrationDecision decision
    ) {
        Result {
            windows = List.copyOf(windows);
        }
    }

    record Config(
            Path output,
            int documentCount,
            int readerCount,
            int seconds,
            int warmupSeconds,
            int windowSeconds,
            int sampleMillis,
            int topK,
            int steadyMillis,
            int burstEverySeconds,
            int burstProducers,
            int burstBatchSize,
            int lifecycleEverySeconds,
            int queueCapacity,
            String sourceCommit,
            String treeState,
            String runKind
    ) {
        Config {
            if (!runKind.equals("local-calibration")
                    && !runKind.equals("final-v34-cloud")) {
                throw new IllegalArgumentException("unsupported long-run kind");
            }
            int maximumSeconds = runKind.equals("final-v34-cloud")
                    ? MAX_FINAL_CLOUD_SECONDS
                    : MAX_SECONDS;
            if (documentCount < 100 || documentCount > MAX_DOCUMENTS
                    || readerCount <= 0 || readerCount > 64
                    || seconds < 2 || seconds > maximumSeconds
                    || warmupSeconds < 0 || warmupSeconds > 300
                    || windowSeconds <= 0 || seconds % windowSeconds != 0
                    || sampleMillis <= 0
                    || sampleMillis > TimeUnit.SECONDS.toMillis(windowSeconds)
                    || topK <= 0 || topK > documentCount
                    || steadyMillis <= 0 || steadyMillis > 60_000
                    || burstEverySeconds <= 0
                    || burstEverySeconds > seconds
                    || lifecycleEverySeconds <= 0
                    || lifecycleEverySeconds > seconds
                    || burstProducers <= 0 || burstProducers > 16
                    || burstBatchSize <= 0
                    || burstBatchSize > V34Phase3Support.MAX_BATCH_SIZE
                    || (long) burstProducers * burstBatchSize > documentCount
                    || queueCapacity < 4 || queueCapacity > 100_000) {
                throw new IllegalArgumentException(
                        "long-run arguments are outside their bounded ranges");
            }
            if (runKind.equals("final-v34-cloud")
                    && seconds != 1_800 && seconds != 7_200) {
                throw new IllegalArgumentException(
                        "final-v34 cloud duration must be 1800 or 7200 seconds");
            }
            if (sourceCommit.isBlank() || treeState.isBlank()
                    || sourceCommit.contains(" ") || treeState.contains(" ")) {
                throw new IllegalArgumentException(
                        "source identity must be non-blank and space-free");
            }
        }

        static Config parse(String[] arguments) {
            Set<String> allowed = Set.of(
                    "--output", "--documents", "--readers", "--seconds",
                    "--warmup-seconds", "--window-seconds", "--sample-millis",
                    "--top-k", "--steady-millis", "--burst-every-seconds",
                    "--burst-producers", "--burst-batch-size",
                    "--lifecycle-every-seconds", "--queue-capacity",
                    "--source-commit", "--tree-state", "--run-kind");
            Map<String, String> values = new HashMap<>();
            for (String argument : arguments) {
                int separator = argument.indexOf('=');
                if (separator <= 0 || separator == argument.length() - 1) {
                    throw new IllegalArgumentException(
                            "arguments must use --name=value: " + argument);
                }
                String name = argument.substring(0, separator);
                if (!allowed.contains(name)) {
                    throw new IllegalArgumentException("unknown argument: " + name);
                }
                if (values.putIfAbsent(
                        name, argument.substring(separator + 1)) != null) {
                    throw new IllegalArgumentException("duplicate argument: " + name);
                }
            }
            return new Config(
                    Path.of(values.getOrDefault(
                            "--output", "benchmark-results/v34-local-long-run")),
                    integer(values, "--documents", 10_000),
                    integer(values, "--readers", 6),
                    integer(values, "--seconds", 1_800),
                    integer(values, "--warmup-seconds", 30),
                    integer(values, "--window-seconds", 60),
                    integer(values, "--sample-millis", 1_000),
                    integer(values, "--top-k", 10),
                    integer(values, "--steady-millis", 25),
                    integer(values, "--burst-every-seconds", 60),
                    integer(values, "--burst-producers", 4),
                    integer(values, "--burst-batch-size", 100),
                    integer(values, "--lifecycle-every-seconds", 120),
                    integer(values, "--queue-capacity", 1_000),
                    values.getOrDefault("--source-commit", "local-uncommitted"),
                    values.getOrDefault("--tree-state", "working-tree"),
                    values.getOrDefault("--run-kind", "local-calibration"));
        }

        private static int integer(
                Map<String, String> values,
                String name,
                int fallback
        ) {
            try {
                return Integer.parseInt(values.getOrDefault(
                        name, Integer.toString(fallback)));
            } catch (NumberFormatException invalid) {
                throw new IllegalArgumentException(
                        "invalid integer for " + name, invalid);
            }
        }
    }
}
