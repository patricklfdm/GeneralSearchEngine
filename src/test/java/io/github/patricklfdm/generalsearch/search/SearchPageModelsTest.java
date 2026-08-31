package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.OptionalLong;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.exception.SearchCursorException;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class SearchPageModelsTest {
    private static final Field<String, String> VALUE =
            Field.of("value", String.class, value -> value);
    private static final TextField<String> TEXT =
            TextField.of(VALUE, Analyzer.simple());
    private static final SearchRequest<String> SEARCH = SearchRequest.of(
            SearchQueries.text(TEXT, "value"));

    @Test
    void requestDefaultsAndBuilderReuseRemainImmutable() {
        SearchPageRequest<String> defaults = SearchPageRequest
                .builder(SEARCH)
                .build();

        assertSame(SEARCH, defaults.searchRequest());
        assertTrue(defaults.after().isEmpty());
        assertEquals(TotalHitsMode.DISABLED, defaults.totalHitsMode());

        Cursor firstCursor = new Cursor("first");
        Cursor secondCursor = new Cursor("second");
        SearchPageRequest.Builder<String> builder = SearchPageRequest
                .builder(SEARCH)
                .after(firstCursor)
                .totalHits(TotalHitsMode.EXACT);
        SearchPageRequest<String> first = builder.build();
        SearchPageRequest<String> second = builder
                .after(secondCursor)
                .totalHits(TotalHitsMode.DISABLED)
                .build();

        assertSame(firstCursor, first.after().orElseThrow());
        assertEquals(TotalHitsMode.EXACT, first.totalHitsMode());
        assertSame(secondCursor, second.after().orElseThrow());
        assertEquals(TotalHitsMode.DISABLED, second.totalHitsMode());
    }

    @Test
    void requestRejectsNullAtEverySupportedBoundary() {
        assertThrows(NullPointerException.class,
                () -> SearchPageRequest.builder(null));
        SearchPageRequest.Builder<String> builder =
                SearchPageRequest.builder(SEARCH);
        assertThrows(NullPointerException.class, () -> builder.after(null));
        assertThrows(NullPointerException.class, () -> builder.totalHits(null));
    }

    @Test
    void resultFactoriesCopyHitsAndExposeTheFourFrozenShapes() {
        SearchHit<String> first = new SearchHit<>("first", 2.0);
        SearchHit<String> second = new SearchHit<>("second", 1.0);
        List<SearchHit<String>> supplied = new ArrayList<>(List.of(first, second));
        Cursor cursor = new Cursor("third-party");

        SearchPageResult<String> disabledFinal =
                SearchPageResult.withoutTotalHits(supplied);
        SearchPageResult<String> disabledNext =
                SearchPageResult.withoutTotalHits(supplied, cursor);
        SearchPageResult<String> exactFinal =
                SearchPageResult.withExactTotalHits(supplied, 9L);
        SearchPageResult<String> exactNext =
                SearchPageResult.withExactTotalHits(supplied, cursor, 9L);
        supplied.clear();

        assertEquals(List.of(first, second), disabledFinal.hits());
        assertThrows(UnsupportedOperationException.class,
                () -> disabledFinal.hits().add(first));
        assertTrue(disabledFinal.nextCursor().isEmpty());
        assertTrue(disabledFinal.totalHits().isEmpty());
        assertSame(cursor, disabledNext.nextCursor().orElseThrow());
        assertTrue(disabledNext.totalHits().isEmpty());
        assertTrue(exactFinal.nextCursor().isEmpty());
        assertEquals(OptionalLong.of(9L), exactFinal.totalHits());
        assertSame(cursor, exactNext.nextCursor().orElseThrow());
        assertEquals(OptionalLong.of(9L), exactNext.totalHits());
        assertEquals(OptionalLong.of(0L), SearchPageResult
                .withExactTotalHits(List.of(), 0L)
                .totalHits());
    }

    @Test
    void resultFactoriesRejectNullAndNegativeState() {
        SearchHit<String> hit = new SearchHit<>("hit", 1.0);

        assertThrows(NullPointerException.class,
                () -> SearchPageResult.withoutTotalHits(null));
        assertThrows(NullPointerException.class, () ->
                SearchPageResult.withoutTotalHits(
                        Arrays.asList(hit, null)));
        assertThrows(NullPointerException.class, () ->
                SearchPageResult.withoutTotalHits(List.of(hit), null));
        assertThrows(NullPointerException.class, () ->
                SearchPageResult.withExactTotalHits(
                        List.of(hit), null, 1L));
        assertThrows(IllegalArgumentException.class, () ->
                SearchPageResult.withExactTotalHits(List.of(hit), -1L));
        assertThrows(IllegalArgumentException.class, () ->
                SearchPageResult.withExactTotalHits(
                        List.of(hit), new Cursor("cursor"), -1L));
    }

    @Test
    void cursorExceptionExposesOnlyFrozenReasonAndMessage() {
        for (SearchCursorException.Reason reason :
                SearchCursorException.Reason.values()) {
            SearchCursorException exception = new SearchCursorException(reason);
            assertEquals(reason, exception.reason());
            assertTrue(!exception.getMessage().isBlank());
        }
        assertThrows(NullPointerException.class,
                () -> new SearchCursorException(null));
    }

    private record Cursor(String value) implements SearchAfterCursor {
    }
}
