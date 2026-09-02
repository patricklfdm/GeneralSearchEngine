package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

/** Exact V3.4 in-memory control retained before durable production work. */
class V40Phase1FixtureTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void v34MutationAndRankedOrderRemainThePreChangeOracle() {
        try (SearchEngine<Integer, Document> engine = SearchEngine
                .builder(Document.class, ID)
                .index(IndexDefinition.text(BODY_TEXT))
                .build()) {
            engine.addAll(List.of(
                    new Document(7, "durable search"),
                    new Document(2, "durable search"),
                    new Document(9, "unrelated")
            )).join();
            assertIds(List.of(7, 2), engine.search(request()).hits());

            engine.update(new Document(7, "unrelated replacement")).join();
            engine.remove(99).join();
            engine.add(new Document(1, "durable search")).join();

            assertIds(List.of(2, 1), engine.search(request()).hits());
            assertEquals(List.of(7, 2, 9, 1), List.of(
                    engine.get(7).id(),
                    engine.get(2).id(),
                    engine.get(9).id(),
                    engine.get(1).id()
            ));
            assertTrue(engine.metrics().acceptingRequests());
        }
    }

    private static SearchRequest<Document> request() {
        return SearchRequest.<Document>builder()
                .query(SearchQueries.text(BODY_TEXT, "durable"))
                .limit(10)
                .build();
    }

    private static void assertIds(
            List<Integer> expected,
            List<SearchHit<Document>> hits
    ) {
        assertEquals(expected, hits.stream()
                .map(hit -> hit.document().id())
                .toList());
    }

    private record Document(int id, String body) {
    }
}
