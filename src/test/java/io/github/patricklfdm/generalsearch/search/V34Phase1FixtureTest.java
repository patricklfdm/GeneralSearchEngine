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

class V34Phase1FixtureTest {
    private static final Field<Document, Integer> ID =
            Field.of("id", Integer.class, Document::id);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void exactV33ReadSurfacesRemainEquivalent() {
        try (SearchEngine<Integer, Document> engine = engine()) {
            engine.addAll(initialDocuments()).join();
            SearchRequest<Document> request = request(10);

            List<SearchHit<Document>> ordinary = engine.search(request).hits();
            SearchPageResult<Document> page = engine.search(
                    SearchPageRequest.<Document>builder(request)
                            .totalHits(TotalHitsMode.EXACT)
                            .build()
            );
            HighlightedSearchResult<Document> highlighted = engine.search(
                    HighlightedSearchRequest.<Document>builder(request)
                            .field(BODY_TEXT)
                            .contextCharacters(0)
                            .maxFragmentsPerField(1)
                            .build()
            );

            assertIds(V34TestReference.initialIds(), ordinary);
            assertEquals(ordinary, page.hits());
            assertEquals(3L, page.totalHits().orElseThrow());
            assertTrue(page.nextCursor().isEmpty());
            assertEquals(ordinary, highlighted.hits().stream()
                    .map(HighlightedSearchHit::hit)
                    .toList());
            assertTrue(highlighted.hits().stream()
                    .allMatch(hit -> !hit.highlights().isEmpty()));
        }
    }

    @Test
    void exactV33PublicationSequenceRetainsSnapshotSemantics() {
        try (SearchEngine<Integer, Document> engine = engine()) {
            engine.addAll(initialDocuments()).join();
            assertIds(V34TestReference.initialIds(), engine.search(request(10)).hits());

            engine.add(new Document(4, "hardening stable")).join();
            assertIds(V34TestReference.afterAdd(), engine.search(request(10)).hits());

            engine.update(new Document(1, "unrelated replacement")).join();
            assertIds(V34TestReference.afterUpdate(), engine.search(request(10)).hits());

            engine.remove(3).join();
            List<SearchHit<Document>> finalHits = engine.search(request(10)).hits();
            assertIds(V34TestReference.afterRemove(), finalHits);
            assertTrue(engine.metrics().acceptingRequests());
        }
    }

    @Test
    void exactTotalAndCursorDefaultsRemainFrozen() {
        try (SearchEngine<Integer, Document> engine = engine()) {
            engine.addAll(initialDocuments()).join();
            SearchRequest<Document> request = request(2);
            SearchPageResult<Document> disabled = engine.search(
                    SearchPageRequest.<Document>builder(request).build()
            );
            SearchPageResult<Document> exact = engine.search(
                    SearchPageRequest.<Document>builder(request)
                            .totalHits(TotalHitsMode.EXACT)
                            .build()
            );

            assertEquals(disabled.hits(), exact.hits());
            assertTrue(disabled.totalHits().isEmpty());
            assertEquals(3L, exact.totalHits().orElseThrow());
            assertTrue(exact.nextCursor().isPresent());
        }
    }

    private static SearchEngine<Integer, Document> engine() {
        return SearchEngine.builder(Document.class, ID)
                .index(IndexDefinition.text(BODY_TEXT))
                .build();
    }

    private static SearchRequest<Document> request(int limit) {
        return SearchRequest.<Document>builder()
                .query(SearchQueries.text(BODY_TEXT, "hardening"))
                .limit(limit)
                .build();
    }

    private static List<Document> initialDocuments() {
        return List.of(
                new Document(0, "hardening stable"),
                new Document(1, "hardening stable"),
                new Document(2, "unrelated stable"),
                new Document(3, "hardening stable")
        );
    }

    private static void assertIds(
            List<Integer> expected,
            List<SearchHit<Document>> hits
    ) {
        List<Integer> actual = hits.stream()
                .map(hit -> hit.document().id())
                .toList();
        assertEquals(expected, actual);
        assertEquals(
                V34TestReference.orderedIdChecksum(expected),
                V34TestReference.orderedIdChecksum(actual)
        );
    }

    private record Document(int id, String body) {
    }
}
