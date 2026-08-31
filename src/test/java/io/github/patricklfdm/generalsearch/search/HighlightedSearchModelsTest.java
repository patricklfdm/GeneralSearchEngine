package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class HighlightedSearchModelsTest {
    private static final Field<String, String> VALUE =
            Field.of("value", String.class, value -> value);
    private static final Field<String, String> OTHER =
            Field.of("other", String.class, value -> value);
    private static final TextField<String> TEXT =
            TextField.of(VALUE, Analyzer.simple());
    private static final TextField<String> OTHER_TEXT =
            TextField.of(OTHER, Analyzer.simple());
    private static final SearchRequest<String> SEARCH = SearchRequest.of(
            SearchQueries.text(TEXT, "value")
    );

    @Test
    void builderAppliesDefaultsOrderAndImmutableSnapshots() {
        HighlightedSearchRequest.Builder<String> builder =
                HighlightedSearchRequest.builder(SEARCH).field(TEXT);
        HighlightedSearchRequest<String> first = builder.build();
        builder.field(OTHER_TEXT)
                .contextCharacters(0)
                .maxFragmentsPerField(1);
        HighlightedSearchRequest<String> second = builder.build();

        assertSame(SEARCH, first.searchRequest());
        assertEquals(List.of(TEXT), first.fields());
        assertEquals(40, first.contextCharacters());
        assertEquals(3, first.maxFragmentsPerField());
        assertEquals(List.of(TEXT, OTHER_TEXT), second.fields());
        assertEquals(0, second.contextCharacters());
        assertEquals(1, second.maxFragmentsPerField());
        assertThrows(UnsupportedOperationException.class, () ->
                second.fields().add(TEXT));
    }

    @Test
    void builderRejectsInvalidInputAndDuplicateLogicalNames() {
        assertThrows(NullPointerException.class, () ->
                HighlightedSearchRequest.builder(null));
        assertThrows(NullPointerException.class, () ->
                HighlightedSearchRequest.builder(SEARCH).field(null));
        assertThrows(IllegalStateException.class, () ->
                HighlightedSearchRequest.builder(SEARCH).build());
        assertThrows(IllegalArgumentException.class, () ->
                HighlightedSearchRequest.builder(SEARCH)
                        .contextCharacters(-1));
        assertThrows(IllegalArgumentException.class, () ->
                HighlightedSearchRequest.builder(SEARCH)
                        .maxFragmentsPerField(0));
        assertThrows(IllegalArgumentException.class, () ->
                HighlightedSearchRequest.builder(SEARCH)
                        .field(TEXT)
                        .field(TextField.of(VALUE, Analyzer.simple())));
    }

    @Test
    void resultValuesDefensivelyCopyAndPreserveCanonicalHit() {
        HighlightSpan first = new HighlightSpan(1, 3);
        HighlightSpan second = new HighlightSpan(3, 5);
        List<HighlightSpan> mutableSpans = new ArrayList<>(List.of(first, second));
        HighlightFragment fragment = new HighlightFragment(
                0,
                5,
                "abcde",
                mutableSpans
        );
        mutableSpans.clear();
        List<HighlightFragment> mutableFragments = new ArrayList<>(List.of(fragment));
        FieldHighlight field = new FieldHighlight("value", mutableFragments);
        mutableFragments.clear();
        SearchHit<String> canonical = new SearchHit<>("abcde", 1.0);
        List<FieldHighlight> mutableFields = new ArrayList<>(List.of(field));
        HighlightedSearchHit<String> hit = new HighlightedSearchHit<>(
                canonical,
                mutableFields
        );
        mutableFields.clear();
        List<HighlightedSearchHit<String>> mutableHits =
                new ArrayList<>(List.of(hit));
        HighlightedSearchResult<String> result =
                new HighlightedSearchResult<>(mutableHits);
        mutableHits.clear();

        assertSame(canonical, result.hits().getFirst().hit());
        assertEquals("value", result.hits().getFirst()
                .highlights().getFirst().fieldName());
        assertEquals("abcde", field.fragments().getFirst().text());
        assertEquals(List.of(first, second), fragment.spans());
        assertThrows(UnsupportedOperationException.class, () ->
                result.hits().clear());
    }

    @Test
    void constructorsRejectMalformedRangesListsAndDuplicates() {
        assertThrows(IllegalArgumentException.class, () -> new HighlightSpan(0, 0));
        assertThrows(IllegalArgumentException.class, () -> new HighlightSpan(-1, 1));
        HighlightSpan span = new HighlightSpan(1, 2);
        assertThrows(IllegalArgumentException.class, () -> new HighlightFragment(
                0, 2, "x", List.of(span)));
        assertThrows(IllegalArgumentException.class, () -> new HighlightFragment(
                0, 2, "xx", List.of()));
        assertThrows(IllegalArgumentException.class, () -> new HighlightFragment(
                0, 2, "xx", List.of(new HighlightSpan(1, 3))));
        assertThrows(IllegalArgumentException.class, () -> new HighlightFragment(
                0,
                4,
                "xxxx",
                List.of(new HighlightSpan(2, 4), new HighlightSpan(1, 2))
        ));
        assertThrows(NullPointerException.class, () -> new HighlightFragment(
                0, 2, "xx", Arrays.asList(span, null)));

        HighlightFragment first = new HighlightFragment(
                0, 1, "x", List.of(new HighlightSpan(0, 1)));
        HighlightFragment overlapping = new HighlightFragment(
                0, 2, "xx", List.of(new HighlightSpan(0, 1)));
        assertThrows(IllegalArgumentException.class, () ->
                new FieldHighlight("value", List.of(first, overlapping)));
        assertThrows(IllegalArgumentException.class, () ->
                new FieldHighlight("", List.of(first)));
        assertThrows(IllegalArgumentException.class, () ->
                new FieldHighlight("value", List.of()));
        FieldHighlight field = new FieldHighlight("value", List.of(first));
        assertThrows(NullPointerException.class, () ->
                new HighlightedSearchHit<String>(null, List.of()));
        assertThrows(IllegalArgumentException.class, () ->
                new HighlightedSearchHit<>(
                        new SearchHit<>("x", 0.0),
                        List.of(field, field)
                ));
        assertThrows(NullPointerException.class, () ->
                new HighlightedSearchResult<String>(Arrays.asList(
                        (HighlightedSearchHit<String>) null
                )));
    }
}
