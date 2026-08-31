package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.LongAdder;
import io.github.patricklfdm.generalsearch.engine.exception.BulkMutationException;
import io.github.patricklfdm.generalsearch.engine.exception.DocumentNotFoundException;
import io.github.patricklfdm.generalsearch.engine.exception.EngineRejectedExecutionException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;

/**
 * Bounded multi-producer mutation matrix with reader, dynamic-index, failure, and
 * drainage oracles. Application producers remain clients of the one engine writer.
 */
public final class V34BurstRecoveryProbe {
    private static final int MAX_PRODUCERS = 16;
    private static final int MAX_BATCHES_PER_PRODUCER = 64;
    private static final int MAX_DOCUMENTS = 1_000_000;

    private V34BurstRecoveryProbe() {
    }

    public static void main(String[] arguments) throws Exception {
        Config config = Config.parse(arguments);
        long matrixChecksum = 1L;
        int cells = 0;
        for (int producers : config.producerCounts()) {
            for (int batchSize : config.batchSizes()) {
                CellResult result = runCell(config, producers, batchSize);
                cells++;
                matrixChecksum = 31L * matrixChecksum + result.checksum();
                System.out.printf(Locale.ROOT,
                        "burstCell=SUCCESS producers=%d batchSize=%d "
                                + "batchesPerProducer=%d documents=%d "
                                + "submittedBatches=%d submittedMutations=%d "
                                + "successfulBatches=%d successfulMutations=%d "
                                + "queueRejections=%d expectedFailures=%d "
                                + "unexpectedFailures=%d unresolvedFutures=%d "
                                + "readerOperations=%d readerChecksum=%d "
                                + "queueMaximum=%d queueCapacity=%d "
                                + "snapshotDelta=%d publicationRate=%.3f "
                                + "submissionRate=%.3f drainNanos=%d "
                                + "admissionP50Nanos=%d admissionP95Nanos=%d "
                                + "admissionP99Nanos=%d completionP50Nanos=%d "
                                + "completionP95Nanos=%d completionP99Nanos=%d "
                                + "readerP50Nanos=%d readerP95Nanos=%d "
                                + "readerP99Nanos=%d gcCount=%d gcTimeMillis=%d "
                                + "checksum=%d corpusDigest=%s%n",
                        producers,
                        batchSize,
                        config.batchesPerProducer(),
                        config.documentCount(),
                        result.submittedBatches(),
                        result.submittedMutations(),
                        result.successfulBatches(),
                        result.successfulMutations(),
                        result.queueRejections(),
                        result.expectedFailures(),
                        result.unexpectedFailures(),
                        result.unresolvedFutures(),
                        result.readerOperations(),
                        result.readerChecksum(),
                        result.queueMaximum(),
                        result.queueCapacity(),
                        result.snapshotDelta(),
                        result.publicationRate(),
                        result.submissionRate(),
                        result.drainNanos(),
                        result.admissionP50Nanos(),
                        result.admissionP95Nanos(),
                        result.admissionP99Nanos(),
                        result.completionP50Nanos(),
                        result.completionP95Nanos(),
                        result.completionP99Nanos(),
                        result.readerP50Nanos(),
                        result.readerP95Nanos(),
                        result.readerP99Nanos(),
                        result.gcCount(),
                        result.gcTimeMillis(),
                        result.checksum(),
                        result.corpusDigest());
            }
        }
        if (cells == 0 || matrixChecksum == 0L) {
            throw new IllegalStateException("burst matrix produced no evidence");
        }
        System.out.printf(
                "burstMatrix=SUCCESS cells=%d checksum=%d%n",
                cells,
                matrixChecksum);
    }

    static CellResult runCell(
            Config config,
            int producerCount,
            int batchSize
    ) throws Exception {
        int requiredDocuments = Math.multiplyExact(
                Math.multiplyExact(producerCount, batchSize),
                config.batchesPerProducer());
        if (requiredDocuments > config.documentCount()) {
            throw new IllegalArgumentException(
                    "cell needs " + requiredDocuments + " documents but only "
                            + config.documentCount() + " were configured");
        }

        try (var fixture = V34Phase3Support.createFixture(
                config.documentCount(), config.queueCapacity())) {
            var engine = fixture.engine();
            List<MutationOperation> operations = operations(
                    producerCount,
                    batchSize,
                    config.batchesPerProducer());
            long initialSnapshot = engine.metrics().snapshotVersion();
            long initialSuccessful = engine.metrics().successfulMutations();
            long gcStarted = V34Phase3Support.gcCount();
            long gcTimeStarted = V34Phase3Support.gcTimeMillis();

            AtomicBoolean stop = new AtomicBoolean();
            AtomicReference<Throwable> failure = new AtomicReference<>();
            AtomicInteger queueMaximum = new AtomicInteger();
            AtomicInteger queueCapacity = new AtomicInteger(config.queueCapacity());
            LongAdder readerOperations = new LongAdder();
            LongAdder readerChecksum = new LongAdder();
            CountDownLatch ready = new CountDownLatch(
                    producerCount + config.readerCount() + 2);
            CountDownLatch start = new CountDownLatch(1);
            CountDownLatch lifecycleSubmitted = new CountDownLatch(1);
            ExecutorService workers = Executors.newFixedThreadPool(
                    producerCount + config.readerCount() + 2);
            List<Future<Void>> producers = new ArrayList<>();
            List<Future<ReaderResult>> readers = new ArrayList<>();
            Future<Void> lifecycle = null;
            Future<Void> sampler = null;
            long burstStarted = 0L;
            long lastSubmission = 0L;
            try {
                for (int producer = 0; producer < producerCount; producer++) {
                    int producerId = producer;
                    producers.add(workers.submit(() -> {
                        ready.countDown();
                        start.await();
                        lifecycleSubmitted.await();
                        for (MutationOperation operation : operations) {
                            if (operation.producer() != producerId) {
                                continue;
                            }
                            submit(engine, operation);
                        }
                        return null;
                    }));
                }
                for (int reader = 0; reader < config.readerCount(); reader++) {
                    int readerId = reader;
                    readers.add(workers.submit(() -> readLoop(
                            engine,
                            operations,
                            readerId,
                            ready,
                            start,
                            stop,
                            failure,
                            readerOperations,
                            readerChecksum)));
                }
                lifecycle = workers.submit(() -> {
                    ready.countDown();
                    start.await();
                    CompletableFuture<Void> range = engine.createIndex(
                            IndexDefinition.range(
                                    V3ProductionBenchmarkSupport.POPULARITY));
                    CompletableFuture<Void> title = engine.createIndex(
                            IndexDefinition.text(
                                    V3ProductionBenchmarkSupport.TITLE_TEXT));
                    lifecycleSubmitted.countDown();
                    range.join();
                    title.join();
                    return null;
                });
                sampler = workers.submit(() -> {
                    ready.countDown();
                    start.await();
                    while (!stop.get()) {
                        var metrics = engine.metrics();
                        int observedCapacity = queueCapacity.get();
                        if (observedCapacity != metrics.writerQueueCapacity()
                                || metrics.writerQueueDepth() < 0
                                || metrics.writerQueueDepth()
                                > metrics.writerQueueCapacity()) {
                            throw new IllegalStateException(
                                    "inconsistent writer queue telemetry");
                        }
                        queueMaximum.accumulateAndGet(
                                metrics.writerQueueDepth(), Math::max);
                        TimeUnit.MILLISECONDS.sleep(1);
                    }
                    return null;
                });

                if (!ready.await(10, TimeUnit.SECONDS)) {
                    throw new TimeoutException("burst workers did not reach barrier");
                }
                burstStarted = System.nanoTime();
                start.countDown();
                for (Future<Void> producer : producers) {
                    producer.get(config.timeoutSeconds(), TimeUnit.SECONDS);
                }
                lastSubmission = operations.stream()
                        .mapToLong(MutationOperation::submittedNanos)
                        .max()
                        .orElseThrow();

                classifyCompletions(operations, config.timeoutSeconds());
                lifecycle.get(config.timeoutSeconds(), TimeUnit.SECONDS);
                V34Phase3Support.awaitDrain(
                        engine, Duration.ofSeconds(config.timeoutSeconds()));
                long drainedAt = System.nanoTime();
                stop.set(true);

                List<ReaderResult> readerResults = new ArrayList<>();
                for (Future<ReaderResult> reader : readers) {
                    readerResults.add(reader.get(10, TimeUnit.SECONDS));
                }
                sampler.get(10, TimeUnit.SECONDS);
                Throwable workerFailure = failure.get();
                if (workerFailure != null) {
                    throw new IllegalStateException(
                            "reader observed a partial publication", workerFailure);
                }

                int expectedFailures = injectExpectedFailures(engine, config);
                V34Phase3Support.awaitDrain(
                        engine, Duration.ofSeconds(config.timeoutSeconds()));
                return validate(
                        config,
                        producerCount,
                        batchSize,
                        engine,
                        operations,
                        readerResults,
                        readerOperations.sum(),
                        readerChecksum.sum(),
                        queueMaximum.get(),
                        queueCapacity.get(),
                        initialSnapshot,
                        initialSuccessful,
                        burstStarted,
                        drainedAt,
                        drainedAt - lastSubmission,
                        expectedFailures,
                        V34Phase3Support.gcCount() - gcStarted,
                        V34Phase3Support.gcTimeMillis() - gcTimeStarted);
            } finally {
                stop.set(true);
                start.countDown();
                lifecycleSubmitted.countDown();
                workers.shutdownNow();
                workers.awaitTermination(30, TimeUnit.SECONDS);
            }
        }
    }

    private static void submit(
            io.github.patricklfdm.generalsearch.engine.SearchEngine<Long,
                    V3ProductionBenchmarkSupport.Document> engine,
            MutationOperation operation
    ) {
        long started = System.nanoTime();
        CompletableFuture<Void> completion = engine.updateAll(operation.documents());
        long submitted = System.nanoTime();
        operation.admissionNanos(submitted - started);
        operation.submittedNanos(submitted);
        operation.completion(completion);
        completion.whenComplete((ignored, failure) ->
                operation.completedNanos(System.nanoTime()));
    }

    private static ReaderResult readLoop(
            io.github.patricklfdm.generalsearch.engine.SearchEngine<Long,
                    V3ProductionBenchmarkSupport.Document> engine,
            List<MutationOperation> operations,
            int readerId,
            CountDownLatch ready,
            CountDownLatch start,
            AtomicBoolean stop,
            AtomicReference<Throwable> failure,
            LongAdder totalOperations,
            LongAdder totalChecksum
    ) throws Exception {
        V3ProductionSoak.LatencyReservoir latency =
                new V3ProductionSoak.LatencyReservoir(20_000, 34_000L + readerId);
        long checksum = 1L;
        int cursor = readerId;
        ready.countDown();
        start.await();
        try {
            while (!stop.get()) {
                MutationOperation operation = operations.get(
                        Math.floorMod(cursor++, operations.size()));
                long started = System.nanoTime();
                List<V3ProductionBenchmarkSupport.Document> matches = engine.search(
                        Query.eq(V3ProductionBenchmarkSupport.CATEGORY,
                                operation.marker()));
                latency.record(System.nanoTime() - started);
                if (!atomicObservation(matches.size(), operation.batchSize())) {
                    throw new IllegalStateException(
                            "partial batch marker=" + operation.marker()
                                    + " count=" + matches.size()
                                    + " expected=0-or-" + operation.batchSize());
                }
                checksum = 31L * checksum + matches.size();
                if (!matches.isEmpty()) {
                    checksum = 31L * checksum + matches.getFirst().id();
                }
                totalOperations.increment();
            }
        } catch (Throwable readerFailure) {
            failure.compareAndSet(null, readerFailure);
            stop.set(true);
            if (readerFailure instanceof Exception exception) {
                throw exception;
            }
            if (readerFailure instanceof Error error) {
                throw error;
            }
            throw new RuntimeException(readerFailure);
        } finally {
            totalChecksum.add(checksum);
        }
        return new ReaderResult(latency.samples(), latency.max());
    }

    static boolean atomicObservation(int observed, int batchSize) {
        return observed == 0 || observed == batchSize;
    }

    private static void classifyCompletions(
            List<MutationOperation> operations,
            int timeoutSeconds
    ) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(timeoutSeconds);
        for (MutationOperation operation : operations) {
            CompletableFuture<Void> completion = operation.completion();
            if (completion == null) {
                throw new IllegalStateException(
                        "producer omitted operation " + operation.marker());
            }
            long remaining = deadline - System.nanoTime();
            if (remaining <= 0L) {
                operation.outcome(Outcome.UNRESOLVED);
                continue;
            }
            try {
                completion.get(remaining, TimeUnit.NANOSECONDS);
                if (operation.completedNanos() == 0L) {
                    operation.completedNanos(System.nanoTime());
                }
                operation.outcome(Outcome.SUCCESS);
            } catch (TimeoutException timeout) {
                operation.outcome(Outcome.UNRESOLVED);
            } catch (Exception failed) {
                Throwable cause = V34Phase3Support.rootCause(failed);
                if (operation.completedNanos() == 0L) {
                    operation.completedNanos(System.nanoTime());
                }
                if (cause instanceof EngineRejectedExecutionException rejected
                        && rejected.reason()
                        == EngineRejectedExecutionException.Reason.QUEUE_FULL) {
                    operation.outcome(Outcome.QUEUE_REJECTED);
                } else {
                    operation.failure(cause);
                    operation.outcome(Outcome.UNEXPECTED_FAILURE);
                }
            }
        }
    }

    private static int injectExpectedFailures(
            io.github.patricklfdm.generalsearch.engine.SearchEngine<Long,
                    V3ProductionBenchmarkSupport.Document> engine,
            Config config
    ) {
        int expected = 0;
        long snapshot = engine.metrics().snapshotVersion();
        V3ProductionBenchmarkSupport.Document before = engine.get(0L);

        V3ProductionBenchmarkSupport.Document valid =
                V34Phase3Support.markedDocument(0L, 99, "invalid-missing");
        V3ProductionBenchmarkSupport.Document missing =
                V34Phase3Support.markedDocument(
                        config.documentCount() + 10L, 99, "invalid-missing");
        expectFailure(engine.updateAll(List.of(valid, missing)),
                DocumentNotFoundException.class, null);
        expected++;
        assertNoPublication(engine, snapshot, before);

        V3ProductionBenchmarkSupport.Document duplicate =
                V34Phase3Support.markedDocument(0L, 100, "invalid-duplicate");
        expectFailure(engine.updateAll(List.of(duplicate, duplicate)),
                BulkMutationException.class, BulkMutationException.Reason.DUPLICATE_ID);
        expected++;
        assertNoPublication(engine, snapshot, before);

        List<V3ProductionBenchmarkSupport.Document> oversized = new ArrayList<>(
                V34Phase3Support.MAX_BATCH_SIZE + 1);
        for (int index = 0; index <= V34Phase3Support.MAX_BATCH_SIZE; index++) {
            oversized.add(V34Phase3Support.markedDocument(
                    0L, 101, "invalid-oversized"));
        }
        expectFailure(engine.updateAll(oversized),
                BulkMutationException.class, BulkMutationException.Reason.TOO_LARGE);
        expected++;
        assertNoPublication(engine, snapshot, before);
        return expected;
    }

    private static void expectFailure(
            CompletableFuture<Void> future,
            Class<? extends Throwable> expected,
            BulkMutationException.Reason reason
    ) {
        try {
            future.join();
            throw new IllegalStateException(
                    "expected failure was reported as success: " + expected.getName());
        } catch (RuntimeException failure) {
            Throwable cause = V34Phase3Support.rootCause(failure);
            if (!expected.isInstance(cause)) {
                throw new IllegalStateException(
                        "wrong expected failure: " + cause, cause);
            }
            if (reason != null
                    && ((BulkMutationException) cause).reason() != reason) {
                throw new IllegalStateException(
                        "wrong bulk failure reason: " + cause);
            }
        }
    }

    private static void assertNoPublication(
            io.github.patricklfdm.generalsearch.engine.SearchEngine<Long,
                    V3ProductionBenchmarkSupport.Document> engine,
            long snapshot,
            V3ProductionBenchmarkSupport.Document before
    ) {
        if (engine.metrics().snapshotVersion() != snapshot
                || !before.equals(engine.get(0L))) {
            throw new IllegalStateException("failed bulk operation published state");
        }
    }

    private static CellResult validate(
            Config config,
            int producerCount,
            int batchSize,
            io.github.patricklfdm.generalsearch.engine.SearchEngine<Long,
                    V3ProductionBenchmarkSupport.Document> engine,
            List<MutationOperation> operations,
            List<ReaderResult> readers,
            long readerOperations,
            long readerChecksum,
            int queueMaximum,
            int queueCapacity,
            long initialSnapshot,
            long initialSuccessful,
            long burstStarted,
            long drainedAt,
            long drainNanos,
            int expectedFailures,
            long gcCount,
            long gcTimeMillis
    ) {
        long successfulBatches = operations.stream()
                .filter(operation -> operation.outcome() == Outcome.SUCCESS).count();
        long rejections = operations.stream()
                .filter(operation -> operation.outcome() == Outcome.QUEUE_REJECTED)
                .count();
        long unexpected = operations.stream()
                .filter(operation -> operation.outcome()
                        == Outcome.UNEXPECTED_FAILURE).count();
        long unresolved = operations.stream()
                .filter(operation -> operation.outcome() == Outcome.UNRESOLVED
                        || operation.completion() == null
                        || !operation.completion().isDone())
                .count();
        long successfulMutations = Math.multiplyExact(successfulBatches, batchSize);
        if (successfulBatches == 0L || unexpected != 0L || unresolved != 0L) {
            throw new IllegalStateException(
                    "invalid burst completion: success=" + successfulBatches
                            + ",unexpected=" + unexpected
                            + ",unresolved=" + unresolved);
        }
        if (successfulBatches + rejections != operations.size()) {
            throw new IllegalStateException("burst outcomes do not cover submissions");
        }
        if (engine.metrics().successfulMutations() - initialSuccessful
                != successfulMutations) {
            throw new IllegalStateException(
                    "writer success metrics do not match completed history");
        }
        if (queueCapacity != config.queueCapacity()
                || queueMaximum < 0 || queueMaximum > queueCapacity
                || engine.metrics().writerQueueDepth() != 0
                || engine.metrics().pendingIndexBuildCount() != 0
                || engine.metrics().mutationJournalLength() != 0) {
            throw new IllegalStateException("writer recovery telemetry is invalid");
        }
        if (engine.metrics().indexBuildsStarted() != 2L
                || engine.metrics().indexBuildsSucceeded() != 2L
                || engine.metrics().registeredIndexCount() != 4) {
            throw new IllegalStateException("dynamic indexes did not publish cleanly");
        }

        Set<Long> successfulIds = new HashSet<>();
        long oracleChecksum = 1L;
        for (MutationOperation operation : operations) {
            int expectedMatches = operation.outcome() == Outcome.SUCCESS
                    ? operation.batchSize() : 0;
            List<V3ProductionBenchmarkSupport.Document> matches = engine.search(
                    Query.eq(V3ProductionBenchmarkSupport.CATEGORY,
                            operation.marker()));
            if (matches.size() != expectedMatches) {
                throw new IllegalStateException(
                        "final marker oracle failed for " + operation.marker());
            }
            for (V3ProductionBenchmarkSupport.Document document
                    : operation.documents()) {
                V3ProductionBenchmarkSupport.Document actual = engine.get(document.id());
                V3ProductionBenchmarkSupport.Document expected =
                        operation.outcome() == Outcome.SUCCESS
                                ? document
                                : V34Phase3Support.initialDocument(document.id());
                if (!expected.equals(actual)) {
                    throw new IllegalStateException(
                            "final document oracle failed for id " + document.id());
                }
                if (operation.outcome() == Outcome.SUCCESS) {
                    successfulIds.add(document.id());
                }
                oracleChecksum = 31L * oracleChecksum + actual.hashCode();
            }
        }
        if (successfulIds.size() != successfulMutations) {
            throw new IllegalStateException("successful history contains duplicate IDs");
        }
        int titleMatches = engine.search(Query.term(
                V3ProductionBenchmarkSupport.TITLE_TEXT, "bursttoken")).size();
        int rangeMatches = engine.search(Query.between(
                V3ProductionBenchmarkSupport.POPULARITY, 0, 10_000)).size();
        if (titleMatches != successfulMutations
                || rangeMatches != config.documentCount()
                || engine.metrics().documentCount() != config.documentCount()) {
            throw new IllegalStateException("dynamic-index final oracle failed");
        }

        List<Long> admission = operations.stream()
                .map(MutationOperation::admissionNanos).toList();
        List<Long> completion = operations.stream()
                .map(operation -> operation.completedNanos()
                        - operation.submittedNanos()).toList();
        List<Long> readerLatency = new ArrayList<>();
        long readerMaximum = 0L;
        for (ReaderResult reader : readers) {
            Arrays.stream(reader.latency()).forEach(readerLatency::add);
            readerMaximum = Math.max(readerMaximum, reader.maximum());
        }
        if (readerOperations <= 0L || readerLatency.isEmpty()
                || readerChecksum == 0L || expectedFailures != 3) {
            throw new IllegalStateException("burst evidence is incomplete");
        }
        long elapsedNanos = drainedAt - burstStarted;
        long snapshotDelta = engine.metrics().snapshotVersion() - initialSnapshot;
        if (elapsedNanos <= 0L || snapshotDelta <= 0L || drainNanos < 0L) {
            throw new IllegalStateException("burst timing/publication evidence invalid");
        }
        long checksum = 31L * V34Phase3Support.corpusChecksum(
                engine, config.documentCount()) + oracleChecksum;
        checksum = 31L * checksum + readerChecksum;
        checksum = 31L * checksum + readerMaximum;
        if (checksum == 0L) {
            throw new IllegalStateException("burst checksum is zero");
        }
        double seconds = elapsedNanos / 1_000_000_000.0;
        return new CellResult(
                operations.size(),
                Math.multiplyExact((long) operations.size(), batchSize),
                successfulBatches,
                successfulMutations,
                rejections,
                expectedFailures,
                unexpected,
                unresolved,
                readerOperations,
                readerChecksum,
                queueMaximum,
                queueCapacity,
                snapshotDelta,
                snapshotDelta / seconds,
                operations.size() / seconds,
                drainNanos,
                V34Phase3Support.percentile(admission, 0.50),
                V34Phase3Support.percentile(admission, 0.95),
                V34Phase3Support.percentile(admission, 0.99),
                V34Phase3Support.percentile(completion, 0.50),
                V34Phase3Support.percentile(completion, 0.95),
                V34Phase3Support.percentile(completion, 0.99),
                V34Phase3Support.percentile(readerLatency, 0.50),
                V34Phase3Support.percentile(readerLatency, 0.95),
                V34Phase3Support.percentile(readerLatency, 0.99),
                gcCount,
                gcTimeMillis,
                checksum,
                V34Phase3Support.corpusDigest(engine, config.documentCount()));
    }

    private static List<MutationOperation> operations(
            int producerCount,
            int batchSize,
            int batchesPerProducer
    ) {
        List<MutationOperation> operations = new ArrayList<>(
                producerCount * batchesPerProducer);
        long nextId = 0L;
        for (int producer = 0; producer < producerCount; producer++) {
            for (int batch = 0; batch < batchesPerProducer; batch++) {
                String marker = String.format(
                        Locale.ROOT, "burst-p%02d-b%02d", producer, batch);
                List<V3ProductionBenchmarkSupport.Document> documents =
                        new ArrayList<>(batchSize);
                for (int item = 0; item < batchSize; item++) {
                    documents.add(V34Phase3Support.markedDocument(
                            nextId++, batch + 1, marker));
                }
                operations.add(new MutationOperation(
                        producer, batchSize, marker, List.copyOf(documents)));
            }
        }
        return List.copyOf(operations);
    }

    enum Outcome {
        PENDING,
        SUCCESS,
        QUEUE_REJECTED,
        UNEXPECTED_FAILURE,
        UNRESOLVED
    }

    static final class MutationOperation {
        private final int producer;
        private final int batchSize;
        private final String marker;
        private final List<V3ProductionBenchmarkSupport.Document> documents;
        private volatile CompletableFuture<Void> completion;
        private volatile long admissionNanos;
        private volatile long submittedNanos;
        private volatile long completedNanos;
        private volatile Outcome outcome = Outcome.PENDING;
        private volatile Throwable failure;

        private MutationOperation(
                int producer,
                int batchSize,
                String marker,
                List<V3ProductionBenchmarkSupport.Document> documents
        ) {
            this.producer = producer;
            this.batchSize = batchSize;
            this.marker = marker;
            this.documents = documents;
        }

        int producer() {
            return producer;
        }

        int batchSize() {
            return batchSize;
        }

        String marker() {
            return marker;
        }

        List<V3ProductionBenchmarkSupport.Document> documents() {
            return documents;
        }

        CompletableFuture<Void> completion() {
            return completion;
        }

        void completion(CompletableFuture<Void> value) {
            completion = value;
        }

        long admissionNanos() {
            return admissionNanos;
        }

        void admissionNanos(long value) {
            admissionNanos = value;
        }

        long submittedNanos() {
            return submittedNanos;
        }

        void submittedNanos(long value) {
            submittedNanos = value;
        }

        long completedNanos() {
            return completedNanos;
        }

        void completedNanos(long value) {
            completedNanos = value;
        }

        Outcome outcome() {
            return outcome;
        }

        void outcome(Outcome value) {
            outcome = value;
        }

        void failure(Throwable value) {
            failure = value;
        }
    }

    record ReaderResult(long[] latency, long maximum) {
        ReaderResult {
            latency = latency.clone();
        }
    }

    record CellResult(
            long submittedBatches,
            long submittedMutations,
            long successfulBatches,
            long successfulMutations,
            long queueRejections,
            long expectedFailures,
            long unexpectedFailures,
            long unresolvedFutures,
            long readerOperations,
            long readerChecksum,
            int queueMaximum,
            int queueCapacity,
            long snapshotDelta,
            double publicationRate,
            double submissionRate,
            long drainNanos,
            long admissionP50Nanos,
            long admissionP95Nanos,
            long admissionP99Nanos,
            long completionP50Nanos,
            long completionP95Nanos,
            long completionP99Nanos,
            long readerP50Nanos,
            long readerP95Nanos,
            long readerP99Nanos,
            long gcCount,
            long gcTimeMillis,
            long checksum,
            String corpusDigest
    ) {
    }

    record Config(
            List<Integer> producerCounts,
            List<Integer> batchSizes,
            int batchesPerProducer,
            int documentCount,
            int readerCount,
            int queueCapacity,
            int timeoutSeconds
    ) {
        Config {
            producerCounts = List.copyOf(producerCounts);
            batchSizes = List.copyOf(batchSizes);
            if (producerCounts.isEmpty() || batchSizes.isEmpty()) {
                throw new IllegalArgumentException(
                        "producer and batch matrices must not be empty");
            }
            requireDistinctRange(producerCounts, 1, MAX_PRODUCERS, "producers");
            requireDistinctRange(
                    batchSizes, 1, V34Phase3Support.MAX_BATCH_SIZE, "batch sizes");
            if (batchesPerProducer <= 0
                    || batchesPerProducer > MAX_BATCHES_PER_PRODUCER
                    || documentCount <= 0 || documentCount > MAX_DOCUMENTS
                    || readerCount <= 0 || readerCount > 64
                    || queueCapacity < 2 || queueCapacity > 100_000
                    || timeoutSeconds <= 0 || timeoutSeconds > 1_800) {
                throw new IllegalArgumentException(
                        "burst arguments are outside their bounded ranges");
            }
            long maximumRequired = (long) producerCounts.stream()
                    .mapToInt(Integer::intValue).max().orElseThrow()
                    * batchSizes.stream().mapToInt(Integer::intValue)
                    .max().orElseThrow()
                    * batchesPerProducer;
            if (maximumRequired > documentCount) {
                throw new IllegalArgumentException(
                        "document count does not cover the largest burst cell");
            }
        }

        static Config parse(String[] arguments) {
            Map<String, String> values = parseArguments(arguments, Set.of(
                    "--producers",
                    "--batch-sizes",
                    "--batches-per-producer",
                    "--documents",
                    "--readers",
                    "--queue-capacity",
                    "--timeout-seconds"));
            return new Config(
                    intList(values.getOrDefault("--producers", "1,4,16")),
                    intList(values.getOrDefault("--batch-sizes", "1,100,1000")),
                    integer(values, "--batches-per-producer", 4),
                    integer(values, "--documents", 64_000),
                    integer(values, "--readers", 4),
                    integer(values, "--queue-capacity", 32),
                    integer(values, "--timeout-seconds", 180));
        }

        private static void requireDistinctRange(
                List<Integer> values,
                int minimum,
                int maximum,
                String name
        ) {
            if (new HashSet<>(values).size() != values.size()
                    || values.stream().anyMatch(value ->
                    value < minimum || value > maximum)) {
                throw new IllegalArgumentException("invalid " + name + ": " + values);
            }
        }

        private static List<Integer> intList(String value) {
            try {
                return Arrays.stream(value.split(",", -1))
                        .map(Integer::parseInt)
                        .toList();
            } catch (RuntimeException invalid) {
                throw new IllegalArgumentException("invalid integer list: " + value,
                        invalid);
            }
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

        private static Map<String, String> parseArguments(
                String[] arguments,
                Set<String> allowed
        ) {
            Map<String, String> values = new HashMap<>();
            for (String argument : arguments) {
                int separator = argument.indexOf('=');
                if (separator <= 0 || separator == argument.length() - 1) {
                    throw new IllegalArgumentException(
                            "arguments must use --name=value: " + argument);
                }
                String name = argument.substring(0, separator);
                String value = argument.substring(separator + 1);
                if (!allowed.contains(name)) {
                    throw new IllegalArgumentException("unknown argument: " + name);
                }
                if (values.putIfAbsent(name, value) != null) {
                    throw new IllegalArgumentException("duplicate argument: " + name);
                }
            }
            return values;
        }
    }
}
