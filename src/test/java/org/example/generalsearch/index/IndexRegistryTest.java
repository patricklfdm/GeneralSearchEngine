package org.example.generalsearch.index;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.example.generalsearch.query.CandidateAccuracy;
import org.example.generalsearch.query.CandidateResult;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.schema.Field;
import org.junit.jupiter.api.Test;

class IndexRegistryTest {
    private static final Field<InventoryItem, String> CATEGORY =
            Field.of("category", String.class, InventoryItem::category);
    private static final Field<InventoryItem, Integer> STOCK =
            Field.of("stock", Integer.class, InventoryItem::stock);
    private static final Field<InventoryItem, String> NAME =
            Field.of("name", String.class, InventoryItem::name);

    @Test
    void genericIndexesSupportAnotherDocumentTypeAndPreserveSnapshots() {
        IndexRegistry<InventoryItem> empty = registry();
        IndexRegistryBuilder<InventoryItem> initialBuilder = empty.toBuilder();
        InventoryItem book = new InventoryItem("book", "Book", 10);
        InventoryItem cable = new InventoryItem("electronics", "Cable", 40);
        initialBuilder.add(0, book);
        initialBuilder.add(1, cable);
        IndexRegistry<InventoryItem> first = initialBuilder.build();

        assertCandidate(first, Query.eq(CATEGORY, "book"), 0, true,
                CandidateAccuracy.EXACT);
        assertCandidate(first, Query.eq(STOCK, 10), 0, true,
                CandidateAccuracy.SUPERSET);
        assertCandidate(first, Query.between(STOCK, 20, 50), 1, true,
                CandidateAccuracy.EXACT);
        assertTrue(first.candidates(Query.prefix(NAME, "Ca")).isEmpty());

        InventoryItem updatedBook = new InventoryItem("electronics", "Book", 25);
        IndexRegistryBuilder<InventoryItem> updateBuilder = first.toBuilder();
        updateBuilder.update(0, book, updatedBook);
        updateBuilder.remove(1, cable);
        IndexRegistry<InventoryItem> second = updateBuilder.build();

        assertCandidate(first, Query.eq(CATEGORY, "book"), 0, true,
                CandidateAccuracy.EXACT);
        assertCandidate(second, Query.eq(CATEGORY, "book"), 0, false,
                CandidateAccuracy.EXACT);
        assertCandidate(second, Query.eq(CATEGORY, "electronics"), 0, true,
                CandidateAccuracy.EXACT);
        assertCandidate(second, Query.between(STOCK, 20, 50), 1, false,
                CandidateAccuracy.EXACT);
    }

    @Test
    void nullEqualityFallsBackBecauseNullValuesAreNotIndexed() {
        IndexRegistryBuilder<InventoryItem> builder = registry().toBuilder();
        builder.add(0, new InventoryItem(null, "Unknown", 0));
        IndexRegistry<InventoryItem> indexes = builder.build();

        assertTrue(indexes.candidates(Query.eq(CATEGORY, null)).isEmpty());
    }

    @Test
    void rejectsDuplicateIndexDefinitionsForTheSameFieldAndType() {
        assertThrows(IllegalArgumentException.class, () -> IndexRegistry.create(List.of(
                IndexDefinition.equality(CATEGORY),
                IndexDefinition.equality(CATEGORY)
        )));
    }

    @Test
    void prefersAnExactCandidateWhenEqualSizedIndexesCoexist() {
        IndexRegistryBuilder<InventoryItem> builder = IndexRegistry.create(List.of(
                IndexDefinition.range(STOCK),
                IndexDefinition.equality(STOCK)
        )).toBuilder();
        builder.add(0, new InventoryItem("book", "Book", 10));

        CandidateResult result = builder.build()
                .candidates(Query.eq(STOCK, 10))
                .orElseThrow();

        assertEquals(CandidateAccuracy.EXACT, result.accuracy());
        assertTrue(result.bitmap().get(0));
    }

    private static IndexRegistry<InventoryItem> registry() {
        return IndexRegistry.create(List.of(
                IndexDefinition.equality(CATEGORY),
                IndexDefinition.range(STOCK)
        ));
    }

    private static void assertCandidate(
            IndexRegistry<InventoryItem> indexes,
            Query<InventoryItem> query,
            int docId,
            boolean expected,
            CandidateAccuracy expectedAccuracy
    ) {
        CandidateResult result = indexes.candidates(query).orElseThrow();
        assertEquals(expectedAccuracy, result.accuracy());
        assertEquals(expected, result.bitmap().get(docId));
    }

    private record InventoryItem(String category, String name, Integer stock) {}
}
