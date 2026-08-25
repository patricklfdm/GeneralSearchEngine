package io.github.patricklfdm.generalsearch.benchmark;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicReferenceArray;
import java.util.concurrent.atomic.LongAdder;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.engine.SnapshotSearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Opt-in P7 soak runner for concurrent structured, text, ranked and lifecycle work. */
public final class V2EngineConcurrencySoak {
    private static final Field<Article, Long> ID =
            Field.of("id", Long.class, Article::id);
    private static final Field<Article, String> CATEGORY =
            Field.of("category", String.class, Article::category);
    private static final Field<Article, Integer> SCORE =
            Field.of("score", Integer.class, Article::score);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final String[] CATEGORIES = {"guide", "reference", "news"};
    private static final String[] TERMS = {
            "java", "search", "engine", "memory", "index", "snapshot",
            "query", "ranking", "unicode", "bitmap", "thread", "stable"
    };

    private V2EngineConcurrencySoak() {}

    public static void main(String[] args) throws Exception {
        SoakConfig config = SoakConfig.parse(args);
        AtomicReferenceArray<Article> oracle =
                new AtomicReferenceArray<>(config.documentCount());
        AtomicReference<Throwable> failure = new AtomicReference<>();
        AtomicLong deadline = new AtomicLong(Long.MAX_VALUE);
        LongAdder unranked = new LongAdder();
        LongAdder ranked = new LongAdder();
        LongAdder mutations = new LongAdder();
        LongAdder indexCycles = new LongAdder();

        SearchSchema<Article, Long> schema = SearchSchema.builder(Article.class, ID)
                .field(CATEGORY)
                .field(SCORE)
                .textField(TEXT)
                .build();
        try (SnapshotSearchEngine<Long, Article> engine = new SnapshotSearchEngine<>(
                new SnapshotEngineConfig(200_000, 1_000, Duration.ofMillis(2)),
                schema,
                List.of(
                        IndexDefinition.equality(CATEGORY),
                        IndexDefinition.text(TEXT)))) {
            long loadStarted = System.nanoTime();
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
                            unranked, ranked, failure))));
                }
                for (int writer = 0; writer < config.writerCount(); writer++) {
                    int workerId = writer;
                    tasks.add(workers.submit(guard(failure, () -> runWriter(
                            engine, oracle, config, start, deadline, workerId,
                            mutations, failure))));
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
                if (failure.get() != null) {
                    throw new IllegalStateException("soak worker failed", failure.get());
                }
                verifyFinalState(engine, oracle);
                System.out.printf(Locale.US,
                        "documents=%,d readers=%d writers=%d duration=%,.2f s "
                                + "load=%,.2f s unranked=%,d ranked=%,d mutations=%,d "
                                + "index_cycles=%,d version=%d status=PASS%n",
                        config.documentCount(), config.readerCount(), config.writerCount(),
                        runSeconds, loadSeconds, unranked.sum(), ranked.sum(),
                        mutations.sum(), indexCycles.sum(),
                        engine.metrics().snapshotVersion());
            } finally {
                workers.shutdownNow();
                workers.awaitTermination(10, TimeUnit.SECONDS);
            }
        }
    }

    private static void load(
            SnapshotSearchEngine<Long, Article> engine,
            AtomicReferenceArray<Article> oracle,
            SoakConfig config
    ) {
        List<Article> batch = new ArrayList<>(1_000);
        for (int slot = 0; slot < config.documentCount(); slot++) {
            Article article = article(slot, 0, config.seed());
            oracle.set(slot, article);
            batch.add(article);
            if (batch.size() == 1_000) {
                engine.addAll(batch).join();
                batch.clear();
            }
        }
        engine.addAll(batch).join();
    }

    private static void runReader(
            SnapshotSearchEngine<Long, Article> engine,
            SoakConfig config,
            CountDownLatch start,
            AtomicLong deadline,
            int workerId,
            LongAdder unranked,
            LongAdder ranked,
            AtomicReference<Throwable> failure
    ) throws InterruptedException {
        start.await();
        Random random = new Random(config.seed() + 10_000L + workerId);
        while (keepRunning(deadline, failure)) {
            Query<Article> filter = randomFilter(random);
            if (random.nextBoolean()) {
                Query<Article> query = random.nextBoolean()
                        ? filter
                        : Query.and(filter, Query.term(TEXT, randomTerm(random)));
                List<Article> result = engine.search(query);
                Set<Long> ids = new HashSet<>();
                for (Article article : result) {
                    if (!query.matches(article) || !ids.add(article.id())) {
                        throw new AssertionError("invalid unranked result");
                    }
                }
                unranked.increment();
            } else {
                RankedSearchRequest<Article> request = RankedSearchRequest.filtered(
                        TextScoringQuery.of(TEXT, randomTerm(random) + " "
                                + randomTerm(random)),
                        filter,
                        25);
                List<SearchHit<Article>> hits = engine.searchTopK(request);
                Set<Long> ids = new HashSet<>();
                double previous = Double.POSITIVE_INFINITY;
                for (SearchHit<Article> hit : hits) {
                    if (!filter.matches(hit.document())
                            || !(hit.score() > 0.0)
                            || !Double.isFinite(hit.score())
                            || hit.score() > previous
                            || !ids.add(hit.document().id())) {
                        throw new AssertionError("invalid ranked result");
                    }
                    previous = hit.score();
                }
                ranked.increment();
            }
        }
    }

    private static void runWriter(
            SnapshotSearchEngine<Long, Article> engine,
            AtomicReferenceArray<Article> oracle,
            SoakConfig config,
            CountDownLatch start,
            AtomicLong deadline,
            int workerId,
            LongAdder mutations,
            AtomicReference<Throwable> failure
    ) throws InterruptedException {
        start.await();
        Random random = new Random(config.seed() + 20_000L + workerId);
        int revision = 1;
        int ownedSlots = (config.documentCount() + config.writerCount() - 1)
                / config.writerCount();
        while (keepRunning(deadline, failure)) {
            int slot = random.nextInt(ownedSlots) * config.writerCount() + workerId;
            if (slot >= config.documentCount()) {
                continue;
            }
            Article current = oracle.get(slot);
            if (current != null && random.nextInt(20) == 0) {
                engine.remove(current.id()).join();
                oracle.set(slot, null);
            } else {
                Article replacement = article(slot, revision++, config.seed());
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
            SnapshotSearchEngine<Long, Article> engine,
            CountDownLatch start,
            AtomicLong deadline,
            LongAdder cycles,
            AtomicReference<Throwable> failure
    ) throws InterruptedException {
        start.await();
        while (keepRunning(deadline, failure)) {
            engine.createIndex(IndexDefinition.range(SCORE)).join();
            engine.dropIndex(SCORE.name()).join();
            cycles.increment();
        }
    }

    private static void verifyFinalState(
            SnapshotSearchEngine<Long, Article> engine,
            AtomicReferenceArray<Article> oracle
    ) {
        Set<Article> expected = new HashSet<>();
        for (int slot = 0; slot < oracle.length(); slot++) {
            Article article = oracle.get(slot);
            if (article != null) {
                expected.add(article);
            }
        }
        Set<Article> actual = new HashSet<>(engine.search(Query.matchAll()));
        if (actual.size() != engine.search(Query.matchAll()).size()
                || !expected.equals(actual)) {
            throw new AssertionError("final exhaustive state mismatch");
        }
    }

    private static Query<Article> randomFilter(Random random) {
        String category = CATEGORIES[random.nextInt(CATEGORIES.length)];
        return switch (random.nextInt(4)) {
            case 0 -> Query.eq(CATEGORY, category);
            case 1 -> Query.between(SCORE, 100, 800);
            case 2 -> Query.and(
                    Query.eq(CATEGORY, category), Query.between(SCORE, 200, 900));
            default -> Query.not(Query.eq(CATEGORY, category));
        };
    }

    private static String randomTerm(Random random) {
        return TERMS[random.nextInt(TERMS.length)];
    }

    private static Article article(int slot, int revision, long seed) {
        long mixed = seed + slot * 31L + revision * 17L;
        StringBuilder body = new StringBuilder();
        for (int token = 0; token < 6; token++) {
            if (!body.isEmpty()) {
                body.append(' ');
            }
            body.append(TERMS[(int) Math.floorMod(mixed + token * 7L, TERMS.length)]);
        }
        return new Article(
                (long) slot,
                CATEGORIES[(int) Math.floorMod(mixed, CATEGORIES.length)],
                (int) Math.floorMod(mixed * 13L, 1_001L),
                body.toString());
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

    private record Article(long id, String category, int score, String body) {}

    private record SoakConfig(
            int documentCount,
            int readerCount,
            int writerCount,
            int seconds,
            long seed
    ) {
        private SoakConfig {
            if (documentCount <= 0 || readerCount <= 0
                    || writerCount <= 0 || seconds <= 0) {
                throw new IllegalArgumentException(
                        "documents, readers, writers and seconds must be positive");
            }
        }

        private static SoakConfig parse(String[] args) {
            int defaultReaders = Math.max(2, Math.min(
                    8, Runtime.getRuntime().availableProcessors() - 2));
            return new SoakConfig(
                    intArg(args, "--documents", 100_000),
                    intArg(args, "--readers", defaultReaders),
                    intArg(args, "--writers", 2),
                    intArg(args, "--seconds", 120),
                    longArg(args, "--seed", 7_007L));
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
