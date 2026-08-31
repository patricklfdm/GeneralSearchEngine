package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.metrics.SearchEngineMetrics;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchPageRequest;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.HighlightedSearchRequest;
import org.junit.jupiter.api.Test;

class SearchEngineV3DefaultCapabilityTest {
    private static final Field<String, String> VALUE =
            Field.of("value", String.class, value -> value);
    private static final TextField<String> TEXT =
            TextField.of(VALUE, Analyzer.simple());
    private static final SearchRequest<String> REQUEST = SearchRequest.of(
            SearchQueries.text(TEXT, "value"));
    private static final SearchPageRequest<String> PAGE_REQUEST =
            SearchPageRequest.builder(REQUEST).build();

    @Test
    void thirdPartyImplementationInheritsUnsupportedCapabilities() {
        SearchEngine<String, String> engine = new MinimalEngine();

        assertThrows(UnsupportedOperationException.class,
                () -> engine.search(REQUEST));
        assertThrows(UnsupportedOperationException.class,
                () -> engine.search(PAGE_REQUEST));
        assertThrows(UnsupportedOperationException.class,
                () -> engine.explain(REQUEST, "id"));
        assertThrows(UnsupportedOperationException.class, () -> engine.search(
                HighlightedSearchRequest.builder(REQUEST).field(TEXT).build()
        ));
        assertEquals(List.of(), engine.search(Query.matchAll()));
    }

    @Test
    void defaultCapabilitiesValidateNullBeforeUnsupportedFailure() {
        SearchEngine<String, String> engine = new MinimalEngine();

        assertThrows(NullPointerException.class,
                () -> engine.search((SearchRequest<String>) null));
        assertThrows(NullPointerException.class,
                () -> engine.search((SearchPageRequest<String>) null));
        assertThrows(NullPointerException.class,
                () -> engine.explain(null, "id"));
        assertThrows(NullPointerException.class,
                () -> engine.explain(REQUEST, null));
        assertThrows(NullPointerException.class,
                () -> engine.search((HighlightedSearchRequest<String>) null));
    }

    private static final class MinimalEngine implements SearchEngine<String, String> {
        @Override
        public CompletableFuture<Void> add(String document) {
            return CompletableFuture.completedFuture(null);
        }

        @Override
        public CompletableFuture<Void> update(String document) {
            return CompletableFuture.completedFuture(null);
        }

        @Override
        public CompletableFuture<Void> remove(String id) {
            return CompletableFuture.completedFuture(null);
        }

        @Override
        public CompletableFuture<Void> createIndex(IndexDefinition<String> definition) {
            return CompletableFuture.completedFuture(null);
        }

        @Override
        public CompletableFuture<Void> dropIndex(String fieldName) {
            return CompletableFuture.completedFuture(null);
        }

        @Override
        public String get(String id) {
            return null;
        }

        @Override
        public List<String> search(Query<String> query) {
            return List.of();
        }

        @Override
        public SearchSchema<String, String> schema() {
            return null;
        }

        @Override
        public SearchEngineMetrics metrics() {
            return null;
        }

        @Override
        public void close() {
        }
    }
}
