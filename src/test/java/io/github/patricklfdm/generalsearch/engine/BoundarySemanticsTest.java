package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.math.BigDecimal;
import java.util.List;
import java.util.concurrent.CompletionException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;

class BoundarySemanticsTest {
    private static final Field<BoundaryItem, Long> ID =
            Field.of("id", Long.class, BoundaryItem::id);
    private static final Field<BoundaryItem, String> TEXT =
            Field.of("text", String.class, BoundaryItem::text);
    private static final Field<BoundaryItem, Double> SCORE =
            Field.of("score", Double.class, BoundaryItem::score);

    @Test
    void nullableFieldsAreSkippedByIndexesWithoutChangingQuerySemantics() {
        try (SearchEngine<Long, BoundaryItem> engine = boundaryEngine()) {
            BoundaryItem missing = new BoundaryItem(1L, null, null);
            BoundaryItem present = new BoundaryItem(2L, "Alpha", 10.0);
            engine.add(missing).join();
            engine.add(present).join();

            assertEquals(List.of(missing), engine.search(Query.eq(TEXT, null)));
            assertEquals(List.of(present), engine.search(Query.prefix(TEXT, "")));
            assertEquals(List.of(present), engine.search(Query.between(SCORE, 0.0, 20.0)));

            BoundaryItem indexed = new BoundaryItem(1L, "Beta", 15.0);
            engine.update(indexed).join();
            assertEquals(List.of(indexed), engine.search(Query.eq(TEXT, "Beta")));
            assertEquals(List.of(indexed), engine.search(Query.between(SCORE, 15.0, 15.0)));

            BoundaryItem nullableAgain = new BoundaryItem(1L, null, null);
            engine.update(nullableAgain).join();
            assertEquals(List.of(nullableAgain), engine.search(Query.eq(TEXT, null)));
            assertEquals(List.of(), engine.search(Query.eq(TEXT, "Beta")));
        }
    }

    @Test
    void nullDocumentsAndIdsAreRejectedAtTheirDocumentedBoundary() {
        try (SearchEngine<Long, BoundaryItem> engine = boundaryEngine()) {
            assertThrows(NullPointerException.class, () -> engine.add(null));
            assertThrows(NullPointerException.class, () -> engine.update(null));
            assertThrows(NullPointerException.class, () -> engine.remove(null));
            assertThrows(NullPointerException.class, () -> engine.get(null));

            CompletionException failure = assertThrows(
                    CompletionException.class,
                    () -> engine.add(new BoundaryItem(null, "value", 1.0)).join());
            assertInstanceOf(NullPointerException.class, failure.getCause());
            assertEquals(0, engine.metrics().documentCount());
        }
    }

    @Test
    void engineRetainsReferencesAndUpdateWithAReplacementPreservesIndexes() {
        Field<MutableItem, Long> id = Field.of("id", Long.class, MutableItem::id);
        Field<MutableItem, String> label =
                Field.of("label", String.class, MutableItem::label);
        try (SearchEngine<Long, MutableItem> engine = SearchEngine
                .builder(MutableItem.class, id)
                .index(IndexDefinition.equality(label))
                .build()) {
            MutableItem original = new MutableItem(1L, "old");
            engine.add(original).join();
            assertSame(original, engine.get(1L));
            assertSame(original, engine.search(Query.eq(label, "old")).getFirst());

            MutableItem replacement = new MutableItem(1L, "new");
            engine.update(replacement).join();
            assertSame(replacement, engine.get(1L));
            assertEquals(List.of(), engine.search(Query.eq(label, "old")));
            assertEquals(List.of(replacement), engine.search(Query.eq(label, "new")));
        }
    }

    @Test
    void rangesUseInclusiveJavaNaturalOrderingIncludingFloatingPointSpecialValues() {
        try (SearchEngine<Long, BoundaryItem> engine = boundaryEngine()) {
            BoundaryItem negativeInfinity =
                    new BoundaryItem(1L, "negative-infinity", Double.NEGATIVE_INFINITY);
            BoundaryItem negativeZero = new BoundaryItem(2L, "negative-zero", -0.0);
            BoundaryItem positiveZero = new BoundaryItem(3L, "positive-zero", 0.0);
            BoundaryItem positiveInfinity =
                    new BoundaryItem(4L, "positive-infinity", Double.POSITIVE_INFINITY);
            BoundaryItem notANumber = new BoundaryItem(5L, "nan", Double.NaN);
            List.of(negativeInfinity, negativeZero, positiveZero, positiveInfinity, notANumber)
                    .forEach(item -> engine.add(item).join());

            assertEquals(
                    List.of(negativeInfinity, negativeZero, positiveZero, positiveInfinity),
                    engine.search(Query.between(
                            SCORE, Double.NEGATIVE_INFINITY, Double.POSITIVE_INFINITY)));
            assertEquals(List.of(notANumber),
                    engine.search(Query.between(SCORE, Double.NaN, Double.NaN)));
            assertEquals(List.of(negativeZero), engine.search(Query.eq(SCORE, -0.0)));
            assertEquals(List.of(positiveZero), engine.search(Query.eq(SCORE, 0.0)));
            assertEquals(List.of(), engine.search(Query.between(SCORE, 1.0, -1.0)));
        }
    }

    @Test
    void stringsRemainCaseSensitiveAndAreNotUnicodeNormalized() {
        try (SearchEngine<Long, BoundaryItem> engine = boundaryEngine()) {
            BoundaryItem upper = new BoundaryItem(1L, "Alpha", 1.0);
            BoundaryItem lower = new BoundaryItem(2L, "alpha", 2.0);
            BoundaryItem composed = new BoundaryItem(3L, "\u00e9clair", 3.0);
            BoundaryItem decomposed = new BoundaryItem(4L, "e\u0301clair", 4.0);
            List.of(upper, lower, composed, decomposed)
                    .forEach(item -> engine.add(item).join());

            assertEquals(List.of(upper), engine.search(Query.prefix(TEXT, "Al")));
            assertEquals(List.of(lower), engine.search(Query.prefix(TEXT, "al")));
            assertEquals(List.of(composed), engine.search(Query.eq(TEXT, "\u00e9clair")));
            assertEquals(List.of(decomposed),
                    engine.search(Query.eq(TEXT, "e\u0301clair")));
        }
    }

    @Test
    void rangeOrderingDoesNotOverrideObjectsEqualsSemantics() {
        Field<DecimalItem, Long> id = Field.of("id", Long.class, DecimalItem::id);
        Field<DecimalItem, BigDecimal> amount =
                Field.of("amount", BigDecimal.class, DecimalItem::amount);
        try (SearchEngine<Long, DecimalItem> engine = SearchEngine
                .builder(DecimalItem.class, id)
                .index(IndexDefinition.range(amount))
                .build()) {
            DecimalItem oneDecimal =
                    new DecimalItem(1L, new BigDecimal("1.0"));
            DecimalItem twoDecimals =
                    new DecimalItem(2L, new BigDecimal("1.00"));
            engine.add(oneDecimal).join();
            engine.add(twoDecimals).join();

            assertEquals(List.of(oneDecimal),
                    engine.search(Query.eq(amount, new BigDecimal("1.0"))));
            assertEquals(List.of(twoDecimals), engine.search(
                    Query.not(Query.eq(amount, new BigDecimal("1.0")))));

            DecimalItem replacement =
                    new DecimalItem(1L, new BigDecimal("1.00"));
            engine.update(replacement).join();
            assertEquals(List.of(replacement, twoDecimals), engine.search(Query.between(
                    amount, new BigDecimal("1.00"), new BigDecimal("1.00"))));
            assertEquals(List.of(),
                    engine.search(Query.eq(amount, new BigDecimal("1.0"))));
        }
    }

    @Test
    void emptyCompositionAndInternalIdResultOrderAreDeterministic() {
        try (SearchEngine<Long, BoundaryItem> engine = boundaryEngine()) {
            BoundaryItem first = new BoundaryItem(1L, "first", 1.0);
            BoundaryItem second = new BoundaryItem(2L, "second", 2.0);
            BoundaryItem third = new BoundaryItem(3L, "third", 3.0);
            List.of(first, second, third).forEach(item -> engine.add(item).join());

            assertEquals(List.of(first, second, third),
                    engine.search(Query.<BoundaryItem>and()));
            assertEquals(List.of(), engine.search(Query.<BoundaryItem>or()));
            assertEquals(List.of(),
                    engine.search(Query.not(Query.<BoundaryItem>matchAll())));

            BoundaryItem updatedFirst = new BoundaryItem(1L, "updated", 10.0);
            BoundaryItem readdedSecond = new BoundaryItem(2L, "readded", 20.0);
            engine.update(updatedFirst).join();
            engine.remove(2L).join();
            engine.add(readdedSecond).join();

            assertEquals(List.of(updatedFirst, third, readdedSecond),
                    engine.search(Query.matchAll()));
        }
    }

    private static SearchEngine<Long, BoundaryItem> boundaryEngine() {
        return SearchEngine.builder(BoundaryItem.class, ID)
                .index(IndexDefinition.equality(TEXT))
                .index(IndexDefinition.prefix(TEXT))
                .index(IndexDefinition.range(SCORE))
                .build();
    }

    private record BoundaryItem(Long id, String text, Double score) {}

    private record DecimalItem(long id, BigDecimal amount) {}

    private static final class MutableItem {
        private final long id;
        private String label;

        private MutableItem(long id, String label) {
            this.id = id;
            this.label = label;
        }

        private long id() {
            return id;
        }

        private String label() {
            return label;
        }

        @SuppressWarnings("unused")
        private void label(String value) {
            label = value;
        }
    }
}
