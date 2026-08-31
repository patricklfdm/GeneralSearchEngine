package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Modifier;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import org.junit.jupiter.api.Test;

class V32HighlightStorageBoundaryTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);

    @Test
    void ordinaryOperationsNeverRequestOffsetsAndSnapshotsStoreNone() {
        CountingOffsetAnalyzer analyzer = new CountingOffsetAnalyzer();
        TextField<Document> text = TextField.of(BODY, analyzer);
        try (SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .index(IndexDefinition.text(text))
                .build()) {
            engine.addAll(List.of(
                    new Document(1, "alpha stable"),
                    new Document(2, "beta stable")
            )).join();
            SearchRequest<Document> search = SearchRequest.of(
                    SearchQueries.text(text, "stable")
            );

            assertEquals(2, engine.search(search).hits().size());
            assertTrue(engine.explain(search, 1).orElseThrow().matched());
            engine.update(new Document(1, "alpha stable updated")).join();
            engine.dropIndex(BODY.name()).join();
            engine.createIndex(IndexDefinition.text(text)).join();
            assertEquals(2, engine.search(search).hits().size());
            assertEquals(0, analyzer.offsetCalls());

            HighlightedSearchRequest<Document> highlighted =
                    HighlightedSearchRequest.<Document>builder(search)
                            .field(text)
                            .contextCharacters(0)
                            .maxFragmentsPerField(3)
                            .build();
            assertEquals(2, engine.search(highlighted).hits().size());
            assertEquals(2, analyzer.offsetCalls());
        }

        Set<String> retainedFields = Arrays.stream(
                        TextIndexSnapshot.class.getDeclaredFields())
                .filter(field -> !Modifier.isStatic(field.getModifiers()))
                .map(java.lang.reflect.Field::getName)
                .collect(Collectors.toUnmodifiableSet());
        assertEquals(Set.of(
                "textField",
                "postings",
                "fuzzyDictionary",
                "documentLengths",
                "totalDocumentLength",
                "statistics"
        ), retainedFields);
        assertFalse(retainedFields.stream().anyMatch(name ->
                name.toLowerCase().contains("offset")
                        || name.toLowerCase().contains("highlight")
                        || name.toLowerCase().contains("evidence")));
    }

    private record Document(int id, String body) {
    }

    private static final class CountingOffsetAnalyzer implements OffsetAnalyzer {
        private final Analyzer ordinary = Analyzer.simple();
        private final OffsetAnalyzer offsets = (OffsetAnalyzer) Analyzer.simple();
        private final AtomicInteger offsetCalls = new AtomicInteger();

        @Override
        public List<Token> analyze(String text) {
            return ordinary.analyze(text);
        }

        @Override
        public List<AnalyzedToken> analyzeWithPositions(String text) {
            return ordinary.analyzeWithPositions(text);
        }

        @Override
        public List<OffsetAnalyzedToken> analyzeWithOffsets(String text) {
            offsetCalls.incrementAndGet();
            return offsets.analyzeWithOffsets(text);
        }

        private int offsetCalls() {
            return offsetCalls.get();
        }
    }
}
