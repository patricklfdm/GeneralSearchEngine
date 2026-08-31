package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.ArrayList;
import java.util.List;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.HighlightFragment;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchHit;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchPageRequest;
import io.github.patricklfdm.generalsearch.search.SearchPageResult;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchQuery;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.TotalHitsMode;

/** Deterministic correctness probe for every frozen V3.4 extreme-corpus axis. */
public final class V34ExtremeCorpusProbe {
    private static final Field<V34DiagnosticCorpus.Document, Integer> ID =
            Field.of("id", Integer.class, V34DiagnosticCorpus.Document::id);
    private static final Field<V34DiagnosticCorpus.Document, String> CATEGORY =
            Field.of("category", String.class,
                    V34DiagnosticCorpus.Document::category);
    private static final Field<V34DiagnosticCorpus.Document, String> PRIMARY =
            Field.of("primary", String.class,
                    V34DiagnosticCorpus.Document::primary);
    private static final Field<V34DiagnosticCorpus.Document, String> SECONDARY =
            Field.of("secondary", String.class,
                    V34DiagnosticCorpus.Document::secondary);

    private V34ExtremeCorpusProbe() {
    }

    public static void main(String[] arguments) {
        Config config = Config.parse(arguments);
        List<V34DiagnosticCorpus.Axis> axes = config.allAxes()
                ? List.of(V34DiagnosticCorpus.Axis.values())
                : List.of(V34DiagnosticCorpus.Axis.parse(config.axis()));
        long combined = 1L;
        for (V34DiagnosticCorpus.Axis axis : axes) {
            Outcome outcome = run(new V34DiagnosticCorpus.Config(
                    config.documentCount(),
                    config.tokensPerField(),
                    config.seed(),
                    axis
            ));
            combined = 31L * combined + outcome.combinedChecksum();
            System.out.printf(
                    "extremeAxis=%s status=SUCCESS documents=%d tokens=%d "
                            + "matches=%d corpusDigest=%s hitChecksum=%d "
                            + "explainChecksum=%d highlightChecksum=%d "
                            + "pageChecksum=%d fuzzyChecksum=%d "
                            + "secondaryChecksum=%d combinedChecksum=%d%n",
                    axis.id(),
                    config.documentCount(),
                    config.tokensPerField(),
                    outcome.matchCount(),
                    outcome.corpusDigest(),
                    outcome.hitChecksum(),
                    outcome.explainChecksum(),
                    outcome.highlightChecksum(),
                    outcome.pageChecksum(),
                    outcome.fuzzyChecksum(),
                    outcome.secondaryChecksum(),
                    outcome.combinedChecksum()
            );
        }
        System.out.printf(
                "extremeSummary=SUCCESS axes=%d combinedChecksum=%d%n",
                axes.size(),
                combined
        );
    }

    static Outcome run(V34DiagnosticCorpus.Config config) {
        List<V34DiagnosticCorpus.Document> documents =
                V34DiagnosticCorpus.generate(config);
        String corpusDigest = V34DiagnosticCorpus.digest(documents);
        TextField<V34DiagnosticCorpus.Document> primaryText = TextField.of(
                PRIMARY,
                V34DiagnosticCorpus.analyzer(config.axis())
        );
        TextField<V34DiagnosticCorpus.Document> secondaryText = TextField.of(
                SECONDARY,
                V34DiagnosticCorpus.analyzer(config.axis())
        );
        List<Integer> expected = V34DiagnosticCorpus.expectedEligibleIds(
                config.documentCount());

        try (SearchEngine<Integer, V34DiagnosticCorpus.Document> engine =
                     SearchEngine.builder(V34DiagnosticCorpus.Document.class, ID)
                             .index(IndexDefinition.equality(CATEGORY))
                             .index(IndexDefinition.text(primaryText))
                             .index(IndexDefinition.text(secondaryText))
                             .build()) {
            addInChunks(engine, documents, 1_000);

            int ordinaryLimit = Math.min(100, expected.size());
            SearchRequest<V34DiagnosticCorpus.Document> ordinaryRequest =
                    request(primaryText, ordinaryLimit,
                            SearchQueries.phrase(primaryText, "anchor exact"));
            List<SearchHit<V34DiagnosticCorpus.Document>> hits =
                    engine.search(ordinaryRequest).hits();
            assertIds(expected.subList(0, ordinaryLimit), hits, "ordinary");
            long hitChecksum = hitChecksum(hits);

            long explainChecksum = 1L;
            for (int index = 0; index < Math.min(25, hits.size()); index++) {
                SearchHit<V34DiagnosticCorpus.Document> hit = hits.get(index);
                var explanation = engine.explain(
                        ordinaryRequest,
                        hit.document().id()
                ).orElseThrow();
                if (!explanation.matched()
                        || Double.doubleToRawLongBits(explanation.score())
                        != Double.doubleToRawLongBits(hit.score())) {
                    throw new IllegalStateException("Explain score oracle failed");
                }
                explainChecksum = 31L * explainChecksum
                        + explanation.document().id();
                explainChecksum = 31L * explainChecksum
                        + Double.doubleToRawLongBits(explanation.score());
            }

            var highlighted = engine.search(HighlightedSearchRequest
                    .<V34DiagnosticCorpus.Document>builder(ordinaryRequest)
                    .field(primaryText)
                    .contextCharacters(0)
                    .maxFragmentsPerField(1)
                    .build());
            if (!highlighted.hits().stream().map(HighlightedSearchHit::hit).toList()
                    .equals(hits)) {
                throw new IllegalStateException("highlighted hit parity failed");
            }
            long highlightChecksum = 1L;
            for (HighlightedSearchHit<V34DiagnosticCorpus.Document> hit
                    : highlighted.hits()) {
                if (hit.highlights().size() != 1
                        || hit.highlights().getFirst().fragments().isEmpty()) {
                    throw new IllegalStateException("missing highlight evidence");
                }
                HighlightFragment fragment = hit.highlights().getFirst()
                        .fragments().getFirst();
                String source = hit.hit().document().primary();
                if (!fragment.text().equals(source.substring(
                        fragment.startOffset(), fragment.endOffset()))) {
                    throw new IllegalStateException("highlight source range failed");
                }
                highlightChecksum = 31L * highlightChecksum
                        + hit.hit().document().id();
                highlightChecksum = 31L * highlightChecksum
                        + fragment.startOffset();
                highlightChecksum = 31L * highlightChecksum
                        + fragment.endOffset();
                for (var span : fragment.spans()) {
                    highlightChecksum = 31L * highlightChecksum
                            + span.startOffset();
                    highlightChecksum = 31L * highlightChecksum
                            + span.endOffset();
                }
            }

            long pageChecksum = pageWalkChecksum(engine, primaryText, expected);

            List<SearchHit<V34DiagnosticCorpus.Document>> fuzzy = engine.search(
                    request(
                            primaryText,
                            Math.max(1, expected.size()),
                            SearchQueries.fuzzy(primaryText, "anchir")
                    )
            ).hits();
            assertIds(expected, fuzzy, "fuzzy");
            long fuzzyChecksum = hitChecksum(fuzzy);

            List<SearchHit<V34DiagnosticCorpus.Document>> secondary = engine.search(
                    request(
                            secondaryText,
                            Math.max(1, expected.size()),
                            SearchQueries.text(secondaryText, "anchor")
                    )
            ).hits();
            assertIds(expected, secondary, "secondary");
            long secondaryChecksum = hitChecksum(secondary);

            if (config.axis() == V34DiagnosticCorpus.Axis.POSITION_HEAVY) {
                List<SearchHit<V34DiagnosticCorpus.Document>> sloppy = engine.search(
                        request(
                                primaryText,
                                Math.max(1, expected.size()),
                                SearchQueries.phrase(
                                        primaryText,
                                        "exact position",
                                        64
                                )
                        )
                ).hits();
                assertIds(expected, sloppy, "position-heavy sloppy phrase");
                secondaryChecksum = 31L * secondaryChecksum + hitChecksum(sloppy);
            }

            long combined = combine(
                    corpusDigest.hashCode(),
                    hitChecksum,
                    explainChecksum,
                    highlightChecksum,
                    pageChecksum,
                    fuzzyChecksum,
                    secondaryChecksum
            );
            return new Outcome(
                    config.axis(),
                    corpusDigest,
                    expected.size(),
                    hitChecksum,
                    explainChecksum,
                    highlightChecksum,
                    pageChecksum,
                    fuzzyChecksum,
                    secondaryChecksum,
                    combined
            );
        }
    }

    private static long pageWalkChecksum(
            SearchEngine<Integer, V34DiagnosticCorpus.Document> engine,
            TextField<V34DiagnosticCorpus.Document> field,
            List<Integer> expected
    ) {
        SearchRequest<V34DiagnosticCorpus.Document> request = request(
                field,
                Math.min(17, Math.max(1, expected.size())),
                SearchQueries.phrase(field, "anchor exact")
        );
        var builder = SearchPageRequest.<V34DiagnosticCorpus.Document>builder(request)
                .totalHits(TotalHitsMode.EXACT);
        List<Integer> actual = new ArrayList<>(expected.size());
        long checksum = 1L;
        while (true) {
            SearchPageResult<V34DiagnosticCorpus.Document> page =
                    engine.search(builder.build());
            if (page.totalHits().orElseThrow() != expected.size()) {
                throw new IllegalStateException("exact total changed across pages");
            }
            for (SearchHit<V34DiagnosticCorpus.Document> hit : page.hits()) {
                actual.add(hit.document().id());
                checksum = 31L * checksum + hit.document().id();
                checksum = 31L * checksum
                        + Double.doubleToRawLongBits(hit.score());
            }
            if (page.nextCursor().isEmpty()) {
                break;
            }
            builder.after(page.nextCursor().orElseThrow());
        }
        if (!actual.equals(expected)) {
            throw new IllegalStateException("page walk oracle failed");
        }
        return checksum;
    }

    private static SearchRequest<V34DiagnosticCorpus.Document> request(
            TextField<V34DiagnosticCorpus.Document> field,
            int limit,
            SearchQuery<V34DiagnosticCorpus.Document> query
    ) {
        return SearchRequest.<V34DiagnosticCorpus.Document>builder()
                .query(query)
                .filter(Query.eq(CATEGORY, "eligible"))
                .limit(limit)
                .build();
    }

    private static void assertIds(
            List<Integer> expected,
            List<SearchHit<V34DiagnosticCorpus.Document>> hits,
            String label
    ) {
        List<Integer> actual = hits.stream()
                .map(hit -> hit.document().id())
                .toList();
        if (!actual.equals(expected)) {
            throw new IllegalStateException(
                    label + " ID oracle failed: expected=" + expected.size()
                            + ", actual=" + actual.size());
        }
        for (int index = 1; index < hits.size(); index++) {
            SearchHit<V34DiagnosticCorpus.Document> previous = hits.get(index - 1);
            SearchHit<V34DiagnosticCorpus.Document> current = hits.get(index);
            int scoreOrder = Double.compare(previous.score(), current.score());
            if (scoreOrder < 0 || (scoreOrder == 0
                    && previous.document().id() >= current.document().id())) {
                throw new IllegalStateException(label + " canonical order failed");
            }
        }
    }

    private static void addInChunks(
            SearchEngine<Integer, V34DiagnosticCorpus.Document> engine,
            List<V34DiagnosticCorpus.Document> documents,
            int batchSize
    ) {
        for (int start = 0; start < documents.size(); start += batchSize) {
            engine.addAll(documents.subList(
                    start,
                    Math.min(start + batchSize, documents.size())
            )).join();
        }
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

    private static long combine(long... values) {
        long checksum = 1L;
        for (long value : values) {
            checksum = 31L * checksum + value;
        }
        return checksum;
    }

    record Outcome(
            V34DiagnosticCorpus.Axis axis,
            String corpusDigest,
            int matchCount,
            long hitChecksum,
            long explainChecksum,
            long highlightChecksum,
            long pageChecksum,
            long fuzzyChecksum,
            long secondaryChecksum,
            long combinedChecksum
    ) {
    }

    record Config(
            int documentCount,
            int tokensPerField,
            long seed,
            String axis,
            boolean allAxes
    ) {
        Config {
            V34DiagnosticCorpus.Axis validationAxis = allAxes
                    ? V34DiagnosticCorpus.Axis.LONG_TEXT
                    : V34DiagnosticCorpus.Axis.parse(axis);
            new V34DiagnosticCorpus.Config(
                    documentCount,
                    tokensPerField,
                    seed,
                    validationAxis
            );
        }

        static Config parse(String[] arguments) {
            int documents = 1_000;
            int tokens = 64;
            long seed = 34L;
            String axis = "all";
            for (String argument : arguments) {
                if (argument.startsWith("--documents=")) {
                    documents = Integer.parseInt(argument.substring(12));
                } else if (argument.startsWith("--tokens=")) {
                    tokens = Integer.parseInt(argument.substring(9));
                } else if (argument.startsWith("--seed=")) {
                    seed = Long.parseLong(argument.substring(7));
                } else if (argument.startsWith("--axis=")) {
                    axis = argument.substring(7);
                } else {
                    throw new IllegalArgumentException(
                            "unknown extreme-corpus argument: " + argument);
                }
            }
            return new Config(documents, tokens, seed, axis, axis.equals("all"));
        }
    }
}
