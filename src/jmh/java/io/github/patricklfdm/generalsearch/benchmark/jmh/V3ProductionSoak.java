package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import jdk.jfr.Configuration;
import jdk.jfr.Recording;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.lang.management.MemoryUsage;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HexFormat;
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
import java.util.concurrent.atomic.AtomicLong;
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
    private static final QueryKind[] QUERY_KINDS = QueryKind.values();

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
            long initialSnapshotVersion = fixture.engine().metrics().snapshotVersion();
            String initialCorpusDigest = config.perQueryMetrics()
                    ? corpusDigest(fixture, config.documentCount())
                    : null;
            List<SearchRequest<V3ProductionBenchmarkSupport.Document>> requests =
                    V3ProductionBenchmarkSupport.requests(fixture, config.topK());
            StabilizationResult stabilization = config.stabilizationEnabled()
                    ? stabilize(
                            fixture,
                            config,
                            requests,
                            initialSnapshotVersion,
                            initialCorpusDigest)
                    : null;
            if (stabilization != null) {
                writeStabilizationSummary(config, stabilization, null);
                if (nextPhaseAfterReadiness(stabilization.readiness().ready())
                        == SoakPhase.NOT_READY) {
                    throw new StabilizationNotReadyException(
                            "stabilization readiness gate did not pass");
                }
            }
            MeasurementTiming measurement = run(
                    fixture,
                    config,
                    requests,
                    loadSeconds,
                    initialSnapshotVersion,
                    initialCorpusDigest);
            if (stabilization != null) {
                double handoffSeconds = (measurement.firstSampleNano()
                        - stabilization.lastSampleNano()) / 1_000_000_000.0;
                writeStabilizationSummary(config, stabilization, handoffSeconds);
                if (config.productionStabilization() && handoffSeconds > 30.0) {
                    throw new IllegalStateException(
                            "stabilization handoff exceeded 30 seconds");
                }
            }
        } catch (Throwable failure) {
            Files.writeString(
                    config.output().resolve("failure.txt"),
                    stackTrace(failure),
                    StandardCharsets.UTF_8);
            rethrow(failure);
        }
    }

    private static MeasurementTiming run(
            V3ProductionBenchmarkSupport.Fixture fixture,
            SoakConfig config,
            List<SearchRequest<V3ProductionBenchmarkSupport.Document>> requests,
            double loadSeconds,
            long initialSnapshotVersion,
            String initialCorpusDigest
    ) throws Exception {
        AtomicBoolean stop = new AtomicBoolean();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        LongAdder readOperations = new LongAdder();
        LongAdder writeOperations = new LongAdder();
        LongAdder indexCycles = new LongAdder();
        LongAdder errors = new LongAdder();
        QueryCounters queryCounters = config.perQueryMetrics()
                ? new QueryCounters()
                : null;
        AtomicLong firstSampleNano = new AtomicLong();
        CountDownLatch start = new CountDownLatch(1);
        int taskCount = config.readerCount() + config.writerCount()
                + (config.indexCycles() ? 1 : 0);
        ExecutorService workers = Executors.newFixedThreadPool(taskCount);
        List<Future<WorkerResult>> readers = new ArrayList<>();
        List<Future<WorkerResult>> writers = new ArrayList<>();
        Future<?> lifecycle = null;
        Recording recording = null;
        try {
            for (int worker = 0; worker < config.readerCount(); worker++) {
                int workerId = worker;
                Callable<WorkerResult> reader = config.perQueryMetrics()
                        ? () -> readLoopWithQueryMetrics(
                                fixture,
                                requests,
                                workerId,
                                start,
                                stop,
                                readOperations,
                                queryCounters)
                        : () -> readLoop(
                                fixture,
                                requests,
                                workerId,
                                start,
                                stop,
                                readOperations);
                readers.add(workers.submit(guarded(failure, errors, reader)));
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

            if (config.jfrOutput() != null) {
                recording = createMeasurementRecording(config.jfrOutput());
                recording.start();
            }
            long gcCountStarted = gcCount();
            long gcTimeStarted = gcTimeMillis();
            long runStarted = System.nanoTime();
            long deadline = runStarted + TimeUnit.SECONDS.toNanos(config.seconds());
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
                    errors,
                    queryCounters,
                    firstSampleNano,
                    start);
            stop.set(true);

            List<WorkerResult> readerResults = await(readers);
            List<WorkerResult> writerResults = await(writers);
            if (lifecycle != null) {
                lifecycle.get();
            }
            if (recording != null) {
                recording.stop();
                recording.close();
                recording = null;
            }
            Throwable workerFailure = failure.get();
            if (workerFailure != null) {
                throw new IllegalStateException("soak worker failed", workerFailure);
            }
            double runSeconds = elapsedSeconds(runStarted);
            String finalCorpusDigest = config.perQueryMetrics()
                    ? corpusDigest(fixture, config.documentCount())
                    : null;
            validateInvestigationOutcome(
                    fixture,
                    config,
                    initialSnapshotVersion,
                    initialCorpusDigest,
                    finalCorpusDigest,
                    readOperations.sum(),
                    writeOperations.sum(),
                    indexCycles.sum(),
                    queryCounters);
            writeSummary(
                    fixture,
                    config,
                    loadSeconds,
                    runSeconds,
                    readOperations.sum(),
                    writeOperations.sum(),
                    indexCycles.sum(),
                    errors.sum(),
                    readerResults,
                    writerResults,
                    queryCounters,
                    initialSnapshotVersion,
                    initialCorpusDigest,
                    finalCorpusDigest,
                    gcCountStarted,
                    gcTimeStarted);
            return new MeasurementTiming(firstSampleNano.get());
        } finally {
            stop.set(true);
            start.countDown();
            workers.shutdownNow();
            workers.awaitTermination(30, TimeUnit.SECONDS);
            if (recording != null) {
                recording.close();
            }
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
        return new WorkerResult(
                operations.sum(),
                latency,
                new LatencyReservoir[0]);
    }

    private static WorkerResult readLoopWithQueryMetrics(
            V3ProductionBenchmarkSupport.Fixture fixture,
            List<SearchRequest<V3ProductionBenchmarkSupport.Document>> requests,
            int workerId,
            CountDownLatch start,
            AtomicBoolean stop,
            LongAdder operations,
            QueryCounters queryCounters
    ) throws InterruptedException {
        LatencyReservoir latency = new LatencyReservoir(RESERVOIR_SIZE, workerId + 1L);
        LatencyReservoir[] queryLatency = queryReservoirs(workerId + 1L);
        int cursor = workerId;
        start.await();
        while (!stop.get()) {
            int requestIndex = Math.floorMod(cursor++, requests.size());
            SearchRequest<V3ProductionBenchmarkSupport.Document> request =
                    requests.get(requestIndex);
            long started = System.nanoTime();
            int hitCount = fixture.engine().search(request).hits().size();
            long elapsed = System.nanoTime() - started;
            latency.record(elapsed);
            if (hitCount > request.limit()) {
                throw new IllegalStateException("soak result exceeded request limit");
            }
            operations.increment();
            QueryKind queryKind = QUERY_KINDS[requestIndex];
            queryLatency[queryKind.ordinal()].record(elapsed);
            queryCounters.record(queryKind, elapsed);
        }
        return new WorkerResult(operations.sum(), latency, queryLatency);
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
            int documentRevision = config.updateMode() == UpdateMode.STABLE
                    ? 0
                    : Math.toIntExact(slot / config.documentCount() + 1L);
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
        return new WorkerResult(
                operations.sum(),
                latency,
                new LatencyReservoir[0]);
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

    private static StabilizationResult stabilize(
            V3ProductionBenchmarkSupport.Fixture fixture,
            SoakConfig config,
            List<SearchRequest<V3ProductionBenchmarkSupport.Document>> requests,
            long loadedSnapshotVersion,
            String loadedCorpusDigest
    ) throws Exception {
        AtomicBoolean stop = new AtomicBoolean();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        LongAdder reads = new LongAdder();
        LongAdder errors = new LongAdder();
        QueryCounters queryCounters = new QueryCounters();
        CountDownLatch start = new CountDownLatch(1);
        ExecutorService workers = Executors.newFixedThreadPool(config.readerCount());
        List<Future<WorkerResult>> readers = new ArrayList<>();
        List<StabilizationSample> samples = new ArrayList<>();
        long gcCountStarted = gcCount();
        long gcTimeStarted = gcTimeMillis();
        long lastSampleNano;
        try {
            for (int worker = 0; worker < config.readerCount(); worker++) {
                int workerId = worker;
                readers.add(workers.submit(guarded(failure, errors, () ->
                        readLoopWithQueryMetrics(
                                fixture,
                                requests,
                                workerId,
                                start,
                                stop,
                                reads,
                                queryCounters))));
            }
            Path evidence = config.output().resolve(
                    "soak-stabilization-samples.csv");
            MemoryMXBean memory = ManagementFactory.getMemoryMXBean();
            long started = System.nanoTime();
            long deadline = started + TimeUnit.SECONDS.toNanos(
                    config.stabilizationSeconds());
            start.countDown();
            try (PrintWriter csv = new PrintWriter(Files.newBufferedWriter(
                    evidence,
                    StandardCharsets.UTF_8))) {
                csv.println("timestamp,elapsed_s,used_heap_bytes,committed_heap_bytes,"
                        + "max_heap_bytes,read_ops,read_latency_ns,text_ops,"
                        + "text_latency_ns,bool_ops,bool_latency_ns,phrase_ops,"
                        + "phrase_latency_ns,fuzzy_ops,fuzzy_latency_ns,errors,"
                        + "snapshot_version,document_count,gc_count,gc_time_ms");
                while (System.nanoTime() < deadline && failure.get() == null) {
                    samples.add(writeStabilizationSample(
                            csv,
                            fixture.engine().metrics(),
                            memory.getHeapMemoryUsage(),
                            started,
                            reads.sum(),
                            errors.sum(),
                            queryCounters));
                    csv.flush();
                    TimeUnit.SECONDS.sleep(config.sampleSeconds());
                }
                stop.set(true);
                samples.add(writeStabilizationSample(
                        csv,
                        fixture.engine().metrics(),
                        memory.getHeapMemoryUsage(),
                        started,
                        reads.sum(),
                        errors.sum(),
                        queryCounters));
                csv.flush();
            }
            lastSampleNano = System.nanoTime();
            List<WorkerResult> readerResults = await(readers);
            Throwable workerFailure = failure.get();
            if (workerFailure != null) {
                throw new IllegalStateException(
                        "stabilization worker failed",
                        workerFailure);
            }
            SearchEngineMetrics postMetrics = fixture.engine().metrics();
            String postCorpusDigest = corpusDigest(fixture, config.documentCount());
            ReadinessDecision readiness = evaluateReadiness(
                    config,
                    samples,
                    loadedSnapshotVersion,
                    postMetrics.snapshotVersion(),
                    loadedCorpusDigest,
                    postCorpusDigest,
                    postMetrics.documentCount(),
                    errors.sum(),
                    readerResults.stream().allMatch(
                            result -> result.latency().size() > 0));
            return new StabilizationResult(
                    samples,
                    readiness,
                    loadedSnapshotVersion,
                    postMetrics.snapshotVersion(),
                    loadedCorpusDigest,
                    postCorpusDigest,
                    postMetrics.documentCount(),
                    samples.get(samples.size() - 1).readOperations(),
                    errors.sum(),
                    gcCount() - gcCountStarted,
                    gcTimeMillis() - gcTimeStarted,
                    lastSampleNano);
        } finally {
            stop.set(true);
            start.countDown();
            workers.shutdownNow();
            workers.awaitTermination(30, TimeUnit.SECONDS);
        }
    }

    private static StabilizationSample writeStabilizationSample(
            PrintWriter csv,
            SearchEngineMetrics metrics,
            MemoryUsage heap,
            long started,
            long reads,
            long errors,
            QueryCounters queryCounters
    ) {
        Instant timestamp = Instant.now();
        double elapsed = elapsedSeconds(started);
        QueryCounterSnapshot query = queryCounters.snapshot();
        long totalLatency = 0L;
        for (QueryKind kind : QUERY_KINDS) {
            totalLatency = Math.addExact(
                    totalLatency,
                    query.latencyNanoseconds(kind));
        }
        StabilizationSample sample = new StabilizationSample(
                timestamp,
                elapsed,
                heap.getUsed(),
                heap.getCommitted(),
                heap.getMax(),
                reads,
                totalLatency,
                query,
                errors,
                metrics.snapshotVersion(),
                metrics.documentCount(),
                gcCount(),
                gcTimeMillis());
        csv.printf(Locale.ROOT,
                "%s,%.9f,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d%n",
                timestamp,
                elapsed,
                heap.getUsed(),
                heap.getCommitted(),
                heap.getMax(),
                reads,
                totalLatency,
                query.operations(QueryKind.TEXT),
                query.latencyNanoseconds(QueryKind.TEXT),
                query.operations(QueryKind.BOOL),
                query.latencyNanoseconds(QueryKind.BOOL),
                query.operations(QueryKind.PHRASE),
                query.latencyNanoseconds(QueryKind.PHRASE),
                query.operations(QueryKind.FUZZY),
                query.latencyNanoseconds(QueryKind.FUZZY),
                errors,
                metrics.snapshotVersion(),
                metrics.documentCount(),
                sample.gcCount(),
                sample.gcTimeMillis());
        return sample;
    }

    static ReadinessDecision evaluateReadiness(
            SoakConfig config,
            List<StabilizationSample> samples,
            long loadedSnapshotVersion,
            long postSnapshotVersion,
            String loadedCorpusDigest,
            String postCorpusDigest,
            int postDocumentCount,
            long errors,
            boolean latencyEvidence
    ) {
        int windows = 5;
        @SuppressWarnings("unchecked")
        List<StabilizationSample>[] byWindow = new List[windows];
        Arrays.setAll(byWindow, ignored -> new ArrayList<>());
        boolean monotonic = true;
        StabilizationSample previous = null;
        for (StabilizationSample sample : samples) {
            int window = Math.min(
                    (int) Math.floor(sample.elapsedSeconds()
                            / config.stabilizationWindowSeconds()),
                    windows - 1);
            byWindow[window].add(sample);
            if (previous != null && !sample.monotonicFrom(previous)) {
                monotonic = false;
            }
            previous = sample;
        }
        int expected = (int) Math.floor(
                (config.stabilizationSeconds()
                        / (double) config.sampleSeconds()) * 0.95) + 1;
        boolean sampleCoverage = samples.size() >= expected;
        boolean windowCoverage = true;
        boolean positiveCoverage = true;
        double[][] rates = new double[QUERY_KINDS.length + 1][3];
        double[][] latencyMeans = new double[QUERY_KINDS.length + 1][3];
        boolean finitePositive = true;
        for (int window = 0; window < windows; window++) {
            windowCoverage &= byWindow[window].size() >= 2;
            if (window < 2 || byWindow[window].size() < 2) {
                continue;
            }
            StabilizationSample first = byWindow[window].get(0);
            StabilizationSample last = byWindow[window].get(
                    byWindow[window].size() - 1);
            double elapsed = last.elapsedSeconds() - first.elapsedSeconds();
            long operations = last.readOperations() - first.readOperations();
            long latency = last.readLatencyNanoseconds()
                    - first.readLatencyNanoseconds();
            int band = window - 2;
            rates[0][band] = operations / elapsed;
            latencyMeans[0][band] = latency / (double) operations;
            positiveCoverage &= elapsed > 0.0 && operations > 0 && latency > 0;
            finitePositive &= finitePositive(rates[0][band])
                    && finitePositive(latencyMeans[0][band]);
            for (QueryKind kind : QUERY_KINDS) {
                long queryOperations = last.query().operations(kind)
                        - first.query().operations(kind);
                long queryLatency = last.query().latencyNanoseconds(kind)
                        - first.query().latencyNanoseconds(kind);
                int metric = kind.ordinal() + 1;
                rates[metric][band] = queryOperations / elapsed;
                latencyMeans[metric][band] = queryLatency
                        / (double) queryOperations;
                positiveCoverage &= queryOperations > 0 && queryLatency > 0;
                finitePositive &= finitePositive(rates[metric][band])
                        && finitePositive(latencyMeans[metric][band]);
            }
        }
        boolean[] rateStable = new boolean[rates.length];
        boolean[] latencyStable = new boolean[latencyMeans.length];
        for (int metric = 0; metric < rates.length; metric++) {
            rateStable[metric] = relativeRange(rates[metric]) <= 0.05;
            latencyStable[metric] = relativeRange(latencyMeans[metric]) <= 0.10;
        }
        QueryCounterSnapshot finalQueries = samples.isEmpty()
                ? new QueryCounterSnapshot(new long[QUERY_KINDS.length],
                        new long[QUERY_KINDS.length])
                : samples.get(samples.size() - 1).query();
        long minimum = Long.MAX_VALUE;
        long maximum = Long.MIN_VALUE;
        for (QueryKind kind : QUERY_KINDS) {
            long count = finalQueries.operations(kind);
            minimum = Math.min(minimum, count);
            maximum = Math.max(maximum, count);
        }
        boolean queryBalance = maximum - minimum <= config.readerCount();
        boolean noErrors = errors == 0;
        boolean documentsUnchanged = postDocumentCount == config.documentCount();
        boolean snapshotUnchanged = postSnapshotVersion == loadedSnapshotVersion;
        boolean corpusUnchanged = loadedCorpusDigest.equals(postCorpusDigest);
        boolean zeroMutations = config.writerCount() <= 1
                && !config.indexCycles();
        boolean performanceStable = all(rateStable) && all(latencyStable);
        boolean ready = sampleCoverage && windowCoverage && positiveCoverage
                && finitePositive && monotonic && noErrors && documentsUnchanged
                && snapshotUnchanged && corpusUnchanged && zeroMutations
                && queryBalance && latencyEvidence
                && (!config.productionStabilization() || performanceStable);
        return new ReadinessDecision(
                ready,
                sampleCoverage,
                windowCoverage,
                positiveCoverage,
                finitePositive,
                monotonic,
                noErrors,
                documentsUnchanged,
                snapshotUnchanged,
                corpusUnchanged,
                zeroMutations,
                queryBalance,
                latencyEvidence,
                rateStable,
                latencyStable,
                rates,
                latencyMeans,
                Arrays.stream(byWindow).mapToInt(List::size).toArray());
    }

    private static boolean finitePositive(double value) {
        return Double.isFinite(value) && value > 0.0;
    }

    private static double relativeRange(double[] values) {
        double minimum = Arrays.stream(values).min().orElse(Double.NaN);
        double maximum = Arrays.stream(values).max().orElse(Double.NaN);
        double mean = Arrays.stream(values).average().orElse(Double.NaN);
        return (maximum - minimum) / mean;
    }

    private static boolean all(boolean[] values) {
        for (boolean value : values) {
            if (!value) {
                return false;
            }
        }
        return true;
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
            LongAdder errors,
            QueryCounters queryCounters,
            AtomicLong firstSampleNano,
            CountDownLatch measurementStart
    ) throws IOException, InterruptedException {
        Path output = config.output().resolve("soak-samples.csv");
        Path queryOutput = config.output().resolve("soak-query-samples.csv");
        MemoryMXBean memory = ManagementFactory.getMemoryMXBean();
        try (PrintWriter csv = new PrintWriter(Files.newBufferedWriter(
                output,
                StandardCharsets.UTF_8));
             PrintWriter queryCsv = config.perQueryMetrics()
                     ? new PrintWriter(Files.newBufferedWriter(
                             queryOutput,
                             StandardCharsets.UTF_8))
                     : null) {
            csv.println("timestamp,elapsed_s,used_heap_bytes,committed_heap_bytes,"
                    + "max_heap_bytes,read_ops,write_ops,index_cycles,errors,"
                    + "writer_queue_depth,writer_queue_capacity,snapshot_version,"
                    + "document_count,gc_count,gc_time_ms");
            if (queryCsv != null) {
                queryCsv.println("timestamp,elapsed_s,text_ops,text_latency_ns,"
                        + "bool_ops,bool_latency_ns,phrase_ops,phrase_latency_ns,"
                        + "fuzzy_ops,fuzzy_latency_ns");
            }
            while (System.nanoTime() < deadline && failure.get() == null) {
                writeSamples(
                        csv,
                        queryCsv,
                        fixture.engine().metrics(),
                        memory.getHeapMemoryUsage(),
                        runStarted,
                        reads.sum(),
                        writes.sum(),
                        indexCycles.sum(),
                        errors.sum(),
                        queryCounters,
                        firstSampleNano);
                csv.flush();
                if (queryCsv != null) {
                    queryCsv.flush();
                }
                measurementStart.countDown();
                TimeUnit.SECONDS.sleep(config.sampleSeconds());
            }
            stop.set(true);
            writeSamples(
                    csv,
                    queryCsv,
                    fixture.engine().metrics(),
                    memory.getHeapMemoryUsage(),
                    runStarted,
                    reads.sum(),
                    writes.sum(),
                    indexCycles.sum(),
                    errors.sum(),
                    queryCounters,
                    firstSampleNano);
        }
    }

    private static void writeSamples(
            PrintWriter csv,
            PrintWriter queryCsv,
            SearchEngineMetrics metrics,
            MemoryUsage heap,
            long runStarted,
            long reads,
            long writes,
            long indexCycles,
            long errors,
            QueryCounters queryCounters,
            AtomicLong firstSampleNano
    ) {
        firstSampleNano.compareAndSet(0L, System.nanoTime());
        Instant timestamp = Instant.now();
        double elapsed = elapsedSeconds(runStarted);
        csv.printf(Locale.ROOT,
                "%s,%.3f,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d%n",
                timestamp,
                elapsed,
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
        if (queryCsv != null) {
            if (queryCounters == null) {
                throw new IllegalStateException(
                        "query output requires per-query counters");
            }
            QueryCounterSnapshot querySnapshot = queryCounters.snapshot();
            queryCsv.printf(Locale.ROOT,
                    "%s,%.3f,%d,%d,%d,%d,%d,%d,%d,%d%n",
                    timestamp,
                    elapsed,
                    querySnapshot.operations(QueryKind.TEXT),
                    querySnapshot.latencyNanoseconds(QueryKind.TEXT),
                    querySnapshot.operations(QueryKind.BOOL),
                    querySnapshot.latencyNanoseconds(QueryKind.BOOL),
                    querySnapshot.operations(QueryKind.PHRASE),
                    querySnapshot.latencyNanoseconds(QueryKind.PHRASE),
                    querySnapshot.operations(QueryKind.FUZZY),
                    querySnapshot.latencyNanoseconds(QueryKind.FUZZY));
        }
    }

    private static void writeStabilizationSummary(
            SoakConfig config,
            StabilizationResult result,
            Double handoffSeconds
    ) throws IOException {
        ReadinessDecision readiness = result.readiness();
        Properties values = new Properties();
        values.setProperty("stabilization_status",
                readiness.ready() ? "READY" : "NOT_READY");
        values.setProperty("measurement_started",
                Boolean.toString(handoffSeconds != null));
        values.setProperty("final_phase_state",
                readiness.ready()
                        ? (handoffSeconds == null
                                ? SoakPhase.EVALUATE_READINESS.name()
                                : SoakPhase.COMPLETE.name())
                        : SoakPhase.NOT_READY.name());
        values.setProperty("stabilization_purpose",
                config.stabilizationPurpose().value());
        values.setProperty("configured_seconds",
                Integer.toString(config.stabilizationSeconds()));
        values.setProperty("configured_window_seconds",
                Integer.toString(config.stabilizationWindowSeconds()));
        values.setProperty("sample_count",
                Integer.toString(result.samples().size()));
        values.setProperty("read_operations", Long.toString(result.reads()));
        values.setProperty("write_operations", "0");
        values.setProperty("index_cycles", "0");
        values.setProperty("errors", Long.toString(result.errors()));
        values.setProperty("loaded_snapshot_version",
                Long.toString(result.loadedSnapshotVersion()));
        values.setProperty("post_snapshot_version",
                Long.toString(result.postSnapshotVersion()));
        values.setProperty("loaded_corpus_sha256", result.loadedCorpusDigest());
        values.setProperty("post_corpus_sha256", result.postCorpusDigest());
        values.setProperty("post_document_count",
                Integer.toString(result.postDocumentCount()));
        values.setProperty("stabilization_gc_count",
                Long.toString(result.gcCount()));
        values.setProperty("stabilization_gc_time_ms",
                Long.toString(result.gcTimeMillis()));
        addReadinessFlag(values, "sample_coverage", readiness.sampleCoverage());
        addReadinessFlag(values, "window_coverage", readiness.windowCoverage());
        addReadinessFlag(values, "positive_coverage", readiness.positiveCoverage());
        addReadinessFlag(values, "finite_positive", readiness.finitePositive());
        addReadinessFlag(values, "monotonic", readiness.monotonic());
        addReadinessFlag(values, "no_errors", readiness.noErrors());
        addReadinessFlag(values, "documents_unchanged",
                readiness.documentsUnchanged());
        addReadinessFlag(values, "snapshot_unchanged",
                readiness.snapshotUnchanged());
        addReadinessFlag(values, "corpus_unchanged", readiness.corpusUnchanged());
        addReadinessFlag(values, "zero_mutations", readiness.zeroMutations());
        addReadinessFlag(values, "query_balance", readiness.queryBalance());
        addReadinessFlag(values, "latency_evidence", readiness.latencyEvidence());
        String[] metrics = {"aggregate", "text", "bool", "phrase", "fuzzy"};
        for (int metric = 0; metric < metrics.length; metric++) {
            addReadinessFlag(values,
                    metrics[metric] + "_rate_stable",
                    readiness.rateStable()[metric]);
            addReadinessFlag(values,
                    metrics[metric] + "_latency_stable",
                    readiness.latencyStable()[metric]);
            for (int band = 0; band < 3; band++) {
                int window = band + 3;
                values.setProperty(metrics[metric] + "_window_" + window
                                + "_ops_per_second",
                        Double.toString(readiness.rates()[metric][band]));
                values.setProperty(metrics[metric] + "_window_" + window
                                + "_mean_latency_ns",
                        Double.toString(readiness.latencyMeans()[metric][band]));
            }
        }
        for (int window = 0; window < readiness.windowSampleCounts().length;
                window++) {
            values.setProperty("window_" + (window + 1) + "_sample_count",
                    Integer.toString(readiness.windowSampleCounts()[window]));
        }
        if (handoffSeconds != null) {
            values.setProperty("stabilization_handoff_seconds",
                    Double.toString(handoffSeconds));
            values.setProperty("handoff_within_30_seconds",
                    Boolean.toString(handoffSeconds <= 30.0));
        }
        try (var output = Files.newOutputStream(config.output().resolve(
                "soak-stabilization-summary.properties"))) {
            values.store(output, "V3 soak stabilization readiness result");
        }
    }

    private static void addReadinessFlag(
            Properties values,
            String name,
            boolean value
    ) {
        values.setProperty("readiness_" + name, Boolean.toString(value));
    }

    private static Recording createMeasurementRecording(Path output)
            throws Exception {
        Path parent = output.toAbsolutePath().getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        Recording recording = new Recording(Configuration.getConfiguration("profile"));
        recording.setName("v3-soak-measurement-only");
        recording.setToDisk(true);
        recording.setDumpOnExit(true);
        recording.setMaxSize(512L * 1024L * 1024L);
        recording.setDestination(output);
        return recording;
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
        values.setProperty("update_mode", config.updateMode().value());
        values.setProperty("per_query_metrics",
                Boolean.toString(config.perQueryMetrics()));
        values.setProperty("investigation_cell", config.investigationCell());
        values.setProperty("stabilization_purpose",
                config.stabilizationPurpose().value());
        values.setProperty("stabilization_seconds",
                Integer.toString(config.stabilizationSeconds()));
        values.setProperty("stabilization_window_seconds",
                Integer.toString(config.stabilizationWindowSeconds()));
        values.setProperty("allow_reduced_stabilization_test",
                Boolean.toString(config.allowReducedStabilizationTest()));
        values.setProperty("jfr_output",
                config.jfrOutput() == null ? "none" : config.jfrOutput().toString());
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
            List<WorkerResult> writerResults,
            QueryCounters queryCounters,
            long initialSnapshotVersion,
            String initialCorpusDigest,
            String finalCorpusDigest,
            long gcCountStarted,
            long gcTimeStarted
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
        values.setProperty("measurement_gc_count",
                Long.toString(gcCount() - gcCountStarted));
        values.setProperty("measurement_gc_time_ms",
                Long.toString(gcTimeMillis() - gcTimeStarted));
        if (config.perQueryMetrics()) {
            values.setProperty("initial_snapshot_version",
                    Long.toString(initialSnapshotVersion));
            values.setProperty("initial_corpus_sha256", initialCorpusDigest);
            values.setProperty("final_corpus_sha256", finalCorpusDigest);
            values.setProperty("corpus_changed",
                    Boolean.toString(!initialCorpusDigest.equals(finalCorpusDigest)));
            addQuerySummaries(values, runSeconds, readerResults, queryCounters);
        }
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

    private static void addQuerySummaries(
            Properties values,
            double runSeconds,
            List<WorkerResult> readerResults,
            QueryCounters queryCounters
    ) {
        QueryCounterSnapshot counters = queryCounters.snapshot();
        for (QueryKind queryKind : QUERY_KINDS) {
            String prefix = queryKind.value() + "_read";
            long operations = counters.operations(queryKind);
            values.setProperty(prefix + "_operations", Long.toString(operations));
            values.setProperty(prefix + "_ops_per_second",
                    decimal(operations / runSeconds));
            long[] latency = querySamples(readerResults, queryKind);
            addLatency(
                    values,
                    prefix,
                    latency,
                    queryMaxLatency(readerResults, queryKind));
        }
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

    private static long queryMaxLatency(
            List<WorkerResult> results,
            QueryKind queryKind
    ) {
        return results.stream()
                .mapToLong(result -> result.queryLatency()[queryKind.ordinal()].max())
                .max()
                .orElse(0L);
    }

    private static long[] querySamples(
            List<WorkerResult> results,
            QueryKind queryKind
    ) {
        int size = results.stream()
                .mapToInt(result -> result.queryLatency()[queryKind.ordinal()].size())
                .sum();
        long[] combined = new long[size];
        int offset = 0;
        for (WorkerResult result : results) {
            long[] workerSamples =
                    result.queryLatency()[queryKind.ordinal()].samples();
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

    private static LatencyReservoir[] queryReservoirs(long seed) {
        LatencyReservoir[] reservoirs = new LatencyReservoir[QUERY_KINDS.length];
        for (QueryKind queryKind : QUERY_KINDS) {
            reservoirs[queryKind.ordinal()] = new LatencyReservoir(
                    RESERVOIR_SIZE,
                    seed * 31L + queryKind.ordinal() + 1L);
        }
        return reservoirs;
    }

    static String corpusDigest(
            V3ProductionBenchmarkSupport.Fixture fixture,
            int documentCount
    ) {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 is unavailable", impossible);
        }
        for (int id = 0; id < documentCount; id++) {
            V3ProductionBenchmarkSupport.Document document =
                    fixture.engine().get((long) id);
            if (document == null) {
                throw new IllegalStateException(
                        "missing document while computing corpus digest: " + id);
            }
            updateLong(digest, document.id());
            updateString(digest, document.category());
            updateInt(digest, document.popularity());
            updateString(digest, document.title());
            updateString(digest, document.body());
            updateString(digest, document.tags());
            updateString(digest, document.summary());
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static void updateLong(MessageDigest digest, long value) {
        digest.update(ByteBuffer.allocate(Long.BYTES)
                .order(ByteOrder.BIG_ENDIAN)
                .putLong(value)
                .array());
    }

    private static void updateInt(MessageDigest digest, int value) {
        digest.update(ByteBuffer.allocate(Integer.BYTES)
                .order(ByteOrder.BIG_ENDIAN)
                .putInt(value)
                .array());
    }

    private static void updateString(MessageDigest digest, String value) {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        updateInt(digest, encoded.length);
        digest.update(encoded);
    }

    private static void validateInvestigationOutcome(
            V3ProductionBenchmarkSupport.Fixture fixture,
            SoakConfig config,
            long initialSnapshotVersion,
            String initialCorpusDigest,
            String finalCorpusDigest,
            long reads,
            long writes,
            long indexCycles,
            QueryCounters queryCounters
    ) {
        if (!config.perQueryMetrics()) {
            return;
        }
        if (fixture.engine().metrics().documentCount() != config.documentCount()) {
            throw new IllegalStateException("investigation document count changed");
        }
        if (indexCycles != 0) {
            throw new IllegalStateException(
                    "investigation workload unexpectedly ran index cycles");
        }
        QueryCounterSnapshot counters = queryCounters.snapshot();
        long queryReads = 0;
        long minimum = Long.MAX_VALUE;
        long maximum = Long.MIN_VALUE;
        for (QueryKind queryKind : QUERY_KINDS) {
            long operations = counters.operations(queryKind);
            long latency = counters.latencyNanoseconds(queryKind);
            if (operations <= 0 || latency <= 0) {
                throw new IllegalStateException(
                        "investigation query has no evidence: " + queryKind.value());
            }
            queryReads = Math.addExact(queryReads, operations);
            minimum = Math.min(minimum, operations);
            maximum = Math.max(maximum, operations);
        }
        if (queryReads != reads) {
            throw new IllegalStateException(
                    "per-query operations do not sum to total reads");
        }
        if (maximum - minimum > config.readerCount()) {
            throw new IllegalStateException(
                    "deterministic query rotation is unexpectedly unbalanced");
        }
        long finalSnapshotVersion = fixture.engine().metrics().snapshotVersion();
        boolean corpusChanged = !initialCorpusDigest.equals(finalCorpusDigest);
        switch (config.updateMode()) {
            case NONE -> {
                if (writes != 0 || finalSnapshotVersion != initialSnapshotVersion
                        || corpusChanged) {
                    throw new IllegalStateException(
                            "read-only investigation changed engine state");
                }
            }
            case STABLE -> {
                if (writes <= 0 || finalSnapshotVersion <= initialSnapshotVersion
                        || corpusChanged) {
                    throw new IllegalStateException(
                            "stable-update investigation violated its state contract");
                }
            }
            case REVISION -> {
                if (writes <= 0 || finalSnapshotVersion <= initialSnapshotVersion
                        || !corpusChanged) {
                    throw new IllegalStateException(
                            "revision-update investigation violated its state contract");
                }
            }
        }
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

    private record WorkerResult(
            long operations,
            LatencyReservoir latency,
            LatencyReservoir[] queryLatency
    ) {
    }

    private record MeasurementTiming(long firstSampleNano) {
        MeasurementTiming {
            if (firstSampleNano <= 0L) {
                throw new IllegalStateException(
                        "measurement did not emit a first sample");
            }
        }
    }

    record StabilizationSample(
            Instant timestamp,
            double elapsedSeconds,
            long usedHeapBytes,
            long committedHeapBytes,
            long maxHeapBytes,
            long readOperations,
            long readLatencyNanoseconds,
            QueryCounterSnapshot query,
            long errors,
            long snapshotVersion,
            int documentCount,
            long gcCount,
            long gcTimeMillis
    ) {
        boolean monotonicFrom(StabilizationSample previous) {
            if (elapsedSeconds < previous.elapsedSeconds
                    || readOperations < previous.readOperations
                    || readLatencyNanoseconds < previous.readLatencyNanoseconds
                    || errors < previous.errors
                    || gcCount < previous.gcCount
                    || gcTimeMillis < previous.gcTimeMillis) {
                return false;
            }
            for (QueryKind kind : QUERY_KINDS) {
                if (query.operations(kind) < previous.query.operations(kind)
                        || query.latencyNanoseconds(kind)
                        < previous.query.latencyNanoseconds(kind)) {
                    return false;
                }
            }
            return true;
        }
    }

    record ReadinessDecision(
            boolean ready,
            boolean sampleCoverage,
            boolean windowCoverage,
            boolean positiveCoverage,
            boolean finitePositive,
            boolean monotonic,
            boolean noErrors,
            boolean documentsUnchanged,
            boolean snapshotUnchanged,
            boolean corpusUnchanged,
            boolean zeroMutations,
            boolean queryBalance,
            boolean latencyEvidence,
            boolean[] rateStable,
            boolean[] latencyStable,
            double[][] rates,
            double[][] latencyMeans,
            int[] windowSampleCounts
    ) {
    }

    private record StabilizationResult(
            List<StabilizationSample> samples,
            ReadinessDecision readiness,
            long loadedSnapshotVersion,
            long postSnapshotVersion,
            String loadedCorpusDigest,
            String postCorpusDigest,
            int postDocumentCount,
            long reads,
            long errors,
            long gcCount,
            long gcTimeMillis,
            long lastSampleNano
    ) {
    }

    private static final class StabilizationNotReadyException
            extends IllegalStateException {
        private StabilizationNotReadyException(String message) {
            super(message);
        }
    }

    enum SoakPhase {
        LOAD_FIXTURE,
        CAPTURE_LOADED_IDENTITY,
        STABILIZE_READ_ONLY,
        CAPTURE_POST_STABILIZATION_IDENTITY,
        EVALUATE_READINESS,
        MEASURE_SELECTED_CELL,
        COMPLETE,
        NOT_READY
    }

    static SoakPhase nextPhaseAfterReadiness(boolean ready) {
        return ready ? SoakPhase.MEASURE_SELECTED_CELL : SoakPhase.NOT_READY;
    }

    enum QueryKind {
        TEXT("text"),
        BOOL("bool"),
        PHRASE("phrase"),
        FUZZY("fuzzy");

        private final String value;

        QueryKind(String value) {
            this.value = value;
        }

        String value() {
            return value;
        }
    }

    enum UpdateMode {
        NONE("none"),
        STABLE("stable"),
        REVISION("revision");

        private final String value;

        UpdateMode(String value) {
            this.value = value;
        }

        String value() {
            return value;
        }

        static UpdateMode parse(String value) {
            for (UpdateMode mode : values()) {
                if (mode.value.equals(value)) {
                    return mode;
                }
            }
            throw new IllegalArgumentException(
                    "update mode must be none, stable, or revision: " + value);
        }
    }

    enum StabilizationPurpose {
        NONE("none"),
        SCREENING("screening"),
        CONFIRMATION("confirmation"),
        PROFILE("profile"),
        REDUCED_TEST("reduced-test");

        private final String value;

        StabilizationPurpose(String value) {
            this.value = value;
        }

        String value() {
            return value;
        }

        static StabilizationPurpose parse(String value) {
            for (StabilizationPurpose purpose : values()) {
                if (purpose.value.equals(value)) {
                    return purpose;
                }
            }
            throw new IllegalArgumentException(
                    "stabilization purpose must be none, screening, confirmation, "
                            + "profile, or reduced-test: " + value);
        }
    }

    static final class QueryCounters {
        private final LongAdder[] operations = adders();
        private final LongAdder[] latencyNanoseconds = adders();

        void record(QueryKind queryKind, long latency) {
            if (latency < 0) {
                throw new IllegalArgumentException("query latency must not be negative");
            }
            latencyNanoseconds[queryKind.ordinal()].add(latency);
            operations[queryKind.ordinal()].increment();
        }

        QueryCounterSnapshot snapshot() {
            long[] operationValues = new long[QUERY_KINDS.length];
            long[] latencyValues = new long[QUERY_KINDS.length];
            for (QueryKind queryKind : QUERY_KINDS) {
                int index = queryKind.ordinal();
                operationValues[index] = operations[index].sum();
                latencyValues[index] = latencyNanoseconds[index].sum();
            }
            return new QueryCounterSnapshot(operationValues, latencyValues);
        }

        private static LongAdder[] adders() {
            LongAdder[] values = new LongAdder[QUERY_KINDS.length];
            Arrays.setAll(values, ignored -> new LongAdder());
            return values;
        }
    }

    record QueryCounterSnapshot(
            long[] operations,
            long[] latencyNanoseconds
    ) {
        QueryCounterSnapshot {
            operations = operations.clone();
            latencyNanoseconds = latencyNanoseconds.clone();
        }

        long operations(QueryKind queryKind) {
            return operations[queryKind.ordinal()];
        }

        long latencyNanoseconds(QueryKind queryKind) {
            return latencyNanoseconds[queryKind.ordinal()];
        }
    }

    static final class LatencyReservoir {
        private final long[] samples;
        private int size;
        private long seen;
        private long randomState;
        private long max;

        LatencyReservoir(int capacity, long seed) {
            samples = new long[capacity];
            randomState = seed;
        }

        void record(long nanoseconds) {
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

        int size() {
            return size;
        }

        long[] samples() {
            return Arrays.copyOf(samples, size);
        }

        long max() {
            return max;
        }
    }

    record SoakConfig(
            Path output,
            int documentCount,
            int readerCount,
            int writerCount,
            int seconds,
            int sampleSeconds,
            int topK,
            String corpusProfile,
            boolean indexCycles,
            UpdateMode updateMode,
            boolean perQueryMetrics,
            StabilizationPurpose stabilizationPurpose,
            int stabilizationSeconds,
            int stabilizationWindowSeconds,
            boolean allowReducedStabilizationTest,
            Path jfrOutput
    ) {
        SoakConfig {
            if (documentCount <= 0 || readerCount <= 0 || writerCount < 0
                    || seconds <= 0 || sampleSeconds <= 0 || topK <= 0) {
                throw new IllegalArgumentException(
                        "numeric soak arguments are outside their valid range");
            }
            if ((writerCount == 0) != (updateMode == UpdateMode.NONE)) {
                throw new IllegalArgumentException(
                        "writers=0 requires update mode none and vice versa");
            }
            if (perQueryMetrics && indexCycles) {
                throw new IllegalArgumentException(
                        "investigation metrics require index cycles to be disabled");
            }
            if (perQueryMetrics && writerCount > 1) {
                throw new IllegalArgumentException(
                        "investigation mutation cells require exactly one writer");
            }
            validateStabilization(
                    readerCount,
                    writerCount,
                    seconds,
                    sampleSeconds,
                    indexCycles,
                    updateMode,
                    perQueryMetrics,
                    stabilizationPurpose,
                    stabilizationSeconds,
                    stabilizationWindowSeconds,
                    allowReducedStabilizationTest,
                    jfrOutput);
        }

        static SoakConfig parse(String[] args) {
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
                    booleanArg(args, "--index-cycles", true),
                    UpdateMode.parse(stringArg(args, "--update-mode", "revision")),
                    booleanArg(args, "--per-query-metrics", false),
                    StabilizationPurpose.parse(stringArg(
                            args,
                            "--stabilization-purpose",
                            "none")),
                    intArg(args, "--stabilization-seconds", 0),
                    intArg(args, "--stabilization-window-seconds", 60),
                    booleanArg(args,
                            "--allow-reduced-stabilization-test",
                            false),
                    pathArg(args, "--jfr-output"));
        }

        boolean stabilizationEnabled() {
            return stabilizationPurpose != StabilizationPurpose.NONE;
        }

        boolean productionStabilization() {
            return stabilizationPurpose != StabilizationPurpose.NONE
                    && stabilizationPurpose != StabilizationPurpose.REDUCED_TEST;
        }

        String investigationCell() {
            if (!perQueryMetrics) {
                return "none";
            }
            return switch (updateMode) {
                case NONE -> "read-only";
                case STABLE -> "stable-update";
                case REVISION -> "revision-update";
            };
        }

        private static int intArg(String[] args, String name, int fallback) {
            return Integer.parseInt(stringArg(args, name, Integer.toString(fallback)));
        }

        private static Path pathArg(String[] args, String name) {
            String value = stringArg(args, name, "");
            return value.isEmpty() ? null : Path.of(value);
        }

        private static void validateStabilization(
                int readers,
                int writers,
                int measurementSeconds,
                int sampleSeconds,
                boolean indexCycles,
                UpdateMode updateMode,
                boolean perQueryMetrics,
                StabilizationPurpose purpose,
                int stabilizationSeconds,
                int windowSeconds,
                boolean allowReduced,
                Path jfrOutput
        ) {
            if (purpose == StabilizationPurpose.NONE) {
                if (stabilizationSeconds != 0 || allowReduced || jfrOutput != null) {
                    throw new IllegalArgumentException(
                            "purpose none requires zero stabilization, no reduced flag, "
                                    + "and no JFR output");
                }
                return;
            }
            if (!perQueryMetrics || indexCycles || writers > 1
                    || updateMode == UpdateMode.NONE) {
                if (purpose != StabilizationPurpose.REDUCED_TEST
                        || !perQueryMetrics || indexCycles || writers > 1) {
                    throw new IllegalArgumentException(
                            "stabilization requires investigation metrics, no index "
                                    + "cycles, and at most one writer");
                }
            }
            if (sampleSeconds != 1) {
                throw new IllegalArgumentException(
                        "stabilization requires one-second evidence sampling");
            }
            if (purpose == StabilizationPurpose.REDUCED_TEST) {
                if (!allowReduced || windowSeconds <= 0
                        || stabilizationSeconds != 5 * windowSeconds
                        || measurementSeconds < 12) {
                    throw new IllegalArgumentException(
                            "reduced-test requires five positive windows, at least "
                                    + "12 measurement seconds, and the reduced flag");
                }
                return;
            }
            if (allowReduced || readers != 16 || writers != 1
                    || (updateMode != UpdateMode.STABLE
                    && updateMode != UpdateMode.REVISION)
                    || stabilizationSeconds != 300 || windowSeconds != 60) {
                throw new IllegalArgumentException(
                        "production stabilization requires 16 readers, one mutation "
                                + "writer, stable/revision mode, and 300s/60s windows");
            }
            int requiredMeasurement = purpose == StabilizationPurpose.CONFIRMATION
                    ? 1_800
                    : 600;
            if (measurementSeconds != requiredMeasurement) {
                throw new IllegalArgumentException(
                        "measurement duration does not match stabilization purpose");
            }
            if ((purpose == StabilizationPurpose.PROFILE) != (jfrOutput != null)) {
                throw new IllegalArgumentException(
                        "profile requires JFR output and other production purposes "
                                + "forbid it");
            }
        }

        private static boolean booleanArg(
                String[] args,
                String name,
                boolean fallback
        ) {
            String value = stringArg(args, name, Boolean.toString(fallback));
            return switch (value) {
                case "true" -> true;
                case "false" -> false;
                default -> throw new IllegalArgumentException(
                        name + " must be true or false: " + value);
            };
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
