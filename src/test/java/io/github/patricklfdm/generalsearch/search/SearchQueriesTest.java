package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class SearchQueriesTest {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void factoriesRetainRawInputAndRejectOnlyNull() {
        assertThrows(NullPointerException.class,
                () -> SearchQueries.text(null, "text"));
        assertThrows(NullPointerException.class,
                () -> SearchQueries.text(TEXT, null));
        assertThrows(NullPointerException.class,
                () -> SearchQueries.phrase(null, "phrase"));
        assertThrows(NullPointerException.class,
                () -> SearchQueries.phrase(TEXT, null));
        assertThrows(NullPointerException.class,
                () -> SearchQueries.phrase(null, "phrase", 0));
        assertThrows(NullPointerException.class,
                () -> SearchQueries.phrase(TEXT, null, 0));
        assertThrows(IllegalArgumentException.class,
                () -> SearchQueries.phrase(null, null, -1));
        assertThrows(NullPointerException.class,
                () -> SearchQueries.fuzzy(null, "fuzzy"));
        assertThrows(NullPointerException.class,
                () -> SearchQueries.fuzzy(TEXT, null));

        assertDoesNotThrow(() -> SearchQueries.text(TEXT, ""));
        assertDoesNotThrow(() -> SearchQueries.phrase(TEXT, ""));
        assertDoesNotThrow(() -> SearchQueries.phrase(TEXT, "", 4));
        assertDoesNotThrow(() -> SearchQueries.fuzzy(TEXT, ""));

        LeafSearchQueryNode<Document> leaf = leaf(
                SearchQueries.phrase(TEXT, "  raw Phrase  "));
        assertSame(TEXT, leaf.field());
        assertEquals("  raw Phrase  ", leaf.text());
        assertEquals(SearchLeafKind.PHRASE, leaf.kind());
        assertEquals(0, leaf.slop());
        assertEquals(
                leaf,
                leaf(SearchQueries.phrase(TEXT, "  raw Phrase  ", 0))
        );
        assertEquals(3, leaf(SearchQueries.phrase(TEXT, "phrase", 3)).slop());
    }

    @Test
    void factoriesDoNotAnalyzeDuringPhaseZeroConstruction() {
        AtomicInteger calls = new AtomicInteger();
        Analyzer analyzer = text -> {
            calls.incrementAndGet();
            return List.of(new Token(text));
        };
        TextField<Document> counting = TextField.of(BODY, analyzer);

        SearchQueries.text(counting, "text");
        SearchQueries.phrase(counting, "two terms");
        SearchQueries.phrase(counting, "sloppy terms", 2);
        SearchQueries.fuzzy(counting, "also two terms");

        assertEquals(0, calls.get());
    }

    @Test
    void boostIsImmutableNestedAndStrictlyPositiveFinite() {
        SearchQuery<Document> base = SearchQueries.text(TEXT, "temple");
        SearchQuery<Document> twice = base.boost(2.0);
        SearchQuery<Document> sixTimes = twice.boost(3.0);

        BoostSearchQueryNode<Document> outer = boost(sixTimes);
        BoostSearchQueryNode<Document> inner = boost(outer.query());
        assertEquals(3.0, outer.multiplier());
        assertEquals(2.0, inner.multiplier());
        assertSame(base, inner.query());

        assertThrows(IllegalArgumentException.class, () -> base.boost(0.0));
        assertThrows(IllegalArgumentException.class, () -> base.boost(-1.0));
        assertThrows(IllegalArgumentException.class, () -> base.boost(Double.NaN));
        assertThrows(IllegalArgumentException.class,
                () -> base.boost(Double.POSITIVE_INFINITY));
        assertThrows(IllegalArgumentException.class,
                () -> base.boost(Double.NEGATIVE_INFINITY));
    }

    @Test
    void boolPreservesOrderDuplicatesNestingAndBuilderSnapshots() {
        SearchQuery<Document> first = SearchQueries.text(TEXT, "first");
        SearchQuery<Document> second = SearchQueries.phrase(TEXT, "second term");
        SearchQueries.BoolBuilder<Document> builder = SearchQueries.<Document>bool()
                .must(first)
                .must(second)
                .should(first);
        SearchQuery<Document> initial = builder.build();
        SearchQuery<Document> third = SearchQueries.fuzzy(TEXT, "third");
        SearchQuery<Document> later = builder.should(third).build();

        BoolSearchQueryNode<Document> initialNode = bool(initial);
        BoolSearchQueryNode<Document> laterNode = bool(later);
        assertEquals(List.of(first, second), initialNode.must());
        assertEquals(List.of(first), initialNode.should());
        assertEquals(null, initialNode.minimumShouldMatch());
        assertEquals(List.of(first, third), laterNode.should());

        SearchQuery<Document> nested = SearchQueries.<Document>bool()
                .must(initial)
                .build()
                .boost(2.0);
        assertSame(initial, bool(boost(nested).query()).must().getFirst());
    }

    @Test
    void boolRejectsNullAndEmptyButRetainsRepeatedOccurrences() {
        SearchQueries.BoolBuilder<Document> empty = SearchQueries.bool();
        assertThrows(IllegalStateException.class, empty::build);
        assertThrows(NullPointerException.class, () -> empty.must(null));
        assertThrows(NullPointerException.class, () -> empty.should(null));

        SearchQuery<Document> repeated = SearchQueries.text(TEXT, "same");
        BoolSearchQueryNode<Document> node = bool(SearchQueries.<Document>bool()
                .must(repeated)
                .must(repeated)
                .should(repeated)
                .build());
        assertEquals(List.of(repeated, repeated), node.must());
        assertEquals(List.of(repeated), node.should());
    }

    @Test
    void minimumShouldMatchValidatesShapeAndFreezesBuilderSnapshots() {
        SearchQuery<Document> first = SearchQueries.text(TEXT, "first");
        SearchQuery<Document> second = SearchQueries.text(TEXT, "second");
        SearchQueries.BoolBuilder<Document> builder = SearchQueries.<Document>bool()
                .should(first)
                .should(second)
                .minimumShouldMatch(1);
        SearchQuery<Document> oneRequired = builder.build();
        SearchQuery<Document> twoRequired = builder
                .minimumShouldMatch(2)
                .build();
        assertEquals(1, bool(oneRequired).minimumShouldMatch());
        assertEquals(2, bool(twoRequired).minimumShouldMatch());

        assertThrows(
                IllegalArgumentException.class,
                () -> builder.minimumShouldMatch(-1)
        );
        assertEquals(2, bool(builder.build()).minimumShouldMatch());

        SearchQueries.BoolBuilder<Document> aboveCount = SearchQueries
                .<Document>bool()
                .should(first)
                .minimumShouldMatch(2);
        assertThrows(IllegalArgumentException.class, aboveCount::build);
        assertDoesNotThrow(() -> aboveCount.should(second).build());

        assertThrows(
                IllegalArgumentException.class,
                () -> SearchQueries.<Document>bool()
                        .should(first)
                        .minimumShouldMatch(0)
                        .build()
        );
        assertDoesNotThrow(() -> SearchQueries.<Document>bool()
                .must(first)
                .minimumShouldMatch(0)
                .build());

        SearchQueries.BoolBuilder<Document> empty = SearchQueries
                .<Document>bool()
                .minimumShouldMatch(0);
        assertThrows(IllegalStateException.class, empty::build);
    }

    @SuppressWarnings("unchecked")
    private static LeafSearchQueryNode<Document> leaf(SearchQuery<Document> query) {
        return (LeafSearchQueryNode<Document>) query.node();
    }

    @SuppressWarnings("unchecked")
    private static BoolSearchQueryNode<Document> bool(SearchQuery<Document> query) {
        return (BoolSearchQueryNode<Document>) query.node();
    }

    @SuppressWarnings("unchecked")
    private static BoostSearchQueryNode<Document> boost(SearchQuery<Document> query) {
        return (BoostSearchQueryNode<Document>) query.node();
    }

    private record Document(String body) {
    }
}
