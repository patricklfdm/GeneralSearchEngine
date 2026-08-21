package org.example.generalsearch.benchmark;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicReferenceArray;
import java.util.concurrent.atomic.LongAdder;
import org.example.generalsearch.engine.SnapshotEngineConfig;
import org.example.generalsearch.engine.SnapshotUpdateEngine;
import org.example.generalsearch.engine.metrics.SearchEngineMetrics;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.example.generalsearch.query.Query;

/**
 * Opt-in concurrency stress runner. It is deliberately not a JUnit test so the
 * normal Maven test lifecycle remains fast and deterministic.
 */
public final class ProductEngineConcurrencyStress {
    private ProductEngineConcurrencyStress() {}

    public static void main(String[] args) throws Exception {
        StressConfig config = StressConfig.parse(args);
        AtomicReferenceArray<Product> oracle =
                new AtomicReferenceArray<>(config.productCount());
        LongAdder queries = new LongAdder();
        LongAdder mutations = new LongAdder();
        LongAdder indexCycles = new LongAdder();
        LongAdder checksum = new LongAdder();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        AtomicLong deadline = new AtomicLong(Long.MAX_VALUE);

        long loadStarted = System.nanoTime();
        try (SnapshotUpdateEngine engine = new SnapshotUpdateEngine(
                new SnapshotEngineConfig(200_000, 1_000, Duration.ofMillis(2)))) {
            load(engine, oracle, config);
            double loadSeconds = elapsedSeconds(loadStarted);

            int workerCount = config.readerCount() + config.writerCount() + 1;
            ExecutorService workers = Executors.newFixedThreadPool(workerCount);
            CountDownLatch start = new CountDownLatch(1);
            List<Future<?>> tasks = new ArrayList<>(workerCount);
            try {
                for (int reader = 0; reader < config.readerCount(); reader++) {
                    int workerId = reader;
                    tasks.add(workers.submit(guard(failure, () -> runReader(
                            engine, config, start, deadline, workerId,
                            queries, checksum, failure))));
                }
                for (int writer = 0; writer < config.writerCount(); writer++) {
                    int workerId = writer;
                    tasks.add(workers.submit(guard(failure, () -> runWriter(
                            engine, oracle, config, start, deadline,
                            workerId, mutations, failure))));
                }
                tasks.add(workers.submit(guard(failure, () -> runIndexManager(
                        engine, start, deadline, indexCycles, failure))));

                long runStarted = System.nanoTime();
                deadline.set(runStarted + TimeUnit.SECONDS.toNanos(config.seconds()));
                start.countDown();
                for (Future<?> task : tasks) {
                    task.get();
                }
                double runSeconds = elapsedSeconds(runStarted);

                Throwable workerFailure = failure.get();
                if (workerFailure != null) {
                    throw new IllegalStateException("stress worker failed", workerFailure);
                }
                verifyFinalState(engine, oracle);
                SearchEngineMetrics metrics = engine.metrics();

                System.out.printf(Locale.US,
                        "products=%,d readers=%d writers=%d duration=%,.2f s "
                                + "load=%,.2f s queries=%,d (%,.0f q/s) "
                                + "mutations=%,d (%,.0f op/s) index_cycles=%,d "
                                + "checksum=%d status=PASS%n",
                        config.productCount(),
                        config.readerCount(),
                        config.writerCount(),
                        runSeconds,
                        loadSeconds,
                        queries.sum(),
                        queries.sum() / runSeconds,
                        mutations.sum(),
                        mutations.sum() / runSeconds,
                        indexCycles.sum(),
                        checksum.sum());
                System.out.printf(Locale.US,
                        "snapshot_version=%d documents=%,d indexes=%d queue=%d/%d "
                                + "journal=%d mutations_ok=%,d mutations_failed=%,d "
                                + "index_builds=%d/%d/%d/%d%n",
                        metrics.snapshotVersion(),
                        metrics.documentCount(),
                        metrics.registeredIndexCount(),
                        metrics.writerQueueDepth(),
                        metrics.writerQueueCapacity(),
                        metrics.mutationJournalLength(),
                        metrics.successfulMutations(),
                        metrics.failedMutations(),
                        metrics.indexBuildsStarted(),
                        metrics.indexBuildsSucceeded(),
                        metrics.indexBuildsFailed(),
                        metrics.indexBuildsCancelled());
            } finally {
                workers.shutdownNow();
                workers.awaitTermination(10, TimeUnit.SECONDS);
            }
        }
    }

    private static void load(
            SnapshotUpdateEngine engine,
            AtomicReferenceArray<Product> oracle,
            StressConfig config
    ) {
        List<CompletableFuture<Void>> pending = new ArrayList<>(1_000);
        for (int slot = 0; slot < config.productCount(); slot++) {
            Product product = product(slot, 0, config.seed());
            oracle.set(slot, product);
            pending.add(engine.add(product));
            if (pending.size() == 1_000) {
                CompletableFuture.allOf(pending.toArray(CompletableFuture[]::new)).join();
                pending.clear();
            }
        }
        CompletableFuture.allOf(pending.toArray(CompletableFuture[]::new)).join();
    }

    private static void runReader(
            SnapshotUpdateEngine engine,
            StressConfig config,
            CountDownLatch start,
            AtomicLong deadline,
            int workerId,
            LongAdder queries,
            LongAdder checksum,
            AtomicReference<Throwable> failure
    ) throws InterruptedException {
        start.await();
        Random random = new Random(config.seed() + 10_000L + workerId);
        while (keepRunning(deadline, failure)) {
            Query<Product> query = randomQuery(random, config.productCount());
            List<Product> result = engine.search(query);
            Set<String> ids = new HashSet<>(result.size());
            for (Product product : result) {
                if (!query.matches(product)) {
                    throw new AssertionError(
                            "query returned a non-matching product: " + product.id());
                }
                if (!ids.add(product.id())) {
                    throw new AssertionError(
                            "query returned a duplicate product: " + product.id());
                }
            }
            queries.increment();
            checksum.add(result.size());
        }
    }

    private static void runWriter(
            SnapshotUpdateEngine engine,
            AtomicReferenceArray<Product> oracle,
            StressConfig config,
            CountDownLatch start,
            AtomicLong deadline,
            int workerId,
            LongAdder mutations,
            AtomicReference<Throwable> failure
    ) throws InterruptedException {
        start.await();
        Random random = new Random(config.seed() + 20_000L + workerId);
        int revision = 1;
        int ownedSlots = (config.productCount() + config.writerCount() - 1)
                / config.writerCount();
        while (keepRunning(deadline, failure)) {
            int ownedSlot = random.nextInt(ownedSlots);
            int slot = ownedSlot * config.writerCount() + workerId;
            if (slot >= config.productCount()) {
                continue;
            }
            Product current = oracle.get(slot);
            if (current != null && random.nextInt(20) == 0) {
                engine.remove(current.id()).join();
                oracle.set(slot, null);
            } else {
                Product replacement = product(slot, revision++, config.seed());
                if (current == null) {
                    engine.add(replacement).join();
                } else {
                    engine.update(replacement).join();
                }
                oracle.set(slot, replacement);
            }
            mutations.increment();
        }
    }

    private static void runIndexManager(
            SnapshotUpdateEngine engine,
            CountDownLatch start,
            AtomicLong deadline,
            LongAdder indexCycles,
            AtomicReference<Throwable> failure
    ) throws InterruptedException {
        start.await();
        while (keepRunning(deadline, failure)) {
            CompletableFuture<Void> range =
                    engine.createIndex(IndexDefinition.range(ProductFields.RATING));
            CompletableFuture<Void> equality =
                    engine.createIndex(IndexDefinition.equality(ProductFields.RATING));
            CompletableFuture.allOf(range, equality).join();
            engine.dropIndex(ProductFields.RATING.name()).join();
            indexCycles.increment();
        }
    }

    private static void verifyFinalState(
            SnapshotUpdateEngine engine,
            AtomicReferenceArray<Product> oracle
    ) {
        List<Query<Product>> queries = List.of(
                Query.matchAll(),
                Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS),
                Query.eq(ProductFields.PRIME, true),
                Query.between(ProductFields.PRICE, 100.0, 800.0),
                Query.between(ProductFields.RATING, 2.0, 4.5),
                Query.prefix(ProductFields.NAME, "Product 1"),
                Query.and(
                        Query.eq(ProductFields.CATEGORY, Category.BOOKS),
                        Query.between(ProductFields.RATING, 3.0, 5.0)),
                Query.not(Query.eq(ProductFields.CATEGORY, Category.CLOTHING))
        );
        for (Query<Product> query : queries) {
            Set<String> expected = new HashSet<>();
            for (int slot = 0; slot < oracle.length(); slot++) {
                Product product = oracle.get(slot);
                if (product != null && query.matches(product)) {
                    expected.add(product.id());
                }
            }
            Set<String> actual = new HashSet<>();
            List<Product> result = engine.search(query);
            result.forEach(product -> actual.add(product.id()));
            if (actual.size() != result.size()) {
                throw new AssertionError("final result contains duplicate document IDs");
            }
            if (!expected.equals(actual)) {
                throw new AssertionError(
                        "final differential verification failed: expected="
                                + expected.size() + ", actual=" + actual.size());
            }
        }
    }

    private static Product product(int slot, int revision, long seed) {
        long mixed = seed + slot * 31L + revision * 17L;
        return new Product(
                "p" + slot,
                (revision % 3 == 0 ? "Updated " : "Product ") + slot,
                Category.values()[(int) Math.floorMod(mixed, Category.values().length)],
                Math.floorMod(mixed * 13L, 100_000L) / 100.0,
                (mixed & 1) == 0,
                1.0 + Math.floorMod(mixed * 7L, 400L) / 100.0
        );
    }

    private static Query<Product> randomQuery(Random random, int productCount) {
        Category category =
                Category.values()[random.nextInt(Category.values().length)];
        return switch (random.nextInt(8)) {
            case 0 -> Query.eq(ProductFields.CATEGORY, category);
            case 1 -> Query.eq(ProductFields.PRIME, random.nextBoolean());
            case 2 -> Query.between(ProductFields.PRICE, 100.0, 750.0);
            case 3 -> Query.between(ProductFields.RATING, 2.0, 4.5);
            case 4 -> Query.prefix(
                    ProductFields.NAME,
                    (random.nextBoolean() ? "Product " : "Updated ")
                            + random.nextInt(productCount));
            case 5 -> Query.and(
                    Query.eq(ProductFields.CATEGORY, category),
                    Query.between(ProductFields.RATING, 2.5, 5.0));
            case 6 -> Query.or(
                    Query.eq(ProductFields.PRIME, true),
                    Query.between(ProductFields.PRICE, 0.0, 50.0));
            default -> Query.not(Query.eq(ProductFields.CATEGORY, category));
        };
    }

    private static Runnable guard(
            AtomicReference<Throwable> failure,
            InterruptibleRunnable action
    ) {
        return () -> {
            try {
                action.run();
            } catch (Throwable workerFailure) {
                failure.compareAndSet(null, workerFailure);
            }
        };
    }

    private static boolean keepRunning(
            AtomicLong deadline,
            AtomicReference<Throwable> failure
    ) {
        return failure.get() == null && System.nanoTime() < deadline.get();
    }

    private static double elapsedSeconds(long started) {
        return (System.nanoTime() - started) / 1_000_000_000.0;
    }

    @FunctionalInterface
    private interface InterruptibleRunnable {
        void run() throws Exception;
    }

    private record StressConfig(
            int productCount,
            int readerCount,
            int writerCount,
            int seconds,
            long seed
    ) {
        private StressConfig {
            if (productCount <= 0 || readerCount <= 0
                    || writerCount <= 0 || seconds <= 0) {
                throw new IllegalArgumentException(
                        "products, readers, writers and seconds must be positive");
            }
        }

        private static StressConfig parse(String[] args) {
            int defaultReaders = Math.max(2, Math.min(
                    8, Runtime.getRuntime().availableProcessors() - 2));
            return new StressConfig(
                    intArg(args, "--products", 100_000),
                    intArg(args, "--readers", defaultReaders),
                    intArg(args, "--writers", 2),
                    intArg(args, "--seconds", 60),
                    longArg(args, "--seed", 42L)
            );
        }

        private static int intArg(String[] args, String name, int fallback) {
            long value = longArg(args, name, fallback);
            if (value > Integer.MAX_VALUE) {
                throw new IllegalArgumentException(name + " is too large: " + value);
            }
            return (int) value;
        }

        private static long longArg(String[] args, String name, long fallback) {
            String prefix = name + "=";
            for (String arg : args) {
                if (arg.startsWith(prefix)) {
                    return Long.parseLong(arg.substring(prefix.length()));
                }
            }
            return fallback;
        }
    }
}
