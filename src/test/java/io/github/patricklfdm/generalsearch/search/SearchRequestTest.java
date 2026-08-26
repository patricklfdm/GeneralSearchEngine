package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class SearchRequestTest {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CITY =
            Field.of("city", String.class, Document::city);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final SearchQuery<Document> QUERY =
            SearchQueries.text(TEXT, "quiet temple");

    @Test
    void ofUsesFrozenDefaults() {
        SearchRequest<Document> request = SearchRequest.of(QUERY);

        assertSame(QUERY, request.query());
        assertFalse(request.filter().isPresent());
        assertEquals(10, request.limit());
        assertSame(Bm25Config.DEFAULT, request.bm25());
    }

    @Test
    void builderRetainsExplicitValues() {
        Query<Document> filter = Query.eq(CITY, "Tokyo");
        Bm25Config bm25 = new Bm25Config(1.5, 0.6);

        SearchRequest<Document> request = SearchRequest.<Document>builder()
                .query(QUERY)
                .filter(filter)
                .limit(25)
                .bm25(bm25)
                .build();

        assertSame(QUERY, request.query());
        assertSame(filter, request.filter().orElseThrow());
        assertEquals(25, request.limit());
        assertSame(bm25, request.bm25());
    }

    @Test
    void rejectsInvalidConstructionImmediately() {
        SearchRequest.Builder<Document> builder = SearchRequest.builder();

        assertThrows(NullPointerException.class, () -> builder.query(null));
        assertThrows(NullPointerException.class, () -> builder.filter(null));
        assertThrows(NullPointerException.class, () -> builder.bm25(null));
        assertThrows(IllegalArgumentException.class, () -> builder.limit(0));
        assertThrows(IllegalArgumentException.class, () -> builder.limit(-1));
        assertThrows(IllegalStateException.class, builder::build);
        assertThrows(NullPointerException.class,
                () -> SearchRequest.<Document>of(null));
    }

    @Test
    void builderReuseDoesNotMutatePriorRequests() {
        SearchRequest.Builder<Document> builder = SearchRequest.<Document>builder()
                .query(QUERY);
        SearchRequest<Document> first = builder.build();
        Query<Document> filter = Query.eq(CITY, "Kyoto");
        SearchRequest<Document> second = builder.filter(filter).limit(3).build();

        assertFalse(first.filter().isPresent());
        assertEquals(10, first.limit());
        assertTrue(second.filter().isPresent());
        assertEquals(3, second.limit());
    }

    private record Document(String body, String city) {
    }
}
