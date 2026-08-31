package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;

/** One independent-JVM cold construction and index-build diagnostic. */
public final class V34ColdBuildProbe {
    private static final Field<V34DiagnosticCorpus.Document, Integer> ID =
            Field.of("id", Integer.class, V34DiagnosticCorpus.Document::id);
    private static final Field<V34DiagnosticCorpus.Document, String> CATEGORY =
            Field.of("category", String.class,
                    V34DiagnosticCorpus.Document::category);
    private static final Field<V34DiagnosticCorpus.Document, String>
            DYNAMIC_CATEGORY = Field.of(
                    "dynamicCategory",
                    String.class,
                    V34DiagnosticCorpus.Document::dynamicCategory
            );
    private static final Field<V34DiagnosticCorpus.Document, String> PRIMARY =
            Field.of("primary", String.class,
                    V34DiagnosticCorpus.Document::primary);
    private static final Field<V34DiagnosticCorpus.Document, String> SECONDARY =
            Field.of("secondary", String.class,
                    V34DiagnosticCorpus.Document::secondary);
    private static final TextField<V34DiagnosticCorpus.Document> PRIMARY_TEXT =
            TextField.of(PRIMARY, Analyzer.simple());
    private static final TextField<V34DiagnosticCorpus.Document> SECONDARY_TEXT =
            TextField.of(SECONDARY, Analyzer.simple());

    private V34ColdBuildProbe() {
    }

    public static void main(String[] arguments) {
        Config config = Config.parse(arguments);
        long processStart = System.nanoTime();
        long previous = processStart;
        emit(Checkpoint.PROCESS_START, processStart, previous, null, 0L);

        SearchEngine<Integer, V34DiagnosticCorpus.Document> engine = null;
        long checksum = 0L;
        String corpusDigest = "unavailable";
        try {
            engine = SearchEngine.builder(V34DiagnosticCorpus.Document.class, ID)
                    .field(CATEGORY)
                    .field(DYNAMIC_CATEGORY)
                    .textField(PRIMARY_TEXT)
                    .textField(SECONDARY_TEXT)
                    .build();
            previous = emit(
                    Checkpoint.ENGINE_CONSTRUCTED,
                    processStart,
                    previous,
                    engine,
                    checksum
            );

            List<V34DiagnosticCorpus.Document> documents =
                    V34DiagnosticCorpus.generate(new V34DiagnosticCorpus.Config(
                            config.documentCount(),
                            config.tokensPerField(),
                            config.seed(),
                            V34DiagnosticCorpus.Axis.SPARSE_VOCABULARY
                    ));
            corpusDigest = V34DiagnosticCorpus.digest(documents);
            checksum = corpusDigest.hashCode();
            previous = emit(
                    Checkpoint.CORPUS_GENERATED,
                    processStart,
                    previous,
                    engine,
                    checksum
            );

            for (int start = 0; start < documents.size(); start += config.batchSize()) {
                engine.addAll(documents.subList(
                        start,
                        Math.min(start + config.batchSize(), documents.size())
                )).join();
            }
            previous = emit(
                    Checkpoint.INITIAL_DOCUMENTS_LOADED,
                    processStart,
                    previous,
                    engine,
                    checksum
            );

            engine.createIndex(IndexDefinition.equality(CATEGORY)).join();
            previous = emit(
                    Checkpoint.INITIAL_STRUCTURED_INDEX_AVAILABLE,
                    processStart,
                    previous,
                    engine,
                    checksum
            );

            engine.createIndex(IndexDefinition.text(PRIMARY_TEXT)).join();
            previous = emit(
                    Checkpoint.INITIAL_TEXT_INDEX_AVAILABLE,
                    processStart,
                    previous,
                    engine,
                    checksum
            );

            previous = emit(
                    Checkpoint.READY_TO_SEARCH,
                    processStart,
                    previous,
                    engine,
                    checksum
            );

            List<SearchHit<V34DiagnosticCorpus.Document>> hits = engine.search(
                    SearchRequest.<V34DiagnosticCorpus.Document>builder()
                            .query(SearchQueries.text(PRIMARY_TEXT, "anchor"))
                            .filter(Query.eq(CATEGORY, "eligible"))
                            .limit(Math.min(100, (config.documentCount() + 1) / 2))
                            .build()
            ).hits();
            checksum = hitChecksum(hits);
            if (hits.isEmpty() || hits.getFirst().document().id() != 0) {
                throw new IllegalStateException("first query oracle failed");
            }
            previous = emit(
                    Checkpoint.FIRST_QUERY_VERIFIED,
                    processStart,
                    previous,
                    engine,
                    checksum
            );

            engine.createIndex(IndexDefinition.equality(DYNAMIC_CATEGORY)).join();
            previous = emit(
                    Checkpoint.DYNAMIC_STRUCTURED_INDEX_AVAILABLE,
                    processStart,
                    previous,
                    engine,
                    checksum
            );

            engine.createIndex(IndexDefinition.text(SECONDARY_TEXT)).join();
            List<SearchHit<V34DiagnosticCorpus.Document>> secondary = engine.search(
                    SearchRequest.<V34DiagnosticCorpus.Document>builder()
                            .query(SearchQueries.text(SECONDARY_TEXT, "anchor"))
                            .limit(10)
                            .build()
            ).hits();
            checksum = 31L * checksum + hitChecksum(secondary);
            previous = emit(
                    Checkpoint.DYNAMIC_TEXT_INDEX_AVAILABLE,
                    processStart,
                    previous,
                    engine,
                    checksum
            );

            if (engine.metrics().documentCount() != config.documentCount()
                    || engine.metrics().registeredIndexCount() != 4
                    || secondary.isEmpty()) {
                throw new IllegalStateException("final cold-build oracle failed");
            }
            System.out.printf(
                    "result=SUCCESS documents=%d indexes=%d checksum=%d "
                            + "corpusDigest=%s%n",
                    config.documentCount(),
                    engine.metrics().registeredIndexCount(),
                    checksum,
                    corpusDigest
            );
        } finally {
            if (engine != null) {
                engine.close();
            }
            emit(Checkpoint.CLOSED, processStart, previous, engine, checksum);
        }
    }

    private static long emit(
            Checkpoint checkpoint,
            long processStart,
            long previous,
            SearchEngine<Integer, V34DiagnosticCorpus.Document> engine,
            long checksum
    ) {
        long now = System.nanoTime();
        long snapshot = engine == null ? 0L : engine.metrics().snapshotVersion();
        int documents = engine == null ? 0 : engine.metrics().documentCount();
        int indexes = engine == null ? 0 : engine.metrics().registeredIndexCount();
        System.out.printf(
                "checkpoint=%s elapsedNanos=%d stageNanos=%d snapshotVersion=%d "
                        + "documents=%d indexes=%d checksum=%d%n",
                checkpoint.name(),
                now - processStart,
                now - previous,
                snapshot,
                documents,
                indexes,
                checksum
        );
        return now;
    }

    private static long hitChecksum(
            List<SearchHit<V34DiagnosticCorpus.Document>> hits
    ) {
        long checksum = hits.size();
        for (SearchHit<V34DiagnosticCorpus.Document> hit : hits) {
            checksum = 31L * checksum + hit.document().id();
            checksum = 31L * checksum
                    + Double.doubleToRawLongBits(hit.score());
        }
        return checksum;
    }

    enum Checkpoint {
        PROCESS_START,
        ENGINE_CONSTRUCTED,
        CORPUS_GENERATED,
        INITIAL_DOCUMENTS_LOADED,
        INITIAL_STRUCTURED_INDEX_AVAILABLE,
        INITIAL_TEXT_INDEX_AVAILABLE,
        READY_TO_SEARCH,
        FIRST_QUERY_VERIFIED,
        DYNAMIC_STRUCTURED_INDEX_AVAILABLE,
        DYNAMIC_TEXT_INDEX_AVAILABLE,
        CLOSED
    }

    record Config(
            int documentCount,
            int tokensPerField,
            int batchSize,
            long seed
    ) {
        Config {
            if (documentCount <= 0
                    || documentCount > V34DiagnosticCorpus.MAX_DOCUMENTS) {
                throw new IllegalArgumentException("invalid document count");
            }
            if (tokensPerField < 2
                    || tokensPerField
                    > V34DiagnosticCorpus.MAX_TOKENS_PER_FIELD) {
                throw new IllegalArgumentException("invalid token count");
            }
            if (batchSize <= 0 || batchSize > 10_000) {
                throw new IllegalArgumentException("invalid batch size");
            }
        }

        static Config parse(String[] arguments) {
            int documents = 100_000;
            int tokens = 16;
            int batch = 1_000;
            long seed = 34L;
            for (String argument : arguments) {
                if (argument.startsWith("--documents=")) {
                    documents = Integer.parseInt(argument.substring(12));
                } else if (argument.startsWith("--tokens=")) {
                    tokens = Integer.parseInt(argument.substring(9));
                } else if (argument.startsWith("--batch-size=")) {
                    batch = Integer.parseInt(argument.substring(13));
                } else if (argument.startsWith("--seed=")) {
                    seed = Long.parseLong(argument.substring(7));
                } else {
                    throw new IllegalArgumentException(
                            "unknown cold-build argument: " + argument);
                }
            }
            return new Config(documents, tokens, batch, seed);
        }
    }
}
