package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;

/** Shared, benchmark-only controls for the V3.4 Phase 3 diagnostics. */
final class V34Phase3Support {
    static final int MAX_BATCH_SIZE = 1_000;
    static final V3ProductionBenchmarkSupport.CorpusProfile PROFILE =
            new V3ProductionBenchmarkSupport.CorpusProfile(false, false, 8, 1);

    private V34Phase3Support() {
    }

    static Fixture createFixture(int documentCount, int queueCapacity) {
        SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine =
                SearchEngine.builder(
                                V3ProductionBenchmarkSupport.Document.class,
                                V3ProductionBenchmarkSupport.ID)
                        .config(new SnapshotEngineConfig(
                                queueCapacity,
                                MAX_BATCH_SIZE,
                                Duration.ofMillis(2)))
                        .index(IndexDefinition.equality(
                                V3ProductionBenchmarkSupport.CATEGORY))
                        .field(V3ProductionBenchmarkSupport.POPULARITY)
                        .textField(V3ProductionBenchmarkSupport.TITLE_TEXT)
                        .index(IndexDefinition.text(
                                V3ProductionBenchmarkSupport.BODY_TEXT))
                        .build();
        List<V3ProductionBenchmarkSupport.Document> batch = new ArrayList<>(
                MAX_BATCH_SIZE);
        for (int id = 0; id < documentCount; id++) {
            batch.add(initialDocument(id));
            if (batch.size() == MAX_BATCH_SIZE) {
                engine.addAll(batch).join();
                batch.clear();
            }
        }
        if (!batch.isEmpty()) {
            engine.addAll(batch).join();
        }
        return new Fixture(engine, documentCount);
    }

    static V3ProductionBenchmarkSupport.Document initialDocument(long id) {
        return V3ProductionBenchmarkSupport.replacement(id, 0, PROFILE);
    }

    static V3ProductionBenchmarkSupport.Document markedDocument(
            long id,
            int revision,
            String marker
    ) {
        V3ProductionBenchmarkSupport.Document base =
                V3ProductionBenchmarkSupport.replacement(id, revision, PROFILE);
        return new V3ProductionBenchmarkSupport.Document(
                id,
                marker,
                base.popularity(),
                "bursttoken " + marker + " " + base.title(),
                base.body(),
                base.tags(),
                base.summary());
    }

    static long corpusChecksum(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            int documentCount
    ) {
        long checksum = 1L;
        for (long id = 0; id < documentCount; id++) {
            V3ProductionBenchmarkSupport.Document document = engine.get(id);
            if (document == null) {
                throw new IllegalStateException("missing document " + id);
            }
            checksum = 31L * checksum + document.id();
            checksum = 31L * checksum + document.category().hashCode();
            checksum = 31L * checksum + document.popularity();
            checksum = 31L * checksum + document.title().hashCode();
            checksum = 31L * checksum + document.body().hashCode();
        }
        return checksum;
    }

    static String corpusDigest(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            int documentCount
    ) {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
        for (long id = 0; id < documentCount; id++) {
            V3ProductionBenchmarkSupport.Document document = engine.get(id);
            if (document == null) {
                throw new IllegalStateException("missing document " + id);
            }
            update(digest, Long.toString(document.id()));
            update(digest, document.category());
            update(digest, Integer.toString(document.popularity()));
            update(digest, document.title());
            update(digest, document.body());
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    static long hitChecksum(
            List<? extends SearchHit<V3ProductionBenchmarkSupport.Document>> hits
    ) {
        long checksum = hits.size();
        for (SearchHit<V3ProductionBenchmarkSupport.Document> hit : hits) {
            checksum = 31L * checksum + hit.document().id();
            checksum = 31L * checksum
                    + Double.doubleToRawLongBits(hit.score());
        }
        return checksum;
    }

    static Throwable rootCause(Throwable failure) {
        Throwable current = failure;
        while ((current instanceof CompletionException
                || current instanceof ExecutionException)
                && current.getCause() != null) {
            current = current.getCause();
        }
        return current;
    }

    static void awaitDrain(
            SearchEngine<?, ?> engine,
            Duration timeout
    ) throws InterruptedException {
        long deadline = System.nanoTime() + timeout.toNanos();
        while (System.nanoTime() < deadline) {
            var metrics = engine.metrics();
            if (metrics.writerQueueDepth() == 0
                    && metrics.pendingIndexBuildCount() == 0
                    && metrics.mutationJournalLength() == 0) {
                return;
            }
            TimeUnit.MILLISECONDS.sleep(2);
        }
        var metrics = engine.metrics();
        throw new IllegalStateException(
                "writer did not drain: queue=" + metrics.writerQueueDepth()
                        + ",builds=" + metrics.pendingIndexBuildCount()
                        + ",journal=" + metrics.mutationJournalLength());
    }

    static long percentile(List<Long> values, double percentile) {
        if (values.isEmpty()) {
            return 0L;
        }
        long[] sorted = values.stream().mapToLong(Long::longValue).sorted().toArray();
        int index = (int) Math.ceil(percentile * sorted.length) - 1;
        return sorted[Math.max(0, Math.min(index, sorted.length - 1))];
    }

    static long gcCount() {
        return ManagementFactory.getGarbageCollectorMXBeans().stream()
                .mapToLong(GarbageCollectorMXBean::getCollectionCount)
                .filter(value -> value >= 0L)
                .sum();
    }

    static long gcTimeMillis() {
        return ManagementFactory.getGarbageCollectorMXBeans().stream()
                .mapToLong(GarbageCollectorMXBean::getCollectionTime)
                .filter(value -> value >= 0L)
                .sum();
    }

    private static void update(MessageDigest digest, String value) {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        digest.update((byte) (encoded.length >>> 24));
        digest.update((byte) (encoded.length >>> 16));
        digest.update((byte) (encoded.length >>> 8));
        digest.update((byte) encoded.length);
        digest.update(encoded);
    }

    record Fixture(
            SearchEngine<Long, V3ProductionBenchmarkSupport.Document> engine,
            int documentCount
    ) implements AutoCloseable {
        @Override
        public void close() {
            engine.close();
        }
    }
}
