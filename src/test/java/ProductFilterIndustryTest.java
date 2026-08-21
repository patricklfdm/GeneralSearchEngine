import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.LockSupport;
import java.util.concurrent.locks.ReentrantReadWriteLock;

/**
 * Correctness and performance harness for ProductFilterIndustry.
 *
 * This deliberately avoids external benchmark libraries so it can be compiled
 * and run next to ProductFilterIndustry.java.  It is not a replacement for
 * JMH; the warm-up, repetitions, checksums, and identical pre-generated work
 * make it useful for an engineering comparison of the implementations here.
 *
 * Run:
 *   javac -d out src/ProductFilterIndustry.java src/ProductFilterIndustryTest.java
 *   java -Xms2g -Xmx2g -cp out ProductFilterIndustryTest
 *
 * Useful options:
 *   --smoke                 small/short correctness run
 *   --full                  broader concurrency matrix
 *   --products=100000
 *   --readers=8
 *   --writers=4
 *   --warmup-seconds=5
 *   --measure-seconds=15
 *   --repetitions=3
 *   --seed=42
 */
public class ProductFilterIndustryTest extends ProductFilterIndustry {

    private static final long CHECKSUM_MULTIPLIER = 0x9E3779B97F4A7C15L;
    private static final int MAX_IN_FLIGHT_PER_PRODUCER = 64;
    private static final CompletableFuture<Void> COMPLETED_WRITE =
            CompletableFuture.completedFuture(null);
    private static volatile long BLACK_HOLE;

    record Config(
            int productCount,
            int queryCount,
            int mutationCount,
            int indexWarmupQueries,
            int indexRepetitions,
            int readers,
            int writers,
            int warmupSeconds,
            int measureSeconds,
            int concurrencyRepetitions,
            long seed,
            boolean full
    ) {
        static Config parse(String[] args) {
            boolean smoke = hasFlag(args, "--smoke");
            boolean full = hasFlag(args, "--full");
            int cpu = Runtime.getRuntime().availableProcessors();

            Config defaults = smoke
                    ? new Config(2_000, 2_000, 1_000, 500, 2,
                    2, 2, 1, 2, 1, 42L, false)
                    : new Config(100_000, 100_000, 50_000, 20_000, 5,
                    Math.max(4, Math.min(16, cpu - 2)), 4,
                    5, 15, 3, 42L, full);

            return new Config(
                    intArg(args, "--products", defaults.productCount),
                    intArg(args, "--queries", defaults.queryCount),
                    intArg(args, "--mutations", defaults.mutationCount),
                    intArg(args, "--index-warmup", defaults.indexWarmupQueries),
                    intArg(args, "--index-repetitions", defaults.indexRepetitions),
                    intArg(args, "--readers", defaults.readers),
                    intArg(args, "--writers", defaults.writers),
                    intArg(args, "--warmup-seconds", defaults.warmupSeconds),
                    intArg(args, "--measure-seconds", defaults.measureSeconds),
                    intArg(args, "--repetitions", defaults.concurrencyRepetitions),
                    longArg(args, "--seed", defaults.seed),
                    full
            );
        }
    }

    record Signature(long count, long idSum, long idXor) {
        Signature add(int docId) {
            long mixed = mix(docId);
            return new Signature(count + 1, idSum + mixed, idXor ^ mixed);
        }
    }

    enum MutationKind { ADD, UPDATE, REMOVE }

    record Mutation(MutationKind kind, int docId, Product product) {}

    record MutationWorkload(List<Mutation> mutations, Product[] finalState) {}

    interface Backend {
        String name();
        Signature search(ProductFilter filter);
        Product get(int docId);
        void apply(Mutation mutation);
    }

    interface ConcurrentEngine extends AutoCloseable {
        String name();
        Signature search(ProductFilter filter);
        Product get(int docId);
        CompletableFuture<Void> updateAsync(int docId, Product product);
        void resetStats();
        long retryCount();
        String extraStats();
        @Override void close();
    }

    public static void main(String[] args) throws Exception {
        Config config = Config.parse(args);
        printConfiguration(config);

        Product[] products = generateProducts(config.productCount, config.seed);
        List<ProductFilter> queries = generateQueries(config.queryCount, config.seed + 1);
        MutationWorkload mutationWorkload = generateMutations(
                products, config.mutationCount, config.seed + 2);

        runIndexComparison(config, products, queries, mutationWorkload);
        runConcurrencyComparison(config, products, queries);

        System.out.println("\nALL PRODUCT FILTER TESTS PASSED");
        System.out.println("blackHole=" + BLACK_HOLE);
    }

    // ---------------------------------------------------------------------
    // Index comparison
    // ---------------------------------------------------------------------

    private static void runIndexComparison(
            Config config,
            Product[] products,
            List<ProductFilter> queries,
            MutationWorkload mutationWorkload
    ) {
        System.out.println("\n============================================================");
        System.out.println("INDEX COMPARISON");
        System.out.println("============================================================");

        List<java.util.function.Function<Product[], Backend>> factories = List.of(
                FullScanBackend::new,
                HashSetBackend::new,
                BitSetBackend::new,
                PersistentTreeBackend::new
        );

        List<Signature> oracle = new ArrayList<>(queries.size());
        Backend oracleBackend = new FullScanBackend(products);
        for (ProductFilter query : queries) {
            oracle.add(oracleBackend.search(query));
        }

        for (java.util.function.Function<Product[], Backend> factory : factories) {
            forceGc();
            long beforeMemory = usedMemory();
            long buildStart = System.nanoTime();
            Backend backend = factory.apply(products);
            long buildNs = System.nanoTime() - buildStart;
            long approximateBytes = Math.max(0, usedMemory() - beforeMemory);

            verifyQueries(backend, queries, oracle, "initial");
            warmUp(backend, queries, config.indexWarmupQueries);

            List<Double> queryTimesMs = new ArrayList<>();
            for (int repetition = 0; repetition < config.indexRepetitions; repetition++) {
                long started = System.nanoTime();
                Signature aggregate = runQueries(backend, queries);
                long elapsed = System.nanoTime() - started;
                BLACK_HOLE ^= aggregate.idXor ^ aggregate.idSum ^ aggregate.count;
                queryTimesMs.add(elapsed / 1_000_000.0);
            }

            List<Double> mutationTimesMs = new ArrayList<>();
            for (int repetition = 0; repetition < config.indexRepetitions; repetition++) {
                Backend mutationBackend = factory.apply(products);
                long started = System.nanoTime();
                for (Mutation mutation : mutationWorkload.mutations) {
                    mutationBackend.apply(mutation);
                }
                long elapsed = System.nanoTime() - started;
                mutationTimesMs.add(elapsed / 1_000_000.0);
                verifyFinalState(mutationBackend, mutationWorkload.finalState);
            }

            System.out.printf(Locale.US,
                    "%-25s build=%8.2f ms  approxHeap=%8.2f MiB  " +
                            "queryMedian=%8.2f ms (%10.0f q/s)  mutationMedian=%8.2f ms (%10.0f op/s)%n",
                    backend.name(), buildNs / 1_000_000.0,
                    approximateBytes / 1024.0 / 1024.0,
                    median(queryTimesMs),
                    config.queryCount / (median(queryTimesMs) / 1000.0),
                    median(mutationTimesMs),
                    config.mutationCount / (median(mutationTimesMs) / 1000.0));
        }
    }

    private static final class FullScanBackend implements Backend {
        private final Product[] products;

        FullScanBackend(Product[] source) {
            this.products = source.clone();
        }

        public String name() { return "full-scan"; }

        public Signature search(ProductFilter filter) {
            Signature result = new Signature(0, 0, 0);
            for (int docId = 0; docId < products.length; docId++) {
                Product product = products[docId];
                if (product != null && filter.matches(product)) {
                    result = result.add(docId);
                }
            }
            return result;
        }

        public Product get(int docId) { return products[docId]; }

        public void apply(Mutation mutation) {
            products[mutation.docId] = mutation.kind == MutationKind.REMOVE
                    ? null : mutation.product;
        }
    }

    private static final class HashSetBackend implements Backend {
        private final Product[] products;
        private final Set<Integer> active = new HashSet<>();
        private final EnumMap<Category, Set<Integer>> categories = new EnumMap<>(Category.class);
        private final Map<Boolean, Set<Integer>> primes = new HashMap<>();

        HashSetBackend(Product[] source) {
            products = source.clone();
            for (Category category : Category.values()) categories.put(category, new HashSet<>());
            primes.put(true, new HashSet<>());
            primes.put(false, new HashSet<>());
            for (int docId = 0; docId < products.length; docId++) {
                if (products[docId] != null) addToIndexes(products[docId], docId);
            }
        }

        public String name() { return "hashset-index"; }

        public Signature search(ProductFilter filter) {
            Set<Integer> candidates = candidates(filter);
            Iterable<Integer> source = candidates == null ? active : candidates;
            Signature result = new Signature(0, 0, 0);
            for (int docId : source) {
                Product product = products[docId];
                if (product != null && filter.matches(product)) result = result.add(docId);
            }
            return result;
        }

        public Product get(int docId) { return products[docId]; }

        public void apply(Mutation mutation) {
            int docId = mutation.docId;
            Product old = products[docId];
            if (old != null) removeFromIndexes(old, docId);
            products[docId] = mutation.kind == MutationKind.REMOVE ? null : mutation.product;
            if (products[docId] != null) addToIndexes(products[docId], docId);
        }

        private void addToIndexes(Product product, int docId) {
            active.add(docId);
            categories.get(product.category()).add(docId);
            primes.get(product.prime()).add(docId);
        }

        private void removeFromIndexes(Product product, int docId) {
            active.remove(docId);
            categories.get(product.category()).remove(docId);
            primes.get(product.prime()).remove(docId);
        }

        private Set<Integer> candidates(ProductFilter filter) {
            if (filter instanceof CategoryFilter f) return categories.get(f.category());
            if (filter instanceof PrimeFilter f) return primes.get(f.requirePrime());
            if (filter instanceof NotFilter) return null;
            if (filter instanceof AndFilter f) {
                Set<Integer> result = null;
                for (ProductFilter child : f.filters()) {
                    Set<Integer> childSet = candidates(child);
                    if (childSet == null) continue;
                    if (result == null) result = new HashSet<>(childSet);
                    else result.retainAll(childSet);
                    if (result.isEmpty()) break;
                }
                return result;
            }
            if (filter instanceof OrFilter f) {
                if (f.filters().isEmpty()) return Set.of();
                Set<Integer> result = new HashSet<>();
                for (ProductFilter child : f.filters()) {
                    Set<Integer> childSet = candidates(child);
                    if (childSet == null) return null;
                    result.addAll(childSet);
                }
                return result;
            }
            return null;
        }
    }

    private static final class BitSetBackend implements Backend {
        private final Product[] products;
        private final BitSet active = new BitSet();
        private final EnumMap<Category, BitSet> categories = new EnumMap<>(Category.class);
        private final Map<Boolean, BitSet> primes = new HashMap<>();

        BitSetBackend(Product[] source) {
            products = source.clone();
            for (Category category : Category.values()) categories.put(category, new BitSet());
            primes.put(true, new BitSet());
            primes.put(false, new BitSet());
            for (int docId = 0; docId < products.length; docId++) {
                if (products[docId] != null) addToIndexes(products[docId], docId);
            }
        }

        public String name() { return "mutable-bitset-index"; }

        public Signature search(ProductFilter filter) {
            BitSet candidates = candidates(filter);
            BitSet source = candidates == null ? active : candidates;
            Signature result = new Signature(0, 0, 0);
            for (int docId = source.nextSetBit(0); docId >= 0;
                 docId = source.nextSetBit(docId + 1)) {
                Product product = products[docId];
                if (product != null && filter.matches(product)) result = result.add(docId);
            }
            return result;
        }

        public Product get(int docId) { return products[docId]; }

        public void apply(Mutation mutation) {
            int docId = mutation.docId;
            Product old = products[docId];
            if (old != null) removeFromIndexes(old, docId);
            products[docId] = mutation.kind == MutationKind.REMOVE ? null : mutation.product;
            if (products[docId] != null) addToIndexes(products[docId], docId);
        }

        private void addToIndexes(Product product, int docId) {
            active.set(docId);
            categories.get(product.category()).set(docId);
            primes.get(product.prime()).set(docId);
        }

        private void removeFromIndexes(Product product, int docId) {
            active.clear(docId);
            categories.get(product.category()).clear(docId);
            primes.get(product.prime()).clear(docId);
        }

        private BitSet candidates(ProductFilter filter) {
            if (filter instanceof CategoryFilter f) return categories.get(f.category());
            if (filter instanceof PrimeFilter f) return primes.get(f.requirePrime());
            if (filter instanceof NotFilter) return null;
            if (filter instanceof AndFilter f) {
                BitSet result = null;
                for (ProductFilter child : f.filters()) {
                    BitSet childSet = candidates(child);
                    if (childSet == null) continue;
                    if (result == null) result = (BitSet) childSet.clone();
                    else result.and(childSet);
                    if (result.isEmpty()) break;
                }
                return result;
            }
            if (filter instanceof OrFilter f) {
                if (f.filters().isEmpty()) return new BitSet();
                BitSet result = new BitSet();
                for (ProductFilter child : f.filters()) {
                    BitSet childSet = candidates(child);
                    if (childSet == null) return null;
                    result.or(childSet);
                }
                return result;
            }
            return null;
        }
    }

    private static final class PersistentTreeBackend implements Backend {
        private CatalogSnapshot snapshot = new CatalogSnapshot();

        PersistentTreeBackend(Product[] source) {
            CatalogSnapshotBuilder builder = new CatalogSnapshotBuilder(snapshot);
            for (int docId = 0; docId < source.length; docId++) {
                // ProductTable requires contiguous initial docIds.
                builder.add(docId, source[docId]);
            }
            snapshot = builder.build();
        }

        public String name() { return "persistent-tree-bitmap"; }

        public Signature search(ProductFilter filter) {
            return searchSnapshot(snapshot, filter);
        }

        public Product get(int docId) { return snapshot.get(docId); }

        public void apply(Mutation mutation) {
            snapshot = switch (mutation.kind) {
                case ADD -> snapshot.add(mutation.docId, mutation.product);
                case UPDATE -> snapshot.update(mutation.docId, mutation.product);
                case REMOVE -> snapshot.remove(mutation.docId);
            };
        }
    }

    // ---------------------------------------------------------------------
    // Concurrent comparison
    // ---------------------------------------------------------------------

    private static void runConcurrencyComparison(
            Config config,
            Product[] products,
            List<ProductFilter> queries
    ) throws Exception {
        System.out.println("\n============================================================");
        System.out.println("READ-HEAVY CONCURRENCY COMPARISON");
        System.out.println("============================================================");

        List<Double> writePercentages = config.full
                ? List.of(0.5, 1.0, 5.0)
                : List.of(1.0);
        List<Integer> readerCounts = config.full
                ? distinctInts(1, 4, 8, 16, config.readers)
                : List.of(config.readers);

        for (double writePercentage : writePercentages) {
            for (int readers : readerCounts) {
                System.out.printf(Locale.US,
                        "\n--- readers=%d writers=%d target read/write=%.1f/%.1f ---%n",
                        readers, config.writers, 100.0 - writePercentage, writePercentage);

                for (int repetition = 1; repetition <= config.concurrencyRepetitions; repetition++) {
                    runOneConcurrentEngine(config, products, queries, readers,
                            writePercentage, repetition,
                            () -> new ReadWriteLockEngine(products));
                    runOneConcurrentEngine(config, products, queries, readers,
                            writePercentage, repetition,
                            () -> new CasSnapshotEngine(products));
                    runOneConcurrentEngine(config, products, queries, readers,
                            writePercentage, repetition,
                            () -> new QueueSnapshotEngine(products, 1_000, 5));
                }
            }
        }
    }

    private static void runOneConcurrentEngine(
            Config config,
            Product[] products,
            List<ProductFilter> queries,
            int readers,
            double writePercentage,
            int repetition,
            java.util.function.Supplier<ConcurrentEngine> factory
    ) throws Exception {
        try (ConcurrentEngine engine = factory.get()) {
            runConcurrentPhase(engine, products.length, queries, readers, config.writers,
                    writePercentage, config.warmupSeconds, config.seed + repetition, false);

            // runConcurrentPhase drains every in-flight future before returning.
            // Reset here so engine counters describe only the measured phase.
            engine.resetStats();
            GcSnapshot gcBefore = gcSnapshot();
            ConcurrentResult result = runConcurrentPhase(
                    engine, products.length, queries, readers, config.writers,
                    writePercentage, config.measureSeconds,
                    config.seed + 10_000L * repetition, true);
            GcSnapshot gcAfter = gcSnapshot();

            verifyConcurrentEngine(engine, queries, products.length);

            System.out.printf(Locale.US,
                    "rep=%d %-24s reads=%10.0f/s writes=%9.0f/s actualWrite=%5.2f%% " +
                            "read[p50=%6.1f p95=%6.1f p99=%6.1f us] " +
                            "write[p50=%6.1f p95=%6.1f p99=%6.1f us] " +
                            "retries=%d gc=%d/%dms %s%n",
                    repetition, engine.name(),
                    result.readOps / result.seconds,
                    result.writeOps / result.seconds,
                    100.0 * result.writeOps / (result.readOps + result.writeOps),
                    percentileMicros(result.readSamples, 50),
                    percentileMicros(result.readSamples, 95),
                    percentileMicros(result.readSamples, 99),
                    percentileMicros(result.writeSamples, 50),
                    percentileMicros(result.writeSamples, 95),
                    percentileMicros(result.writeSamples, 99),
                    engine.retryCount(),
                    gcAfter.collections - gcBefore.collections,
                    gcAfter.timeMs - gcBefore.timeMs,
                    engine.extraStats());
        }
    }

    record ConcurrentResult(
            long readOps,
            long writeOps,
            double seconds,
            List<Long> readSamples,
            List<Long> writeSamples
    ) {}

    record PendingWrite(
            CompletableFuture<Void> completion,
            long submittedAtNs,
            boolean latencySample
    ) {}

    private static ConcurrentResult runConcurrentPhase(
            ConcurrentEngine engine,
            int productCount,
            List<ProductFilter> queries,
            int readerThreads,
            int writerThreads,
            double writePercentage,
            int seconds,
            long seed,
            boolean sampleLatency
    ) throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(readerThreads + writerThreads);
        CountDownLatch ready = new CountDownLatch(readerThreads + writerThreads);
        CountDownLatch start = new CountDownLatch(1);
        AtomicBoolean stop = new AtomicBoolean();
        LongAdder reads = new LongAdder();
        LongAdder writes = new LongAdder();
        AtomicLong submittedWrites = new AtomicLong();
        ConcurrentLinkedQueue<Long> readSamples = new ConcurrentLinkedQueue<>();
        ConcurrentLinkedQueue<Long> writeSamples = new ConcurrentLinkedQueue<>();
        AtomicReference<Throwable> failure = new AtomicReference<>();
        List<Future<?>> futures = new ArrayList<>();

        for (int reader = 0; reader < readerThreads; reader++) {
            final int id = reader;
            futures.add(pool.submit(() -> {
                Random random = new Random(seed + id);
                long local = 0;
                long localChecksum = 0;
                ready.countDown();
                start.await();
                while (!stop.get() && failure.get() == null) {
                    ProductFilter filter = queries.get(random.nextInt(queries.size()));
                    long before = sampleLatency && local % 100 == 0 ? System.nanoTime() : 0;
                    Signature signature = engine.search(filter);
                    if (before != 0) readSamples.add(System.nanoTime() - before);
                    // Keep consumption thread-local during the timed section. A shared
                    // volatile write per query would itself become a read bottleneck.
                    localChecksum ^= signature.idXor ^ signature.idSum ^ signature.count;
                    reads.increment();
                    local++;
                }
                BLACK_HOLE ^= localChecksum;
                return null;
            }));
        }

        for (int writer = 0; writer < writerThreads; writer++) {
            final int id = writer;
            futures.add(pool.submit(() -> {
                Random random = new Random(seed + 100_000 + id);
                long local = 0;
                ArrayDeque<PendingWrite> inFlight = new ArrayDeque<>();
                ready.countDown();
                start.await();
                try {
                    while (!stop.get() && failure.get() == null) {
                        while (completeHead(inFlight, false, writes, writeSamples)) {
                            // Reap every already-completed write without blocking.
                        }

                        if (inFlight.size() >= MAX_IN_FLIGHT_PER_PRODUCER) {
                            completeHead(inFlight, true, writes, writeSamples);
                            continue;
                        }

                        if (!reserveWriteSlot(submittedWrites, reads, writePercentage)) {
                            LockSupport.parkNanos(50_000);
                            continue;
                        }

                        // Disjoint writer partitions are the reproducible,
                        // low-contention baseline.
                        int partitionStart = id * productCount / writerThreads;
                        int partitionEnd = (id + 1) * productCount / writerThreads;
                        int docId = partitionStart + random.nextInt(partitionEnd - partitionStart);
                        Product old = engine.get(docId);
                        if (old == null) {
                            throw new IllegalStateException("Concurrent test product disappeared");
                        }
                        Product updated = concurrentUpdate(old, random);

                        boolean latencySample = sampleLatency && local % 100 == 0;
                        long submittedAt = latencySample ? System.nanoTime() : 0;
                        CompletableFuture<Void> completion = engine.updateAsync(docId, updated);
                        inFlight.addLast(new PendingWrite(
                                completion, submittedAt, latencySample));
                        local++;
                    }
                } finally {
                    // No warm-up or measured mutation may leak into the next phase.
                    while (!inFlight.isEmpty()) {
                        completeHead(inFlight, true, writes, writeSamples);
                    }
                }
                return null;
            }));
        }

        ready.await();
        long started = System.nanoTime();
        start.countDown();
        LockSupport.parkNanos(TimeUnit.SECONDS.toNanos(seconds));
        stop.set(true);

        pool.shutdown();
        if (!pool.awaitTermination(Math.max(10, seconds), TimeUnit.SECONDS)) {
            pool.shutdownNow();
            throw new AssertionError("Concurrent workers did not terminate");
        }
        for (Future<?> future : futures) {
            try {
                future.get();
            } catch (ExecutionException e) {
                failure.compareAndSet(null, e.getCause());
            }
        }
        if (failure.get() != null) throw new AssertionError("Concurrent phase failed", failure.get());

        double elapsedSeconds = (System.nanoTime() - started) / 1_000_000_000.0;
        return new ConcurrentResult(reads.sum(), writes.sum(), elapsedSeconds,
                new ArrayList<>(readSamples), new ArrayList<>(writeSamples));
    }

    private static boolean reserveWriteSlot(
            AtomicLong submittedWrites,
            LongAdder reads,
            double writePercentage
    ) {
        long allowed = (long) Math.floor(
                reads.sum() * writePercentage / (100.0 - writePercentage));
        while (true) {
            long submitted = submittedWrites.get();
            if (submitted >= allowed) return false;
            if (submittedWrites.compareAndSet(submitted, submitted + 1)) return true;
        }
    }

    private static boolean completeHead(
            ArrayDeque<PendingWrite> inFlight,
            boolean wait,
            LongAdder completedWrites,
            ConcurrentLinkedQueue<Long> writeSamples
    ) {
        PendingWrite pending = inFlight.peekFirst();
        if (pending == null || (!wait && !pending.completion.isDone())) return false;
        pending.completion.join();
        inFlight.removeFirst();
        if (pending.latencySample) {
            writeSamples.add(System.nanoTime() - pending.submittedAtNs);
        }
        completedWrites.increment();
        return true;
    }

    private static final class ReadWriteLockEngine implements ConcurrentEngine {
        private final Product[] products;
        private final BitSet active = new BitSet();
        private final EnumMap<Category, BitSet> categories = new EnumMap<>(Category.class);
        private final Map<Boolean, BitSet> primes = new HashMap<>();
        private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();

        ReadWriteLockEngine(Product[] source) {
            products = source.clone();
            for (Category category : Category.values()) categories.put(category, new BitSet());
            primes.put(true, new BitSet());
            primes.put(false, new BitSet());
            for (int docId = 0; docId < products.length; docId++) addIndex(products[docId], docId);
        }

        public String name() { return "read-write-lock"; }

        public Signature search(ProductFilter filter) {
            lock.readLock().lock();
            try {
                BitSet candidate = mutableCandidates(filter, active, categories, primes);
                BitSet source = candidate == null ? active : candidate;
                Signature result = new Signature(0, 0, 0);
                for (int docId = source.nextSetBit(0); docId >= 0;
                     docId = source.nextSetBit(docId + 1)) {
                    Product product = products[docId];
                    if (product != null && filter.matches(product)) result = result.add(docId);
                }
                return result;
            } finally {
                lock.readLock().unlock();
            }
        }

        public Product get(int docId) {
            lock.readLock().lock();
            try { return products[docId]; }
            finally { lock.readLock().unlock(); }
        }

        public CompletableFuture<Void> updateAsync(int docId, Product product) {
            lock.writeLock().lock();
            try {
                Product old = products[docId];
                removeIndex(old, docId);
                products[docId] = product;
                addIndex(product, docId);
            } finally {
                lock.writeLock().unlock();
            }
            return COMPLETED_WRITE;
        }

        private void addIndex(Product product, int docId) {
            active.set(docId);
            categories.get(product.category()).set(docId);
            primes.get(product.prime()).set(docId);
        }

        private void removeIndex(Product product, int docId) {
            active.clear(docId);
            categories.get(product.category()).clear(docId);
            primes.get(product.prime()).clear(docId);
        }

        public void resetStats() {}
        public long retryCount() { return 0; }
        public String extraStats() { return ""; }
        public void close() {}
    }

    private static final class CasSnapshotEngine implements ConcurrentEngine {
        private final AtomicReference<CatalogSnapshot> current;
        private final LongAdder retries = new LongAdder();

        CasSnapshotEngine(Product[] products) {
            current = new AtomicReference<>(buildSnapshot(products));
        }

        public String name() { return "multi-writer-cas-snapshot"; }
        public Signature search(ProductFilter filter) { return searchSnapshot(current.get(), filter); }
        public Product get(int docId) { return current.get().get(docId); }

        public CompletableFuture<Void> updateAsync(int docId, Product product) {
            while (true) {
                CatalogSnapshot old = current.get();
                CatalogSnapshot next = old.update(docId, product);
                if (current.compareAndSet(old, next)) return COMPLETED_WRITE;
                retries.increment();
            }
        }

        public void resetStats() { retries.reset(); }
        public long retryCount() { return retries.sum(); }
        public String extraStats() { return ""; }
        public void close() {}
    }

    private static final class QueueSnapshotEngine implements ConcurrentEngine {
        private final AtomicReference<CatalogSnapshot> current;
        private final BlockingQueue<QueuedUpdate> queue = new LinkedBlockingQueue<>(100_000);
        private final Thread writer;
        private final int maxBatchSize;
        private final long maxBatchWaitMs;
        private final LongAdder batches = new LongAdder();
        private final LongAdder batchItems = new LongAdder();
        private final AtomicInteger maximumQueueDepth = new AtomicInteger();
        private volatile boolean running = true;

        record QueuedUpdate(int docId, Product product, CompletableFuture<Void> completion) {}

        QueueSnapshotEngine(Product[] products, int maxBatchSize, long maxBatchWaitMs) {
            this.current = new AtomicReference<>(buildSnapshot(products));
            this.maxBatchSize = maxBatchSize;
            this.maxBatchWaitMs = maxBatchWaitMs;
            this.writer = new Thread(this::writerLoop, "product-filter-test-writer");
            this.writer.start();
        }

        public String name() { return "queue-single-writer-snapshot"; }
        public Signature search(ProductFilter filter) { return searchSnapshot(current.get(), filter); }
        public Product get(int docId) { return current.get().get(docId); }

        public CompletableFuture<Void> updateAsync(int docId, Product product) {
            CompletableFuture<Void> completion = new CompletableFuture<>();
            QueuedUpdate update = new QueuedUpdate(docId, product, completion);
            if (!running || !queue.offer(update)) {
                throw new RejectedExecutionException("snapshot update queue unavailable");
            }
            maximumQueueDepth.accumulateAndGet(queue.size(), Math::max);
            return completion;
        }

        private void writerLoop() {
            while (running || !queue.isEmpty()) {
                try {
                    QueuedUpdate first = queue.poll(100, TimeUnit.MILLISECONDS);
                    if (first == null) continue;
                    List<QueuedUpdate> batch = new ArrayList<>(maxBatchSize);
                    batch.add(first);
                    long deadline = System.nanoTime()
                            + TimeUnit.MILLISECONDS.toNanos(maxBatchWaitMs);
                    while (batch.size() < maxBatchSize) {
                        queue.drainTo(batch, maxBatchSize - batch.size());
                        if (batch.size() >= maxBatchSize) break;
                        long remaining = deadline - System.nanoTime();
                        if (remaining <= 0) break;
                        QueuedUpdate next = queue.poll(remaining, TimeUnit.NANOSECONDS);
                        if (next == null) break;
                        batch.add(next);
                    }
                    processBatch(batch);
                } catch (InterruptedException e) {
                    if (running) Thread.currentThread().interrupt();
                }
            }
        }

        private void processBatch(List<QueuedUpdate> batch) {
            CatalogSnapshotBuilder builder = new CatalogSnapshotBuilder(current.get());
            List<QueuedUpdate> successful = new ArrayList<>(batch.size());
            for (QueuedUpdate update : batch) {
                try {
                    builder.update(update.docId, update.product);
                    successful.add(update);
                } catch (Throwable t) {
                    update.completion.completeExceptionally(t);
                }
            }
            if (!successful.isEmpty()) current.set(builder.build());
            batches.increment();
            batchItems.add(successful.size());
            for (QueuedUpdate update : successful) update.completion.complete(null);
        }

        public void resetStats() {
            if (!queue.isEmpty()) {
                throw new IllegalStateException("Cannot reset stats with queued updates");
            }
            batches.reset();
            batchItems.reset();
            maximumQueueDepth.set(0);
        }

        public long retryCount() { return 0; }

        public String extraStats() {
            long count = batches.sum();
            double average = count == 0 ? 0 : batchItems.sum() / (double) count;
            return String.format(Locale.US, "avgBatch=%.1f maxQueue=%d", average,
                    maximumQueueDepth.get());
        }

        public void close() {
            running = false;
            writer.interrupt();
            try { writer.join(10_000); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            QueuedUpdate update;
            while ((update = queue.poll()) != null) {
                update.completion.completeExceptionally(
                        new IllegalStateException("queue engine closed"));
            }
        }
    }

    // ---------------------------------------------------------------------
    // Shared query/index helpers
    // ---------------------------------------------------------------------

    private static Signature searchSnapshot(CatalogSnapshot snapshot, ProductFilter filter) {
        ImmutableBitmap candidates = snapshot.getCandidates(filter)
                .map(CandidateResult::bitmap)
                .orElse(snapshot.activeProducts());
        long[] values = new long[3];
        candidates.forEachSetBit(docId -> {
            Product product = snapshot.get(docId);
            if (product != null && filter.matches(product)) {
                long mixed = mix(docId);
                values[0]++;
                values[1] += mixed;
                values[2] ^= mixed;
            }
        });
        return new Signature(values[0], values[1], values[2]);
    }

    private static BitSet mutableCandidates(
            ProductFilter filter,
            BitSet active,
            EnumMap<Category, BitSet> categories,
            Map<Boolean, BitSet> primes
    ) {
        if (filter instanceof CategoryFilter f) return categories.get(f.category());
        if (filter instanceof PrimeFilter f) return primes.get(f.requirePrime());
        if (filter instanceof NotFilter) return null;
        if (filter instanceof AndFilter f) {
            BitSet result = null;
            for (ProductFilter child : f.filters()) {
                BitSet childSet = mutableCandidates(child, active, categories, primes);
                if (childSet == null) continue;
                if (result == null) result = (BitSet) childSet.clone();
                else result.and(childSet);
                if (result.isEmpty()) break;
            }
            return result;
        }
        if (filter instanceof OrFilter f) {
            if (f.filters().isEmpty()) return new BitSet();
            BitSet result = new BitSet();
            for (ProductFilter child : f.filters()) {
                BitSet childSet = mutableCandidates(child, active, categories, primes);
                if (childSet == null) return null;
                result.or(childSet);
            }
            return result;
        }
        return null;
    }

    private static CatalogSnapshot buildSnapshot(Product[] products) {
        CatalogSnapshotBuilder builder = new CatalogSnapshotBuilder(new CatalogSnapshot());
        for (int docId = 0; docId < products.length; docId++) builder.add(docId, products[docId]);
        return builder.build();
    }

    // ---------------------------------------------------------------------
    // Workload generation and validation
    // ---------------------------------------------------------------------

    private static Product[] generateProducts(int count, long seed) {
        Random random = new Random(seed);
        Product[] products = new Product[count];
        for (int docId = 0; docId < count; docId++) products[docId] = randomProduct(docId, random);
        return products;
    }

    private static Product randomProduct(int docId, Random random) {
        Category[] categories = Category.values();
        return new Product(
                "P" + docId,
                "Product-" + docId + "-" + random.nextInt(10_000),
                categories[random.nextInt(categories.length)],
                0.01 + random.nextInt(200_000) / 100.0,
                random.nextBoolean(),
                1.0 + random.nextDouble() * 4.0);
    }

    private static Product updatedProduct(Product old, Random random) {
        Category[] categories = Category.values();
        int type = random.nextInt(100);
        if (type < 30) {
            return new Product(old.id(), old.name(), categories[random.nextInt(categories.length)],
                    old.price(), old.prime(), old.rating());
        }
        if (type < 55) {
            return new Product(old.id(), old.name(), old.category(), old.price(),
                    !old.prime(), old.rating());
        }
        if (type < 75) {
            return new Product(old.id(), old.name(), categories[random.nextInt(categories.length)],
                    old.price(), !old.prime(), old.rating());
        }
        if (type < 90) {
            return new Product(old.id(), old.name(), old.category(), old.price(),
                    old.prime(), 1.0 + random.nextDouble() * 4.0);
        }
        int docId = Integer.parseInt(old.id().substring(1));
        return randomProduct(docId, random);
    }

    private static Product concurrentUpdate(Product old, Random random) {
        // Always touches an indexed field so each writer mode performs real index work.
        if (random.nextBoolean()) {
            Category next = Category.values()[(old.category().ordinal() + 1) % Category.values().length];
            return new Product(old.id(), old.name(), next, old.price(), old.prime(), old.rating());
        }
        return new Product(old.id(), old.name(), old.category(), old.price(),
                !old.prime(), old.rating());
    }

    private static List<ProductFilter> generateQueries(int count, long seed) {
        Random random = new Random(seed);
        Category[] categories = Category.values();
        List<ProductFilter> result = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            int choice = random.nextInt(100);
            Category c1 = categories[random.nextInt(categories.length)];
            Category c2 = categories[random.nextInt(categories.length)];
            ProductFilter filter;
            if (choice < 20) filter = new CategoryFilter(c1);
            else if (choice < 35) filter = new PrimeFilter(random.nextBoolean());
            else if (choice < 60) filter = new AndFilter(List.of(
                        new CategoryFilter(c1), new PrimeFilter(random.nextBoolean())));
            else if (choice < 70) filter = new OrFilter(List.of(
                        new CategoryFilter(c1), new CategoryFilter(c2)));
            else if (choice < 80) filter = new OrFilter(List.of(
                        new CategoryFilter(c1), new PrimeFilter(random.nextBoolean())));
            else if (choice < 90) filter = new AndFilter(List.of(
                        new CategoryFilter(c1), new PrimeFilter(random.nextBoolean()),
                        new RatingFilter(3.5 + random.nextDouble() * 1.5)));
            else if (choice < 95) filter = new RatingFilter(3.0 + random.nextDouble() * 2.0);
            else filter = new AndFilter(List.of(
                        new OrFilter(List.of(new CategoryFilter(c1), new CategoryFilter(c2))),
                        new PrimeFilter(random.nextBoolean())));
            result.add(filter);
        }
        return List.copyOf(result);
    }

    private static MutationWorkload generateMutations(Product[] initial, int count, long seed) {
        Random random = new Random(seed);
        Product[] state = initial.clone();
        ArrayList<Integer> inactive = new ArrayList<>();
        List<Mutation> mutations = new ArrayList<>(count);

        for (int i = 0; i < count; i++) {
            int action = random.nextInt(100);
            if (action < 15 && !inactive.isEmpty()) {
                int slot = random.nextInt(inactive.size());
                int docId = inactive.get(slot);
                inactive.set(slot, inactive.get(inactive.size() - 1));
                inactive.remove(inactive.size() - 1);
                Product product = randomProduct(docId, random);
                state[docId] = product;
                mutations.add(new Mutation(MutationKind.ADD, docId, product));
            } else if (action < 30) {
                int docId = findActive(state, random);
                state[docId] = null;
                inactive.add(docId);
                mutations.add(new Mutation(MutationKind.REMOVE, docId, null));
            } else {
                int docId = findActive(state, random);
                Product product = updatedProduct(state[docId], random);
                state[docId] = product;
                mutations.add(new Mutation(MutationKind.UPDATE, docId, product));
            }
        }
        return new MutationWorkload(List.copyOf(mutations), state);
    }

    private static int findActive(Product[] products, Random random) {
        while (true) {
            int docId = random.nextInt(products.length);
            if (products[docId] != null) return docId;
        }
    }

    private static void verifyQueries(
            Backend backend,
            List<ProductFilter> queries,
            List<Signature> expected,
            String phase
    ) {
        for (int i = 0; i < queries.size(); i++) {
            Signature actual = backend.search(queries.get(i));
            if (!actual.equals(expected.get(i))) {
                throw new AssertionError(backend.name() + " " + phase +
                        " query mismatch at " + i + " filter=" + queries.get(i) +
                        " expected=" + expected.get(i) + " actual=" + actual);
            }
        }
    }

    private static void verifyFinalState(Backend backend, Product[] expected) {
        for (int docId = 0; docId < expected.length; docId++) {
            if (!Objects.equals(expected[docId], backend.get(docId))) {
                throw new AssertionError(backend.name() + " state mismatch at docId=" + docId);
            }
        }
    }

    private static void verifyConcurrentEngine(
            ConcurrentEngine engine,
            List<ProductFilter> queries,
            int productCount
    ) {
        Product[] state = new Product[productCount];
        for (int docId = 0; docId < productCount; docId++) state[docId] = engine.get(docId);
        FullScanBackend oracle = new FullScanBackend(state);
        int checks = Math.min(100, queries.size());
        for (int i = 0; i < checks; i++) {
            ProductFilter query = queries.get(i * queries.size() / checks);
            Signature expected = oracle.search(query);
            Signature actual = engine.search(query);
            if (!actual.equals(expected)) {
                throw new AssertionError(engine.name() + " final query mismatch: " + query +
                        " expected=" + expected + " actual=" + actual);
            }
        }
    }

    // ---------------------------------------------------------------------
    // Measurement helpers
    // ---------------------------------------------------------------------

    private static void warmUp(Backend backend, List<ProductFilter> queries, int count) {
        Signature aggregate = new Signature(0, 0, 0);
        for (int i = 0; i < count; i++) {
            Signature current = backend.search(queries.get(i % queries.size()));
            aggregate = new Signature(aggregate.count + current.count,
                    aggregate.idSum + current.idSum, aggregate.idXor ^ current.idXor);
        }
        BLACK_HOLE ^= aggregate.count ^ aggregate.idSum ^ aggregate.idXor;
    }

    private static Signature runQueries(Backend backend, List<ProductFilter> queries) {
        long count = 0, sum = 0, xor = 0;
        for (ProductFilter query : queries) {
            Signature current = backend.search(query);
            count += current.count;
            sum += current.idSum;
            xor ^= current.idXor;
        }
        return new Signature(count, sum, xor);
    }

    private static long mix(long value) {
        value += CHECKSUM_MULTIPLIER;
        value = (value ^ (value >>> 30)) * 0xBF58476D1CE4E5B9L;
        value = (value ^ (value >>> 27)) * 0x94D049BB133111EBL;
        return value ^ (value >>> 31);
    }

    private static double percentileMicros(List<Long> samples, int percentile) {
        if (samples.isEmpty()) return Double.NaN;
        samples.sort(Long::compare);
        int index = (int) Math.ceil(percentile / 100.0 * samples.size()) - 1;
        return samples.get(Math.max(0, index)) / 1_000.0;
    }

    private static double median(List<Double> values) {
        List<Double> sorted = new ArrayList<>(values);
        sorted.sort(Double::compare);
        int middle = sorted.size() / 2;
        return sorted.size() % 2 == 1
                ? sorted.get(middle)
                : (sorted.get(middle - 1) + sorted.get(middle)) / 2.0;
    }

    record GcSnapshot(long collections, long timeMs) {}

    private static GcSnapshot gcSnapshot() {
        long collections = 0, time = 0;
        for (GarbageCollectorMXBean bean : ManagementFactory.getGarbageCollectorMXBeans()) {
            if (bean.getCollectionCount() >= 0) collections += bean.getCollectionCount();
            if (bean.getCollectionTime() >= 0) time += bean.getCollectionTime();
        }
        return new GcSnapshot(collections, time);
    }

    private static long usedMemory() {
        Runtime runtime = Runtime.getRuntime();
        return runtime.totalMemory() - runtime.freeMemory();
    }

    private static void forceGc() {
        System.gc();
        LockSupport.parkNanos(TimeUnit.MILLISECONDS.toNanos(100));
    }

    private static List<Integer> distinctInts(int... values) {
        return List.copyOf(new TreeSet<>(Arrays.stream(values).boxed().toList()));
    }

    private static boolean hasFlag(String[] args, String flag) {
        for (String arg : args) if (arg.equals(flag)) return true;
        return false;
    }

    private static int intArg(String[] args, String name, int fallback) {
        return Integer.parseInt(stringArg(args, name, Integer.toString(fallback)));
    }

    private static long longArg(String[] args, String name, long fallback) {
        return Long.parseLong(stringArg(args, name, Long.toString(fallback)));
    }

    private static String stringArg(String[] args, String name, String fallback) {
        String prefix = name + "=";
        for (String arg : args) if (arg.startsWith(prefix)) return arg.substring(prefix.length());
        return fallback;
    }

    private static void printConfiguration(Config c) {
        System.out.println("ProductFilterIndustry benchmark configuration");
        System.out.printf(Locale.US,
                "products=%,d queries=%,d mutations=%,d seed=%d%n",
                c.productCount, c.queryCount, c.mutationCount, c.seed);
        System.out.printf(Locale.US,
                "indexWarmup=%,d indexRepetitions=%d readers=%d writers=%d " +
                        "concurrencyWarmup=%ds measure=%ds repetitions=%d inFlightPerWriter=%d full=%s%n",
                c.indexWarmupQueries, c.indexRepetitions, c.readers, c.writers,
                c.warmupSeconds, c.measureSeconds, c.concurrencyRepetitions,
                MAX_IN_FLIGHT_PER_PRODUCER, c.full);
        System.out.println("Note: approximate heap deltas are directional, not precise object-size measurements.");
    }
}
