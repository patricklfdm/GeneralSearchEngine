package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;

@Timeout(10)
class ReleaseHardeningSearchTest {
    private static final Field<Document, Long> ID =
            Field.of("id", Long.class, Document::id);
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void wideShouldTreePreservesEveryClauseAndExplainScore() {
        try (SearchEngine<Long, Document> engine = newEngine()) {
            engine.addAll(List.of(
                    new Document(1L, "common", "common"),
                    new Document(2L, "common", "absent"),
                    new Document(3L, "absent", "absent")
            )).join();

            SearchQueries.BoolBuilder<Document> bool = SearchQueries.bool();
            for (int clause = 0; clause < 64; clause++) {
                TextField<Document> field = clause % 2 == 0
                        ? TITLE_TEXT
                        : BODY_TEXT;
                bool.should(SearchQueries.text(field, "common"));
            }
            SearchRequest<Document> request = SearchRequest.of(bool.build());

            SearchResult<Document> result = engine.search(request);
            assertEquals(List.of(1L, 2L), ids(result));
            SearchExplanation<Document> explanation =
                    engine.explain(request, 1L).orElseThrow();
            assertTrue(explanation.matched());
            assertEquals(result.hits().getFirst().score(), explanation.score());
            assertEquals(64, explanation.detail().children()
                    .getFirst().children()
                    .getFirst().children().size());
        }
    }

    @Test
    void longRepeatedPhraseRejectsOneInteriorBreak() {
        String queryText = repeated("echo", 32);
        String broken = repeated("echo", 24)
                + " noise "
                + repeated("echo", 24);
        try (SearchEngine<Long, Document> engine = newEngine()) {
            engine.addAll(List.of(
                    new Document(1L, "exact", repeated("echo", 48)),
                    new Document(2L, "broken", broken)
            )).join();
            SearchRequest<Document> request = SearchRequest.of(
                    SearchQueries.phrase(BODY_TEXT, queryText));

            assertEquals(List.of(1L), ids(engine.search(request)));
            SearchExplanation<Document> nonMatch =
                    engine.explain(request, 2L).orElseThrow();
            assertFalse(nonMatch.matched());
            assertEquals(0.0, nonMatch.score());
        }
    }

    @Test
    void fuzzyExpansionRemainsCompleteBeyondTypicalTopKSize() {
        List<Document> documents = new ArrayList<>();
        documents.add(new Document(0L, "exact", "aaaaaaaa"));
        long id = 1L;
        for (char first = 'b'; first <= 'z'; first++) {
            for (char second = 'b'; second <= 'z'; second++) {
                documents.add(new Document(
                        id++,
                        "two edits",
                        new String(new char[]{
                                first, second, 'a', 'a', 'a', 'a', 'a', 'a'
                        })
                ));
            }
        }

        try (SearchEngine<Long, Document> engine = newEngine()) {
            engine.addAll(documents).join();
            SearchRequest<Document> request = SearchRequest.<Document>builder()
                    .query(SearchQueries.fuzzy(BODY_TEXT, "aaaaaaaa"))
                    .limit(1_000)
                    .build();

            SearchResult<Document> result = engine.search(request);
            assertEquals(626, result.hits().size());
            assertEquals(0L, result.hits().getFirst().document().id());

            SearchHit<Document> lastExpansion = result.hits().stream()
                    .filter(hit -> hit.document().id() == 625L)
                    .findFirst()
                    .orElseThrow();
            SearchExplanation<Document> explanation =
                    engine.explain(request, 625L).orElseThrow();
            assertTrue(explanation.matched());
            assertEquals(lastExpansion.score(), explanation.score());
        }
    }

    private static SearchEngine<Long, Document> newEngine() {
        return SearchEngine.builder(Document.class, ID)
                .index(IndexDefinition.text(TITLE_TEXT))
                .index(IndexDefinition.text(BODY_TEXT))
                .build();
    }

    private static String repeated(String term, int count) {
        return String.join(" ", Collections.nCopies(count, term));
    }

    private static List<Long> ids(SearchResult<Document> result) {
        return result.hits().stream()
                .map(hit -> hit.document().id())
                .toList();
    }

    private record Document(long id, String title, String body) {
    }
}
